# AMD Ryzen 7 5800X 8-Core Processor (Linux x86_64, 31 GB)

Sample: kirby_shielded_10min.ddd.flac (Kirby instructional video, ten minutes: minutes 30 to 40 of the capture, recorded with the Duplicator's lid on), fingerprint f8c9f9c449920c80, player Philips DVP3050V; used as kirby_shielded_10min.ddd.flac at 40 MS/s, PAL, 4 cores.

| Build | Frames/s | Range | Runs | CPU s | Peak RAM | One hour of tape | vs tape-decode@generic |
|---|---|---|---|---|---|---|---|
| tape-decode native | 12.8 | 12.6-13.0 | 2 | 4114 | 741 MB | 117 min | 1.91x |
| tape-decode generic | 6.7 | 6.7-6.7 | 2 | 7889 | 746 MB | 3.7 h | 1.00x |
| tape-decode release | 6.4 | 6.3-6.5 | 2 | 8179 | 5081 MB | 3.9 h | 0.96x |
