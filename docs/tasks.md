# Tasks

- 2026-01-07 Voice room flow updates
  - Require join API before entering the room; token comes from GET /api/voice-room/token and must be passed to join.
  - ZIM also requires a token; private chat uses it.
  - Backend owns room broadcast; frontend only calls the announcement update API.
  - Update API docs after backend changes.
