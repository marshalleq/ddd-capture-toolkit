# AMD Ryzen 7 5800X 8-Core Processor (Linux x86_64, 31 GB)

Sample: kirby_shielded_10min.ddd.flac (Kirby instructional video, ten minutes: minutes 30 to 40 of the capture, recorded with the Duplicator's lid on), fingerprint f8c9f9c449920c80, player Philips DVP3050V; used as kirby_shielded_10min.ddd.flac at 40 MS/s, PAL, 2/4/8 cores.

| Build | Frames/s | Range | Runs | CPU s | Peak RAM | One hour of tape |
|---|---|---|---|---|---|---|
| tape-decode native [2 cores] | 9.6 | 9.5-9.6 | 2 | 3009 | 436 MB | 2.6 h |
| tape-decode native [4 cores] | 12.6 | 12.6-12.6 | 2 | 4111 | 748 MB | 119 min |
| tape-decode native [8 cores] | 13.5 | 13.2-13.8 | 2 | 4289 | 1412 MB | 111 min |

Frames per second by cores:

| Build | 2 cores | 4 cores | 8 cores |
|---|---|---|---|
| tape-decode native | 9.6 | 12.6 | 13.5 |
