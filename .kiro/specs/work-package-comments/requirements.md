# Requirements Document

## Introduction

The OpenProject CLI (`openproject_cli.py`) currently supports writing comments to work packages via the `add-comment` command, but provides no way to read or list existing comments/activities. The `get-work-package` command fetches work package details without displaying associated comments. This feature adds the ability to read and display work package comments and activity history through the CLI, both as a standalone `list-comments` command and as an optional addition to `get-work-package` output.

## Glossary

- **CLI**: The single-file Python command-line interface at `scripts/openproject_cli.py`
- **Activity**: An OpenProject journal entry on a work package, which may contain a user comment and/or a record of field changes. Exposed at `/api/v3/work_packages/{id}/activities`
- **Comment**: The user-authored text portion of an Activity. An Activity with a non-empty `comment` field is considered a comment
- **Activities_Endpoint**: The OpenProject API v3 endpoint at `/api/v3/work_packages/{id}/activities` that returns a HAL collection of Activity resources
- **OpenProjectClient**: The Python class in the CLI that encapsulates all HTTP interactions with the OpenProject API v3
- **Formatter**: A helper function that transforms raw Activity data into human-readable CLI output

## Requirements

### Requirement 1: Fetch Activities from API

**User Story:** As a CLI user, I want the OpenProjectClient to retrieve activities for a work package, so that comment and activity data is available for display.

#### Acceptance Criteria

1. WHEN a valid work package ID is provided, THE OpenProjectClient SHALL return a list of Activity objects from the Activities_Endpoint
2. WHEN the Activities_Endpoint returns a paginated collection, THE OpenProjectClient SHALL collect all pages up to a configurable limit
3. IF the Activities_Endpoint returns an HTTP error status, THEN THE OpenProjectClient SHALL raise an OpenProjectError with the status code and error message
4. IF the work package ID does not exist, THEN THE OpenProjectClient SHALL raise an OpenProjectError indicating the work package was not found

### Requirement 2: Standalone list-comments Command

**User Story:** As a CLI user, I want a `list-comments` command that displays comments on a work package, so that I can review discussion history without leaving the terminal.

#### Acceptance Criteria

1. WHEN the `list-comments` command is invoked with a work package ID, THE CLI SHALL display all activities that contain a non-empty comment, ordered from oldest to newest
2. THE Formatter SHALL display each comment with the author name, timestamp, and comment text
3. WHEN the `--all` flag is provided, THE CLI SHALL display all activities including those without user comments (field change records)
4. WHEN no activities with comments exist for the work package, THE CLI SHALL print a message indicating no comments were found
5. WHEN the `--debug-json` flag is provided, THE CLI SHALL print the raw JSON response in addition to the formatted output

### Requirement 3: Comment Count in get-work-package Output

**User Story:** As a CLI user, I want `get-work-package` to show a comment count, so that I can see at a glance whether a work package has discussion activity.

#### Acceptance Criteria

1. WHEN the `get-work-package` command is invoked, THE CLI SHALL display the total number of comments alongside the existing work package detail fields
2. WHEN the work package has zero comments, THE CLI SHALL display "Comments: 0"

### Requirement 4: Format Activity Output for Terminal

**User Story:** As a CLI user, I want activities displayed in a readable format, so that I can quickly scan comment history.

#### Acceptance Criteria

1. THE Formatter SHALL display each comment as a block containing: author name, date, and comment text
2. THE Formatter SHALL extract comment text from the Activity `comment` field using the same formattable-text extraction pattern used for work package descriptions
3. WHEN an Activity contains only field changes and no comment text, THE Formatter SHALL display a summary line indicating which fields changed (when `--all` flag is active)
4. THE Formatter SHALL separate individual activity entries with a visual delimiter for readability

### Requirement 5: Filter Comments by Author

**User Story:** As a CLI user, I want to filter comments by author, so that I can find comments from a specific person.

#### Acceptance Criteria

1. WHEN the `--author` option is provided to `list-comments`, THE CLI SHALL display only activities whose author name or login matches the provided value (case-insensitive substring match)
2. WHEN the `--author` filter matches no activities, THE CLI SHALL print a message indicating no matching comments were found

### Requirement 6: Limit Number of Displayed Comments

**User Story:** As a CLI user, I want to limit how many comments are displayed, so that I can manage output for work packages with long histories.

#### Acceptance Criteria

1. WHEN the `--limit` option is provided to `list-comments`, THE CLI SHALL display at most the specified number of most recent comments
2. WHEN `--limit` is not provided, THE CLI SHALL default to displaying all comments up to the API collection limit
