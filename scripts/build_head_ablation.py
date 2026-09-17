#!/usr/bin/env python3
"""Publish verified head-pool audit tables without private paths or training data."""
import argparse
import hashlib
import html
import json
from pathlib import Path

BEGIN = "<!-- BEGIN HEAD ABLATION -->"
END = "<!-- END HEAD ABLATION -->"
NAMES = {"relativefx": "RelFx", "fxencoderpp": "Fx-Encoder++", "afxrep": "AFx-Rep"}
TOPOLOGIES = {"known": "Known", "unknown": "Hidden"}
FILES = ("ablation.csv", "paired_contrasts.csv", "pool_accounting.csv",
         "center_audit.csv", "rejected_centers.csv")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def public_data(report):
    result = {key: report[key] for key in
              ("tables", "contrasts", "center_acceptance", "common_valid_counts", "pool_accounting")}
    result["protocol"] = {key: report["protocol"][key] for key in
                          ("n1", "valid_center", "common_valid_center", "missing", "bootstrap",
                           "resamples", "bootstrap_seed", "direction", "scope", "render_accounting")}
    result["candidate_seed"] = 20270724
    result["sources_sha256"] = {
        name: {key: value["sha256"] for key, value in run["inputs"].items()}
        for name, run in report["inputs"].items()}
    return result


def table(headers, rows):
    body = []
    for row in rows:
        cells = [f"<th scope=\"row\">{html.escape(str(row[0]))}</th>"]
        cells += [f"<td>{html.escape(str(v))}</td>" for v in row[1:]]
        body.append("<tr>" + "".join(cells) + "</tr>")
    return ("<div class=\"table-wrap\"><table><thead><tr>" +
            "".join(f"<th scope=\"col\">{html.escape(v)}</th>" for v in headers) +
            "</tr></thead><tbody>" + "\n".join(body) + "</tbody></table></div>")


