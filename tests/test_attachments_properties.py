"""Hypothesis property tests for wp-attachments feature.

Each test validates a correctness property from the design document using
randomly generated inputs.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from hypothesis import given, settings
import hypothesis.strategies as st
from hypothesis.strategies import from_regex


# ---------------------------------------------------------------------------
# Load CLI module dynamically (same pattern as other test files)
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

_file_name_st = from_regex(r"[A-Za-z][A-Za-z0-9]{1,10}\.[a-z]{2,4}", fullmatch=True)
_content_type_st = from_regex(r"[a-z]{3,10}/[a-z]{3,10}", fullmatch=True)
_created_at_st = from_regex(
    r"20[0-9]{2}-[01][0-9]-[0-3][0-9]T[0-2][0-9]:[0-5][0-9]:[0-5][0-9]Z",
    fullmatch=True,
)
_description_st = from_regex(
    r"[A-Za-z][A-Za-z0-9 ]{0,30}[A-Za-z0-9]", fullmatch=True
)
_output_path_st = from_regex(r"[a-z]{1,5}/[a-z]{1,10}\.[a-z]{2,4}", fullmatch=True)
_dir_path_st = from_regex(
    r"[a-z]{1,5}(/[a-z]{1,5}){1,3}/[a-z]{1,8}\.[a-z]{2,4}", fullmatch=True
)


# ---------------------------------------------------------------------------
# Property 1: Upload confirmation contains required fields
# Feature: wp-attachments, Property 1: Upload confirmation contains required fields
# Validates: Requirements 1.3
# ---------------------------------------------------------------------------

@given(
    aid=st.integers(min_value=1),
    fname=st.text(min_size=1, max_size=30),
    fsize=st.integers(min_value=1),
)
@settings(max_examples=100)
def test_upload_confirmation_contains_required_fields(aid, fname, fsize):
    """Property 1: The upload confirmation line contains the attachment ID,
    file name, and formatted file size."""
    formatted_size = cli.format_file_size(fsize)
    output = f"Uploaded: #{aid} {fname} ({formatted_size})"
    assert str(aid) in output
    assert fname in output
    assert formatted_size in output


# ---------------------------------------------------------------------------
# Property 2: Description propagated to upload metadata
# Feature: wp-attachments, Property 2: Description propagated to upload metadata
# Validates: Requirements 1.5, 1.6
# ---------------------------------------------------------------------------

@given(description=_description_st)
@settings(max_examples=100)
def test_description_propagated_to_upload_metadata(description):
    """Property 2: The description passed to upload_attachment appears in the
    metadata JSON sent to the API."""
    client = cli.OpenProjectClient.__new__(cli.OpenProjectClient)
    client.base_url = "https://example.com"
    client.session = MagicMock()

    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.json.return_value = {"id": 1, "fileName": "test.txt", "fileSize": 100}
    client.session.post.return_value = mock_resp

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
    try:
        tmp.write(b"test content")
        tmp.close()
        client.upload_attachment(1, tmp.name, description)

        call_kwargs = client.session.post.call_args
        files_arg = call_kwargs.kwargs.get("files") or call_kwargs[1].get("files")
        metadata_tuple = files_arg["metadata"]
        metadata_json = json.loads(metadata_tuple[1])
        assert metadata_json["description"] == description
    finally:
        os.unlink(tmp.name)


# ---------------------------------------------------------------------------
# Property 3: Attachment formatter displays all required fields
# Feature: wp-attachments, Property 3: Attachment formatter displays all required fields
# Validates: Requirements 2.2
# ---------------------------------------------------------------------------

@given(
    aid=st.integers(min_value=1, max_value=999999),
    fname=_file_name_st,
    fsize=st.integers(min_value=0, max_value=10**9),
    ctype=_content_type_st,
    created=_created_at_st,
)
@settings(max_examples=100)
def test_attachment_formatter_displays_all_required_fields(aid, fname, fsize, ctype, created):
    """Property 3: print_attachments output contains all field values."""
    attachment = {
        "id": aid,
        "fileName": fname,
        "fileSize": fsize,
        "contentType": ctype,
        "createdAt": created,
    }
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        cli.print_attachments([attachment])
    output = buf.getvalue()

    assert str(aid) in output
    assert fname in output
    assert cli.format_file_size(fsize) in output
    assert ctype in output
    assert cli.format_date(created) in output


# ---------------------------------------------------------------------------
# Property 4: Download confirmation contains required fields
# Feature: wp-attachments, Property 4: Download confirmation contains required fields
# Validates: Requirements 3.2
# ---------------------------------------------------------------------------

@given(
    file_name=_file_name_st,
    byte_count=st.integers(min_value=1),
    output_path=_output_path_st,
)
@settings(max_examples=100)
def test_download_confirmation_contains_required_fields(file_name, byte_count, output_path):
    """Property 4: The download confirmation line contains the file name,
    byte count, and output path."""
    output = f"Downloaded: {file_name} ({byte_count} bytes) -> {output_path}"
    assert file_name in output
    assert str(byte_count) in output
    assert output_path in output


# ---------------------------------------------------------------------------
# Property 5: format_file_size unit correctness
# Feature: wp-attachments, Property 5: format_file_size unit correctness
# Validates: Requirements 4.1, 4.2, 4.3
# ---------------------------------------------------------------------------

@given(size_bytes=st.integers(min_value=0, max_value=10**12))
@settings(max_examples=100)
def test_format_file_size_unit_correctness(size_bytes):
    """Property 5: The unit suffix matches the correct magnitude range."""
    result = cli.format_file_size(size_bytes)
    # Parse the unit suffix (last token)
    parts = result.split()
    assert len(parts) == 2, f"Expected 'value unit', got {result!r}"
    unit = parts[1]

    if size_bytes < 1024:
        assert unit == "B", f"Expected B for {size_bytes}, got {unit}"
    elif size_bytes < 1024**2:
        assert unit == "KB", f"Expected KB for {size_bytes}, got {unit}"
    elif size_bytes < 1024**3:
        assert unit == "MB", f"Expected MB for {size_bytes}, got {unit}"
    else:
        assert unit == "GB", f"Expected GB for {size_bytes}, got {unit}"


# ---------------------------------------------------------------------------
# Property 6: format_file_size round-trip consistency
# Feature: wp-attachments, Property 6: format_file_size round-trip consistency
# Validates: Requirements 4.4
# ---------------------------------------------------------------------------

_UNIT_INDEX = {"B": 0, "KB": 1, "MB": 2, "GB": 3}


@given(size_bytes=st.integers(min_value=0, max_value=10**12))
@settings(max_examples=100)
def test_format_file_size_round_trip_consistency(size_bytes):
    """Property 6: Parsing the formatted string and reconstructing the byte
    count yields a value within rounding tolerance of the original."""
    result = cli.format_file_size(size_bytes)
    parts = result.split()
    numeric = float(parts[0])
    unit = parts[1]
    idx = _UNIT_INDEX[unit]
    reconstructed = numeric * (1024 ** idx)

    if unit == "B":
        assert reconstructed == size_bytes
    else:
        tolerance = 0.05 * (1024 ** idx) + 1
        assert abs(reconstructed - size_bytes) <= tolerance, (
            f"Round-trip mismatch: {size_bytes} -> {result} -> {reconstructed}, "
            f"tolerance={tolerance}"
        )


# ---------------------------------------------------------------------------
# Property 7: File name resolved from basename
# Feature: wp-attachments, Property 7: File name resolved from basename
# Validates: Requirements 5.3
# ---------------------------------------------------------------------------

@given(path_str=_dir_path_st)
@settings(max_examples=100)
def test_file_name_resolved_from_basename(path_str):
    """Property 7: The metadata fileName equals os.path.basename of the
    provided file path."""
    client = cli.OpenProjectClient.__new__(cli.OpenProjectClient)
    client.base_url = "https://example.com"
    client.session = MagicMock()

    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.json.return_value = {"id": 1, "fileName": "test.txt", "fileSize": 100}
    client.session.post.return_value = mock_resp

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
    try:
        tmp.write(b"test content")
        tmp.close()

        client.upload_attachment(1, tmp.name, "")

        call_kwargs = client.session.post.call_args
        files_arg = call_kwargs.kwargs.get("files") or call_kwargs[1].get("files")
        metadata_tuple = files_arg["metadata"]
        metadata_json = json.loads(metadata_tuple[1])
        assert metadata_json["fileName"] == os.path.basename(tmp.name)
    finally:
        os.unlink(tmp.name)
