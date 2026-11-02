# Thermal test: Apple M2 (macOS 27.0.1, 16 GB)

Run on 2026-11-02T14:36:16+13:00 by quentinj with toolkit unknown (not a git checkout).

**Cool baseline.** Idle for 20 minutes first (load average 2.37 falling to 0.99); thermal pressure Nominal; the short probe decoded at 29.79 fps.

**Slowing began 3.7 minutes into the load** (CPU clock under 90% of 2974 MHz for two minutes); the early speed was 24.38 fps. The load ran 25.7 minutes in all.

macOS first reported thermal pressure Moderate 2.2 minutes into the load.

Straight after the load the probe ran at 23.05 fps. It was back to within 5% of the cool figure after 6.4 minutes idle.

| Minutes into load | Decode fps | CPU clock (MHz) | Thermal pressure |
|---|---|---|---|
| 0 to 5 | 23.8 | 3003 | Heavy, Moderate, Nominal |
| 5 to 10 | 10.8 | 2570 | Heavy |
| 10 to 15 | 10.6 | 2507 | Heavy |
| 15 to 20 | 18.1 | 2457 | Heavy |
| 20 to 25 | 16.4 | 2412 | Heavy |
| 25 to 30 | 10.2 | 2391 | Heavy |

| Minute | Probe | fps |
|---|---|---|
| 20.65 | cool | 29.79 |
| 47.16 | straight after the load | 23.05 |
| 52.77 | 6 min after the load | 30.66 |
