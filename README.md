# DDD Capture Toolkit

A full VHS-decode workflow control centre — capture, decode, compress, export, validate, archive.

![DDD Capture Toolkit](media/Images/Capture%20Toolkit%20New3.png)

Originally built to solve the audio-sync problem on Domesday Duplicator captures, the toolkit has grown into a general-purpose batch workflow system for the whole VHS-decode pipeline. If you can produce a `.lds` / `.ldf` (with or without DdD hardware), it queues, prioritises, validates and archives the rest of the work for you.

> **For full information on any topic below, see the [project wiki](https://github.com/marshalleq/ddd-capture-toolkit/wiki).** This README is a quick overview only.

Headline capabilities:

- **Batch and auto-queuing** of pipeline jobs with hardware-aware concurrency.
- **CPU-aware scheduling** — concurrent decodes are pinned to disjoint L3 cache groups (CCDs on AMD, P/E clusters on Intel) so they don't fight for cache. Other CPU-heavy jobs are dynamically kept off the decode cores.
- **Three-tier compress validation** with a `.ldf.verified` sidecar gate before you delete original `.lds` masters.
- **Automatic content hashing** to a per-project `_validation.log`; the matrix surfaces `HASHING` / `VALIDATED` / `STALE` / `INVALID` per step.
- **Live, exact progress** computed from kernel-side byte counters (Linux `/proc`, macOS `libproc`), not estimated from compression ratios.
- **Audio sync** — the original feature: synchronised capture with Clockgen Lite, automatic offset measurement, and VCR speed compensation.

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
