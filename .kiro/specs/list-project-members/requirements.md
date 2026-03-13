# Requirements Document

## Introduction

Add a `list-project-members` command to the OpenProject CLI that lists members of a specific project along with their assigned roles. The existing `list-users` command retrieves all users globally and requires elevated permissions (often returning 403). This feature provides a project-scoped alternative using the OpenProject API v3 `/api/v3/memberships` endpoint, which returns membership objects filtered by project. Each membership links a principal (user or group) to one or more roles within a project, enabling project-level team visibility without global user-list permissions.

## Glossary

- **CLI**: The single-file Python command-line interface (`scripts/openproject_cli.py`) that wraps OpenProject API v3.
- **Membership**: An OpenProject API v3 resource representing the association of a Principal with a Project and one or more Roles. Retrieved from the `/api/v3/memberships` endpoint.
- **Principal**: The user or group associated with a Membership. Accessible via the `_links.principal` HAL link on a Membership object.
- **Role**: A named permission set assigned to a Principal within a Project. A Membership contains one or more Roles accessible via `_embedded.roles` or `_links.roles` on the Membership object.
- **Project**: An OpenProject project, identified by numeric ID or string identifier. Used to scope the memberships query.
- **Formatter**: A function in the CLI that converts raw API response data into human-readable tabular output for the terminal.
- **Client_Method**: A method on the `OpenProjectClient` class that performs an HTTP request against the OpenProject API v3.
- **Parser**: The argparse-based command parser in `build_parser()` that registers subcommands and their arguments.
- **HAL_Link**: A hypermedia link in the OpenProject API v3 response following the HAL specification, containing `href` and optionally `title` fields.

## Requirements

### Requirement 1: Retrieve Project Memberships

**User Story:** As a CLI user, I want to list the members of a specific project, so that I can see who is on the team and what roles each person has without needing global user-list permissions.

#### Acceptance Criteria

1. WHEN the `list-project-members --project <project_ref>` command is invoked, THE Client_Method SHALL retrieve Membership objects from the OpenProject API v3 `/api/v3/memberships` endpoint filtered by the specified Project.
2. WHEN the `--project` argument is omitted, THE CLI SHALL fall back to the `OPENPROJECT_DEFAULT_PROJECT` environment variable using the existing `require_project` helper.
3. WHEN Membership objects are retrieved, THE Client_Method SHALL use the existing `_collect_collection` pagination helper to handle paginated API responses.
4. WHEN the Project reference is a name or identifier, THE CLI SHALL resolve the Project to its numeric ID using the existing `resolve_project` method before querying memberships.
5. THE Client_Method SHALL pass the project filter to the API using the standard OpenProject filter syntax: `[{"project":{"operator":"=","values":["<project_id>"]}}]`.

### Requirement 2: Display Project Members

**User Story:** As a CLI user, I want to see project members displayed in a clear tabular format, so that I can quickly scan team composition and role assignments.

#### Acceptance Criteria

1. WHEN Membership objects are retrieved, THE Formatter SHALL display each Membership as a row containing the member name, member ID, and comma-separated list of Role names.
2. WHEN a Principal has multiple Roles in the Project, THE Formatter SHALL display all Role names in a single comma-separated field.
3. THE Formatter SHALL extract the member name from the `_links.principal.title` HAL_Link on each Membership object.
4. THE Formatter SHALL extract Role names from the `_links.roles` array of HAL_Link objects on each Membership object.
5. WHEN no Membership objects are returned for the specified Project, THE Formatter SHALL print a message indicating zero members were found.
6. THE Formatter SHALL truncate long member names and role lists to a maximum display width consistent with existing CLI formatters.

### Requirement 3: Filter Members by Name

**User Story:** As a CLI user, I want to filter the member list by name, so that I can quickly find a specific person in a large project team.

#### Acceptance Criteria

1. WHERE the `--query <text>` argument is provided, THE CLI SHALL display only Membership objects whose Principal name contains the specified text (case-insensitive substring match).
2. WHEN the `--query` filter is applied and no Membership objects match, THE Formatter SHALL print a message indicating zero members matched the filter.

### Requirement 4: Limit Results

**User Story:** As a CLI user, I want to limit the number of members returned, so that I can control output volume for large projects.

#### Acceptance Criteria

1. WHERE the `--limit N` argument is provided, THE Client_Method SHALL retrieve at most N Membership objects from the API.
2. WHEN the `--limit` argument is omitted, THE Client_Method SHALL use a default limit of 200.

### Requirement 5: Error Handling

**User Story:** As a CLI user, I want clear error messages when something goes wrong, so that I can diagnose and resolve issues without guessing.

#### Acceptance Criteria

1. IF the API request fails due to authentication or permission errors (HTTP 403), THEN THE CLI SHALL print a descriptive error message and exit with a non-zero status code.
2. IF the specified Project cannot be resolved, THEN THE CLI SHALL print a descriptive error message indicating the project was not found and exit with a non-zero status code.
3. IF the `/api/v3/memberships` endpoint returns an unexpected error, THEN THE CLI SHALL print the error details extracted from the API response and exit with a non-zero status code.

### Requirement 6: CLI Integration and Debug Output

**User Story:** As a CLI user, I want the new command to follow the same conventions as existing commands, so that the interface remains consistent and predictable.

#### Acceptance Criteria

1. THE CLI SHALL register the `list-project-members` subcommand in the Parser following the same pattern used by existing commands.
2. THE CLI SHALL support the `--debug-json` global flag to optionally print raw JSON API responses alongside formatted output, consistent with existing CLI commands.
3. THE CLI SHALL display the resolved project identifier or name as a header line before the member table, consistent with the `list-work-packages` command output pattern.
4. THE Client_Method SHALL be implemented as a method on the `OpenProjectClient` class, consistent with existing client methods.
