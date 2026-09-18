#!/usr/bin/env python3
"""Publish the completed normalization audit without changing its measurements."""

import argparse
import csv
import hashlib
import io
import json
from collections import Counter
from html import escape
from pathlib import Path

CONDITIONS = {
    "gain_minus6": "Gain -6 dB",
    "gain_plus6": "Gain +6 dB",
    "eq_minus6": "Peak EQ -6 dB",
    "eq_plus6": "Peak EQ +6 dB",
    "comp_ratio2": "Compression 2:1",
    "comp_ratio4": "Compression 4:1",
}
ENCODERS = {"relativefx": "RelFx", "fxencoderpp": "Fx-Encoder++", "afx_rep": "AFx-Rep"}
STEMS = ("bass", "drums", "vocals", "other")
BEGIN = "      <!-- BEGIN NORMALIZATION DIAGNOSTIC -->"
END = "      <!-- END NORMALIZATION DIAGNOSTIC -->"
PREFIX = "assets/results/normalization/"
LD = "<i>L</i><sub>d</sub>"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    return json.loads(path.read_text())


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True, allow_nan=False) + "\n")


def number(value):
    if abs(value) < 1e-6:
        return "&asymp;0" if value else "0"
    if abs(value) < 0.001:
        return f"{value:.2e}"
    return f"{value:.3f}"


def ci(stats):
    low, high = stats["ci95_song_bootstrap"]
    return f"[{number(low)}, {number(high)}]"


def table(caption, headers, rows):
    head = "".join(f'<th scope="col">{h}</th>' for h in headers)
    body = "\n".join(
        f'<tr><th scope="row">{row[0]}</th>'
        + "".join(f"<td>{cell}</td>" for cell in row[1:]) + "</tr>"
        for row in rows
    )
    label = escape(caption, quote=True)
    return (f'<div class="table-wrap" role="region" tabindex="0" aria-label="{label}">'
            f'<table><caption>{escape(caption)}</caption><thead><tr>{head}</tr></thead>'
            f'<tbody>{body}</tbody></table></div>')


