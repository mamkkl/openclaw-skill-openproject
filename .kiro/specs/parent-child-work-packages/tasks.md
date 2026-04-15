# Implementation Plan: Parent-Child Work Packages

## Overview

Add parent-child hierarchy support to the OpenProject CLI in `scripts/openproject_cli.py`. Implementation proceeds bottom-up: pure helpers → client methods → formatters → command functions → argparse registration, with tests interleaved close to each layer. Unit tests go in `tests/test_parent_child.py`, property tests in `tests/test_parent_child_properties.py`.

## Tasks

- [x] 1. Add pure helper functions and argparse type
  - [x] 1.1 Implement `build_parent_href(value)` and `parent_id_or_none(value)`
    - Add `build_parent_href(value: str) -> Optional[str]` near `extract_numeric_id_from_href` in `scripts/openproject_cli.py`
    - Returns `"/api/v3/work_packages/{id}"` for positive integer strings, `None` for case-insensitive `"none"`, raises `ValueError` otherwise
    - Add `parent_id_or_none(value: str) -> str` as an argparse type function nearby
    - Accepts positive integers or case-insensitive `"none"`, raises `argparse.ArgumentTypeError` otherwise
    - _Requirements: 8.1, 8.2, 1.3, 2.3_

  - [x] 1.2 Write property tests for `build_parent_href` and `parent_id_or_none`
    - **Property 1: Parent href round-trip** — `build_parent_href(str(id))` → `extract_numeric_id_from_href(href, "work_packages")` returns original ID. Strategy: `st.integers(min_value=1, max_value=10**9)`
    - **Validates: Requirements 8.1, 8.3**
    - **Property 2: "none" produces null href** — all case variations of `"none"` return `None`. Strategy: `st.sampled_from(...)` over case permutations
    - **Validates: Requirements 3.1, 8.2**
    - **Property 3: Invalid parent values are rejected** — non-integer, non-"none" strings raise `ArgumentTypeError`. Strategy: `st.from_regex(r"[a-zA-Z!@#$%^&*()]{1,20}")` filtered to exclude "none" variants and digit-only strings
    - **Validates: Requirements 1.3, 2.3**
    - Create `tests/test_parent_child_properties.py` with these three property tests
    - Use `@settings(max_examples=100)`, importlib.util loading, `from_regex` strategies

  - [x] 1.3 Write unit tests for `build_parent_href` and `parent_id_or_none`
    - Create `tests/test_parent_child.py`
    - Test `build_parent_href("42")` → `"/api/v3/work_packages/42"`
    - Test `build_parent_href("none")` → `None`
    - Test `build_parent_href("None")` → `None` (case-insensitive)
    - Test `parent_id_or_none("42")` → `"42"`
    - Test `parent_id_or_none("none")` → `"none"`
    - Test `parent_id_or_none("abc")` raises `ArgumentTypeError`
    - Test `parent_id_or_none("-1")` raises `ArgumentTypeError`
    - Test `parent_id_or_none("0")` raises `ArgumentTypeError`
    - Use importlib.util loading pattern
    - _Requirements: 8.1, 8.2, 8.3, 1.3, 2.3_

- [x] 2. Extend client methods for parent support
  - [x] 2.1 Extend `create_work_package` to accept `parent_id`
    - Add `parent_id: Optional[int] = None` parameter to `OpenProjectClient.create_work_package`
    - When `parent_id` is provided, add `"parent": {"href": build_parent_href(str(parent_id))}` to `_links` in the POST payload
    - Use bare path `/work_packages` (already correct — `_request` prepends `/api/v3`)
    - _Requirements: 1.1, 1.2_

  - [x] 2.2 Extend `update_work_package` to accept `parent_ref`
    - Add `parent_ref: Optional[str] = None` parameter to `OpenProjectClient.update_work_package`
    - When `parent_ref` is provided, call `build_parent_href(parent_ref)` and add `"parent": {"href": result}` to `link_updates`
    - A `None` href (from `"none"`) tells the API to unset the parent
    - _Requirements: 2.1, 2.2, 3.1_

  - [x] 2.3 Implement `list_children` client method
    - Add `list_children(self, work_package_id: int, limit: int = 50) -> List[Dict[str, Any]]` to `OpenProjectClient`
    - Use filter parameter: `[{"parent":{"operator":"=","values":["<id>"]}}]`
    - Use `_collect_collection` with bare path `/work_packages` and the filter in params
    - _Requirements: 6.1, 6.4_

