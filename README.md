# mojo-cityhash

`mojo-cityhash` is a from-source Mojo implementation of Google's CityHash
family with a Python API compatible with the public API of
[`python-cityhash`](https://github.com/escherba/python-cityhash). The hash
kernels are Mojo; Python only validates buffers, loads the shared library, and
crosses a small ctypes boundary.

CityHash is a fast, non-cryptographic hash. Do not use it for passwords,
signatures, authentication, or adversarially controlled hash tables.

## Coverage

The port covers every function exported by `python-cityhash 0.4.10`:

- `CityHash32(data)`
- `CityHash64(data)`
- `CityHash64WithSeed(data, seed=0)`
- `CityHash64WithSeeds(data, seed0=0, seed1=0)`
- `CityHash128(data)`
- `CityHash128WithSeed(data, seed=0)`

Strings, bytes, bytearrays, memoryviews, and C-contiguous buffer objects are
accepted. Strings use UTF-8, matching upstream. Return values and 128-bit seed
packing match the upstream Python package.

The CRC-accelerated functions from Google's C++ headers are not covered because
they are not exposed by the target Python package. There is no streaming API:
CityHash itself is a family of one-shot hash functions. This package is also
not a C++ ABI replacement.

## Install

This repository currently supports source-tree use on Linux x86-64; it does
not publish a prebuilt wheel or provide a C++ ABI. The checked-in Pixi
environment pins the Mojo compiler used by the port and installs
`python-cityhash` only as the test oracle.

```bash
git clone https://github.com/lee101/mojo-cityhash.git
cd mojo-cityhash
pixi install
pixi run build
pixi run test
```

The build task compiles the single Mojo unit to
`dist/libmojo-cityhash.so`. Activating the Pixi environment also adds `python/`
to `PYTHONPATH`.

## Usage

```python
import cityhash

assert cityhash.CityHash64(b"hello") == 13009744463427800296
assert cityhash.CityHash32("hello") == 2039911270

seeded = cityhash.CityHash128WithSeed(
    b"cityhash in Mojo",
    0x0123456789ABCDEFFEDCBA9876543210,
)
print(seeded)
```

Run the example through the project environment:

```bash
pixi run python examples/quickstart.py
```

## Benchmarks

Measured with `pixi run bench` on an Intel Xeon E5-2697 v4 at 2.30 GHz,
Linux x86-64, Python 3.13.14. Times are best per-call wall times from five
trials after adaptive batching. `upstream / Mojo` is greater than 1 only when
Mojo is faster.

| Function | Input | Mojo | upstream | upstream / Mojo |
|---|---:|---:|---:|---:|
| `CityHash64` | small-key latency | 1.62 µs | 0.26 µs | 0.16x |
| `CityHash64` | 4 KiB | 3.87 µs | 0.56 µs | 0.15x |
| `CityHash64` | 1 MiB | 99.26 µs | 135.56 µs | 1.37x |
| `CityHash32` | 1 MiB | 340.72 µs | 311.12 µs | 0.91x |
| `CityHash128` | 1 MiB | 83.17 µs | 81.64 µs | 0.98x |
| `CityHash64WithSeeds` | 1 MiB, seeded | 108.93 µs | 101.13 µs | 0.93x |

These are the direct results of the final `pixi run bench`. Mojo was faster in
one listed case and slower in the other five in this run. The fixed
Python-to-ctypes boundary is especially visible on small keys. The benchmark
checks parity before timing each case. No parallel, SIMD, or GPU path is
provided.

## How it works

The algorithms in `src/cityhash.mojo` follow the original CityHash operations:
little-endian loads, fixed-width wrapping arithmetic, intrinsic bit rotates,
weak 32-byte hashes, and the length-specialized mixing paths. The 32-bit block
loop is unrolled two blocks at a time with an odd-block remainder. Bytes are
assembled explicitly so unaligned input is safe; optimized builds fold those
assemblies into native unaligned scalar loads.

Python obtains a pointer to a contiguous input buffer and passes its address and
byte length as two signed 64-bit values. The exported Mojo functions reconstruct an
`UnsafePointer[UInt8, AnyOrigin[mut=True]]` internally. Scalar 32- and 64-bit
results return directly through the C ABI. A 128-bit result is written into a
reusable, thread-local two-element `uint64` array and combined into a Python
integer in the same lane order as `python-cityhash`. Exported function handles
are cached, and the bytes fast path passes the existing immutable buffer
directly. Mutable and generic buffers remain exported for the duration of the
call, preventing a resize from invalidating the native pointer. Empty generic
buffers use a non-null sentinel. No input data is copied for bytes, bytearrays,
or contiguous buffer objects; their raw bytes are hashed regardless of dtype.

The tests compare every function with the installed upstream extension across
all short-input and block-loop boundaries, seeded extremes, fixed regression
vectors, buffer types, and a randomized 1,000,003-byte payload.
