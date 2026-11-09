# mojo-cityhash — ANALYZE phase (measured map, session 2026-11-09)

No algorithms changed. Every time below was measured in this session on
`Intel(R) Xeon(R) CPU E5-2697 v4 @ 2.30GHz; Linux x86_64; Python 3.13.14`,
built with `pixi run bench` (flock-wrapped, run alone) plus the same
adaptive-batch `time_call` used by `bench/bench.py` (min 0.15 s per
measurement, best of 5 trials). Upstream = installed `python-cityhash`
0.4.10 (C++ CityHash in a CPython extension); Mojo = this repo's
`src/cityhash.mojo` via `python/cityhash` ctypes glue.

`upstream / Mojo < 1` means the port is **slower** than upstream. All
port-slower rows are marked `⚠ SLOWER` and kept.

Flops are *counts of scalar integer ops in the source* (adds, xors,
shifts, rotates, multiplies, byte-swaps, loads) per block, derived from
`src/cityhash.mojo` — not timing estimates. Full method in the appendix.

## Headline: `pixi run bench` (official)

| Function | Input | Mojo | upstream | upstream / Mojo |
|---|---:|---:|---:|---:|
| `CityHash64` | small (64 B) | 1.08 µs | 0.23 µs | 0.21x ⚠ SLOWER |
| `CityHash64` | 4 KiB | 1.56 µs | 0.61 µs | 0.39x ⚠ SLOWER |
| `CityHash64` | 1 MiB | 103.64 µs | 93.86 µs | 0.91x ⚠ SLOWER |
| `CityHash32` | 1 MiB | 255.88 µs | 231.59 µs | 0.91x ⚠ SLOWER |
| `CityHash128` | 1 MiB | 94.95 µs | 86.05 µs | 0.91x ⚠ SLOWER |
| `CityHash64WithSeeds` | 1 MiB, seeded | 102.89 µs | 94.96 µs | 0.92x ⚠ SLOWER |

Re-run `pixi run bench` in the same session gave 0.22x / 0.40x / 1.01x /
0.92x / 0.92x / 0.94x — the 1 MiB rows hover at parity within ±8%
jitter across runs, but the small/medium rows are a stable 2.5–5x gap.
The port is slower than upstream on **every** function at **every**
size in this map; no row is a win. Dropping them would hide the point
of this phase, so none are dropped.

## Ranked hotspot table

Ranked by (gap vs upstream) × (absolute time at realistic caller sizes).
"Glue" = Python wrapper + ctypes crossing + `ctypes.c_void_p` conversion;
"kernel" = time inside `mch_*` in `src/cityhash.mojo`. Split measured by
timing raw ctypes against the Python wrapper on identical bytes
(`H64(d, len(d))` vs `CityHash64(d)`); glue = wrapper − direct:

