# Product Overview

openclaw-skill-openproject is an alpha OpenClaw skill that provides conservative OpenProject project management operations via a Python CLI wrapper. It combines:

- Read/write operations against OpenProject API v3 (work packages, statuses, types, priorities, users, relations)
- Lightweight local knowledge artifacts: weekly status summaries and decision logs in Markdown
- A skill definition (SKILL.md) that governs agent behavior and safety constraints

OpenProject is the source of truth for execution status. Local Markdown files serve as auditable, version-controlled artifacts.

Current version: v0.1.4-alpha

## Key Constraints

- No delete operations — the CLI is deliberately conservative
- No arbitrary shell execution
- Wiki operations use browser automation (Playwright), not the OpenProject API
- Security-first: no secret leakage, least-privilege tokens, `.env` for credentials
- Fail closed with clear errors when permissions or endpoints are unavailable
