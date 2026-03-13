---
name: openproject-pm-knowledge
description: Manage OpenProject work packages and lightweight project knowledge artifacts (weekly summaries and decision logs). Use when work requires reading project/work package status and metadata, creating or updating work packages, managing relations, adding comments, generating weekly markdown status updates, or logging project decisions.
---

# OpenProject PM + Knowledge Skill

Purpose: use OpenProject as project source of truth and keep lightweight knowledge artifacts in markdown.

## Safety Rules

- Never execute arbitrary shell commands.
- Only use the local Python wrapper: `scripts/openproject_cli.py`.
- Never expose API tokens, credentials, or secret values.
- Do not perform delete operations in v1.
- Fail closed with clear errors when permissions, transitions, or endpoints are not available.
- Wiki operations use browser automation (`scripts/openproject_wiki_cli.py`), not the OpenProject API.
- Browser automation requires separate login credentials (`OPENPROJECT_WIKI_USERNAME` / `OPENPROJECT_WIKI_PASSWORD`).
- Wiki browser automation is deterministic but may need selector adjustments if the OpenProject UI changes significantly.

## Environment Variables

- `OPENPROJECT_BASE_URL` (required): OpenProject base URL, e.g. `https://openproject.example.org`.
- `OPENPROJECT_API_TOKEN` (required for default auth): API token used with username `apikey`.
- `OPENPROJECT_DEFAULT_PROJECT` (optional): default project id/identifier used when `--project` is omitted.
- `OPENPROJECT_DECISION_LOG_DIR` (optional): directory for decision markdown files. Default: `project-knowledge/decisions`.

### Wiki browser automation variables

- `OPENPROJECT_WIKI_USERNAME` (required for wiki): OpenProject login username for browser automation.
- `OPENPROJECT_WIKI_PASSWORD` (required for wiki): OpenProject login password for browser automation.

## Supported Operations

Use `python scripts/openproject_cli.py <command> [args]`.

- `list-projects`
  - List visible projects with project ID, identifier, and name.
- `list-work-packages --project <id|identifier> [--status ...] [--assignee ...] [--limit N]`
  - List work packages with WP ID, subject, status, assignee, and updated date.
  - Applies filtering conservatively (API-side where practical, otherwise client-side).
- `create-work-package --project <id|identifier> --subject "..." [--type Task] [--description "..."]`
  - Create a work package and print created ID and subject.
  - Resolves type by name with helpful errors if type is unknown.
- `update-work-package-status --id <wp_id> --status "..."`
  - Resolve status by name (case-insensitive) and patch the work package.
  - Prints confirmation including WP ID and resulting status.
- `get-work-package --id <wp_id>`
  - Fetch full details for a single work package (status/type/priority/assignee/dates/description).
  - Displays a comment count showing how many user comments exist on the work package.
- `update-work-package --id <wp_id> [--subject ...] [--description ...] [--status ...] [--assignee ...] [--priority ...] [--type ...] [--start-date YYYY-MM-DD] [--due-date YYYY-MM-DD]`
  - Patch one or more mutable fields in a single call using transition-safe status resolution.
- `add-comment --id <wp_id> --comment "..."`
  - Best-effort comment creation using OpenProject API v3.
  - Returns a clear message when endpoint behavior differs by version/config.
- `list-comments --id <wp_id> [--all] [--author ...] [--limit N]`
  - List comments and activity history for a work package.
  - By default shows only activities with user comments, ordered oldest to newest.
  - `--all` includes field-change-only activities.
  - `--author` filters by author name (case-insensitive substring match).
  - `--limit N` shows only the N most recent entries.
- `update-comment --id <activity_id> --comment "..."`
  - Update the text of an existing comment (activity) by its activity ID.
  - The `--id` argument must be a positive integer (the activity ID, not the work package ID).
  - Returns a confirmation message on success.
- `list-statuses`
  - List available work package statuses.
- `list-types [--project <id|identifier>]`
  - List available work package types (project-scoped when provided).
- `list-priorities`
  - List available priority values.
- `list-users [--query ...] [--limit N]`
  - List visible users and optionally filter by name/login/id.
- `list-project-members --project <id|identifier> [--query ...] [--limit N]`
  - List members of a specific project with their assigned roles.
  - Uses the `/api/v3/memberships` endpoint filtered by project, which is accessible to users with project membership visibility (unlike `list-users` which requires global permissions).
  - Displays member ID, name, and comma-separated role names.
  - `--query` filters by member name (case-insensitive substring match).
  - `--limit N` caps the number of memberships fetched (default: 200).
- `list-relations --id <wp_id> [--limit N]`
  - List relations for one work package.
- `create-relation --from-id <wp_id> --to-id <wp_id> --type <relation_type> [--description ...] [--lag N]`
  - Create a work package relation (non-destructive link operation).
- `weekly-summary --project <id|identifier> [--output path.md]`
  - Build compact markdown grouped by completion/in-progress/blockers/next focus.
  - Writes output to provided path or default `project-knowledge/status/YYYY-MM-DD-weekly-status.md`.