def render_section(summary):
    conditions = summary["conditions"]
    main_rows, feature_rows, stem_rows, sensitivity_rows = [], [], [], []
    for name, label in CONDITIONS.items():
        before, after = conditions[name]["input"], conditions[name]["normalized"]
        main_rows.append([label, number(before["ld"]["mean"]), number(after["ld"]["mean"]),
                          ci(after["ld"]), number(after["ld_loudness_matched"]["mean"])])
        feature_rows.append([label] + [number(stats[metric]["mean"])
                            for metric in ("centered_band_rmse_db", "centered_envelope_rmse_db")
                            for stats in (before, after)])
        stem_rows.append([label] + [number(after["per_stem_ld"][stem]["mean"]) for stem in STEMS])
        unclipped = after["unclipped_ld_sensitivity"]
        delta = conditions[name]["paired_after_minus_before_ld"]
        sensitivity_rows.append([label, str(unclipped["n"]), number(unclipped["mean"]), ci(unclipped),
                                 number(delta["mean"]), ci(delta)])
    main_table = table("All 100 clips per intervention; mean audio distance.",
                       ["Intervention", f"Before {LD}", f"After {LD}", "After 95% CI",
                        f"After {LD}, loudness matched"], main_rows)
    feature_table = table("Acoustic feature differences, in dB (lower is closer).",
                          ["Intervention", "Spectral shape, before", "Spectral shape, after",
                           "Dynamic envelope, before", "Dynamic envelope, after"], feature_rows)
    stem_table = table("Mean audio distance after normalization; 25 clips per stem.",
                       ["Intervention"] + [stem.capitalize() for stem in STEMS], stem_rows)
    sensitivity_table = table("Clipping sensitivity and paired changes; intervals use song clusters.",
                               ["Intervention", "Unclipped n", f"Unclipped after {LD}", "95% CI",
                                f"After minus before {LD}, all clips", "Paired 95% CI"], sensitivity_rows)
    embeddings = []
    for encoder, label in ENCODERS.items():
        rows = []
        for name, condition_label in CONDITIONS.items():
            values = summary["embeddings"][encoder][name]
            before, after = values["input"], values["normalized"]
            rows.append([condition_label, number(before["mean"]), number(after["mean"]),
                         number(after["median"]), ci(after)])
        embeddings.append(f"<h4>{label}</h4>" + table(f"{label}: cosine distance on 100 clips per intervention.",
                          ["Intervention", "Before mean", "After mean", "After median", "After 95% CI"], rows))
    repeat = conditions["identity_repeat"]["normalized"]["ld"]
    return f'''      <section class="result-block result-detail" id="normalization" aria-labelledby="normalization-title">
        <details>
          <summary class="result-detail-summary">
            <span class="result-detail-title" id="normalization-title">Effect-neutralization audit</span>
            <span class="result-detail-description">Where Fx-Normalization removes processing differences and where residual differences remain</span>
          </summary>
          <div class="result-detail-body">
        <p>
          Does Fx-Normalization map different processing histories to a common
          state? This separate diagnostic uses {summary["items"]} ten-second clips from
          {summary["unique_songs"]} songs in the MUSDB18-HQ test split, with 25 clips each of
          bass, drums, vocals, and other. Clips were screened for activity and
          clipping before normalization, without using the eventual results.
        </p>
        <p>
          For each source <i>x</i>, we apply an intervention <i>F</i> and compare
          <i>F</i>(<i>x</i>) with <i>x</i> before normalization, then compare
          <i>N</i>(<i>F</i>(<i>x</i>)) with <i>N</i>(<i>x</i>) after normalization.
          Here <i>N</i> is the released Fx-Normalization pipeline. Both signals
          have the same musical content; <i>x</i> is not assumed to be dry or
          effect-neutral. This is not a CounterFX-200 subset.
        </p>
        {main_table}
        <p class="normalization-note">
          {LD} is the paper's three-resolution STFT audio distance, not an
          embedding distance. The last column is a secondary analysis after
          matching loudness. All 95% intervals below use 10,000 song-cluster
          bootstrap resamples, keeping clips from the same song together.
        </p>
        <p>
          <b>Gain differences are largely removed.</b> EQ differences also
          decrease in spectral shape, although nonzero audio distance remains.
          <b>Compression-induced differences persist</b> in both the audio
          distance and dynamic envelope. The diagnostic therefore does not
          justify treating normalized audio as a guaranteed common neutral
          state. It does not invalidate existing rendered triplet targets.
        </p>

        <details>
          <summary>Acoustic features and stem breakdown</summary>
          <figure class="paper-figure normalization-figure">
            <img src="{PREFIX}acoustic-differences.png" width="2000" height="760"
                 loading="lazy" alt="Before and after normalization: gain differences are largely removed, EQ spectral shape improves, and compression retains dynamic-envelope differences.">
            <figcaption>
              Means and 95% song-cluster intervals. Spectral shape is the
              centered five-band power profile; the dynamic envelope uses
              centered 20-ms RMS levels. The feature measures distinguish
              spectral and dynamic changes from overall gain.
              <a href="{PREFIX}acoustic-differences.pdf">Vector PDF</a>.
            </figcaption>
          </figure>
          {feature_table}
          {stem_table}
        </details>

        <details>
          <summary>Three frozen representations</summary>
          <p>
            These tables report cosine distance using each encoder's native
            input protocol. Fx-Encoder++ and AFx-Rep compare the embeddings of
            the baseline and its processed version. RelFx compares the
            baseline-to-version relation with the baseline-to-itself relation.
            After normalization, the baseline is <i>N</i>(<i>x</i>).
            Distances are not directly comparable across encoders.
          </p>
          {"".join(embeddings)}
          <p class="normalization-note">
            Compression retains nonzero distances in all three representations.
            EQ means and medians can differ substantially, especially for
            Fx-Encoder++; the median and per-item data are included to expose
            this variation. AFx-Rep's amplitude-normalizing preprocessing makes
            its gain distances near zero even before Fx-Normalization.
            Values with magnitude below 10<sup>&minus;6</sup> are shown as
            &asymp;0; tiny negative cosine distances are numerical noise.
          </p>
        </details>

        <details>
          <summary>Repeat controls and clipping sensitivity</summary>
          <p>
            Independent identity repeats, one per stem type, give mean
            {LD} = {number(repeat["mean"])} over {repeat["n"]} clips. The main results
            retain all selected clips, including cases with clipping during
            normalization. The sensitivity analysis excludes a pair if either
            signal clips at any normalization stage; no replacement clips are
            selected. Compression residuals remain in the unclipped subsets.
          </p>
          {sensitivity_table}
          <p class="normalization-note">
            Paired changes describe the mean, not every clip. Residual-distance
            intervals are not equivalence tests and do not set a perceptual
            threshold for neutrality.
          </p>
        </details>

        <details>
          <summary>Data selection and reproducibility</summary>
          <p>
            Sources are stereo, 44.1-kHz stems from
            <a href="https://zenodo.org/records/3338373">MUSDB18-HQ</a>.
            Selection uses one active 10-s window per song/stem, with fixed
            thresholds and seed 20260910. Each full stem receives common
            peak-only attenuation to at most &minus;12 dBFS before its
            intervention variants are created. EQ uses 1 kHz and Q = 0.707;
            compression uses 10-ms attack, 100-ms release, and a source-derived
            threshold shared by both ratios.
          </p>
          <p>
            The <a href="https://github.com/sony/FxNorm-automix/tree/916bf7e438b43f7f1dda24292dc3fd5d08e0f250">official pipeline</a>
            processes full stems through EQ, compression, panning, and loudness
            normalization, without reverb augmentation. Identical windows are
            cropped only afterward. The released MUSDB18 normalization
            statistics and all encoder weights are fixed; no models are
            trained in this diagnostic. Their hashes, software versions,
            selection rules, parameter values, and metric definitions are in
            the linked protocol and manifest. The exact song split used to
            create the released normalization statistics was not independently
            verified.
          </p>
          <p class="normalization-note">
            Downloads contain measurements and metadata only, not MUSDB18-HQ
            audio or model weights. This controlled diagnostic tests the
            normalization assumption for these interventions, not every
            possible effect or an encoder leaderboard.
          </p>
        </details>

        <div class="normalization-downloads" aria-label="Normalization diagnostic downloads">
          <a href="{PREFIX}protocol.md">Full protocol</a>
          <a href="{PREFIX}comparison_table.csv" download>Summary CSV</a>
          <a href="{PREFIX}summary.json" download>All statistics</a>
          <a href="{PREFIX}audio_metrics.csv" download>Per-clip audio metrics</a>
          <a href="{PREFIX}embedding_metrics.csv" download>Per-clip embedding distances</a>
          <a href="{PREFIX}manifest.json" download>Clip manifest</a>
          <a href="{PREFIX}provenance.json" download>Provenance</a>
          <a href="{PREFIX}checksums.sha256" download>Checksums</a>
        </div>
          </div>
        </details>
      </section>'''


