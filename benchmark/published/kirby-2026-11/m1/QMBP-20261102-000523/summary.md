# Apple M1 Pro (Darwin arm64, 32 GB)

Sample: kirby_shielded_10min.ddd.flac (Kirby instructional video, ten minutes: minutes 30 to 40 of the capture, recorded with the Duplicator's lid on), fingerprint 29884c8c98cb1cb9, player Philips DVP3050V; used as kirby_shielded_10min.ddd.flac at 40 MS/s, PAL, 4 cores (unpinned on this platform).

| Build | Frames/s | Range | Runs | CPU s | Peak RAM | One hour of tape | vs exe=/Volumes/4TB_NVME/bench/generic/bin/tape-decode:tape-decode |
|---|---|---|---|---|---|---|---|
| tape-decode native | 15.4 | 15.4-15.4 | 2 | 3421 | 5357 MB | 97 min | 1.69x |
| tape-decode generic | 9.1 | 9.1-9.1 | 2 | 5974 | 1176 MB | 2.7 h | 1.00x |
