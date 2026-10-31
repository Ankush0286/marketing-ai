# Marketing AI Agent

An offline-first, autonomous marketing AI agent and social CRM built for high-leverage growth operations. The system combines local LLM/cloud agent orchestration, encrypted credential management, stealth browser automation, and embedded SQLite/libSQL persistence into a single self-hosted application or standalone desktop executable.

---

## Core Capabilities

* **Multi-Account Credential Vault (`accounts`):** Connect Twitter/X, Instagram, and other social profiles using API keys, Playwright browser sessions, or a hybrid approach. All sensitive tokens are encrypted at rest via AES-128 Fernet cryptography.
* **Autonomous Content & Campaign Pipeline (`campaigns`):** Draft, queue, and schedule multi-channel posts with automated media handling and publishing lifecycles.
* **Competitor & Keyword Monitoring (`triggers`):** Watch target handles and keyword streams to surface high-intent conversations and trigger contextual auto-replies.
* **Influencer & Lead Outreach CRM (`outreach`):** Discover leads, track relationship stages, and stage cold DMs with human-in-the-loop approval gates.
* **Interactive AI Copilot (`copilot` & `agent`):** Streaming ReAct tool-calling agent capable of querying account health, drafting campaigns, and queuing outreach directly from natural language.
* **Anti-Ban Safety & Throttling (`automation` & `platforms`):** Token-bucket rate limiting, automated daily quota resets, cooldown enforcement, and human-like browser jitter via Playwright.
* **Offline-First Persistence (`db`):** Powered by SQLAlchemy 2.0 and Turso (`libSQL`) embedded local replicas for zero-latency local reads/writes with optional cloud sync.

---

## Tech Stack

| Layer | Technology |
| :--- | :--- |
| **Backend Framework** | FastAPI, Uvicorn, Pydantic v2 |
| **Database & ORM** | Turso (`libSQL`) Embedded Replica, SQLAlchemy 2.0, Alembic (Batch Mode) |
| **Security** | `cryptography` (AES-128 Fernet symmetric encryption) |
| **Browser Automation** | Playwright (Stealth context management, persistent cookie states) |
| **Background Jobs** | APScheduler, custom token-bucket throttlers |
| **Frontend UI** | Vite, React, TypeScript |
| **Package & Env Manager** | `uv` (Python 3.12+), `npm` |
| **Testing** | `pytest`, FastAPI `TestClient`, in-memory `StaticPool` SQLite fixtures |
| **Desktop Packaging** | PyInstaller, Inno Setup |

---

## Architectural Principles

1. **Vertical Domain Slices:** Business domains (`accounts`, `campaigns`, `triggers`, `outreach`, `copilot`, `history`) are self-contained inside `src/app/modules/`.
2. **Strict Boundary Separation (Command Pattern):**
   * **`schemas.py` (Pydantic):** Lives strictly at the HTTP router boundary to validate incoming JSON and sanitize outgoing responses (stripping encrypted fields).
   * **`commands.py` (Dataclasses):** Immutable plain-Python data structures passed into `service.py`. Allows FastAPI endpoints, background workers, CLI scripts, and AI Copilot tools to invoke business logic without HTTP coupling.
3. **Centralized Exception Translation:** Services raise pure domain exceptions (`AccountNotFoundError`, `DailyPostQuotaExceededError`) inherited from `src/app/common/exceptions.py`. Global FastAPI handlers in `src/app/core/error_handlers.py` automatically map them via Method Resolution Order (MRO) into standardized HTTP status codes (`404`, `409`, `422`, `429`, `500`).

---

## Project Folder Structure

