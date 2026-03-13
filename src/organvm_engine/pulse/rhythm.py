"""Pulse rhythm — orchestrate a complete proprioceptive cycle.

One pulse cycle:
  1. Run all sensors → emit change events
  2. Compute AMMOI from current state
  3. Store AMMOI snapshot to history
  4. Emit PULSE_HEARTBEAT event
  5. Return AMMOI
"""

from __future__ import annotations

import signal
import sys
import time
from pathlib import Path
from typing import Any

from organvm_engine.pulse.ammoi import AMMOI, _append_history, compute_ammoi


def pulse_once(
    workspace: Path | None = None,
    registry: dict | None = None,
    run_sensors: bool = True,
) -> AMMOI:
    """Execute one full pulse cycle.

    Args:
        workspace: Workspace root. Defaults to ~/Workspace.
        registry: Pre-loaded registry. Loaded from default if None.
        run_sensors: Whether to run ontologia sensors before computing.

    Returns:
        The computed AMMOI snapshot.
    """
    ws = workspace or Path.home() / "Workspace"

    # 1. Run sensors (best-effort)
    sensor_count = 0
    if run_sensors:
        try:
            from ontologia.sensing.scanner import scan_and_emit

            sensor_count = scan_and_emit(ws)
        except ImportError:
            pass
        except Exception:
            pass

    # 2. Compute AMMOI
    ammoi = compute_ammoi(registry=registry, workspace=ws)

    # 3. Store to history
    _append_history(ammoi)

    # 4. Emit heartbeat event
    try:
        from organvm_engine.pulse.emitter import emit_engine_event
        from organvm_engine.pulse.types import AMMOI_COMPUTED, PULSE_HEARTBEAT

        emit_engine_event(
            event_type=AMMOI_COMPUTED,
            source="pulse",
            payload={
                "system_density": ammoi.system_density,
                "total_entities": ammoi.total_entities,
                "active_edges": ammoi.active_edges,
                "pulse_count": ammoi.pulse_count + 1,
            },
        )
        emit_engine_event(
            event_type=PULSE_HEARTBEAT,
            source="pulse",
            payload={
                "sensor_events": sensor_count,
                "density": ammoi.system_density,
            },
        )
    except Exception:
        pass

    return ammoi


def pulse_daemon(
    interval: int = 900,
    workspace: Path | None = None,
    max_cycles: int = 0,
) -> None:
    """Run continuous pulse loop.

    Args:
        interval: Seconds between pulses (default 900 = 15 minutes).
        workspace: Workspace root. Defaults to ~/Workspace.
        max_cycles: Stop after N cycles (0 = unlimited, for production).
    """
    ws = workspace or Path.home() / "Workspace"
    running = True

    def _handle_signal(signum: int, frame: object) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    cycle = 0
    while running:
        cycle += 1
        try:
            ammoi = pulse_once(workspace=ws)
            print(
                f"[pulse] cycle={cycle} density={ammoi.system_density:.1%}"
                f" entities={ammoi.total_entities} edges={ammoi.active_edges}",
                flush=True,
            )
        except Exception as exc:
            print(f"[pulse] cycle={cycle} error: {exc}", file=sys.stderr, flush=True)

        if max_cycles and cycle >= max_cycles:
            break

        # Sleep in 1-second increments for responsive shutdown
        for _ in range(interval):
            if not running:
                break
            time.sleep(1)

    print(f"[pulse] stopped after {cycle} cycles", flush=True)


# ---------------------------------------------------------------------------
# LaunchAgent management
# ---------------------------------------------------------------------------

PLIST_LABEL = "com.4jp.organvm.pulse"
PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{PLIST_LABEL}.plist"
LOG_PATH = Path.home() / "System" / "Logs" / "organvm-pulse.log"
ERR_LOG_PATH = Path.home() / "System" / "Logs" / "organvm-pulse-stderr.log"


def _generate_plist(interval: int = 900) -> str:
    """Generate the LaunchAgent plist XML."""
    # Find the organvm executable — prefer venv, fall back to PATH
    venv_bin = Path.home() / "Workspace" / "meta-organvm" / ".venv" / "bin" / "organvm"
    organvm_bin = str(venv_bin) if venv_bin.exists() else "/opt/homebrew/bin/organvm"

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{PLIST_LABEL}</string>

    <key>ProgramArguments</key>
    <array>
        <string>{organvm_bin}</string>
        <string>pulse</string>
        <string>scan</string>
    </array>

    <key>WorkingDirectory</key>
    <string>/Users/4jp/Workspace/meta-organvm</string>

    <key>StartInterval</key>
    <integer>{interval}</integer>

    <key>ProcessType</key>
    <string>Background</string>

    <key>Nice</key>
    <integer>10</integer>

    <key>LowPriorityIO</key>
    <true/>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/Users/4jp/.local/bin</string>
        <key>HOME</key>
        <string>/Users/4jp</string>
    </dict>

    <key>StandardOutPath</key>
    <string>{LOG_PATH}</string>
    <key>StandardErrorPath</key>
    <string>{ERR_LOG_PATH}</string>
</dict>
</plist>
"""


def install_launchagent(interval: int = 900) -> str:
    """Install the pulse LaunchAgent plist. Returns the plist path."""
    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    PLIST_PATH.write_text(_generate_plist(interval))
    return str(PLIST_PATH)


def uninstall_launchagent() -> bool:
    """Remove the plist file. Returns True if it existed."""
    if PLIST_PATH.exists():
        PLIST_PATH.unlink()
        return True
    return False


def launchagent_status() -> dict[str, Any]:
    """Query LaunchAgent status via launchctl."""
    import subprocess

    result: dict[str, Any] = {
        "installed": PLIST_PATH.exists(),
        "plist_path": str(PLIST_PATH),
        "log_path": str(LOG_PATH),
    }

    if not PLIST_PATH.exists():
        result["running"] = False
        return result

    try:
        proc = subprocess.run(
            ["launchctl", "list", PLIST_LABEL],
            capture_output=True,
            text=True,
            timeout=5,
        )
        result["running"] = proc.returncode == 0
        if proc.returncode == 0:
            for line in proc.stdout.splitlines():
                if "PID" in line and "=" in line:
                    result["pid"] = line.split("=")[-1].strip().rstrip(";")
    except Exception:
        result["running"] = False

    # Last log lines
    if LOG_PATH.exists():
        try:
            lines = LOG_PATH.read_text().strip().splitlines()
            result["last_log"] = lines[-1] if lines else ""
            result["log_lines"] = len(lines)
        except Exception:
            pass

    return result


def pulse_history(days: int = 30, limit: int = 200) -> list[dict[str, Any]]:
    """Read AMMOI history for temporal analysis.

    Args:
        days: Only return snapshots from the last N days.
        limit: Maximum snapshots to return.

    Returns:
        List of AMMOI snapshot dicts, most recent last.
    """
    from datetime import datetime, timedelta, timezone

    from organvm_engine.pulse.ammoi import _read_history

    snapshots = _read_history(limit=limit)
    if days > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        cutoff_str = cutoff.isoformat()
        snapshots = [s for s in snapshots if s.timestamp >= cutoff_str]

    return [s.to_dict() for s in snapshots]
