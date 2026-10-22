import os
import requests
import time
import sys

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:28491")

def test_api_health():
    print("=== 1. Testing API Endpoints ===")
    res = requests.get(f"{BASE_URL}/api/devices")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    dev_data = res.json()
    print("Devices:", dev_data)
    assert len(dev_data["devices"]) > 0, "No device connected"

    res = requests.get(f"{BASE_URL}/api/workflows")
    assert res.status_code == 200
    workflows = res.json()
    print(f"Loaded {len(workflows)} workflows:")
    wf_ids = []
    for wf in workflows:
        wf_ids.append(wf["id"])
        print(f" - {wf['id']}: {wf['name']} ({len(wf['tasks'])} tasks)")
    
    assert "wf-doom-scroll-instagram-reels" in wf_ids, "Missing Instagram Reels workflow"
    assert "wf-doom-scroll-github-popular" in wf_ids, "Missing GitHub Popular workflow"

    res = requests.get(f"{BASE_URL}/api/scheduler")
    assert res.status_code == 200
    print("Scheduler items:", res.json()["items"])

    res = requests.get(f"{BASE_URL}/api/device/screenshot")
    assert res.status_code == 200
    assert len(res.content) > 1000
    print(f"Screenshot endpoint returned {len(res.content)} bytes JPEG image.")

def test_pause_resume_stop():
    print("\n=== 2. Testing Start, Pause, Resume, Stop Controls ===")
    sched = {
        "items": [{"workflow_id": "wf-doom-scroll-github-popular", "repetitions": 1}],
        "inter_repetition_delay": 1.0,
        "inter_workflow_delay": 2.0,
        "cooldown_interval": 0,
        "cooldown_duration": 0,
        "max_execution_duration": 300.0
    }
    res = requests.post(f"{BASE_URL}/api/control/start", json=sched)
    print("Start response:", res.json())

    time.sleep(3.0)
    status = requests.get(f"{BASE_URL}/api/status").json()
    print("State while running:", status["progress"]["state"], "| Task:", status["progress"]["current_task_name"])

    # Test PAUSE
    print("Calling Pause...")
    res = requests.post(f"{BASE_URL}/api/control/pause")
    time.sleep(1.0)
    status = requests.get(f"{BASE_URL}/api/status").json()
    print("State after pause:", status["progress"]["state"])
    assert status["progress"]["state"] == "paused", f"Expected paused, got {status['progress']['state']}"

    # Test RESUME
    print("Calling Resume...")
    res = requests.post(f"{BASE_URL}/api/control/resume")
    time.sleep(1.0)
    status = requests.get(f"{BASE_URL}/api/status").json()
    print("State after resume:", status["progress"]["state"])
    assert status["progress"]["state"] == "running", f"Expected running, got {status['progress']['state']}"

    # Test STOP
    print("Calling Stop...")
    res = requests.post(f"{BASE_URL}/api/control/stop")
    time.sleep(1.0)
    status = requests.get(f"{BASE_URL}/api/status").json()
    print("State after stop:", status["progress"]["state"])
    assert status["progress"]["state"] == "stopped", f"Expected stopped, got {status['progress']['state']}"
    print("Start, Pause, Resume, Stop test passed successfully!")

if __name__ == "__main__":
    test_api_health()
    test_pause_resume_stop()
