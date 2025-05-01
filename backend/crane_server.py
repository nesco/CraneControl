import asyncio
import json
import math
import time

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

## Constants

REFRESH_DELAY = 0.04  # 40ms / 25Hz

MAX_SPEED = {  # units / s
    "swingDeg": 90,
    "liftMm": 300,
    "elbowDeg": 120,
    "wristDeg": 180,
    "gripMm": 200,
}
MAX_ACCEL = {k: v * 3 for k, v in MAX_SPEED.items()}  # simple rule

ELBOW_LEN = 0.75
WRIST_LEN = 0.5625
PIVOT_W = 0.15

MIN_LIFT_MM = 200
MAX_LIFT_MM = 3000

DROPBOX_H = 0.12
ELBOW_W = PIVOT_W * 4/5
WRIST_W = ELBOW_W * 4/5

## Crane State

class CraneState(BaseModel):
    swingDeg: float
    liftMm: float
    elbowDeg: float
    wristDeg: float
    gripMm: float = 70


## App

app = FastAPI()
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


## Global Variables

state = CraneState(
    swingDeg=0,
    liftMm=2_000,
    elbowDeg=45,
    wristDeg=330,
)
state_lock = asyncio.Lock()  # protect concurrent writers
clients: set[WebSocket] = set()  # every connected front-end

targets = state.model_dump()  # current goals = current positions
vel = {k: 0.0 for k in MAX_SPEED}


## Helpers

def wrap180(a_deg: float) -> float:
    """Shortest signed angle difference in (-180, 180] deg."""
    return (a_deg + 180.0) % 360.0 - 180.0


def ik_xyz_to_joints(
    x_mm: float,
    y_mm: float,
    z_mm: float,
) -> dict[str, float]:
    """
    Analytic 2-R IK (base-swing + elbow) for a crane whose vertical motion
    is produced **only** by the prismatic lift.
    The function returns whichever inverse branch needs the smallest
    change in base swing from the current pose.
    """

    # 1 ── metric units and planar reduction ────────────────────────────
    x, z = x_mm / 1000.0, z_mm / 1000.0          # m
    theta1 = math.atan2(z, x)                    # rad, candidate swing
    r = math.hypot(x, z) - PIVOT_W               # horizontal reach

    # 2 ── workspace check (purely planar) ──────────────────────────────
    r_min = abs(ELBOW_LEN - WRIST_LEN)
    r_max = ELBOW_LEN + WRIST_LEN
    if not r_min <= r <= r_max:
        print("Target out of reach in the X-Z plane")
        r = min(max(r, r_min), r_max)

    # 3 ── elbow magnitude (law of cosines, planar) ─────────────────────
    cos_el = (r*r - ELBOW_LEN**2 - WRIST_LEN**2) / (2*ELBOW_LEN*WRIST_LEN)
    theta2_mag = math.acos(cos_el)               # ≥ 0, rad
    pos_bend = x - WRIST_LEN*math.cos(theta2_mag), z - WRIST_LEN*math.sin(theta2_mag)
    neg_bend = x - WRIST_LEN*math.cos(theta2_mag), z + WRIST_LEN*math.sin(theta2_mag)
    print(f"theta1: {math.degrees(theta1)}, theta2: {math.degrees(theta2_mag)}")

    # 4 ── produce the two inverse branches ─────────────────────────────
    branches = [
        {   # elbow-down (positive bend)
            "swingDeg": math.degrees(math.atan2(pos_bend[1], pos_bend[0])),
            "elbowDeg":  math.degrees(+theta2_mag),
        },
        {   # elbow-up (negative bend)
            "swingDeg": math.degrees(math.atan2(neg_bend[1], neg_bend[0])),
            "elbowDeg":  math.degrees(-theta2_mag),
        },
    ]

    # 5 ── choose the one that disturbs swing the least ─────────────────
    best = min(
        branches,
        key=lambda b: abs(wrap180(b["swingDeg"] - state.swingDeg))
    )
    print(f"swing deg: { best["swingDeg"]} elbow deg: {best["elbowDeg"]} total: {best["swingDeg"] + best["elbowDeg"]} ")

    # 6 ── clamp lift (lift is the *only* source of Y motion) ───────────
    best["liftMm"] = max(MIN_LIFT_MM, min(MAX_LIFT_MM, y_mm))

    # wrap swing into 0…360 for the renderer / controller
    best["swingDeg"] %= 360.0

    return best

### Async functions


async def broadcaster():
    while True:
        await asyncio.sleep(REFRESH_DELAY)
        payload = state.model_dump_json()
        bad: set[WebSocket] = set()
        for ws in clients:
            try:
                await ws.send_text(payload)
            except WebSocketDisconnect:
                bad.add(ws)
        clients.difference_update(bad)  # drop closed sockets


async def motion_loop():
    last = time.perf_counter()
    while True:
        await asyncio.sleep(REFRESH_DELAY)
        now, dt = time.perf_counter(), time.perf_counter() - last
        last = now
        async with state_lock:
            cur = state.model_dump()
            for k, tgt in targets.items():
                err = tgt - cur[k]
                # desired speed limited by position error and max speed
                spd = max(-MAX_SPEED[k], min(MAX_SPEED[k], err / max(dt, 1e-4)))
                # acceleration limit
                dv = spd - vel[k]
                max_dv = MAX_ACCEL[k] * dt
                if abs(dv) > max_dv:
                    spd = vel[k] + max_dv * (1 if dv > 0 else -1)
                vel[k] = spd
                cur[k] += vel[k] * dt
            globals()["state"] = CraneState(**cur)


async def demo_motion():
    """Drive the same sine-wave animation that was in React."""
    t0 = time.perf_counter()
    while True:
        await asyncio.sleep(REFRESH_DELAY)  # 25 Hz
        t = time.perf_counter() - t0  # seconds since start
        new_vals = {
            # swingDeg stays fixed; elbowDeg commented out in original
            "gripMm": 20 + 50 * abs(math.sin(t)),
            "wristDeg": -100 * math.sin(t),
        }
        async with state_lock:
            global state
            state = state.model_copy(update=new_vals)  # Pydantic 2.x partial update


@app.on_event("startup")
async def start_tasks():
    asyncio.create_task(broadcaster())
    asyncio.create_task(motion_loop())
    # asyncio.create_task(demo_motion())


## WebSocket endpoint


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    clients.add(ws)
    try:
        while True:  # optional: receive commands
            raw = await ws.receive_text()
            msg = json.loads(raw)
            async with state_lock:
                if "xyz" in msg:
                    targets.update(ik_xyz_to_joints(**msg["xyz"]))
                else:
                    targets.update(msg)
    except WebSocketDisconnect:
        clients.discard(ws)
