# AMD Ryzen 7 5800X 8-Core Processor (Linux x86_64, 31 GB)

Sample: kirby_shielded_10min.ddd.flac (Kirby instructional video, ten minutes: minutes 30 to 40 of the capture, recorded with the Duplicator's lid on), fingerprint f8c9f9c449920c80, player Philips DVP3050V; used as kirby_shielded_10min.ddd.flac at 40 MS/s, PAL, 4 cores.

| Build | Frames/s | Range | Runs | CPU s | Peak RAM | One hour of tape |
|---|---|---|---|---|---|---|
| tape-decode native | 12.8 | 12.8-12.8 | 2 | 4129 | 732 MB | 117 min |
| ffmpeg release export | 98.7 | 94.1-103.4 | 2 | 1707 | 11172 MB | 15 min |
| ffmpeg generic export | 96.6 | 84.1-109.2 | 2 | 1718 | 10917 MB | 16 min |
| ffmpeg release mux | FAILED: this ffmpeg was built without libsoxr, which the final mux needs | | | | | |
| ffmpeg generic mux | 745.5 | 568.2-922.7 | 2 | 10 | 78 MB | 2 min |
| ffmpeg native | FAILED: build failed (curl: (35) Recv failure: Connection reset by peer [ERROR] Failed to download FFmpeg source [ERROR] FFmpeg build failed); see /mnt/1TB/bench-work/ffmpeg_native/build.log | | | | | |
