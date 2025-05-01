# Crane Control

A two-part system:

| Folder   | Tech stack | Description                     |
|----------|------------|---------------------------------|
| `backend`| Python + uvicorn | REST/WebSocket API for crane motors |
| `frontend`| Next.js + React | Operator UI dashboard |

## Quick start
```bash
# backend
cd backend && uvicorn main:app --reload
# frontend
cd frontend && npm install && npm run dev

