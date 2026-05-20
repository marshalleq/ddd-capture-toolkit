# VHS capture and decode quality guide (DomesdayDuplicator + vhs-decode)

A practical guide to producing clean VHS decodes with the Domesday Duplicator and vhs-decode pipeline. Covers two distinct sets of levers:

- **Part 1: Capture-side** — RF gain, level meter interpretation, lead-in timing. These determine the quality ceiling of the captured `.lds` file.
- **Part 2: Decode-side** — vhs-decode and ld-chroma-decoder parameters for fixing chroma dropouts ("B&W patches"), ringing, and related artefacts. These tune how the captured RF is converted into video.

Use Part 1 to ensure the capture is sound. Use Part 2 when the capture is already clean but visible artefacts remain in the decoded video.

---

## Part 1: Capture-side (gain and timing)

### Quick reference

| Setting | Value |
|---|---|
| **Ideal target (AC RMS)** | **0.22 – 0.30** (Excellent tier) |
| Acceptable range | 0.20 – 0.40 (OK or better) |
| Maximum safe RMS | 0.50 |
| Minimum without quality loss | ~0.18 |
| Capture start timing | Begin **before** the tape audibly engages |

If the DdD capture app's level meter reads above ~0.50, gain is too high and transients are clipping continuously. If it reads below ~0.15, gain is too low and quantization noise starts becoming visible in the decoded picture. Between those, you're fine — but lower-within-band consistently outperforms higher-within-band on the clipping metric.

#### Capture quality tier ladder

Empirically calibrated against side-by-side user comparison of test captures. The analyser tool (`capture_analysis.py`) reports the matching tier for any capture:

| Tier | Clipping rate | Meaning |
|---|---|---|
| **EXCELLENT** | < 0.01 % | Only unavoidable sync-pulse clipping; lots of headroom |
| **GOOD** | 0.01 – 0.02 % | Clean capture; minor transient clipping |
| **OK** | 0.02 – 0.05 % | Acceptable; more headroom would help |
| **FAIR** | 0.05 – 0.20 % | Usable but worth tightening |
| **MILD CLIPPING** | 0.20 – 0.50 % | Reduce gain |
| **HEAVY CLIPPING** | ≥ 0.50 % | Definitely reduce gain |
| **SIGNAL HOT** | (override) | RMS > 0.55 — too much amplification |
| **SIGNAL LOW** | (override) | RMS < 0.15 — quantization noise risk |

Override conditions take priority over the clipping ladder: a hot-but-not-yet-heavily-clipped capture still gets flagged as SIGNAL HOT, and a heavily clipped capture is reported as HEAVY CLIPPING regardless of RMS.

