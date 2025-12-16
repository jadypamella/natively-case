# Architecture

## Overview

This is an AI-powered website builder that uses Claude to generate websites from natural language descriptions. The architecture consists of a Next.js frontend and a Python backend running on Modal's serverless infrastructure.

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Next.js App   │────▶│   Modal Backend  │────▶│  Claude Agent   │
│   (Frontend)    │◀────│   (FastAPI)      │◀────│  (Anthropic)    │
└─────────────────┘     └──────────────────┘     └─────────────────┘
         │                       │
         │ WebSocket             │ Generates HTML/CSS/JS
         ▼                       ▼
┌─────────────────┐     ┌──────────────────┐
│  Live Preview   │◀────│   HTTP Server    │
│   (iframe)      │     │   (npx serve)    │
└─────────────────┘     └──────────────────┘
```

---

## Tech Stack

### Frontend
| Technology | Purpose |
|------------|---------|
| **Next.js 16** | React framework with App Router |
| **TypeScript** | Type safety |
| **Tailwind CSS 4** | Styling |
| **Radix UI** | Accessible UI primitives |
| **Lucide React** | Icons |

### Backend
| Technology | Purpose |
|------------|---------|
| **Python 3.12** | Backend language |
| **FastAPI** | REST API framework |
| **Modal** | Serverless compute platform |
| **Claude Agent SDK** | AI agent orchestration |
| **uvicorn** | ASGI server for WebSockets |

### External Services
| Service | Purpose |
|---------|---------|
| **Anthropic API** | Claude AI for code generation |
| **Modal** | Serverless deployment & sandboxing |

---

## Components

### Frontend (`appandrunning/`)

#### `app/page.tsx`
Main entry page with example prompts and chat input.

#### `app/chat/[id]/page.tsx`
Chat interface that:
- Connects to backend WebSocket
- Displays AI responses
- Shows website preview in iframe
- Handles `pages_discovered` events for Page Selector

#### `app/components/WebsitePreview.tsx`
iframe wrapper that displays generated website with:
- Refresh button
- Open in new tab
- **Page Selector** dropdown for navigation

#### `app/components/PageSelector.tsx`
Hierarchical dropdown showing:
- All HTML pages in generated website
- Sections with IDs within each page
- Click to navigate iframe

#### `app/hooks/useAgentSession.ts`
WebSocket hook for real-time communication with backend.

#### `app/lib/api-client.ts`
HTTP client for REST API calls.

---

### Backend (Root)

#### `API.py`
Modal app entry point. Defines the web endpoint and imports routes.

#### `routes.py`
FastAPI routes:
- `POST /api/chat` - Start new chat session
- `GET /api/sessions/{id}` - Get session status
- `GET /api/sessions` - List all sessions

#### `agent.py`
Core agent logic:
- `run_agent_in_sandbox()` - Main Modal function
- `run_claude_agent_multiturn()` - Multi-turn conversation handler
- `scan_workspace_pages()` - Parses HTML files for Page Selector
- WebSocket server for real-time events

#### `dev_server.py`
`DevServerManager` class:
- Starts `npx serve` to host generated files
- Health checks and auto-restart
- Monitors server status

#### `config.py`
Modal app configuration:
- Docker image with Node.js, npm, git
- Modal Dict for session storage

---

## Data Flow

1. **User submits prompt** → Frontend sends to `/api/chat`
2. **Backend creates session** → Spawns Modal sandbox
3. **Claude Agent runs** → Generates HTML/CSS/JS files
4. **Dev server starts** → `npx serve` hosts files on port 3000
5. **Modal tunnel created** → Public URL for preview
6. **WebSocket events sent** → Real-time updates to frontend
7. **`pages_discovered`** → Page Selector receives page list
8. **iframe loads** → User sees live preview

---

## Key Events (WebSocket)

| Event | Description |
|-------|-------------|
| `websocket_ready` | Connection established |
| `coding_start` | Agent started working |
| `claude_text` | Streaming text response |
| `claude_tool_use` | Agent using tool (file write, etc.) |
| `dev_server_started` | Preview server ready |
| `pages_discovered` | Pages/sections for Page Selector |
| `ready_for_input` | Agent waiting for next prompt |
| `agent_complete` | Session finished |

---

## Deployment

### Backend (Modal)
```bash
uv run modal deploy API.py
```

### Frontend (Local Dev)
```bash
cd appandrunning
npm run dev
```

### Frontend (Production)
Deploy to Vercel or any Node.js hosting.

---

## Environment Variables

### Backend
- `ANTHROPIC_API_KEY` - Claude API key (Modal secret)

### Frontend
- `NEXT_PUBLIC_API_URL` - Modal backend URL
