"""Unit tests for parent-child work-package helpers."""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import unittest
from pathlib import Path


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


class TestBuildParentHref(unittest.TestCase):
    """Tests for build_parent_href helper."""

    def test_positive_integer(self) -> None:
        result = cli.build_parent_href("42")
        self.assertEqual(result, "/api/v3/work_packages/42")

    def test_none_lowercase(self) -> None:
        result = cli.build_parent_href("none")
        self.assertIsNone(result)

    def test_none_mixed_case(self) -> None:
        result = cli.build_parent_href("None")
        self.assertIsNone(result)


class TestParentIdOrNone(unittest.TestCase):
    """Tests for parent_id_or_none argparse type function."""

    def test_valid_positive_integer(self) -> None:
        result = cli.parent_id_or_none("42")
        self.assertEqual(result, "42")

    def test_none_literal(self) -> None:
        result = cli.parent_id_or_none("none")
        self.assertEqual(result, "none")

    def test_non_numeric_string_raises(self) -> None:
        with self.assertRaises(argparse.ArgumentTypeError):
            cli.parent_id_or_none("abc")

    def test_negative_integer_raises(self) -> None:
        with self.assertRaises(argparse.ArgumentTypeError):
            cli.parent_id_or_none("-1")

    def test_zero_raises(self) -> None:
        with self.assertRaises(argparse.ArgumentTypeError):
            cli.parent_id_or_none("0")


def _make_link(title: str) -> dict:
    """Build a minimal HAL link object."""
    return {"href": f"/api/v3/{title}/1", "title": title.capitalize()}


def _make_wp(wp_id: int, subject: str, parent_href=None, parent_title=None) -> dict:
    """Build a minimal work package dict for display tests."""
    parent_link: dict = {"href": parent_href, "title": parent_title}
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
            "parent": parent_link,
        },
    }


class TestPrintWorkPackageDetailParent(unittest.TestCase):
    """Tests for parent display in print_work_package_detail."""

    def test_detail_with_parent_shows_parent_line(self) -> None:
        wp = _make_wp(99, "Child task",
                      parent_href="/api/v3/work_packages/42",
                      parent_title="Parent epic")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cli.print_work_package_detail(wp)
        output = buf.getvalue()
        self.assertIn("Parent: #42", output)
        self.assertIn("Parent epic", output)

    def test_detail_without_parent_omits_parent_line(self) -> None:
        wp = _make_wp(99, "Orphan task", parent_href=None, parent_title=None)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cli.print_work_package_detail(wp)
        output = buf.getvalue()
        self.assertNotIn("Parent:", output)


class TestPrintWorkPackagesParent(unittest.TestCase):
    """Tests for parent column in print_work_packages."""

    def test_list_with_parent_shows_parent_id(self) -> None:
        wp = _make_wp(10, "Child",
                      parent_href="/api/v3/work_packages/42",
                      parent_title="Parent")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cli.print_work_packages([wp])
        output = buf.getvalue()
        lines = output.splitlines()
        # Data row is the third line (after header + separator)
        data_line = lines[2]
        self.assertIn("42", data_line)

    def test_list_without_parent_shows_dash(self) -> None:
        wp = _make_wp(10, "Orphan", parent_href=None, parent_title=None)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cli.print_work_packages([wp])
        output = buf.getvalue()
        lines = output.splitlines()
        data_line = lines[2]
        # The parent column should show "-"
        self.assertIn("-", data_line)


from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers for command-level tests
# ---------------------------------------------------------------------------

def _make_create_args(subject="Test WP", project="demo", wp_type="Task",
                      description=None, parent=None):
    """Build an argparse.Namespace for command_create_work_package."""
    ns = argparse.Namespace(
        subject=subject,
        project=project,
        type=wp_type,
        description=description,
        debug_json=False,
    )
    if parent is not None:
        ns.parent = parent
    return ns


def _make_update_args(wp_id=99, parent=None):
    """Build an argparse.Namespace for command_update_work_package."""
    return argparse.Namespace(
        id=wp_id,
        subject=None,
        description=None,
        status=None,
        assignee=None,
        priority=None,
        type=None,
        start_date=None,
        due_date=None,
        parent=parent,
        debug_json=False,
    )


def _make_list_children_args(wp_id=42, limit=50):
    """Build an argparse.Namespace for command_list_children."""
    return argparse.Namespace(
        id=wp_id,
        limit=limit,
        debug_json=False,
    )


def _stub_project():
    return {"id": 1, "_links": {"self": {"href": "/api/v3/projects/1"}}}


def _stub_created_wp(wp_id=100, subject="Test WP", parent_id=None):
    wp = {"id": wp_id, "subject": subject}
    return wp


def _stub_updated_wp(wp_id=99):
    """Return a minimal work-package dict that print_work_package_detail can handle."""
    return _make_wp(wp_id, "Updated task",
                    parent_href=None, parent_title=None)


