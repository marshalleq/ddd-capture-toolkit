# DDD Capture Toolkit — An archival workflow for VHS-Decode and Domesday Duplicator

**Capture, decode, export, align, archive.** Built for archivists who want true archival masters of their tapes and work through large batches of them.

![DDD Capture Toolkit](media/Images/Capture%20Toolkit%20New3.png)

The toolkit grew out of a fix for the Domesday Duplicator (DdD) audio-sync problem, and that is still a main reason to use it: recording the DdD's RF alongside Clockgen Lite audio so the two stay in sync. It has since become a general-purpose batch workflow system for the **VHS-Decode** family of decoders. It captures, decodes, exports, aligns the audio and muxes the result, and it keeps the books on every file along the way. It is for archivists who want true archival masters of their tapes and who work through large batches of them.  The application is intentionally built in a basic console and auto compiles for your exact hardware so that it remains light and responsive, leaving no performance on the table.  This unlocks some other features like control over ssh and headless captures and decodes.  If you'd prefer a GUI option, please see [MiSRC GUI](https://github.com/harrypm/MISRC-GUI/).  There is a basic agreement that we should work toward joining these two tools up as much as we can and as such they use the same underlying code base.  But as it stands right now, this tool is still the stronger tool for a number of use cases, including audio sync on difficult devices such as the Domesday Duplicator and when you need to batch large amounts of decode work.

Capture and decode programs are **pluggable backends**. The toolkit controls each through the same set of options (the job queue, per-project flags, CPU scheduling, progress and checks), so a new version of a supported program generally works with no changes, and a new capture or decode program needs only one small backend. Today it supports the upstream Domesday Duplicator app (`ddd-gui`) for capture, and `tape-decode` (the Rust decoder) or `vhs-decode` for decoding, each compiled for your CPU or as a prebuilt binary. See [Architecture](https://github.com/marshalleq/ddd-capture-toolkit/wiki/Architecture).

> **For full information on any topic below, see the [project wiki](https://github.com/marshalleq/ddd-capture-toolkit/wiki).** This README is a quick overview only.

Headline capabilities:

- **Domesday Duplicator audio sync** — the original reason for the project, and still a main one: synchronised capture of the RF and the Clockgen Lite audio (Clockgen Lite is required), automatic offset measurement, and VCR speed compensation. CLI control of the DdD software (added as part of this project) makes the synchronisation possible at all.
- **Pluggable capture and decode backends** — the capture program and the decoder are chosen in config, each controlled through the same set of options, so new versions of supported programs generally just work, and new programs need one small backend. Each is installed compiled for your CPU or as a prebuilt binary. See the Architecture page in the wiki.
- **Batch and auto-queuing** of pipeline jobs with hardware-aware concurrency. Queue an overnight run, walk away.
- **Per-project flags** — decode, export, audio, compress, and segment-test options are configurable independently for each project. Different tapes get different processing — B&W vs colour, wrong field order, sub-deemphasis on noisy sources, faster validation on test runs — without touching global config.
- **CPU-aware scheduling** — concurrent VHS-Decode jobs are pinned to disjoint L3 cache groups (CCDs on AMD, P/E clusters on Intel) so they don't fight for cache. Other CPU-heavy jobs are dynamically kept off the decode cores.
- **Live, exact progress** computed from kernel-side byte counters (Linux `/proc`, macOS `libproc`), not estimated from compression ratios.
- **Three-tier compress validation** — structural seek check, end-to-end FLAC integrity, and a sample-count round-trip against the source `.lds`. On PASS, writes a `.ldf.verified` sidecar — the gate before you delete an original RF master.
- **Automatic content hashing** to a per-project `_validation.log`; the matrix surfaces `HASHING` / `VALIDATED` / `STALE` / `INVALID` per step so file changes are spotted immediately, not weeks later.
- **Non-destructive archive staging** — one command (`stage N`) moves the backup set (`.ldf`, `.ldf.validated`, original `.flac`, `.json`, `_final.mkv`, capture and validation logs, and their `.sha256` sidecars) into a `<basename>.backup/` subfolder, ready to copy to backup storage. The regenerable leftovers (`.lds`, the decode outputs `.tbc` / `_chroma.tbc` / `.tbc.json` / `.log`, `_ffv1.mkv`, `_aligned.flac`) stay at the top level to delete. Reversible.

## Built for bulk archival

If you have a wall of VHS tapes to digitise, the toolkit replaces the manual command-line dance — *which decode flags does this tape need, has the export finished yet, which files do I keep, which do I delete* — with a single coordinated batch system. Set per-project flags once, queue everything, walk away. Far fewer keystrokes, and dramatically fewer ways to slip up at three in the morning on tape number forty.

It runs entirely in a terminal (no X server, no desktop required), so a dedicated headless Linux box can chew through tapes overnight while you're not in the room. A purpose-built Linux distribution tuned for VHS capture and pipeline processing is in early development.

## Quick install

```bash
git clone --recurse-submodules https://github.com/marshalleq/ddd-capture-toolkit.git
cd ddd-capture-toolkit
./setup.sh                 # easy mode, ~5 min, uses prebuilt packages
# or ./setup.sh --performance    # compile-from-source for your CPU, ~30–60 min,
                                 # decodes nearly twice as fast (see below)
conda activate ddd-capture-toolkit
python3 ddd_main_menu.py
```

### Easy mode or performance mode?

Easy mode installs prebuilt programs and is working in five minutes. **Performance mode compiles the
decoder for your exact CPU, and a tape you decode overnight finishes in about half the time.** You pay once,
at install, and every decode after that is faster.

Measured on a real 52 minute PAL capture (77,916 frames), four cores or threads per decode, `tape-decode` compiled
for the CPU. Each figure is the speed of the whole decode:

| Machine | Frames/s | Time for one hour of tape |
|---|---|---|
| Ryzen 9 9950X3D | **30.0** | **50 minutes** |
| Apple M1 Pro | **19.9** | **75 minutes** |
| Ryzen 7 5800X | **15.9** | **94 minutes** |
| Apple M2 (Air) | **15.6** | **96 minutes** |

Speed depends on the tape. The same machines decode the stretch of that capture from minute 5 to 15 about 1.6 to
1.9 times faster than the stretch from minute 30 to 40. The table below uses minutes 30 to 40 (ten minutes, 15,000
frames), the slower of the two, so treat it as a cautious figure for a hard tape:

| Build (frames per second, higher is faster) | Ryzen 9 9950X3D | Ryzen 7 5800X | Apple M1 Pro | Apple M2 (Air) |
|---|---|---|---|---|
| **tape-decode**, compiled for the CPU | **22.9** | **12.8** | **15.4** | **12.1** |
| tape-decode, easy-mode release (best x86-64 build for the CPU) | 9.9 | 6.4 | n/a | n/a |
| tape-decode, generic build (no CPU-specific instructions) | 9.1 | 6.7 | 9.1 | 7.4 |
| vhs-decode v0.4.0, compiled | 9.2 | 5.2 | 6.1 | not tried |
| vhs-decode March 2026, compiled (reading `.lds`) | 13.0 | 7.2 | 7.6 | not tried |

On this section, compiling `tape-decode` for your CPU is **2.0 to 2.3 times faster than easy mode** (an hour of
tape in 65 minutes instead of 2.5 hours on the 9950X3D) and about **2.5 times faster than `vhs-decode`**. The generic
build shows how much of that is the compiler's CPU-specific instructions: 1.6 to 2.5 times. Part of the easy-mode
gap is also that performance mode builds the decoder's current source while easy mode takes its latest release, which is older.
The figures are for the decode step only.

Recording at 20 million samples a second instead of 40 decodes faster again: 39.6 frames/s against 22.9 on the
9950X3D, 20.0 against 12.8 on the 5800X and 28.1 against 15.4 on the M1 Pro.

An hour of PAL is 90,000 frames, so divide by the figure. The 10 minute `tape-decode` figures are the mean of two
runs and `vhs-decode` was run once. The full capture was run twice on the 9950X3D; on the other three the first run
was set aside because the tool wrongly thought another decode was running (the two runs agreed within 3%). The raw
results are in [benchmark/published/kirby-2026-11](benchmark/published/kirby-2026-11). Linux decodes are pinned
to four cores. The Macs cannot pin, so they get four threads with the rest of the chip free. The M2 binary was built on
the M1 Mac for the M2 chip (`target-cpu=apple-m2`). Speed stops improving at about eight cores on every machine
(the Air barely improves beyond two), and the toolkit gives each decode four.

Earlier, on a single 26 second capture, `tape-decode` reached 35, 25, 28.5 and 30 frames/s on the same four machines. Short samples
flatter the decoder, so use the table above.

Full results and method: [Decoders](https://github.com/marshalleq/ddd-capture-toolkit/wiki/Decoders).

> **Use the conda environment — do not `pip install -r requirements.txt` against a system Python.** The toolkit pins Python 3.12 and installs everything (including `tbc-video-export`, which has no wheels for Python ≥ 3.14) into the isolated `ddd-capture-toolkit` conda env. Installing into a bare python.org interpreter will fail to resolve dependencies. **On Windows** this means installing [Git for Windows](https://git-scm.com/downloads/win) (for the Git Bash shell `setup.sh` needs) and [Miniconda](https://docs.conda.io/en/latest/miniconda.html) first, then running `./setup.sh` from Git Bash — see [SETUP.md](SETUP.md).

Linux and macOS are both first-class platforms. On macOS the decoders (`tape-decode` and `vhs-decode`), the export and the benchmark have been run on an Apple M1 Pro and an M2; **capturing on a Mac has not been tested yet**, and `./setup.sh --performance` has not been run end to end on one (easy mode has no prebuilt `tape-decode` for macOS). Windows has the groundwork in place but needs testers. See [Getting Started](https://github.com/marshalleq/ddd-capture-toolkit/wiki/Getting-Started) in the wiki for platform-specific notes.

## More information

Everything beyond the quick install — workflow, individual pipeline steps, troubleshooting, the scheduler, validation, configuration — is in the **[project wiki](https://github.com/marshalleq/ddd-capture-toolkit/wiki)**. Highlights:

| Topic | Page |
|---|---|
| Quick start, install to first decode | [Quick Start](https://github.com/marshalleq/ddd-capture-toolkit/wiki/Quick-Start) |
| Choosing the decoder (tape-decode or vhs-decode) | [Decoders](https://github.com/marshalleq/ddd-capture-toolkit/wiki/Decoders) |
| Install + first-time setup | [Getting Started](https://github.com/marshalleq/ddd-capture-toolkit/wiki/Getting-Started) |
| How the parts fit together (diagrams) | [Architecture](https://github.com/marshalleq/ddd-capture-toolkit/wiki/Architecture) |
| What each pipeline step does | [Pipeline Overview](https://github.com/marshalleq/ddd-capture-toolkit/wiki/Pipeline-Overview) |
| The main interface | [Workflow Control Centre](https://github.com/marshalleq/ddd-capture-toolkit/wiki/Workflow-Control-Centre) |
| Per-project decode / export / audio / compress / segment flags | [Project Flags](https://github.com/marshalleq/ddd-capture-toolkit/wiki/Project-Flags) |
| Audio sync (the original use case) | [Audio Synchronisation](https://github.com/marshalleq/ddd-capture-toolkit/wiki/Audio-Synchronisation) |
| `.lds`-safe compression | [Compress Validation](https://github.com/marshalleq/ddd-capture-toolkit/wiki/Compress-Validation) |
| Integrity checking | [Checksums and Verification](https://github.com/marshalleq/ddd-capture-toolkit/wiki/Checksums-and-Verification) |
| Job scheduling + CPU pinning | [Prioritisation and Queuing](https://github.com/marshalleq/ddd-capture-toolkit/wiki/Prioritisation-and-Queuing) |
| Per-step progress maths | [Progress Reporting](https://github.com/marshalleq/ddd-capture-toolkit/wiki/Progress-Reporting) |
| Why the scheduling defaults are what they are | [Performance Benchmarks](https://github.com/marshalleq/ddd-capture-toolkit/wiki/Performance-Benchmarks) |
| Common issues | [Troubleshooting](https://github.com/marshalleq/ddd-capture-toolkit/wiki/Troubleshooting) |

## Credits

- [vhs-decode](https://github.com/oyvindln/vhs-decode) — VHS RF decoding
- [ld-decode](https://github.com/happycube/ld-decode) — LaserDisc / VHS decoding foundation
- [tbc-video-export](https://github.com/JuniorIsAJitterbug/tbc-video-export) — TBC to video conversion
- [Domesday Duplicator](https://github.com/simoninns/DomesdayDuplicator) — RF capture hardware
- [VhsDecodeAutoAudioAlign](https://gitlab.com/wolfre/vhs-decode-auto-audio-align) — Audio drift compensation by Rene Wolf
- [Clockgen Lite](https://github.com/namazso/cxadc-clockgen-mod) — Clock synchronisation mod

## Licence

This project integrates multiple open-source components. See individual component licences for terms.
