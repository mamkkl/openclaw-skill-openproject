"""Hypothesis property tests for update-comment feature.

Each test validates a correctness property from the design document.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
from pathlib import Path
from unittest.mock import patch, MagicMock

from hypothesis import given, settings, HealthCheck
import hypothesis.strategies as st


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
# Strategies
# ---------------------------------------------------------------------------
_positive_id = st.integers(min_value=1, max_value=10_000_000)
_nonempty_comment = st.from_regex(r"[A-Za-z0-9][A-Za-z0-9 _\-]{0,79}", fullmatch=True)


# ---------------------------------------------------------------------------
# Property 1: update_comment constructs correct PATCH request and returns result
# **Validates: Requirements 1.1, 1.2**
# ---------------------------------------------------------------------------

@given(activity_id=_positive_id, comment=_nonempty_comment)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_property1_patch_request_construction_and_return(activity_id, comment):
    """For any positive activity_id and non-empty comment, update_comment must
    invoke _request with the correct PATCH args and return the result unchanged."""
    client = cli.OpenProjectClient(
        base_url="https://example.openproject.com", api_token="test-token"
    )
    sentinel = {"_type": "Activity", "id": activity_id}
    with patch.object(client, "_request", return_value=sentinel) as mock_req:
        result = client.update_comment(activity_id, comment)

    mock_req.assert_called_once_with(
        "PATCH",
        f"/activities/{activity_id}",
        payload={"comment": {"raw": comment}},
        expected_statuses=(200,),
    )
    assert result is sentinel


# ---------------------------------------------------------------------------
# Property 2: Confirmation message includes activity ID
# **Validates: Requirements 2.2**
# ---------------------------------------------------------------------------

@given(activity_id=_positive_id, comment=_nonempty_comment)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_property2_confirmation_message_includes_activity_id(activity_id, comment):
    """For any positive activity_id and non-empty comment, the stdout output of
    command_update_comment must contain the string representation of activity_id."""
    mock_client = MagicMock()
    mock_client.update_comment.return_value = {"_type": "Activity", "id": activity_id}

    args = argparse.Namespace(id=activity_id, comment=comment, debug_json=False)
    buf = io.StringIO()
    with patch.object(cli, "build_client_from_env", return_value=mock_client):
        with contextlib.redirect_stdout(buf):
            cli.command_update_comment(args)

    assert str(activity_id) in buf.getvalue()


# ---------------------------------------------------------------------------
# Property 3: Parser rejects non-positive integer IDs
# **Validates: Requirements 3.1**
# ---------------------------------------------------------------------------

@given(val=st.integers(max_value=0))
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_property3a_parser_rejects_non_positive_int_ids(val):
    """For any integer <= 0, the update-comment parser must raise SystemExit."""
    parser = cli.build_parser()
    try:
        parser.parse_args(["update-comment", "--id", str(val), "--comment", "x"])
        assert False, f"Parser accepted non-positive id {val}"
    except SystemExit:
        pass  # expected


@given(val=st.from_regex(r"[a-zA-Z]+", fullmatch=True))
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_property3b_parser_rejects_non_numeric_ids(val):
    """For any non-numeric string, the update-comment parser must raise SystemExit."""
    parser = cli.build_parser()
    try:
        parser.parse_args(["update-comment", "--id", val, "--comment", "x"])
        assert False, f"Parser accepted non-numeric id {val!r}"
    except SystemExit:
        pass  # expected


# ---------------------------------------------------------------------------
# Property 4: Whitespace-only comments are rejected
# **Validates: Requirements 3.2**
# ---------------------------------------------------------------------------

@given(ws_string=st.from_regex(r"\s{0,20}", fullmatch=True))
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_property4_whitespace_only_comments_rejected(ws_string):
    """For any whitespace-only string (including empty), command_update_comment
    must raise OpenProjectError without making any API call."""
    mock_client = MagicMock()
    args = argparse.Namespace(id=1, comment=ws_string, debug_json=False)

    with patch.object(cli, "build_client_from_env", return_value=mock_client):
        try:
            cli.command_update_comment(args)
            assert False, f"command_update_comment accepted whitespace-only comment {ws_string!r}"
        except cli.OpenProjectError:
            pass  # expected

    mock_client.update_comment.assert_not_called()
