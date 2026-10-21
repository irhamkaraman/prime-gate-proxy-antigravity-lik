import os
import sys
import json
import time
import subprocess
from typing import Dict, Any, Optional
from ..config import PID_FILE, PROJECT_ROOT, DEFAULT_API_PORT, DEFAULT_UI_PORT

# Windows process creation flags to run hidden in background without console window
DETACHED_FLAGS = 0x08000000 | 0x00000200  # CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP

def get_daemon_status() -> Dict[str, Any]:
    """Check whether daemon is actively running."""
    if not PID_FILE.exists():
        return {"running": False, "pid": None, "api_port": None, "ui_port": None}

    try:
        with open(PID_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        pid = data.get("pid")
        if not pid:
            return {"running": False, "pid": None}

        # Check if process is still alive on Windows
        check = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV"],
            capture_output=True,
            text=True,
            shell=True
        )

        is_alive = str(pid) in check.stdout
        if not is_alive:
            # Stale PID file, clean it
            try:
                PID_FILE.unlink()
            except Exception:
                pass
            return {"running": False, "pid": pid, "stale": True}

        return {
            "running": True,
            "pid": pid,
            "ui_pid": data.get("ui_pid"),
            "api_port": data.get("api_port", DEFAULT_API_PORT),
            "ui_port": data.get("ui_port", DEFAULT_UI_PORT),
            "started_at": data.get("started_at")
        }
    except Exception as e:
        return {"running": False, "error": str(e)}

def start_daemon(api_port: int = DEFAULT_API_PORT, ui_port: int = DEFAULT_UI_PORT) -> Dict[str, Any]:
    """Start the proxy server and web UI as headless background processes on Windows."""
    status = get_daemon_status()
    if status.get("running"):
        return {"success": False, "message": f"Daemon sudah berjalan pada PID {status['pid']}", "status": status}

    log_file = PROJECT_ROOT / "daemon.log"
    log_handle = open(log_file, "a", encoding="utf-8")

    # Command to run python core server in background
    cmd_py = [
        sys.executable,
        "-m", "prime_gate.server",
        "--port", str(api_port),
        "--host", "127.0.0.1"
    ]

    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT) + (os.pathsep + env.get("PYTHONPATH", "") if env.get("PYTHONPATH") else "")

    py_proc = subprocess.Popen(
        cmd_py,
        stdout=log_handle,
        stderr=log_handle,
        cwd=str(PROJECT_ROOT),
        creationflags=DETACHED_FLAGS,
        close_fds=False,
        env=env
    )

    # Command to run Node.js Web UI server in background
    cmd_ui = [
        "node",
        str(PROJECT_ROOT / "ui" / "server.js"),
        "--port", str(ui_port),
        "--api-port", str(api_port)
    ]

    ui_proc = subprocess.Popen(
        cmd_ui,
        stdout=log_handle,
        stderr=log_handle,
        cwd=str(PROJECT_ROOT),
        creationflags=DETACHED_FLAGS,
        close_fds=False,
        shell=True
    )

    # Save state
    state = {
        "pid": py_proc.pid,
        "ui_pid": ui_proc.pid,
        "api_port": api_port,
        "ui_port": ui_port,
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }

    with open(PID_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)

    return {"success": True, "state": state}

def stop_daemon() -> Dict[str, Any]:
    """Stop running background daemon processes."""
    status = get_daemon_status()
    if not status.get("running"):
        if PID_FILE.exists():
            try:
                PID_FILE.unlink()
            except Exception:
                pass
        return {"success": True, "message": "No active daemon process running."}

    pids_to_kill = [status.get("pid"), status.get("ui_pid")]
    killed = []

    for p in pids_to_kill:
        if p:
            try:
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(p)], capture_output=True, shell=True)
                killed.append(p)
            except Exception:
                pass

    if PID_FILE.exists():
        try:
            PID_FILE.unlink()
        except Exception:
            pass

    return {"success": True, "killed_pids": killed}
