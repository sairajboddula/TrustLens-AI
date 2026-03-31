"""
KYC Application Launcher

Starts the FastAPI backend as a managed subprocess, waits for it to
become ready, then opens the frontend in the system default browser (or a
bundled web-view when running as a PyInstaller .exe).

Usage:
    python kyc_launcher.py          # development
    ./KYCPlatform.exe               # packaged executable
"""

import os
import signal
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Optional


class KYCLauncher:
    """
    Manages the lifecycle of the KYC backend process and browser window.

    The launcher:
      1. Locates the backend entry-point (main.py / embedded in .exe).
      2. Spawns it as a subprocess on a configurable port.
      3. Polls the /health endpoint until the server is ready.
      4. Opens the user's default browser to the frontend URL.
      5. Keeps running until the user closes the browser tab or sends SIGINT.
      6. Cleans up the backend subprocess on exit.
    """

    def __init__(self, port: int = 8000):
        self.backend_process: Optional[subprocess.Popen] = None
        self.backend_port: int = port
        self.frontend_url: str = f"http://localhost:{self.backend_port}"
        self._shutdown_event = threading.Event()

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    def get_base_path(self) -> Path:
        """
        Return the application base directory.

        When running as a PyInstaller bundle, sys._MEIPASS points to the
        temporary extraction directory.  In development, it is the repo root.
        """
        if getattr(sys, "frozen", False):
            # PyInstaller sets sys._MEIPASS to the temp extraction folder
            return Path(sys._MEIPASS)  # type: ignore[attr-defined]
        # Development: two levels up from this script (desktop/pyinstaller/)
        return Path(__file__).resolve().parent.parent.parent

    def get_backend_entry(self) -> Path:
        """Return the path to main.py (backend entry point)."""
        return self.get_base_path() / "backend" / "main.py"

    def get_python_executable(self) -> str:
        """
        Return the Python interpreter to use for spawning the backend.

        PyInstaller bundles its own python interpreter inside sys.executable,
        but we need the real interpreter for subprocess use.  We try several
        common locations.
        """
        if getattr(sys, "frozen", False):
            # In a frozen bundle, look for a bundled python next to the exe
            bundled_python = Path(sys.executable).parent / "python.exe"
            if bundled_python.exists():
                return str(bundled_python)
            bundled_python = Path(sys.executable).parent / "python"
            if bundled_python.exists():
                return str(bundled_python)
        return sys.executable

    # ------------------------------------------------------------------
    # Backend lifecycle
    # ------------------------------------------------------------------

    def start_backend(self) -> bool:
        """
        Spawn the FastAPI backend as a subprocess.

        Returns True if the process was started, False on error.
        """
        entry_point = self.get_backend_entry()
        if not entry_point.exists():
            print(f"[KYC Launcher] ERROR: Backend entry point not found: {entry_point}")
            return False

        python_exe = self.get_python_executable()
        base_path = self.get_base_path()

        env = os.environ.copy()
        env["PYTHONPATH"] = str(base_path / "backend")
        env["PORT"] = str(self.backend_port)
        env["HOST"] = "127.0.0.1"

        cmd = [
            python_exe,
            "-m",
            "uvicorn",
            "main:app",
            "--host", "127.0.0.1",
            "--port", str(self.backend_port),
            "--log-level", "warning",
        ]

        print(f"[KYC Launcher] Starting backend on port {self.backend_port}...")
        print(f"[KYC Launcher] Command: {' '.join(cmd)}")

        try:
            self.backend_process = subprocess.Popen(
                cmd,
                cwd=str(base_path / "backend"),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                # Windows: prevent CMD window from appearing
                creationflags=(subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0),
            )
            print(f"[KYC Launcher] Backend process started (PID {self.backend_process.pid})")

            # Background thread to drain stderr so the pipe buffer doesn't fill
            def _drain(stream, prefix: str):
                for line in iter(stream.readline, b""):
                    decoded = line.decode("utf-8", errors="replace").rstrip()
                    if decoded:
                        print(f"[Backend {prefix}] {decoded}")
                stream.close()

            threading.Thread(target=_drain, args=(self.backend_process.stdout, "OUT"), daemon=True).start()
            threading.Thread(target=_drain, args=(self.backend_process.stderr, "ERR"), daemon=True).start()

            return True

        except FileNotFoundError:
            print(f"[KYC Launcher] ERROR: Python interpreter not found: {python_exe}")
            return False
        except Exception as exc:
            print(f"[KYC Launcher] ERROR: Failed to start backend: {exc}")
            return False

    def wait_for_backend(self, timeout: int = 30) -> bool:
        """
        Poll GET /health until the backend responds 200 or timeout expires.

        Returns True when the backend is ready, False on timeout.
        """
        import urllib.request
        import urllib.error

        health_url = f"{self.frontend_url}/health"
        deadline = time.monotonic() + timeout
        interval = 0.5  # seconds between polls

        print(f"[KYC Launcher] Waiting for backend to be ready at {health_url} ...")

        while time.monotonic() < deadline:
            # Check if the subprocess died early
            if self.backend_process and self.backend_process.poll() is not None:
                rc = self.backend_process.returncode
                print(f"[KYC Launcher] Backend process exited unexpectedly (rc={rc})")
                return False

            try:
                with urllib.request.urlopen(health_url, timeout=2) as resp:
                    if resp.status == 200:
                        print("[KYC Launcher] Backend is ready.")
                        return True
            except (urllib.error.URLError, OSError):
                pass  # not ready yet

            time.sleep(interval)

        print(f"[KYC Launcher] ERROR: Backend did not become ready within {timeout}s")
        return False

    # ------------------------------------------------------------------
    # Browser
    # ------------------------------------------------------------------

    def open_browser(self) -> None:
        """Open the frontend URL in the system default browser."""
        print(f"[KYC Launcher] Opening browser at {self.frontend_url} ...")
        webbrowser.open(self.frontend_url)

    # ------------------------------------------------------------------
    # Signal handling
    # ------------------------------------------------------------------

    def _register_signal_handlers(self) -> None:
        """Register SIGINT / SIGTERM handlers for clean shutdown."""
        def _handler(signum, frame):
            print(f"\n[KYC Launcher] Received signal {signum}. Shutting down...")
            self._shutdown_event.set()

        signal.signal(signal.SIGINT, _handler)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, _handler)

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    def shutdown(self) -> None:
        """Terminate the backend subprocess and perform clean-up."""
        if self.backend_process is None:
            return

        proc = self.backend_process

        if proc.poll() is None:  # still running
            print(f"[KYC Launcher] Stopping backend process (PID {proc.pid})...")
            try:
                if sys.platform == "win32":
                    proc.terminate()
                else:
                    proc.send_signal(signal.SIGTERM)

                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    print("[KYC Launcher] Backend did not stop in time; killing it.")
                    proc.kill()
                    proc.wait(timeout=3)

            except Exception as exc:
                print(f"[KYC Launcher] WARNING: Error during shutdown: {exc}")

        self.backend_process = None
        print("[KYC Launcher] Backend stopped.")

    # ------------------------------------------------------------------
    # Main entry
    # ------------------------------------------------------------------

    def run(self) -> int:
        """
        Execute the full launcher flow.

        Returns an exit code (0 = success, non-zero = error).
        """
        print("=" * 60)
        print("  KYC Verification Platform")
        print("=" * 60)

        self._register_signal_handlers()

        # 1. Start backend
        if not self.start_backend():
            print("[KYC Launcher] Failed to start backend. Aborting.")
            return 1

        # 2. Wait for backend to be ready
        if not self.wait_for_backend(timeout=30):
            self.shutdown()
            return 1

        # 3. Open browser
        self.open_browser()

        # 4. Wait until the user signals shutdown
        print("[KYC Launcher] Application running. Press Ctrl+C to exit.")
        try:
            while not self._shutdown_event.is_set():
                # Also exit if the backend process dies unexpectedly
                if self.backend_process and self.backend_process.poll() is not None:
                    print("[KYC Launcher] Backend process exited unexpectedly.")
                    break
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            self.shutdown()

        print("[KYC Launcher] Goodbye.")
        return 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="KYC Application Launcher")
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for the backend server (default: 8000)",
    )
    args = parser.parse_args()

    launcher = KYCLauncher(port=args.port)
    sys.exit(launcher.run())