class TestCommandCreateWorkPackage(unittest.TestCase):
    """Tests for command_create_work_package."""

    @patch.object(cli, "build_client_from_env")
    def test_create_with_parent_includes_parent_id(self, mock_build):
        mock_client = MagicMock()
        mock_build.return_value = mock_client
        mock_client.resolve_project.return_value = _stub_project()
        mock_client.create_work_package.return_value = _stub_created_wp(100, "Child")

        args = _make_create_args(subject="Child", parent=42)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cli.command_create_work_package(args)

        mock_client.create_work_package.assert_called_once()
        call_kwargs = mock_client.create_work_package.call_args
        self.assertEqual(call_kwargs.kwargs.get("parent_id")
                         if call_kwargs.kwargs else call_kwargs[1].get("parent_id"), 42)

    @patch.object(cli, "build_client_from_env")
    def test_create_without_parent_omits_parent_id(self, mock_build):
        mock_client = MagicMock()
        mock_build.return_value = mock_client
        mock_client.resolve_project.return_value = _stub_project()
        mock_client.create_work_package.return_value = _stub_created_wp(100, "Solo")

        args = _make_create_args(subject="Solo")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cli.command_create_work_package(args)

        call_kwargs = mock_client.create_work_package.call_args
        parent_val = (call_kwargs.kwargs.get("parent_id")
                      if call_kwargs.kwargs else call_kwargs[1].get("parent_id"))
        self.assertIsNone(parent_val)


class TestCommandUpdateWorkPackage(unittest.TestCase):
    """Tests for command_update_work_package."""

    @patch.object(cli, "build_client_from_env")
    def test_update_with_parent_42(self, mock_build):
        mock_client = MagicMock()
        mock_build.return_value = mock_client
        mock_client.update_work_package.return_value = _stub_updated_wp(99)

        args = _make_update_args(wp_id=99, parent="42")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cli.command_update_work_package(args)

        mock_client.update_work_package.assert_called_once()
        call_kwargs = mock_client.update_work_package.call_args
        self.assertEqual(call_kwargs.kwargs.get("parent_ref"), "42")

    @patch.object(cli, "build_client_from_env")
    def test_update_with_parent_none(self, mock_build):
        mock_client = MagicMock()
        mock_build.return_value = mock_client
        mock_client.update_work_package.return_value = _stub_updated_wp(99)

        args = _make_update_args(wp_id=99, parent="none")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cli.command_update_work_package(args)

        mock_client.update_work_package.assert_called_once()
        call_kwargs = mock_client.update_work_package.call_args
        self.assertEqual(call_kwargs.kwargs.get("parent_ref"), "none")
        output = buf.getvalue()
        self.assertIn("Parent removed", output)


class TestCommandListChildren(unittest.TestCase):
    """Tests for command_list_children."""

    @patch.object(cli, "build_client_from_env")
    def test_empty_result_prints_no_children(self, mock_build):
        mock_client = MagicMock()
        mock_build.return_value = mock_client
        mock_client.list_children.return_value = []

        args = _make_list_children_args(wp_id=42)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cli.command_list_children(args)

        output = buf.getvalue()
        self.assertIn("No children found for work package #42.", output)

    @patch.object(cli, "build_client_from_env")
    def test_with_results_prints_table(self, mock_build):
        mock_client = MagicMock()
        mock_build.return_value = mock_client
        mock_client.list_children.return_value = [
            _make_wp(101, "Child A", parent_href="/api/v3/work_packages/42",
                     parent_title="Parent"),
            _make_wp(102, "Child B", parent_href="/api/v3/work_packages/42",
                     parent_title="Parent"),
        ]

        args = _make_list_children_args(wp_id=42)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cli.command_list_children(args)

        output = buf.getvalue()
        self.assertIn("Child A", output)
        self.assertIn("Child B", output)
        self.assertIn("101", output)
        self.assertIn("102", output)


class TestCommandErrorHandling(unittest.TestCase):
    """Tests for API error propagation in command functions."""

    @patch.object(cli, "build_client_from_env")
    def test_404_error_for_nonexistent_parent(self, mock_build):
        mock_client = MagicMock()
        mock_build.return_value = mock_client
        mock_client.update_work_package.side_effect = cli.OpenProjectError(
            "Work package not found.", status_code=404
        )

        args = _make_update_args(wp_id=99, parent="9999")
        with self.assertRaises(cli.OpenProjectError) as ctx:
            cli.command_update_work_package(args)

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertIn("not found", str(ctx.exception))

    @patch.object(cli, "build_client_from_env")
    def test_422_error_for_circular_hierarchy(self, mock_build):
        mock_client = MagicMock()
        mock_build.return_value = mock_client
        mock_client.update_work_package.side_effect = cli.OpenProjectError(
            "Circular dependency: work package cannot be its own ancestor.",
            status_code=422,
        )

        args = _make_update_args(wp_id=99, parent="42")
        with self.assertRaises(cli.OpenProjectError) as ctx:
            cli.command_update_work_package(args)

        self.assertEqual(ctx.exception.status_code, 422)
        self.assertIn("Circular dependency", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
