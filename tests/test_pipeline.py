import csv
from pathlib import Path
import sys
from unittest.mock import MagicMock, patch

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import main as pipeline


def test_empty_file_skips_ollama_and_logs_warning(tmp_path: Path):
    empty_txt = tmp_path / "empty_notes.txt"
    empty_txt.write_text("   \n  ", encoding="utf-8")
    log_csv = tmp_path / "pipeline_log.csv"

    with patch("main.requests.post") as mock_post:
        ok = pipeline.process_single_file(empty_txt, log_path=log_csv)

    assert ok is False
    mock_post.assert_not_called()

    rows = list(csv.DictReader(log_csv.open(encoding="utf-8")))
    assert len(rows) == 1
    assert rows[0]["filename"] == "empty_notes.txt"
    assert rows[0]["status"] == "EMPTY_FILE"


def test_ollama_timeout_logs_error_and_isolates_failure(tmp_path: Path):
    note_txt = tmp_path / "sprint_notes.txt"
    note_txt.write_text("Database migration scheduled for Friday 10pm UTC.", encoding="utf-8")
    log_csv = tmp_path / "pipeline_log.csv"

    with patch("main.requests.post", side_effect=requests.exceptions.Timeout("Timed out")):
        ok = pipeline.process_single_file(note_txt, log_path=log_csv)

    assert ok is False
    rows = list(csv.DictReader(log_csv.open(encoding="utf-8")))
    assert len(rows) == 1
    assert rows[0]["status"] == "TIMEOUT_ERROR"


def test_successful_file_writes_markdown_and_audit_log(tmp_path: Path):
    input_txt = tmp_path / "input_sync.txt"
    input_txt.write_text("Fix connection pool leak on payments service by Thursday.", encoding="utf-8")
    log_csv = tmp_path / "pipeline_log.csv"

    fake_resp = MagicMock()
    fake_resp.json.return_value = {"response": "# Sync Summary\n\n* Fix pool leak"}
    fake_resp.raise_for_status.return_value = None

    with patch("main.requests.post", return_value=fake_resp):
        ok = pipeline.process_single_file(input_txt, log_path=log_csv, model_name="llama3.2")

    assert ok is True
    output_md = tmp_path / "output_sync.md"
    assert output_md.exists()
    assert "# Sync Summary" in output_md.read_text(encoding="utf-8")

    rows = list(csv.DictReader(log_csv.open(encoding="utf-8")))
    assert len(rows) == 1
    assert rows[0]["status"] == "SUCCESS"
    assert rows[0]["model_used"] == "llama3.2"