VHS sync pulses inherently clip at any reasonable gain setting (they're short, sharp, and at maximum carrier deviation by design), so 0 % clipping is not achievable or desirable. EXCELLENT represents the practical ceiling: low enough that essentially all clipping is sync-pulse only, with headroom for content transients.

### The level meter reads RMS, not peak

The single biggest pitfall in DdD capture setup is misreading the level meter. The DomesdayDuplicator capture app displays **AC RMS** of the captured 10-bit samples, normalised to the half-range (0..1 scale).

Community advice frequently states "aim for 0.7." That advice is correct **only if interpreted as peak amplitude**, not as RMS. Applied to an RMS reading, it produces continuous clipping.

#### The math

The DdD ADC is 10-bit unsigned (0..1023) with DC centre near 512. The RF carrier swings above and below that centre. An AC RMS reading of *R* on the 0..1 scale means the RMS of the AC component is R × 512 ADC counts.

For an FM-modulated RF carrier off a tape head, the crest factor (peak ÷ RMS ratio) is approximately 1.5 – 1.8. So expected peak deflection from centre is:

```
peak_deflection = R × 512 × crest_factor
```

The ADC can represent peak deflections up to ±512 before clipping. Working backwards:

| RMS reading | Peak deflection (crest factor 1.5) | Peak deflection (crest factor 1.8) | Result |
|---|---|---|---|
| 0.30 | ±230 | ±277 | Clean |
| 0.40 | ±307 | ±369 | Clean |
| 0.50 | ±384 | ±461 | Borderline |
| 0.60 | ±461 | ±553 | **Transients clip** |
| 0.70 | ±538 | ±645 | **Continuous clipping** |

At RMS 0.70, peaks are 5 – 26 % past the rails on every cycle. The ADC pins them at 0 or 1023, destroying the FM information they carried.

#### Empirical confirmation

Tested on the same hardware chain capturing the same tape:

| Setting | Measured clipping rate |
|---|---|
| RMS ≈ 0.70 | 1.71 % of samples clipped |
| RMS ≈ 0.32 | 0.04 % of samples clipped |

A 40× reduction in clipping from a correctly-interpreted level target.

### Clipping is asymmetric: a cliff, not a slope

Capture-side errors come in two forms with very different consequences.

#### Clipping (signal too hot)

When an analog input exceeds the ADC range, the sample is pinned at 0 or 1023. The original analog value is lost permanently — a peak that was 1.05× full-scale and a peak that was 1.50× full-scale both become exactly the same number. No subsequent processing can recover the difference.

For FM-encoded VHS RF, clipping primarily damages **reference-level detection**. vhs-decode measures the sync-tip and blanking levels in the demodulated waveform to calibrate the rest of the decode. If sync tips are clipped, level detection fails with errors like:

```
Level detection failed - sync or blank is None
Unable to determine start of field - dropping field
Possibly skipped field (Two fields with same isFirstField in a row)
```

#### Quiet capture (signal too low)

When a signal fills only part of the ADC range, fewer bits of resolution are used. Quantization noise becomes proportionally larger relative to the signal, and analog noise from the amp/cable/head is captured at proportionally lower resolution.

For a 10-bit ADC and typical VHS RF:

| AC RMS | Effective bits used | Quantization SNR | Visible effect |
|---|---|---|---|
| 0.50 | ~9 | ~56 dB | None |
| 0.32 | ~8.5 | ~52 dB | None |
| 0.20 | ~7.5 | ~46 dB | Slight graininess |
| 0.10 | ~6.5 | ~40 dB | Noticeable graininess + chroma speckle |
| 0.05 | ~5.5 | ~34 dB | Picture quality degrades |

Below RMS 0.05 the FM demodulator hits threshold effects and the decode may fail entirely. Above 0.15, quality is essentially unaffected.

#### Why the asymmetry matters

| | Lost data | Recoverable? |
|---|---|---|
| Clipping | Yes — samples destroyed at the rails | **No, ever** |
| Quiet capture | No — waveform shape preserved | **Yes — within demod limits** |

The operational rule: **always stay clear of the clipping cliff, even if it means accepting a few dB you could theoretically have used.** Headroom is cheap; clipping is permanent.

### How well vhs-decode tolerates clipping (and why)

FM demodulation extracts information from the **timing of zero crossings**, not from waveform amplitude. Clipping flattens peaks but barely shifts zero crossings, so the frequency content (which encodes brightness and colour) survives even heavy clipping.

What clipping does break is the level-detection algorithm. If the source recording has rock-solid sync (broadcast television, well-recorded prosumer equipment), the decoder can still measure sync-tip and blanking levels even with clipped peaks. If the source has marginal sync (consumer camcorder, worn tape, off-spec deck), clipping is the additional damage that pushes detection past the point of recovery.

#### Worked examples

| Capture | Clipping | Decode errors | Source quality | Result |
|---|---|---|---|---|
| Broadcast recording | 4.73 % | 3 | Clean | Excellent decode |
| 1980s camcorder | 1.71 % | 42,858 | Marginal | Lost first 4.5 min of tape |
| Same camcorder, fixed gain | 0.04 % | 26 | Same as above | Clean decode end-to-end |

The broadcast capture decodes beautifully despite 4.73 % clipping because its underlying signal is bulletproof. The camcorder capture at one-third the clipping rate fails catastrophically because the signal had no margin to lose.

**Practical implication:** the 0.30 – 0.45 sweet spot exists because you don't know in advance which sources will be marginal. Headroom is insurance against worst-case material.

### The lead-in rule

vhs-decode builds its sync-tip and blanking-level references from the **start of the capture file**, then tracks from there. If the first seconds are degraded, the level detector never establishes calibration.

Symptoms of getting this wrong:

- The decode log grows for many minutes while `.tbc` output files remain at 0 bytes
- "Level detection failed - sync or blank is None" errors accumulate
- Short captures fail completely with no decoded frames
- Long captures eventually "muscle through" but skip many frames at the start

#### The rule

**Start the DdD capture half a second to a second before the tape audibly engages.** Pre-roll material — head-switching snow, empty-section noise, lead-in garbage — is preferred over starting on recorded content.

#### Why pre-roll helps

The decoder needs a clean window to establish reference levels. It doesn't need *picture quality* — it needs *well-formed sync pulses*. Even snowy broadcast lead-in has properly-formed horizontal and vertical sync because the broadcast equipment puts them down regardless of picture content. Once calibrated, the decoder can ride through later degraded sections without losing lock.

#### Empirical confirmation

Two short captures of the same tape:

| Capture | Start timing | First locked frame | Errors |
|---|---|---|---|
| A | Begin when tape audibly engages | Frame 194 (~8 s) | 1,209 |
| B | Begin ~0.5 s before tape engages | Frame 32 (~1.3 s) | 197 |

Six times fewer errors and three and a half times more frames decoded, from pressing record slightly earlier.

### Verifying gain on existing captures

The DdD writes a JSON sidecar with every capture, containing:

- `clippedMaxSampleCount` — samples pinned at ADC max
- `clippedMinSampleCount` — samples pinned at ADC min
- `sampleCount` — total sample count

Clipping rate is computed as:

```
clipping % = (clippedMaxSampleCount + clippedMinSampleCount) / sampleCount × 100
```

Anything above 0.5 % is over-amplified and worth investigating. Anything above 1 % is heavily clipped.

#### Interactive analyser

The toolkit's `capture_analysis.py` (available in the VHS-Decode menu as "Analyse Capture Levels", or callable from the CLI) extracts a slice of a `.lds`/`.ldf` capture, unpacks it to signed 16-bit PCM, and reports clipping statistics plus AC RMS in the same 0..1 scale as the DdD level meter:

```
--- LEVELS (10-bit ADC, 0..1023, centre 512) ---
mean sample  : 508.8        (ideal centre: 512)
AC RMS       : 0.234        (DdD-style 0..1 normalised; aim ~0.30-0.45)

--- CLIPPING ---
total clipped: 1,031,959    (0.0430%)

--- VERDICT: OK (clipping 0.0430%, RMS 0.234) ---
```

The unpacked `.raw` is written alongside the original capture for direct waveform inspection in Audacity.

CLI usage:

```bash
python3 capture_analysis.py <file.lds> [skip_seconds=30] [duration_seconds=60]
```

#### Inspecting waveforms in Audacity

Open the unpacked `.raw` via File → Import → Raw Data with these settings:

| Setting | Value |
|---|---|
| Encoding | Signed 16-bit PCM |
| Byte order | Little-endian |
| Channels | 1 (mono) |
| Start offset | 0 bytes |
| Sample rate | Any (the actual is 40 MHz; the label only affects the time axis) |

The Analyze → Plot Spectrum view shows the FM carrier (~5 MHz for VHS) and the noise floor — useful for confirming the carrier is clean and centred.

#### What a healthy waveform looks like

A well-set capture shows:

- A **tight dense band** in the centre, occupying roughly ±0.3 on the ±1.0 scale — this is the steady RF carrier
- **Isolated needle-like spikes** reaching toward the rails — these are head-switching transients and dropouts, intrinsic to VHS playback
- **Visible whitespace** between the band and the rails — confirms headroom

Failure modes visible in the waveform:

- Body of the waveform **sitting against the rails** (no whitespace) → gain too high
- Body of the waveform **squeezed into a thin strip near zero** → gain too low (or signal genuinely weak)
- **Sustained flat-topping** rather than isolated needles → continuous clipping

### When to recapture

Re-capturing requires the original tape and ~real-time on the VCR. Each playback also incrementally wears the tape. So the recapture decision should be informed:

| Situation | Recommendation |
|---|---|
| Decoded picture has visible glitches or fails | **Recapture** — the existing capture is unusable as-is |
| Decoded picture looks clean, clipping < 0.5 % | **Leave it** — already extracted everything the analog signal had |
| Decoded picture looks clean, clipping 0.5 – 5 % | **Leave it** — recapture won't make a visible difference unless source was marginal |
| Decoded picture looks clean, but tape is precious | **Optional** — hedge against future re-decoder improvements |
| Tape is fragile / degrading | **Recapture sooner rather than later** — analog source quality is the limiting factor and it's getting worse |

The key principle: a clean decoded picture means analog noise was the limiting factor, not ADC quantization or clipping. Re-doing the capture cleaner won't improve what your eye can see.

---

## Part 2: Decode-side tuning

When the capture is clean (per Part 1) but the decoded video still shows artefacts, the levers move to the **decode** and **export** stages. Two common artefacts have specific remedies: regional chroma dropouts ("B&W patches") and edge ringing.

### Why VHS has these artefacts in the first place

VHS uses a divided-spectrum signal architecture:

- **Luma** (brightness) is FM-modulated onto a carrier in the 3.4 – 4.4 MHz range
- **Chroma** (colour) is heterodyned onto a separate **colour-under subcarrier** at ~627 kHz (PAL) or ~629 kHz (NTSC)
- Chroma sits *below* luma in the spectrum, at much lower amplitude (typically 20 – 30 dB quieter)

The chroma decoder is anchored to a **burst** — a short reference signal in the horizontal blanking interval that tells the decoder which phase the colour is in. If burst detection loses confidence, the decoder falls back to luma-only output to avoid producing incorrectly-tinted picture.

This architecture is the source of most of the format's characteristic artefacts. The pre-emphasis curve applied at record time (boosted highs, to improve SNR on tape) must be undone at decode time, and any mismatch shows as **ringing**. The low-amplitude chroma subcarrier sits close to the noise floor and can drop below detection threshold, showing as **regional B&W patches**.

### Regional B&W patches (chroma dropouts)

#### Mechanism

Three things can cause chroma to drop region-by-region while luma stays intact:

**1. Luma-chroma crosstalk on bright/high-contrast content.** When luma is at peak whites, the FM carrier hits maximum frequency deviation, which widens the carrier's *spectrum*. A wider luma spectrum encroaches on the chroma band and masks the chroma subcarrier. The decoder sees chroma buried under luma sidebands and discards it. This is the classic mechanism behind "bright scenes lose colour."

**2. Burst-phase loss.** If burst detection loses lock for a few lines (noise, tape dropout, low chroma SNR), those lines output as B&W. Visible as horizontal bands or whole regions going monochrome.

**3. Chroma SNR cliff.** Because chroma is 20 – 30 dB quieter than luma, it has correspondingly less SNR margin. Small amounts of capture-side noise or clipping that don't visibly affect luma can push chroma below the demodulator's threshold.

#### What capture-side fixes can and can't do

Reducing capture clipping (Part 1) helps with mechanisms 1 and 3:

- Less clipping → less luma harmonic splatter → less encroachment on the chroma band
- Less general noise → chroma above threshold more often

But residual contributions remain:

- Crosstalk on bright peaks is partly **baked into the original recording** (imperfect anti-crosstalk filters in the camera or recording deck)
- The chroma subcarrier's amplitude is fixed in the recording — if it was weak originally, capture can't recover it
- Burst-detection thresholds are decoder-side, not capture-side

If the new capture (with correct gain) still loses colour in highlights, the fixes move to decode and export parameters.

#### Decoder-side levers (in order of typical impact)

**`--chroma_nr <N>`** *(vhs-decode flag)*

Chroma noise reduction. Default depends on tape speed: 0 for SP, 1 for LP, 2 for EP. Bumping this up (3 or 4) makes chroma more stable on marginal sources at the cost of slightly softer colour detail. Per-project override via `project_flags.json`.

**`ld-chroma-decoder --decoder <type>`** *(export-side)*

vhs-decode produces a separated luma `.tbc` and chroma `.tbc.chroma`. The export step does the final chroma demod. PAL default is `transform2d`. Alternatives:

- `transform3d` — uses temporal information across frames; smoother chroma, but can produce motion-tracking artefacts on fast motion
- `pal2d` — simpler 2D decoder, sometimes more stable on very marginal sources

NTSC has analogous decoders: `ntsc2d`, `ntsc3d`, `ntsc1d`.

**`ld-chroma-decoder --chroma-gain <value>`**

Boosts chroma amplitude during demod. If chroma is consistently weak across the whole tape (not just highlights), a modest boost (1.5× – 2×) can keep it above burst-detection threshold more reliably. Too high oversaturates colour and can introduce its own artefacts.

**`ld-chroma-decoder --chroma-phase <value>`**

Phase offset adjustment. If colour is consistently shifted wrong (e.g. flesh tones look greenish or bluish), this is the lever. Rarely needed once decoder choice and gain are right.

**Burst detection / dropout correction tuning** *(advanced)*

Lower-level parameters in vhs-decode's RF config control how aggressively burst-phase is tracked and how aggressively dropouts are corrected. Less commonly exposed; usually only worth touching after the above haven't fully solved the issue.

#### Experimental procedure for chroma dropouts

The cheapest way to iterate is **Segment Mode** — re-decode a short range of frames around a known problem area, varying one parameter per run, comparing outputs side by side.

1. Identify a representative problem region (e.g. a specific bright scene that consistently loses colour). Note the frame numbers.
2. Configure `segment_config.py` for that range — e.g. `start_frame_pal: 14500, frame_count_pal: 1000` for ~40 seconds at PAL.
3. Run baseline decode + export with current settings; keep as reference.
4. Try `--chroma_nr 3` (or 4) — single flag change, decode + export the same segment.
5. If still problematic, try `--decoder transform3d` at export time on the same segment.
6. If colour is universally weak rather than just regionally dropping, try `--chroma-gain 1.8`.
7. Compare exports side by side. Pick the best.
8. Save the winning combination per-tape via `project_flags.json` for future use of similar tapes.

A full segment cycle (decode + export of 1000 frames) is ~10 – 20 minutes depending on hardware, so three or four variants can be tested in an evening.

### Ringing (edge halos and overshoot)

#### Mechanism

Ringing — bright/dark halos adjacent to sharp edges, sometimes with visible decaying oscillation — comes from several sources, in rough order of contribution:

**1. Pre-emphasis / de-emphasis mismatch.** VHS applies heavy pre-emphasis at record time (boosted highs to combat tape noise) and the decoder applies a complementary de-emphasis curve at playback. Any mismatch between the original recording's pre-emphasis and the decoder's de-emphasis produces ringing on edges. This is the **largest practical lever** because the decoder's curve is parameterised.

**2. The VHS format itself.** Limited luma bandwidth (~3 MHz) combined with the emphasis curve produces some ringing inherently. Can't be eliminated without losing detail.

**3. The original recording chain.** The camera or deck used to *record* the tape had its own filters that may have rung on edges. Permanently encoded; capture and decode can't touch it.

**4. The playback VCR.** Different decks have different bandpass and de-emphasis characteristics on their RF tap. Some ring more than others.

**5. Clipping.** Clipped FM creates harmonic content after demodulation that can read as ringing or sharpening. Smaller contributor than the above; addressed by Part 1.

#### Decoder-side levers

The de-emphasis curve in vhs-decode is parameterised by three values that appeared in the decode log's `RF Parameters` section:

```
deemph_tau   : 1.3e-06    (time constant)
deemph_mid   : 273755.82  (mid-frequency reference, Hz)
deemph_q     : 0.462088   (filter Q factor)
```

These have format-specific defaults (PAL vs NTSC, VHS vs S-VHS, etc.) but can be overridden via project flags or custom decode commands.

The other relevant flag is:

**`--high_boost <value>`** *(vhs-decode flag)*

Adjusts the luma high-frequency boost during demod. Default varies by tape speed. Raising it sharpens but increases ringing; lowering it softens but reduces ringing. Useful when the deemphasis curve is approximately right but needs fine adjustment.

#### Per-tape-format presets

The vhs-decode project ships with documented parameter sets for different recording profiles:

- Early VHS (1980s consumer recordings)
- Late VHS (1990s+)
- S-VHS
- Camcorder EP-mode
- Specific brand/model profiles where users have published tuned sets

These are in the vhs-decode wiki under the "Tape Type" or "Format" documentation. A tape from a 1980s Panasonic camcorder may benefit substantially from a profile that better matches the original recording's emphasis characteristics, where the default profile is tuned for later commercial VHS.

#### Experimental procedure for ringing

Same Segment Mode approach as for chroma, with different parameters:

1. Identify a frame range with sharp edges and visible ringing — high-contrast titles or text are ideal. Configure segment mode for that range.
2. Run baseline export with current settings; keep as reference.
3. Try `--high_boost -3` (negative values lower the boost). Compare.
4. If a documented tape-format preset exists for your source (e.g. a 1980s consumer camcorder profile in the vhs-decode wiki), try those `deemph_*` overrides next.
5. Compare visually. Ringing reduction usually trades against perceived sharpness — judge by which looks more natural rather than by which is "sharper."
6. Save the winning combination per-project.

For text-heavy or sharp-edge content (titles, on-screen graphics), aggressive ringing reduction is usually worth the slight softening. For motion-heavy natural content, milder adjustments preserve perceived detail.

### Shared workflow: Segment Mode parameter sweeps

Both artefact categories use the same iteration pattern, so it's worth describing the workflow once:

1. **Pick a representative segment.** Short (500 – 2000 frames), containing the artefact you want to fix, ideally with some clean reference content for comparison.
2. **Configure segment mode** in `segment_config.py` with the chosen frame range. The same range will apply to every variant you test.
3. **Set up project flag variants.** Use `project_flags.json` to define per-project decode/export overrides; create a temporary "test project" pointed at the same `.lds` for each parameter variant.
4. **Run the variants.** Decode → export each one to a separate output file. With segment mode this is fast — minutes per run, not hours.
5. **Compare side-by-side.** Open all variant outputs simultaneously; A/B them on the same frames. Look for the artefact you were targeting and judge the trade-offs (chroma stability vs softness; ringing reduction vs sharpness; etc.).
6. **Save the winning combination.** Update the *real* project's `project_flags.json` with the chosen parameters. Reuse on similar tapes (same vintage, same camera, same deck) by referencing the same flag set.

The iteration cost is roughly **15 minutes per parameter variant** for a 1000-frame segment on a modern CPU. So three or four variants is an evening's experimentation; full optimisation of a difficult tape might take a few sessions.

---

## Diagnostic checklist

Symptoms and where to look:

| Symptom | First suspect | Lever |
|---|---|---|
| Decode log grows but `.tbc` stays at 0 bytes | Capture lead-in too short | Recapture with pre-roll (Part 1) |
| "Level detection failed - sync or blank is None" | Capture clipping + marginal source | Recapture with lower gain (Part 1) |
| Position-varying mid-tape glitches | Capture clipping on bright transients | Recapture with lower gain (Part 1) |
| Decode succeeds but B&W patches in bright scenes | Chroma decoder threshold | `--chroma_nr`, alternative decoder (Part 2) |
| Consistently weak / desaturated colour | Chroma gain | `--chroma-gain` (Part 2) |
| Ringing/halos on sharp edges | De-emphasis mismatch | `--high_boost`, deemph profile (Part 2) |
| Soft picture but no ringing | Could trade some ringing for sharpness | Increase `--high_boost` (Part 2) |
| Specific tape vintage consistently problematic | Wrong format profile | Apply vintage-specific preset (Part 2) |

## Summary

1. **Capture side:** target AC RMS 0.30 – 0.45, start capture before tape audibly engages. Verify via `capture_analysis.py` or the JSON `clippedMaxSampleCount`/`clippedMinSampleCount` fields. Clipping is permanent damage; headroom is cheap insurance.
2. **Decode side — chroma dropouts:** try `--chroma_nr 3`, then alternative ld-chroma-decoder modes (`transform3d`, `pal2d`/`ntsc3d`), then `--chroma-gain` for systematically weak chroma. Iterate via Segment Mode.
3. **Decode side — ringing:** try `--high_boost` adjustments first, then look for tape-vintage-specific deemphasis profiles in the vhs-decode wiki. Iterate via Segment Mode.
4. **Save winning parameter combinations** in `project_flags.json` for reuse on similar tapes (same vintage, same source equipment).
5. **Don't reflexively recapture clean decodes.** Once analog noise floor is the limiting factor, capture-side improvements are invisible.