- [x] 3. Checkpoint — Verify helpers and client methods
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Update display formatters for parent info
  - [x] 4.1 Update `print_work_package_detail` to show parent
    - After existing fields, add a `Parent:` line when `_links.parent.href` is present and non-null
    - Extract parent ID via `extract_numeric_id_from_href` and show parent title from `_links.parent.title`
    - Omit the `Parent:` line entirely when there is no parent
    - _Requirements: 4.1, 4.2_

  - [x] 4.2 Update `print_work_packages` to show parent column
    - Add a `Parent` column to the table header
    - For each work package, extract parent ID from `_links.parent.href` or display `-` if no parent
    - _Requirements: 5.1, 5.2_

  - [x] 4.3 Write property tests for parent display
    - **Property 4: Detail view parent display** — `print_work_package_detail` includes `Parent:` line iff `_links.parent.href` is non-null string. Composite strategy generating work package dicts with/without parent.
    - **Validates: Requirements 4.1, 4.2**
    - **Property 5: List view parent column** — each row shows parent ID or dash based on `_links.parent.href`. Composite strategy generating lists of work package dicts with mixed parent presence.
    - **Validates: Requirements 5.1, 5.2**
    - Add to `tests/test_parent_child_properties.py`
    - Use `io.StringIO` + `contextlib.redirect_stdout` for stdout capture

  - [x] 4.4 Write unit tests for parent display
    - Test `print_work_package_detail` with parent shows `Parent:` line containing parent ID and title
    - Test `print_work_package_detail` without parent omits `Parent:` line
    - Test `print_work_packages` with parent shows parent ID in row
    - Test `print_work_packages` without parent shows `-` in parent column
    - Add to `tests/test_parent_child.py`
    - _Requirements: 4.1, 4.2, 5.1, 5.2_

- [x] 5. Implement command functions and argparse registration
  - [x] 5.1 Update `command_create_work_package` for `--parent`
    - Pass `parent_id=args.parent` to `client.create_work_package` when provided
    - Display parent work package ID in creation confirmation output when parent is set
    - _Requirements: 1.1, 1.2, 1.4_

  - [x] 5.2 Update `command_update_work_package` for `--parent`
    - Pass `parent_ref=args.parent` to `client.update_work_package` when provided
    - **CRITICAL**: Add `args.parent` to the guard tuple (lines 1721–1730) that checks "at least one field provided" — otherwise `--parent` alone will be rejected with "Provide at least one field to update"
    - Display confirmation when parent is removed (set to `none`)
    - _Requirements: 2.1, 2.2, 2.3, 3.1, 3.2_

  - [x] 5.3 Implement `command_list_children` and register all subparsers
    - Add `command_list_children(args)` — calls `client.list_children(args.id, limit=args.limit)`, prints results via `print_work_packages`, shows "No children found for work package #ID." when empty
    - Register `--parent` on `create-work-package` subparser with `type=positive_int`, optional
    - Register `--parent` on `update-work-package` subparser with `type=parent_id_or_none`, optional
    - Register `list-children` subparser with `--id` (required, `type=positive_int`) and `--limit` (optional, `type=positive_int`, default 50)
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

  - [x] 5.4 Write unit tests for command functions
    - Test `command_create_work_package` with `--parent 42` includes parent in API payload (mock client via `build_client_from_env`)
    - Test `command_create_work_package` without `--parent` omits parent from payload
    - Test `command_update_work_package` with `--parent 42` includes parent href in PATCH payload
    - Test `command_update_work_package` with `--parent none` includes null parent href in PATCH payload
    - Test `command_list_children` with empty result prints "No children found" message
    - Test `command_list_children` with results prints work package table
    - Test API 404 error for non-existent parent surfaces clear message
    - Test API 422 error for circular hierarchy surfaces API rejection reason
    - Add to `tests/test_parent_child.py`
    - Use `MagicMock` for client, `io.StringIO` for stdout capture
    - _Requirements: 1.1, 1.4, 2.1, 3.1, 6.2, 6.3, 7.1, 7.2, 7.3_

- [x] 6. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Update documentation
  - [x] 7.1 Update `SKILL.md` and `README.md`
    - Add `list-children` to Supported Operations in `SKILL.md`
    - Update `create-work-package` and `update-work-package` descriptions to mention `--parent` flag
    - Update `README.md` Command Reference table with new/modified commands
    - Audit the full command table for any previously missing commands
    - _Requirements: 1.1, 2.1, 3.1, 6.1_

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- All code goes in `scripts/openproject_cli.py` — single file per project convention
- Unit tests in `tests/test_parent_child.py`, property tests in `tests/test_parent_child_properties.py`
- `_request()` already prepends `/api/v3` — use bare paths in new client methods
- The `command_update_work_package` guard tuple MUST include `args.parent` (task 5.2)
- Property tests use `hypothesis` with `@settings(max_examples=100)` and `from_regex` strategies
- Both test files use importlib.util loading, io.StringIO for stdout capture, MagicMock for client
