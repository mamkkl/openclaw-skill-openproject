"""Unit tests for list-project-members feature in scripts/openproject_cli.py."""

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


# ---------------------------------------------------------------------------
# Sample membership HAL objects
# ---------------------------------------------------------------------------

SAMPLE_MEMBER_JANE = {
    "id": 42,
    "_links": {
        "principal": {"href": "/api/v3/users/5", "title": "Jane Doe"},
        "roles": [
            {"href": "/api/v3/roles/3", "title": "Member"},
            {"href": "/api/v3/roles/7", "title": "Developer"},
        ],
        "project": {"href": "/api/v3/projects/1", "title": "My Project"},
    },
}

SAMPLE_MEMBER_BOB = {
    "id": 99,
    "_links": {
        "principal": {"href": "/api/v3/users/8", "title": "Bob Smith"},
        "roles": [
            {"href": "/api/v3/roles/3", "title": "Member"},
        ],
        "project": {"href": "/api/v3/projects/1", "title": "My Project"},
    },
}


# ---------------------------------------------------------------------------
# 1. Client method tests
# ---------------------------------------------------------------------------


class TestGetProjectMemberships(unittest.TestCase):
    """Tests for OpenProjectClient.get_project_memberships()."""

    def _make_client(self) -> cli.OpenProjectClient:
        return cli.OpenProjectClient(
            base_url="https://example.openproject.com",
            api_token="test-token",
        )

    def test_calls_collect_collection_with_correct_params(self) -> None:
        """Verify path, filters JSON, and limit are forwarded correctly."""
        client = self._make_client()
        fake_members = [SAMPLE_MEMBER_JANE]

        with patch.object(client, "_collect_collection", return_value=fake_members) as mock_collect:
            result = client.get_project_memberships(7, limit=50)

        expected_filters = json.dumps([{"project": {"operator": "=", "values": ["7"]}}])
        mock_collect.assert_called_once_with(
            "/memberships",
            params={"filters": expected_filters},
            limit=50,
        )
        self.assertEqual(result, fake_members)

    def test_default_limit(self) -> None:
        """Verify default limit of 200 when not specified."""
        client = self._make_client()

        with patch.object(client, "_collect_collection", return_value=[]) as mock_collect:
            client.get_project_memberships(1)

        _, kwargs = mock_collect.call_args
        self.assertEqual(kwargs["limit"], 200)


# ---------------------------------------------------------------------------
# 2. Filter function tests
# ---------------------------------------------------------------------------


class TestFilterMembers(unittest.TestCase):
    """Tests for filter_members()."""

    def test_empty_query_returns_all(self) -> None:
        """None/empty query returns all members unchanged."""
        members = [SAMPLE_MEMBER_JANE, SAMPLE_MEMBER_BOB]
        self.assertEqual(cli.filter_members(members, None), members)
        self.assertEqual(cli.filter_members(members, ""), members)

    def test_matching_query(self) -> None:
        """Case-insensitive match on principal name."""
        members = [SAMPLE_MEMBER_JANE, SAMPLE_MEMBER_BOB]
        result = cli.filter_members(members, "jane")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], 42)

    def test_no_matches_returns_empty(self) -> None:
        """Non-matching query returns empty list."""
        members = [SAMPLE_MEMBER_JANE, SAMPLE_MEMBER_BOB]
        result = cli.filter_members(members, "zzz_nonexistent")
        self.assertEqual(result, [])


# ---------------------------------------------------------------------------
# 3. Formatter tests
# ---------------------------------------------------------------------------


class TestPrintMembers(unittest.TestCase):
    """Tests for print_members()."""

    def _capture(self, members):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cli.print_members(members)
        return buf.getvalue()

    def test_empty_list(self) -> None:
        """Empty list prints 'No members found.'"""
        output = self._capture([])
        self.assertIn("No members found.", output)

    def test_single_member(self) -> None:
        """Single member prints correct table row with ID, name, roles."""
        output = self._capture([SAMPLE_MEMBER_BOB])
        self.assertIn("8", output)           # member ID from href
        self.assertIn("Bob Smith", output)    # principal name
        self.assertIn("Member", output)       # role

    def test_multiple_roles(self) -> None:
        """Multiple roles are comma-separated in output."""
        output = self._capture([SAMPLE_MEMBER_JANE])
        self.assertIn("Member, Developer", output)


# ---------------------------------------------------------------------------
# 4. Command tests
# ---------------------------------------------------------------------------


class TestCommandListProjectMembers(unittest.TestCase):
    """Tests for command_list_project_members()."""

    FAKE_PROJECT = {"id": 1, "name": "My Project", "identifier": "my-project"}

    def _make_args(self, project="my-project", query=None, limit=200, debug_json=False):
        return argparse.Namespace(
            project=project, query=query, limit=limit, debug_json=debug_json,
        )

    def _run_command(self, args, members):
        """Run command with mocked client, return captured stdout."""
        mock_client = MagicMock()
        mock_client.resolve_project.return_value = self.FAKE_PROJECT
        mock_client.get_project_memberships.return_value = members
        buf = io.StringIO()
        with patch.object(cli, "build_client_from_env", return_value=mock_client):
            with contextlib.redirect_stdout(buf):
                cli.command_list_project_members(args)
        return buf.getvalue()

    def test_success_output(self) -> None:
        """Prints project header and member table."""
        args = self._make_args()
        output = self._run_command(args, [SAMPLE_MEMBER_JANE])
        self.assertIn("Project: My Project", output)
        self.assertIn("Jane Doe", output)
        self.assertIn("Member, Developer", output)

    def test_debug_json(self) -> None:
        """--debug-json flag triggers JSON output."""
        args = self._make_args(debug_json=True)
        output = self._run_command(args, [SAMPLE_MEMBER_JANE])
        self.assertIn('"id": 42', output)

    def test_error_propagation(self) -> None:
        """OpenProjectError from client propagates."""
        mock_client = MagicMock()
        mock_client.resolve_project.side_effect = cli.OpenProjectError("Forbidden", status_code=403)
        args = self._make_args()
        with patch.object(cli, "build_client_from_env", return_value=mock_client):
            with self.assertRaises(cli.OpenProjectError) as ctx:
                cli.command_list_project_members(args)
        self.assertEqual(ctx.exception.status_code, 403)


# ---------------------------------------------------------------------------
# 5. Parser registration tests
# ---------------------------------------------------------------------------


class TestParserRegistration(unittest.TestCase):
    """Tests for list-project-members subparser registration."""

    def test_list_project_members_parses(self) -> None:
        """Subcommand parses with --project, --query, --limit."""
        parser = cli.build_parser()
        args = parser.parse_args([
            "list-project-members",
            "--project", "my-proj",
            "--query", "jane",
            "--limit", "50",
        ])
        self.assertEqual(args.project, "my-proj")
        self.assertEqual(args.query, "jane")
        self.assertEqual(args.limit, 50)
        self.assertEqual(args.func, cli.command_list_project_members)


if __name__ == "__main__":
    unittest.main()
