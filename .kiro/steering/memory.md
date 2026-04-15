# Lessons Learned

Observations from building and implementing specs in this project. Use these to avoid repeating mistakes.

## Environment

- This is a Windows machine. Use `python` not `python3`. PowerShell is the shell — avoid bash-isms like `tail`, `&&`, and inline single-quote strings in `-c` flags.
- For complex inline Python checks, write a temp `.py` file and run it instead of fighting PowerShell quoting.
- `unittest` on PowerShell reports stderr even on success (exit code 1 with "OK" output). Check the "OK" / "FAILED" line, not the exit code alone.
- Git commit messages with escaped double quotes (`\"`) fail in PowerShell. Use simple single-line messages or avoid special characters in commit messages.
- `git push` on PowerShell reports stderr (exit code 1) even on success because git writes progress/remote messages to stderr. Verify success by checking `git log --oneline -1` for `origin/master` matching `HEAD`, not the exit code.

## Testing Patterns

- Unit tests use `unittest` and load the CLI via `importlib.util` — never import it as a package.
- Property tests use `hypothesis` (not in `requirements.txt` — install separately with `pip install hypothesis`).
- Property tests run via `pytest`, unit tests via `unittest discover`. Both coexist in `tests/`.
- When capturing stdout in tests, use `io.StringIO` + `contextlib.redirect_stdout`.
- Mock `build_client_from_env` to return a `MagicMock` client for command-level tests. Mock `_collect_collection` on client instances for client-method tests.
- For dynamically-loaded CLI modules, use `patch.object(cli, 'build_client_from_env')` instead of `patch('openproject_cli.build_client_from_env')`. The string-based patch path doesn't work because the module isn't in `sys.modules` under a normal name.

## Code Placement

- All CLI code lives in `scripts/openproject_cli.py` — single file, no modules.
- New filter functions go near `filter_work_packages()` / `filter_users()`.
- New formatter functions go near `print_projects()` / `print_work_packages()`.
- New command functions go near related existing commands (e.g., `command_list_comments` after `command_add_comment`).
- Subparser registration in `build_parser()` should mirror the command function ordering.
- `--debug-json` is a global parser argument — don't re-add it to subparsers.
- When adding an optional `--parent`-style flag that only applies to some subparsers, use `getattr(args, "parent", None)` in the command function instead of `args.parent` directly. This avoids `AttributeError` if the attribute isn't set on the namespace (e.g., when the arg is registered on one subparser but the command function is shared or tested in isolation).

## Subagent Delegation

- For "run all tasks" sessions, handle simple implementation tasks (helpers, client method extensions, formatter tweaks, argparse registration) directly as orchestrator and only delegate test-writing tasks to subagents. This is significantly faster than delegating every task — the parent-child feature completed in one pass with zero retries using this approach.
- Subagents sometimes create code eagerly in earlier tasks. Always check if code already exists before delegating a task — avoids duplicates.
- Watch for nested class bugs: a subagent once placed a test class inside another test class, making it invisible to `unittest discover`. Always verify test discovery count after adding tests.
- Keep subagent prompts specific: include exact line numbers, function signatures, and the surrounding code context. Vague prompts lead to misplaced code.
- For parser registration tasks, read the full `build_parser()` function before delegating so you can specify exact insertion points (e.g., "after the list-comments block, before get-work-package"). This eliminates misplacement entirely.

## Spec Workflow

- Checkpoint tasks (3, 6) are valuable — run the full suite at those points to catch issues early.
- Property tests with `@settings(max_examples=100)` take ~20s on this machine. Budget accordingly.
- Use `from_regex` strategies instead of `st.text().filter(...)` in Hypothesis — much faster generation, avoids health check warnings.

## Subagent Batching

- When multiple tasks share the same output file and strategies (e.g., property tests 2.4–2.10), batch them into a single subagent call. Much faster and avoids merge conflicts in the same file.
- For unit test tasks that add to an existing file, always read the file first and pass its current content in the prompt so the subagent knows where to append.

## Task Queuing

