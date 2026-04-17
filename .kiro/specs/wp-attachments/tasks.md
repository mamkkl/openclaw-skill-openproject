# Implementation Plan: wp-attachments

## Overview

Add file attachment support to the OpenProject CLI. Three new commands (`upload-attachment`, `list-attachments`, `download-attachment`), four client methods, a `format_file_size` helper, and a `print_attachments` formatter — all in `scripts/openproject_cli.py`. Tests in `tests/test_attachments.py` (unit) and `tests/test_attachments_properties.py` (property).

## Tasks

- [x] 1. Add `format_file_size` helper and `print_attachments` formatter
  - [x] 1.1 Implement `format_file_size(size_bytes: int) -> str` in `scripts/openproject_cli.py`
    - Place near existing helper functions (after `format_date` / `truncate` area)
    - Units: B, KB, MB, GB with binary 1024 divisor
    - Returns `"0 B"` for zero or negative inputs
    - One decimal place for KB/MB/GB (e.g., `"1.2 MB"`)
    - _Requirements: 4.1, 4.2, 4.3, 4.4_

  - [x] 1.2 Implement `print_attachments(attachments: List[Dict[str, Any]]) -> None` in `scripts/openproject_cli.py`
    - Place near existing formatter functions (after `print_notifications` / `print_notification_detail`)
    - Columns: ID, File Name, Size (via `format_file_size`), Content Type, Created (via `format_date`)
    - Follow the same tabular `print()` style as `print_work_packages`, `print_members`, etc.
    - _Requirements: 2.2_

  - [x] 1.3 Write property test: Property 5 (format_file_size unit correctness)
    - **Property 5: format_file_size unit correctness**
    - **Validates: Requirements 4.1, 4.2, 4.3**
    - File: `tests/test_attachments_properties.py`
    - Strategy: `st.integers(min_value=0, max_value=10**12)` for byte counts
    - Assert returned string ends with valid unit suffix matching the correct magnitude range

  - [x] 1.4 Write property test: Property 6 (format_file_size round-trip consistency)
    - **Property 6: format_file_size round-trip consistency**
    - **Validates: Requirements 4.4**
    - File: `tests/test_attachments_properties.py`
    - Parse numeric portion and unit, reconstruct byte count, assert within rounding tolerance

  - [x] 1.5 Write property test: Property 3 (attachment formatter displays all required fields)
    - **Property 3: Attachment formatter displays all required fields**
    - **Validates: Requirements 2.2**
    - File: `tests/test_attachments_properties.py`
    - Generate random attachment dicts with valid `id`, `fileName`, `fileSize`, `contentType`, `createdAt`
    - Call `print_attachments`, capture stdout, assert all field values appear as substrings

- [x] 2. Add client methods on `OpenProjectClient`
  - [x] 2.1 Implement `upload_attachment(self, work_package_id, file_path, description="")` method
    - Place after `list_children` (last current client method)
    - Build multipart request with `metadata` (JSON) and `file` (binary) parts
    - Use `self.session.request("POST", url, files=...)` directly — bypass `_request`
    - URL: `{self.base_url}/api/v3/work_packages/{id}/attachments`
    - Check response status (200/201), raise `OpenProjectError` on failure using `extract_error_message`
    - Handle `requests.RequestException` with `OpenProjectError`
    - _Requirements: 1.1, 1.10, 6.1, 6.2_

  - [x] 2.2 Implement `list_attachments(self, work_package_id)` method
    - Call `_request("GET", f"/work_packages/{work_package_id}/attachments")`
    - Extract elements via `extract_embedded_elements`
    - _Requirements: 2.1, 2.5_

  - [x] 2.3 Implement `get_attachment(self, attachment_id)` method
    - Call `_request("GET", f"/attachments/{attachment_id}")`
    - _Requirements: 3.6_

  - [x] 2.4 Implement `download_attachment_content(self, download_url)` method
    - Handle absolute vs relative URLs (prepend `self.base_url` for relative paths, without `/api/v3`)
    - Use `self.session.get(url, timeout=REQUEST_TIMEOUT_SECONDS)`
    - Check for 200 status, raise `OpenProjectError` on failure
    - Return `response.content` (raw bytes)
    - _Requirements: 3.1, 3.7, 6.1, 6.2_

  - [x] 2.5 Write property test: Property 2 (description propagated to upload metadata)
    - **Property 2: Description propagated to upload metadata**
    - **Validates: Requirements 1.5, 1.6**
    - File: `tests/test_attachments_properties.py`
    - Strategy: `from_regex` for description strings
    - Mock session, call `upload_attachment`, capture `files=` arg, parse metadata JSON, assert description matches

  - [x] 2.6 Write property test: Property 7 (file name resolved from basename)
    - **Property 7: File name resolved from basename**
    - **Validates: Requirements 5.3**
    - File: `tests/test_attachments_properties.py`
    - Generate path strings with directory components, assert metadata file name equals `os.path.basename(path)`

