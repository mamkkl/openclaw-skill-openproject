"""Unit tests for file attachment features in scripts/openproject_cli.py."""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


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
# 7.1 TestFormatFileSize
# ---------------------------------------------------------------------------
class TestFormatFileSize(unittest.TestCase):
    """Unit tests for format_file_size helper."""

    def test_zero_returns_zero_b(self):
        self.assertEqual(cli.format_file_size(0), "0 B")

    def test_one_byte(self):
        self.assertEqual(cli.format_file_size(1), "1 B")

    def test_1023_bytes(self):
        self.assertEqual(cli.format_file_size(1023), "1023 B")

    def test_1024_bytes(self):
        self.assertEqual(cli.format_file_size(1024), "1.0 KB")

    def test_1048576_bytes(self):
        self.assertEqual(cli.format_file_size(1048576), "1.0 MB")

    def test_1073741824_bytes(self):
        self.assertEqual(cli.format_file_size(1073741824), "1.0 GB")

    def test_negative_returns_zero_b(self):
        self.assertEqual(cli.format_file_size(-5), "0 B")


# ---------------------------------------------------------------------------
# 7.2 TestPrintAttachments
# ---------------------------------------------------------------------------
class TestPrintAttachments(unittest.TestCase):
    """Unit tests for print_attachments formatter."""

    def test_empty_list_prints_message(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cli.print_attachments([])
        self.assertIn("No attachments found", buf.getvalue())

    def test_single_attachment_displays_all_columns(self):
        attachment = {
            "id": 42,
            "fileName": "report.pdf",
            "fileSize": 125432,
            "contentType": "application/pdf",
            "createdAt": "2026-03-15T10:30:00Z",
        }
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cli.print_attachments([attachment])
        output = buf.getvalue()
        self.assertIn("42", output)
        self.assertIn("report.pdf", output)
        self.assertIn("application/pdf", output)
        self.assertIn("2026-03-15", output)


# ---------------------------------------------------------------------------
# 7.3 TestCommandUploadAttachment
# ---------------------------------------------------------------------------
class TestCommandUploadAttachment(unittest.TestCase):
    """Unit tests for command_upload_attachment."""

    def test_file_not_found_skips_and_continues(self):
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
        tmp.write(b"hello")
        tmp.close()
        try:
            args = argparse.Namespace(
                file=["/nonexistent/file.txt", tmp.name],
                id=1,
                debug_json=False,
                description=None,
            )
            mock_client = MagicMock()
            mock_client.upload_attachment.return_value = {
                "id": 10,
                "fileName": os.path.basename(tmp.name),
                "fileSize": 5,
            }
            buf = io.StringIO()
            with patch.object(cli, "build_client_from_env", return_value=mock_client):
                with contextlib.redirect_stdout(buf):
                    cli.command_upload_attachment(args)
            mock_client.upload_attachment.assert_called_once()
        finally:
            os.unlink(tmp.name)

    def test_directory_path_skips_and_continues(self):
        tmpdir = tempfile.mkdtemp()
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
        tmp.write(b"hello")
        tmp.close()
        try:
            args = argparse.Namespace(
                file=[tmpdir, tmp.name],
                id=1,
                debug_json=False,
                description=None,
            )
            mock_client = MagicMock()
            mock_client.upload_attachment.return_value = {
                "id": 11,
                "fileName": os.path.basename(tmp.name),
                "fileSize": 5,
            }
            buf = io.StringIO()
            with patch.object(cli, "build_client_from_env", return_value=mock_client):
                with contextlib.redirect_stdout(buf):
                    cli.command_upload_attachment(args)
            mock_client.upload_attachment.assert_called_once()
        finally:
            os.unlink(tmp.name)
            os.rmdir(tmpdir)

    def test_all_files_invalid_exits_without_api_calls(self):
        args = argparse.Namespace(
            file=["/nonexistent1.txt", "/nonexistent2.txt"],
            id=1,
            debug_json=False,
            description=None,
        )
        mock_client = MagicMock()
        with patch.object(cli, "build_client_from_env", return_value=mock_client):
            with self.assertRaises(SystemExit):
                cli.command_upload_attachment(args)
        mock_client.upload_attachment.assert_not_called()

    def test_partial_failure_continues_and_reports(self):
        tmp1 = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
        tmp1.write(b"aaa")
        tmp1.close()
        tmp2 = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
        tmp2.write(b"bbb")
        tmp2.close()
        try:
            args = argparse.Namespace(
                file=[tmp1.name, tmp2.name],
                id=1,
                debug_json=False,
                description=None,
            )
            mock_client = MagicMock()
            mock_client.upload_attachment.side_effect = [
                cli.OpenProjectError("fail", status_code=500),
                {"id": 20, "fileName": os.path.basename(tmp2.name), "fileSize": 3},
            ]
            buf = io.StringIO()
            with patch.object(cli, "build_client_from_env", return_value=mock_client):
                with contextlib.redirect_stdout(buf):
                    with self.assertRaises(SystemExit):
                        cli.command_upload_attachment(args)
            self.assertEqual(mock_client.upload_attachment.call_count, 2)
        finally:
            os.unlink(tmp1.name)
            os.unlink(tmp2.name)


# ---------------------------------------------------------------------------
# 7.4 TestCommandListAttachments
# ---------------------------------------------------------------------------
class TestCommandListAttachments(unittest.TestCase):
    """Unit tests for command_list_attachments."""

    def test_empty_result_prints_message(self):
        args = argparse.Namespace(id=42, debug_json=False)
        mock_client = MagicMock()
        mock_client._request.return_value = {"_embedded": {"elements": []}}
        buf = io.StringIO()
        with patch.object(cli, "build_client_from_env", return_value=mock_client):
            with contextlib.redirect_stdout(buf):
                cli.command_list_attachments(args)
        self.assertIn("No attachments found for work package #42", buf.getvalue())


# ---------------------------------------------------------------------------
# 7.5 TestCommandDownloadAttachment
# ---------------------------------------------------------------------------
class TestCommandDownloadAttachment(unittest.TestCase):
    """Unit tests for command_download_attachment."""

    def test_missing_parent_directory_prints_error(self):
        args = argparse.Namespace(id=1, output="/nonexistent_dir/file.txt", debug_json=False)
        mock_client = MagicMock()
        mock_client.get_attachment.return_value = {
            "fileName": "file.txt",
            "_links": {"downloadLocation": {"href": "https://example.com/dl"}},
        }
        err_buf = io.StringIO()
        with patch.object(cli, "build_client_from_env", return_value=mock_client):
            with contextlib.redirect_stderr(err_buf):
                with self.assertRaises(SystemExit):
                    cli.command_download_attachment(args)
        self.assertIn("Output directory does not exist", err_buf.getvalue())

    def test_omitted_output_uses_original_filename(self):
        tmpdir = tempfile.mkdtemp()
        original_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)
            args = argparse.Namespace(id=1, output=None, debug_json=False)
            mock_client = MagicMock()
            mock_client.get_attachment.return_value = {
                "fileName": "report.pdf",
                "_links": {"downloadLocation": {"href": "https://example.com/dl"}},
            }
            mock_client.download_attachment_content.return_value = b"content"
            buf = io.StringIO()
            with patch.object(cli, "build_client_from_env", return_value=mock_client):
                with contextlib.redirect_stdout(buf):
                    cli.command_download_attachment(args)
            self.assertTrue(Path(tmpdir, "report.pdf").exists())
        finally:
            os.chdir(original_cwd)
            # Clean up
            report_path = Path(tmpdir, "report.pdf")
            if report_path.exists():
                report_path.unlink()
            os.rmdir(tmpdir)


