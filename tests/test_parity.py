from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import inspect

import numpy as np
import pytest

import cityhash
from conftest import upstream_cityhash as upstream


BOUNDARIES = [
    0,
    1,
    2,
    3,
    4,
    5,
    7,
    8,
    12,
    13,
    16,
    17,
    20,
    24,
    25,
    31,
    32,
    33,
    63,
    64,
    65,
    127,
    128,
    129,
    191,
    239,
    240,
    255,
    256,
    511,
    512,
    1000,
    4096,
]


def payloads():
    rng = np.random.default_rng(20260729)
    for length in BOUNDARIES:
        yield rng.integers(0, 256, length, dtype=np.uint8).tobytes()


def test_public_api_matches_upstream():
    assert cityhash.__all__ == upstream.__all__
    for name in cityhash.__all__:
        assert callable(getattr(cityhash, name))


@pytest.mark.parametrize(
    ("data", "expected32", "expected64", "expected128"),
    [
        (
            b"",
            3696677242,
            11160318154034397263,
            82332263323914296566372529678324145705,
        ),
        (
            b"a",
            1016544589,
            12917804110809363939,
            147003471682549106763909555260705465697,
        ),
        (
            b"hello",
            2039911270,
            13009744463427800296,
            148140867367287440781264987133682512711,
        ),
        (
            bytes(range(256)),
            2824210825,
            894299094737143437,
            243478677264254830179484597597726133141,
        ),
    ],
)
def test_fixed_regression_vectors(data, expected32, expected64, expected128):
    assert cityhash.CityHash32(data) == expected32
    assert cityhash.CityHash64(data) == expected64
    assert cityhash.CityHash128(data) == expected128


@pytest.mark.parametrize("name", ["CityHash32", "CityHash64", "CityHash128"])
def test_unseeded_parity_across_length_boundaries(name):
    ours = getattr(cityhash, name)
    reference = getattr(upstream, name)
    for data in payloads():
        assert ours(data) == reference(data), (name, len(data))


@pytest.mark.parametrize(
    ("name", "seeds"),
    [
        ("CityHash64WithSeed", (0,)),
        ("CityHash64WithSeed", ((1 << 64) - 1,)),
        ("CityHash64WithSeeds", (0x0123456789ABCDEF, 0xFEDCBA9876543210)),
        ("CityHash128WithSeed", (0,)),
        ("CityHash128WithSeed", ((1 << 128) - 1,)),
    ],
)
def test_seeded_parity_across_length_boundaries(name, seeds):
    ours = getattr(cityhash, name)
    reference = getattr(upstream, name)
    for data in payloads():
        assert ours(data, *seeds) == reference(data, *seeds), (name, len(data))


def test_randomized_long_input_parity():
    rng = np.random.default_rng(7)
    data = rng.integers(0, 256, 1_000_003, dtype=np.uint8).tobytes()
    assert cityhash.CityHash32(data) == upstream.CityHash32(data)
    assert cityhash.CityHash64(data) == upstream.CityHash64(data)
    assert cityhash.CityHash128(data) == upstream.CityHash128(data)


@pytest.mark.parametrize("length", [25, 40, 41, 60, 61, 80, 81])
def test_cityhash32_unrolled_loop_and_remainder_parity(length):
    data = bytes((i * 53 + 19) & 255 for i in range(length))
    assert cityhash.CityHash32(data) == upstream.CityHash32(data)


@pytest.mark.parametrize("length", [0, 1, 19, 20, 21, 63, 64, 65, 129])
def test_bytes_fast_path_matches_generic_buffer_path(length):
    data = bytes((i * 29 + 7) & 255 for i in range(length))
    generic = bytearray(data)
    for name in ("CityHash32", "CityHash64", "CityHash128"):
        ours = getattr(cityhash, name)
        reference = getattr(upstream, name)
        assert ours(data) == ours(generic) == reference(data)


def test_cityhash128_thread_local_result_buffer():
    payloads = [bytes([i]) * (127 + i) for i in range(16)]
    expected = [upstream.CityHash128(data) for data in payloads]
    with ThreadPoolExecutor(max_workers=4) as pool:
        actual = list(pool.map(cityhash.CityHash128, payloads))
    assert actual == expected


@pytest.mark.parametrize(
    "data",
    [
        "Grüße, 世界",
        b"bytes\x00with\xffbinary",
        bytearray(range(64)),
        memoryview(b"memory view"),
        np.arange(50, dtype=np.uint16),
        np.arange(24, dtype=np.float32).reshape(4, 6),
    ],
)
def test_supported_input_types_match_upstream(data):
    for name in ("CityHash32", "CityHash64", "CityHash128"):
        assert getattr(cityhash, name)(data) == getattr(upstream, name)(data)


@pytest.mark.parametrize("data", [None, 42, [1, 2, 3], object()])
def test_unsupported_input_types_raise_type_error(data):
    with pytest.raises(TypeError):
        cityhash.CityHash64(data)


def test_non_contiguous_buffer_is_rejected():
    data = np.arange(20, dtype=np.uint8)[::2]
    with pytest.raises(ValueError, match="not C-contiguous"):
        cityhash.CityHash64(data)


def test_bytearray_is_exported_for_the_duration_of_the_ffi_call(monkeypatch):
    data = bytearray(b"resize guard")

    def hash_while_trying_to_resize(address, size):
        assert address
        assert size == len(data)
        with pytest.raises(BufferError):
            data.append(0)
        return 123

    monkeypatch.setattr(cityhash, "_HASH64", hash_while_trying_to_resize)
    assert cityhash.CityHash64(data) == 123


def test_bytes_fast_path_passes_original_buffer_to_ffi(monkeypatch):
    data = b"zero-copy bytes"

    def hash_without_copy(buffer, size):
        assert buffer is data
        assert size == len(data)
        return 123

    monkeypatch.setattr(cityhash, "_HASH64", hash_without_copy)
    assert cityhash.CityHash64(data) == 123


@pytest.mark.parametrize("seed", [-1, 1 << 64])
def test_uint64_seed_range_is_checked(seed):
    with pytest.raises(OverflowError):
        cityhash.CityHash64WithSeed(b"x", seed)


@pytest.mark.parametrize("seed", [-1, 1 << 128])
def test_uint128_seed_range_is_checked(seed):
    with pytest.raises(OverflowError):
        cityhash.CityHash128WithSeed(b"x", seed)


def test_seed_defaults_and_signatures_match_upstream():
    data = b"default seeds"
    assert cityhash.CityHash64WithSeed(data) == upstream.CityHash64WithSeed(data)
    assert cityhash.CityHash64WithSeeds(data) == upstream.CityHash64WithSeeds(data)
    assert cityhash.CityHash128WithSeed(data) == upstream.CityHash128WithSeed(data)
    assert tuple(inspect.signature(cityhash.CityHash64WithSeeds).parameters) == (
        "data",
        "seed0",
        "seed1",
    )
