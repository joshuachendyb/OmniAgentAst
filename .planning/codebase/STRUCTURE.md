# STRUCTURE.md - Directory Structure

## Project Root

```
OmniAgentAs-desk/
├── backend/              # Python FastAPI backend
├── frontend/           # React TypeScript frontend
├── config/             # Configuration files
├── doc-4月优化/        # Recent optimization docs
├── logs/               # Runtime logs
└── workspace/         # File operation workspace
```

## Frontend Structure

```
frontend/
├── src/
│   ├── main.tsx              # Entry point
│   ├── App.tsx              # Root component
│   ├── index.css            # Global styles
│   ├── components/
│   │   ├── Layout/        # Layout (Header, Sider, Content)
│   │   ├── Chat/
│   │   │   ├── NewChatContainer.tsx
│   │   │   ├── MessageItem.tsx
│   │   │   ├── ExecutionPanel.tsx
│   │   │   ├── ChatInput.tsx
│   │   │   ├── views/      # File operation views
│   │   │   └── ErrorDetail.tsx
│   │   ├── ShortcutPanel/
│   │   └── SecurityNotification/
│   ├── pages/             # Page components
│   ├── services/          # API services
│   ├── contexts/         # React contexts
│   ├── utils/           # Utilities
│   └── types/           # TypeScript types
├── public/              # Static assets
├── tests/               # Test files
│   ├── unit/           # Unit tests
│   └── e2e/          # E2E tests
├── package.json
├── vite.config.ts
├── tsconfig.json
└── playwright.config.ts
```

## Backend Structure

```
backend/
├── app/
│   ├── main.py              # Entry point
│   ├── config.py           # Configuration
│   ├── api/
│   │   └── v1/           # API routes
│   │       ├── sessions.py
│   │       ├── execution.py
│   │       ├── config.py
│   │       ├── metrics.py
│   │       └── security.py
│   ├── services/
│   │   ├── agent/         # Agent execution
│   │   │   ├── adapter.py
│   │   │   ├── session.py
│   │   │   ├── file_react.py
│   │   │   └── llm_strategies.py
│   │   ├── tools/         # Tool implementations
│   │   │   ├── file/
│   │   │   ├── desktop/
│   │   │   ├── network/
│   │   │   └── database/
│   │   ├── safety/       # Security checks
│   │   │   ├── file/
│   │   │   └── network/
│   │   ├── preprocessing/  # Input preprocessing
│   │   │   ├── pipeline.py
│   │   │   ├── intent_classifier.py
│   │   │   └── corrector.py
│   │   └── chat_router.py
│   ├── chat_stream/      # SSE streaming
│   │   ├── chat_stream_query.py
│   │   ├── sse_formatter.py
│   │   └── message_saver.py
│   ├── utils/
│   │   ├── logger.py
│   │   └── monitoring.py
│   └── models/
├── tests/
├── requirements.txt
└── app.db
```

## Key File Locations

| Component | Path |
|----------|------|
| Frontend entry | `frontend/src/main.tsx` |
| Backend entry | `backend/app/main.py` |
| Layout | `frontend/src/components/Layout/index.tsx` |
| Chat container | `frontend/src/components/Chat/NewChatContainer.tsx` |
| Message item | `frontend/src/components/Chat/MessageItem.tsx` |
| Agent adapter | `backend/app/services/agent/adapter.py` |
| Tool executor | `backend/app/services/agent/tool_executor.py` |

---

**Created**: 2026-04-12
**Focus**: arch