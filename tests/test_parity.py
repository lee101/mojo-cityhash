from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from fractions import Fraction
import array
import inspect
import math

import numpy as np
import pytest

import cityhash
from conftest import upstream_cityhash as upstream


# Hash outputs are integers, so parity is exact: tolerance 0 (no rounding allowed).
TOLERANCE = 0


def assert_parity(actual, expected):
    assert type(actual) is int
    assert type(expected) is int
    assert abs(actual - expected) <= TOLERANCE


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


@pytest.mark.parametrize("name", upstream.__all__)
def test_each_public_function_parity_with_tolerance(name):
    ours = getattr(cityhash, name)
    reference = getattr(upstream, name)
    data = b"cityhash parity tolerance check"
    if name == "CityHash64WithSeed":
        ours_data, reference_data = ours(data, 0x0123456789ABCDEF), reference(
            data, 0x0123456789ABCDEF
        )
    elif name == "CityHash64WithSeeds":
        ours_data, reference_data = ours(
            data, 0x0123456789ABCDEF, 0xFEDCBA9876543210
        ), reference(data, 0x0123456789ABCDEF, 0xFEDCBA9876543210)
    elif name == "CityHash128WithSeed":
        ours_data, reference_data = ours(
            data, 0x0123456789ABCDEFFEDCBA9876543210
        ), reference(data, 0x0123456789ABCDEFFEDCBA9876543210)
    else:
        ours_data, reference_data = ours(data), reference(data)
    assert_parity(ours_data, reference_data)


@pytest.mark.parametrize(
    "data",
    [
        b"",
        "",
        bytearray(),
        memoryview(b""),
        np.zeros(0, dtype=np.uint8),
        np.zeros((0, 5), dtype=np.uint8),
        array.array("B"),
    ],
)
def test_empty_input_parity(data):
    for name in ("CityHash32", "CityHash64", "CityHash128"):
        assert_parity(
            getattr(cityhash, name)(data), getattr(upstream, name)(data)
        )
    assert_parity(
        cityhash.CityHash64WithSeed(data, 7), upstream.CityHash64WithSeed(data, 7)
    )
    assert_parity(
        cityhash.CityHash64WithSeeds(data, 7, 8),
        upstream.CityHash64WithSeeds(data, 7, 8),
    )
    assert_parity(
        cityhash.CityHash128WithSeed(data, 7),
        upstream.CityHash128WithSeed(data, 7),
    )


@pytest.mark.parametrize(
    "data",
    [
        b"a",
        b"\x00",
        b"\xff",
        "x",
        bytearray(b"q"),
        memoryview(b"z"),
        np.array([42], dtype=np.uint8),
        np.array(5, dtype=np.uint8),
    ],
)
def test_one_element_input_parity(data):
    for name in ("CityHash32", "CityHash64", "CityHash128"):
        assert_parity(
            getattr(cityhash, name)(data), getattr(upstream, name)(data)
        )
    assert_parity(
        cityhash.CityHash128WithSeed(data, 0),
        upstream.CityHash128WithSeed(data, 0),
    )


@pytest.mark.parametrize(
    "data",
    [
        b"a" * 2,
        b"\x00" * 100,
        b"x" * 100,
        b"ab" * 64,
        b"\xff" * 1000,
        bytearray(b"a" * 64),
        b"a" * 4096,
    ],
)
def test_duplicate_bytes_parity(data):
    for name in ("CityHash32", "CityHash64", "CityHash128"):
        assert_parity(
            getattr(cityhash, name)(data), getattr(upstream, name)(data)
        )
    assert_parity(
        cityhash.CityHash64WithSeed(data, 1),
        upstream.CityHash64WithSeed(data, 1),
    )
    assert_parity(
        cityhash.CityHash64WithSeeds(data, 1, 2),
        upstream.CityHash64WithSeeds(data, 1, 2),
    )
    assert_parity(
        cityhash.CityHash128WithSeed(data, 1),
        upstream.CityHash128WithSeed(data, 1),
    )


