# AMD Ryzen 9 9950X3D 16-Core Processor (Linux x86_64, 123 GB)

Sample: kirby_shielded_10min.ddd.flac (Kirby instructional video, ten minutes: minutes 30 to 40 of the capture, recorded with the Duplicator's lid on), fingerprint f8c9f9c449920c80, player Philips DVP3050V; used as kirby_shielded_10min.ddd.flac at 40 MS/s, PAL, 4 cores.

| Build | Frames/s | Range | Runs | CPU s | Peak RAM | One hour of tape | vs tape-decode@generic |
|---|---|---|---|---|---|---|---|
| tape-decode native | 22.9 | 22.9-23.0 | 2 | 2414 | 730 MB | 65 min | 2.53x |
| tape-decode generic | 9.1 | 9.1-9.1 | 2 | 5814 | 747 MB | 2.8 h | 1.00x |
| tape-decode release | 9.9 | 9.9-9.9 | 2 | 5370 | 5049 MB | 2.5 h | 1.09x |
