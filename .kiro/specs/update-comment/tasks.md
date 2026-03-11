# Tasks: update-comment

- [x] 1 Implement `positive_int` helper and `update_comment` client method
  - [x] 1.1 Add `positive_int(value: str) -> int` helper function near other helpers in `scripts/openproject_cli.py`
  - [x] 1.2 Add `OpenProjectClient.update_comment(activity_id: int, comment: str) -> Dict[str, Any]` method immediately after `add_comment()`
- [x] 2 Implement CLI command and parser registration
  - [x] 2.1 Add `command_update_comment(args: argparse.Namespace) -> None` immediately after `command_add_comment()`
  - [x] 2.2 Register `update-comment` subparser in `build_parser()` after the `list-comments` block, using `positive_int` type for `--id`
- [x] 3 Checkpoint: syntax check and manual smoke test
- [x] 4 Write unit tests
  - [x] 4.1 Create `tests/test_update_comment.py` with unit tests for `positive_int`, parser registration, command success, debug-json output, error propagation, 403, and 404 cases
- [x] 5 Write property tests
  - [x] 5.1 Create `tests/test_update_comment_properties.py` with Property 1 (PATCH request construction and return value)
  - [x] 5.2 Add Property 2 (confirmation message includes activity ID)
  - [x] 5.3 Add Property 3 (parser rejects non-positive integer IDs)
  - [x] 5.4 Add Property 4 (whitespace-only comments are rejected)
- [x] 6 Checkpoint: run full test suite (unittest + pytest)
- [x] 7 Update documentation
  - [x] 7.1 Add `update-comment` to SKILL.md Supported Operations and agent behavior guidance
  - [x] 7.2 Update README.md if it documents CLI commands
