# INTEGRATIONS.md - External Integrations

## AI Providers

| Provider | Configuration | Models |
|----------|---------------|--------|
| OpenCode | `config.yaml` | minimax-m2.5-free, kimi-k2.5-free |
| 智谱AI (ZhipuAI) | `config.yaml` | glm-4-flash, glm-4-plus |

## Database

| Type | Engine | Location |
|------|--------|----------|
| SQLite | aiosqlite | `C:\Users\40968\.omniagent\chat_history.db` |
| SQLite | aiosqlite | `C:\Users\40968\.omniagent\operations.db` |

## Frontend-Backend Communication

- **Protocol**: HTTP + SSE (Server-Sent Events)
- **Frontend Port**: 5173
- **Backend Port**: 8000
- **API Docs**: `http://localhost:8000/docs`

### Key API Endpoints

```
POST /api/v1/chat/completion    # Chat with AI
GET  /api/v1/chat/execution/{session_id}/stream  # SSE streaming
POST /api/v1/sessions         # Create session
GET  /api/v1/sessions        # List sessions
GET  /api/v1/sessions/{session_id}/messages  # Get messages
PATCH /api/v1/sessions/{session_id}/title  # Update title
GET  /api/v1/config          # Get config
POST /api/v1/config         # Update config
GET  /api/v1/metrics         # System metrics
```

## External Dependencies

### Backend Python Packages

| Package | Purpose |
|---------|---------|
| pycorrector | Text correction |
| gliclass | Classification |

---

**Created**: 2026-04-12
**Focus**: tech