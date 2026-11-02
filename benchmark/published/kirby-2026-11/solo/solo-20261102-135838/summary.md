# AMD Ryzen 7 5800X 8-Core Processor (Linux x86_64, 31 GB)

Sample: kirby_shielded_10min.ddd.flac (Kirby instructional video, ten minutes: minutes 30 to 40 of the capture, recorded with the Duplicator's lid on), fingerprint f8c9f9c449920c80, player Philips DVP3050V; used as kirby_shielded_10min.ddd.flac at 40 MS/s, PAL, 4 cores.

| Build | Frames/s | Range | Runs | CPU s | Peak RAM | One hour of tape |
|---|---|---|---|---|---|---|
| tape-decode native | 12.7 | 12.7-12.8 | 2 | 4147 | 742 MB | 118 min |
| ffmpeg release export | 94.0 | 89.7-98.3 | 2 | 1675 | 10923 MB | 16 min |
| ffmpeg native export | 102.2 | 100.3-104.1 | 2 | 1698 | 11016 MB | 15 min |
| ffmpeg generic export | 94.4 | 85.9-102.8 | 2 | 1715 | 10919 MB | 16 min |
| ffmpeg release mux | FAILED: this ffmpeg was built without libsoxr, which the final mux needs | | | | | |
| ffmpeg native mux | 274.4 | 197.0-351.8 | 2 | 10 | 75 MB | 5 min |
| ffmpeg generic mux | 394.4 | 220.5-568.3 | 2 | 10 | 76 MB | 4 min |