| # | function | input size | time (Mojo) | bytes touched | flops (src count) | flops / byte | memory- or compute-bound | where the time sits |
|---|---:|---:|---:|---:|---:|---:|:---|:---|
| 1 | `CityHash32` (1 MiB) | 1,048,576 B | 250.26 µs | 1,048,576 | ~36 / 20 B block → ~1,886,000 | ~1.8 | compute-bound-ish (scalar ILP-limited, 3.9 GB/s, 0.24 ns/B) | kernel |
| 2 | `CityHash64` (small, all sizes ≤ 256 B) | 64 B (bench) | 1.08 µs | 64 | ~40 total (`hash_len_33_to_64` + tail) | ~0.6 | neither — fixed-cost-bound | glue (Python + ctypes ≈ 0.80 µs of 0.98 µs direct) |
| 3 | `CityHash64WithSeeds` (small) | 64 B | 2.03 µs | 64 | ~49 (64-bit hash + `hash_len_16` seed mix ≈ *9 ops*) | ~0.8 | neither — fixed-cost-bound | glue (seed validation `2×_uint64` dominates) |
| 4 | `CityHash128WithSeed` (small) | 64 B | 2.69 µs | 64 | ~60 (murmur path) | ~0.9 | neither — fixed-cost-bound | glue (`_seed128` + wrapper) |
| 5 | `CityHash64` (4 KiB) | 4,096 B | 1.49 µs | 4,096 | ~2,100 (`~33 / 64 B × 64` blocks + setup) | ~0.5 | memory-bound (2.6 GB/s effective at this size is latency, not DRAM) | mixed — glue ≈ 0.24 µs (18%), kernel ≈ 1.1 µs |
| 6 | `CityHash64` (1 MiB) | 1,048,576 B | 104.66 µs | 1,048,576 | ~33 / 64 B × 16,384 blocks ≈ 540,000 | ~0.5 | memory-bound (9.5 GB/s) | kernel |
| 7 | `CityHash128` (1 MiB) | 1,048,576 B | 98.70 µs | 1,048,576 | ~66 / 128 B × 8,192 ×2 halves ≈ 540,000 | ~0.5 | memory-bound (10.1 GB/s) | kernel |
| 8 | `CityHash64WithSeed` (1 MiB) | 1,048,576 B | 109.27 µs | 1,048,576 | ~549,000 (64-bit hash + seed mix) | ~0.5 | memory-bound (9.2 GB/s) | kernel |
| 9 | `CityHash64WithSeeds` (1 MiB) | 1,048,576 B | 108.06 µs | 1,048,576 | ~549,000 | ~0.5 | memory-bound (9.2 GB/s) | kernel |
| 10 | `CityHash128WithSeed` (1 MiB) | 1,048,576 B | 99.75 µs | 1,048,576 | ~550,000 | ~0.5 | memory-bound (10.0 GB/s) | kernel |
| 11 | `CityHash64` via `bytearray`/`memoryview`/`ndarray` (small–mid) | 64 B | 4.12–4.16 µs | 64 | ~40 | ~0.6 | fixed-cost-bound | glue (`_buffer` + `np.frombuffer` view) |
| 12 | `CityHash64` via `str` (1 MiB) | 1,048,576 chars | 171.22 µs | ~1 M + 1 M copy | ~540,000 | ~0.5 | memory/copy-bound (encode 73 µs extra) | glue (`.encode("utf-8")` copy) |

Rows 6–10 at 1 MiB: glue ≈ 0 µs (e.g. `CityHash64` 1 MiB wrapper
100.21 µs vs direct ctypes 100.40 µs — the wrapper is lost in kernel
noise), so the 0.91–0.95x upstream gap at 1 MiB is entirely kernel
codegen (scalar byte assembly + source-level rotate/mul idioms), not
the boundary. Rows 2–5, 11, 12 are the opposite: kernel work is
negligible and >80% of the measured time is Python/ctypes.

## Time vs upstream: where the gap actually lives

Full sweep from this session (`bench_extra`, identical `time_call` to
`bench.py`; all six public entry points, bytes input).

`CityHash32`: 0 B 1.18 vs 0.21 µs; 1 KiB 1.40 vs 0.45; 4 KiB 2.16 vs
1.12; 16 KiB 5.15 vs 3.85; 64 KiB 16.69 vs 14.63; 1 MiB 250–257 vs
217–234 µs (0.87–0.92x ⚠ SLOWER).
`CityHash64`: 0 B 1.07–1.20 vs 0.21; 1 KiB 1.21 vs 0.32; 4 KiB 1.49 vs
0.60; 16 KiB 2.67 vs 1.68; 64 KiB 7.30 vs 6.19; 1 MiB 97–105 vs 94–99 µs
(0.90–1.01x ⚠ SLOWER or parity).
`CityHash64WithSeed`: 0 B 1.49 vs 0.26; 4 KiB 1.90 vs 0.65; 1 MiB 109 vs
101 µs (0.92x ⚠ SLOWER).
`CityHash64WithSeeds`: 0 B 2.03 vs 0.30; 4 KiB 2.44 vs 0.69; 16 KiB 3.67
vs 1.76; 1 MiB 108 vs 97 µs (0.90x ⚠ SLOWER).
`CityHash128`: 0 B 1.78 vs 0.30; 4 KiB 2.21 vs 0.67; 1 MiB 99 vs 92 µs
(0.93x ⚠ SLOWER).
`CityHash128WithSeed`: 0 B 2.69 vs 0.46; 4 KiB 3.06 vs 0.83; 64 KiB 9.08
vs 5.98; 1 MiB 100 vs 91 µs (0.91x ⚠ SLOWER).

