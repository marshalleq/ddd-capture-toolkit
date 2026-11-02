# AMD Ryzen 9 9950X3D 16-Core Processor (Linux x86_64, 123 GB)

Sample: kirby_shielded_10min.ddd.flac (Kirby instructional video, ten minutes: minutes 30 to 40 of the capture, recorded with the Duplicator's lid on), fingerprint f8c9f9c449920c80, player Philips DVP3050V; used as kirby_shielded_10min.ddd.flac at 40 MS/s, PAL, 4 cores.

| Build | Frames/s | Range | Runs | CPU s | Peak RAM | One hour of tape |
|---|---|---|---|---|---|---|
| tape-decode native | 22.9 | 22.8-22.9 | 2 | 2410 | 742 MB | 66 min |
| ffmpeg release export | 200.6 | 200.6-200.7 | 2 | 1310 | 21269 MB | 7 min |
| ffmpeg native export | 200.6 | 200.6-200.7 | 2 | 1365 | 21405 MB | 7 min |
| ffmpeg generic export | 200.5 | 200.5-200.6 | 2 | 1350 | 21054 MB | 7 min |
| ffmpeg release mux | FAILED: this ffmpeg was built without libsoxr, which the final mux needs | | | | | |
| ffmpeg native mux | 2458.7 | 2457.4-2460.0 | 2 | 8 | 79 MB | 1 min |
| ffmpeg generic mux | 2702.6 | 2452.0-2953.2 | 2 | 8 | 78 MB | 1 min |
