# Project page

Static, non-anonymous project page for the paper. It has no build step, backend,
analytics, or external JavaScript dependency.

Preview locally:

```bash
python3 -m http.server 18992 --bind 127.0.0.1
```

Then open `http://127.0.0.1:18992/`.

## Contents

- `index.html`: page structure and paper-facing copy.
- `styles.css`: responsive layout.
- `app.js`: compact audio playback controls.
- `data.js`: audited example metadata and experiment values.
- `assets/audio`: ten curated CounterFX-200 examples in lossless FLAC.
- `assets/images`: paper-aligned result figures.
- `assets/results/normalization`: the completed 100-clip same-content
  Fx-Normalization diagnostic, with tables, protocol, manifest, and per-clip
  metrics. This separate MUSDB18-HQ diagnostic contains no redistributed audio.

The examples include five known-topology and five hidden-topology cases. They
are curated demonstrations rather than an additional evaluation subset. Cases
in which another method outperforms Head@16 are retained to avoid showing only
favorable examples. Source recordings and Creative Commons licenses are linked
per case.

Paper and code links should be added only after public URLs are available.

## CounterFX-200 Specification

The existing benchmark section includes a native expandable
`#benchmark-specification` block. Its downloads under `assets/results/counterfx200`
document evaluation construction, separately from the normalization audit and
registration audio pairing. No audio or internal training data are included.

```bash
python3 scripts/build_counterfx_spec.py /path/to/paper/repository
python3 -m unittest discover -s tests -v
```

The exporter uses frozen target manifests and a saved formal-evaluation schema,
checks that their priors agree, and exports physical controls to avoid confusion
with legacy plugin-normalized metadata. It requires only the Python standard
library and does not run inference or rebuild the test set.

## Normalization Supplement

The public page is served from `gh-pages`. Its `#normalization` section is
static HTML, including the tables; expandable details require no JavaScript.
The displayed numbers and figure are generated from the completed audit, not
transcribed manually. To refresh that section from a completed formal run:

```bash
python3 scripts/build_normalization.py /path/to/completed/formal
python3 -m unittest discover -s tests -v
```

Only this export step needs NumPy and Matplotlib. It verifies the completion
and manifest hashes, rejects incomplete counts, removes machine-specific paths
from public metadata, and does not change the source run. It replaces only the
marked diagnostic block in `index.html`. The static site itself has no build
or Python dependency. The listening table is synchronized with manuscript
revision `d629a83` (28 listeners); the normalization supplement is independent
of that listening study.
