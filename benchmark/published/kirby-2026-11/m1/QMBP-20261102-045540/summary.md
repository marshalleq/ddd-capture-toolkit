# Apple M1 Pro (Darwin arm64, 32 GB)

Sample: kirby_shielded_10min.ddd.flac (Kirby instructional video, ten minutes: minutes 30 to 40 of the capture, recorded with the Duplicator's lid on), fingerprint 29884c8c98cb1cb9, player Philips DVP3050V; used as kirby_shielded_10min.ddd.flac at 40 MS/s, PAL, 4 cores (unpinned on this platform).

| Build | Frames/s | Range | Runs | CPU s | Peak RAM | One hour of tape |
|---|---|---|---|---|---|---|
| vhs-decode v0.4.0 | 6.1 | 6.1-6.1 | 1 | 7203 | 2293 MB | 4.1 h |
| vhs-decode v0.4.0 on .lds | 6.4 | 6.4-6.4 | 1 | 6362 | 1613 MB | 3.9 h |
| vhs-decode March 2026 | FAILED: the decode finished but wrote no usable .tbc.json: Completed without handling any frames.; Error! Something went wrong when decoding or building json! | | | | | |
| vhs-decode March 2026 on .lds | 7.6 | 7.6-7.6 | 1 | 5964 | 1936 MB | 3.3 h |
