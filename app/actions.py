from __future__ import annotations
import time
import random
from typing import Dict, Any, Optional, Callable
from app.models import (
    TaskAction,
    ActionType,
    RandomizationConfig,
    BehaviorPreset
)
from app.device import ADBDevice

class ActionExecutor:
    def __init__(self, device: ADBDevice, random_config: RandomizationConfig, preset: BehaviorPreset):
        self.device = device
        self.config = random_config
        self.preset = preset

    def _apply_jitter(self, base_val: float, jitter_pct: float = 0.2) -> float:
        if self.preset == BehaviorPreset.CONSISTENT:
            jitter_pct = 0.08
        elif self.preset == BehaviorPreset.EXPLORATORY:
            jitter_pct = 0.35
        factor = 1.0 + random.uniform(-jitter_pct, jitter_pct)
        return max(0.1, base_val * factor)

    def _sleep_action_delay(self, custom_delay: Optional[float] = None, logger: Optional[Callable[[str, str], None]] = None):
        if custom_delay is not None and custom_delay > 0:
            delay = self._apply_jitter(custom_delay)
        else:
            delay = random.uniform(self.config.min_delay, self.config.max_delay)

        # Occasional reading pause in Natural or Exploratory mode
        if self.preset != BehaviorPreset.CONSISTENT and random.random() < self.config.reading_pause_chance:
            extra_pause = random.uniform(self.config.reading_pause_min, self.config.reading_pause_max)
            delay += extra_pause
            if logger:
                logger(f"Reading pause (+{extra_pause:.1f}s)", "info")

        time.sleep(delay)

    def execute_action(
        self,
        task: TaskAction,
        logger: Callable[[str, str], None],
        should_stop: Callable[[], bool]
    ) -> bool:
        if not task.enabled:
            logger(f"Skipping disabled action: {task.name}", "info")
            return True

        retries = max(1, task.retries if task.on_failure == "retry" else 1)
        last_error = None

        for attempt in range(1, retries + 1):
            if should_stop():
                return False

            try:
                if attempt > 1:
                    logger(f"Retrying action '{task.name}' (attempt {attempt}/{retries})...", "warning")
                    time.sleep(1.0)

                success = self._run_single_action(task, logger, should_stop)
                if success:
                    # Delay after successful action
                    self._sleep_action_delay(task.params.get("delay_after"), logger)
                    return True
                else:
                    last_error = "Action logic returned failure"
            except Exception as e:
                last_error = str(e)
                logger(f"Action '{task.name}' error: {e}", "error")

        if task.on_failure == "abort":
            logger(f"Aborting workflow due to failure in '{task.name}': {last_error}", "error")
            return False
        else:
            logger(f"Action '{task.name}' failed but continuing (on_failure={task.on_failure})", "warning")
            return True

    def _run_single_action(
        self,
        task: TaskAction,
        logger: Callable[[str, str], None],
        should_stop: Callable[[], bool]
    ) -> bool:
        atype = task.action_type
        params = task.params

        if atype == ActionType.OPEN_URL:
            url = params.get("url", "https://github.com/explore")
            logger(f"Opening URL: {url}", "info")
            self.device.open_url(url)
            time.sleep(1.5)
            return True

        elif atype == ActionType.LAUNCH_APP:
            pkg = params.get("package", "com.android.chrome")
            logger(f"Launching application: {pkg}", "info")
            self.device.launch_app(pkg)
            time.sleep(1.5)
            return True

        elif atype == ActionType.SEARCH_TOPIC:
            topic = params.get("topic", "flutter")
            # If search_url_template is provided, use it
            template = params.get("url_template", "https://github.com/search?q={query}&type=repositories")
            if "{query}" in template:
                url = template.replace("{query}", topic)
                logger(f"Navigating to search for '{topic}': {url}", "info")
                self.device.open_url(url)
                time.sleep(2.0)
                return True
            else:
                logger(f"Entering search query: {topic}", "info")
                self.device.enter_text(topic, press_enter=True)
                return True

        elif atype == ActionType.HUMAN_SCROLL:
            direction = params.get("direction", "down")
            scroll_pct = params.get("distance_pct")
            if scroll_pct is None:
                scroll_pct = random.uniform(self.config.min_scroll_pct, self.config.max_scroll_pct)
            else:
                scroll_pct = self._apply_jitter(float(scroll_pct))

            duration = random.randint(self.config.swipe_duration_min, self.config.swipe_duration_max)
            logger(f"Human scroll {direction} (~{int(scroll_pct * 100)}% distance, {duration}ms)", "info")
            self.device.human_scroll(direction=direction, distance_pct=scroll_pct, duration_ms=duration)

            # Check if wiggle should be triggered
            if self.config.wiggle_enabled and (self.preset != BehaviorPreset.CONSISTENT) and random.random() < self.config.wiggle_chance:
                time.sleep(0.4)
                logger("Performing natural viewport wiggle", "info")
                self.device.wiggle()
            return True

        elif atype == ActionType.TAP_ELEMENT:
            query = params.get("query", "")
            match_by = params.get("match_by", "text")  # text, desc, id, any
            exact = params.get("exact", False)
            logger(f"Searching for UI element matching '{query}' ({match_by})...", "info")

            element = self.device.find_element(query, match_by=match_by, exact=exact)
            if element:
                cx, cy = element["center"]
                logger(f"Found element '{element['text'] or element['desc']}' at ({cx}, {cy}). Tapping...", "success")
                self.device.tap(cx, cy)
                return True
            else:
                # Optional fallback coordinates
                fb_x = params.get("fallback_x")
                fb_y = params.get("fallback_y")
                if fb_x is not None and fb_y is not None:
                    logger(f"Element not found. Tapping fallback coordinates ({fb_x}, {fb_y})", "warning")
                    self.device.tap(fb_x, fb_y)
                    return True
                raise RuntimeError(f"UI element matching '{query}' not found on screen.")

        elif atype == ActionType.TAP_COORDS:
            x = float(params.get("x", 0.5))
            y = float(params.get("y", 0.5))
            logger(f"Tapping coordinates ({x}, {y})", "info")
            self.device.tap(x, y)
            return True

        elif atype == ActionType.ENTER_TEXT:
            text = params.get("text", "")
            press_enter = params.get("press_enter", False)
            logger(f"Entering text: '{text}' (enter={press_enter})", "info")
            self.device.enter_text(text, press_enter=press_enter)
            return True

        elif atype == ActionType.PRESS_BACK:
            logger("Pressing BACK button", "info")
            self.device.press_key("BACK")
            return True

        elif atype == ActionType.PRESS_KEY:
            key = params.get("key", "ENTER")
            logger(f"Pressing key: {key}", "info")
            self.device.press_key(key)
            return True

        elif atype == ActionType.WAIT_INSPECT:
            wait_s = params.get("seconds", 2.0)
            adjusted_s = self._apply_jitter(float(wait_s))
            logger(f"Waiting & inspecting screen ({adjusted_s:.1f}s)...", "info")
            time.sleep(adjusted_s)
            return True

        elif atype == ActionType.FIND_AND_CLICK_MORE:
            # User requirement: scroll down, wiggle, and when reaches end it sees big "More" button, clicks it
            max_scrolls = int(params.get("max_scroll_attempts", 8))
            logger(f"Searching for 'More' / 'Load more' button (up to {max_scrolls} scrolls)...", "info")

            for i in range(max_scrolls):
                if should_stop():
                    return False

                # Check if visible More button is already present on screen
                elems = self.device.dump_ui_elements()
                w, h = self.device.get_screen_size()
                more_btn = None
                for el in elems:
                    t = el["text"].strip().lower()
                    d = el["desc"].strip().lower()
                    # Check for "more" or "load more" button
                    if t in ["more", "load more"] or d in ["more", "load more"]:
                        # Ensure it's in the visible vertical range
                        cx, cy = el["center"]
                        if 200 < cy < (h - 100) and el["height"] > 10:
                            more_btn = el
                            break

                if more_btn:
                    cx, cy = more_btn["center"]
                    logger(f"Visible 'More' button found at ({cx}, {cy})! Clicking...", "success")
                    # Micro pause before click
                    time.sleep(0.5)
                    self.device.tap(cx, cy)
                    time.sleep(2.0)
                    return True

                # If not found yet, perform human scroll down with wiggle
                logger(f"Scroll step {i+1}/{max_scrolls} searching for 'More' button...", "info")
                scroll_dist = random.uniform(0.40, 0.65)
                self.device.human_scroll("down", distance_pct=scroll_dist, duration_ms=random.randint(220, 380))
                time.sleep(0.8)
                if self.config.wiggle_enabled and random.random() < 0.4:
                    self.device.wiggle()
                    time.sleep(0.5)

            logger("Could not locate 'More' button within max scroll attempts.", "warning")
            return False

        elif atype == ActionType.SWIPE_NEXT_REEL:
            w, h = self.device.get_screen_size()
            direction = params.get("direction", "up")
            mid_x = w // 2 + random.randint(-30, 30)

            # Upward swipe advances to next reel
            if direction == "up":
                y1 = int(h * 0.78) + random.randint(-30, 30)
                y2 = int(h * 0.22) + random.randint(-30, 30)
            else:
                y1 = int(h * 0.25)
                y2 = int(h * 0.75)

            duration = random.randint(210, 290)
            self.device.swipe(mid_x, y1, mid_x + random.randint(-15, 15), y2, duration)

            watch_sec = float(params.get("watch_seconds", 6.0))
            adjusted_watch = self._apply_jitter(watch_sec)
            logger(f"Swiped to next Reel. Watching for {adjusted_watch:.1f}s...", "info")

            elapsed = 0.0
            while elapsed < adjusted_watch:
                if should_stop():
                    return False
                chunk = min(0.5, adjusted_watch - elapsed)
                time.sleep(chunk)
                elapsed += chunk

            if self.config.wiggle_enabled and random.random() < 0.2:
                self.device.wiggle()

            return True

        elif atype == ActionType.COOLDOWN:
            seconds = float(params.get("seconds", self.config.min_delay * 3))
            logger(f"Cooldown pause for {seconds:.1f}s...", "info")
            time.sleep(seconds)
            return True

        else:
            logger(f"Unknown action type: {atype}", "warning")
            return True
