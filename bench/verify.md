# VERIFY phase — mojo-cityhash vs upstream `python-cityhash`

Date: 2026-11-09. Machine for every number below (printed by `bench/bench.py` on every run,
confirmed against `/proc/cpuinfo`):
`Intel(R) Xeon(R) CPU E5-2697 v4 @ 2.30GHz; Linux x86_64; Python 3.13.14`
— the same CPU/OS/Python the README claims.
Protocol, in order: `pixi run build && pixi run test`, then `pixi run bench`.
This is a second VERIFY pass; it re-runs everything from scratch and replaces the
numbers in `README.md` with this session's final bench run. Numbers not measured in
this session do not appear in the README.

## 1. Baseline commands (as instructed)

- `pixi run build && pixi run test` → **green**: build succeeded (Mojo
  deprecation warnings for `UnsafePointer`/positional `__getitem__` only),
  `156 passed in 0.79s`.
- `pixi run bench` (exit 0, run alone, flock-wrapped):

  | Function | Input | Mojo | upstream | upstream / Mojo |
  |---|---:|---:|---:|---:|
  | `CityHash64` | small-key latency | 1.01 µs | 0.23 µs | 0.23x |
  | `CityHash64` | 4 KiB | 1.54 µs | 0.61 µs | 0.40x |
  | `CityHash64` | 1 MiB | 107.02 µs | 96.91 µs | 0.91x |
  | `CityHash32` | 1 MiB | 256.63 µs | 228.98 µs | 0.89x |
  | `CityHash128` | 1 MiB | 93.77 µs | 93.92 µs | 1.00x |
  | `CityHash64WithSeeds` | 1 MiB, seeded | 99.12 µs | 97.81 µs | 0.99x |

## 2. Every README row, rerun individually

`bench/bench.py` iterates the six cases sequentially, so each `pixi run bench`
re-measures every row. I ran it **six times** in this session (the baseline run
plus four reruns, plus one final run after the README edit, which is the run now
quoted in the README) and compared each run's cells to the README's pre-existing
cells (1.02/0.22/0.22x, 1.44/0.57/0.39x, 97.69/90.70/0.93x, 239.20/224.06/0.94x,
92.09/88.66/0.96x, 99.35/93.91/0.95x), flagging any cell deviating by more than 20%.

### What reproduced (within 20% in every one of the six runs)

- `CityHash64` small-key latency — README 1.02 / 0.22 / 0.22x vs measured 1.00–1.11 /
  0.21–0.24 / 0.20–0.24x (max deviation 9.1%).
- `CityHash64` 4 KiB — README 1.44 / 0.57 / 0.39x vs measured 1.45–1.54 /
  0.56–0.62 / 0.38–0.42x (max deviation 8.8%).
- `CityHash64` 1 MiB — README 97.69 / 90.70 / 0.93x vs measured 96.19–107.02 /
  90.41–97.26 / 0.90–0.94x (max deviation 9.6%).
- `CityHash32` 1 MiB — README 239.20 / 224.06 / 0.94x vs measured 231.59–256.63 /
  213.96–231.16 / 0.89–0.95x (max deviation 7.3%).
- `CityHash128` 1 MiB — README 92.09 / 88.66 / 0.96x vs measured 91.06–98.55 /
  85.06–93.92 / 0.88–1.00x (max deviation 8.3%).
- `CityHash64WithSeeds` 1 MiB, seeded — README 99.35 / 93.91 / 0.95x vs
  measured 98.71–108.56 / 91.25–98.04 / 0.90–0.99x (max deviation 9.3%).

No cell in any run deviated by more than 20%. The session medians sit a few percent
above the old README values, consistent with run-to-run jitter on a shared Xeon,
not with an overstated claim. Per the task rule, rows that reproduce within 20%
would not have needed correction, but the README table was still refreshed to this
session's final run so every number in it was measured here.

### The six session runs (for the record)

| Run | 64 small Mojo/up/ratio | 64 4 KiB | 64 1 MiB | 32 1 MiB | 128 1 MiB | 64ws 1 MiB |
|---|---|---|---|---|---|---|
| 1 (baseline) | 1.01 / 0.23 / 0.23x | 1.54 / 0.61 / 0.40x | 107.02 / 96.91 / 0.91x | 256.63 / 228.98 / 0.89x | 93.77 / 93.92 / 1.00x | 99.12 / 97.81 / 0.99x |
| 2 | 1.00 / 0.24 / 0.24x | 1.51 / 0.57 / 0.38x | 97.27 / 90.85 / 0.93x | 233.59 / 213.96 / 0.92x | 91.32 / 86.14 / 0.94x | 98.71 / 91.25 / 0.92x |
| 3 | 1.08 / 0.22 / 0.20x | 1.45 / 0.57 / 0.39x | 104.44 / 93.91 / 0.90x | 236.97 / 226.15 / 0.95x | 94.60 / 89.65 / 0.95x | 103.54 / 97.77 / 0.94x |
| 4 | 1.05 / 0.21 / 0.20x | 1.49 / 0.56 / 0.38x | 96.19 / 90.41 / 0.94x | 231.59 / 215.61 / 0.93x | 91.06 / 85.06 / 0.93x | 98.99 / 92.09 / 0.93x |
| 5 | 1.11 / 0.23 / 0.21x | 1.51 / 0.60 / 0.40x | 105.86 / 96.99 / 0.92x | 247.33 / 228.62 / 0.92x | 98.55 / 87.10 / 0.88x | 103.73 / 96.75 / 0.93x |
| 6 (final) | **1.09 / 0.24 / 0.22x** | **1.47 / 0.62 / 0.42x** | **103.94 / 97.26 / 0.94x** | **254.88 / 231.16 / 0.91x** | **96.94 / 89.17 / 0.92x** | **108.56 / 98.04 / 0.90x** |

