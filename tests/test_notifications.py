"""Unit tests for notification features in scripts/openproject_cli.py."""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
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


SAMPLE_NOTIFICATION = {
    "id": 42,
    "reason": "mentioned",
    "readIAN": False,
    "createdAt": "2025-01-15T10:30:00Z",
    "_links": {
        "project": {"href": "/api/v3/projects/5", "title": "My Project"},
        "resource": {"href": "/api/v3/work_packages/123", "title": "Fix login bug"},
        "actor": {"href": "/api/v3/users/7", "title": "Jane Doe"},
    },
}

SAMPLE_NOTIFICATION_READ = {
    "id": 99,
    "reason": "assigned",
    "readIAN": True,
    "createdAt": "2025-01-14T08:00:00Z",
    "_links": {
        "project": {"href": "/api/v3/projects/5", "title": "My Project"},
        "resource": {"href": "/api/v3/work_packages/456", "title": "Update docs"},
        "actor": {"href": "/api/v3/users/8", "title": "John Smith"},
    },
}


class TestListNotificationsClient(unittest.TestCase):
    """Tests for OpenProjectClient.list_notifications()."""

    def _make_client(self):
        return cli.OpenProjectClient(
            base_url="https://example.openproject.com", api_token="test-token"
        )

    def test_calls_collect_collection_with_correct_path_and_limit(self):
        """Verify list_notifications calls _collect_collection with /notifications and default limit."""
        client = self._make_client()
        fake = [SAMPLE_NOTIFICATION]
        with patch.object(client, "_collect_collection", return_value=fake) as mock_cc:
            result = client.list_notifications()
        mock_cc.assert_called_once_with("/notifications", limit=200)
        self.assertEqual(result, fake)


class TestGetNotificationClient(unittest.TestCase):
    """Tests for OpenProjectClient.get_notification()."""

    def _make_client(self):
        return cli.OpenProjectClient(
            base_url="https://example.openproject.com", api_token="test-token"
        )

    def test_calls_request_with_correct_get_path(self):
        """Verify get_notification calls _request with GET and correct path."""
        client = self._make_client()
        with patch.object(client, "_request", return_value=SAMPLE_NOTIFICATION) as mock_req:
            result = client.get_notification(42)
        mock_req.assert_called_once_with("GET", "/notifications/42", expected_statuses=(200,))
        self.assertEqual(result, SAMPLE_NOTIFICATION)


class TestReadNotificationClient(unittest.TestCase):
    """Tests for OpenProjectClient.read_notification()."""

    def _make_client(self):
        return cli.OpenProjectClient(
            base_url="https://example.openproject.com", api_token="test-token"
        )

    def test_calls_request_with_post_read_ian(self):
        """Verify read_notification calls _request with POST to /read_ian."""
        client = self._make_client()
        with patch.object(client, "_request", return_value={}) as mock_req:
            result = client.read_notification(42)
        mock_req.assert_called_once_with(
            "POST", "/notifications/42/read_ian", expected_statuses=(204,)
        )
        self.assertEqual(result, {})


class TestUnreadNotificationClient(unittest.TestCase):
    """Tests for OpenProjectClient.unread_notification()."""

    def _make_client(self):
        return cli.OpenProjectClient(
            base_url="https://example.openproject.com", api_token="test-token"
        )

    def test_calls_request_with_post_unread_ian(self):
        """Verify unread_notification calls _request with POST to /unread_ian."""
        client = self._make_client()
        with patch.object(client, "_request", return_value={}) as mock_req:
            result = client.unread_notification(42)
        mock_req.assert_called_once_with(
            "POST", "/notifications/42/unread_ian", expected_statuses=(204,)
        )
        self.assertEqual(result, {})