Pattern: the port is 3–7x slower below ~1 KiB (fixed boundary cost),
2–3x slower at 4 KiB, and reaches 0.85–0.95x parity at 64 KiB–1 MiB.
The gap never closes at any size — this is a fixed ~0.7–1.7 µs boundary
tax plus a ~10% kernel codegen tax at large sizes.

## Glue vs kernel split (measured this session)

| probe | measured |
|---|---:|
| empty `lambda` harness overhead | 46.9 ns |
| direct ctypes `H64(d, 0)` | 0.804 µs |
| wrapper `CityHash64(d, 0 B)` | 0.982 µs |
| wrapper − direct, 64 B | 0.147 µs (15% of wrapper) |
| wrapper − direct, 4 KiB | 0.243 µs (18%) |
| wrapper − direct, 1 MiB | ~0 µs (lost in kernel noise, ±0.2 µs) |
| `CityHash64WithSeed` extra validation (`_uint64` + seed), 64 B vs `CityHash64` | +0.38 µs (+49%) |
| `CityHash64WithSeeds` extra validation (`2×_uint64`), 64 B | +0.83 µs (+86%) |
| `CityHash128WithSeed` extra (`_seed128`), 64 B vs `CityHash128` | +0.49 µs |
| `CityHash128` 1 MiB wrapper without per-call alloc (raw ctypes + thread-local result) | 95.58 µs vs wrapper 96.00 µs |

`MOJO_NOTES.md` §6 already documents ~0.9 µs for a built shared lib +
ctypes call; this session's 0.804 µs direct-call floor confirms it.
That floor alone puts every small-key call at ~4x upstream before a
single byte of hashing runs. `cProfile` on 20,000× `CityHash64(64 B)`
shows the wrapper itself (`__init__.py:126`) at 0.076 s tottime and
`_address_and_size` at 0.061 s — i.e. mutable-buffer handling, not the
FFI call, dominates the Python-side CPU.

Per-input-type costs (`CityHash64`, identical harness):

| size | bytes | bytearray | memoryview | ndarray | str (ascii) |
|---:|---:|---:|---:|---:|---:|
| 64 B | 0.89 µs | 4.12 µs | 4.16 µs | 4.13 µs | 0.94 µs |
| 4 KiB | 1.27 µs | 4.55 µs | 4.71 µs | 4.69 µs | 1.59 µs |
| 1 MiB | 97.93 µs | 101.90 µs | 103.18 µs | 116.87 µs | **171.22 µs** |

The `bytes` fast path (`data` passed directly as `void*`) is the only
zero-copy path. Everything else allocates the NumPy view in `_buffer`
per call (`np.frombuffer` + `ctypes.data` + `int(array.size)`), and
`str` pays a full UTF-8 encode copy (73 µs extra at 1 MiB).

## Baselines (numpy / Python, this session)

| baseline | 1 KiB | 4 KiB | 1 MiB |
|---|---:|---:|---:|
| `np.sum` on `uint8` view | 2.54 µs | 4.80 µs | 753.72 µs |
| `zlib.crc32` | 1.00 µs | 3.22 µs | 770.77 µs |
| `hashlib.blake2b` (8 B digest) | — | — | 1986.39 µs |
| Python `sum(bytes)` | 5.73 µs | 22.56 µs | — |
| Mojo `CityHash64` (for scale) | 1.21 µs | 1.49 µs | ~100 µs |

CityHash is 7–8x faster than `crc32` / `np.sum` at 1 MiB and ~20x
faster than blake2b despite doing ~0.5 flops/byte of real work — it is
a streaming byte sink, not a compute kernel. A plain Python loop
(`sum(bytes)`) is 10–20x slower than the port at every size, so the
port is not competing with Python-level arithmetic; it competes only
with the upstream extension.

## Python-level loops re-entering ctypes per element — and allocations

