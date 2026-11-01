# AMD Ryzen 9 9950X3D 16-Core Processor (Linux x86_64, 123 GB)

Sample: kirby_shielded_10min.ddd.flac (Kirby instructional video, ten minutes: minutes 30 to 40 of the capture, recorded with the Duplicator's lid on), fingerprint f8c9f9c449920c80, player Philips DVP3050V; used as kirby_shielded_10min.ddd.flac at 40 MS/s, PAL, 4 cores.

| Build | Frames/s | Range | Runs | CPU s | Peak RAM | One hour of tape |
|---|---|---|---|---|---|---|
| tape-decode native | 22.9 | 22.8-23.0 | 2 | 2413 | 734 MB | 65 min |
| ffmpeg release export | FAILED: exit code 1:     from tbc_video_export.__main__ import main; ModuleNotFoundError: No module named 'tbc_video_export' | | | | | |
| ffmpeg native export | FAILED: exit code 1:     from tbc_video_export.__main__ import main; ModuleNotFoundError: No module named 'tbc_video_export' | | | | | |
| ffmpeg release mux | FAILED: no exported video to mux (the export step failed) | | | | | |
| ffmpeg native mux | FAILED: no exported video to mux (the export step failed) | | | | | |
| ffmpeg generic | FAILED: build failed (curl: (28) Failed to connect to ffmpeg.org:443 after 135933 ms: Could not connect to server [ERROR] Failed to download FFmpeg source [ERROR] FFmpeg build failed); see /mnt/nvme2tb/bench-work/ffmpeg_generic/build.log | | | | | |
