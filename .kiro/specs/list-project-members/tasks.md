# Tasks

## Task 1: Implement client method and filter function
- [x] 1.1 Add `get_project_memberships(self, project_id: int, limit: int = 200)` method to `OpenProjectClient` class after `get_activities()`. It should call `self._collect_collection("/api/v3/memberships", params={"filters": json.dumps([{"project": {"operator": "=", "values": [str(project_id)]}}])}, limit=limit)`.
- [x] 1.2 Add `filter_members(members, query)` function near `filter_users()`. Case-insensitive substring match on `link_title(member, "principal")`. Return all members if query is None/empty.

## Task 2: Implement formatter function
- [x] 2.1 Add `print_members(members)` function near `print_users()`. Print table with columns: ID, Name, Roles. Extract name via `link_title(item, "principal")`, ID via `extract_numeric_id_from_href(href, "users")` from `_links.principal.href`, roles by joining `[r.get("title", "-") for r in item.get("_links", {}).get("roles", [])]` with `, `. Use `truncate()` for name (32 chars) and roles (40 chars). Print "No members found." for empty list.

## Task 3: Implement command function and parser registration
- [x] 3.1 Add `command_list_project_members(args)` function near `command_list_users()`. Use `require_project(args.project)`, `client.resolve_project()`, `client.get_project_memberships()`, `filter_members()`, print project header, `print_members()`, `maybe_print_json()`.
- [x] 3.2 Register `list-project-members` subparser in `build_parser()` after the `list-users` block, before `list-relations`. Add `--project`, `--query`, `--limit` (type=int, default=200) arguments. Set defaults func to `command_list_project_members`.

## Task 4: Unit tests
- [x] 4.1 Create `tests/test_project_members.py` with unit tests for: client method (`get_project_memberships` calls `_collect_collection` correctly), filter function (empty query, matching, no matches), formatter (empty list, single member, multiple roles), command (success output, debug-json, error propagation), and parser registration (`list-project-members` parses with all args).

## Task 5: Property-based tests
- [x] 5.1 Create `tests/test_project_members_properties.py` with property tests using hypothesis. Property 1: client method API call construction. Property 2: formatter output contains all required fields. Property 3: filter returns only matching members. Property 4: command output includes project header. Use `@settings(max_examples=100)` and `from_regex` strategies.

## Task 6: Checkpoint — run full test suite
- [x] 6.1 Run `python -m unittest discover -s tests -p "test_project_members.py"` and `python -m pytest tests/test_project_members_properties.py -v` to verify all tests pass. Fix any failures.

## Task 7: Update documentation
- [x] 7.1 Update `SKILL.md` to add `list-project-members` to Supported Operations with description and agent behavior guidance.
- [x] 7.2 Update `README.md` Command Reference table to include `list-project-members` with its arguments and description.
