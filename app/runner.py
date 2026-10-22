from __future__ import annotations
import threading
import time
import datetime
from typing import Dict, List, Optional, Callable
from app.models import (
    Workflow,
    SchedulerConfig,
    ExecutionState,
    ExecutionProgress,
    ActivityLogEntry,
    ActionType
)
from app.device import DeviceManager, ADBDevice
from app.actions import ActionExecutor

class AutomationRunner:
    def __init__(self, device_manager: DeviceManager):
        self.device_manager = device_manager
        self.progress = ExecutionProgress()
        self.logs: List[ActivityLogEntry] = []
        self._max_logs = 500

        self._thread: Optional[threading.Thread] = None
        self._pause_event = threading.Event()
        self._stop_event = threading.Event()
        self._pause_event.set()

        self._lock = threading.Lock()
        self._on_update_callbacks: List[Callable[[], None]] = []

    def subscribe_update(self, cb: Callable[[], None]):
        self._on_update_callbacks.append(cb)

    def _notify_update(self):
        for cb in self._on_update_callbacks:
            try:
                cb()
            except Exception:
                pass

    def log(self, message: str, level: str = "info", workflow_id: Optional[str] = None, task_name: Optional[str] = None):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        entry = ActivityLogEntry(
            timestamp=ts,
            level=level,
            message=message,
            workflow_id=workflow_id or self.progress.current_workflow_id,
            task_name=task_name or self.progress.current_task_name
        )
        with self._lock:
            self.logs.append(entry)
            if len(self.logs) > self._max_logs:
                self.logs.pop(0)
        self._notify_update()

    def get_logs(self) -> List[ActivityLogEntry]:
        with self._lock:
            return list(self.logs)

    def clear_logs(self):
        with self._lock:
            self.logs.clear()
        self._notify_update()

    def get_progress(self) -> ExecutionProgress:
        with self._lock:
            return self.progress.model_copy()

    def start(self, scheduler_config: SchedulerConfig, workflows: Dict[str, Workflow]):
        if self._thread and self._thread.is_alive():
            if self.progress.state == ExecutionState.RUNNING:
                raise RuntimeError("Automation is already running.")
            else:
                self._stop_event.set()
                self._pause_event.set()
                self._thread.join(timeout=3.0)

        dev = self.device_manager.get_active_device()
        if not dev or not dev.is_connected():
            raise RuntimeError("No connected Android device found to execute automation.")

        if not scheduler_config.items:
            raise RuntimeError("No workflows added to queue.")

        self._stop_event.clear()
        self._pause_event.set()
        self.progress.state = ExecutionState.RUNNING
        self.progress.error_message = None
        self.progress.active_device = dev.serial
        self.progress.elapsed_seconds = 0.0

        dur_text = "Infinite (non-stop)" if scheduler_config.duration_minutes <= 0 else f"{scheduler_config.duration_minutes:.1f} minutes"
        self.log(f"Starting automation: {dur_text} on device {dev.serial}", "info")

        self._thread = threading.Thread(
            target=self._run_loop,
            args=(scheduler_config, workflows, dev),
            daemon=True
        )
        self._thread.start()
        self._notify_update()

    def pause(self):
        if self.progress.state == ExecutionState.RUNNING:
            self._pause_event.clear()
            self.progress.state = ExecutionState.PAUSED
            self.log("Automation paused by user.", "warning")
            self._notify_update()

    def resume(self):
        if self.progress.state == ExecutionState.PAUSED:
            self.progress.state = ExecutionState.RUNNING
            self._pause_event.set()
            self.log("Automation resumed.", "info")
            self._notify_update()

    def stop(self):
        if self.progress.state in [ExecutionState.RUNNING, ExecutionState.PAUSED]:
            self._stop_event.set()
            self._pause_event.set()
            self.progress.state = ExecutionState.STOPPED
            self.log("Automation stopped by user.", "warning")
            self._notify_update()
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=3.0)

    def _run_loop(self, config: SchedulerConfig, workflows: Dict[str, Workflow], device: ADBDevice):
        start_time = time.time()
        
        target_limit_sec = None
        if config.duration_minutes and config.duration_minutes > 0:
            target_limit_sec = config.duration_minutes * 60.0
        elif config.max_execution_duration and config.max_execution_duration > 0:
            target_limit_sec = config.max_execution_duration

        is_infinite = (target_limit_sec is None)
        self.progress.is_infinite = is_infinite
        self.progress.duration_minutes = config.duration_minutes
        self.progress.total_queue_items = len(config.items)

        try:
            current_queue_idx = 0
            while not self._stop_event.is_set():
                if target_limit_sec and (time.time() - start_time) >= target_limit_sec:
                    self.log(f"Configured duration of {config.duration_minutes:.1f}m reached. Automation complete.", "info")
                    break

                item = config.items[current_queue_idx % len(config.items)]
                self.progress.current_queue_index = (current_queue_idx % len(config.items)) + 1
                wf = workflows.get(item.workflow_id)
                if not wf:
                    self.log(f"Workflow ID '{item.workflow_id}' not found. Skipping.", "error")
                    current_queue_idx += 1
                    continue

                self.progress.current_workflow_id = wf.id
                self.progress.current_workflow_name = wf.name
                self.progress.total_tasks = len(wf.tasks)

                executor = ActionExecutor(device, wf.randomization, wf.preset)

                item_duration_sec = None
                if item.duration_minutes and item.duration_minutes > 0:
                    item_duration_sec = item.duration_minutes * 60.0
                elif len(config.items) > 1 and target_limit_sec:
                    item_duration_sec = target_limit_sec / len(config.items)

                item_start_time = time.time()
                cycle = 0

                while not self._stop_event.is_set():
                    elapsed = time.time() - start_time
                    self.progress.elapsed_seconds = round(elapsed, 1)

                    if target_limit_sec and elapsed >= target_limit_sec:
                        break

                    if item_duration_sec and (time.time() - item_start_time) >= item_duration_sec:
                        self.log(f"Item duration reached for '{wf.name}'. Advancing to next workflow.", "info")
                        break

                    cycle += 1
                    self.progress.current_rep = cycle
                    self.log(f"Workflow '{wf.name}' — Cycle #{cycle}", "info")

                    for t_idx, task in enumerate(wf.tasks):
                        while not self._pause_event.is_set() and not self._stop_event.is_set():
                            time.sleep(0.3)

                        if self._stop_event.is_set():
                            break

                        elapsed = time.time() - start_time
                        self.progress.elapsed_seconds = round(elapsed, 1)
                        if target_limit_sec and elapsed >= target_limit_sec:
                            break

                        if not device.is_connected():
                            self.log(f"Device disconnected! Pausing until reconnected.", "error")
                            self.progress.state = ExecutionState.PAUSED
                            self.progress.error_message = "Device disconnected"
                            self._pause_event.clear()
                            self._notify_update()
                            while not self._pause_event.is_set() and not self._stop_event.is_set():
                                time.sleep(1.0)
                            if self._stop_event.is_set():
                                break

                        if cycle > 1:
                            if task.action_type in [ActionType.LAUNCH_APP, ActionType.OPEN_URL]:
                                continue
                            if task.action_type == ActionType.TAP_COORDS and ("tab" in task.name.lower() or "switch" in task.name.lower()):
                                continue
                            if task.action_type == ActionType.WAIT_INSPECT and ("init" in task.id or "first" in task.id):
                                continue

                        self.progress.current_task_index = t_idx + 1
                        self.progress.current_task_name = task.name
                        self._notify_update()

                        try:
                            executor.execute_action(
                                task,
                                logger=lambda msg, lvl: self.log(msg, lvl, wf.id, task.name),
                                should_stop=lambda: self._stop_event.is_set()
                            )
                        except Exception as e:
                            self.log(f"Notice on task '{task.name}': {e}. Continuing...", "warning")
                            time.sleep(1.0)

                    if not self._stop_event.is_set() and config.inter_repetition_delay > 0:
                        time.sleep(config.inter_repetition_delay)

                    if not is_infinite and not item_duration_sec and cycle >= max(1, item.repetitions):
                        break

                current_queue_idx += 1
                if not self._stop_event.is_set() and len(config.items) > 1:
                    time.sleep(config.inter_workflow_delay)

                if not is_infinite and current_queue_idx >= len(config.items) and not target_limit_sec:
                    break

            total_elapsed = round(time.time() - start_time, 1)
            self.progress.elapsed_seconds = total_elapsed

            if self._stop_event.is_set() and self.progress.state != ExecutionState.ERROR:
                self.progress.state = ExecutionState.STOPPED
                self.log(f"Automation stopped by user after {total_elapsed}s.", "warning")
            else:
                self.progress.state = ExecutionState.COMPLETED
                self.log(f"Automation completed in {total_elapsed}s.", "success")

        except Exception as e:
            self.progress.state = ExecutionState.ERROR
            self.progress.error_message = str(e)
            self.log(f"Automation halted due to error: {e}", "error")
        finally:
            self._notify_update()
