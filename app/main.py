from __future__ import annotations
import json
import os
import asyncio
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.models import (
    Workflow,
    SchedulerConfig,
    ExecutionProgress,
    DeviceStatus,
    ActivityLogEntry,
    BehaviorPreset
)
from app.device import DeviceManager
from app.runner import AutomationRunner

from contextlib import asynccontextmanager
import sys

# PyInstaller bundle path resolution
if getattr(sys, "frozen", False):
    BUNDLE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
else:
    BUNDLE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

STATIC_DIR = os.path.join(BUNDLE_DIR, "static")
if not os.path.exists(STATIC_DIR):
    STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "static")
if not os.path.exists(STATIC_DIR):
    STATIC_DIR = os.path.join(os.getcwd(), "static")

# Workflows file path resolution
LOCAL_WORKFLOWS = os.path.join(os.getcwd(), "workflows.json")
BUNDLED_WORKFLOWS = os.path.join(BUNDLE_DIR, "app", "workflows.json")
if not os.path.exists(BUNDLED_WORKFLOWS):
    BUNDLED_WORKFLOWS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "workflows.json")

WORKFLOWS_FILE = LOCAL_WORKFLOWS if os.path.exists(LOCAL_WORKFLOWS) else BUNDLED_WORKFLOWS

@asynccontextmanager
async def lifespan(app: FastAPI):
    async def periodic_check():
        while True:
            await asyncio.sleep(2.0)
            await broadcast_status()
    task = asyncio.create_task(periodic_check())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

app = FastAPI(title="Android Automation Engine", version="1.0.0", lifespan=lifespan)

device_manager = DeviceManager()
runner = AutomationRunner(device_manager)

# In-memory storage synced with workflows.json
workflows_store: Dict[str, Workflow] = {}
scheduler_store: SchedulerConfig = SchedulerConfig()

def load_data():
    global scheduler_store
    target = WORKFLOWS_FILE if os.path.exists(WORKFLOWS_FILE) else BUNDLED_WORKFLOWS
    if os.path.exists(target):
        try:
            with open(target, "r", encoding="utf-8") as f:
                data = json.load(f)
                for wf_data in data.get("workflows", []):
                    wf = Workflow.model_validate(wf_data)
                    workflows_store[wf.id] = wf
                if "scheduler" in data:
                    scheduler_store = SchedulerConfig.model_validate(data["scheduler"])
        except Exception as e:
            print(f"Error loading {target}: {e}")

