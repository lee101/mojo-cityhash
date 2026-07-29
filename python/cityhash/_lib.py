"""Load the compiled Mojo CityHash library."""

from __future__ import annotations

import ctypes
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
SRC = os.path.join(ROOT, "src", "cityhash.mojo")
LIB = os.environ.get("MOJO_CITYHASH_LIB") or os.path.join(
    ROOT, "dist", "libmojo-cityhash.so"
)

I = ctypes.c_int64
U32 = ctypes.c_uint32
U64 = ctypes.c_uint64

_SIGNATURES = {
    "mch_cityhash32": ([I, I], U32),
    "mch_cityhash64": ([I, I], U64),
    "mch_cityhash64_with_seed": ([I, I, U64], U64),
    "mch_cityhash64_with_seeds": ([I, I, U64, U64], U64),
    "mch_cityhash128": ([I, I, I], None),
    "mch_cityhash128_with_seed": ([I, I, U64, U64, I], None),
}


class BuildError(RuntimeError):
    pass


def build(force: bool = False) -> str:
    """Build the shared library if it is missing or older than its source."""
    if os.environ.get("MOJO_CITYHASH_LIB") and os.path.exists(LIB) and not force:
        return LIB
    if not force and os.path.exists(LIB):
        if os.path.getmtime(LIB) >= os.path.getmtime(SRC):
            return LIB
    script = os.path.join(ROOT, "build", "build.sh")
    try:
        subprocess.run(
            ["bash", script],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=1800,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        stderr = getattr(exc, "stderr", None)
        raise BuildError((stderr or str(exc)).strip()[:4000]) from exc
    if not os.path.exists(LIB):
        raise BuildError(f"build succeeded without producing {LIB}")
    return LIB


_loaded: ctypes.CDLL | None = None


def lib() -> ctypes.CDLL:
    global _loaded
    if _loaded is None:
        _loaded = ctypes.CDLL(build())
        for name, (argtypes, restype) in _SIGNATURES.items():
            function = getattr(_loaded, name)
            function.argtypes = argtypes
            function.restype = restype
    return _loaded
