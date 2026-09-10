#!/usr/bin/env python3
"""Export the existing frozen CounterFX-200 manifests, without generating targets."""

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    return json.loads(path.read_text())


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True, allow_nan=False) + "\n")


def export(paper, site):
    manifest = paper / "manifests/fma_test_core_200.csv"
    target_file = paper / "manifests/pedalboard_known_test_seed20270722.jsonl"
    summary_file = paper / "manifests/pedalboard_known_test_seed20270722.summary.json"
    run_file = paper / "results/relativefx_cmaes_unknown_test200_pop128_iter32_seed20270726/run_config.json"
    lock_file = paper / "locks/pedalboard_renderer_lock.json"
    with manifest.open(newline="") as handle:
        audio = list(csv.DictReader(handle))
    targets = [json.loads(line) for line in target_file.read_text().splitlines()]
    summary, run, lock = read_json(summary_file), read_json(run_file), read_json(lock_file)
    schema = run["schema"]
    if len(audio) != 200 or len(targets) != 200 or summary["items"] != 200:
        raise ValueError("Expected the complete frozen Test-200 set")
    if [r["item_id"] for r in audio] != [r["item_id"] for r in targets]:
        raise ValueError("Source/target item order differs")
    if len({r["item_id"] for r in audio}) != 200:
        raise ValueError("Duplicate test items")
    if dict(Counter(str(r["chain_length"]) for r in targets)) != summary["chain_lengths"]:
        raise ValueError("Chain counts disagree with frozen summary")
    if schema["activation_probabilities"] != summary["effect_activation_probabilities"]:
        raise ValueError("Frozen schema and test activation priors differ")

    # Recover ranges from the accepted target records, cross-checked against
    # the schema saved by a formal evaluation, not mutable current defaults.
    priors = {}
    for row in targets:
        if not 1 <= row["chain_length"] <= 4 or row["source_target_ld_min"] < 0.8:
            raise ValueError("Unexpected target constraint")
        if max(row["render_peak_a"], row["render_peak_b"]) >= 1:
            raise ValueError("Clipped accepted target")
        for effect, params in row["benchmark_param_priors"].items():
            if effect in priors and priors[effect] != params:
                raise ValueError("Target parameter priors changed within manifest")
            priors[effect] = params
    for effect, params in schema["parameters"].items():
        frozen = {p["name"]: {key: p[key] for key in ("minimum", "maximum", "distribution", "fixed")} for p in params}
        if frozen != priors[effect]:
            raise ValueError(f"Saved schema and target ranges differ for {effect}")

    folder = site / "assets/results/counterfx200"
    folder.mkdir(parents=True, exist_ok=True)
    config = {
        "name": "CounterFX-200",
        "manifest_version": summary["benchmark_version"],
        "items": 200, "dataset": "FMA-small", "split": "test",
        "sample_rate": 44100, "channels": 2, "window_seconds": 10,
        "preferred_start_a_seconds": 5, "target_lufs_per_window": -20,
        "audio_seed": summary["audio_seed"], "effect_seed": summary["effect_seed"],
        "genre_quotas": summary["requested_genre_quotas"],
        "effect_order": schema["effect_order"],
        "effect_activation_probabilities": schema["activation_probabilities"],
        "order_templates": schema["order_templates"],
        "chain_length": {"minimum": 1, "maximum": 4,
                         "rule": "Independent Bernoulli draws; if empty, weighted choice of one effect; if more than four, weighted subset of four without replacement. No independent uniform length prior."},
        "parameter_priors": priors,
        "variable_controls": sum(p["fixed"] is None for params in priors.values() for p in params.values()),
        "parameter_coordinates": {"linear": "x = lower + u * (upper - lower)",
                                  "log": "x = exp(log(lower) + u * (log(upper) - log(lower)))",
                                  "u": "Uniform(0,1) for global-prior parameter sampling",
                                  "target_manifest": "Physical controls are authoritative; legacy registry-normalized fields are not exported."},
        "source_screening": {"minimum_decoded_seconds": 28, "minimum_rms_dbfs_exclusive": -45,
                             "active_frame_seconds": 0.1, "active_threshold_dbfs_exclusive": -55,
                             "minimum_active_ratio": 0.6, "maximum_peak_exclusive": 1},
        "target_acceptance": {"minimum_ld_on_both_windows": 0.8, "maximum_peak_exclusive": 1,
                              "finite_only": True, "max_parameter_attempts": 256,
                              "redraw": "Controls only; effect set and order stay fixed."},
        "renderer": {key: lock["target_renderer"][key] for key in
                     ("id", "package_version", "sample_rate", "buffer_size", "reset", "peak_limiter", "rms_matching")},
        "metric": {"name": "Ld", "fft_sizes": [1024, 2048, 512],
                   "hop_sizes": [120, 240, 50], "win_lengths": [600, 1200, 240],
                   "window": "Hann", "components": ["spectral convergence", "log-magnitude L1"]},
    }
    if config["variable_controls"] != 22:
        raise ValueError("Expected 22 variable controls")
    dump(folder / "configuration.json", config)
    (folder / "audio_manifest.csv").write_bytes(manifest.read_bytes())
    fields = ("item_id", "chain_length", "chain_order", "continuous_params_physical",
              "effect_seed", "final_parameter_seed", "render_attempt", "renderer_id",
              "renderer_version", "renderer_buffer_size", "renderer_reset",
              "source_target_ld_a", "source_target_ld_b", "source_target_ld_min",
              "render_peak_a", "render_peak_b")
    exported_targets = [{key: row[key] for key in fields} for row in targets]
    (folder / "target_chains.jsonl").write_text("".join(json.dumps(row, ensure_ascii=True, allow_nan=False) + "\n" for row in exported_targets))
    dump(folder / "summary.json", {key: summary[key] for key in
         ("items", "genres", "chain_lengths", "effect_occurrences", "source_target_ld_min",
          "rejected_audio_candidates", "rejected_target_parameter_draws", "rejected_target_draws_by_reason")})
    with (folder / "parameter_ranges.csv").open("w", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["effect", "parameter", "minimum", "maximum", "distribution", "fixed"])
        for effect in config["effect_order"]:
            for name, prior in priors[effect].items():
                writer.writerow([effect, name, prior["minimum"], prior["maximum"], prior["distribution"], prior["fixed"]])
    renderer_lock = json.loads(json.dumps(lock))
    renderer_lock["candidate_renderer"].pop("root", None)
    renderer_lock["candidate_renderer"].pop("formal_chain_parity_report", None)
    renderer_lock["target_renderer"].pop("package_path", None)
    dump(folder / "provenance.json", {
        "export_date": "2026-09-11",
        "sources_sha256": {str(path.relative_to(paper)): sha(path) for path in
                           (manifest, target_file, summary_file, run_file, lock_file)},
        "renderer_lock": renderer_lock,
        "notes": ["Source audio manifest copied byte-for-byte. Target export retains physical controls, seeds, and acceptance measurements.",
                  "The renderer lock retains its historical development-version label; the frozen test manifest has its own version.",
                  "No source audio, model weights, or internal training metadata are included.",
                  "This specifies CounterFX evaluation construction, not registration audio pairing."],
    })
    for path in folder.iterdir():
        if path.suffix in (".json", ".jsonl", ".csv", ".md"):
            if any(root in path.read_text() for root in ("/data/workspace/", "/data2/", "/root/")):
                raise ValueError(f"Machine path in public export: {path.name}")
    (folder / "checksums.sha256").write_text("".join(f"{sha(p)}  {p.name}\n" for p in sorted(folder.iterdir())
                                                   if p.is_file() and p.name != "checksums.sha256"))
    print(f"Exported {len(audio)} items, {len(priors)} processors, {config['variable_controls']} variable controls")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paper", type=Path)
    parser.add_argument("--site", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    export(args.paper, args.site)
