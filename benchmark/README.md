# Decoder benchmark

Full documentation, including what native, generic and release builds are, is on the wiki: https://github.com/marshalleq/ddd-capture-toolkit/wiki/Benchmarking

Measures how fast each decoder build decodes the same capture on your machine, and writes a table you can
compare with other machines. Works on Linux and macOS. Windows is untested.

```bash
conda activate ddd-capture-toolkit
python3 benchmark/bench.py --sample Capture.ddd.flac --seconds 20 --variants tape-decode@native,tape-decode@generic
```

It is not part of `setup.sh` and nothing here changes your installation. Builds are made by the toolkit's own
scripts in `build-scripts/` (the same ones setup uses), into `benchmark/work/`, so what it measures is what
setup would install and cannot drift away from it.

## Choosing what to measure

`--variants` takes a comma separated list. Put `#a label` after any of them to name it in the table.

| Variant | Meaning |
|---|---|
| `tape-decode@release` | namazso's newest release binary for this CPU (Linux x86-64) |
| `tape-decode@native` | Built from source for this CPU. `@native:REF` builds a tag, branch or commit |
| `tape-decode@generic` | The same source built without CPU-specific instructions |
| `vhs-decode@release` | Upstream's prebuilt AppImage (Linux) |
| `vhs-decode@REF` | Built from `external/vhs-decode` at `REF`, for example `vhs-decode@v0.4.0` or `vhs-decode@efc3818f`. Add `:generic` for a portable build |
| `exe=PATH:KIND` | A program you already have. `KIND` is `tape-decode` or `vhs-decode` |

A build that fails is reported with the reason and left out of the table. Nothing is substituted for it.

## The sample

- `--sample FILE` is a `.ddd.flac` capture. `--seconds N --start S` cuts N seconds from it.
- `--repeat-to SECONDS` repeats the sample until it is about that long. A boring capture repeated to ten minutes
  (`--repeat-to 600`) gives a long run for a steady figure. The joins cost a moment of lost sync each, nothing more.
- `--resample-to 20` decodes a 20 MS/s copy of the sample, which is what a 20 MS/s recorder would have written.
- `--lds` also runs the `vhs-decode` builds on an uncompressed `.lds` copy.
- `--standard ntsc` for NTSC captures. Frames per hour use 25 or 29.97 frames per second.

## Method

One discarded warm-up, then `--runs` timed runs (default 3) of every build in turn, so slow drift hits them all
alike. On Linux each decode is pinned to `--cores` physical cores (default 4), chosen the way the toolkit chooses
them. macOS cannot pin, so a decode there runs on four threads with the rest of the chip free.

If any other decode starts on the machine while a run is in progress, that run is marked disturbed and left out
of the figures, and the tool waits up to two minutes for an existing decode to finish before it starts. Stop other
work on the machine while it runs.

## Results

Written to `benchmark/results/<host>-<date>/`: `results.csv` (every run), `results.json` (with the machine's
details) and `summary.md` (the table). Peak RAM is sampled once a second, so it is a floor.

Share a `summary.md` together with the machine and the exact command you ran.