class TestReadAllNotificationsClient(unittest.TestCase):
    """Tests for OpenProjectClient.read_all_notifications()."""

    def _make_client(self):
        return cli.OpenProjectClient(
            base_url="https://example.openproject.com", api_token="test-token"
        )

    def test_calls_request_with_post_collection_read_ian(self):
        """Verify read_all_notifications calls _request with POST to /notifications/read_ian."""
        client = self._make_client()
        with patch.object(client, "_request", return_value={}) as mock_req:
            result = client.read_all_notifications()
        mock_req.assert_called_once_with(
            "POST", "/notifications/read_ian", expected_statuses=(204,)
        )
        self.assertEqual(result, {})


class TestFilterNotifications(unittest.TestCase):
    """Tests for filter_notifications()."""

    def test_filter_by_reason_case_insensitive(self):
        """Verify reason filter is case-insensitive."""
        notifications = [SAMPLE_NOTIFICATION, SAMPLE_NOTIFICATION_READ]
        result = cli.filter_notifications(notifications, reason="MENTIONED")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["reason"], "mentioned")

    def test_filter_unread_only(self):
        """Verify unread_only keeps only readIAN=False notifications."""
        notifications = [SAMPLE_NOTIFICATION, SAMPLE_NOTIFICATION_READ]
        result = cli.filter_notifications(notifications, unread_only=True)
        self.assertEqual(len(result), 1)
        self.assertFalse(result[0]["readIAN"])

    def test_no_filters_returns_all(self):
        """Verify no filters returns all notifications unchanged."""
        notifications = [SAMPLE_NOTIFICATION, SAMPLE_NOTIFICATION_READ]
        result = cli.filter_notifications(notifications)
        self.assertEqual(len(result), 2)


class TestPrintNotifications(unittest.TestCase):
    """Tests for print_notifications() output."""

    def test_output_contains_expected_columns(self):
        """Verify tabular output contains ID, reason, resource subject, project, read status."""
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cli.print_notifications([SAMPLE_NOTIFICATION])
        output = buf.getvalue()
        self.assertIn("42", output)
        self.assertIn("mentioned", output)
        self.assertIn("Fix login bug", output)
        self.assertIn("My Project", output)
        self.assertIn("No", output)  # readIAN=False -> "No"


class TestPrintNotificationDetail(unittest.TestCase):
    """Tests for print_notification_detail() output."""

    def test_output_contains_expected_fields(self):
        """Verify detail output contains ID, reason, read status, project, resource subject."""
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cli.print_notification_detail(SAMPLE_NOTIFICATION)
        output = buf.getvalue()
        self.assertIn("Notification #42", output)
        self.assertIn("mentioned", output)
        self.assertIn("No", output)  # readIAN=False -> Read: No
        self.assertIn("Fix login bug", output)
        self.assertIn("My Project", output)


class TestCommandListNotifications(unittest.TestCase):
    """Tests for command_list_notifications()."""

    def _make_args(self, reason=None, unread_only=False, limit=None, debug_json=False):
        return argparse.Namespace(
            reason=reason, unread_only=unread_only, limit=limit, debug_json=debug_json
        )

    def _run_command(self, args, notifications):
        mock_client = MagicMock()
        mock_client.list_notifications.return_value = notifications
        buf = io.StringIO()
        with patch.object(cli, "build_client_from_env", return_value=mock_client):
            with contextlib.redirect_stdout(buf):
                cli.command_list_notifications(args)
        return buf.getvalue()

    def test_success_shows_formatted_output(self):
        """Verify command outputs formatted notification data."""
        args = self._make_args()
        output = self._run_command(args, [SAMPLE_NOTIFICATION])
        self.assertIn("42", output)
        self.assertIn("mentioned", output)

    def test_empty_result_shows_no_notifications_message(self):
        """Verify empty result prints 'No notifications found.'"""
        args = self._make_args()
        output = self._run_command(args, [])
        self.assertIn("No notifications found.", output)

    def test_debug_json_flag_triggers_json_output(self):
        """Verify --debug-json causes raw JSON to appear in output."""
        args = self._make_args(debug_json=True)
        output = self._run_command(args, [SAMPLE_NOTIFICATION])
        self.assertIn('"id": 42', output)