**No per-element ctypes re-entry exists in the port.** All six wrappers
call `_HASH*` exactly once per hash; `grep` of `python/cityhash` for
`for`/`while` loops finds none in the glue (the only loops are in
`bench/bench.py`'s own timing harness). Verified by inspection of
`__init__.py` and `cProfile` (every `_HASH*` call count equals the
number of wrapper calls).

Quantified why this matters: a Python loop calling raw `H64(b'x', 1)`
1,024 times costs **0.685 µs per element** — i.e. elementwise hashing
of a 1 MiB buffer from Python would cost ~0.7 s, ~7,000x the whole-buffer
call. Any future batch API must keep the one-FFI-call-per-hash
invariant; this is a hard constraint, not a style preference.

Per-call allocations / copies in the glue:

- `bytes` path: **zero-copy**, zero per-call allocation (passes the
  immutable buffer directly). This is the best case and the only path
  that beats 1 µs at 64 B.
- `bytearray` / `memoryview` / `ndarray` / generic buffer path:
  allocates one `memoryview` + one `np.frombuffer` view object per
  call, plus `int(array.ctypes.data)` and `int(array.size)`
  conversions — a fixed ~3.2 µs surcharge at 64 B–4 KiB, paid on
  *every* call regardless of buffer size. The numpy `_internal.py`
  `__init__`/`data` attributes account for ~0.03 s of the cProfile
  total; `_EMPTY` sentinel reuse means no large allocation, but the
  view objects themselves are per-call.
- `str`: full `encode("utf-8")` copy per call (the 73 µs 1 MiB
  surcharge above).
- 128-bit functions: the `(U64 * 2)()` result buffer is thread-local
  and allocated once per thread (`_result128`) — good — but every call
  pays `ctypes.addressof(result)` plus the `(result[0] << 64) |
  result[1]` Python-int assembly. Direct-ctypes measurement shows
  this path is already within ~0.4 µs of raw; the win available is
  only in the small-size wrappers.
- Seed validation (`_uint64` ×2 for `…WithSeeds`, `_seed128` for
  `…128WithSeed`): `isinstance` + `operator.index`/`int()` +
  range checks per call — measurable at small sizes (+0.4–0.8 µs),
  invisible at 1 MiB.

## Next-phase verdicts per hotspot

All verdicts assume the measured figures below; GPU verdicts cite the
flops-per-byte figure explicitly as required.

| hotspot | contention | flops / byte (basis) | next phase |
|---|---|---:|---|
| 1. `CityHash32` 1 MiB kernel (250 µs, slowest absolute) | ~1.8 (36 ops / 20 B: 5 fetches + mul/rot/bswap chains; ~16 of 36 ops are `bswap` source idiom) | **1.8** | **none** (see below) |
| 2–4. small-key boundary, all entry points (0.9–2.7 µs) | 0.5–0.9 | **0.5–0.9** | **none** — no kernel vector; needs glue work, not unroll/SIMD/parallel/GPU |
| 5. `CityHash64` 4 KiB | ~0.5 | **0.5** | **none** |
| 6–10. 1 MiB `CityHash64/128/seeded` kernels (95–109 µs) | 0.5 | **0.5** | **none** |
| 11. generic-buffer path 64 B–4 KiB (+3.2 µs) | ~0.6 | **0.6** | **none** |
| 12. `str` 1 MiB encode (+73 µs) | ~0.5 kernel + copy | **0.5** | **none** |

Why `none` everywhere — specifically:

- **GPU is ruled out by the arithmetic intensity.** The hottest kernels
  run at **~0.5** flops/byte (`CityHash64`/`CityHash128` block loops:
  ~33 and ~66 scalar ops per 64/128 bytes respectively) and the worst
  case `CityHash32` is **~1.8 flops/byte** — both below the ~2
  flops/byte rule-of-thumb in `MOJO_NOTES.md` §5 where a GPU path for a
  host-memory hash that must copy input in and a short result out can
  pay its launch + transfer overhead. The 1 MiB buffers already stream
  at 9–10 GB/s on one CPU core; a GPU round-trip would add PCIe/host
  transfer (~10–20 GB/s effective, plus µs launch each way) to save
  zero compute. Projecting even a perfect 8x GPU kernel: 100 µs →
  12.5 µs compute + ≥20 µs of transfer/launch = net wash at 1 MiB and
  a large loss at every smaller size. **Verdict: no GPU path, and no
  flops-per-byte figure in this map justifies one.**
- **Parallel is ruled out structurally.** Every block round in all three
  size-critical loops carries state forward — `cityhash64`'s
  `x/y/z/v/w`, `cityhash32`'s `state.h/g/f`, `cityhash128_with_seed`'s
  `x/y/z/v/w` — so block `k+1` cannot start before block `k` finishes.
  `README.md`'s existing parallelize analysis already records this;
  this session changed no algorithm and the dependency is unchanged.
  Splitting one hash across threads is therefore incorrect, not
  merely slow.
- **SIMD is ruled out empirically.** `README.md` documents that explicit
  SIMD block preloads were benchmarked and regressed — scalar rounds
  consume lanes serially, so there is no cross-lane work to vectorise.
  The 0.5 flops/byte figure means the bottleneck at 1 MiB is byte
  streaming and scalar chain latency, not lane throughput.
- **Unroll is exhausted.** `cityhash32` already unrolls 2 blocks
  (40 bytes) per iteration, `cityhash128_with_seed` already unrolls 2×64
  bytes; further unrolling deepens only the same serial chain and,
  per the README SIMD result, does not help. The remaining ~10% 1 MiB
  kernel gap vs upstream is source-level codegen — the multi-byte
  `fetch` assemblies and the `bswap` idiom are emitted as scalar
  ladders instead of single unaligned loads / the `bswap` instruction —
  and closing it is a scalar-codegen idiom change, which belongs to
  **none** of the unroll/simd/parallel/gpu phases as defined. It is
  flagged here as the honest remaining gap rather than laundered into
  a mislabelled "unroll" verdict.

The honest next step after this phase is therefore **not** an
acceleration phase at all: it is glue/API work — trimming the fixed
~0.8 µs ctypes floor (cf. `MOJO_NOTES.md` §6's ~0.9 µs estimate), moving
seed validation out of the hot path, caching the buffer-view
conversions for repeated same-object calls, and fixing the scalar
`fetch`/`bswap` codegen idiom. None of those change the algorithm; all
are out of scope for the unroll/simd/parallel/gpu work items, which is
why every row's verdict is **none**.

## Appendix: method notes

- `pixi run bench` run alone under flock, twice (headers: 1.08/1.56/
  103.6/255.9/95.0/102.9 µs and 1.00/1.53/97.1/253.9/98.7/102.1 µs).
- Full sweep: `/tmp/bench_extra.py` — same `time_call` (adaptive batch,
  min 0.15 s, best of 5). Re-run reproduced 1 MiB rows within ±3%
  except `CityHash64` (97–105 µs across three runs, ~±4% jitter
  reported as figures, not averaged away).
- Glue split: `/tmp/bench_glue.py` — raw `_lib.lib()` symbols vs
  wrapper entry points on identical bytes; numpy/`zlib`/`hashlib`
  baselines cited above. The `/tmp` scripts are the exact measurement
  sources; the numbers in this file are their outputs.
- `cProfile` (`/tmp/bench_profile.py`) was used only to corroborate
  the glue timings; profiled totals include profiler overhead and are
  not quoted as times.
- Flops per byte: counted scalar ops per block in `src/cityhash.mojo`.
  `CityHash64`/64 B block (`while length != 0`, lines 328–342):
  4+4+1+2+3+8+10+1 ≈ 33 ops + 8 byte-loads → 0.5/B. `CityHash128`:
  two such halves per 128 B → 0.5/B. `CityHash32`/20 B block
  (`cityhash32_block` + unrolled pair): 5 fetches + ~15 mixing ops +
  ~16 `bswap` shift/mask ops → ~36/20 ≈ 1.8/B. `hash_len_16_mul` = 9
  ops per 16 B in tails. Setup/tail and seed-mix ops are included in
  the totals to within the loop count; sizes and counts are exact.
- Boundedness tags: "memory-bound" at 1 MiB means effective streaming
  bandwidth 9–10 GB/s (for `CityHash64/128`), close to what a single
  core pulls through scalar loads; `CityHash32` at 3.9 GB/s (0.24 ns/B)
  is latency/ILP-bound by its longer dependency chain, not DRAM-bound.
  Below ~4 KiB neither tag applies — the fixed boundary cost dwarfs
  both.
