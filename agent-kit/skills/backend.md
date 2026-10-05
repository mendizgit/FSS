# Skill — Backend & API Development

## Role

Act as a senior backend engineer working within the approved system architecture.

## Rules

- Follow the defined API architecture.
- Do not invent endpoints when a specification exists.
- Validate all external input.
- Enforce authorization server-side.
- Keep business logic out of route handlers where practical.
- Keep database access organized.
- Return consistent errors.
- Use appropriate HTTP status codes.
- Protect secrets.

## API implementation

For each endpoint consider:

- authentication
- authorization
- validation
- request structure
- response structure
- error handling
- pagination/filtering where applicable
- database behavior

## Data integrity

Handle:

- missing records
- duplicates
- invalid input
- relationships
- transaction requirements

Avoid unnecessary database calls.

## Security

Never trust client-provided permissions.

Do not expose:

- passwords
- secrets
- internal stack traces
- private database information

## Error handling

Use predictable API errors that the frontend can display appropriately.

## TSS specifics

- The API is **read-only** in v1. Do not add mutating endpoints without user approval.
- Authentication is handled by Caddy basic auth. The API itself has no user model. Bind the API to the internal Docker network or 127.0.0.1 only.
- Routes delegate to `db/repositories/`. No SQL in routes, agents or domain.
- Use async SQLAlchemy sessions, one per request or agent run. Bulk inserts (`insert().values([...])` or `COPY`) for snapshots.
- Every migration is generated with Alembic and reviewed. Never edit an applied migration.
- Use Pydantic response models for every endpoint. Exclude internal fields.
- Error handlers map `TSSError` to `{error:{code,message,component}}` with an appropriate status (502 for upstream data source, 503 for halted/unavailable, 422 for validation).
- Timestamps go out as UTC ISO-8601.

## Scope

Do not redesign backend architecture during feature implementation unless the defined architecture prevents safe implementation.
