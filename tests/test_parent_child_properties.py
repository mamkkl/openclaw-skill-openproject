"""Hypothesis property tests for parent-child work-package helpers.

Each test validates a correctness property from the design document using
randomly generated inputs.
"""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path

from hypothesis import given, settings
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
# Property 1: Parent href round-trip
# Feature: parent-child-work-packages, Property 1: Parent href round-trip
# **Validates: Requirements 8.1, 8.3**
# ---------------------------------------------------------------------------

@given(wp_id=st.integers(min_value=1, max_value=10**9))
@settings(max_examples=100)
def test_parent_href_round_trip(wp_id: int) -> None:
    """build_parent_href(str(id)) -> extract_numeric_id_from_href returns original ID."""
    href = cli.build_parent_href(str(wp_id))
    assert href is not None
    extracted = cli.extract_numeric_id_from_href(href, "work_packages")
    assert extracted == wp_id


# ---------------------------------------------------------------------------
# Property 2: "none" produces null href
# Feature: parent-child-work-packages, Property 2: "none" produces null href
# **Validates: Requirements 3.1, 8.2**
# ---------------------------------------------------------------------------

_NONE_VARIANTS = [
    "none", "None", "NONE", "nOnE", "noNe", "nONE", "NoNe", "nonE",
    "nONe", "NONe", "NOne", "nONE", "NoNE", "nONE", "NONE", "noNE",
]


@given(value=st.sampled_from(_NONE_VARIANTS))
@settings(max_examples=100)
def test_none_produces_null_href(value: str) -> None:
    """All case variations of 'none' return None from build_parent_href."""
    result = cli.build_parent_href(value)
    assert result is None


# ---------------------------------------------------------------------------
# Property 3: Invalid parent values are rejected
# Feature: parent-child-work-packages, Property 3: Invalid parent values are rejected
# **Validates: Requirements 1.3, 2.3**
# ---------------------------------------------------------------------------

@given(value=st.from_regex(r"[a-zA-Z!@#$%^&*()]{1,20}", fullmatch=True).filter(
    lambda s: s.lower() != "none" and not s.isdigit()
))
@settings(max_examples=100)
def test_invalid_parent_values_rejected(value: str) -> None:
    """Non-integer, non-'none' strings raise ArgumentTypeError from parent_id_or_none."""
    try:
        cli.parent_id_or_none(value)
        assert False, f"Expected ArgumentTypeError for {value!r}"
    except argparse.ArgumentTypeError:
        pass  # expected


# ---------------------------------------------------------------------------
# Shared strategies for work-package dicts
# ---------------------------------------------------------------------------

import contextlib
import io


def _make_link(title: str) -> dict:
    """Build a minimal HAL link object."""
    return {"href": f"/api/v3/{title}/1", "title": title.capitalize()}


@st.composite
def work_package_with_parent(draw):
    """Generate a work package dict that HAS a parent link."""
    wp_id = draw(st.integers(min_value=1, max_value=10**6))
    subject = draw(st.from_regex(r"[A-Za-z][A-Za-z0-9]{0,14}", fullmatch=True))
    parent_id = draw(st.integers(min_value=1, max_value=10**6))
    parent_title = draw(st.from_regex(r"[A-Za-z][A-Za-z0-9]{0,14}", fullmatch=True))
    return {
        "id": wp_id,
        "subject": subject,
        "createdAt": "2025-01-01T00:00:00Z",
        "updatedAt": "2025-01-02T00:00:00Z",
        "startDate": None,
        "dueDate": None,
        "lockVersion": 1,
        "description": "",
        "_links": {
            "status": _make_link("statuses"),
            "type": _make_link("types"),
            "priority": _make_link("priorities"),
            "assignee": _make_link("users"),
            "author": _make_link("users"),
            "parent": {
                "href": f"/api/v3/work_packages/{parent_id}",
                "title": parent_title,
            },
        },
    }, parent_id, parent_title


@st.composite
def work_package_without_parent(draw):
    """Generate a work package dict that has NO parent (href is null)."""
    wp_id = draw(st.integers(min_value=1, max_value=10**6))
    subject = draw(st.from_regex(r"[A-Za-z][A-Za-z0-9]{0,14}", fullmatch=True))
    return {
        "id": wp_id,
        "subject": subject,
        "createdAt": "2025-01-01T00:00:00Z",
        "updatedAt": "2025-01-02T00:00:00Z",
        "startDate": None,
        "dueDate": None,
        "lockVersion": 1,
        "description": "",
        "_links": {
            "status": _make_link("statuses"),
            "type": _make_link("types"),
            "priority": _make_link("priorities"),
            "assignee": _make_link("users"),
            "author": _make_link("users"),
            "parent": {"href": None, "title": None},
        },
    }


# ---------------------------------------------------------------------------
# Property 4: Detail view parent display
# Feature: parent-child-work-packages, Property 4: Detail view parent display
# **Validates: Requirements 4.1, 4.2**
# ---------------------------------------------------------------------------

@given(data=work_package_with_parent())
@settings(max_examples=100)
def test_detail_view_shows_parent_when_present(data) -> None:
    """print_work_package_detail includes 'Parent:' line when _links.parent.href is set."""
    wp, parent_id, _parent_title = data
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        cli.print_work_package_detail(wp)
    output = buf.getvalue()
    assert f"Parent: #{parent_id}" in output


@given(wp=work_package_without_parent())
@settings(max_examples=100)
def test_detail_view_omits_parent_when_absent(wp) -> None:
    """print_work_package_detail omits 'Parent:' line when _links.parent.href is null."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        cli.print_work_package_detail(wp)
    output = buf.getvalue()
    assert "Parent:" not in output


# ---------------------------------------------------------------------------
# Property 5: List view parent column
# Feature: parent-child-work-packages, Property 5: List view parent column
# **Validates: Requirements 5.1, 5.2**
# ---------------------------------------------------------------------------

@st.composite
def work_package_list_mixed(draw):
    """Generate a non-empty list of work package dicts with mixed parent presence.

    Returns (list_of_wps, list_of_expected) where expected is parent_id (int) or None.
    """
    n = draw(st.integers(min_value=1, max_value=10))
    wps = []
    expected = []
    for _ in range(n):
        has_parent = draw(st.booleans())
        if has_parent:
            wp, parent_id, _ = draw(work_package_with_parent())
            wps.append(wp)
            expected.append(parent_id)
        else:
            wp = draw(work_package_without_parent())
            wps.append(wp)
            expected.append(None)
    return wps, expected


@given(data=work_package_list_mixed())
@settings(max_examples=100)
def test_list_view_parent_column(data) -> None:
    """Each row in print_work_packages shows parent ID or dash."""
    wps, expected = data
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        cli.print_work_packages(wps)
    lines = buf.getvalue().splitlines()
    # Skip header (2 lines), remaining lines are data rows
    data_lines = lines[2:]
    assert len(data_lines) == len(wps)
    for line, exp_parent_id in zip(data_lines, expected):
        if exp_parent_id is not None:
            assert str(exp_parent_id) in line
        else:
            # The parent column should contain "-"; verify by splitting
            # The parent column is between Assignee and Updated columns
            assert "-" in line
