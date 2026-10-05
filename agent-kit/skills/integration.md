# Skill — Full-Stack Integration

## Role

Connect frontend, backend, APIs, authentication, and data into one coherent feature.

## Integration flow

```text
UI
→ Client State
→ API Client
→ API
→ Business Logic
→ Data Access
→ Database
→ Response
→ UI State
```

## Rules

- Keep request/response types aligned.
- Avoid duplicating API contracts unnecessarily.
- Handle loading and errors.
- Handle authentication expiration.
- Handle authorization failures.
- Map backend errors to useful UI messages.
- Keep data transformations explicit.
- Do not hide API failures.

## Data mismatch

If frontend requirements do not map to backend/API data:

1. Identify the exact mismatch.
2. Check whether another existing source provides the required data.
3. If not, ask the user before inventing a solution.

## Feature completeness

A feature is not complete if the UI exists but the required data flow is missing.

## State

Represent meaningful states explicitly:

- idle
- loading
- success
- empty
- error

Use the project's established state-management approach.

## TSS specifics

- Event flow:
  1. agent writes to the DB
  2. `NOTIFY tss_events`
  3. the api `LISTEN` loop receives it
  4. the api broadcasts on `/ws`
  5. the UI invalidates the matching TanStack Query key
- The UI never polls faster than a 60 s fallback interval. WS events are the primary trigger.
- Event → query invalidation map:
  - `cycle_complete` → discovery, classification
  - `movers_updated` → movers
  - `agent_status` → status
  - `news_new` → news
  - `signal_new` → signals
  - `system_state` → status
- `ticker` events update a client-side price store only. They never trigger refetches.
- On WS reconnect, refetch all panel queries once to resynchronise.
- Show stale data with a stale badge instead of hiding it when a refetch fails.
- The backend sends UTC ISO-8601 timestamps. Only `lib/time.ts` converts them to IST.
- Backend error `{error:{code,message,component}}` maps to the panel error state, which shows the component name.
