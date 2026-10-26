import sys

if sys.platform == "win32":
    from .process_win import start_daemon, stop_daemon, get_daemon_status
else:
    from .process_posix import start_daemon, stop_daemon, get_daemon_status

__all__ = ["start_daemon", "stop_daemon", "get_daemon_status"]