@pytest.mark.parametrize(
    "array_data",
    [
        np.array([np.nan, 1.0, -1.0], dtype=np.float32),
        np.array([np.inf, 1.0, -1.0], dtype=np.float32),
        np.array([-np.inf, 1.0, -1.0], dtype=np.float32),
        np.array([np.nan, 1.0, -1.0], dtype=np.float64),
        np.array([np.inf, 1.0, -1.0], dtype=np.float64),
        np.array([-np.inf, 1.0, -1.0], dtype=np.float64),
        np.array([[np.nan, np.inf], [-np.inf, 1.0]], dtype=np.float64),
        np.array([0.0, -0.0], dtype=np.float64),
    ],
)
def test_nan_and_inf_payload_parity(array_data):
    for name in ("CityHash32", "CityHash64", "CityHash128"):
        assert_parity(
            getattr(cityhash, name)(array_data),
            getattr(upstream, name)(array_data),
        )


@pytest.mark.parametrize(
    "data",
    [
        b"\x00\x00\x80\x7f",
        b"\x00\x00\x80\xff",
        b"\x00\x00\xc0\x7f",
        b"\x00\x00\x00\x7f\xf0\xff\xff\xff",
        b"\x00" * 8,
        b"\xff" * 8,
    ],
)
def test_float_bit_pattern_payload_parity(data):
    for name in ("CityHash32", "CityHash64", "CityHash128"):
        assert_parity(
            getattr(cityhash, name)(data), getattr(upstream, name)(data)
        )


@pytest.mark.parametrize(
    "seed",
    [
        0,
        1,
        3.0,
        3.5,
        -0.5,
        True,
        np.uint64(5),
        np.int64(5),
        np.int32(5),
        np.float32(5.0),
        np.float64(3.9),
        np.bool_(True),
        np.bool_(False),
        Decimal(5),
        Decimal("5.5"),
        Fraction(5, 1),
        Fraction(5, 2),
    ],
)
def test_seed_int_conversion_parity(seed):
    assert_parity(
        cityhash.CityHash64WithSeed(b"x", seed),
        upstream.CityHash64WithSeed(b"x", seed),
    )
    assert_parity(
        cityhash.CityHash64WithSeeds(b"x", 0, seed),
        upstream.CityHash64WithSeeds(b"x", 0, seed),
    )


class _IndexOnly:
    def __index__(self):
        return 5


class _IntOnly:
    def __int__(self):
        return 5


class _IntAndIndex:
    def __index__(self):
        return 6

    def __int__(self):
        return 7


def test_seed_index_only_is_rejected_like_upstream():
    with pytest.raises(TypeError, match="an integer is required"):
        cityhash.CityHash64WithSeed(b"x", _IndexOnly())


def test_seed_int_only_matches_upstream():
    assert_parity(
        cityhash.CityHash64WithSeed(b"x", _IntOnly()),
        upstream.CityHash64WithSeed(b"x", _IntOnly()),
    )
    assert_parity(
        cityhash.CityHash64WithSeed(b"x", _IntAndIndex()),
        upstream.CityHash64WithSeed(b"x", _IntAndIndex()),
    )


def test_seed_int_exception_propagates_like_upstream():
    class _RaisingInt:
        def __int__(self):
            raise ValueError("boom-int")

    with pytest.raises(ValueError, match="boom-int"):
        cityhash.CityHash64WithSeed(b"x", _RaisingInt())
    with pytest.raises(ValueError, match="boom-int"):
        upstream.CityHash64WithSeed(b"x", _RaisingInt())


@pytest.mark.parametrize(
    "seed",
    [
        "5",
        b"5",
        None,
        [1],
        5 + 0j,
        float("nan"),
        float("inf"),
        -float("inf"),
    ],
)
def test_seed_rejected_like_upstream(seed):
    with pytest.raises((TypeError, ValueError, OverflowError)) as ours_info:
        cityhash.CityHash64WithSeed(b"x", seed)
    with pytest.raises((TypeError, ValueError, OverflowError)) as upstream_info:
        upstream.CityHash64WithSeed(b"x", seed)
    assert ours_info.value.__class__ is upstream_info.value.__class__


