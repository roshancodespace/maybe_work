from __future__ import annotations
import subprocess
import re
import io
import time
import random
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional, Tuple
from PIL import Image
from app.models import DeviceStatus

KEY_CODES = {
    "BACK": 4,
    "HOME": 3,
    "ENTER": 66,
    "TAB": 61,
    "ESCAPE": 111,
    "APP_SWITCH": 187,
    "SEARCH": 84,
    "VOLUME_UP": 24,
    "VOLUME_DOWN": 25,
}

class ADBDevice:
    def __init__(self, serial: str):
        self.serial = serial
        self._width: Optional[int] = None
        self._height: Optional[int] = None

    def execute_adb(self, cmd: List[str], timeout: float = 12.0) -> str:
        full_cmd = ["adb", "-s", self.serial] + cmd
        try:
            res = subprocess.run(
                full_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout,
                check=False
            )
            if res.returncode != 0:
                err_msg = res.stderr.strip() or f"ADB command exited with code {res.returncode}"
                raise RuntimeError(err_msg)
            return res.stdout.strip()
        except subprocess.TimeoutExpired:
            raise TimeoutError(f"ADB command timed out after {timeout}s: {' '.join(full_cmd)}")
        except FileNotFoundError:
            raise RuntimeError("ADB binary not found on host system.")

    def execute_adb_bytes(self, cmd: List[str], timeout: float = 15.0) -> bytes:
        full_cmd = ["adb", "-s", self.serial] + cmd
        try:
            res = subprocess.run(
                full_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
                check=False
            )
            if res.returncode != 0:
                raise RuntimeError(res.stderr.decode("utf-8", errors="ignore").strip() or f"Code {res.returncode}")
            return res.stdout
        except subprocess.TimeoutExpired:
            raise TimeoutError(f"ADB bytes command timed out: {' '.join(full_cmd)}")

    def is_connected(self) -> bool:
        try:
            out = self.execute_adb(["get-state"], timeout=3.0)
            return "device" in out
        except Exception:
            return False

    def get_screen_size(self) -> Tuple[int, int]:
        if self._width and self._height:
            return self._width, self._height
        try:
            out = self.execute_adb(["shell", "wm", "size"], timeout=4.0)
            # Physical size: 1080x2408 or Override size: ...
            match = re.search(r"(\d+)x(\d+)", out)
            if match:
                self._width = int(match.group(1))
                self._height = int(match.group(2))
                return self._width, self._height
        except Exception:
            pass
        return 1080, 2400

    def get_battery_level(self) -> Optional[int]:
        try:
            out = self.execute_adb(["shell", "dumpsys", "battery"], timeout=4.0)
            m = re.search(r"level:\s*(\d+)", out)
            if m:
                return int(m.group(1))
        except Exception:
            pass
        return None

    def get_model(self) -> str:
        try:
            return self.execute_adb(["shell", "getprop", "ro.product.model"], timeout=4.0)
        except Exception:
            return "Unknown"

    def get_status(self) -> DeviceStatus:
        w, h = self.get_screen_size()
        model = self.get_model()
        battery = self.get_battery_level()
        connected = self.is_connected()
        transport = "wifi" if ":" in self.serial else "usb"
        return DeviceStatus(
            serial=self.serial,
            model=model,
            connected=connected,
            width=w,
            height=h,
            battery_level=battery,
            transport_type=transport
        )

    def tap(self, x: float, y: float):
        w, h = self.get_screen_size()
        # Support normalized coordinates (0.0 - 1.0)
        if 0.0 <= x <= 1.0 and 0.0 <= y <= 1.0:
            px = int(x * w)
            py = int(y * h)
        else:
            px = int(x)
            py = int(y)
        self.execute_adb(["shell", "input", "tap", str(px), str(py)])

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300):
        self.execute_adb(["shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(max(50, duration_ms))])

    def human_scroll(
        self,
        direction: str = "down",
        distance_pct: float = 0.45,
        duration_ms: int = 300,
        lateral_wiggle: bool = True
    ):
        w, h = self.get_screen_size()
        # Stay comfortably in central vertical area (avoid status bar and nav bar)
        mid_x = w // 2 + random.randint(-40, 40)
        start_y = int(h * 0.75) if direction == "down" else int(h * 0.35)
        scroll_dist = int(h * max(0.1, min(0.8, distance_pct)))
        end_y = start_y - scroll_dist if direction == "down" else start_y + scroll_dist

        # Ensure bounds stay inside screen
        start_y = max(int(h * 0.15), min(int(h * 0.85), start_y))
        end_y = max(int(h * 0.15), min(int(h * 0.85), end_y))

        end_x = mid_x + (random.randint(-25, 25) if lateral_wiggle else 0)
        jitter_duration = max(150, duration_ms + random.randint(-30, 40))

        self.swipe(mid_x, start_y, end_x, end_y, jitter_duration)

    def wiggle(self, duration_ms: int = 250):
        """Slight human-like micro scroll adjustment (e.g. read and re-adjust viewport)."""
        w, h = self.get_screen_size()
        mid_x = w // 2 + random.randint(-30, 30)
        # Small reverse nudge
        y_start = int(h * 0.50) + random.randint(-50, 50)
        delta = random.randint(120, 240) * random.choice([1, -1])
        y_end = y_start + delta
        self.swipe(mid_x, y_start, mid_x + random.randint(-15, 15), y_end, duration_ms)

    def press_key(self, key: str | int):
        if isinstance(key, str):
            code = KEY_CODES.get(key.upper(), key)
        else:
            code = key
        self.execute_adb(["shell", "input", "keyevent", str(code)])

    def enter_text(self, text: str, press_enter: bool = False):
        # Escape spaces as %s and escape quotes/special shell chars
        escaped = text.replace(" ", "%s").replace("&", "\\&").replace("'", "\\'").replace('"', '\\"')
        self.execute_adb(["shell", "input", "text", escaped])
        if press_enter:
            time.sleep(0.3)
            self.press_key("ENTER")

    def open_url(self, url: str):
        # Use Android standard VIEW intent
        self.execute_adb(["shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", f'"{url}"'])

    def launch_app(self, package_name: str):
        # Try launcher monkey first, fall back to am start
        try:
            self.execute_adb(["shell", "monkey", "-p", package_name, "-c", "android.intent.category.LAUNCHER", "1"])
        except Exception:
            self.execute_adb(["shell", "am", "start", "-n", package_name])

    def capture_screenshot_bytes(self, max_width: int = 640) -> bytes:
        # Fetch PNG from device
        raw_png = self.execute_adb_bytes(["exec-out", "screencap", "-p"], timeout=10.0)
        if not raw_png:
            raise RuntimeError("Empty screenshot data received from device.")

        # Optimize/resize for fast live preview if max_width is given
        if max_width:
            try:
                img = Image.open(io.BytesIO(raw_png))
                if img.width > max_width:
                    ratio = max_width / float(img.width)
                    new_height = int(img.height * ratio)
                    img = img.resize((max_width, new_height), Image.Resampling.BILINEAR)
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=75)
                return buf.getvalue()
            except Exception:
                pass
        return raw_png

    def dump_ui_elements(self) -> List[Dict[str, Any]]:
        # Run uiautomator dump on device
        try:
            self.execute_adb(["shell", "uiautomator", "dump", "/sdcard/window_dump.xml"], timeout=8.0)
            xml_data = self.execute_adb(["shell", "cat", "/sdcard/window_dump.xml"], timeout=6.0)
        except Exception as e:
            return []

        elements = []
        try:
            root = ET.fromstring(xml_data)
            for node in root.iter("node"):
                t = node.attrib.get("text", "").strip()
                c = node.attrib.get("content-desc", "").strip()
                res_id = node.attrib.get("resource-id", "").strip()
                cls = node.attrib.get("class", "").strip()
                b = node.attrib.get("bounds", "")
                if t or c or res_id:
                    m = re.findall(r"\d+", b)
                    if len(m) == 4:
                        x1, y1, x2, y2 = map(int, m)
                        cx = (x1 + x2) // 2
                        cy = (y1 + y2) // 2
                        w = x2 - x1
                        h = y2 - y1
                        elements.append({
                            "text": t,
                            "desc": c,
                            "id": res_id,
                            "class": cls,
                            "bounds": [x1, y1, x2, y2],
                            "center": (cx, cy),
                            "width": w,
                            "height": h,
                            "visible": (cx > 0 and cy > 0 and w > 0 and h > 0)
                        })
        except Exception:
            pass
        return elements

    def find_element(
        self,
        query: str,
        match_by: str = "text",
        exact: bool = False,
        screen_bound_check: bool = True
    ) -> Optional[Dict[str, Any]]:
        elements = self.dump_ui_elements()
        q = query.strip().lower()
        w, h = self.get_screen_size()

        candidates = []
        for el in elements:
            if screen_bound_check:
                # Must be reasonably within visible screen bounds
                cx, cy = el["center"]
                if cx <= 0 or cx >= w or cy <= 120 or cy >= (h - 80):
                    continue
                if el["width"] <= 5 or el["height"] <= 5:
                    continue

            val = ""
            if match_by == "text":
                val = el["text"].lower()
            elif match_by == "desc":
                val = el["desc"].lower()
            elif match_by == "id":
                val = el["id"].lower()
            elif match_by == "any":
                val = f"{el['text']} {el['desc']} {el['id']}".lower()

            if exact and val == q:
                candidates.append(el)
            elif not exact and q in val:
                candidates.append(el)

        if candidates:
            # Return top-most candidate on screen
            candidates.sort(key=lambda x: x["center"][1])
            return candidates[0]
        return None

class DeviceManager:
    def __init__(self):
        self.active_serial: Optional[str] = None
        self._devices_cache: Dict[str, ADBDevice] = {}

    def get_adb_device(self, serial: str) -> ADBDevice:
        if serial not in self._devices_cache:
            self._devices_cache[serial] = ADBDevice(serial)
        return self._devices_cache[serial]

    def list_connected_serials(self) -> List[Dict[str, str]]:
        try:
            res = subprocess.run(
                ["adb", "devices", "-l"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5.0,
                check=False
            )
            devices = []
            for line in res.stdout.splitlines():
                line = line.strip()
                if not line or line.startswith("List of devices"):
                    continue
                parts = line.split()
                if len(parts) >= 2 and parts[1] == "device":
                    serial = parts[0]
                    model = "Device"
                    for p in parts[2:]:
                        if p.startswith("model:"):
                            model = p.split(":")[1]
                    devices.append({"serial": serial, "model": model})
            return devices
        except Exception:
            return []

    def get_active_device(self) -> Optional[ADBDevice]:
        connected = self.list_connected_serials()
        if not connected:
            self.active_serial = None
            return None

        # Check if currently active serial is still in list
        serials = [d["serial"] for d in connected]
        if self.active_serial and self.active_serial in serials:
            return self.get_adb_device(self.active_serial)

        # Prefer USB serials over wifi if both exist, else pick first
        usb_devices = [d["serial"] for d in connected if ":" not in d["serial"]]
        if usb_devices:
            self.active_serial = usb_devices[0]
        else:
            self.active_serial = serials[0]

        return self.get_adb_device(self.active_serial)

    def select_device(self, serial: str) -> bool:
        connected = [d["serial"] for d in self.list_connected_serials()]
        if serial in connected:
            self.active_serial = serial
            return True
        return False
