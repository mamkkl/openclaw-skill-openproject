# Tech Stack

- Language: Python 3.10+
- Dependencies (requirements.txt): `requests>=2.31.0`, `python-dotenv>=1.0.0`
- Wiki dependencies (separate install): `playwright`, `python-dotenv`
- No framework — single-file CLI scripts with argparse
- Auth: HTTP Basic auth with `apikey:<token>` pattern against OpenProject API v3
- Wiki auth: browser login via Playwright (requires OpenProject login credentials, no LLM needed)
- Config: environment variables via `.env` file (loaded with python-dotenv)

## Common Commands

```bash
# Setup
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
cp .env.example .env

# Validate CLI
python3 scripts/openproject_cli.py --help

# Syntax check
python3 -m py_compile scripts/openproject_cli.py

# Run tests
python3 -m unittest discover -s tests -p 'test_*.py'
```

## Testing

- Framework: unittest (stdlib)
- Tests live in `tests/` with `test_*.py` naming
- CLI module is loaded dynamically via `importlib.util` in tests (not installed as a package)
- Use a non-production OpenProject instance for any write-operation testing