def save_data():
    try:
        data = {
            "workflows": [wf.model_dump() for wf in workflows_store.values()],
            "scheduler": scheduler_store.model_dump()
        }
        target = WORKFLOWS_FILE
        if getattr(sys, "frozen", False) and target.startswith(getattr(sys, "_MEIPASS", "")):
            target = os.path.join(os.getcwd(), "workflows.json")
        with open(target, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Error saving data: {e}")

load_data()

# Connected WebSocket clients
active_websockets: List[WebSocket] = []

async def broadcast_status():
    if not active_websockets:
        return
    data = {
        "type": "update",
        "progress": runner.get_progress().model_dump(),
        "recent_logs": [entry.model_dump() for entry in runner.get_logs()[-15:]]
    }
    msg_str = json.dumps(data)
    to_remove = []
    for ws in active_websockets:
        try:
            await ws.send_text(msg_str)
        except Exception:
            to_remove.append(ws)
    for ws in to_remove:
        if ws in active_websockets:
            active_websockets.remove(ws)

# Schedule periodic broadcast / runner update hook
def runner_update_hook():
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(broadcast_status())
    except RuntimeError:
        pass

runner.subscribe_update(runner_update_hook)

# --- REST APIs ---

@app.get("/api/devices")
def get_devices():
    serials = device_manager.list_connected_serials()
    active_dev = device_manager.get_active_device()
    status = active_dev.get_status().model_dump() if active_dev else None
    return {
        "devices": serials,
        "active_serial": device_manager.active_serial,
        "active_status": status
    }

class SelectDeviceRequest(BaseModel):
    serial: str

@app.post("/api/devices/select")
def select_device(req: SelectDeviceRequest):
    ok = device_manager.select_device(req.serial)
    if not ok:
        raise HTTPException(status_code=400, detail="Device not found or not connected")
    return {"status": "ok", "selected": req.serial}

@app.get("/api/status")
def get_status():
    dev = device_manager.get_active_device()
    dev_status = dev.get_status().model_dump() if dev else None
    return {
        "progress": runner.get_progress().model_dump(),
        "device": dev_status
    }

@app.get("/api/workflows")
def list_workflows():
    return list(workflows_store.values())

@app.post("/api/workflows")
def create_workflow(wf: Workflow):
    if wf.id in workflows_store:
        raise HTTPException(status_code=400, detail="Workflow ID already exists")
    workflows_store[wf.id] = wf
    save_data()
    return wf

@app.get("/api/workflows/{wf_id}")
def get_workflow(wf_id: str):
    if wf_id not in workflows_store:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflows_store[wf_id]

@app.put("/api/workflows/{wf_id}")
def update_workflow(wf_id: str, wf: Workflow):
    workflows_store[wf_id] = wf
    save_data()
    return wf

@app.delete("/api/workflows/{wf_id}")
def delete_workflow(wf_id: str):
    if wf_id in workflows_store:
        del workflows_store[wf_id]
        # Also remove from scheduler queue if present
        scheduler_store.items = [i for i in scheduler_store.items if i.workflow_id != wf_id]
        save_data()
    return {"status": "ok"}

@app.post("/api/workflows/{wf_id}/duplicate")
def duplicate_workflow(wf_id: str):
    if wf_id not in workflows_store:
        raise HTTPException(status_code=404, detail="Workflow not found")
    orig = workflows_store[wf_id]
    new_id = f"{orig.id}-copy-{int(asyncio.get_event_loop().time() * 1000) % 10000}"
    new_wf = orig.model_copy(deep=True)
    new_wf.id = new_id
    new_wf.name = f"{orig.name} (Copy)"
    workflows_store[new_id] = new_wf
    save_data()
    return new_wf

@app.get("/api/scheduler")
def get_scheduler():
    return scheduler_store

@app.post("/api/scheduler")
def update_scheduler(sched: SchedulerConfig):
    global scheduler_store
    scheduler_store = sched
    save_data()
    return scheduler_store

@app.post("/api/control/start")
def control_start(req: Optional[SchedulerConfig] = None):
    global scheduler_store
    if req:
        scheduler_store = req
        save_data()
    try:
        runner.start(scheduler_store, workflows_store)
        return {"status": "started"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/control/pause")
def control_pause():
    runner.pause()
    return {"status": "paused"}

@app.post("/api/control/resume")
def control_resume():
    runner.resume()
    return {"status": "resumed"}

@app.post("/api/control/stop")
def control_stop():
    runner.stop()
    return {"status": "stopped"}

@app.get("/api/logs")
def get_logs():
    return runner.get_logs()

@app.delete("/api/logs")
def clear_logs():
    runner.clear_logs()
    return {"status": "cleared"}

@app.get("/api/device/screenshot")
def get_screenshot(quality: int = 70):
    dev = device_manager.get_active_device()
    if not dev or not dev.is_connected():
        raise HTTPException(status_code=503, detail="No connected device")
    try:
        img_bytes = dev.capture_screenshot_bytes(max_width=540)
        return Response(content=img_bytes, media_type="image/jpeg")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class DirectTapRequest(BaseModel):
    x: float
    y: float

@app.post("/api/device/tap")
def interactive_tap(req: DirectTapRequest):
    dev = device_manager.get_active_device()
    if not dev or not dev.is_connected():
        raise HTTPException(status_code=503, detail="No connected device")
    try:
        dev.tap(req.x, req.y)
        runner.log(f"Manual interactive tap at ({req.x:.2f}, {req.y:.2f})", "info")
        return {"status": "tapped"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class DirectKeyRequest(BaseModel):
    key: str

@app.post("/api/device/key")
def interactive_key(req: DirectKeyRequest):
    dev = device_manager.get_active_device()
    if not dev or not dev.is_connected():
        raise HTTPException(status_code=503, detail="No connected device")
    try:
        dev.press_key(req.key)
        runner.log(f"Manual interactive key: {req.key}", "info")
        return {"status": "pressed"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_websockets.append(websocket)
    # Send initial snapshot
    init_data = {
        "type": "init",
        "progress": runner.get_progress().model_dump(),
        "recent_logs": [entry.model_dump() for entry in runner.get_logs()[-30:]]
    }
    await websocket.send_text(json.dumps(init_data))
    try:
        while True:
            # Keep connection alive, listen for ping
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        if websocket in active_websockets:
            active_websockets.remove(websocket)
    except Exception:
        if websocket in active_websockets:
            active_websockets.remove(websocket)

# Serve static UI
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/")
    def serve_index():
        return FileResponse(os.path.join(STATIC_DIR, "index.html"))

def run_server():
    import argparse
    import uvicorn
    import multiprocessing
    multiprocessing.freeze_support()

    default_port = int(os.environ.get("PORT", "28491"))
    default_host = os.environ.get("HOST", "127.0.0.1")

    parser = argparse.ArgumentParser(description="Android Automation Engine")
    parser.add_argument("--host", default=default_host, help=f"Bind host (default: {default_host})")
    parser.add_argument("--port", type=int, default=default_port, help=f"Bind port (default: {default_port})")
    args = parser.parse_args()

    print(f"Starting Android Automation Server on http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")

if __name__ == "__main__":
    run_server()
