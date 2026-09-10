# CounterFX-200: Protocol and Configuration

This specification documents the existing frozen evaluation set, internally
versioned `pedalboard-fma-test-v0.1`. It does not introduce a new experiment
or describe the audio pairing used to train registration heads.

## Task and Inputs

Two adjacent, non-overlapping 10-second windows, A and B, come from the same
recording. The recording's existing processing is retained. For a known
generating chain `(c, theta)`, construct:

```text
System inputs:     A_source = A,  B_ref = R(B, c, theta)
Evaluation target: A_target = R(A, c, theta)
```

The system does not receive B or A_target. The public target manifest is for
evaluation and reproducibility, not an additional inference input. An empty
source chain means no *added* processing; it does not mean that A is dry.
No musical-section annotations are used to construct these evaluation windows.

Known topology supplies effect identities and their order, but withholds
continuous controls. Hidden topology withholds chain length, identities,
order, and controls. Different chains may produce similar sound; the primary
evaluation compares the resulting audio, not exact parameter recovery.

## Audio Selection

The set contains 200 excerpts from the official FMA-small **test** split.
Source identities, licenses, URLs, hashes, offsets, and screening measurements
are in [audio_manifest.csv](audio_manifest.csv). Audio is not redistributed here.

The license filter excludes missing licenses and NoDerivatives licenses, and
requires a recognized attribution, Creative Commons, CC0, or public-domain
marker. The resulting genre quotas are: Electronic 26, Experimental 26,
Folk 26, Hip-Hop 26, Instrumental 19, International 26, Pop 25, Rock 26.
These are not uniform quotas: the derivative-allowed Instrumental pool has
only 19 eligible tracks.

Within each genre, eligible tracks are sorted by the SHA-256 of
`"20270720:track_id"`. The first qualifying tracks fill that genre's quota.
Sources must decode to at least 28 seconds. Mono is duplicated to stereo;
more than two channels are rejected. Audio is converted to float32 and
resampled to 44,100 Hz when necessary.

The preferred pair is A = [5, 15) s and B = [15, 25) s. If it fails screening,
other feasible integer-second starts are tried in deterministic hash order
using `"20270720:track_id:start"`, always with `start_B = start_A + 10`.
The manifest offsets, rather than an assumed common offset, define each item.

Each window is independently normalized to -20 LUFS using pyloudnorm. Reject
nonfinite audio, invalid integrated loudness (including below -70 LUFS before
normalization), normalized RMS at or below -45 dBFS, or peak magnitude at or
above 1.0. At least 60% of non-overlapping 100-ms frames must have stereo RMS
above -55 dBFS. Test item identities are disjoint from the development set.

## Processor Library and Chain Prior

The canonical effect order and Bernoulli inclusion probabilities are:

| Effect ID | Inclusion probability |
|---|---:|
| highpass_filter | 0.35 |
| lowpass_filter | 0.25 |
| peak_filter | 0.60 |
| compressor | 0.55 |
| distortion | 0.15 |
| chorus | 0.30 |
| delay | 0.15 |
| reverb | 0.35 |

Draw one Bernoulli variable per effect. If the set is empty, select one effect
with probability proportional to the listed weights. If more than four are
active, choose four from that active set without replacement, weighted by
their inclusion probabilities. Otherwise retain the set. This is **not**
rejection sampling and does not use a separate uniform chain-length prior.
No effect repeats in a chain.

Sort the selected effects using one of four templates:

1. highpass_filter, lowpass_filter, peak_filter, compressor, distortion, chorus, delay, reverb
2. distortion, highpass_filter, lowpass_filter, peak_filter, compressor, chorus, delay, reverb
3. compressor, distortion, highpass_filter, lowpass_filter, peak_filter, chorus, delay, reverb
4. highpass_filter, lowpass_filter, peak_filter, distortion, compressor, chorus, delay, reverb

The deterministic target builder chooses the template by a hashed item seed
modulo four. Random sampling uses the four templates with equal probability.
The frozen accepted set contains 30 one-effect, 57 two-effect, 68 three-effect,
and 45 four-effect chains. These are realized counts, not specified priors.

The full 22 variable controls and their physical ranges are in
[parameter_ranges.csv](parameter_ranges.csv) and
[configuration.json](configuration.json). There are also two fixed reverb
controls: `dry_level = 0.5` and `freeze_mode = 0`.

