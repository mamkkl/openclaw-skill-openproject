# Requirements Document

## Introduction

Add notification management commands to the OpenProject CLI. This feature enables users to view, inspect, and manage their in-app notifications (IAN) from the command line using the OpenProject API v3 Notifications endpoints. Notifications inform users about changes to resources they are involved with (e.g., mentioned, assigned, watched, or commented on work packages).

## Glossary

- **CLI**: The single-file Python command-line interface (`scripts/openproject_cli.py`) that wraps OpenProject API v3.
- **Notification**: An in-app notification (IAN) object from OpenProject representing an event relevant to the authenticated user (e.g., a mention, assignment, or comment on a watched work package).
- **Notification_Reason**: The cause of a notification, such as `mentioned`, `assigned`, `responsible`, `watched`, `commented`, `created`, `scheduled`, `prioritized`, or `dateAlert`.
- **Read_Status**: A boolean property of a Notification indicating whether the user has acknowledged the notification. A Notification is either read or unread.
- **Resource**: The OpenProject object (typically a work package) that a Notification references.
- **Formatter**: A function in the CLI that converts raw API response data into human-readable tabular or detail output for the terminal.
- **Client_Method**: A method on the `OpenProjectClient` class that performs an HTTP request against the OpenProject API v3.
- **Parser**: The argparse-based command parser in `build_parser()` that registers subcommands and their arguments.

## Requirements

### Requirement 1: List Notifications

**User Story:** As a CLI user, I want to list my notifications, so that I can see what events require my attention without opening the OpenProject web UI.

#### Acceptance Criteria

1. WHEN the `list-notifications` command is invoked, THE CLI SHALL retrieve notifications for the authenticated user from the OpenProject API v3 `/api/v3/notifications` endpoint.
2. WHEN notifications are retrieved, THE Formatter SHALL display each Notification with its ID, reason, associated resource subject, project name, read status, and creation timestamp.
3. WHERE the `--reason` filter is provided, THE CLI SHALL display only Notification objects whose Notification_Reason matches the specified value (case-insensitive).
4. WHERE the `--unread-only` flag is provided, THE CLI SHALL display only Notification objects whose Read_Status is unread.
5. WHERE the `--limit N` argument is provided, THE CLI SHALL display at most N Notification objects.
6. WHEN no notifications match the applied filters, THE CLI SHALL print a message indicating zero notifications were found.
7. IF the API request fails due to authentication or permission errors, THEN THE CLI SHALL print a descriptive error message and exit with a non-zero status code.

### Requirement 2: Get Notification Detail

**User Story:** As a CLI user, I want to view the full details of a single notification, so that I can understand the context of the event without navigating to the web UI.

#### Acceptance Criteria

1. WHEN the `get-notification --id <notification_id>` command is invoked, THE CLI SHALL retrieve the Notification object from the OpenProject API v3 `/api/v3/notifications/{id}` endpoint.
2. WHEN a Notification is retrieved, THE Formatter SHALL display the Notification ID, reason, read status, creation timestamp, associated resource type, resource subject, resource ID, and project name.
3. IF the specified notification ID does not exist or is not accessible, THEN THE CLI SHALL print a descriptive error message and exit with a non-zero status code.

### Requirement 3: Mark Notification as Read

**User Story:** As a CLI user, I want to mark a specific notification as read, so that I can acknowledge events and reduce noise in my notification list.

#### Acceptance Criteria

1. WHEN the `read-notification --id <notification_id>` command is invoked, THE CLI SHALL send a POST request to the OpenProject API v3 `/api/v3/notifications/{id}/read_ian` endpoint.
2. WHEN the API confirms the operation, THE CLI SHALL print a confirmation message including the Notification ID and the resulting Read_Status.
3. IF the specified notification ID does not exist or is not accessible, THEN THE CLI SHALL print a descriptive error message and exit with a non-zero status code.

### Requirement 4: Mark Notification as Unread

**User Story:** As a CLI user, I want to mark a specific notification as unread, so that I can flag events for later follow-up.

#### Acceptance Criteria

1. WHEN the `unread-notification --id <notification_id>` command is invoked, THE CLI SHALL send a POST request to the OpenProject API v3 `/api/v3/notifications/{id}/unread_ian` endpoint.
2. WHEN the API confirms the operation, THE CLI SHALL print a confirmation message including the Notification ID and the resulting Read_Status.
3. IF the specified notification ID does not exist or is not accessible, THEN THE CLI SHALL print a descriptive error message and exit with a non-zero status code.

### Requirement 5: Mark All Notifications as Read

**User Story:** As a CLI user, I want to mark all my notifications as read in one command, so that I can quickly clear my notification backlog.

#### Acceptance Criteria

1. WHEN the `read-all-notifications` command is invoked, THE CLI SHALL send a POST request to the OpenProject API v3 `/api/v3/notifications/read_ian` endpoint.
2. WHEN the API confirms the operation, THE CLI SHALL print a confirmation message indicating all notifications have been marked as read.
3. IF the API request fails due to authentication or permission errors, THEN THE CLI SHALL print a descriptive error message and exit with a non-zero status code.

### Requirement 6: Filter and Format Notifications

**User Story:** As a CLI user, I want consistent filtering and formatting of notification output, so that I can efficiently scan and process notification data.

#### Acceptance Criteria

1. THE Formatter SHALL sort notifications by creation timestamp in descending order (newest first).
2. THE Formatter SHALL truncate long resource subjects to a maximum display width consistent with existing CLI formatters.
3. THE Formatter SHALL use the `--debug-json` global flag to optionally print raw JSON API responses before formatted output, consistent with existing CLI commands.
4. THE CLI SHALL register all notification subcommands in the Parser following the same pattern used by existing commands.
5. THE Client_Method for listing notifications SHALL use the existing `_collect_collection` pagination helper to handle paginated API responses.
