# Apple M2 (Darwin arm64, 16 GB)

Sample: kirby_shielded_10min.ddd.flac (Kirby instructional video, ten minutes: minutes 30 to 40 of the capture, recorded with the Duplicator's lid on), fingerprint f8c9f9c449920c80, player Philips DVP3050V; used as kirby_shielded_10min.ddd.flac at 40 MS/s, PAL, 2/4/8 cores (unpinned on this platform).

| Build | Frames/s | Range | Runs | CPU s | Peak RAM | One hour of tape |
|---|---|---|---|---|---|---|
| tape-decode native [2 cores] | 11.2 | 11.2-11.2 | 2 | 2672 | 5147 MB | 134 min |
| tape-decode native [4 cores] | 11.9 | 11.8-12.0 | 2 | 4436 | 5316 MB | 126 min |
| tape-decode native [8 cores] | 12.1 | 12.1-12.1 | 2 | 4986 | 5986 MB | 124 min |

Frames per second by cores:

| Build | 2 cores | 4 cores | 8 cores |
|---|---|---|---|
| tape-decode native | 11.2 | 11.9 | 12.1 |
