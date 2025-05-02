"""
FastAPI server which simulates a Monumental.co crane sending data, and receiving commands through telemetry
"""

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

MAX_SPEED |= {
    "xM": 1.0,
    "yM": 1.0,
    "zM": 1.0,
    "yawDeg": 90.0,
}

MAX_ACCEL = {k: v * 3 for k, v in MAX_SPEED.items()}  # simple rule

ELBOW_LEN = 0.75
WRIST_LEN = 0.5625
PIVOT_W = 0.15

MIN_LIFT_MM = 200
MAX_LIFT_MM = 3000

DROPBOX_H = 0.12
ELBOW_W = PIVOT_W * 4 / 5
WRIST_W = ELBOW_W * 4 / 5

ELBOW_DIST = PIVOT_W + ELBOW_LEN

JOINT_KEYS = {"swingDeg", "liftMm", "elbowDeg", "wristDeg", "gripMm"}

HYSTERESIS_DEG = 8.0  # only switch branch if it's this many degrees better
BLEND_DIST_MM = 20.0  # only allow switch when within 20 mm of target


## Crane State
class RootPose(BaseModel):
    xM: float = 0.0
    yM: float = 0.0
    zM: float = 0.0
    yawDeg: float = 0.0


class CraneState(RootPose):
    swingDeg: float
    liftMm: float
    elbowDeg: float
    wristDeg: float
    gripMm: float = 70


## IK Context


class IKContext:
    def __init__(self):
        # +1 = elbow-down branch, −1 = elbow-up branch
        self.elbow_sign = +1
        # last joint angles (deg)
        self.swing_prev = 0.0
        self.elbow_prev = 0.0


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
integrals = {k: 0.0 for k in MAX_SPEED}
Kp, Ki = 3.0, 0.3  # tune these

hold_xyz_mm: tuple[float, float, float] | None = None
ik_ctx = IKContext()

## Helpers


def wrap180(a_deg: float) -> float:
    """Shortest signed angle difference in (-180, 180] deg."""
    return (a_deg + 180.0) % 360.0 - 180.0


def angle_diff(a: float, b: float) -> float:
    """Calculate the shortest distance between two angles in degrees.
    Returns the signed difference in the range [-180, 180]."""
    diff = (a - b) % 360.0
    if diff > 180.0:
        diff -= 360.0
    return diff


def clamp(min_val: float, max_val: float, value: float) -> float:
    return min(max_val, max(min_val, value))


def planar_2R_ik(
    x: float, z: float, l1: float, l2: float
) -> tuple[tuple[float, float], tuple[float, float]]:
    r2 = x * x + z * z
    r = math.sqrt(r2)

    # Clamping if needed

    r_max = l1 + l2
    r_min = abs(l1 - l2)

    if r > r_max:
        x *= r_max / r
        z *= r_max / r
        r = r_max
        r2 = r * r
    elif r < r_min:
        if r < 1e-9:  # target was almost exactly at the elbow origin
            x, z = r_min, 0
        else:
            x *= r_min / r
            z *= r_min / r
        r = r_min
        r2 = r * r

    # Cosine law
    cos_el = (r2 - l1 * l1 - l2 * l2) / (2 * l1 * l2)
    cos_el = clamp(-1.0, 1.0, cos_el)
    θ2_mag = math.acos(cos_el)

    cos_al = (l1 * l1 + r2 - l2 * l2) / (2 * l1 * r)
    cos_al = max(-1.0, min(1.0, cos_al))
    α = math.acos(cos_al)
    φ = math.atan2(z, x)

    # elbow-down / elbow-up
    return ((φ - α, +θ2_mag), (φ + α, -θ2_mag))


def proportional_control(
    key: str, target: float, dt: float, current_state: dict
) -> float:
    error = target - current_state[key]
    integrals[key] += error * dt
    cmd = Kp * error + Ki * integrals[key]
    # Compute required speed
    speed = clamp(-MAX_SPEED[key], MAX_SPEED[key], cmd)

    # Check acceleration limit
    dv = speed - vel[key]
    max_dv = MAX_ACCEL[key] * dt

    if abs(dv) > max_dv:
        speed = vel[key] + max_dv * (1 if dv > 0 else -1)

    return speed


def joints_to_xz(current_state: CraneState):
    swing = math.radians(current_state.swingDeg)
    elbow = math.radians(current_state.elbowDeg)
    yaw = math.radians(current_state.yawDeg)

    lx = ELBOW_DIST * math.cos(swing) + WRIST_LEN * math.cos(swing + elbow)
    lz = ELBOW_DIST * math.sin(swing) + WRIST_LEN * math.sin(swing + elbow)

    dx = lx * math.cos(yaw) - lz * math.sin(yaw)
    dz = lx * math.sin(yaw) + lz * math.cos(yaw)

    x = dx + current_state.xM
    z = dz + current_state.zM

    return x, z