For a uniform coordinate `u` in [0,1], linear sampling uses
`x = lower + u * (upper - lower)`; log-uniform sampling uses
`x = exp(log(lower) + u * (log(upper) - log(lower)))`.
The public target manifest records **physical** controls. Legacy normalized
fields in the internal target manifest use the wider plugin registry's linear
coordinates, not these benchmark-prior coordinates, and are intentionally
omitted to prevent accidental reinterpretation.

## Frozen Targets and Rendering

The audio seed is 20270720 and the effect seed is 20270722. Define
`H(parts...)` as the integer value of the first 16 hexadecimal characters of
SHA-256 of the colon-joined argument strings, modulo `2^32`.

- Activation generator: NumPy `default_rng(H(20270722, item_id, "activation"))`.
- Item seed: `H(20270722, item_id)`.
- Template index: `H(item_seed, "order") % 4`, using the zero-based list above.
- Parameter generator at attempt j: `default_rng(H(item_seed, "params", j))`.

Parameters are sampled in chain order and the parameter order in the locked
benchmark specification. For exact replay, use the accepted physical controls
and seeds in [target_chains.jsonl](target_chains.jsonl); the exported JSON/CSV
parameter listing order is not a random-number-consumption contract.

Targets are rendered using Spotify Pedalboard 0.9.23 at 44.1 kHz, with buffer
size 8,192 and reset enabled. The same chain and parameters are applied to A
and B. There is no output peak limiter, RMS matching, or output loudness
normalization. The input and output windows retain their original length.

Reject any nonfinite output or either output's peak magnitude at or above 1.
Otherwise require `min(Ld(A, A_target), Ld(B, B_ref)) >= 0.8`. If rejected,
redraw **parameters only**, retaining effect identities and order, for up to
256 attempts. Exhausting attempts aborts construction rather than silently
replacing the item. These checks precede model evaluation.

The frozen build reports one rejected audio candidate and 388 rejected target
parameter draws: 356 below the Ld threshold and 32 for clipping. The accepted
targets' minimum source-target Ld is approximately 0.80078. The salience filter
defines an evaluation distribution of changes detectable by this metric;
it is not a perceptual threshold for every possible effect.

The renderer lock records the public Pedalboard target backend and the
separately implemented CUDA candidate renderer, along with source hashes and
the chain-parity report hash. They are not the same underlying implementation.
The inherited renderer-lock version label refers to development; it is not
the version of the frozen test manifest.

## Evaluation

Ld is the three-resolution STFT distance used in the manuscript, combining
spectral convergence and log-magnitude L1 with Hann windows. FFT sizes are
1,024 / 2,048 / 512; hop sizes 120 / 240 / 50; window lengths 600 / 1,200 / 240.
Lower is better. Evaluate final outputs against A_target, never against the
different-content B_ref waveform. Representation similarity to the reference
is the verifier objective, not the reported ground-truth audio error.

For each fixed candidate pool, selected Ld is the error of the verifier's
choice; oracle Ld is the minimum available candidate error. Oracle reflects
coverage; selected minus oracle measures ranking error within that pool.
Global-random pools are shared across encoders to compare verifiers, while
head-centered pools are encoder-specific and compare complete systems.

Candidate budget N counts valid candidates scored, not necessarily all render
attempts. Rejected renders can increase actual calls. CMA-ES uses a
renderer-call budget. FX-set F1 compares unordered selected and target effect
sets, ignoring order and controls. Exact topology compares effect identities
and order, not continuous parameter equality. Unless otherwise specified,
objective-result confidence intervals use 20,000 paired item-level bootstrap
resamples; the listening study and Fx-Norm audit have their own protocols.

## Downloads and Provenance

- [Configuration](configuration.json): priors, four templates, all physical
  ranges, constraints, seeds, and renderer settings.
- [Audio manifest](audio_manifest.csv): original frozen 200-item source CSV.
- [Target manifest](target_chains.jsonl): physical controls and acceptance
  measurements for every item; no waveform data or hidden inputs for models.
- [Summary](summary.json): realized genre, chain-length, and effect counts.
- [Provenance](provenance.json): hashes of the original frozen files and the
  path-redacted renderer lock. Metadata are exported from the completed
  experiments, not inferred from current mutable defaults.
- [Checksums](checksums.sha256): hashes of the public files. Exported target
  and provenance files differ from their internal originals by design.

The [separate Fx-Normalization diagnostic](../normalization/protocol.md) tests
normalization on MUSDB18-HQ. Its data and results are not part of CounterFX-200.
