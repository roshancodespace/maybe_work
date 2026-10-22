import requests
import time

BASE_URL = "http://127.0.0.1:8000"

def test_feed_scroller():
    print("=== Testing GitHub Feed Infinite Scroller (with More button click) ===")
    sched = {
        "items": [{"workflow_id": "wf-github-feed-scroller", "repetitions": 1}],
        "inter_repetition_delay": 1.0,
        "inter_workflow_delay": 1.0,
        "cooldown_interval": 0,
        "cooldown_duration": 0.0,
        "max_execution_duration": 300.0
    }
    res = requests.post(f"{BASE_URL}/api/control/start", json=sched)
    assert res.status_code == 200, f"Start failed: {res.text}"
    print("Started Feed Scroller workflow.")

    start_t = time.time()
    last_task = None
    while time.time() - start_t < 120:
        status = requests.get(f"{BASE_URL}/api/status").json()
        p = status["progress"]
        st = p["state"]
        curr_task = p["current_task_name"]
        if curr_task != last_task:
            print(f"[{p['elapsed_seconds']:.1f}s] Task {p['current_task_index']}/{p['total_tasks']}: {curr_task}")
            last_task = curr_task

        if st in ["completed", "error", "stopped"]:
            print(f"Feed scroller finished with state: {st} (elapsed {p['elapsed_seconds']:.1f}s)")
            assert st == "completed", f"Feed scroller ended in {st}: {p.get('error_message')}"
            break
        time.sleep(1.5)

    print("=== GitHub Feed Infinite Scroller Completed Successfully! ===")

if __name__ == "__main__":
    test_feed_scroller()
