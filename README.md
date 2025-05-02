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
```


## Questions
- Bonus: How can you deal with an origin sensor is noisy or has some jitter? Or oscillates slowly like it’s on a wavy ocean? Or if the data is lagging in time?

1. I would try to solve a noisy or jitter sensor through a low-pass filter to remove high frequencies from the signal.
2. Similarly to remove a oscillation I would add a band-stop filter around the frequency of this oscillation to attenuate it.
3. To solve a data lag issue, I would at first use linear extrapolations to predict the current state. In case it appears to be insufficient I would move to more complex predictive models.


- If you want to change the dimensions of the robotic crane, what needs to change? Can we use a single definition/configuration? What if we want to constrain the ranges of motions? Add another degree of freedom? Have multiple robots work together? Is your architecture easy to extend?

1. I currently  need to change all the physical constants both backend and frontend, they can be centralized in a JSON that would be imported both in the backend and frontend
2. To constrains the ranges of motions or add new degrees of freedom, a numeric solver can be used for the inverse kinematic.
3. To have multiple robots work together, the backend should simulate each one of them a dedicate a WebSocket channel to each. Then the front end should allow to select the crane which will receive the command of the coordinates or state panels.
4. For the current architecture to be able to extend nicely, I need to move the entire configuration in configuration files for the backend, and use a modular numeric solver for the IK.

