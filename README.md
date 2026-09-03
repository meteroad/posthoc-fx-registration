# Project page

Static, non-anonymous project page for the paper. It has no build step, backend,
analytics, or external JavaScript dependency.

Preview locally:

```bash
python3 -m http.server 18992 --directory project_page
```

Then open `http://127.0.0.1:18992/`.

## Contents

- `index.html`: page structure and paper-facing copy.
- `styles.css`: responsive layout.
- `app.js`: compact audio playback controls.
- `data.js`: audited example metadata and experiment values.
- `assets/audio`: ten curated CounterFX-200 examples in lossless FLAC.
- `assets/images`: paper-aligned result figures.

The examples include five known-topology and five hidden-topology cases. They
are curated demonstrations rather than an additional evaluation subset. Cases
in which another method outperforms Head@16 are retained to avoid showing only
favorable examples. Source recordings and Creative Commons licenses are linked
per case.

Paper and code links should be added only after public URLs are available.