```text
marketing-ai/
├── .env.example                               # Template for environment variables (keys, paths)
├── .gitignore                                 # Ignores .venv, storage/, dist/, node_modules/
├── alembic.ini                                # Alembic migration runner configuration
├── pyproject.toml                             # uv project definition, dependencies, pytest config
├── README.md                                  # Setup, architecture overview, and developer commands
├── run_desktop.py                             # Desktop launcher (PyInstaller entrypoint)
│
├── alembic/                                   # Database migration scripts
│   ├── env.py                                 # Custom libSQL proxy & batch migration configuration
│   ├── script.py.mako                         # Migration revision template
│   └── versions/                              # Tracked database migration revisions
│       └── 87022a803884_create_accounts_table.py
│
├── storage/                                   # Local runtime state (gitignored)
│   ├── browser_sessions/                      # Playwright storage_state.json cookies per account
│   ├── local_db/                              # Embedded replica SQLite files
│   │   └── local_auth.db
│   ├── logs/                                  # Rotating application log files
│   │   └── app.log
│   └── media/                                 # Local campaign images, videos, and generated assets
│
├── frontend/                                  # Independent Vite + React (TypeScript) SPA
│   ├── index.html                             # App root HTML
│   ├── package.json                           # Frontend npm dependencies and build scripts
│   ├── tsconfig.json                          # TypeScript configuration
│   ├── vite.config.ts                         # Vite dev server with /api and /ws proxy to :8000
│   ├── dist/                                  # Production static build (served by FastAPI)
│   └── src/
│       ├── main.tsx                           # React bootstrap
│       ├── App.tsx                            # Root application layout and navigation
│       ├── api/                               # Typed API client wrappers (fetch/axios)
│       ├── components/                        # Reusable UI widgets, modals, tables, navbars
│       ├── features/                          # Feature views matching domain modules
│       │   ├── accounts/                      # Account connection & session manager UI
│       │   ├── campaigns/                     # Content calendar & post queue visualizer
│       │   ├── triggers/                      # Target watcher & auto-reply rule manager
│       │   ├── outreach/                      # Influencer lead CRM & staging pipeline
│       │   ├── copilot/                       # Streaming agent chat interface
│       │   └── history/                       # Unified activity audit trail logs
│       └── hooks/                             # Custom React hooks (WebSocket, auth, polling)
│
├── tests/                                     # Root test suite (pytest)
│   ├── conftest.py                            # Shared fixtures: in-memory DB, proxy fixtures, TestClient
│   ├── unit/                                  # Fast, isolated domain, proxy, and cryptography tests
│   │   ├── __init__.py
│   │   ├── test_common_models.py              # AuditBase UUID and timestamp tests
│   │   ├── test_db_proxy.py                   # LibSqlProxyConnection interception tests
│   │   ├── test_security.py                   # Fernet AES token encryption/decryption tests
│   │   ├── test_accounts_service.py           # AccountService commands, quotas, and exceptions
│   │   ├── test_campaigns_service.py          # Campaign lifecycle and scheduling logic
│   │   ├── test_triggers_service.py           # Trigger rule evaluation and matching logic
│   │   ├── test_outreach_service.py           # Lead progression and DM approval gates
│   │   └── test_throttler.py                  # Anti-ban token bucket and cooldown logic
│   └── integration/                           # End-to-end DB session, HTTP router, & agent tests
│       ├── __init__.py
│       ├── test_db_session.py                 # Session lifecycles and rollback verification
│       ├── test_error_handlers.py             # Global exception mapping & status code verification
│       ├── test_accounts_api.py               # /api/v1/accounts endpoint integration tests
│       ├── test_campaigns_api.py              # /api/v1/campaigns endpoint integration tests
│       ├── test_triggers_api.py               # /api/v1/triggers endpoint integration tests
│       ├── test_outreach_api.py               # /api/v1/outreach endpoint integration tests
│       └── test_tool_calling.py               # Copilot LLM tool execution integration tests
│
└── src/                                       # Python application root (PYTHONPATH="src")
    └── app/
        ├── main.py                            # FastAPI app, lifespan setup, router mounts, SPA host
        │
        ├── core/                              # Cross-cutting foundational utilities
        │   ├── __init__.py
        │   ├── agent_config.py                # LLM provider settings, model parameters, temperature
        │   ├── config.py                      # Pydantic Settings (.env, database paths, secret keys)
        │   ├── logging.py                     # Logfire / standard library rotating logger
        │   ├── security.py                    # Master key generation, Fernet token encrypt/decrypt
        │   ├── error_handlers.py              # Centralized global FastAPI exception handlers
        │   └── deps.py                        # Common FastAPI dependency injections (pagination, auth)
        │
        ├── common/                            # Reusable base classes and domain primitives
        │   ├── __init__.py
        │   ├── base_models.py                 # AuditBase mixin (UUID primary key, created/updated timestamps)
        │   ├── enums.py                       # PlatformType, AccountStatus, CampaignStatus, etc.
        │   └── exceptions.py                  # Base domain error hierarchy (NotFoundError, ConflictError)
        │
        ├── db/                                # Database engine & session persistence
        │   ├── __init__.py
        │   ├── base.py                        # DeclarativeBase root metadata
        │   ├── dependencies.py                # FastAPI get_db_session dependency provider
        │   ├── proxy.py                       # LibSqlProxyConnection SQLite dialect interceptor
        │   ├── session.py                     # libSQL engine factory and session lifecycle management
        │   └── all_models.py                  # Global model registry importing every module model
        │
        ├── modules/                           # Vertical Domain Feature Slices
        │   │
        │   ├── accounts/                      # Social Accounts & Credential Vault
        │   │   ├── __init__.py
        │   │   ├── models.py                  # ConnectedAccount model
        │   │   ├── commands.py                # CreateAccountCommand, UpdateAccountCommand (dataclasses)
        │   │   ├── schemas.py                 # AccountCreateRequest, AccountResponse (Pydantic)
        │   │   ├── exceptions.py              # AccountNotFoundError, AccountAlreadyExistsError
        │   │   ├── service.py                 # AccountService (business logic, quota checks)
        │   │   └── router.py                  # HTTP endpoints (/api/v1/accounts)
        │   │
        │   ├── campaigns/                     # Marketing Goals, Posts & Scheduling
        │   │   ├── __init__.py
        │   │   ├── models.py                  # Campaign, ScheduledPost models
        │   │   ├── commands.py                # CreateCampaignCommand, QueuePostCommand
        │   │   ├── schemas.py                 # CampaignCreateRequest, PostResponse
        │   │   ├── exceptions.py              # CampaignNotFoundError, InvalidScheduleError
        │   │   ├── service.py                 # CampaignService (publishing pipelines, status changes)
        │   │   └── router.py                  # HTTP endpoints (/api/v1/campaigns)
        │   │
        │   ├── triggers/                      # Competitor/Keyword Monitoring & Auto-Replies
        │   │   ├── __init__.py
        │   │   ├── models.py                  # WatchedHandle, TriggerRule, TriggerMatch models
        │   │   ├── commands.py                # AddWatchedHandleCommand, CreateTriggerRuleCommand
        │   │   ├── schemas.py                 # TriggerRuleRequest, WatchedHandleResponse
        │   │   ├── exceptions.py              # TriggerRuleNotFoundError
        │   │   ├── service.py                 # TriggerService (keyword evaluation, match dispatch)
        │   │   └── router.py                  # HTTP endpoints (/api/v1/triggers)
        │   │
        │   ├── outreach/                      # Influencer Discovery & Cold Outreach CRM
        │   │   ├── __init__.py
        │   │   ├── models.py                  # Influencer, OutreachCampaign, OutreachMessage models
        │   │   ├── commands.py                # ImportLeadCommand, StageMessageCommand, ApproveMessageCommand
        │   │   ├── schemas.py                 # LeadRequest, OutreachMessageResponse
        │   │   ├── exceptions.py              # LeadNotFoundError, MessageAlreadySentError
        │   │   ├── service.py                 # OutreachService (pipeline stages, review gates)
        │   │   └── router.py                  # HTTP endpoints (/api/v1/outreach)
        │   │
        │   ├── copilot/                       # AI Agent Conversations & Tool Traces
        │   │   ├── __init__.py
        │   │   ├── models.py                  # ChatSession, ChatMessage, ToolExecutionLog models
        │   │   ├── commands.py                # SendChatMessageCommand, LogToolExecutionCommand
        │   │   ├── schemas.py                 # ChatMessageRequest, ChatStreamResponse
        │   │   ├── exceptions.py              # SessionNotFoundError, ToolExecutionFailedError
        │   │   ├── service.py                 # CopilotService (chat persistence, history hydration)
        │   │   └── router.py                  # WebSocket & SSE streaming endpoints (/api/v1/copilot)
        │   │
        │   └── history/                       # Audit Trail & Activity Logging
        │       ├── __init__.py
        │       ├── models.py                  # ActivityLog model
        │       ├── commands.py                # LogActivityCommand
        │       ├── schemas.py                 # ActivityLogFilterQuery, ActivityLogResponse
        │       ├── exceptions.py              # ActivityLogNotFoundError
        │       ├── service.py                 # HistoryService (centralized append-only audit trail)
        │       └── router.py                  # HTTP query endpoints (/api/v1/history)
        │
        ├── agent/                             # LLM Orchestration & Copilot Engine
        │   ├── __init__.py
        │   ├── llm.py                         # OpenAI/Anthropic/Local Ollama client initialization
        │   ├── prompts.py                     # System prompts, marketing persona directives
        │   ├── loop.py                        # ReAct/Tool-calling execution loop with streaming
        │   └── tools/                         # Typed tool declarations exposed to LLM
        │       ├── __init__.py
        │       ├── account_tools.py           # get_accounts, check_account_health
        │       ├── campaign_tools.py          # draft_post, schedule_post, list_pending_posts
        │       ├── trigger_tools.py           # watch_handle, review_auto_reply_matches
        │       └── outreach_tools.py          # find_leads, queue_outreach_dm
        │
        ├── platforms/                         # Social Media Platform Automation Adapters
        │   ├── __init__.py
        │   ├── base.py                        # BasePlatformAdapter abstract base class
        │   ├── registry.py                    # Adapter factory resolving platform instances
        │   ├── browser/                       # Playwright Stealth Automation Engine
        │   │   ├── __init__.py
        │   │   ├── driver.py                  # Headless/headed Playwright browser factory
        │   │   ├── session_manager.py         # Cookie loading, dumping, and validity checks
        │   │   └── human_behavior.py          # Jittered mouse trajectories, human-like typing
        │   ├── twitter/                       # X / Twitter Automation
        │   │   ├── __init__.py
        │   │   ├── adapter.py                 # Implements BasePlatformAdapter (posts, replies, DMs)
        │   │   ├── selectors.py               # DOM element selectors (kept isolated for easy updates)
        │   │   └── scraper.py                 # Timeline, search, and profile scraper
        │   └── instagram/                     # Instagram Automation
        │       ├── __init__.py
        │       ├── adapter.py                 # Implements BasePlatformAdapter
        │       └── selectors.py               # Instagram web DOM selectors
        │
        └── automation/                        # Offline Background Schedulers & Workers
            ├── __init__.py
            ├── scheduler.py                   # APScheduler configuration & lifecycle hooks
            ├── throttler.py                   # Token bucket rate-limiter & anti-ban safety pacing
            └── workers/                       # Dedicated worker task loops
                ├── __init__.py
                ├── post_dispatcher.py         # Polls scheduled posts and triggers platform adapter
                ├── watcher_worker.py          # Periodic scraper polling watched competitor feeds
                └── quota_reset_worker.py      # Daily counter maintenance & session health checker

```

