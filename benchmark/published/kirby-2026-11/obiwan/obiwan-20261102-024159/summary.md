# AMD Ryzen 9 9950X3D 16-Core Processor (Linux x86_64, 123 GB)

Sample: kirby_shielded_10min.ddd.flac (Kirby instructional video, ten minutes: minutes 30 to 40 of the capture, recorded with the Duplicator's lid on), fingerprint f8c9f9c449920c80, player Philips DVP3050V; used as kirby_shielded_10min.ddd.flac at 40 MS/s, PAL, 4 cores.

| Build | Frames/s | Range | Runs | CPU s | Peak RAM | One hour of tape |
|---|---|---|---|---|---|---|
| vhs-decode v0.4.0 | 9.2 | 9.2-9.2 | 1 | 4171 | 1377 MB | 2.7 h |
| vhs-decode v0.4.0 on .lds | 9.8 | 9.8-9.8 | 1 | 3800 | 1239 MB | 2.5 h |
| vhs-decode efc3818f | FAILED: the decode finished but wrote no usable .tbc.json: Completed without handling any frames.; Error! Something went wrong when decoding or building json! | | | | | |
| vhs-decode efc3818f on .lds | 13.0 | 13.0-13.0 | 1 | 3072 | 1210 MB | 115 min |
