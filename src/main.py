from pathlib import Path
import os
from typing import Any
import requests


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
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
    return str(response_data.get("response", "")).strip()
