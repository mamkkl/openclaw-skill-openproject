# Design Document: wp-attachments

## Overview

This feature adds file attachment support to the OpenProject CLI. Three new commands are introduced: `upload-attachment`, `list-attachments`, and `download-attachment`. A new `format_file_size` helper converts byte counts to human-readable strings. The implementation follows the established single-file CLI pattern — client methods on `OpenProjectClient`, standalone formatter/helper functions, command functions, and argparse subparser registration — all in `scripts/openproject_cli.py`.

The key design challenge is that the existing `_request` method sends `json=payload` (Content-Type: application/json), but the OpenProject attachments upload endpoint requires `multipart/form-data` with two parts: a `metadata` JSON blob and a `file` binary part. A new `upload_attachment` method on `OpenProjectClient` will use the `requests` library's `files=` parameter directly, bypassing `_request` for the upload call while reusing the session's auth configuration.

## Architecture

The feature adds four layers of code, consistent with every prior CLI feature:

```
┌─────────────────────────────────────────────────────┐
│  argparse subparsers (build_parser)                 │
│  upload-attachment, list-attachments,                │
│  download-attachment                                │
├─────────────────────────────────────────────────────┤
│  Command functions                                  │
│  command_upload_attachment, command_list_attachments,│
│  command_download_attachment                        │
├─────────────────────────────────────────────────────┤
│  Formatter / Helper functions                       │
│  print_attachments, format_file_size                │
├─────────────────────────────────────────────────────┤
│  OpenProjectClient methods                          │
│  upload_attachment, list_attachments,               │
│  get_attachment, download_attachment_content         │
└─────────────────────────────────────────────────────┘
```

Data flows top-down: argparse → command function → client method → OpenProject API v3. Formatters are called by command functions to display results.

## Components and Interfaces

### Client Methods (on `OpenProjectClient`)

#### `upload_attachment(self, work_package_id: int, file_path: str, description: str = "") -> Dict[str, Any]`

Uploads a single file to a work package.

- Builds the multipart request with two parts:
  - `metadata`: a JSON string `{"fileName": "<basename>", "description": "<desc>"}` sent as content type `application/json`.
  - `file`: the binary file content with the original filename.
- Uses `self.session.request("POST", url, files=...)` directly (not `_request`) because `_request` forces `json=` serialization.
- The URL is `{self.base_url}/api/v3/work_packages/{id}/attachments` — constructed manually since we bypass `_request`.
- Checks response status (200 or 201) and raises `OpenProjectError` on failure using `extract_error_message`.
- Returns the parsed JSON response (attachment resource).

#### `list_attachments(self, work_package_id: int) -> List[Dict[str, Any]]`

Fetches all attachments for a work package.

- Calls `_request("GET", f"/work_packages/{work_package_id}/attachments")`.
- Extracts elements from `_embedded.elements` using `extract_embedded_elements`.
- Returns the list of attachment dicts.

Note: The attachments endpoint returns all attachments in a single response (no pagination needed for typical work packages), so `_request` is sufficient — no need for `_collect_collection`.

#### `get_attachment(self, attachment_id: int) -> Dict[str, Any]`

Fetches metadata for a single attachment.

- Calls `_request("GET", f"/attachments/{attachment_id}")`.
- Returns the attachment resource dict.

#### `download_attachment_content(self, download_url: str) -> bytes`

Downloads the binary content from a download location URL.

- The `download_url` comes from `attachment["_links"]["downloadLocation"]["href"]`.
- If the URL is absolute (starts with `http://` or `https://`), uses it directly.
- If the URL is a relative API path, prepends `self.base_url` (without `/api/v3` since the download URL already includes the full path).
- Uses `self.session.get(url, timeout=REQUEST_TIMEOUT_SECONDS)` to leverage existing auth. Note: `requests` follows redirects by default (`allow_redirects=True`), so no special redirect handling is needed.
- Checks for 200 status, raises `OpenProjectError` on failure.
- Returns `response.content` (raw bytes).

### Helper Functions

#### `format_file_size(size_bytes: int) -> str`

Converts a byte count to a human-readable string.

- Units: B, KB, MB, GB.
- If `size_bytes < 1024`, returns `"{size_bytes} B"`.
- Otherwise divides by successive powers of 1024 and returns one decimal place (e.g., `"1.2 MB"`).
- Handles zero and negative inputs gracefully (returns `"0 B"` for zero, treats negative as `"0 B"`).

### Formatter Functions

#### `print_attachments(attachments: List[Dict[str, Any]]) -> None`

Displays a formatted table of attachments.

- Columns: ID, File Name, Size, Content Type, Created.
- Size is formatted using `format_file_size`.
- Created date is formatted using the existing `format_date` helper.
- Uses the same `print()` tabular style as `print_work_packages`, `print_members`, etc.

### Command Functions

#### `command_upload_attachment(args: argparse.Namespace) -> None`

