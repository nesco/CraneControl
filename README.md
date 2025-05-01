# Crane Control

A two-part system:

| Folder   | Tech stack | Description                     |
|----------|------------|---------------------------------|
| `backend`| Python + uvicorn | REST/WebSocket API for crane motors |
| `frontend`| Next.js + React | Operator UI dashboard |

## Quick start
```bash
# backend
cd backend && uv venv .venv --python 3.12 && source .venv/bin/activate && uv sync && uv run uvicorn crane_server:app --reload
# frontend
cd frontend && npm install && npm run dev