---

## Getting Started

### 1. Prerequisites

* **Python 3.12+** managed via [`uv`](https://docs.astral.sh/uv/)
* **Node.js 20+** (for building/developing the Vite frontend)

### 2. Environment Configuration

Copy the example environment file and generate a master encryption key:

```powershell
Copy-Item .env.example .env

```

Generate a fresh 32-byte Fernet `SECRET_KEY`:

```powershell
uv run python -c "from app.core.security import generate_master_key; print(generate_master_key())"

```

Paste the output into `.env` under `SECRET_KEY`.

### 3. Install Dependencies & Browsers

```powershell
# Sync Python virtual environment and packages
uv sync

# Install Playwright Chromium binary for browser automation
uv run playwright install chromium

```

### 4. Database Migrations

Apply Alembic migrations to initialize the local `libSQL` replica inside `storage/local_db/`:

```powershell
uv run alembic upgrade head

```

To generate a new migration after creating or modifying models in `src/app/modules/*/models.py` (ensure the model is imported in `src/app/db/all_models.py`):

```powershell
uv run alembic revision --autogenerate -m "describe_schema_changes"
uv run alembic upgrade head

```

---

## Running the Application

### Start the FastAPI Backend

```powershell
uv run uvicorn app.main:app --reload --app-dir src --host 127.0.0.1 --port 8000

```

* **Interactive Swagger Docs:** `http://127.0.0.1:8000/docs`
* **Healthcheck Endpoint:** `http://127.0.0.1:8000/health`

### Start the Vite Frontend (Development)

```powershell
cd frontend
npm install
npm run dev

```

* **Frontend Dev Server:** `http://localhost:5173`

---

## Testing

The test suite uses an isolated in-memory SQLite engine (`StaticPool`) with automatic per-test transaction rollbacks and FastAPI dependency overrides.

```powershell
# Run the complete test suite
uv run pytest -v

# Run only fast unit tests (services, commands, encryption, proxies)
uv run pytest tests/unit -v

# Run only integration tests (HTTP endpoints, error handlers, DB sessions)
uv run pytest tests/integration -v

```

---

## Building a Standalone Windows Binary

You can package the entire backend, database engine, and compiled React frontend into a standalone Windows application:

```powershell
# 1. Compile the Vite frontend into static assets
cd frontend
npm run build
cd ..

# 2. Bundle with PyInstaller
uv run pyinstaller `
    --name "MarketingAI" `
    --noconsole `
    --onedir `
    --add-data "frontend/dist;frontend/dist" `
    --collect-all "libsql" `
    --collect-all "playwright" `
    --paths "src" `
    run_desktop.py

```

The standalone executable will be generated in `dist/MarketingAI/MarketingAI.exe` and can be wrapped into a standard Windows `Setup.exe` installer using **Inno Setup**.

```

<FollowUp label="Ready to build the `campaigns` domain module next?" query="Let's build the campaigns domain module (models, commands, schemas, exceptions, service, router)."/>