def world_xyz_to_joints(x_mm, y_mm, z_mm, current_state: CraneState):
    global ik_ctx
    # 1 - Translate global coordinates into the local origin of the crane
    dx = x_mm / 1000 - current_state.xM
    dy = y_mm / 1000 - current_state.yM
    dz = -(z_mm / 1000 - current_state.zM)

    # 2 - Translate into the frame of the crane
    yaw = math.radians(current_state.yawDeg)
    cy = math.cos(-yaw)
    sy = math.sin(-yaw)
    lx = dx * cy - dz * sy  # local +X (forward)
    lz = dx * sy + dz * cy  # local +Z (left)

    (θ1_dn, θ2_dn), (θ1_up, θ2_up) = planar_2R_ik(lx, lz, l1=ELBOW_DIST, l2=WRIST_LEN)

    # 4 ── pick the branch closest to current swing
    cand = [
        {
            "sign": 1,
            "swingDeg": wrap180(math.degrees(θ1_dn)),
            "elbowDeg": wrap180(math.degrees(θ2_dn)),
        },
        {
            "sign": -1,
            "swingDeg": wrap180(math.degrees(θ1_up)),
            "elbowDeg": wrap180(math.degrees(θ2_up)),
        },
    ]

    # 5 ── cost = joint‐space change from last frame
    def cost(sol):
        ds = angle_diff(sol["swingDeg"], ik_ctx.swing_prev)
        de = angle_diff(sol["elbowDeg"], ik_ctx.elbow_prev)
        return math.hypot(ds, de)

    for s in cand:
        s["cost"] = cost(s)

    best = min(cand, key=lambda s: s["cost"])
    current = next(s for s in cand if s["sign"] == ik_ctx.elbow_sign)

    # 6 ── hysteresis + proximity check before switching
    if best["sign"] != current["sign"]:
        if (best["cost"] + HYSTERESIS_DEG) < current["cost"]:
            # only if elbow is already near the Cartesian target
            # compute FK to see distance to goal:
            x_fk, z_fk = joints_to_xz(
                CraneState(
                    **{
                        **current_state.model_dump(),
                        "swingDeg": best["swingDeg"],
                        "elbowDeg": best["elbowDeg"],
                    }
                )
            )
            dist = math.hypot(x_fk * 1000 - x_mm, z_fk * 1000 - z_mm)
            if dist < BLEND_DIST_MM:
                ik_ctx.elbow_sign = best["sign"]
                current = best

    # 7 ── commit this branch
    ik_ctx.swing_prev = current["swingDeg"]
    ik_ctx.elbow_prev = current["elbowDeg"]

    # 8 ── cope with lift & bookkeeping
    best["liftMm"] = clamp(
        MIN_LIFT_MM, MAX_LIFT_MM, y_mm + DROPBOX_H + WRIST_W + ELBOW_W
    )

    del best["cost"]
    del best["sign"]

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
    global hold_xyz_mm, state
    last = time.perf_counter()
    while True:
        await asyncio.sleep(REFRESH_DELAY)
        now, dt = time.perf_counter(), time.perf_counter() - last
        last = now
        async with state_lock:
            cur = state.model_dump()
            # Control loop
            for k, tgt in targets.items():
                vel[k] = proportional_control(k, tgt, dt, cur)
                cur[k] += vel[k] * dt
            if hold_xyz_mm is not None:
                # recompute joint targets every tick so that EE ≈ hold_xyz in world
                jt = world_xyz_to_joints(*hold_xyz_mm, current_state=CraneState(**cur))
                targets.update(jt)
            globals()["state"] = CraneState(**cur)


async def demo_motion():
    global state
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
            state = state.model_copy(update=new_vals)  # Pydantic 2.x partial update


async def spin_origin(r=1.0, period=60.0):
    t0 = time.perf_counter()
    while True:
        await asyncio.sleep(REFRESH_DELAY)
        t = (time.perf_counter() - t0) * 2 * math.pi / period
        async with state_lock:
            targets.update(
                {
                    "xM": r * math.cos(t),
                    "zM": r * math.sin(t),
                    "yawDeg": math.degrees(t) % 360,
                }
            )


@app.on_event("startup")
async def start_tasks():
    asyncio.create_task(broadcaster())
    asyncio.create_task(motion_loop())
    asyncio.create_task(spin_origin())
    # asyncio.create_task(demo_motion())


## WebSocket endpoint


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    global hold_xyz_mm, state, _base_x0, _base_z0
    await ws.accept()
    clients.add(ws)
    try:
        while True:  # optional: receive commands
            raw = await ws.receive_text()
            msg = json.loads(raw)
            async with state_lock:
                if "xyz" in msg:
                    hold_xyz_mm = (
                        msg["xyz"]["x_mm"],
                        msg["xyz"]["y_mm"],
                        msg["xyz"]["z_mm"],
                    )
                    _base_x0, _base_z0 = state.xM, state.zM
                    targets.update(
                        world_xyz_to_joints(**msg["xyz"], current_state=state)
                    )
                elif any(k in msg for k in JOINT_KEYS):
                    hold_xyz_mm = None
                    targets.update({k: msg[k] for k in JOINT_KEYS if k in msg})
                else:
                    targets.update(msg)
    except WebSocketDisconnect:
        clients.discard(ws)