def render(data):
    rows = []
    for encoder in NAMES:
        for topology in TOPOLOGIES:
            group = [r for r in data["tables"] if r["subset"] == "all_200"
                     and r["encoder"] == encoder and r["topology"] == topology]
            assert len(group) == 3 and all(r["n_items"] == 200 for r in group)
            group.sort(key=lambda r: r["budget"])
            rows.append([NAMES[encoder], TOPOLOGIES[topology]] +
                        [f"{r['selected_ld_mean']:.3f} / {r['oracle_ld_mean']:.3f}" for r in group])
    full = table(["Encoder", "Topology", "Head@1", "Head@16", "Head@512"], rows)
    cost_rows = [[NAMES[r["encoder"]], TOPOLOGIES[r["topology"]],
                  f"{r['center_acceptance_rate']:.1%}", f"{r['fallback_rate']:.1%}",
                  f"{r['full_pool_attempts_mean']:.2f}", f"{r['pooled_rejection_rate']:.2%}",
                  f"{r['unused_valid_renders_mean']:.2f}"] for r in data["pool_accounting"]]
    costs = table(["Encoder", "Topology", "Center accepted", "Fallback", "Mean attempts",
                   "Rejected / attempts", "Mean surplus valid"], cost_rows)
    diagnostic_rows = []
    for r in data["contrasts"]:
        if r["subset"] == "common_valid_center" and r["contrast"] == "N16_minus_N1":
            diagnostic_rows.append([NAMES[r["encoder"]], TOPOLOGIES[r["topology"]], r["n"],
                                    f"{r['delta_mean']:+.4f} [{r['ci95_low']:+.4f}, {r['ci95_high']:+.4f}]"])
    diagnostics = table(["Encoder", "Topology", "Items", "Head@16 minus Head@1 [95% CI]"], diagnostic_rows)
    downloads = "\n".join(f'<a href="assets/results/head-ablation/{name}" download>{label}</a>'
                           for name, label in (
                               ("ablation.csv", "All ablation tables"),
                               ("paired_contrasts.csv", "Paired intervals"),
                               ("pool_accounting.csv", "Render accounting"),
                               ("center_audit.csv", "Per-item center audit"),
                               ("rejected_centers.csv", "Rejected centers"),
                               ("summary.json", "Protocol and results"),
                               ("checksums.sha256", "Checksums")))
    return f'''<section class="result-block" id="head-ablation" aria-labelledby="head-ablation-title">
        <h3 id="head-ablation-title">Head-Pool Ablation</h3>
        <p>
          Head@1 scores one valid proposal: the predicted center when valid,
          otherwise the first valid head-centered sample. It performs no
          multi-candidate ranking. Head@16 and Head@512 select from larger
          pools. Each cell reports selected / oracle mean <i>L</i><sub>d</sub>
          over all 200 items; lower is better. Pools are encoder-specific.
        </p>
        {full}
        <p>
          RelFx and Fx-Encoder++ improve on Head@1 at 16 candidates. AFx-Rep
          improves oracle error but not mean selected error at that budget:
          better coverage does not guarantee better selection. This comparison
          assesses proposal expansion together with verification, not the
          verifier in isolation. Oracle error is for evaluation only.
        </p>
        <details>
          <summary>Validity and actual rendering cost</summary>
          <p>
            Center acceptance and fallback are fractions of the 200 items.
            Mean attempts counts individual candidate renders for the complete
            512-valid-candidate pool, not standalone Head@1 or Head@16 queries.
            Rejection rate is total rejected renders divided by total attempts.
            Replacement batches also produce surplus valid renders beyond
            the retained pool; these are not invalid outputs.
          </p>
          {costs}
          <p>
            The records do not retain independent Head@1/Head@16 attempt counts
            or separate peak and nonfinite rejection reasons. Thus N=1 does
            not establish a one-render cost. These archival pool-building costs
            are separate from the matched-runtime experiment below.
          </p>
        </details>
        <details>
          <summary>Valid-center sensitivity analysis</summary>
          <p>
            These paired diagnostics use only items whose predicted centers
            were valid for all three encoders: 194 known and 198 hidden items.
            They do not replace the full 200-item results. Negative differences
            favor Head@16. Intervals use 20,000 paired item-level bootstrap
            resamples with a fixed candidate seed; they are descriptive,
            not multiplicity-adjusted, and do not capture sampling-seed variance.
          </p>
          {diagnostics}
          <p>
            Downloads also include each encoder's own valid-center subset and
            comparisons with Head@512. A confidence interval containing zero
            does not establish equivalence. Rejected centers have no archived
            raw-output error, so their replacement error is not a pure-center metric.
          </p>
        </details>
        <div class="benchmark-downloads" aria-label="Head-pool ablation downloads">
          {downloads}
        </div>
      </section>'''


def export(audit, site):
    complete = json.loads((audit / "COMPLETE.json").read_text())
    if complete["rows_audited"] != 1200 or not complete["inputs_unchanged"]:
        raise ValueError("Incomplete or modified audit inputs")
    for line in (audit / "SHA256SUMS").read_text().splitlines():
        expected, name = line.split(maxsplit=1)
        if Path(name).name != name or sha(audit / name) != expected:
            raise ValueError(f"Audit checksum mismatch: {name}")
    data = public_data(json.loads((audit / "report.json").read_text()))
    index = site / "index.html"
    source = index.read_text()
    if source.count(BEGIN) != 1 or source.count(END) != 1:
        raise ValueError("Expected unique head-ablation markers")
    payloads = {name: (audit / name).read_text() for name in FILES}
    payloads["summary.json"] = json.dumps(data, indent=2, allow_nan=False) + "\n"
    for name, value in payloads.items():
        if any(prefix in value for prefix in ("/data/", "/root/", "/tmp/")):
            raise ValueError(f"Local path in public export: {name}")
    folder = site / "assets/results/head-ablation"
    folder.mkdir(parents=True, exist_ok=True)
    for name, value in payloads.items():
        (folder / name).write_text(value)
    (folder / "checksums.sha256").write_text("".join(
        f"{sha(folder / name)}  {name}\n" for name in sorted(payloads)))
    start, rest = source.split(BEGIN)
    _, end = rest.split(END)
    index.write_text(start + BEGIN + "\n      " + render(data) + "\n      " + END + end)
    print(f"Exported six complete runs and diagnostics to {folder}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audit", type=Path)
    parser.add_argument("--site", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    export(args.audit, args.site)
