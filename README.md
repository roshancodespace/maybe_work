# Antigravity // Android Automation Engine

A lightweight, futuristic Android automation tool inspired by the Google Antigravity aesthetic. Directly interfaces with physical and virtual Android devices connected via ADB and executes configurable, repeatable multi-step workflows through an ultra-clean, responsive dark web dashboard styled with Montserrat typography and luminous telemetry indicators.

---

## Highlights

- **Google Antigravity Aesthetic**: Minimalist obsidian void theme (`#07080c`), glassmorphic panels, glowing telemetry indicators, and refined **Montserrat** typography.
- **Dedicated Unique Port**: Binds to **`28491`** (`http://127.0.0.1:28491`) out-of-the-box, avoiding common service conflicts.
- **Strictly Idempotent Server Runner**:
  - Automatically identifies and shuts down lingering processes or port listeners before launching.
  - Automatically traps `SIGINT` (Ctrl+C), `SIGTERM`, and `EXIT` to ensure zero orphaned background processes.
  - Provides `./run.sh [start|stop|restart|status]` with optional `--daemon` / `-d` background mode.
- **Infinite Doom Scrollers**:
  1. **Instagram Reels Infinite Doom Scroller**: Launches Instagram (`com.instagram.android`), navigates directly to the Reels feed tab, and continuously swipes through reels with randomized, natural watch times (4–12s) and micro-wiggles.
  2. **GitHub Popular Repos Infinite Doom Scroller**: Opens GitHub top-starred repositories (`stars:>10000`), scrolls through results, taps into repository details, scrolls down into the README/documentation with natural reading pauses, presses `BACK`, and scrolls down to inspect the next repository.
- **Cross-Platform Standalone Binaries**:
  - Single-file executables for **Linux** and **Windows** generated via PyInstaller.
  - Bundles the FastAPI engine, Uvicorn, static web assets, and default workflows into a portable executable.
- **CI/CD Release Automation**:
  - GitHub Actions workflow (`.github/workflows/release.yml`) builds standalone binaries on Ubuntu and Windows runners and publishes GitHub Releases.

---

## Directory Structure

```
.
├── .github/workflows/
│   └── release.yml             # GitHub Actions CI/CD workflow for Linux & Windows
├── app/
│   ├── main.py                 # FastAPI backend, REST endpoints & WebSocket server
│   ├── device.py               # ADB Device Manager & Hardware Controller
│   ├── actions.py              # Action implementations (swipe reel, human scroll, element click)
│   ├── runner.py               # Background thread state machine & scheduler loop
│   ├── models.py               # Pydantic schemas for workflows & devices
│   └── workflows.json          # Bundled doom scroller workflows & default queue
├── static/
│   ├── index.html              # Antigravity HUD Web UI layout
│   ├── style.css               # Futuristic minimal stylesheet (Montserrat & JetBrains Mono)
│   └── app.js                  # Frontend reactive state & WebSocket client
├── run.sh                      # Idempotent server management script
├── build.sh                    # Linux single-file binary builder
├── build_windows.bat           # Windows single-file binary builder (Batch)
├── build_windows.ps1           # Windows single-file binary builder (PowerShell)
├── android_automator.spec      # PyInstaller cross-platform bundle specification
├── requirements.txt            # Python dependencies
├── main_entry.py               # Standalone binary entrypoint
├── test_system.py              # End-to-end integration test suite
└── test_feed_scroller.py       # Standalone test script
```

---

## Quick Start

### 1. Launch with the Idempotent Runner
```bash
./run.sh
```
Or run as a background daemon:
```bash
./run.sh -d
```
Check status:
```bash
./run.sh status
```
Stop:
```bash
./run.sh stop
```

### 2. Access the Dashboard
Open your browser at:
```
http://127.0.0.1:28491
```

---

## Standalone Binary Build

### Linux
```bash
./build.sh
```
Produces `dist/android-automator-linux` (single 26MB executable with all dependencies and static assets bundled).

Run it directly:
```bash
./dist/android-automator-linux --port 28491
```

### Windows
```cmd
build_windows.bat
```
or
```powershell
.\build_windows.ps1
```
Produces `dist\android-automator.exe`.

Run it directly:
```cmd
dist\android-automator.exe --port 28491
```

---

## Automated Verification

Run the integration test suite:
```bash
.venv/bin/python test_system.py
```