# ---------------------------------------------------------------------------
# 7.6 TestClientMethods
# ---------------------------------------------------------------------------
class TestClientMethods(unittest.TestCase):
    """Unit tests for OpenProjectClient attachment methods."""

    def _make_client(self) -> cli.OpenProjectClient:
        return cli.OpenProjectClient(
            base_url="https://example.openproject.com",
            api_token="test-token",
        )

    def test_upload_attachment_sends_correct_multipart_structure(self):
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
        tmp.write(b"test content")
        tmp.close()
        try:
            client = self._make_client()
            mock_response = MagicMock()
            mock_response.status_code = 201
            mock_response.json.return_value = {"id": 1, "fileName": "test.txt", "fileSize": 12}
            with patch.object(client.session, "post", return_value=mock_response) as mock_post:
                result = client.upload_attachment(1, tmp.name, "desc")
            mock_post.assert_called_once()
            call_kwargs = mock_post.call_args
            files_arg = call_kwargs.kwargs.get("files") or call_kwargs[1].get("files")
            # Verify metadata part
            metadata_tuple = files_arg["metadata"]
            metadata_json = json.loads(metadata_tuple[1])
            self.assertEqual(metadata_json["fileName"], os.path.basename(tmp.name))
            self.assertEqual(metadata_json["description"], "desc")
            # Verify file part
            file_tuple = files_arg["file"]
            self.assertEqual(file_tuple[0], os.path.basename(tmp.name))
            self.assertEqual(result["id"], 1)
        finally:
            os.unlink(tmp.name)

    def test_download_attachment_content_absolute_url(self):
        client = self._make_client()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"data"
        with patch.object(client.session, "get", return_value=mock_response) as mock_get:
            result = client.download_attachment_content("https://cdn.example.com/file.bin")
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        self.assertEqual(call_args[0][0], "https://cdn.example.com/file.bin")
        self.assertEqual(result, b"data")

    def test_download_attachment_content_relative_url(self):
        client = self._make_client()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"data"
        with patch.object(client.session, "get", return_value=mock_response) as mock_get:
            result = client.download_attachment_content("/attachments/42/file.bin")
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        self.assertEqual(call_args[0][0], "https://example.openproject.com/attachments/42/file.bin")
        self.assertEqual(result, b"data")


if __name__ == "__main__":
    unittest.main()
