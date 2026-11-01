# Apple M2 (Darwin arm64, 16 GB)

Sample: kirby_shielded_10min.ddd.flac (Kirby instructional video, ten minutes: minutes 30 to 40 of the capture, recorded with the Duplicator's lid on), fingerprint f8c9f9c449920c80, player Philips DVP3050V; used as kirby_shielded_10min.ddd.flac at 40 MS/s, PAL, 4 cores (unpinned on this platform).

| Build | Frames/s | Range | Runs | CPU s | Peak RAM | One hour of tape | vs exe=/Users/quentinj/bench/tape-decode-generic:tape-decode |
|---|---|---|---|---|---|---|---|
| tape-decode native | 12.1 | 12.0-12.1 | 2 | 4369 | 5345 MB | 124 min | 1.64x |
| tape-decode generic | 7.4 | 7.4-7.4 | 2 | 7390 | 1129 MB | 3.4 h | 1.00x |
