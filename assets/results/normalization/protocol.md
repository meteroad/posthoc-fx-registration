# Effect-Normalization Diagnostic

Completed formal run, 10 September 2026. This diagnostic is separate from
CounterFX-200. It tests whether differently processed versions of the **same
content** converge after Fx-Normalization, not whether different songs acquire
identical embeddings. No source is assumed to be dry or effect-neutral.

## Comparison

Let `x` be a source stem after common input attenuation, `F` an intervention,
and `N` the released normalization pipeline. The before comparison is
`F(x)` versus `x`; the after comparison is `N(F(x))` versus `N(x)`.
Normalization processes full stems. Measurements use the same 10-second
window in both signals, cropped after processing.

## Sources and Selection

- Dataset: [MUSDB18-HQ](https://zenodo.org/records/3338373), official test split,
  stereo 44.1 kHz. The 100 clips cover 49 songs, with 25 clips each of bass,
  drums, vocals, and other. At most one clip per song/stem.
- Seed: 20260910. For each stem type in the order bass, drums, vocals, other,
  a NumPy generator with `seed + stem_index` permutes the sorted song list.
  One eligible window is sampled uniformly per eligible song until 25 are
  selected. Clips are not ranked by post-normalization error.
- Candidate windows: 10 seconds, scanned every 5 seconds, at least 5 seconds
  from either recording boundary. Entire source files must be finite stereo
  44.1-kHz audio.
- Eligibility: RMS at least -35 dBFS; integrated loudness at least -35 LUFS;
  at least 80% of 250-ms blocks have RMS at least -45 dBFS; no silent run
  longer than 1 second; at most 0.1% of samples have magnitude at least 0.999.
- Thresholds were fixed before normalization. Selection did not use normalized
  audio or embedding distances, and failed outcomes were not replaced.
- Source-only headroom: multiply each full stem by
  `min(1, 10^(-12/20) / source_peak)`. All variants share this attenuation;
  there is no per-variant limiter or input loudness normalization.

The [public manifest](manifest.json) records source identities, source hashes,
window offsets, screening measures, headroom gains, and compressor thresholds.
Machine-specific paths have been replaced with dataset-relative paths. The
original private manifest hash is retained as a provenance identifier; it is
not the hash of the path-redacted public manifest.

## Interventions

| Condition | Parameters |
|---|---|
| Identity | No added processing |
| Gain -6 / +6 dB | Constant gain |
| Peak EQ -6 / +6 dB | 1,000 Hz, Q = 0.707 |
| Compression 2:1 / 4:1 | Attack 10 ms, release 100 ms |

Interventions use Pedalboard 0.9.23. Each compressor threshold is derived once
from the common-attenuated, full original stem: compute stereo RMS in 20-ms
blocks, retain blocks above -60 dBFS, take the 75th percentile in dB and
subtract 6 dB. Both ratios use this same threshold. Actual values are in the
manifest. Each clip has all seven conditions. The first selected clip of each
stem also has an independently processed identity repeat, giving 704
normalization outputs in total.

## Normalization Implementation

We use the released [Sony FxNorm-automix pipeline](https://github.com/sony/FxNorm-automix/tree/916bf7e438b43f7f1dda24292dc3fd5d08e0f250),
commit `916bf7e438b43f7f1dda24292dc3fd5d08e0f250`, with the official
`trainings/features/features_MUSDB18.npy` statistics. The statistics file and
upstream source hashes are recorded in [provenance.json](provenance.json).
The exact contributing song split of those released statistics was not
independently established; no train-only provenance is asserted.

The order is EQ, compression, panning, and loudness normalization. Reverb
augmentation is disabled. Inputs are PCM32, upstream PCM16 intermediate
outputs are preserved, and final 10-second analysis crops are floating-point
WAV. Before measurements use the actual quantized input passed to the pipeline.
Alignment, length, and finiteness are checked at output.

Upstream source is unchanged. Two compatibility wrappers remove the deprecated
`firwin2(nyq=None)` argument and map positional `librosa.util.frame` arguments
to keywords. They do not replace the normalization algorithm. Normalization
runs on CPU; audio metrics and frozen encoders use an NVIDIA L20 GPU.
Software versions and checkpoint hashes are included in provenance.json.
No model is trained in this experiment.

## Measurements

**Audio distance.** `Ld` is the manuscript's three-resolution STFT distance.
FFT sizes are `(1024, 2048, 512)`, hop lengths `(120, 240, 50)`, and Hann window
lengths `(600, 1200, 240)` at 44.1 kHz. For each resolution, sum spectral
convergence (Frobenius magnitude error divided by baseline magnitude norm)
and mean absolute log-magnitude error, then average the three resolutions.
Magnitude is `sqrt(max(real^2 + imag^2, 1e-8))`. The baseline is `x` before
and `N(x)` after. Stereo channels are included in each per-item reduction.

**Loudness-matched distance.** As a secondary check only, match each variant's
integrated loudness to its baseline, then attenuate both by the same factor
if needed to keep peak magnitude at most 0.7 before computing Ld. This does
not alter the primary measurements or saved normalized audio.

**Spectral shape.** Welch spectra use 4,096-sample segments with 2,048 overlap.
Average power over channels and frequency bins in five bands: 20-125,
125-500, 500-2,000, 2,000-8,000, and 8,000-20,000 Hz. Convert to dB with a
power floor of `1e-15`, subtract each signal's mean across bands, and measure
the RMSE between these centered five-band profiles.

**Dynamic envelope.** Compute stereo RMS in 20-ms blocks, convert to dB with
an amplitude floor of `1e-12`, subtract each signal's temporal mean, and
measure the RMSE between the centered envelopes. Absolute LUFS and crest
factor differences are also included in the per-clip data.

**Embedding distance.** Fx-Encoder++ and AFx-Rep use
`1 - cosine(E(baseline), E(variant))`. AFx-Rep uses its native amplitude
preprocessing and normalized mid embedding. RelFx uses
`1 - cosine(f_rel(baseline, baseline), f_rel(baseline, variant))`.
The baseline changes from `x` to `N(x)` between the before and after domains.
Each encoder's native preprocessing is retained. These different geometries
are not a cross-model accuracy scale. Values near zero, including tiny
negative values, can reflect floating-point roundoff; raw values are retained.

## Statistics and Controls

- Main estimates are item-weighted means across 100 clips per intervention.
  All six non-identity interventions are reported, including successful gain
  normalization. Embedding tables also show medians.
- 95% percentile intervals use 10,000 song-cluster bootstrap resamples. Songs
  are drawn with replacement and all clips from a drawn song stay together;
  each draw's estimate is its item-weighted mean. The paired after-minus-before
  analysis uses the same item pairing before resampling songs.
- Intervals estimate residual magnitude or a paired mean change. They are not
  equivalence tests or calibrated perceptual thresholds.
- Independent identity repeats cover four clips, one per stem type, and give
  mean Ld = 0. Identity/self comparisons for every clip are also retained.
- Clipping is measured before each normalization stage is written to PCM16:
  samples below -1 or above `32767/32768` are flagged. The main result retains
  these cases. The unclipped sensitivity subset excludes a pair if either
  baseline or variant has any flagged sample at any stage. No failed or
  high-error outcome is substituted. Subset sizes are 96-97, depending on
  intervention.

## Interpretation and Files

Gain differences are largely removed. EQ spectral shape improves, despite
residual STFT differences and some tail-sensitive embedding means.
Compression retains acoustic and representation differences, including in
unclipped subsets. Thus this pipeline should not automatically be treated as
an exact common-neutral-state constructor for these processing histories.
This is not a claim that every normalization task fails, nor does it invalidate
the exact rendered targets in existing triplet evaluations.

- [comparison_table.csv](comparison_table.csv): six intervention summaries.
- [summary.json](summary.json): all statistics, intervals, stem breakdowns,
  identity controls, and sensitivity subsets.
- [audio_metrics.csv](audio_metrics.csv): 1,408 rows, one per item/condition/domain.
- [embedding_metrics.csv](embedding_metrics.csv): 4,224 rows across three encoders.
- [manifest.json](manifest.json): 100 selected clip records and sampling settings.
- [provenance.json](provenance.json): completion marker, protocol lock, versions,
  source and model hashes; local paths omitted.
- [checksums.sha256](checksums.sha256): hashes of published diagnostic artifacts.

This release includes measurements and metadata, not source audio or model
weights. Obtain MUSDB18-HQ separately under its dataset license. The website
exporter checks the completed summary and locked manifest before publication;
it does not rerun inference or modify the frozen experimental results.