def make_figure(summary, folder):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    plt.rcParams.update({"font.family": "DejaVu Serif", "font.size": 9})
    fig, axes = plt.subplots(1, 3, figsize=(10, 3.8), layout="constrained")
    metrics = [("ld", "Audio distance", "Mean $L_d$"),
               ("centered_band_rmse_db", "Spectral shape", "Centered band RMSE (dB)"),
               ("centered_envelope_rmse_db", "Dynamic envelope", "Centered envelope RMSE (dB)")]
    positions = np.arange(6)
    for axis, (metric, title, ylabel) in zip(axes, metrics):
        for offset, domain, label, color in [(-0.18, "input", "Before normalization", "#c86b25"),
                                            (0.18, "normalized", "After normalization", "#16709b")]:
            values = [summary["conditions"][name][domain][metric] for name in CONDITIONS]
            means = np.array([s["mean"] for s in values])
            intervals = np.array([s["ci95_song_bootstrap"] for s in values])
            error = np.maximum([means - intervals[:, 0], intervals[:, 1] - means], 0)
            axis.bar(positions + offset, means, width=0.34, yerr=error, capsize=2,
                     color=color, label=label, error_kw={"elinewidth": 0.7})
        axis.set_xticks(positions, ["Gain\n-6", "Gain\n+6", "EQ\n-6", "EQ\n+6", "Comp.\n2:1", "Comp.\n4:1"], fontsize=8)
        axis.set_title(title, fontsize=11)
        axis.set_ylabel(ylabel, fontsize=9)
        axis.set_ylim(bottom=0)
        axis.spines[["top", "right"]].set_visible(False)
        axis.grid(axis="y", color="#dddddd", linewidth=0.5)
        axis.set_axisbelow(True)
    fig.legend(*axes[0].get_legend_handles_labels(), loc="outside upper center", ncol=2,
               frameon=False, fontsize=9)
    fig.savefig(folder / "acoustic-differences.png", dpi=200)
    fig.savefig(folder / "acoustic-differences.pdf", metadata={"CreationDate": None, "ModDate": None})
    plt.close(fig)


