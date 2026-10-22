# Device Automator

A local Android automation tool that controls Android devices connected via ADB and executes configurable multi-step workflows through a flat web dashboard built with Montserrat typography.

---

## Highlights

- **Clean Flat Interface**: Clean dark theme with flat material layout, Montserrat typography, and responsive controls.
- **Dedicated Port**: Runs on port `28491` (`http://127.0.0.1:28491`) to prevent port collisions.
- **Idempotent Server Runner**:
  - Checks and shuts down old processes or listeners before starting.
  - Automatically cleans up child processes and PID file upon exit (`Ctrl+C` or `SIGTERM`).
  - Supports `./run.sh [start|stop|restart|status]` and daemon mode (`-d`).
- **Included Workflows**:
  1. **Instagram Reels Infinite Doom Scroller**: Launches Instagram, opens the Reels tab, and scrolls through reels with randomized watch durations (4–12s).
  2. **GitHub Popular Repos Infinite Doom Scroller**: Searches top-starred repos, scrolls the list, opens repo details, reads the README, presses back, and scrolls to the next repo.
- **Standalone Binaries**:
  - Compiles into single-file standalone executables for Linux and Windows using PyInstaller.
- **GitHub Release CI/CD**:
  - Automated release workflow in `.github/workflows/release.yml` building both binaries and attaching them to GitHub Releases.

---

## Directory Structure

```
.
├── .github/workflows/
│   └── release.yml
├── app/
│   ├── main.py
│   ├── device.py
│   ├── actions.py
│   ├── runner.py
│   ├── models.py
│   └── workflows.json
├── static/
│   ├── index.html
│   ├── style.css
│   └── app.js
├── run.sh
├── build.sh
├── build_windows.bat
├── build_windows.ps1
├── android_automator.spec
├── requirements.txt
├── main_entry.py
├── test_system.py
└── test_feed_scroller.py
```

---

## Usage

### 1. Start Server
```bash
./run.sh
```
Or start in the background:
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

### 2. Open Web Dashboard
Navigate in browser to:
```
http://127.0.0.1:28491
```

---

## Build Binaries

### Linux
```bash
./build.sh
```
Binary generated at `dist/android-automator-linux`.

### Windows
```cmd
build_windows.bat
```
Binary generated at `dist\android-automator.exe`.
