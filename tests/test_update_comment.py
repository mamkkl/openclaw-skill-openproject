"""Unit tests for update-comment feature in scripts/openproject_cli.py."""

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


class TestPositiveInt(unittest.TestCase):
    """Tests for the positive_int argparse type helper."""

    def test_valid_positive_int(self):
        self.assertEqual(cli.positive_int("42"), 42)
        self.assertEqual(cli.positive_int("1"), 1)

    def test_zero_raises(self):
        with self.assertRaises(argparse.ArgumentTypeError):
            cli.positive_int("0")

    def test_negative_raises(self):
        with self.assertRaises(argparse.ArgumentTypeError):
            cli.positive_int("-5")

    def test_non_numeric_raises(self):
        with self.assertRaises(argparse.ArgumentTypeError):
            cli.positive_int("abc")


class TestUpdateCommentParser(unittest.TestCase):
    """Tests for update-comment subparser registration."""

    def setUp(self):
        self.parser = cli.build_parser()

    def test_parses_valid_args(self):
        args = self.parser.parse_args(["update-comment", "--id", "42", "--comment", "hello"])
        self.assertEqual(args.id, 42)
        self.assertEqual(args.comment, "hello")

    def test_missing_id_exits(self):
        with self.assertRaises(SystemExit):
            self.parser.parse_args(["update-comment", "--comment", "hello"])

    def test_missing_comment_exits(self):
        with self.assertRaises(SystemExit):
            self.parser.parse_args(["update-comment", "--id", "42"])


class TestCommandUpdateComment(unittest.TestCase):
    """Tests for command_update_comment function."""

    def test_success_prints_confirmation(self):
        mock_client = MagicMock()
        mock_client.update_comment.return_value = {"_type": "Activity", "id": 42}

        args = argparse.Namespace(id=42, comment="fixed typo", debug_json=False)
        buf = io.StringIO()
        with patch.object(cli, "build_client_from_env", return_value=mock_client):
            with contextlib.redirect_stdout(buf):
                cli.command_update_comment(args)

        self.assertIn("Updated comment on activity #42", buf.getvalue())
        mock_client.update_comment.assert_called_once_with(42, "fixed typo")

    def test_debug_json_prints_json(self):
        mock_client = MagicMock()
        result = {"_type": "Activity", "id": 99, "comment": {"raw": "new text"}}
        mock_client.update_comment.return_value = result

        args = argparse.Namespace(id=99, comment="new text", debug_json=True)
        buf = io.StringIO()
        with patch.object(cli, "build_client_from_env", return_value=mock_client):
            with contextlib.redirect_stdout(buf):
                cli.command_update_comment(args)

        output = buf.getvalue()
        self.assertIn("Updated comment on activity #99", output)
        self.assertIn('"_type": "Activity"', output)

    def test_error_propagation(self):
        mock_client = MagicMock()
        mock_client.update_comment.side_effect = cli.OpenProjectError("boom", status_code=500)

        args = argparse.Namespace(id=1, comment="text", debug_json=False)
        with patch.object(cli, "build_client_from_env", return_value=mock_client):
            with self.assertRaises(cli.OpenProjectError):
                cli.command_update_comment(args)


class TestUpdateCommentClient(unittest.TestCase):
    """Tests for OpenProjectClient.update_comment error cases."""

    def _make_client(self):
        return cli.OpenProjectClient(
            base_url="https://example.openproject.com", api_token="test-token"
        )

    def test_403_propagates(self):
        client = self._make_client()
        with patch.object(client, "_request", side_effect=cli.OpenProjectError("Forbidden", status_code=403)):
            with self.assertRaises(cli.OpenProjectError) as ctx:
                client.update_comment(42, "new text")
            self.assertEqual(ctx.exception.status_code, 403)

    def test_404_propagates(self):
        client = self._make_client()
        with patch.object(client, "_request", side_effect=cli.OpenProjectError("Not found", status_code=404)):
            with self.assertRaises(cli.OpenProjectError) as ctx:
                client.update_comment(999, "new text")
            self.assertEqual(ctx.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