- [x] 3. Checkpoint
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Add command functions
  - [x] 4.1 Implement `command_upload_attachment(args)` in `scripts/openproject_cli.py`
    - Place after `command_read_all_notifications` (near end of command functions)
    - Validate each `--file` path: existence, is_file, warn on zero-byte
    - If all files fail validation, exit non-zero without API calls
    - Upload each valid file sequentially; on per-file failure print error and continue
    - On 404/403 (WP not found or no permission), stop immediately
    - Print confirmation per file: attachment ID, file name, file size
    - Support `--description` applied to all files
    - Call `maybe_print_json` when `--debug-json` is set
    - Return non-zero exit code if any file failed
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 5.1, 5.2, 5.3, 5.4, 6.3_

  - [x] 4.2 Implement `command_list_attachments(args)` in `scripts/openproject_cli.py`
    - Fetch via `client.list_attachments(args.id)`
    - Empty list: print "No attachments found for work package #N."
    - Otherwise call `print_attachments`
    - Call `maybe_print_json` when `--debug-json` is set
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 6.3_

  - [x] 4.3 Implement `command_download_attachment(args)` in `scripts/openproject_cli.py`
    - Fetch metadata via `client.get_attachment(args.id)`
    - Extract download URL from `_links.downloadLocation.href`
    - Determine output path: `--output` if provided, else `fileName` in cwd
    - Validate parent directory exists before downloading
    - Download content via `client.download_attachment_content(url)`
    - Write bytes to output file
    - Print confirmation: file name, bytes written, output path
    - Call `maybe_print_json` with attachment metadata when `--debug-json` is set
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 6.1, 6.3_

  - [x] 4.4 Write property test: Property 1 (upload confirmation contains required fields)
    - **Property 1: Upload confirmation contains required fields**
    - **Validates: Requirements 1.3**
    - File: `tests/test_attachments_properties.py`
    - Generate random attachment ID (int), file name (text), file size (int)
    - Simulate confirmation print, assert all three appear in output

  - [x] 4.5 Write property test: Property 4 (download confirmation contains required fields)
    - **Property 4: Download confirmation contains required fields**
    - **Validates: Requirements 3.2**
    - File: `tests/test_attachments_properties.py`
    - Generate random file name, byte count, output path
    - Simulate confirmation print, assert all three appear in output

- [x] 5. Register subparsers in `build_parser()`
  - [x] 5.1 Register `upload-attachment` subparser
    - `--id` with `type=positive_int, required=True`
    - `--file` with `action="append", required=True`
    - `--description` optional
    - Do NOT add `--debug-json` (already global)
    - Set `func=command_upload_attachment`
    - _Requirements: 1.1, 1.2, 1.5_

  - [x] 5.2 Register `list-attachments` subparser
    - `--id` with `type=positive_int, required=True`
    - Set `func=command_list_attachments`
    - _Requirements: 2.1_

  - [x] 5.3 Register `download-attachment` subparser
    - `--id` with `type=positive_int, required=True`
    - `--output` optional
    - Set `func=command_download_attachment`
    - _Requirements: 3.1, 3.3_

- [x] 6. Checkpoint
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Write unit tests
  - [x] 7.1 Write unit tests for `format_file_size`
    - File: `tests/test_attachments.py`
    - Test exact values: 0, 1, 1023, 1024, 1048576, 1073741824
    - Test negative input returns `"0 B"`
    - _Requirements: 4.1, 4.2, 4.3_

  - [x] 7.2 Write unit tests for `print_attachments`
    - File: `tests/test_attachments.py`
    - Test empty list prints "no attachments" message
    - Test single attachment displays all columns
    - _Requirements: 2.2, 2.3_

  - [x] 7.3 Write unit tests for `command_upload_attachment`
    - File: `tests/test_attachments.py`
    - Test file not found skips and continues
    - Test directory path skips and continues
    - Test all files invalid exits without API calls
    - Test partial failure continues and reports
    - Use `MagicMock` client, `patch.object(cli, 'build_client_from_env')`
    - _Requirements: 1.4, 1.7, 5.1, 5.4_

  - [x] 7.4 Write unit tests for `command_list_attachments`
    - File: `tests/test_attachments.py`
    - Test empty result prints message
    - _Requirements: 2.3_

  - [x] 7.5 Write unit tests for `command_download_attachment`
    - File: `tests/test_attachments.py`
    - Test missing parent directory prints error
    - Test omitted `--output` uses original filename
    - _Requirements: 3.3, 3.4_

  - [x] 7.6 Write unit tests for client methods
    - File: `tests/test_attachments.py`
    - Test `upload_attachment` sends correct multipart structure
    - Test `download_attachment_content` handles absolute and relative URLs
    - _Requirements: 1.10, 3.7_

- [x] 8. Final checkpoint
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Update documentation
  - [x] 9.1 Update `SKILL.md` with new attachment commands
    - Add `upload-attachment`, `list-attachments`, `download-attachment` to Supported Operations
    - Add agent behavior guidance for attachment operations
    - _Requirements: 1.1, 2.1, 3.1_

  - [x] 9.2 Update `README.md` Command Reference table
    - Add all three new commands with descriptions
    - Audit existing table for any previously missing commands
    - _Requirements: 1.1, 2.1, 3.1_

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- All code goes in `scripts/openproject_cli.py` — single file, no modules
- Test files use `importlib.util` loading, `io.StringIO` for stdout capture, `MagicMock` for client
- Property tests use `hypothesis` with `@settings(max_examples=100)` and `from_regex` strategies
