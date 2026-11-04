import csv
from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Any
import requests


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
LOG_FILE_PATH = DATA_DIR / "pipeline_log.csv"
ENV_FILE_PATH = BASE_DIR / ".env"


def load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


load_env_file(ENV_FILE_PATH)

OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://localhost:11434/api/generate")
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
REQUEST_TIMEOUT_SECONDS = int(os.getenv("OLLAMA_TIMEOUT", "30"))

CSV_HEADERS = [
    "timestamp",
    "filename",
    "status",
    "model_used",
    "error_message",
]


class EmptyFileError(ValueError):
    pass


def get_utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_prompt(raw_notes: str) -> str:
    return (
        "You are a technical program manager. "
        "Convert the following unstructured engineering meeting notes into a concise "
        "Markdown summary.\n\n"
        "Requirements:\n"
        "1. Include a line of relevant tags (e.g., #Backend #Security #DevOps).\n"
        "2. Summarize the notes into 3 bullet points covering priority, action items, "
        "owners, and deadlines.\n"
        "3. Write in clear, direct English.\n\n"
        f"Notes:\n\"\"\"\n{raw_notes}\n\"\"\""
    )


def log_pipeline_event(
    log_path: Path,
    filename: str,
    status: str,
    model_used: str,
    error_message: str = "None",
) -> None:
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_exists = log_path.exists() and log_path.stat().st_size > 0

        with log_path.open(mode="a", encoding="utf-8", newline="") as csv_file:
            writer = csv.writer(csv_file)
            if not file_exists:
                writer.writerow(CSV_HEADERS)

            writer.writerow([
                get_utc_timestamp(),
                filename,
                status,
                model_used,
                error_message,
            ])
    except OSError as io_err:
        print(f"[CRITICAL] Failed to write audit log at '{log_path}': {io_err}")


def read_text_file(file_path: Path) -> str:
    content = file_path.read_text(encoding="utf-8")
    return content.strip()


def generate_structured_markdown(
    raw_text: str,
    model_name: str = DEFAULT_MODEL,
    api_url: str = OLLAMA_API_URL,
    timeout: int = REQUEST_TIMEOUT_SECONDS,
) -> str:
    payload: dict[str, Any] = {
        "model": model_name,
        "prompt": build_prompt(raw_text),
        "stream": False,
    }

    response = requests.post(api_url, json=payload, timeout=timeout)
    response.raise_for_status()

    response_data: dict[str, Any] = response.json()
    generated_markdown = str(response_data.get("response", "")).strip()

    if not generated_markdown:
        raise ValueError("Ollama API returned an empty response payload.")

    return generated_markdown


def resolve_output_path(input_path: Path) -> Path:
    stem = input_path.stem
    if stem.startswith("input_"):
        output_stem = stem.replace("input_", "output_", 1)
    else:
        output_stem = f"{stem}_output"

    return input_path.parent / f"{output_stem}.md"


def save_markdown_output(output_path: Path, markdown_content: str) -> None:
    output_path.write_text(markdown_content + "\n", encoding="utf-8")


def process_single_file(
    file_path: Path,
    log_path: Path,
    model_name: str = DEFAULT_MODEL,
) -> bool:
    filename = file_path.name
    print(f"[INFO] Processing {filename}...")

    try:
        raw_notes = read_text_file(file_path)
        structured_md = generate_structured_markdown(
            raw_text=raw_notes,
            model_name=model_name,
        )

        output_path = resolve_output_path(file_path)
        save_markdown_output(output_path, structured_md)

        log_pipeline_event(
            log_path=log_path,
            filename=filename,
            status="SUCCESS",
            model_used=model_name,
        )
        print(f"[OK] Saved {output_path.name}")
        return True

    except EmptyFileError as empty_err:
        log_pipeline_event(
            log_path=log_path,
            filename=filename,
            status="EMPTY_FILE",
            model_used=model_name,
            error_message=str(empty_err),
        )
        print(f"[WARN] Skipped '{filename}': {empty_err}")

    except requests.exceptions.Timeout:
        timeout_msg = (
            f"Ollama API request timed out after {REQUEST_TIMEOUT_SECONDS} seconds "
            f"at {OLLAMA_API_URL}."
        )
        log_pipeline_event(
            log_path=log_path,
            filename=filename,
            status="TIMEOUT_ERROR",
            model_used=model_name,
            error_message=timeout_msg,
        )
        print(f"[ERROR] Timeout on '{filename}': {timeout_msg}")

    except requests.exceptions.RequestException as req_err:
        api_err_msg = f"Ollama HTTP error: {req_err}"
        log_pipeline_event(
            log_path=log_path,
            filename=filename,
            status="API_CONNECTION_ERROR",
            model_used=model_name,
            error_message=api_err_msg,
        )
        print(f"[ERROR] Connection failure for '{filename}': {api_err_msg}")

    except (OSError, UnicodeDecodeError) as io_err:
        io_err_msg = f"File I/O error: {io_err}"
        log_pipeline_event(
            log_path=log_path,
            filename=filename,
            status="FILE_IO_ERROR",
            model_used=model_name,
            error_message=io_err_msg,
        )
        print(f"[ERROR] I/O failure for '{filename}': {io_err_msg}")

    except ValueError as val_err:
        val_err_msg = f"Invalid response payload: {val_err}"
        log_pipeline_event(
            log_path=log_path,
            filename=filename,
            status="INVALID_RESPONSE_ERROR",
            model_used=model_name,
            error_message=val_err_msg,
        )
        print(f"[ERROR] Validation error for '{filename}': {val_err_msg}")

    return False


def run_pipeline(
    data_dir: Path = DATA_DIR,
    log_path: Path = LOG_FILE_PATH,
    model_name: str = DEFAULT_MODEL,
) -> None:
    if not data_dir.exists() or not data_dir.is_dir():
        print(f"[ERROR] Data directory not found: {data_dir}")
        return

    txt_files = sorted(data_dir.glob("*.txt"))
    if not txt_files:
        print(f"[INFO] No .txt files found in '{data_dir}'.")
        return

    print(f"[INFO] Running batch | files={len(txt_files)} | model={model_name}")

    success_count = 0
    for txt_file in txt_files:
        if process_single_file(txt_file, log_path=log_path, model_name=model_name):
            success_count += 1

    print(f"[INFO] Done ({success_count}/{len(txt_files)} succeeded). Log: {log_path}")


if __name__ == "__main__":
    run_pipeline()
