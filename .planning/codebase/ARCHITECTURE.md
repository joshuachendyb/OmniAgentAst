# ARCHITECTURE.md - System Architecture

## Architecture Pattern

**Frontend**: React SPA with Ant Design
**Backend**: FastAPI with layered architecture

## Frontend Architecture

```
frontend/src/
├── main.tsx              # Entry point
├── App.tsx              # Root component + routing
├── components/          # UI components
│   ├── Layout/         # Layout components
│   ├── Chat/           # Chat components
│   └── Security/       # Security components
├── pages/              # Page components
├── services/           # API services
├── contexts/           # React contexts
└── utils/              # Utilities
```

### Frontend State Management

- **React Context**: `SecurityProvider`
- **Local State**: `useState`, `useEffect`

## Backend Architecture

```
backend/app/
├── api/v1/              # API layer (routes)
│   ├── sessions.py       # Session management
│   ├── execution.py    # Chat execution
│   ├── config.py       # Configuration
│   └── metrics.py      # Monitoring
├── services/           # Business logic layer
│   ├── agent/         # Agent execution
│   ├── tools/         # Tool implementations
│   ├── safety/        # Security checks
│   ├── preprocessing/ # Input preprocessing
│   └── intents/       # Intent handling
├── chat_stream/        # SSE streaming
├── utils/             # Utilities
└── models/            # Data models
```

### Backend Layers

1. **API Layer** (`api/v1/`) - HTTP endpoints
2. **Service Layer** (`services/`) - Business logic
3. **Tool Layer** (`tools/`) - File operations, etc.
4. **Safety Layer** (`safety/`) - Security checks
5. **Data Layer** (`models/`) - ORM models

### Data Flow

```
User Input → API → Preprocessing → Intent Classification → Agent Execution → Tool Execution → Safety Check → Response → SSE → Frontend
```

## Key Design Patterns

### Frontend

- **Component Pattern**: Functional components with hooks
- **Context Pattern**: Provider for global state
- **SSE Pattern**: Server-Sent Events for streaming

### Backend

- **Adapter Pattern**: `agent/adapter.py` for AI provider abstraction
- **Strategy Pattern**: `llm_strategies.py` for different LLM strategies
- **Pipeline Pattern**: `preprocessing/pipeline.py` for input processing
- **Event Handler Pattern**: Error handling in chat_stream

---

**Created**: 2026-04-12
**Focus**: arch