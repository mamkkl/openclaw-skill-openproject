# Implementation Plan: Work Package Comments

## Overview

Add read-side comment/activity support to the OpenProject CLI. Implementation follows the existing single-file pattern in `scripts/openproject_cli.py`, adding a client method, filtering/formatting helpers, a `list-comments` command, and a comment count in `get-work-package` output. All new functions slot into the existing layered architecture.

## Tasks

- [x] 1. Add `get_activities()` method to `OpenProjectClient`
  - [x] 1.1 Implement `get_activities(self, work_package_id: int, limit: int = 200)` in `scripts/openproject_cli.py`
    - Add method to `OpenProjectClient` class after `add_comment()`
    - Delegate to `self._collect_collection(f"/work_packages/{work_package_id}/activities", limit=limit)`
    - Return `List[Dict[str, Any]]` of activity dicts
    - Error handling inherited from `_request()` / `_collect_collection()` — no new exception types
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

  - [x] 1.2 Write unit tests for `get_activities()`
    - Add tests in `tests/test_comments.py`
    - Load CLI module via `importlib.util` (same pattern as `test_cli_helpers.py`)
    - Mock `_collect_collection` to verify correct endpoint path and limit parameter
    - Test that `OpenProjectError` propagates on HTTP errors
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

- [x] 2. Implement filtering and formatting helpers
  - [x] 2.1 Implement `filter_activities_by_author()` in `scripts/openproject_cli.py`
    - Add as a module-level function near existing `filter_work_packages()` / `filter_users()`
    - Use `link_title(activity, "user")` for author name extraction
    - Case-insensitive substring match on author name
    - Return filtered list preserving original order
    - _Requirements: 5.1, 5.2_

  - [x] 2.2 Implement `format_activity()` in `scripts/openproject_cli.py`
    - Add as a module-level function near existing formatter functions
    - Extract author via `link_title(activity, "user")`
    - Extract date via `format_date(activity.get("createdAt", ""))`
    - Extract comment text via `extract_formattable_text(activity.get("comment"))`
    - When `show_changes=True` and comment is empty, list changed field names from `activity.get("details", [])`
    - Return multi-line formatted string
    - _Requirements: 4.1, 4.2, 4.3_

  - [x] 2.3 Implement `print_activities()` in `scripts/openproject_cli.py`
    - Add near other `print_*` functions
    - Iterate activities, call `format_activity()`, print with `---` separator between entries
    - _Requirements: 4.4_

  - [x] 2.4 Write property test: comment filtering preserves only non-empty comments
    - Create `tests/test_comments_properties.py` with Hypothesis strategies for Activity dicts
    - **Property 1: Comment filtering preserves only non-empty comments**
    - **Validates: Requirements 2.1**

  - [x] 2.5 Write property test: formatted activity contains author, date, and comment text
    - **Property 2: Formatted activity contains author, date, and comment text**
    - **Validates: Requirements 2.2, 4.1**

  - [x] 2.6 Write property test: all-activities mode returns every activity
    - **Property 3: All-activities mode returns every activity**
    - **Validates: Requirements 2.3**

  - [x] 2.7 Write property test: field-change-only activities show changed field names
    - **Property 5: Field-change-only activities show changed field names**
    - **Validates: Requirements 4.3**

  - [x] 2.8 Write property test: author filter returns only matching activities
    - **Property 6: Author filter returns only matching activities**
    - **Validates: Requirements 5.1**

  - [x] 2.9 Write property test: limit returns at most N most-recent entries
    - **Property 7: Limit returns at most N most-recent entries**
    - **Validates: Requirements 6.1**

  - [x] 2.10 Write property test: multiple activities are separated by delimiters
    - **Property 8: Multiple activities are separated by delimiters**
    - **Validates: Requirements 4.4**

- [x] 3. Checkpoint — Verify helpers
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Implement `list-comments` command and argparse registration
  - [x] 4.1 Implement `command_list_comments()` in `scripts/openproject_cli.py`
    - Add near existing command functions (after `command_add_comment()`)
    - Call `client.get_activities(args.id)`
    - Unless `--all`, filter to activities with non-empty comment text via `extract_formattable_text()`
    - Apply `filter_activities_by_author()` if `--author` provided
    - Apply `--limit` by slicing last N entries (most recent)
    - Print "No comments found for work package #{id}." when result is empty (no author filter)
    - Print "No matching comments found." when author filter yields empty result
    - Call `print_activities(activities, show_changes=args.all)`
    - Call `maybe_print_json(raw_data, args.debug_json)` if `--debug-json`
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 5.1, 5.2, 6.1, 6.2_

  - [x] 4.2 Register `list-comments` subcommand in `build_parser()`
    - Add subparser with `--id` (int, required), `--all` (flag), `--author` (str, optional), `--limit` (int, optional), `--debug-json` (flag)
    - Set `func=command_list_comments`
    - Place registration near existing `add-comment` subparser
    - _Requirements: 2.1, 2.3, 5.1, 6.1_

  - [x] 4.3 Write unit tests for `command_list_comments()`
    - Add tests in `tests/test_comments.py`
    - Test empty activity list prints "No comments found" message
    - Test `--author` with no matches prints "No matching comments found."
    - Test `--debug-json` flag triggers JSON output
    - Test `--limit 0` or negative treated as "show all"
    - _Requirements: 2.4, 5.2, 2.5, 6.1_

- [x] 5. Add comment count to `get-work-package` output
  - [x] 5.1 Modify `command_get_work_package()` in `scripts/openproject_cli.py`
    - After existing `print_work_package_detail()` call, fetch activities via `client.get_activities(args.id)`
    - Count activities with non-empty comment text
    - Print `Comments: {count}` line
    - Display "Comments: 0" when no comments exist
    - _Requirements: 3.1, 3.2_

  - [x] 5.2 Write property test: comment count equals number of activities with non-empty comments
    - **Property 4: Comment count equals number of activities with non-empty comments**
    - **Validates: Requirements 3.1, 3.2**

  - [x] 5.3 Write unit tests for comment count in `get-work-package`
    - Test zero comments displays "Comments: 0"
    - Test mixed activities (some with comments, some without) shows correct count
    - _Requirements: 3.1, 3.2_

- [x] 6. Final checkpoint — Full integration
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Property tests use Hypothesis in `tests/test_comments_properties.py`
- Unit tests go in `tests/test_comments.py`, loaded via `importlib.util`
- All code changes are in the single file `scripts/openproject_cli.py`
- Checkpoints ensure incremental validation
