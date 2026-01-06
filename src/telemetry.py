from __future__ import annotations

import json
import os
import platform
import socket
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Generator, Optional

import psutil


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_int(v: Any, default: int) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _env_bool(key: str, default: bool = True) -> bool:
    v = os.getenv(key)
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass
class Span:
    name: str
    ts_start_utc: str
    ts_end_utc: Optional[str] = None
    duration_s: Optional[float] = None
    meta: Dict[str, Any] = field(default_factory=dict)
    resources: Dict[str, Any] = field(default_factory=dict)


class TelemetryRecorder:
    """
    Minimal, reusable process-level telemetry recorder.

    Captures:
    - wall-clock duration (run + spans)
    - process RSS start/end + sampled peak
    - CPU user/system time (end - start)
    - optional progress events (append-only list)

    Writes a single JSON per run under TELEMETRY_DIR/<step>/run_<timestamp>.json
    """

    def __init__(
        self,
        step: str,
        out_dir: Optional[Path] = None,
        enabled: Optional[bool] = None,
        sample_interval_s: float = 0.25,
    ) -> None:
        self.step = step
        self.enabled = _env_bool("TELEMETRY_ENABLED", True) if enabled is None else enabled
        self.sample_interval_s = sample_interval_s

        base_dir = Path(os.getenv("TELEMETRY_DIR", "telemetry")) if out_dir is None else out_dir
        self.step_dir = base_dir / step

        self.run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ")
        self.ts_start_utc: Optional[str] = None
        self.ts_end_utc: Optional[str] = None
        self.duration_s: Optional[float] = None

        self._proc = psutil.Process(os.getpid())
        self._cpu_start: Optional[psutil._common.pcputimes] = None
        self._rss_start: Optional[int] = None
        self._rss_peak: int = 0

        self._sampler_stop = threading.Event()
        self._sampler_thread: Optional[threading.Thread] = None

        self.spans: list[Span] = []
        self.events: list[Dict[str, Any]] = []

        self.inputs: Dict[str, Any] = {}
        self.outputs: Dict[str, Any] = {}
        self.extra: Dict[str, Any] = {}

        self._t0: Optional[float] = None

    def start(self, inputs: Optional[Dict[str, Any]] = None, extra: Optional[Dict[str, Any]] = None) -> None:
        if not self.enabled:
            return

        self.step_dir.mkdir(parents=True, exist_ok=True)
        self.ts_start_utc = _utc_now_iso()
        self._t0 = time.perf_counter()

        self._cpu_start = self._proc.cpu_times()
        self._rss_start = self._proc.memory_info().rss
        self._rss_peak = int(self._rss_start or 0)

        if inputs:
            self.inputs.update(inputs)
        if extra:
            self.extra.update(extra)

        self._start_sampler()

    def _start_sampler(self) -> None:
        def _loop() -> None:
            while not self._sampler_stop.is_set():
                try:
                    rss = self._proc.memory_info().rss
                    if rss > self._rss_peak:
                        self._rss_peak = rss
                except Exception:
                    # if process info is temporarily unavailable, skip
                    pass
                time.sleep(self.sample_interval_s)

        self._sampler_stop.clear()
        self._sampler_thread = threading.Thread(target=_loop, name="telemetry-sampler", daemon=True)
        self._sampler_thread.start()

    def event(self, name: str, **fields: Any) -> None:
        if not self.enabled:
            return
        self.events.append({"ts_utc": _utc_now_iso(), "name": name, **fields})

    @contextmanager
    def span(self, name: str, **meta: Any) -> Generator[None, None, None]:
        if not self.enabled:
            yield
            return

        s = Span(name=name, ts_start_utc=_utc_now_iso(), meta=dict(meta))
        t0 = time.perf_counter()
        rss0 = None
        try:
            rss0 = self._proc.memory_info().rss
        except Exception:
            pass

        try:
            yield
        finally:
            t1 = time.perf_counter()
            s.ts_end_utc = _utc_now_iso()
            s.duration_s = t1 - t0
            try:
                rss1 = self._proc.memory_info().rss
            except Exception:
                rss1 = None
            s.resources = {
                "rss_start_bytes": rss0,
                "rss_end_bytes": rss1,
            }
            self.spans.append(s)

    def finalize(
        self,
        outputs: Optional[Dict[str, Any]] = None,
        inputs: Optional[Dict[str, Any]] = None,
        extra: Optional[Dict[str, Any]] = None,
        git_commit: Optional[str] = None,
    ) -> Optional[Path]:
        if not self.enabled:
            return None

        if inputs:
            self.inputs.update(inputs)
        if outputs:
            self.outputs.update(outputs)
        if extra:
            self.extra.update(extra)

        self._sampler_stop.set()
        if self._sampler_thread and self._sampler_thread.is_alive():
            self._sampler_thread.join(timeout=2.0)

        self.ts_end_utc = _utc_now_iso()
        t1 = time.perf_counter()
        self.duration_s = (t1 - self._t0) if self._t0 is not None else None

        cpu_end = self._proc.cpu_times()
        rss_end = None
        try:
            rss_end = self._proc.memory_info().rss
        except Exception:
            pass

        cpu_user_s = None
        cpu_system_s = None
        if self._cpu_start is not None:
            cpu_user_s = cpu_end.user - self._cpu_start.user
            cpu_system_s = cpu_end.system - self._cpu_start.system

        payload: Dict[str, Any] = {
            "run_id": self.run_id,
            "step": self.step,
            "ts_start_utc": self.ts_start_utc,
            "ts_end_utc": self.ts_end_utc,
            "duration_s": self.duration_s,
            "host": {
                "hostname": socket.gethostname(),
                "platform": platform.platform(),
                "machine": platform.machine(),
                "python": platform.python_version(),
            },
            "git_commit": git_commit,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "resources": {
                "rss_start_bytes": self._rss_start,
                "rss_end_bytes": rss_end,
                "rss_peak_bytes": self._rss_peak,
                "cpu_user_s": cpu_user_s,
                "cpu_system_s": cpu_system_s,
            },
            "spans": [s.__dict__ for s in self.spans],
            "events": self.events,
            "extra": self.extra,
        }

        out = self.step_dir / f"run_{self.run_id}.json"
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return out