@pytest.mark.parametrize(
    "seed",
    [
        np.float32(np.nan),
        np.float32(np.inf),
        np.float32(-np.inf),
        Decimal("NaN"),
        Decimal("Infinity"),
        Decimal("-Infinity"),
        Fraction(-1, 1),
        Fraction(1 << 70, 1),
    ],
)
def test_seed_nonfinite_and_out_of_range_raise_like_upstream(seed):
    with pytest.raises((ValueError, OverflowError)) as ours_info:
        cityhash.CityHash64WithSeed(b"x", seed)
    with pytest.raises((ValueError, OverflowError)) as upstream_info:
        upstream.CityHash64WithSeed(b"x", seed)
    assert ours_info.value.__class__ is upstream_info.value.__class__


@pytest.mark.parametrize(
    "data",
    [
        np.arange(20, dtype=np.uint8)[::2],
        np.arange(20, dtype=np.uint8)[::-1],
        np.arange(24, dtype=np.uint8).reshape(4, 6).T,
        np.asfortranarray(np.arange(24, dtype=np.uint8).reshape(4, 6)),
        np.arange(24, dtype=np.uint8).reshape(4, 6)[:, ::2],
        np.arange(10, dtype=np.uint16)[::2],
        np.ma.array(np.arange(20, dtype=np.uint8)[::2]),
    ],
)
def test_ndarray_noncontiguous_raises_value_error_like_upstream(data):
    for name in ("CityHash32", "CityHash64", "CityHash128"):
        with pytest.raises(ValueError, match="not C-contiguous") as ours_info:
            getattr(cityhash, name)(data)
        with pytest.raises(ValueError, match="not C-contiguous") as upstream_info:
            getattr(upstream, name)(data)
        assert (
            ours_info.value.__class__ is upstream_info.value.__class__
        )


@pytest.mark.parametrize(
    "data",
    [
        memoryview(b"0123456789")[::2],
        memoryview(b"")[::2],
        memoryview(np.arange(20, dtype=np.uint8)[::2]),
        memoryview(bytearray(b"0123456789"))[::2],
        memoryview(np.arange(24, dtype=np.uint8).reshape(4, 6).T),
    ],
)
def test_memoryview_noncontiguous_raises_buffer_error_like_upstream(data):
    for name in ("CityHash32", "CityHash64", "CityHash128"):
        with pytest.raises(BufferError) as ours_info:
            getattr(cityhash, name)(data)
        with pytest.raises(BufferError) as upstream_info:
            getattr(upstream, name)(data)
        assert (
            ours_info.value.__class__ is upstream_info.value.__class__
        )


@pytest.mark.parametrize(
    "data",
    [
        np.arange(24, dtype=np.uint8).reshape(4, 6),
        np.arange(10, dtype=np.uint8)[2:],
        memoryview(b"0123456789")[2:],
        np.arange(1, dtype=np.uint8)[::2],
        np.array([1, 2, 3], dtype=np.int32),
        np.array([True, False], dtype=bool),
        np.array([1 + 2j], dtype=np.complex128),
        np.array([1, 2], dtype=">u2"),
        array.array("I", [65, 66, 67]),
        "Grüße, 世界",
        b"bytes\x00with\xffbinary",
    ],
)
def test_mismatched_and_multidimensional_shapes_parity(data):
    for name in ("CityHash32", "CityHash64", "CityHash128"):
        assert_parity(
            getattr(cityhash, name)(data), getattr(upstream, name)(data)
        )


@pytest.mark.parametrize("data", [None, 42, 3.14, [1, 2, 3], {"a": 1}, (1, 2)])
def test_unsupported_types_raise_type_error_like_upstream(data):
    with pytest.raises(TypeError) as ours_info:
        cityhash.CityHash64(data)
    with pytest.raises(TypeError) as upstream_info:
        upstream.CityHash64(data)
    assert ours_info.value.__class__ is upstream_info.value.__class__