Handles the `upload-attachment` subcommand.

- Validates each `--file` path before uploading:
  - Checks existence (`Path.exists()`).
  - Checks it's a file, not a directory (`Path.is_file()`).
  - Warns on zero-byte files but proceeds.
- If all files fail validation, exits with non-zero status (no API calls made).
- Uploads each valid file sequentially, one API call per file.
- On per-file upload failure: prints the error, sets a failure flag, continues with remaining files.
- On success per file: prints confirmation with attachment ID, file name, and size.
- If the work package doesn't exist or the user lacks permission (404/403 on any upload call), reports error and stops immediately — does not attempt remaining files.
- Supports `--description` applied to all files in the batch.
- Calls `maybe_print_json` with the upload response when `--debug-json` is set.
- Returns non-zero exit code if any file failed.

#### `command_list_attachments(args: argparse.Namespace) -> None`

Handles the `list-attachments` subcommand.

- Fetches attachments via `client.list_attachments(args.id)`.
- If empty, prints "No attachments found for work package #N."
- Otherwise calls `print_attachments`.
- Calls `maybe_print_json` with raw data when `--debug-json` is set.

#### `command_download_attachment(args: argparse.Namespace) -> None`

Handles the `download-attachment` subcommand.

- Fetches attachment metadata via `client.get_attachment(args.id)`.
- Extracts download URL from `_links.downloadLocation.href`.
- Determines output path:
  - If `--output` provided, uses that path.
  - Otherwise uses the attachment's `fileName` in the current working directory.
- Validates the output path's parent directory exists before downloading.
- Downloads content via `client.download_attachment_content(url)`.
- Writes bytes to the output file.
- Prints confirmation with file name, bytes written, and output path.

### Argparse Registration (in `build_parser`)

Three new subparsers:

```
upload-attachment --id <wp_id> --file <path> [--file <path> ...] [--description "..."]
list-attachments --id <wp_id>
download-attachment --id <attachment_id> [--output <path>]
```

- `--id` uses `type=positive_int, required=True` for all three (reuses existing `positive_int` argparse type to reject zero/negative IDs).
- `--file` uses `action="append", required=True` on `upload-attachment` to support multiple files.
- `--description` is optional on `upload-attachment`.
- `--output` is optional on `download-attachment`.
- `--debug-json` is already a global parser argument — not re-added.

## Data Models

### Attachment Resource (from OpenProject API v3)

```json
{
  "id": 42,
  "fileName": "report.pdf",
  "fileSize": 125432,
  "contentType": "application/pdf",
  "description": { "format": "markdown", "raw": "Q3 report", "html": "<p>Q3 report</p>" },
  "createdAt": "2026-03-15T10:30:00Z",
  "_links": {
    "self": { "href": "/api/v3/attachments/42" },
    "downloadLocation": { "href": "https://storage.example.com/attachments/42/report.pdf" },
    "container": { "href": "/api/v3/work_packages/123" }
  }
}
```

Key fields used by the CLI:
- `id` — displayed in list and upload confirmation.
- `fileName` — displayed in list, used as default download filename.
- `fileSize` — displayed via `format_file_size`.
- `contentType` — displayed in list.
- `createdAt` — displayed in list via `format_date`.
- `_links.downloadLocation.href` — used by download command.

### Upload Multipart Request Structure

```
POST /api/v3/work_packages/{id}/attachments
Content-Type: multipart/form-data

Part 1 (metadata):
  Content-Disposition: form-data; name="metadata"
  Content-Type: application/json
  {"fileName": "report.pdf", "description": "Q3 report"}

Part 2 (file):
  Content-Disposition: form-data; name="file"; filename="report.pdf"
  Content-Type: application/octet-stream
  <binary content>
```

In Python `requests`, this translates to:

```python
files = {
    "metadata": (None, json.dumps(metadata), "application/json"),
    "file": (file_name, file_handle, "application/octet-stream"),
}
response = self.session.post(url, files=files)
```


## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Upload confirmation contains required fields

*For any* successful upload response containing an attachment ID, file name, and file size, the printed confirmation message SHALL contain all three values as substrings.

**Validates: Requirements 1.3**

### Property 2: Description propagated to upload metadata

*For any* non-empty description string provided via `--description`, the metadata JSON sent in the multipart upload request SHALL contain that exact description value. When no description is provided, the metadata SHALL contain an empty string for the description field.

**Validates: Requirements 1.5, 1.6**

### Property 3: Attachment formatter displays all required fields

*For any* attachment dict containing an `id`, `fileName`, `fileSize`, `contentType`, and `createdAt`, the output of `print_attachments` SHALL contain the attachment ID, file name, human-readable file size, content type, and formatted creation date as substrings.

**Validates: Requirements 2.2**

### Property 4: Download confirmation contains required fields

*For any* successful download with a file name, byte count written, and output path, the printed confirmation message SHALL contain all three values as substrings.

