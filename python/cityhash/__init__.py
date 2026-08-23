"""Python-compatible bindings to the CityHash family implemented in Mojo."""

from __future__ import annotations

import ctypes
import operator
import threading

import numpy as np

from ._lib import U64, lib

__version__ = "0.1.0"
__all__ = [
    "CityHash32",
    "CityHash64",
    "CityHash64WithSeed",
    "CityHash64WithSeeds",
    "CityHash128",
    "CityHash128WithSeed",
]

_U64_MAX = (1 << 64) - 1
_U128_MAX = (1 << 128) - 1
_EMPTY = np.zeros(1, dtype=np.uint8)
_LIB = lib()
_HASH32 = _LIB.mch_cityhash32
_HASH64 = _LIB.mch_cityhash64
_HASH64_WITH_SEED = _LIB.mch_cityhash64_with_seed
_HASH64_WITH_SEEDS = _LIB.mch_cityhash64_with_seeds
_HASH128 = _LIB.mch_cityhash128
_HASH128_WITH_SEED = _LIB.mch_cityhash128_with_seed
_RESULTS = threading.local()


def _type_error(data) -> TypeError:
    return TypeError(
        "Argument 'data' has incorrect type: expected "
        f"['basestring', 'buffer'], got '{type(data).__name__}' instead"
    )


def _buffer(data) -> np.ndarray:
    if isinstance(data, str):
        data = data.encode("utf-8")
    try:
        view = memoryview(data)
    except TypeError:
        raise _type_error(data) from None
    if not view.c_contiguous:
        raise ValueError(f"{type(data).__name__} is not C-contiguous")
    array = np.frombuffer(view, dtype=np.uint8, count=view.nbytes)
    return array if array.size else _EMPTY[:0]


def _address_and_size(data) -> tuple[object, object, int]:
    if isinstance(data, str):
        data = data.encode("utf-8")
    if isinstance(data, bytes):
        return data, data, len(data)
    array = _buffer(data)
    return array, int(array.ctypes.data), int(array.size)


def _uint64(value, name: str) -> int:
    if isinstance(value, float):
        number = int(value)
    else:
        try:
            number = operator.index(value)
        except TypeError:
            raise TypeError(
                f"an integer is required for {name}, got {type(value).__name__}"
            ) from None
    if number < 0:
        raise OverflowError("can't convert negative value to uint64_t")
    if number > _U64_MAX:
        raise OverflowError("Python int too large to convert to C unsigned long")
    return number


def _seed128(seed) -> int:
    if type(seed) is not int:
        raise TypeError(
            f"Argument 'seed' has incorrect type (expected int, got "
            f"{type(seed).__name__})"
        )
    if seed < 0:
        raise OverflowError("can't convert negative value to uint64_t")
    if seed > _U128_MAX:
        raise OverflowError("Python int too large to convert to C unsigned long")
    return seed


def _result128():
    result = getattr(_RESULTS, "result128", None)
    if result is None:
        result = (U64 * 2)()
        _RESULTS.result128 = result
    return result


def CityHash32(data) -> int:
    """Obtain a 32-bit hash from a string, bytes, or contiguous buffer."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    if isinstance(data, bytes):
        return int(_HASH32(data, len(data)))
    array, address, size = _address_and_size(data)
    result = _HASH32(address, size)
    _ = array
    return int(result)


def CityHash64(data) -> int:
    """Obtain a 64-bit hash from a string, bytes, or contiguous buffer."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    if isinstance(data, bytes):
        return int(_HASH64(data, len(data)))
    array, address, size = _address_and_size(data)
    result = _HASH64(address, size)
    _ = array
    return int(result)


def CityHash64WithSeed(data, seed=0) -> int:
    """Obtain a 64-bit hash using one unsigned 64-bit seed."""
    seed = _uint64(seed, "seed")
    if isinstance(data, str):
        data = data.encode("utf-8")
    if isinstance(data, bytes):
        return int(_HASH64_WITH_SEED(data, len(data), seed))
    array, address, size = _address_and_size(data)
    result = _HASH64_WITH_SEED(address, size, seed)
    _ = array
    return int(result)


def CityHash64WithSeeds(data, seed0=0, seed1=0) -> int:
    """Obtain a 64-bit hash using two unsigned 64-bit seeds."""
    seed0 = _uint64(seed0, "seed0")
    seed1 = _uint64(seed1, "seed1")
    if isinstance(data, str):
        data = data.encode("utf-8")
    if isinstance(data, bytes):
        return int(
            _HASH64_WITH_SEEDS(data, len(data), seed0, seed1)
        )
    array, address, size = _address_and_size(data)
    result = _HASH64_WITH_SEEDS(address, size, seed0, seed1)
    _ = array
    return int(result)


def CityHash128(data) -> int:
    """Obtain a 128-bit hash from a string, bytes, or contiguous buffer."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    if isinstance(data, bytes):
        result = _result128()
        _HASH128(
            data,
            len(data),
            ctypes.addressof(result),
        )
        return (result[0] << 64) | result[1]
    array, address, size = _address_and_size(data)
    result = _result128()
    _HASH128(address, size, ctypes.addressof(result))
    _ = array
    return (result[0] << 64) | result[1]


def CityHash128WithSeed(data, seed: int = 0) -> int:
    """Obtain a 128-bit hash using an unsigned 128-bit integer seed."""
    seed = _seed128(seed)
    if isinstance(data, str):
        data = data.encode("utf-8")
    if isinstance(data, bytes):
        result = _result128()
        _HASH128_WITH_SEED(
            data,
            len(data),
            seed >> 64,
            seed & _U64_MAX,
            ctypes.addressof(result),
        )
        return (result[0] << 64) | result[1]
    array, address, size = _address_and_size(data)
    result = _result128()
    _HASH128_WITH_SEED(
        address,
        size,
        seed >> 64,
        seed & _U64_MAX,
        ctypes.addressof(result),
    )
    _ = array
    return (result[0] << 64) | result[1]
