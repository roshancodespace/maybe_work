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
    BehaviorPreset
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
        self._pause_event.set()  # set = running, clear = paused

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
            level=level,  # type: ignore
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
            raise RuntimeError("No workflows added to scheduler queue.")

        self._stop_event.clear()
        self._pause_event.set()
        self.progress.state = ExecutionState.RUNNING
        self.progress.error_message = None
        self.progress.active_device = dev.serial
        self.progress.elapsed_seconds = 0.0

        self.log(f"Starting automation queue on device {dev.serial} ({len(scheduler_config.items)} workflow items)", "info")

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
            self.log("Automation execution paused by user.", "warning")
            self._notify_update()

    def resume(self):
        if self.progress.state == ExecutionState.PAUSED:
            self.progress.state = ExecutionState.RUNNING
            self._pause_event.set()
            self.log("Automation execution resumed.", "info")
            self._notify_update()

    def stop(self):
        if self.progress.state in [ExecutionState.RUNNING, ExecutionState.PAUSED]:
            self._stop_event.set()
            self._pause_event.set()  # Unblock thread if paused so it can exit
            self.progress.state = ExecutionState.STOPPED
            self.log("Automation execution stopped by user.", "warning")
            self._notify_update()
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=3.0)

    def _run_loop(self, config: SchedulerConfig, workflows: Dict[str, Workflow], device: ADBDevice):
        start_time = time.time()
        completed_repetitions_total = 0

        self.progress.total_queue_items = len(config.items)

        try:
            for item_idx, item in enumerate(config.items):
                if self._stop_event.is_set():
                    break

                self.progress.current_queue_index = item_idx + 1
                wf = workflows.get(item.workflow_id)
                if not wf:
                    self.log(f"Workflow ID '{item.workflow_id}' not found in library. Skipping.", "error")
                    continue

                self.progress.current_workflow_id = wf.id
                self.progress.current_workflow_name = wf.name
                self.progress.total_reps = item.repetitions
                self.progress.total_tasks = len(wf.tasks)

                executor = ActionExecutor(device, wf.randomization, wf.preset)

                self.log(f"Beginning Workflow [{item_idx + 1}/{len(config.items)}]: '{wf.name}' ({item.repetitions} repetition(s), preset={wf.preset.value})", "info")

                for rep in range(1, item.repetitions + 1):
                    if self._stop_event.is_set():
                        break

                    self.progress.current_rep = rep
                    self.log(f"Workflow '{wf.name}' - Repetition {rep}/{item.repetitions}", "info")

                    # Execute each task in the workflow
                    for t_idx, task in enumerate(wf.tasks):
                        # Check pause / stop before each task
                        while not self._pause_event.is_set() and not self._stop_event.is_set():
                            time.sleep(0.3)

                        if self._stop_event.is_set():
                            break

                        # Check time limit
                        elapsed = time.time() - start_time
                        self.progress.elapsed_seconds = round(elapsed, 1)
                        if config.max_execution_duration and elapsed >= config.max_execution_duration:
                            self.log(f"Max execution duration reached ({config.max_execution_duration}s). Stopping.", "warning")
                            self._stop_event.set()
                            break

                        # Verify device connectivity
                        if not device.is_connected():
                            self.log(f"Device disconnected: {device.serial}! Pausing automation.", "error")
                            self.progress.state = ExecutionState.PAUSED
                            self.progress.error_message = f"Device {device.serial} disconnected"
                            self._pause_event.clear()
                            self._notify_update()
                            while not self._pause_event.is_set() and not self._stop_event.is_set():
                                time.sleep(1.0)
                            if self._stop_event.is_set():
                                break

                        self.progress.current_task_index = t_idx + 1
                        self.progress.current_task_name = task.name
                        self._notify_update()

                        # Execute action
                        success = executor.execute_action(
                            task,
                            logger=lambda msg, lvl: self.log(msg, lvl, wf.id, task.name),
                            should_stop=lambda: self._stop_event.is_set()
                        )

                        if not success and task.on_failure == "abort":
                            self.log(f"Workflow '{wf.name}' aborted due to task failure.", "error")
                            break

                    completed_repetitions_total += 1

                    # Cooldown check
                    if config.cooldown_interval > 0 and (completed_repetitions_total % config.cooldown_interval == 0):
                        if rep < item.repetitions or item_idx < (len(config.items) - 1):
                            self.log(f"Scheduled cooldown triggered: resting for {config.cooldown_duration:.1f}s...", "info")
                            time.sleep(config.cooldown_duration)

                    # Inter-repetition delay
                    if rep < item.repetitions and not self._stop_event.is_set():
                        self.log(f"Waiting {config.inter_repetition_delay:.1f}s before next repetition...", "info")
                        time.sleep(config.inter_repetition_delay)

                # Inter-workflow delay
                if item_idx < (len(config.items) - 1) and not self._stop_event.is_set():
                    self.log(f"Workflow '{wf.name}' completed. Waiting {config.inter_workflow_delay:.1f}s before next workflow...", "info")
                    time.sleep(config.inter_workflow_delay)

            total_elapsed = round(time.time() - start_time, 1)
            self.progress.elapsed_seconds = total_elapsed

            if self._stop_event.is_set() and self.progress.state != ExecutionState.ERROR:
                self.progress.state = ExecutionState.STOPPED
                self.log(f"Automation stopped after {total_elapsed}s.", "warning")
            else:
                self.progress.state = ExecutionState.COMPLETED
                self.log(f"All scheduled workflows finished successfully in {total_elapsed}s!", "success")

        except Exception as e:
            self.progress.state = ExecutionState.ERROR
            self.progress.error_message = str(e)
            self.log(f"Automation execution halted due to error: {e}", "error")
        finally:
            self._notify_update()
