# Design Document: Work Package Comments

## Overview

This feature adds read-side comment/activity support to the OpenProject CLI. Today the CLI can write comments via `add-comment` but cannot list or display them. The design adds:

1. A `get_activities()` method on `OpenProjectClient` that fetches paginated activities from `/api/v3/work_packages/{id}/activities`.
2. A standalone `list-comments` command with `--all`, `--author`, `--limit`, and `--debug-json` flags.
3. A comment count line in the existing `get-work-package` output.
4. Formatter functions (`format_activity()`, `print_activities()`) that render activities for the terminal.

All new code lives in the single `scripts/openproject_cli.py` file, following the existing patterns for API methods, commands, formatters, and argparse registration.

## Architecture

The feature follows the existing layered pattern in the CLI:

```
┌─────────────────────────────────────────────┐
│  CLI Layer (argparse commands)              │
│  command_list_comments()                    │
│  command_get_work_package() (modified)      │
├─────────────────────────────────────────────┤
│  Filtering / Presentation Layer             │
│  filter_activities_by_author()              │
│  print_activities()                         │
│  format_activity()                          │
├─────────────────────────────────────────────┤
│  Client Layer (OpenProjectClient)           │
│  get_activities()                           │
│  Uses existing: _collect_collection(),      │
│  _request(), extract_formattable_text()     │
└─────────────────────────────────────────────┘
```

No new classes or modules are introduced. The feature is a vertical slice through the existing architecture.

### Design Decisions

1. **Reuse `_collect_collection()` for pagination** — The activities endpoint returns a standard HAL collection, so the existing pagination helper works directly. No custom pagination logic needed.

2. **Comment-only filtering is client-side** — The OpenProject API v3 activities endpoint does not support server-side filtering by comment presence. We fetch all activities and filter in Python. This is acceptable because work package activity counts are typically in the low hundreds.

3. **Author matching reuses the `link_title()` pattern** — Activity payloads embed the author as a HAL `_links.user` reference with a `title` field. We match against this title using case-insensitive substring, consistent with how `--assignee` filtering works on `list-work-packages`.

4. **Comment count uses a separate lightweight call** — `get-work-package` will call `get_activities()` and count entries with non-empty comments. This adds one API round-trip but keeps the implementation simple and avoids coupling to any undocumented count fields.

## Components and Interfaces

### OpenProjectClient.get_activities()

```python
def get_activities(self, work_package_id: int, limit: int = 200) -> List[Dict[str, Any]]:
    """Fetch activities (journal entries) for a work package.

    Returns a list of Activity dicts from the API, ordered by the API's
    default (oldest first).
    """
```

- Delegates to `_collect_collection(f"/work_packages/{work_package_id}/activities", limit=limit)`.
- Raises `OpenProjectError` on HTTP errors (inherited from `_request()`).

### filter_activities_by_author()

```python
def filter_activities_by_author(activities: List[Dict[str, Any]], author_query: str) -> List[Dict[str, Any]]:
    """Filter activities to those whose author title matches the query (case-insensitive substring)."""
```

- Extracts author name via `link_title(activity, "user")`.
- Returns activities where `author_query.lower()` is a substring of the author name lowered.

### format_activity()

```python
def format_activity(activity: Dict[str, Any], show_changes: bool = False) -> str:
    """Format a single activity for terminal display.

    Returns a multi-line string with author, date, and comment text.
    When show_changes is True and the activity has no comment, returns
    a summary of changed fields instead.
    """
```

- Uses `link_title(activity, "user")` for author name.
- Uses `format_date(activity.get("createdAt", ""))` for timestamp.
- Uses `extract_formattable_text(activity.get("comment"))` for comment body.
- When `show_changes=True` and comment is empty, lists changed field names from `activity.get("details", [])`.

### print_activities()

```python
def print_activities(activities: List[Dict[str, Any]], show_changes: bool = False) -> None:
    """Print formatted activities to stdout, separated by delimiters."""
```

- Iterates activities, calls `format_activity()`, prints with `---` separator between entries.

### command_list_comments()

```python
def command_list_comments(args: argparse.Namespace) -> None:
    """CLI handler for the list-comments subcommand."""
```

- Calls `client.get_activities(args.id)`.
- Unless `--all`, filters to activities with non-empty comment text.
- Applies `--author` filter if provided.
- Applies `--limit` by slicing the last N entries (most recent).
- Calls `print_activities()`.
- Calls `maybe_print_json()` if `--debug-json`.

### command_get_work_package() (modified)

- After printing work package detail, calls `client.get_activities(args.id)`.
- Counts activities with non-empty comment text.
- Prints `Comments: {count}` line in the detail output.

### Argparse Registration (in build_parser)

```
list-comments
  --id        (int, required)   Work package ID
  --all       (flag)            Show all activities including field changes
  --author    (str, optional)   Filter by author name/login substring
  --limit     (int, optional)   Show only the N most recent comments
```

## Data Models

### Activity Object (from OpenProject API v3)

The activities endpoint returns HAL+JSON resources. Key fields used:

```json
{
  "_type": "Activity::Comment",
  "id": 42,
  "comment": {
    "format": "markdown",
    "raw": "This is the comment text",
    "html": "<p>This is the comment text</p>"
  },
  "createdAt": "2025-01-15T10:30:00Z",
  "details": [
    { "format": "markdown", "raw": "Status changed from New to In progress", "html": "..." }
  ],
  "_links": {
    "user": {
      "href": "/api/v3/users/5",
      "title": "Alice Admin"
    },
    "workPackage": {
      "href": "/api/v3/work_packages/123",
      "title": "Fix login bug"
    }
  }
}
```