- `log-decision --project <id|identifier> --title "..." --decision "..." [--context ...] [--impact ...] [--followup ...]`
  - Create a decision markdown entry in `project-knowledge/decisions`.
- `list-notifications [--reason ...] [--unread-only] [--limit N]`
  - List in-app notifications for the authenticated user.
  - Displays ID, reason, resource subject, project, read status, and creation date.
  - `--reason` filters by notification reason (e.g., `mentioned`, `assigned`).
  - `--unread-only` shows only unread notifications.
  - `--limit N` caps the number of displayed notifications.
- `get-notification --id <notification_id>`
  - Fetch and display full details for a single notification.
- `read-notification --id <notification_id>`
  - Mark a notification as read. Prints confirmation with notification ID.
- `unread-notification --id <notification_id>`
  - Mark a notification as unread. Prints confirmation with notification ID.
- `read-all-notifications`
  - Mark all notifications as read in one operation.

Wiki commands may exist in the CLI for legacy compatibility, but they are out of scope for this skill and should not be used in normal workflows.

## Wiki Operations (Browser Automation)

Use `python scripts/openproject_wiki_cli.py <command> [args]`.

Wiki operations use Playwright browser automation to interact with the OpenProject web UI directly, since the wiki API is not reliably available across OpenProject versions. The browser runs headless by default; pass `--visible` to any command to show the browser window for debugging.

### Setup

```bash
pip install playwright python-dotenv
playwright install chromium
```

### Commands

- `write-wiki --project <identifier> --title "..." --content "..." [--content-file path] [--visible]`
  - Create or update a wiki page through the browser UI.
  - Provide content inline with `--content` or from a file with `--content-file`.
  - Content is injected via CKEditor API for speed; supports basic markdown (headings, lists, bold, tables).
- `read-wiki --project <identifier> --title "..." [--visible]`
  - Read and print the content of a wiki page.
- `list-wiki --project <identifier> [--visible]`
  - List visible wiki page titles for a project.

## Agent Behavior

### Project status

- Prefer `list-work-packages` against the project in scope.
- Summarize by status buckets and include key WP IDs in outputs.
- Flag uncertainty explicitly when status labels are ambiguous.

### Creating tasks

- Use `create-work-package` with clear subject and optional description.
- Keep task type explicit when not defaulting to `Task`.
- Return created WP ID for traceability.

### Updating tasks

- Use `update-work-package` for multi-field updates and `update-work-package-status` for status-only changes.
- Resolve status by name and handle transition/workflow errors clearly.
- Validate date inputs as `YYYY-MM-DD` before sending updates.
- Confirm updates with WP ID and key resulting fields.

### Metadata and lookup

- Use `list-statuses`, `list-types`, `list-priorities`, and `list-users` before creating/updating when values are uncertain.
- Prefer explicit metadata lookups over guesswork when type/status/priority names vary between OpenProject instances.
- Use `list-project-members` to see who is on a project team and their roles. Prefer this over `list-users` when you only need project-scoped team visibility, as it does not require global user-list permissions.

### Comments and activity

- Use `list-comments` to review discussion history on a work package.
- Use `--author` to find comments from a specific person.
- Use `--all` when field change history is relevant (e.g., tracking status transitions).
- Use `add-comment` to contribute to work package discussions.
- Use `update-comment` to edit an existing comment when correcting mistakes or adding clarifications.

### Relations

- Use `list-relations` to inspect dependencies and ordering constraints.
- Use `create-relation` for new links (`relates`, `blocks`, `follows`, etc.) and include `--lag` only when needed.

### Weekly status summary

- Use `weekly-summary`.
- Produce compact markdown with sections:
  - Wins / completed
  - In progress
  - Blockers / risks
  - Next focus
- Save summary in `project-knowledge/status/` with date-based filename unless output path is provided.

### Wiki requests

- Use `scripts/openproject_wiki_cli.py` for wiki read/write operations via browser automation.
- Prefer `write-wiki --content-file` with a local markdown file over inline content for longer pages.
- Draft wiki content locally in `project-knowledge/wiki-drafts/` before pushing to OpenProject.
- Browser automation is slower and less deterministic than API calls — confirm success from the output.
- If browser automation fails, fall back to creating local markdown artifacts and advise manual wiki sync.

### Decision logging

- Use `log-decision` for durable decisions.
- Capture context, decision, impact, and follow-up actions.
- Store files under `project-knowledge/decisions/` with date + slug naming.

### Notifications

- Use `list-notifications` to check for events requiring attention.
- Use `--reason` to focus on specific notification types (e.g., `mentioned`, `assigned`).
- Use `--unread-only` to see only unacknowledged notifications.
- Use `get-notification` to inspect a specific notification's details.
- Use `read-notification` to acknowledge a notification after reviewing it.
- Use `unread-notification` to flag a notification for later follow-up.
- Use `read-all-notifications` to clear notification backlog in bulk.

## Output Style

- Keep outputs concise and structured.
- Always include work package IDs (e.g., `#123`) when referencing tasks.
- Prefer markdown lists and short sections over long prose.
