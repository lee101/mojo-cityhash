"""Benchmark Mojo CityHash against python-cityhash on identical byte strings."""

from __future__ import annotations

import math
import os
import platform
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYTHON_DIR = os.path.join(ROOT, "python")

sys.path = [
    path
    for path in sys.path
    if os.path.realpath(path or os.getcwd()) != os.path.realpath(PYTHON_DIR)
]
import cityhash as upstream

del sys.modules["cityhash"]
sys.path.insert(0, PYTHON_DIR)
import cityhash as mojo_cityhash


def time_call(function, minimum_seconds=0.15, trials=5):
    loops = 1
    while True:
        start = time.perf_counter()
        for _ in range(loops):
            function()
        elapsed = time.perf_counter() - start
        if elapsed >= minimum_seconds:
            break
        loops *= max(2, int(minimum_seconds / max(elapsed, 1e-9)))
    best = math.inf
    for _ in range(trials):
        start = time.perf_counter()
        for _ in range(loops):
            function()
        best = min(best, (time.perf_counter() - start) / loops)
    return best


def machine() -> str:
    cpu = "unknown CPU"
    try:
        with open("/proc/cpuinfo", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("model name"):
                    cpu = line.split(":", 1)[1].strip()
                    break
    except OSError:
        pass
    return f"{cpu}; {platform.system()} {platform.machine()}; Python {platform.python_version()}"


def main() -> None:
    cases = [
        ("CityHash64", 64, (), "small-key latency"),
        ("CityHash64", 4 * 1024, (), "4 KiB"),
        ("CityHash64", 1024 * 1024, (), "1 MiB"),
        ("CityHash32", 1024 * 1024, (), "1 MiB"),
        ("CityHash128", 1024 * 1024, (), "1 MiB"),
        (
            "CityHash64WithSeeds",
            1024 * 1024,
            (0x0123456789ABCDEF, 0xFEDCBA9876543210),
            "1 MiB, seeded",
        ),
    ]
    print(f"Machine: {machine()}")
    print()
    print("| Function | Input | Mojo | upstream | upstream / Mojo |")
    print("|---|---:|---:|---:|---:|")
    for name, size, seeds, label in cases:
        data = bytes((i * 37 + 11) & 255 for i in range(size))
        ours = getattr(mojo_cityhash, name)
        reference = getattr(upstream, name)
        assert ours(data, *seeds) == reference(data, *seeds)
        ours(data, *seeds)
        mojo_seconds = time_call(lambda: ours(data, *seeds))
        upstream_seconds = time_call(lambda: reference(data, *seeds))
        ratio = upstream_seconds / mojo_seconds
        print(
            f"| `{name}` | {label} | {mojo_seconds * 1e6:.2f} µs | "
            f"{upstream_seconds * 1e6:.2f} µs | {ratio:.2f}x |"
        )


if __name__ == "__main__":
    main()