- When queueing all tasks upfront, queue only leaf tasks (sub-tasks without children). Parent tasks get marked complete after all their children finish.
- The `OpenProjectClient.__init__` parameter is `api_token`, not `api_key`. Always check the actual constructor signature before writing test helpers like `_make_client()`.

## Cleanup

- Always delete temp files created during verification (e.g., `_verify.py`). Don't leave artifacts in the project root.
- After a trail run, verify the test discovery count matches expectations (e.g., 19 unit tests + 8 property tests for the comments feature).

## Post-Implementation Checklist

- After adding a new CLI command, always update `SKILL.md`: add the command to Supported Operations, update any modified command descriptions, and add agent behavior guidance if applicable.
- Check if `README.md` also needs corresponding updates (per steering rule in `structure.md`).
- When adding a new command to README's Command Reference table, audit the full table for previously missing commands. The `list-comments` command was missing from the table despite being implemented in an earlier feature — caught only when adding `update-comment`.

## API Verification

- Always verify OpenProject API endpoint availability against the official docs (https://www.openproject.org/docs/api/endpoints/) before writing requirements that depend on them. Don't assume endpoints exist from memory alone.
- Check `_links` on API resource examples — OpenProject uses HAL hypermedia controls (e.g., `_links.update` with `method: "patch"`) to advertise available operations. The presence of these links is permission-dependent.
- Community forums may report version-specific bugs (e.g., PATCH on activities returning 500 in some versions). Requirements should account for graceful error handling on endpoints that may behave inconsistently across OpenProject versions.
- PATCH `/api/v3/activities/{id}` expects `{"comment": "plain string"}` — NOT the formattable object `{"comment": {"raw": "..."}}`. The formattable object is what the API *returns*, but the PATCH request body wants a plain string. Sending the object format returns 400 "comment is invalid". Discovered via live testing with multiple payload variants.
- When debugging API payload issues, write a temp script that tries multiple payload formats in one run (plain string, formattable object, with/without version, different content types). This is faster than iterating one-at-a-time.
- Setting a non-existent parent work package ID returns 422 ("Multiple field constraints have been violated"), NOT 404. The design doc for parent-child assumed 404 but the API treats it as a validation error. Error handling tests should use 422 for this case.

## Property Test Gotchas

- `from_regex` strategies that allow trailing spaces (e.g., `r"[A-Za-z][A-Za-z0-9 ]{0,15}"`) can generate values like `'A '`. When the code under test strips or truncates these values (e.g., `link_title` returns stripped strings), assertions comparing the raw generated value against output will fail. Fix: use `.strip()` on the expected value in assertions, or tighten the regex to exclude trailing spaces (e.g., end with a non-space character class).

## API Path Prefix Pitfall

- `OpenProjectClient._request` already prepends `/api/v3` to all paths. When writing new client methods that call `_collect_collection`, use bare paths like `/memberships` — NOT `/api/v3/memberships`. The subagent used the full `/api/v3/memberships` path for `get_project_memberships`, which would have produced a double-prefix URL (`/api/v3/api/v3/memberships`). Always review subagent-generated client method paths against the `_request` implementation before marking the task complete.

## Design Review

- When extending an existing command with a new optional flag (e.g., adding `--parent` to `update-work-package`), check for "at least one field provided" guard logic in the command function. The guard tuple must include the new `args.<field>` or the new flag alone will be rejected. The design doc should call this out explicitly so the task list doesn't miss it.

## Spec Workflow — Pre-Spec Investigation

- Users may ask to verify current CLI capabilities before committing to a spec type (feature vs. bugfix). Use `readCode` to inspect relevant methods, commands, and formatters before presenting the spec type choice. This avoids speccing something that already exists or mischaracterizing the work.
- When investigating, check all four layers: client method, command function, CLI parser registration, and display/formatter. A feature can be partially implemented (e.g., API method exists but no CLI flag).

## Spec Workflow — Multi-Phase Delegation

- When the user asks to "create tasks" but the design document doesn't exist yet, create design first then tasks in a single subagent call. Tell the subagent explicitly to proceed through both phases — this avoids an extra round-trip back to the user.
- Include "The user explicitly asked for tasks to be created" in the subagent prompt so it knows to continue past the design phase without pausing for user confirmation.
