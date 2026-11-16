import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from urllib.request import urlopen


GIB = 1024 ** 3


def available_memory() -> int:
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) * 1024
    raise RuntimeError("MemAvailable is missing from /proc/meminfo")


def release_model_page_cache(model: Path) -> None:
    released = 0
    for checkpoint in sorted(model.glob("*.safetensors")):
        with checkpoint.open("rb") as source:
            os.posix_fadvise(source.fileno(), 0, 0, os.POSIX_FADV_DONTNEED)
        released += checkpoint.stat().st_size
    print(f"Requested model file page cache release: {released} bytes", flush=True)


def model_ready(url: str) -> bool:
    try:
        with urlopen(url, timeout=1) as response:
            return response.status == 200
    except OSError:
        return False


def main() -> int:
    if len(sys.argv) < 2:
        raise SystemExit("Model directory is required.")
    model = Path(sys.argv[1])
    release_model_page_cache(model)
    minimum_start = int(os.environ.get("LLM_MIN_START_AVAILABLE_GIB", "70")) * GIB
    minimum_running = int(os.environ.get("LLM_MIN_RUNNING_AVAILABLE_GIB", "12")) * GIB
    stopping = False
    child = None

    def signal_child(signum: int) -> None:
        if child is not None and child.poll() is None:
            try:
                os.killpg(child.pid, signum)
            except ProcessLookupError:
                pass

    def stop(signum: int, _frame: object) -> None:
        nonlocal stopping
        stopping = True
        signal_child(signum)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    while not stopping:
        available = available_memory()
        if available >= minimum_start:
            break
        print(f"Waiting for shared RAM: {available / GIB:.1f} GiB available, {minimum_start / GIB:.0f} GiB required", flush=True)
        time.sleep(15)
    if stopping:
        return 0
    child = subprocess.Popen(["vllm", "serve", *sys.argv[1:]], start_new_session=True)
    released_after_load = False
    next_health_check = 0.0
    health_url = os.environ.get("LLM_HEALTH_URL", "http://127.0.0.1:30004/health")
    while child.poll() is None:
        if not stopping and available_memory() < minimum_running:
            print("Shared RAM safety reserve reached; stopping generation LLM", flush=True)
            signal_child(signal.SIGTERM)
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                signal_child(signal.SIGKILL)
                child.wait()
            return 1
        if not stopping and not released_after_load and time.monotonic() >= next_health_check:
            next_health_check = time.monotonic() + 10
            if model_ready(health_url):
                release_model_page_cache(model)
                released_after_load = True
        time.sleep(1)
    return child.returncode if not stopping else 0


if __name__ == "__main__":
    raise SystemExit(main())
