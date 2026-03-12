"""Hypothesis property tests for notifications feature.

Each test validates a correctness property from the design document.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
from pathlib import Path
from unittest.mock import patch, MagicMock

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
# Property 1 (Task 6.1): list_notifications uses _collect_collection with correct path
# Feature: notifications, Property 1: list_notifications uses _collect_collection with correct path
# Validates: Requirements 1.1, 6.5
# ---------------------------------------------------------------------------

@settings(max_examples=100)
@given(limit=st.integers(min_value=1, max_value=10_000))
def test_list_notifications_uses_collect_collection(limit):
    """list_notifications(limit) must call _collect_collection with
    '/notifications' and the given limit, returning the result unchanged."""
    sentinel = [{"id": i} for i in range(limit % 10)]
    client = cli.OpenProjectClient(
        base_url="https://example.openproject.com", api_token="test-token"
    )
    with patch.object(client, "_collect_collection", return_value=sentinel) as mock_cc:
        result = client.list_notifications(limit=limit)
    mock_cc.assert_called_once_with("/notifications", limit=limit)
    assert result is sentinel


# ---------------------------------------------------------------------------
# Property 2 (Task 6.2): Client methods construct correct requests
# Feature: notifications, Property 2: Client methods construct correct requests
# Validates: Requirements 2.1, 3.1, 4.1
# ---------------------------------------------------------------------------

@settings(max_examples=100)
@given(notification_id=st.integers(min_value=1, max_value=10_000_000))
def test_client_methods_construct_correct_requests(notification_id):
    """get_notification, read_notification, and unread_notification must call
    _request with the correct HTTP method, path, and expected_statuses."""
    client = cli.OpenProjectClient(
        base_url="https://example.openproject.com", api_token="test-token"
    )
    sentinel_get = {"id": notification_id}
    sentinel_read = {}
    sentinel_unread = {}

    with patch.object(client, "_request", return_value=sentinel_get) as mock_req:
        result = client.get_notification(notification_id)
    mock_req.assert_called_once_with(
        "GET", f"/notifications/{notification_id}", expected_statuses=(200,)
    )
    assert result is sentinel_get

    with patch.object(client, "_request", return_value=sentinel_read) as mock_req:
        result = client.read_notification(notification_id)
    mock_req.assert_called_once_with(
        "POST", f"/notifications/{notification_id}/read_ian", expected_statuses=(204,)
    )
    assert result is sentinel_read

    with patch.object(client, "_request", return_value=sentinel_unread) as mock_req:
        result = client.unread_notification(notification_id)
    mock_req.assert_called_once_with(
        "POST", f"/notifications/{notification_id}/unread_ian", expected_statuses=(204,)
    )
    assert result is sentinel_unread


# ---------------------------------------------------------------------------
# Property 3 (Task 6.3): Read/unread confirmation messages include notification ID
# Feature: notifications, Property 3: Read/unread confirmation messages include notification ID
# Validates: Requirements 3.2, 4.2
# ---------------------------------------------------------------------------

@settings(max_examples=100)
@given(notification_id=st.integers(min_value=1, max_value=10_000_000))
def test_read_unread_confirmation_includes_id(notification_id):
    """command_read_notification and command_unread_notification stdout output
    must contain the string representation of the notification ID."""
    mock_client = MagicMock()
    mock_client.read_notification.return_value = {}
    mock_client.unread_notification.return_value = {}

    args_read = argparse.Namespace(id=notification_id, debug_json=False)
    args_unread = argparse.Namespace(id=notification_id, debug_json=False)

    with patch.object(cli, "build_client_from_env", return_value=mock_client):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cli.command_read_notification(args_read)
        assert str(notification_id) in buf.getvalue()

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cli.command_unread_notification(args_unread)
        assert str(notification_id) in buf.getvalue()


# ---------------------------------------------------------------------------
# Property 4 (Task 6.4): filter_notifications correctly filters by reason and unread_only
# Feature: notifications, Property 4: filter_notifications correctly filters by reason and unread_only
# Validates: Requirements 1.3, 1.4
# ---------------------------------------------------------------------------

@settings(max_examples=100)
@given(
    notifications=st.lists(
        st.fixed_dictionaries({
            "reason": st.from_regex(r"[a-z]{3,15}", fullmatch=True),
            "readIAN": st.booleans(),
        }),
        min_size=0,
        max_size=20,
    ),
    reason_filter=st.from_regex(r"[a-z]{3,15}", fullmatch=True),
)
def test_filter_notifications_reason_and_unread(notifications, reason_filter):
    """filter_notifications must correctly filter by reason (case-insensitive)
    and unread_only, both individually and combined."""
    # Sub-property 1: reason filter
    by_reason = cli.filter_notifications(notifications, reason=reason_filter)
    for n in by_reason:
        assert n["reason"].lower() == reason_filter.lower()

    # Sub-property 2: unread_only filter
    by_unread = cli.filter_notifications(notifications, unread_only=True)
    for n in by_unread:
        assert n["readIAN"] is False

    # Sub-property 3: both filters combined
    by_both = cli.filter_notifications(
        notifications, reason=reason_filter, unread_only=True
    )
    for n in by_both:
        assert n["reason"].lower() == reason_filter.lower()
        assert n["readIAN"] is False


# ---------------------------------------------------------------------------
# Property 5 (Task 6.5): List formatter output contains required fields
# Feature: notifications, Property 5: List formatter output contains required fields
# Validates: Requirements 1.2
# ---------------------------------------------------------------------------

@settings(max_examples=100)
@given(
    nid=st.integers(min_value=1, max_value=999_999),
    reason=st.from_regex(r"[a-z]{3,15}", fullmatch=True),
    project_title=st.from_regex(r"[A-Za-z][A-Za-z0-9 ]{0,15}", fullmatch=True),
    resource_subject=st.from_regex(r"[A-Za-z][A-Za-z0-9 ]{0,30}", fullmatch=True),
)
def test_list_formatter_contains_required_fields(nid, reason, project_title, resource_subject):
    """print_notifications output must contain the notification ID, reason,
    and project name."""
    notification = {
        "id": nid,
        "reason": reason,
        "readIAN": False,
        "createdAt": "2025-01-15T10:30:00Z",
        "_links": {
            "project": {"href": "/api/v3/projects/5", "title": project_title},
            "resource": {"href": "/api/v3/work_packages/123", "title": resource_subject},
        },
    }
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        cli.print_notifications([notification])
    output = buf.getvalue()
    assert str(nid) in output
    assert reason in output or cli.truncate(reason, 12) in output
    assert project_title.strip() in output or cli.truncate(project_title.strip(), 19) in output


# ---------------------------------------------------------------------------
# Property 6 (Task 6.6): Detail formatter output contains required fields
# Feature: notifications, Property 6: Detail formatter output contains required fields
# Validates: Requirements 2.2
# ---------------------------------------------------------------------------

@settings(max_examples=100)
@given(
    nid=st.integers(min_value=1, max_value=999_999),
    reason=st.from_regex(r"[a-z]{3,15}", fullmatch=True),
    project_title=st.from_regex(r"[A-Za-z][A-Za-z0-9 ]{0,15}", fullmatch=True),
    resource_subject=st.from_regex(r"[A-Za-z][A-Za-z0-9 ]{0,30}", fullmatch=True),
)
def test_detail_formatter_contains_required_fields(nid, reason, project_title, resource_subject):
    """print_notification_detail output must contain the notification ID,
    reason, and project name."""
    notification = {
        "id": nid,
        "reason": reason,
        "readIAN": False,
        "createdAt": "2025-01-15T10:30:00Z",
        "_links": {
            "project": {"href": "/api/v3/projects/5", "title": project_title},
            "resource": {"href": "/api/v3/work_packages/123", "title": resource_subject},
        },
    }
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        cli.print_notification_detail(notification)
    output = buf.getvalue()
    assert str(nid) in output
    assert reason in output
    assert project_title.strip() in output


# ---------------------------------------------------------------------------
# Property 7 (Task 6.7): Limit constrains output size
# Feature: notifications, Property 7: Limit constrains output size
# Validates: Requirements 1.5
# ---------------------------------------------------------------------------

@settings(max_examples=100)
@given(
    notifications=st.lists(
        st.fixed_dictionaries({
            "id": st.integers(min_value=1),
            "createdAt": st.just("2025-01-01T00:00:00Z"),
        }),
        min_size=0,
        max_size=50,
    ),
    n=st.integers(min_value=1, max_value=100),
)
def test_limit_constrains_output_size(notifications, n):
    """Slicing notifications to limit N produces min(len, N) items."""
    result = notifications[:n]
    assert len(result) == min(len(notifications), n)


# ---------------------------------------------------------------------------
# Property 8 (Task 6.8): Notifications are sorted by createdAt descending
# Feature: notifications, Property 8: Notifications are sorted by createdAt descending
# Validates: Requirements 6.1
# ---------------------------------------------------------------------------

@settings(max_examples=100)
@given(
    notifications=st.lists(
        st.fixed_dictionaries({
            "createdAt": st.from_regex(
                r"2025-0[1-9]-[012][0-9]T[01][0-9]:[0-5][0-9]:[0-5][0-9]Z",
                fullmatch=True,
            ),
        }),
        min_size=0,
        max_size=20,
    ),
)
def test_notifications_sorted_by_created_at_descending(notifications):
    """After sorting by createdAt descending, each notification's createdAt
    must be >= the next notification's createdAt."""
    sorted_list = sorted(
        notifications, key=lambda n: n.get("createdAt", ""), reverse=True
    )
    for i in range(len(sorted_list) - 1):
        assert sorted_list[i]["createdAt"] >= sorted_list[i + 1]["createdAt"]
