# Lessons Learned

Observations from building and implementing specs in this project. Use these to avoid repeating mistakes.

## Environment

- This is a Windows machine. Use `python` not `python3`. PowerShell is the shell — avoid bash-isms like `tail`, `&&`, and inline single-quote strings in `-c` flags.
- For complex inline Python checks, write a temp `.py` file and run it instead of fighting PowerShell quoting.
- `unittest` on PowerShell reports stderr even on success (exit code 1 with "OK" output). Check the "OK" / "FAILED" line, not the exit code alone.

## Testing Patterns

- Unit tests use `unittest` and load the CLI via `importlib.util` — never import it as a package.
- Property tests use `hypothesis` (not in `requirements.txt` — install separately with `pip install hypothesis`).
- Property tests run via `pytest`, unit tests via `unittest discover`. Both coexist in `tests/`.
- When capturing stdout in tests, use `io.StringIO` + `contextlib.redirect_stdout`.
- Mock `build_client_from_env` to return a `MagicMock` client for command-level tests. Mock `_collect_collection` on client instances for client-method tests.

## Code Placement

- All CLI code lives in `scripts/openproject_cli.py` — single file, no modules.
- New filter functions go near `filter_work_packages()` / `filter_users()`.
- New formatter functions go near `print_projects()` / `print_work_packages()`.
- New command functions go near related existing commands (e.g., `command_list_comments` after `command_add_comment`).
- Subparser registration in `build_parser()` should mirror the command function ordering.
- `--debug-json` is a global parser argument — don't re-add it to subparsers.

## Subagent Delegation

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

## Spec Workflow — Multi-Phase Delegation

- When the user asks to "create tasks" but the design document doesn't exist yet, create design first then tasks in a single subagent call. Tell the subagent explicitly to proceed through both phases — this avoids an extra round-trip back to the user.
- Include "The user explicitly asked for tasks to be created" in the subagent prompt so it knows to continue past the design phase without pausing for user confirmation.