- `_type`: Either `"Activity::Comment"` (has user comment) or `"Activity"` (field changes only). We don't rely on `_type` for filtering — we check whether `comment.raw` is non-empty.
- `comment`: A formattable object (same shape as work package `description`). Extracted via `extract_formattable_text()`.
- `details`: Array of formattable objects describing field changes. Used only when `--all` is active.
- `_links.user.title`: Author display name. Used for display and `--author` filtering.
- `createdAt`: ISO 8601 timestamp. Formatted via `format_date()`.

No new data models or classes are introduced. All data flows as `Dict[str, Any]` consistent with the rest of the CLI.


## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Comment filtering preserves only non-empty comments

*For any* list of Activity dicts (some with non-empty `comment.raw`, some with empty or missing `comment`), filtering to "comments only" should return exactly those activities where `extract_formattable_text(activity["comment"])` produces a non-empty string, and the result should preserve the original ordering.

**Validates: Requirements 2.1**

### Property 2: Formatted activity contains author, date, and comment text

*For any* Activity dict with a non-empty comment, a non-empty `_links.user.title`, and a valid `createdAt` timestamp, the output of `format_activity()` should contain the author name, the formatted date string, and the extracted comment text.

**Validates: Requirements 2.2, 4.1**

### Property 3: All-activities mode returns every activity

*For any* list of Activity dicts, when the `--all` flag is active (no comment filtering), the number of displayed activities should equal the total number of input activities.

**Validates: Requirements 2.3**

### Property 4: Comment count equals number of activities with non-empty comments

*For any* list of Activity dicts for a work package, the comment count displayed by `get-work-package` should equal the number of activities where `extract_formattable_text(activity["comment"])` is non-empty.

**Validates: Requirements 3.1, 3.2**

### Property 5: Field-change-only activities show changed field names

*For any* Activity dict that has an empty comment but non-empty `details` entries, when `show_changes=True`, the output of `format_activity()` should contain text derived from each detail entry.

**Validates: Requirements 4.3**

### Property 6: Author filter returns only matching activities

*For any* list of Activity dicts and any non-empty query string, `filter_activities_by_author(activities, query)` should return only activities where `link_title(activity, "user").lower()` contains `query.lower()`, and should preserve ordering.

**Validates: Requirements 5.1**

### Property 7: Limit returns at most N most-recent entries

*For any* list of Activity dicts with length L and any positive integer N, applying `--limit N` should return `min(N, L)` activities, and those activities should be the last `min(N, L)` entries from the full list (i.e., the most recent).

**Validates: Requirements 6.1**

### Property 8: Multiple activities are separated by delimiters

*For any* list of N ≥ 2 Activity dicts, the output of `print_activities()` should contain exactly N − 1 delimiter separators between formatted entries.

**Validates: Requirements 4.4**

## Error Handling

Error handling follows the existing CLI patterns:

| Scenario | Behavior |
|---|---|
| Invalid work package ID (404) | `_request()` raises `OpenProjectError` with status code and message. `main()` catches it and prints the error. |
| Network / HTTP errors | `_request()` raises `OpenProjectError`. No new error handling needed. |
| No comments found | `command_list_comments()` prints "No comments found for work package #{id}." and exits cleanly (exit code 0). |
| No matching author | `command_list_comments()` prints "No matching comments found." and exits cleanly (exit code 0). |
| `--limit` with non-positive value | argparse `type=int` handles parsing; the command treats limit ≤ 0 as "show all" (defensive). |
| Activity with missing/malformed fields | `link_title()` returns default `"-"`, `extract_formattable_text()` returns `""`, `format_date()` returns `""`. Graceful degradation, no crashes. |

No new exception types are introduced. All errors flow through the existing `OpenProjectError` → `main()` → `sys.exit(1)` path.

## Testing Strategy

### Property-Based Testing

Library: **Hypothesis** (`hypothesis` package for Python).

Each correctness property from the design is implemented as a single Hypothesis test. Tests generate random Activity dicts with varying shapes (with/without comments, with/without details, various author names, timestamps).

Configuration:
- Minimum 100 examples per test via `@settings(max_examples=100)`
- Each test tagged with a comment: `# Feature: work-package-comments, Property N: <title>`

Properties to implement:
1. Comment filtering (Property 1)
2. Formatter output fields (Property 2)
3. All-activities mode count (Property 3)
4. Comment count accuracy (Property 4)
5. Field change summary (Property 5)
6. Author filter correctness (Property 6)
7. Limit most-recent (Property 7)
8. Delimiter count (Property 8)

### Unit Tests

Unit tests complement property tests for specific examples and edge cases:

- **Empty activity list**: `list-comments` with no activities prints "No comments found" message.
- **Zero comments**: `get-work-package` displays "Comments: 0".
- **`--debug-json` flag**: Raw JSON appears in output when flag is set.
- **Author filter with no matches**: Prints "No matching comments found."
- **Activity with missing `_links.user`**: Formatter gracefully shows `"-"` as author.
- **`--limit 0` or negative**: Treated as "show all" (defensive behavior).

### Test File Location

- Property tests: `tests/test_comments_properties.py`
- Unit tests: added to `tests/test_cli_helpers.py` or a new `tests/test_comments.py`

### Running Tests

```bash
# Install hypothesis for property tests
python3 -m pip install hypothesis

# Run all tests
python3 -m unittest discover -s tests -p 'test_*.py'

# Run only property tests
python3 -m pytest tests/test_comments_properties.py -v
```
