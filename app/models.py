from __future__ import annotations
from enum import Enum
from typing import Dict, Any, List, Optional, Literal, Tuple
from pydantic import BaseModel, Field

class BehaviorPreset(str, Enum):
    CONSISTENT = "consistent"
    NATURAL = "natural"
    EXPLORATORY = "exploratory"

class RandomizationConfig(BaseModel):
    min_delay: float = 1.0
    max_delay: float = 2.5
    min_scroll_pct: float = 0.25
    max_scroll_pct: float = 0.60
    swipe_duration_min: int = 200
    swipe_duration_max: int = 400
    wiggle_enabled: bool = True
    wiggle_chance: float = 0.35
    reading_pause_chance: float = 0.25
    reading_pause_min: float = 2.0
    reading_pause_max: float = 5.0
    explore_result_variation: bool = True

class ActionType(str, Enum):
    OPEN_URL = "open_url"
    LAUNCH_APP = "launch_app"
    SEARCH_TOPIC = "search_topic"
    HUMAN_SCROLL = "human_scroll"
    TAP_ELEMENT = "tap_element"
    TAP_COORDS = "tap_coords"
    ENTER_TEXT = "enter_text"
    PRESS_BACK = "press_back"
    PRESS_KEY = "press_key"
    WAIT_INSPECT = "wait_inspect"
    FIND_AND_CLICK_MORE = "find_and_click_more"
    SWIPE_NEXT_REEL = "swipe_next_reel"
    COOLDOWN = "cooldown"

class TaskAction(BaseModel):
    id: str
    name: str
    action_type: ActionType
    params: Dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    on_failure: Literal["continue", "retry", "abort"] = "continue"
    retries: int = 1

class Workflow(BaseModel):
    id: str
    name: str
    description: str = ""
    preset: BehaviorPreset = BehaviorPreset.NATURAL
    randomization: RandomizationConfig = Field(default_factory=RandomizationConfig)
    tasks: List[TaskAction] = Field(default_factory=list)
    repetitions: int = 1

class ScheduledWorkflowItem(BaseModel):
    workflow_id: str
    repetitions: int = 1

class SchedulerConfig(BaseModel):
    items: List[ScheduledWorkflowItem] = Field(default_factory=list)
    inter_repetition_delay: float = 2.0
    inter_workflow_delay: float = 4.0
    cooldown_interval: int = 5
    cooldown_duration: float = 10.0
    max_execution_duration: Optional[float] = None  # in seconds (e.g. 600)

class ExecutionState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    COMPLETED = "completed"
    ERROR = "error"

class DeviceStatus(BaseModel):
    serial: str
    model: str = "Unknown"
    connected: bool = True
    width: int = 1080
    height: int = 2400
    battery_level: Optional[int] = None
    transport_type: str = "usb"

class ActivityLogEntry(BaseModel):
    timestamp: str
    level: Literal["info", "success", "warning", "error"]
    message: str
    workflow_id: Optional[str] = None
    task_name: Optional[str] = None

class ExecutionProgress(BaseModel):
    state: ExecutionState = ExecutionState.IDLE
    active_device: Optional[str] = None
    current_workflow_id: Optional[str] = None
    current_workflow_name: Optional[str] = None
    current_task_index: int = 0
    total_tasks: int = 0
    current_task_name: Optional[str] = None
    current_rep: int = 0
    total_reps: int = 0
    current_queue_index: int = 0
    total_queue_items: int = 0
    elapsed_seconds: float = 0.0
    error_message: Optional[str] = None
