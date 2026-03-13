"""Hypothesis property tests for list-project-members feature.

Each test validates a correctness property from the design document using
randomly generated Membership dicts.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
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
# Hypothesis strategies
# ---------------------------------------------------------------------------

_name_text = st.from_regex(r"[A-Za-z][A-Za-z ]{0,29}[A-Za-z]", fullmatch=True)
_role_text = st.from_regex(r"[A-Za-z][A-Za-z ]{0,14}[A-Za-z]", fullmatch=True)
_query_text = st.from_regex(r"[A-Za-z]{1,10}", fullmatch=True)
_project_name = st.from_regex(r"[A-Za-z][A-Za-z0-9 ]{0,24}[A-Za-z0-9]", fullmatch=True)


@st.composite
def membership_strategy(draw):
    """Generate a Membership HAL dict with principal and roles."""
    name = draw(_name_text)
    user_id = draw(st.integers(min_value=1, max_value=9999))
    num_roles = draw(st.integers(min_value=1, max_value=5))
    roles = [
        {
            "href": f"/api/v3/roles/{draw(st.integers(min_value=1, max_value=99))}",
            "title": draw(_role_text),
        }
        for _ in range(num_roles)
    ]
    return {
        "id": draw(st.integers(min_value=1, max_value=999999)),
        "_links": {
            "principal": {"href": f"/api/v3/users/{user_id}", "title": name},
            "roles": roles,
            "project": {"href": "/api/v3/projects/1", "title": "Test Project"},
        },
    }


# ---------------------------------------------------------------------------
# Property 1: Client method constructs correct API call
# Feature: list-project-members, Property 1: Client method constructs correct API call
# Validates: Requirements 1.1, 1.5, 4.1
# ---------------------------------------------------------------------------

@settings(max_examples=100)
@given(
    project_id=st.integers(min_value=1, max_value=999999),
    limit=st.integers(min_value=1, max_value=1000),
)
def test_client_method_constructs_correct_api_call(project_id, limit):
    """For any positive project ID and limit, get_project_memberships must
    invoke _collect_collection with path '/memberships', a filters param
    containing the correct project filter JSON, and the specified limit."""
    client = cli.OpenProjectClient(
        base_url="https://example.openproject.com",
        api_token="test-token",
    )
    with patch.object(client, "_collect_collection", return_value=[]) as mock_collect:
        client.get_project_memberships(project_id, limit=limit)

    mock_collect.assert_called_once()
    call_args, call_kwargs = mock_collect.call_args

    # Path must be /memberships
    assert call_args[0] == "/memberships"

    # Filter JSON must contain the project filter with correct ID
    filters_json = call_kwargs["params"]["filters"]
    filters = json.loads(filters_json)
    assert len(filters) == 1
    assert filters[0]["project"]["operator"] == "="
    assert filters[0]["project"]["values"] == [str(project_id)]

    # Limit must match
    assert call_kwargs["limit"] == limit


# ---------------------------------------------------------------------------
# Property 2: Formatter output contains all required fields
# Feature: list-project-members, Property 2: Formatter output contains all required fields
# Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.6
# ---------------------------------------------------------------------------

@settings(max_examples=100)
@given(member=membership_strategy())
def test_formatter_output_contains_all_required_fields(member):
    """For any membership object, print_members output must contain the
    principal name (or truncation), the principal ID, and every role name."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        cli.print_members([member])
    output = buf.getvalue()

    # Principal name (stripped, possibly truncated to 32 chars)
    raw_name = member["_links"]["principal"]["title"].strip()
    if len(raw_name) <= 32:
        assert raw_name in output
    else:
        assert raw_name[:29] in output  # truncated prefix before "..."

    # Principal ID extracted from href
    href = member["_links"]["principal"]["href"]
    user_id = href.rstrip("/").split("/")[-1]
    assert user_id in output

    # Each role name must appear (possibly truncated in the combined string)
    role_names = [r["title"].strip() for r in member["_links"]["roles"]]
    combined_roles = ", ".join(role_names)
    if len(combined_roles) <= 40:
        for role_name in role_names:
            assert role_name in output
    else:
        # Truncated — at least the truncated prefix should appear
        assert combined_roles[:37] in output


# ---------------------------------------------------------------------------
# Property 3: Filter returns only matching members
# Feature: list-project-members, Property 3: Filter returns only matching members
# Validates: Requirements 3.1
# ---------------------------------------------------------------------------

@settings(max_examples=100)
@given(
    members=st.lists(membership_strategy(), min_size=0, max_size=15),
    query=_query_text,
)
def test_filter_returns_only_matching_members(members, query):
    """For any list of members and any query, filter_members must return
    only members whose principal name contains the query (case-insensitive),
    and must not exclude any member whose name contains the query."""
    result = cli.filter_members(members, query)
    result_ids = {m["id"] for m in result}
    needle = query.lower()

    # Every returned member must match
    for m in result:
        name = cli.link_title(m, "principal").lower()
        assert needle in name

    # Every excluded member must NOT match
    for m in members:
        if m["id"] not in result_ids:
            name = cli.link_title(m, "principal").lower()
            assert needle not in name


# ---------------------------------------------------------------------------
# Property 4: Command output includes project header
# Feature: list-project-members, Property 4: Command output includes project header
# Validates: Requirements 6.3
# ---------------------------------------------------------------------------

@settings(max_examples=100)
@given(project_name=_project_name)
def test_command_output_includes_project_header(project_name):
    """For any project name, command_list_project_members output must
    include a 'Project: <name>' header line."""
    fake_project = {
        "id": 1,
        "name": project_name,
        "identifier": "test-project",
    }
    mock_client = MagicMock()
    mock_client.resolve_project.return_value = fake_project
    mock_client.get_project_memberships.return_value = []

    args = argparse.Namespace(
        project="test-project",
        query=None,
        limit=200,
        debug_json=False,
    )

    buf = io.StringIO()
    with patch.object(cli, "build_client_from_env", return_value=mock_client):
        with contextlib.redirect_stdout(buf):
            cli.command_list_project_members(args)
    output = buf.getvalue()

    assert f"Project: {project_name}" in output
