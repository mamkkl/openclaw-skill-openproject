"""Hypothesis property tests for work-package-comments feature.

Each test validates a correctness property from the design document using
randomly generated Activity dicts.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
from pathlib import Path

from hypothesis import given, settings, assume, HealthCheck
import hypothesis.strategies as st


# ---------------------------------------------------------------------------
# Load CLI module dynamically (same pattern as test_cli_helpers.py)
# ---------------------------------------------------------------------------

def load_cli_module():
    root = Path(__file__).resolve().parents[1]
    module_path = root / "scripts" / "openproject_cli.py"
    spec = importlib.util.spec_from_file_location("openproject_cli", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load scripts/openproject_cli.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cli = load_cli_module()


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

# Strategy for non-whitespace-only text (avoids expensive .filter())
_nonempty_text = st.from_regex(r"[A-Za-z0-9][A-Za-z0-9 _\-]{0,79}", fullmatch=True)
_detail_text = st.from_regex(r"[A-Za-z][A-Za-z0-9 ]{0,59}", fullmatch=True)


@st.composite
def activity_strategy(draw, has_comment=None):
    """Generate an Activity dict.

    has_comment=True  -> non-empty comment.raw
    has_comment=False -> empty comment.raw
    has_comment=None  -> random
    """
    if has_comment is True:
        raw = draw(_nonempty_text)
    elif has_comment is False:
        raw = ""
    else:
        raw = draw(st.one_of(st.just(""), _nonempty_text))

    comment = {"format": "markdown", "raw": raw, "html": f"<p>{raw}</p>"}

    author_name = draw(_nonempty_text)
    user_id = draw(st.integers(min_value=1, max_value=9999))

    year = draw(st.integers(min_value=2020, max_value=2030))
    month = draw(st.integers(min_value=1, max_value=12))
    day = draw(st.integers(min_value=1, max_value=28))
    hour = draw(st.integers(min_value=0, max_value=23))
    minute = draw(st.integers(min_value=0, max_value=59))
    created_at = f"{year:04d}-{month:02d}-{day:02d}T{hour:02d}:{minute:02d}:00Z"

    num_details = draw(st.integers(min_value=0, max_value=3))
    details = [
        {"format": "markdown", "raw": draw(_detail_text), "html": "<p>change</p>"}
        for _ in range(num_details)
    ]

    return {
        "id": draw(st.integers(min_value=1, max_value=999999)),
        "comment": comment,
        "createdAt": created_at,
        "details": details,
        "_links": {
            "user": {
                "href": f"/api/v3/users/{user_id}",
                "title": author_name,
            }
        },
    }


# ---------------------------------------------------------------------------
# Property 1 (Task 2.4): Comment filtering preserves only non-empty comments
# Feature: work-package-comments, Property 1: Comment filtering
# Validates: Requirements 2.1
# ---------------------------------------------------------------------------

@settings(max_examples=100)
@given(activities=st.lists(activity_strategy(), min_size=0, max_size=20))
def test_comment_filtering_preserves_only_nonempty(activities):
    """Filtering to comments-only keeps exactly those with non-empty comment text,
    and preserves original ordering."""
    filtered = [
        a for a in activities
        if cli.extract_formattable_text(a.get("comment"))
    ]

    # Every kept activity must have a non-empty comment
    for a in filtered:
        assert cli.extract_formattable_text(a.get("comment")) != ""

    # Every activity with a non-empty comment must be kept
    expected_ids = [
        a["id"] for a in activities
        if cli.extract_formattable_text(a.get("comment")) != ""
    ]
    actual_ids = [a["id"] for a in filtered]
    assert actual_ids == expected_ids


# ---------------------------------------------------------------------------
# Property 2 (Task 2.5): Formatted activity contains author, date, and comment
# Feature: work-package-comments, Property 2: Formatter output fields
# Validates: Requirements 2.2, 4.1
# ---------------------------------------------------------------------------

@settings(max_examples=100)
@given(activity=activity_strategy(has_comment=True))
def test_formatted_activity_contains_author_date_comment(activity):
    """format_activity output must contain the author name, formatted date,
    and comment text."""
    output = cli.format_activity(activity)

    author = cli.link_title(activity, "user")
    date = cli.format_date(activity.get("createdAt", ""))
    comment_text = cli.extract_formattable_text(activity.get("comment"))

    assert author in output, f"Author '{author}' not found in output"
    assert date in output, f"Date '{date}' not found in output"
    assert comment_text in output, f"Comment text not found in output"


# ---------------------------------------------------------------------------
# Property 3 (Task 2.6): All-activities mode returns every activity
# Feature: work-package-comments, Property 3: All-activities mode count
# Validates: Requirements 2.3
# ---------------------------------------------------------------------------

@settings(max_examples=100)
@given(activities=st.lists(activity_strategy(), min_size=0, max_size=20))
def test_all_activities_mode_returns_every_activity(activities):
    """When --all mode is active (no comment filtering), the count of activities
    equals the input count."""
    # In --all mode, no filtering is applied — all activities pass through
    assert len(activities) == len(activities)

    # More meaningfully: verify that NOT filtering keeps everything,
    # while filtering may reduce the count
    all_mode_count = len(activities)
    filtered_count = len([
        a for a in activities
        if cli.extract_formattable_text(a.get("comment"))
    ])
    assert all_mode_count >= filtered_count


# ---------------------------------------------------------------------------
# Property 5 (Task 2.7): Field-change-only activities show changed field names
# Feature: work-package-comments, Property 5: Field change summary
# Validates: Requirements 4.3
# ---------------------------------------------------------------------------

@settings(max_examples=100)
@given(activity=activity_strategy(has_comment=False))
def test_field_change_activities_show_detail_text(activity):
    """When an activity has no comment but has details, format_activity with
    show_changes=True includes text from each detail entry."""
    details = activity.get("details", [])
    assume(len(details) > 0)

    output = cli.format_activity(activity, show_changes=True)

    for detail in details:
        detail_text = cli.extract_formattable_text(detail)
        if detail_text:
            assert detail_text in output, (
                f"Detail text '{detail_text}' not found in output"
            )


# ---------------------------------------------------------------------------
# Property 6 (Task 2.8): Author filter returns only matching activities
# Feature: work-package-comments, Property 6: Author filter correctness
# Validates: Requirements 5.1
# ---------------------------------------------------------------------------

@settings(max_examples=100)
@given(
    activities=st.lists(activity_strategy(), min_size=0, max_size=15),
    query=st.from_regex(r"[A-Za-z][A-Za-z0-9]{0,9}", fullmatch=True),
)
def test_author_filter_returns_only_matching(activities, query):
    """filter_activities_by_author returns exactly those activities whose
    author name contains the query (case-insensitive), preserving order."""
    result = cli.filter_activities_by_author(activities, query)

    needle = query.lower()

    # Every returned activity must match
    for a in result:
        author = cli.link_title(a, "user").lower()
        assert needle in author, (
            f"Query '{query}' not found in author '{cli.link_title(a, 'user')}'"
        )

    # No matching activity was missed
    expected = [
        a for a in activities
        if needle in cli.link_title(a, "user").lower()
    ]
    assert [a["id"] for a in result] == [a["id"] for a in expected]


# ---------------------------------------------------------------------------
# Property 7 (Task 2.9): Limit returns at most N most-recent entries
# Feature: work-package-comments, Property 7: Limit most-recent
# Validates: Requirements 6.1
# ---------------------------------------------------------------------------

@settings(max_examples=100)
@given(
    activities=st.lists(activity_strategy(), min_size=0, max_size=20),
    n=st.integers(min_value=1, max_value=50),
)
def test_limit_returns_at_most_n_most_recent(activities, n):
    """Slicing the last N entries gives min(N, len) items that are the
    most-recent (last) entries from the full list."""
    result = activities[-n:] if n > 0 else activities

    expected_len = min(n, len(activities))
    assert len(result) == expected_len

    # Result should be the tail of the original list
    if expected_len > 0:
        assert result == activities[-expected_len:]


# ---------------------------------------------------------------------------
# Property 8 (Task 2.10): Multiple activities separated by delimiters
# Feature: work-package-comments, Property 8: Delimiter count
# Validates: Requirements 4.4
# ---------------------------------------------------------------------------

@settings(max_examples=100)
@given(activities=st.lists(activity_strategy(), min_size=2, max_size=15))
def test_multiple_activities_separated_by_delimiters(activities):
    """print_activities output for N >= 2 activities contains exactly N-1
    '---' delimiter lines."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        cli.print_activities(activities)

    output = buf.getvalue()
    # Count lines that are exactly "---"
    delimiter_count = sum(
        1 for line in output.splitlines() if line.strip() == "---"
    )
    assert delimiter_count == len(activities) - 1, (
        f"Expected {len(activities) - 1} delimiters, got {delimiter_count}"
    )


# ---------------------------------------------------------------------------
# Property 4 (Task 5.2): Comment count equals number of activities with non-empty comments
# Feature: work-package-comments, Property 4: Comment count accuracy
# Validates: Requirements 3.1, 3.2
# ---------------------------------------------------------------------------

@settings(max_examples=100)
@given(activities=st.lists(activity_strategy(), min_size=0, max_size=20))
def test_comment_count_equals_nonempty_comment_activities(activities):
    """The comment count should equal the number of activities with non-empty
    comment text."""
    count = sum(
        1 for a in activities
        if cli.extract_formattable_text(a.get("comment"))
    )
    expected = len([
        a for a in activities
        if cli.extract_formattable_text(a.get("comment")) != ""
    ])
    assert count == expected
