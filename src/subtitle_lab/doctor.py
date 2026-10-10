"""Non-invasive, read-only discovery; no drivers or model installs."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import os
import platform
import shutil
import subprocess
import sys


def _command(*argv: str, timeout: int = 6) -> dict:
    if not shutil.which(argv[0]):
        return {"available": False}
    try:
        completed = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        return {"available": True, "returncode": completed.returncode,
                "stdout": completed.stdout[-14000:], "stderr": completed.stderr[-1500:]}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"available": True, "error": str(exc)}


def doctor() -> dict:
    result = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "hostname": platform.node(),
        "platform": platform.platform(),
        "python": sys.version,
        "machine": platform.machine(),
        "environment_device_overrides": {
            name: os.environ[name] for name in ("ZE_AFFINITY_MASK", "ONEAPI_DEVICE_SELECTOR", "SYCL_DEVICE_FILTER")
            if name in os.environ
        },
        "tools": {name: _command(name, *args) for name, args in {
            "lspci": ("-nn",), "lscpu": (), "free": ("-h",),
            "sycl-ls": (), "xpu-smi": ("discovery",), "ffmpeg": ("-version",),
            "vainfo": (), "piper": ("--help",),
        }.items()},
    }
    try:
        import torch
        state = {"installed": True, "version": torch.__version__, "xpu_available": bool(torch.xpu.is_available())}
        if state["xpu_available"]:
            devices = []
            for device_idx in range(torch.xpu.device_count()):
                props = torch.xpu.get_device_properties(device_idx)
                devices.append({
                    "xpu_index": device_idx,
                    "name": str(props.name),
                    "total_memory_bytes": getattr(props, "total_memory", None),
                    "is_integrated_gpu": getattr(props, "is_integrated_gpu", None),
                    "driver_version": str(getattr(props, "driver_version", "unknown")),
                    "device_id": str(getattr(props, "device_id", "unknown")),
                })
            state["devices"] = devices
        result["pytorch"] = state
    except ImportError:
        result["pytorch"] = {"installed": False, "note": "XPU probe optional; install into isolated env after baseline"}
    except Exception as exc:
        result["pytorch"] = {"installed": True, "error": f"{type(exc).__name__}: {exc}"}
    return result
