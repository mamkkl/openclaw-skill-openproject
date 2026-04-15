# Requirements Document

## Introduction

Add parent-child relationship support for work packages in the OpenProject CLI. This feature enables users to establish, view, modify, and query hierarchical relationships between work packages using the OpenProject API v3 `_links.parent` mechanism. Parent-child relationships are distinct from relations (which model lateral dependencies like "blocks" or "follows") and represent containment hierarchy (e.g., an Epic containing Tasks, or a Feature containing sub-tasks).

## Glossary

- **CLI**: The single-file Python command-line interface at `scripts/openproject_cli.py`.
- **Work_Package**: An OpenProject work item with an ID, subject, status, type, and other metadata.
- **Parent_Link**: The `_links.parent` HAL link on a work package payload. When set, its `href` points to the parent work package. When `null`, the work package has no parent.
- **Child**: A work package whose `_links.parent.href` points to another work package.
- **Hierarchy**: The tree structure formed by parent-child relationships between work packages.
- **OpenProject_API**: The OpenProject API v3 using HAL+JSON hypermedia format.
- **Lock_Version**: An optimistic concurrency field on work packages required for PATCH operations.

## Requirements

### Requirement 1: Set Parent on Creation

**User Story:** As a CLI user, I want to specify a parent work package when creating a new work package, so that the new work package is immediately placed in the correct hierarchy.

#### Acceptance Criteria

1. WHEN the `--parent` flag is provided with a valid work package ID to the `create-work-package` command, THE CLI SHALL include `_links.parent.href` pointing to the specified work package in the creation payload.
2. WHEN the `--parent` flag is omitted from the `create-work-package` command, THE CLI SHALL create the work package without a parent link (preserving current behavior).
3. IF the `--parent` flag value is not a positive integer, THEN THE CLI SHALL exit with a non-zero exit code and a descriptive error message.
4. WHEN a work package is successfully created with a parent, THE CLI SHALL display the parent work package ID in the creation confirmation output.

### Requirement 2: Set or Change Parent on Update

**User Story:** As a CLI user, I want to set or change the parent of an existing work package, so that I can reorganize work package hierarchy as plans evolve.

#### Acceptance Criteria

1. WHEN the `--parent` flag is provided with a valid work package ID to the `update-work-package` command, THE CLI SHALL include `_links.parent.href` pointing to the specified work package in the PATCH payload.
2. WHEN the `--parent` flag is provided alongside other update flags (e.g., `--status`, `--subject`), THE CLI SHALL include the parent link change together with the other field updates in a single PATCH call.
3. IF the `--parent` flag value is not a positive integer and is not the literal string `none`, THEN THE CLI SHALL exit with a non-zero exit code and a descriptive error message.

### Requirement 3: Remove Parent from Work Package

**User Story:** As a CLI user, I want to remove the parent from a work package, so that I can detach a work package from its current hierarchy.

#### Acceptance Criteria

1. WHEN the `--parent` flag is provided with the literal value `none` (case-insensitive) to the `update-work-package` command, THE CLI SHALL set `_links.parent.href` to `null` in the PATCH payload.
2. WHEN the parent is successfully removed, THE CLI SHALL display confirmation that the work package no longer has a parent.

### Requirement 4: Display Parent in Work Package Detail

**User Story:** As a CLI user, I want to see the parent work package when viewing work package details, so that I can understand where a work package sits in the hierarchy.

#### Acceptance Criteria

1. WHEN a work package has a parent and the `get-work-package` command is used, THE CLI SHALL display the parent work package ID and subject in the detail output.
2. WHEN a work package has no parent and the `get-work-package` command is used, THE CLI SHALL omit the parent line from the detail output.

### Requirement 5: Display Parent in Work Package List

**User Story:** As a CLI user, I want to see parent information in the work package list view, so that I can quickly identify hierarchy when scanning multiple work packages.

#### Acceptance Criteria

1. WHEN listing work packages that have a parent, THE CLI SHALL include the parent work package ID in each list row.
2. WHEN listing work packages that have no parent, THE CLI SHALL display a dash (`-`) in the parent column for those rows.

### Requirement 6: List Children of a Work Package

**User Story:** As a CLI user, I want to list the direct children of a specific work package, so that I can see what sub-items exist under a parent.

#### Acceptance Criteria

1. WHEN the `list-children` command is invoked with a valid `--id` argument, THE CLI SHALL query the OpenProject_API for work packages whose parent is the specified work package ID.
2. THE CLI SHALL display each child work package with its ID, subject, status, and assignee.
3. WHEN the specified work package has no children, THE CLI SHALL display a message indicating no children were found.
4. WHERE the `--limit` option is provided, THE CLI SHALL cap the number of returned children to the specified limit.

### Requirement 7: API Error Handling for Parent Operations

**User Story:** As a CLI user, I want clear error messages when parent-child operations fail, so that I can understand and resolve issues.

#### Acceptance Criteria

1. IF the OpenProject_API returns a 404 when the specified parent work package does not exist, THEN THE CLI SHALL display an error message stating the parent work package was not found.
2. IF the OpenProject_API returns a 422 when a parent assignment creates a circular hierarchy, THEN THE CLI SHALL display an error message describing the rejection reason from the API response.
3. IF the OpenProject_API returns a 422 for any other parent-related validation failure, THEN THE CLI SHALL display the error detail from the API response body.

### Requirement 8: Build Parent Href from Work Package ID

**User Story:** As a developer, I want a helper that constructs the correct HAL href for a parent work package ID, so that parent link payloads are built consistently.

#### Acceptance Criteria

1. THE CLI SHALL construct parent hrefs using the format `/api/v3/work_packages/{id}` for a given positive integer work package ID.
2. WHEN the parent value is `none` (case-insensitive), THE CLI SHALL produce a `null` href value.
3. FOR ALL positive integer IDs, building a parent href and extracting the numeric ID from that href SHALL return the original ID (round-trip property).
