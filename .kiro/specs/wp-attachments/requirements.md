# Requirements Document

## Introduction

Add file attachment support to work packages in the OpenProject CLI (`scripts/openproject_cli.py`). This feature enables users to upload files to work packages, list existing attachments, and download attachment content — all through the existing CLI interface. The implementation uses the OpenProject API v3 attachments endpoints and follows the established single-file CLI patterns (client methods, command functions, formatters, argparse subparsers).

## Glossary

- **CLI**: The command-line interface implemented in `scripts/openproject_cli.py`.
- **OpenProjectClient**: The Python class in the CLI that wraps OpenProject API v3 HTTP calls.
- **Attachment**: A file associated with a work package, stored by OpenProject and accessible via the attachments API.
- **Work_Package**: An OpenProject work item (task, bug, feature, etc.) identified by a numeric ID.
- **Multipart_Upload**: An HTTP `multipart/form-data` request containing a `metadata` JSON part and a `file` binary part, as required by the OpenProject attachments upload endpoint.
- **Attachment_Formatter**: A display function that prints attachment metadata (ID, file name, size, content type, description, creation date) to stdout.
- **Download_Location**: The URL provided in an attachment's `_links.downloadLocation.href` field, used to retrieve the file content.

## Requirements

### Requirement 1: Upload Files to a Work Package

**User Story:** As a CLI user, I want to upload one or more files to a work package, so that I can attach documents, screenshots, or other files to track alongside the work item.

#### Acceptance Criteria

1. WHEN the user invokes `upload-attachment --id <wp_id> --file <path>`, THE CLI SHALL read the file at `<path>` and upload it to the specified work package using the OpenProject API v3 `POST /api/v3/work_packages/{id}/attachments` endpoint with a `multipart/form-data` request.
2. WHEN the user provides multiple `--file` flags (e.g., `--file a.pdf --file b.png`), THE CLI SHALL upload each file sequentially to the same work package, issuing one API call per file.
3. WHEN an upload succeeds, THE CLI SHALL print a confirmation message per file containing the attachment ID, file name, and file size.
4. WHEN uploading multiple files and one file fails, THE CLI SHALL report the error for that file and continue uploading the remaining files, then exit with a non-zero status code.
5. WHERE the user provides `--description "..."`, THE CLI SHALL include the description in the upload metadata for all files in the batch.
6. WHEN the user omits `--description`, THE CLI SHALL send each upload with an empty description.
7. IF a specified file path does not exist or is not readable, THEN THE CLI SHALL skip that file, print a clear error message, and continue with the remaining files.
8. IF the specified work package ID does not exist, THEN THE CLI SHALL report the API error message to the user and stop (since all files target the same WP).
9. IF the user lacks permission to add attachments, THEN THE CLI SHALL report the authentication or permission error clearly.
10. THE OpenProjectClient SHALL provide an `upload_attachment` method that sends the multipart request using the `requests` library `files=` parameter, bypassing the existing `_request` method's `json=` serialization.

### Requirement 2: List Attachments on a Work Package

**User Story:** As a CLI user, I want to list all attachments on a work package, so that I can see what files are associated with a work item.

#### Acceptance Criteria

1. WHEN the user invokes `list-attachments --id <wp_id>`, THE CLI SHALL fetch attachments from the OpenProject API v3 `GET /api/v3/work_packages/{id}/attachments` endpoint and display them.
2. THE Attachment_Formatter SHALL display each attachment with its ID, file name, file size (human-readable), content type, and creation date.
3. WHEN the work package has no attachments, THE CLI SHALL print a message indicating no attachments were found.
4. IF the specified work package ID does not exist, THEN THE CLI SHALL report the API error message to the user.
5. THE OpenProjectClient SHALL provide a `list_attachments` method that retrieves the attachment collection for a given work package ID.

### Requirement 3: Download an Attachment

**User Story:** As a CLI user, I want to download an attachment by its ID, so that I can retrieve files attached to work packages.

#### Acceptance Criteria

1. WHEN the user invokes `download-attachment --id <attachment_id> --output <path>`, THE CLI SHALL fetch the attachment metadata from `GET /api/v3/attachments/{id}`, extract the download URL from `_links.downloadLocation.href`, download the file content, and write it to `<path>`.
2. WHEN the download succeeds, THE CLI SHALL print a confirmation message containing the file name, file size in bytes written, and the output path.
3. WHEN the user omits `--output`, THE CLI SHALL save the file to the current working directory using the original file name from the attachment metadata.
4. IF the output path's parent directory does not exist, THEN THE CLI SHALL print a clear error message and exit with a non-zero status code without making the download request.
5. IF the specified attachment ID does not exist, THEN THE CLI SHALL report the API error message to the user.
6. THE OpenProjectClient SHALL provide a `get_attachment` method that retrieves single attachment metadata by ID.
7. THE OpenProjectClient SHALL provide a `download_attachment_content` method that fetches the binary content from the download location URL, handling any redirects transparently.

### Requirement 4: Human-Readable File Size Formatting

**User Story:** As a CLI user, I want file sizes displayed in human-readable format (e.g., "1.2 MB"), so that I can quickly understand attachment sizes.

#### Acceptance Criteria

1. THE CLI SHALL provide a `format_file_size` helper function that converts a byte count integer into a human-readable string using binary units (B, KB, MB, GB).
2. WHEN the byte count is less than 1024, THE `format_file_size` function SHALL return the value with a "B" suffix.
3. WHEN the byte count is 1024 or greater, THE `format_file_size` function SHALL divide by successive powers of 1024 and return a value with one decimal place and the appropriate unit suffix.
4. FOR ALL non-negative integer byte counts, formatting then parsing the numeric portion SHALL produce a value within rounding tolerance of the original (round-trip consistency).

### Requirement 5: File Validation Before Upload

**User Story:** As a CLI user, I want the CLI to validate the file before attempting upload, so that I get fast, clear feedback on local errors without waiting for a network round-trip.

#### Acceptance Criteria

1. WHEN the user provides a `--file` path that points to a directory instead of a file, THE CLI SHALL print an error message stating that the path is a directory and skip that file.
2. WHEN the user provides a `--file` path to a file with zero bytes, THE CLI SHALL print a warning but proceed with the upload (OpenProject may accept or reject empty files server-side).
3. THE CLI SHALL resolve the file name for the upload metadata from the base name of the provided path (e.g., `/docs/report.pdf` yields `report.pdf`).
4. WHEN all provided `--file` paths fail validation (none are uploadable), THE CLI SHALL exit with a non-zero status code without making any API calls.

### Requirement 6: Consistent Error Handling

**User Story:** As a CLI user, I want attachment commands to handle errors consistently with existing CLI commands, so that the experience is predictable.

#### Acceptance Criteria

1. WHEN an API call for any attachment operation returns an HTTP error status, THE CLI SHALL extract the error message using the existing `extract_error_message` helper and raise an `OpenProjectError`.
2. WHEN a network error occurs during any attachment operation, THE CLI SHALL raise an `OpenProjectError` with a descriptive network error message.
3. WHEN `--debug-json` is provided, THE CLI SHALL print the raw JSON response for attachment list and upload operations, consistent with existing command behavior.
