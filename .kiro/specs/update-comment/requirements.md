# Requirements Document

## Introduction

Add an `update-comment` command to the OpenProject CLI that allows editing the text of an existing comment (activity) by its activity ID. The OpenProject API v3 exposes `PATCH /api/v3/activities/{id}` for updating an activity's comment text. This feature complements the existing `add-comment` and `list-comments` commands, giving users a complete comment lifecycle without requiring the OpenProject web UI.

## Glossary

- **CLI**: The single-file Python command-line interface at `scripts/openproject_cli.py`.
- **Activity**: An OpenProject journal entry associated with a work package. Activities may contain user comments, field changes, or both. Each activity has a unique numeric ID.
- **Comment**: The user-authored text portion of an Activity, represented as a formattable object with a `raw` field in the OpenProject API v3.
- **OpenProjectClient**: The Python class in the CLI that wraps OpenProject API v3 HTTP calls.
- **Parser**: The argparse-based argument parser constructed by `build_parser()` in the CLI.

## Requirements

### Requirement 1: Update Activity Comment via API

**User Story:** As a project manager, I want to update the text of an existing comment on a work package, so that I can correct mistakes or add clarifications without creating duplicate comments.

#### Acceptance Criteria

1. WHEN an activity ID and new comment text are provided, THE OpenProjectClient SHALL send a PATCH request to `/api/v3/activities/{id}` with the new comment text in `{"comment": {"raw": "<text>"}}` format.
2. WHEN the API returns a successful response (HTTP 200), THE OpenProjectClient SHALL return the updated Activity object.
3. IF the API returns HTTP 403 (forbidden), THEN THE OpenProjectClient SHALL raise an OpenProjectError indicating the user lacks permission to edit the comment.
4. IF the API returns HTTP 404 (not found), THEN THE OpenProjectClient SHALL raise an OpenProjectError indicating the activity ID does not exist.
5. IF the API returns any other error status, THEN THE OpenProjectClient SHALL raise an OpenProjectError containing the HTTP status code and error detail from the response.

### Requirement 2: CLI Subcommand for Updating Comments

**User Story:** As a CLI user, I want an `update-comment` subcommand, so that I can edit comment text directly from the terminal.

#### Acceptance Criteria

1. THE Parser SHALL register an `update-comment` subcommand accepting a required `--id` argument (integer, the activity ID) and a required `--comment` argument (string, the new comment text).
2. WHEN the `update-comment` subcommand is invoked with valid arguments, THE CLI SHALL call the OpenProjectClient update method and print a confirmation message including the activity ID.
3. WHEN the `--debug-json` flag is active, THE CLI SHALL print the raw JSON response from the API after the confirmation message.
4. IF the OpenProjectClient raises an OpenProjectError, THEN THE CLI SHALL print the error message to stderr and exit with a non-zero exit code.

### Requirement 3: Input Validation

**User Story:** As a CLI user, I want clear feedback when I provide invalid input, so that I can correct my command without guessing.

#### Acceptance Criteria

1. IF the `--id` argument is not a valid positive integer, THEN THE Parser SHALL reject the input with an argparse error message before making any API call.
2. IF the `--comment` argument is an empty string, THEN THE CLI SHALL raise an OpenProjectError with a message indicating that comment text must not be empty.

### Requirement 4: SKILL.md Documentation Update

**User Story:** As an agent consumer of the skill definition, I want the `update-comment` command documented in SKILL.md, so that the agent knows when and how to use it.

#### Acceptance Criteria

1. WHEN the feature is implemented, THE SKILL.md SHALL list `update-comment --id <activity_id> --comment "..."` under Supported Operations with a description of its purpose.
2. THE SKILL.md Agent Behavior section under "Comments and activity" SHALL include guidance on using `update-comment` to edit existing comments.
