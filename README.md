# AI-Native Data Pipeline

Batch ETL script in Python that reads raw `.txt` engineering notes from `data/`, summarizes them into structured Markdown using a local Ollama LLM, and writes execution records to `data/pipeline_log.csv`.

## Overview

* **Local inference only:** All text processing runs against a local Ollama endpoint (`http://localhost:11434/api/generate`), keeping internal notes off external APIs.
* **Per-file fault isolation:** Malformed files, empty inputs, or inference timeouts are caught per file and recorded in `data/pipeline_log.csv` without aborting the rest of the batch.
* **Minimal dependencies:** Uses Python's standard library (`pathlib`, `csv`, `datetime`) and `requests`.

## Project Structure

```text
ai-native-data-pipeline/
├── data/
│   ├── input_example.txt     # Sample unstructured meeting notes
│   ├── output_example.md     # Generated Markdown summary and tags
│   └── pipeline_log.csv      # Execution audit log
├── src/
│   └── main.py               # Batch processor and Ollama client
├── tests/
│   └── test_pipeline.py      # Unit tests for fault isolation and CSV audit logging
├── .env                      # Default local Ollama configuration
├── requirements.txt          # Dependencies
└── README.md
```

## Audit Log Statuses

Each run appends `[timestamp, filename, status, model_used, error_message]` to `data/pipeline_log.csv`:

| Status | Condition | Behavior |
| :--- | :--- | :--- |
| `SUCCESS` | Input read, summarized, and written to `.md` | Saves output file and logs completion |
| `EMPTY_FILE` | File is empty or whitespace only | Skips Ollama request and logs warning |
| `TIMEOUT_ERROR` | Request exceeds `OLLAMA_TIMEOUT` (default `30s`) | Aborts request and continues batch |
| `API_CONNECTION_ERROR` | Ollama unreachable or non-2xx HTTP status | Logs connection error and continues batch |
| `FILE_IO_ERROR` | Unreadable file or UTF-8 decode failure | Logs I/O error and continues batch |

## Local Setup

### Prerequisites
1. Python 3.10+
2. [Ollama](https://ollama.com/) running locally with `llama3.2` pulled:
   ```bash
   ollama pull llama3.2
   ```

### Run the Pipeline

**Windows (PowerShell):**
```powershell
git clone https://github.com/marlon-hernandez/ai-native-data-pipeline.git
cd ai-native-data-pipeline
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python src/main.py
```

**Linux / macOS:**
```bash
git clone https://github.com/marlon-hernandez/ai-native-data-pipeline.git
cd ai-native-data-pipeline
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python src/main.py
```

### Configuration (`.env`)

Default Ollama settings are pre-configured in `.env` and loaded automatically on startup:

```ini
OLLAMA_API_URL=http://localhost:11434/api/generate
OLLAMA_MODEL=llama3.2
OLLAMA_TIMEOUT=30
```

## Running Tests

```bash
pytest -v
```