class TestCommandGetNotification(unittest.TestCase):
    """Tests for command_get_notification()."""

    def test_success_shows_detail_output(self):
        """Verify command outputs notification detail."""
        mock_client = MagicMock()
        mock_client.get_notification.return_value = SAMPLE_NOTIFICATION
        args = argparse.Namespace(id=42, debug_json=False)
        buf = io.StringIO()
        with patch.object(cli, "build_client_from_env", return_value=mock_client):
            with contextlib.redirect_stdout(buf):
                cli.command_get_notification(args)
        output = buf.getvalue()
        self.assertIn("Notification #42", output)
        self.assertIn("mentioned", output)


class TestCommandReadNotification(unittest.TestCase):
    """Tests for command_read_notification()."""

    def test_success_shows_confirmation_with_id(self):
        """Verify confirmation message contains the notification ID."""
        mock_client = MagicMock()
        mock_client.read_notification.return_value = {}
        args = argparse.Namespace(id=42, debug_json=False)
        buf = io.StringIO()
        with patch.object(cli, "build_client_from_env", return_value=mock_client):
            with contextlib.redirect_stdout(buf):
                cli.command_read_notification(args)
        output = buf.getvalue()
        self.assertIn("42", output)
        self.assertIn("read", output.lower())


class TestCommandUnreadNotification(unittest.TestCase):
    """Tests for command_unread_notification()."""

    def test_success_shows_confirmation_with_id(self):
        """Verify confirmation message contains the notification ID."""
        mock_client = MagicMock()
        mock_client.unread_notification.return_value = {}
        args = argparse.Namespace(id=42, debug_json=False)
        buf = io.StringIO()
        with patch.object(cli, "build_client_from_env", return_value=mock_client):
            with contextlib.redirect_stdout(buf):
                cli.command_unread_notification(args)
        output = buf.getvalue()
        self.assertIn("42", output)
        self.assertIn("unread", output.lower())


class TestCommandReadAllNotifications(unittest.TestCase):
    """Tests for command_read_all_notifications()."""

    def test_success_shows_confirmation_message(self):
        """Verify confirmation message for read-all."""
        mock_client = MagicMock()
        mock_client.read_all_notifications.return_value = {}
        args = argparse.Namespace(debug_json=False)
        buf = io.StringIO()
        with patch.object(cli, "build_client_from_env", return_value=mock_client):
            with contextlib.redirect_stdout(buf):
                cli.command_read_all_notifications(args)
        output = buf.getvalue()
        self.assertIn("All notifications marked as read.", output)


class TestNotificationParserRegistration(unittest.TestCase):
    """Tests for notification subparser registration in build_parser()."""

    def test_all_five_subcommands_parse(self):
        """Verify all five notification subcommands are registered and parse correctly."""
        parser = cli.build_parser()
        for cmd in [
            "list-notifications",
            "get-notification",
            "read-notification",
            "unread-notification",
            "read-all-notifications",
        ]:
            args = parser.parse_args([cmd] if cmd in ("list-notifications", "read-all-notifications") else [cmd, "--id", "1"])
            self.assertTrue(hasattr(args, "func"), f"{cmd} missing func attribute")


class TestNotificationErrorPropagation(unittest.TestCase):
    """Tests for error propagation from client methods."""

    def _make_client(self):
        return cli.OpenProjectClient(
            base_url="https://example.openproject.com", api_token="test-token"
        )

    def test_openproject_error_propagates(self):
        """Verify OpenProjectError raised by _request propagates from get_notification."""
        client = self._make_client()
        error = cli.OpenProjectError("Not Found", status_code=404)
        with patch.object(client, "_request", side_effect=error):
            with self.assertRaises(cli.OpenProjectError) as ctx:
                client.get_notification(999)
        self.assertEqual(ctx.exception.status_code, 404)
        self.assertIn("Not Found", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
