# DDD Capture Toolkit — An archival workflow for VHS-Decode and Domesday Duplicator

**Capture, decode, compress, export, validate, archive.** Built for archivists who want to keep the original RF masters of their VHS tapes and prove cryptographically that the compressed copies are true and correct.

![DDD Capture Toolkit](media/Images/Capture%20Toolkit%20New3.png)

The toolkit grew out of a fix for the Domesday Duplicator (DdD) audio-sync problem and has since become a general-purpose batch workflow system for the entire **VHS-Decode** pipeline. If you can produce a `.lds` or `.ldf` (with or without DdD hardware), it queues, prioritises, validates and archives the rest of the work for you — decode (vhs-decode), compress (FLAC-in-LDF), export to FFV1, audio align, final mux.

The validation pipeline is the heart of it. A three-tier compress check (always-on structural check, optional end-to-end FLAC integrity, manual full sample-count round-trip against the source `.lds`), plus per-file SHA-256 logging, means you can safely delete raw `.lds` masters once their `.ldf` has been proven a complete lossless compression. No more "is this archive copy actually intact?" anxiety.

> **For full information on any topic below, see the [project wiki](https://github.com/marshalleq/ddd-capture-toolkit/wiki).** This README is a quick overview only.

Headline capabilities:

- **Three-tier compress validation** — structural seek check, end-to-end FLAC integrity, and a sample-count round-trip against the source `.lds`. On PASS, writes a `.ldf.verified` sidecar — the gate before you delete an original RF master.
- **Automatic content hashing** to a per-project `_validation.log`; the matrix surfaces `HASHING` / `VALIDATED` / `STALE` / `INVALID` per step so file changes are spotted immediately, not weeks later.
- **Non-destructive archive staging** — one command (`stage N`) moves intermediate files (`.tbc`, `_ffv1.mkv`, etc.) into a subfolder, leaving only the archive set (`.ldf`, `.ldf.verified`, `.flac`, `_final.mkv`, validation log) at the top level. Reversible.
- **Batch and auto-queuing** of pipeline jobs with hardware-aware concurrency. Queue an overnight run, walk away.
- **Per-project flags** — decode, export, audio, compress, and segment-test options are configurable independently for each project. Different tapes get different processing — B&W vs colour, wrong field order, sub-deemphasis on noisy sources, faster validation on test runs — without touching global config.
- **CPU-aware scheduling** — concurrent VHS-Decode jobs are pinned to disjoint L3 cache groups (CCDs on AMD, P/E clusters on Intel) so they don't fight for cache. Other CPU-heavy jobs are dynamically kept off the decode cores.
- **Live, exact progress** computed from kernel-side byte counters (Linux `/proc`, macOS `libproc`), not estimated from compression ratios.
- **Domesday Duplicator audio sync** — the original feature: synchronised capture with Clockgen Lite, automatic offset measurement, and VCR speed compensation. CLI control of the DdD software (added as part of this project) makes the synchronisation possible at all.

## Quick install

```bash
git clone --recurse-submodules https://github.com/marshalleq/ddd-capture-toolkit.git
cd ddd-capture-toolkit
./setup.sh                 # easy mode, ~5 min, uses prebuilt packages
# or ./setup.sh --performance    # compile-from-source with -march=native, ~30–60 min,
                                 # notable throughput win for ffmpeg-bound steps
conda activate ddd-capture-toolkit
python3 ddd_main_menu.py
```

Linux is the first-class platform. macOS and Windows have the groundwork in place but need testers — see [Getting Started](https://github.com/marshalleq/ddd-capture-toolkit/wiki/Getting-Started) in the wiki for platform-specific notes.

## More information

Everything beyond the quick install — workflow, individual pipeline steps, troubleshooting, the scheduler, validation, configuration — is in the **[project wiki](https://github.com/marshalleq/ddd-capture-toolkit/wiki)**. Highlights:

| Topic | Page |
|---|---|
| Install + first-time setup | [Getting Started](https://github.com/marshalleq/ddd-capture-toolkit/wiki/Getting-Started) |
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