**Validates: Requirements 3.2**

### Property 5: format_file_size unit correctness

*For any* non-negative integer byte count, `format_file_size` SHALL return a string ending with a valid unit suffix (B, KB, MB, or GB), and the unit SHALL correspond to the correct magnitude: "B" for values in [0, 1024), "KB" for values in [1024, 1024²), "MB" for values in [1024², 1024³), and "GB" for values ≥ 1024³.

**Validates: Requirements 4.1, 4.2, 4.3**

### Property 6: format_file_size round-trip consistency

*For any* non-negative integer byte count, formatting with `format_file_size` then parsing the numeric portion and multiplying by the unit's power of 1024 SHALL produce a value within rounding tolerance (±0.5 of the smallest displayed unit) of the original byte count.

**Validates: Requirements 4.4**

### Property 7: File name resolved from basename

*For any* file path string containing directory separators, the file name used in the upload metadata SHALL equal the base name (last path component) of the provided path.

**Validates: Requirements 5.3**

## Error Handling

Error handling follows the established CLI patterns:

### API Errors (upload_attachment)

Since `upload_attachment` bypasses `_request`, it must replicate the same error handling:
- Check `response.status_code` against expected values (200, 201).
- On 401/403: raise `OpenProjectError` with the standard auth-failure message.
- On other errors: call `extract_error_message(response)` and raise `OpenProjectError` with status code and detail.
- On `requests.RequestException`: raise `OpenProjectError` with a network error message.

### API Errors (other methods)

`list_attachments`, `get_attachment` use `_request`, which already handles all error cases consistently.

### Download Errors (download_attachment_content)

- Uses `self.session.get()` directly (the download URL may be absolute/external).
- Checks for 200 status; raises `OpenProjectError` on failure.
- Wraps `requests.RequestException` in `OpenProjectError`.

### File Validation Errors (command_upload_attachment)

- Non-existent path: prints error, skips file, continues.
- Path is a directory: prints error, skips file, continues.
- Zero-byte file: prints warning, proceeds with upload.
- All files invalid: exits with non-zero status, no API calls made.

### Download Path Errors (command_download_attachment)

- Parent directory doesn't exist: prints error, exits with non-zero status before any network call.

### Partial Failure (batch upload)

- Each file upload is independent. On per-file failure, the error is printed and a failure flag is set.
- After all files are processed, if any failed, the command returns a non-zero exit code.

## Testing Strategy

### Property-Based Tests (Hypothesis)

Library: `hypothesis` (already used in this project for prior features).

Each correctness property maps to a single Hypothesis test in `tests/test_attachments_properties.py`. Tests use `@settings(max_examples=100)` for sufficient coverage.

| Property | Test Strategy |
|----------|--------------|
| Property 1: Upload confirmation fields | Generate random attachment ID (int), file name (text), file size (int). Simulate the confirmation print and assert all three appear in output. |
| Property 2: Description in metadata | Generate random description strings. Call `upload_attachment` with a mocked session, capture the `files=` argument, parse the metadata JSON, and assert the description matches. |
| Property 3: Formatter displays fields | Generate random attachment dicts with valid fields. Call `print_attachments`, capture stdout, assert all field values appear. |
| Property 4: Download confirmation fields | Generate random file name, byte count, output path. Simulate the confirmation print and assert all three appear. |
| Property 5: Unit correctness | Generate random non-negative integers. Call `format_file_size`, parse the unit suffix, and assert it matches the expected magnitude range. |
| Property 6: Round-trip consistency | Generate random non-negative integers. Call `format_file_size`, parse numeric value and unit, reconstruct byte count, assert within tolerance. |
| Property 7: Basename resolution | Generate random path strings with directory components. Assert the metadata file name equals `os.path.basename(path)`. |

Each test is tagged with: `# Feature: wp-attachments, Property {N}: {title}`

### Unit Tests (unittest)

Unit tests in `tests/test_attachments.py` cover specific examples and edge cases:

- `format_file_size`: exact values (0, 1, 1023, 1024, 1048576, 1073741824).
- `print_attachments`: empty list prints "no attachments" message.
- `command_upload_attachment`: file not found skips and continues.
- `command_upload_attachment`: directory path skips and continues.
- `command_upload_attachment`: all files invalid exits without API calls.
- `command_upload_attachment`: partial failure continues and reports.
- `command_list_attachments`: empty result prints message.
- `command_download_attachment`: missing parent directory prints error.
- `command_download_attachment`: omitted --output uses original filename.
- `upload_attachment` client method: correct multipart structure.
- `download_attachment_content`: handles absolute and relative URLs.

Tests use the established patterns: `importlib.util` for module loading, `MagicMock` for client, `io.StringIO` + `contextlib.redirect_stdout` for output capture, `patch.object(cli, 'build_client_from_env')` for command-level mocking.