Bold = the run now quoted in the README table. Note run 1's `CityHash128`
1 MiB ratio of 1.00x: at 1 MiB the port is at parity within jitter
(0.88–1.00x across runs). It is still slower-or-equal on every run, never faster
beyond noise; the row stays in the table as a non-win, and the README sentence
stating the port is slower than upstream on every row is now qualified by this
jitter in this file (in the final run all ratios are `< 1`, so the statement
holds for the quoted numbers).

### What could not be reproduced

Nothing. No cell breached the 20% threshold in any of the six runs, no row was
unmeasurable, no function was missing, and no parity assert in the bench failed.
The README's machine line (CPU, OS, Python 3.13.14) was confirmed by the bench's
own `/proc/cpuinfo` print on every run.

## 3. Same-input / no-skipped-work audit

Code-inspected `bench/bench.py` (`main()` builds `data = bytes(...)` once per
case, derives it from the same deterministic generator for both sides, asserts
`ours(data, *seeds) == reference(data, *seeds)`, then times
`lambda: ours(data, *seeds)` and `lambda: reference(data, *seeds)` with the same
adaptive-batch `time_call`: min 0.15 s, best of 5 trials, `perf_counter`).
Then verified empirically this session with an independent script (not `bench.py`):

- For all six bench cases, both sides return identical hashes on the same
  `bytes` object: parity `True` on every case, including the seeded case with
  `(0x0123456789ABCDEF, 0xFEDCBA9876543210)`.
- Flipping the **last** byte of each input changes both sides' hashes and
  the new hashes still match — both implementations consume the full
  buffer, neither hashes a prefix.
- Repeated calls with alternating distinct payloads (`CityHash64`,
  `CityHash128`, forward and reversed order) return the fresh upstream-matching
  value every time — no stale/cached result from the thread-local 128-bit buffer
  or the ctypes layer is being timed.
- The Mojo side's Python wrapper (`python/cityhash/__init__.py`) passes the
  original `bytes` object to ctypes without copying (verified by identity spy:
  `buf is data` is `True`; also covered by
  `test_bytes_fast_path_passes_original_buffer_to_ffi`); the upstream side
  is the installed `python-cityhash` C++ extension called with the same
  object. Neither side is handed a shorter or pre-digested input.

Conclusion: the ratios are honest — same bytes, same seeds, full hashes.
The port's deficit is real: at small sizes it is the Python→ctypes fixed
cost (≈1 µs vs ≈0.2 µs), at 1 MiB it is kernel codegen (scalar byte
assembly in `src/cityhash.mojo`). In the final run it is slower than upstream on
every row (ratios 0.22–0.94x) and the table says so explicitly; no row was
removed or reworded to look better.

## 4. Test-parity audit (`git log -p -- tests/`)

History of `tests/` across all commits (`aa6ab72` initial port,
`b36c04c` accel pass, `c3acf4e` test phase):

- The earliest commit already asserts **exact integer parity**
  (`assert ours(data) == reference(data)`) on fixed vectors, all length
  boundaries, seeded extremes, and a 1,000,003-byte randomized payload.
- `git log -p -- tests/` contains **zero removed lines** (`grep -cE '^-[^-]' = 0`):
  no assertion was ever deleted.
- The only tolerance-like artifact is `TOLERANCE = 0` with
  `assert abs(actual - expected) <= TOLERANCE` in the newest tests
  (`tests/test_parity.py:17-24`, added by `c3acf4e`) — i.e. tolerance zero,
  exact parity, written in an absolute-difference idiom plus a strict
  `type(actual) is int` check. That is *stricter* than a plain `==` on
  equal ints, not looser. `git log -S TOLERANCE` shows a single addition
  of the value `0`; it was never set to a nonzero number.
- No `pytest.approx`, `pytest.close`, `math.isclose`, `rel=`/`abs=`,
  `skip`, or `xfail` exists in `tests/`, `bench/`, `python/`, or `src/`
  (grepped; the only hits are in this file's prose).
- Net finding: **no loosened tolerances and no removed assertions to
  restore.** The suite passes as-is (156 tests) and every hash assertion
  in it is exact equality or `<= 0` difference.

One nit, left unchanged per the "change code only to fix a shown bug"
rule: the helper is named `test_each_public_function_parity_with_tolerance`
and `assert_parity`, but the tolerance is 0 — the name is cosmetic and
does not weaken the check.

## 5. What changed

- `README.md` benchmark table: replaced with the final (run 6) `pixi run
  bench` output measured in this session —
  1.09/0.24/0.22x, 1.47/0.62/0.42x, 103.94/97.26/0.94x, 254.88/231.16/0.91x,
  96.94/89.17/0.92x, 108.56/98.04/0.90x — plus one word noting this is the
  second VERIFY pass. The slower-than-upstream sentence, machine line, units,
  and `upstream / Mojo` definition are unchanged; all six rows are kept.
- This file, `bench/verify.md` (rewritten for this session; numbers above are
  from the six runs in §2, not copied from the earlier pass).
- **No source or test changes**: no bug with a failing test was found to
  fix, and (per §4) no loosened assertion needed restoring.

## 6. Final gate

`pixi run build && pixi run test` — run again after the README edit:
build green, **156 passed**.
