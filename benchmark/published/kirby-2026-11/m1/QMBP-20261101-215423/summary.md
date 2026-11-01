# Apple M1 Pro (Darwin arm64, 32 GB)

Sample: kirby_shielded_10min.ddd.flac (Kirby instructional video, ten minutes: minutes 30 to 40 of the capture, recorded with the Duplicator's lid on), fingerprint 29884c8c98cb1cb9, player Philips DVP3050V; used as kirby_shielded_10min.ddd.flac at 40 MS/s, PAL, 2/4/8/10 cores (unpinned on this platform).

| Build | Frames/s | Range | Runs | CPU s | Peak RAM | One hour of tape |
|---|---|---|---|---|---|---|
| tape-decode native [2 cores] | 11.3 | 11.3-11.3 | 1 | 2671 | 5154 MB | 133 min |
| tape-decode native [4 cores] | 15.3 | 15.3-15.4 | 2 | 3428 | 5416 MB | 98 min |
| tape-decode native [8 cores] | 16.6 | 16.6-16.6 | 2 | 3500 | 5989 MB | 90 min |
| tape-decode native [10 cores] | 16.7 | 16.7-16.7 | 2 | 3561 | 6337 MB | 90 min |

Frames per second by cores:

| Build | 2 cores | 4 cores | 8 cores | 10 cores |
|---|---|---|---|---|
| tape-decode native | 11.3 | 15.3 | 16.6 | 16.7 |
