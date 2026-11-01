# Benchmark samples

Drop a capture here and name it on the command line:

```bash
python3 benchmark/bench.py --sample kirby-pal --variants tape-decode@native
python3 benchmark/bench.py --list-samples
```

`--sample` takes either a path or the name of a file in this folder (the `.ddd.flac` can be left off). The captures
themselves are not kept in git.

## Notes beside a sample

Put a `<name>.sample.json` next to the capture to say what it is. Everything in it is copied into the results, so a
published result identifies its sample.

```json
{
  "description": "Kirby instructional video, static scene",
  "standard": "ntsc",
  "player": "Panasonic AG-1980",
  "tape": "VHS, SP",
  "recorded": "2026-11-02",
  "notes": "one hour, no dropouts to speak of"
}
```

All fields are optional. `standard` (`pal` or `ntsc`) becomes the default for `--standard`. The results also record
the sample's length, size and a fingerprint (a hash of its first 64 MiB and its size), so two people can tell
whether they measured the same file.

## Disk space

A capture at 40 MS/s is about 120 GB an hour. A machine that cannot hold the whole thing can use a part of it:
`--seconds 600 --start 300` cuts ten minutes from the middle (that copy needs about 20 GB of free space in the
work folder).
