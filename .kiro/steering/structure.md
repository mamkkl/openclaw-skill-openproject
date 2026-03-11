# Project Structure

```
openclaw-skill-openproject/
├── SKILL.md                          # Skill definition — agent behavior policy and safety rules
├── README.md                         # Canonical onboarding and operations doc
├── SECURITY.md                       # Security policy and vulnerability reporting
├── CHANGELOG.md                      # Version history
├── LICENSE                           # MIT license
├── requirements.txt                  # Python dependencies
├── .env.example                      # Environment variable template (never commit .env)
├── scripts/
│   ├── openproject_cli.py            # Single-file CLI — all API logic, commands, and helpers
│   └── openproject_wiki_cli.py       # Wiki operations via browser automation (Playwright)
├── tests/
│   └── test_cli_helpers.py           # Unit tests for CLI helper functions
├── templates/
│   ├── decision-log-entry.md         # Template for decision log Markdown files
│   └── weekly-status-template.md     # Template for weekly status Markdown files
└── project-knowledge/
    ├── decisions/                    # Generated decision log entries (date-slugged .md files)
    ├── status/                       # Generated weekly status summaries (date-based .md files)
    └── wiki-drafts/                  # Local wiki content drafts before browser-push
```

## Conventions

- All CLI logic lives in a single file: `scripts/openproject_cli.py`
- No package structure — the CLI is loaded directly, not installed via pip
- Knowledge artifacts use date-based filenames (e.g., `2026-03-09-weekly-status.md`, `2026-03-09_adopt-cli.md`)
- Templates in `templates/` define the shape of generated Markdown outputs
- Policy and agent constraints belong in `SKILL.md`, not in code comments
- Keep `README.md` and `SKILL.md` in sync when adding or changing commands
