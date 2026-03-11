"""Unit tests for work-package comment/activity features in scripts/openproject_cli.py."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock


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


class TestGetActivities(unittest.TestCase):
    """Tests for OpenProjectClient.get_activities()."""

    def _make_client(self) -> cli.OpenProjectClient:
        """Create a client instance with dummy credentials for testing."""
        return cli.OpenProjectClient(
            base_url="https://example.openproject.com",
            api_token="test-token",
        )

    def test_calls_collect_collection_with_correct_endpoint(self) -> None:
        """Verify get_activities passes the correct endpoint path to _collect_collection."""
        client = self._make_client()
        fake_activities = [{"id": 1}, {"id": 2}]

        with patch.object(client, "_collect_collection", return_value=fake_activities) as mock_collect:
            result = client.get_activities(123)

        mock_collect.assert_called_once_with(
            "/work_packages/123/activities", limit=200
        )
        self.assertEqual(result, fake_activities)

    def test_forwards_custom_limit(self) -> None:
        """Verify the limit parameter is forwarded to _collect_collection."""
        client = self._make_client()

        with patch.object(client, "_collect_collection", return_value=[]) as mock_collect:
            client.get_activities(456, limit=50)

        mock_collect.assert_called_once_with(
            "/work_packages/456/activities", limit=50
        )

    def test_openproject_error_propagates(self) -> None:
        """Verify that OpenProjectError raised by _collect_collection propagates."""
        client = self._make_client()
        error = cli.OpenProjectError("Not Found", status_code=404)

        with patch.object(client, "_collect_collection", side_effect=error):
            with self.assertRaises(cli.OpenProjectError) as ctx:
                client.get_activities(999)

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertIn("Not Found", str(ctx.exception))


import argparse
import contextlib
import io
import json


# Sample activity dicts for command_list_comments tests
ACTIVITY_WITH_COMMENT = {
    "id": 1,
    "comment": {"format": "markdown", "raw": "This is a comment", "html": "<p>This is a comment</p>"},
    "createdAt": "2025-01-15T10:30:00Z",
    "details": [],
    "_links": {"user": {"href": "/api/v3/users/5", "title": "Alice Admin"}},
}
ACTIVITY_WITHOUT_COMMENT = {
    "id": 2,
    "comment": {"format": "markdown", "raw": "", "html": ""},
    "createdAt": "2025-01-16T11:00:00Z",
    "details": [{"format": "markdown", "raw": "Status changed", "html": "<p>Status changed</p>"}],
    "_links": {"user": {"href": "/api/v3/users/6", "title": "Bob Builder"}},
}


class TestCommandListComments(unittest.TestCase):
    """Tests for command_list_comments()."""

    def _make_args(self, wp_id=123, all_flag=False, author=None, limit=None, debug_json=False):
        return argparse.Namespace(id=wp_id, all=all_flag, author=author, limit=limit, debug_json=debug_json)

    def _run_command(self, args, activities):
        """Run command_list_comments with mocked client, return captured stdout."""
        mock_client = MagicMock()
        mock_client.get_activities.return_value = activities
        buf = io.StringIO()
        with patch.object(cli, "build_client_from_env", return_value=mock_client):
            with contextlib.redirect_stdout(buf):
                cli.command_list_comments(args)
        return buf.getvalue()

    def test_empty_activities_prints_no_comments_message(self):
        """Empty activity list prints 'No comments found for work package #ID.'"""
        args = self._make_args(wp_id=42)
        output = self._run_command(args, [])
        self.assertIn("No comments found for work package #42.", output)

    def test_author_no_matches_prints_no_matching(self):
        """--author with no matches prints 'No matching comments found.'"""
        args = self._make_args(author="Nonexistent")
        output = self._run_command(args, [ACTIVITY_WITH_COMMENT])
        self.assertIn("No matching comments found.", output)

    def test_debug_json_flag_triggers_json_output(self):
        """--debug-json flag causes raw JSON to appear in output."""
        activities = [ACTIVITY_WITH_COMMENT]
        args = self._make_args(debug_json=True)
        output = self._run_command(args, activities)
        # The raw JSON dump should contain the activity id
        self.assertIn('"id": 1', output)
        # Verify it's valid JSON by finding the JSON portion
        self.assertIn('"comment"', output)

    def test_limit_zero_shows_all(self):
        """--limit 0 is treated as 'show all' (no slicing)."""
        activities = [ACTIVITY_WITH_COMMENT]
        args = self._make_args(limit=0)
        output = self._run_command(args, activities)
        # Should still display the comment (not filtered out)
        self.assertIn("This is a comment", output)

    def test_limit_negative_shows_all(self):
        """--limit with negative value is treated as 'show all'."""
        activities = [ACTIVITY_WITH_COMMENT]
        args = self._make_args(limit=-5)
        output = self._run_command(args, activities)
        self.assertIn("This is a comment", output)


MINIMAL_WP = {
    "id": 123,
    "subject": "Test WP",
    "createdAt": "2025-01-01T00:00:00Z",
    "updatedAt": "2025-01-01T00:00:00Z",
    "_links": {
        "status": {"title": "New"},
        "type": {"title": "Task"},
        "priority": {"title": "Normal"},
        "assignee": {"title": "Unassigned"},
        "author": {"title": "Admin"},
    },
}


class TestGetWorkPackageCommentCount(unittest.TestCase):
    """Tests for comment count display in command_get_work_package()."""

    def _run_get_wp(self, activities):
        """Run command_get_work_package with mocked client, return captured stdout."""
        mock_client = MagicMock()
        mock_client.get_work_package.return_value = MINIMAL_WP
        mock_client.get_activities.return_value = activities
        args = argparse.Namespace(id=123, debug_json=False)
        buf = io.StringIO()
        with patch.object(cli, "build_client_from_env", return_value=mock_client):
            with contextlib.redirect_stdout(buf):
                cli.command_get_work_package(args)
        return buf.getvalue()

    def test_zero_comments_displays_comments_zero(self):
        """When no activities have comments, output contains 'Comments: 0'."""
        output = self._run_get_wp([ACTIVITY_WITHOUT_COMMENT])
        self.assertIn("Comments: 0", output)

    def test_mixed_activities_shows_correct_count(self):
        """Mixed activities (some with comments, some without) shows correct count."""
        activities = [ACTIVITY_WITH_COMMENT, ACTIVITY_WITHOUT_COMMENT, ACTIVITY_WITH_COMMENT]
        output = self._run_get_wp(activities)
        self.assertIn("Comments: 2", output)


if __name__ == "__main__":
    unittest.main()
