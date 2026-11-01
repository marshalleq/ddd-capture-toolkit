# AMD Ryzen 9 9950X3D 16-Core Processor (Linux x86_64, 123 GB)

Sample: kirby_shielded_10min.ddd.flac (Kirby instructional video, ten minutes: minutes 30 to 40 of the capture, recorded with the Duplicator's lid on), fingerprint f8c9f9c449920c80, player Philips DVP3050V; used as kirby_shielded_10min.ddd.flac at 40 MS/s, PAL, 2/4/8/16 cores.

| Build | Frames/s | Range | Runs | CPU s | Peak RAM | One hour of tape |
|---|---|---|---|---|---|---|
| tape-decode native [2 cores] | 16.8 | 16.8-16.8 | 2 | 1775 | 429 MB | 89 min |
| tape-decode native [4 cores] | 23.0 | 22.9-23.1 | 2 | 2405 | 716 MB | 65 min |
| tape-decode native [8 cores] | 24.2 | 24.1-24.2 | 2 | 2529 | 1362 MB | 62 min |
| tape-decode native [16 cores] | 23.1 | 23.1-23.1 | 2 | 2562 | 2782 MB | 65 min |

Frames per second by cores:

| Build | 2 cores | 4 cores | 8 cores | 16 cores |
|---|---|---|---|---|
| tape-decode native | 16.8 | 23.0 | 24.2 | 23.1 |