def publish(run, site):
    complete = read_json(run / "COMPLETE.json")
    summary_bytes = (run / "summary.json").read_bytes()
    if digest(summary_bytes) != complete["summary_sha256"]:
        raise ValueError("Completed summary checksum mismatch")
    summary = json.loads(summary_bytes)
    manifest = read_json(run.parent / "manifest.json")
    lock = read_json(run / "protocol_lock.json")
    if digest((run.parent / "manifest.json").read_bytes()) != lock["manifest_sha256"]:
        raise ValueError("Locked manifest checksum mismatch")
    if summary["items"] != 100 or complete["items"] != 100 or len(manifest["items"]) != 100:
        raise ValueError("Only the completed 100-clip formal run may be published")
    if set(summary["embeddings"]) != set(ENCODERS):
        raise ValueError("Missing encoder result")
    if Counter(item["stem"] for item in manifest["items"]) != Counter(dict.fromkeys(STEMS, 25)):
        raise ValueError("Stem balance does not match the formal protocol")

    folder = site / PREFIX
    folder.mkdir(parents=True, exist_ok=True)
    for filename in ("summary.json", "comparison_table.csv", "audio_metrics.csv", "embedding_metrics.csv"):
        data = (run / filename).read_bytes()
        if any(root in data for root in (b"/data/workspace/", b"/root/", b"/data2/")):
            raise ValueError(f"Unexpected machine path in {filename}")
        if filename.endswith(".csv"):
            rows = list(csv.DictReader(io.StringIO(data.decode())))
            expected = {"comparison_table.csv": 6, "audio_metrics.csv": 1408, "embedding_metrics.csv": 4224}[filename]
            if len(rows) != expected:
                raise ValueError(f"Incomplete CSV: {filename}")
        (folder / filename).write_bytes(data)

    # The public manifest keeps source identities and hashes, not machine paths.
    public_manifest = {key: manifest[key] for key in ("seed", "per_stem", "selection", "unique_songs", "selection_audit_sha256")}
    public_manifest["source_split"] = "MUSDB18-HQ/test"
    public_manifest["original_manifest_sha256"] = lock["manifest_sha256"]
    public_manifest["items"] = []
    for item in manifest["items"]:
        row = {key: value for key, value in item.items() if key != "source"}
        row["source"] = f'test/{item["song"]}/{item["stem"]}.wav'
        public_manifest["items"].append(row)
    write_json(folder / "manifest.json", public_manifest)
    public_lock = {key: value for key, value in lock.items() if key != "metric_and_encoder_source_sha256"}
    public_lock["metric_and_encoder_source_sha256"] = {
        "/".join(Path(path).parts[-2:]): value
        for path, value in lock["metric_and_encoder_source_sha256"].items()
    }
    models = read_json(run / "embedding_provenance.json")
    provenance = {
        "complete": complete,
        "protocol_lock": public_lock,
        "compute_environment": read_json(run / "compute_environment.json"),
        "encoders": {name: {"label": ENCODERS[name], "checkpoint_sha256": values["sha256"]}
                     for name, values in models.items()},
        "public_manifest_note": "Machine paths replaced with dataset-relative paths; original manifest hash retained for provenance.",
    }
    write_json(folder / "provenance.json", provenance)
    make_figure(summary, folder)
    checksums = [f"{digest(path.read_bytes())}  {path.name}" for path in sorted(folder.iterdir())
                 if path.is_file() and path.name != "checksums.sha256"]
    (folder / "checksums.sha256").write_text("\n".join(checksums) + "\n")
    index = site / "index.html"
    original = index.read_text()
    if original.count(BEGIN) != 1 or original.count(END) != 1:
        raise ValueError("Expected exactly one diagnostic insertion point")
    start, rest = original.split(BEGIN)
    _, end = rest.split(END)
    index.write_text(start + BEGIN + "\n" + render_section(summary) + "\n" + END + end)
    print(f"Published {summary['items']} clips, {summary['unique_songs']} songs, {len(ENCODERS)} encoders to {folder}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path, help="Completed formal run directory")
    parser.add_argument("--site", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    publish(args.run, args.site)
