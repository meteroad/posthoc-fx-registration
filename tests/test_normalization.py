import csv
import hashlib
import importlib.util
import json
import math
import statistics
import unittest
from collections import Counter
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]
ROOT = SITE / "assets/results/normalization"
SPEC = importlib.util.spec_from_file_location("normalization", SITE / "scripts/build_normalization.py")
BUILD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILD)


class NormalizationReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.summary = json.loads((ROOT / "summary.json").read_text())
        with (ROOT / "audio_metrics.csv").open() as handle:
            cls.audio = list(csv.DictReader(handle))
        with (ROOT / "embedding_metrics.csv").open() as handle:
            cls.embeddings = list(csv.DictReader(handle))

    def test_completion_and_checksums(self):
        complete = json.loads((ROOT / "provenance.json").read_text())["complete"]
        self.assertEqual(complete["items"], 100)
        self.assertEqual(hashlib.sha256((ROOT / "summary.json").read_bytes()).hexdigest(), complete["summary_sha256"])
        for line in (ROOT / "checksums.sha256").read_text().splitlines():
            expected, filename = line.split("  ", 1)
            self.assertEqual(hashlib.sha256((ROOT / filename).read_bytes()).hexdigest(), expected, filename)

    def test_complete_balanced_pairs(self):
        self.assertEqual(len(self.audio), 1408)
        self.assertEqual(len(self.embeddings), 4224)
        manifest = json.loads((ROOT / "manifest.json").read_text())
        self.assertEqual(len(manifest["items"]), 100)
        self.assertEqual(len({item["song"] for item in manifest["items"]}), 49)
        self.assertEqual(Counter(item["stem"] for item in manifest["items"]), dict.fromkeys(BUILD.STEMS, 25))
        for condition in BUILD.CONDITIONS:
            for domain in ("input", "normalized"):
                rows = [r for r in self.audio if r["condition"] == condition and r["domain"] == domain]
                self.assertEqual(len({r["id"] for r in rows}), 100)

    def test_summary_matches_per_item_data(self):
        for condition, domains in self.summary["conditions"].items():
            for domain in ("input", "normalized"):
                rows = [r for r in self.audio if r["condition"] == condition and r["domain"] == domain]
                values = [float(r["ld"]) for r in rows]
                self.assertTrue(all(math.isfinite(v) for v in values))
                self.assertAlmostEqual(statistics.mean(values), domains[domain]["ld"]["mean"], places=12)
                subset = [float(r["ld"]) for r in rows if float(r["max_stage_clipped_fraction"]) == 0]
                sensitivity = domains[domain]["unclipped_ld_sensitivity"]
                if subset:
                    self.assertEqual(len(subset), sensitivity["n"])
                    self.assertAlmostEqual(statistics.mean(subset), sensitivity["mean"], places=12)
        for encoder, conditions in self.summary["embeddings"].items():
            for condition, domains in conditions.items():
                for domain in ("input", "normalized"):
                    values = [float(r["cosine_distance"]) for r in self.embeddings
                              if (r["encoder"], r["condition"], r["domain"]) == (encoder, condition, domain)]
                    self.assertTrue(all(math.isfinite(v) for v in values))
                    self.assertAlmostEqual(statistics.mean(values), domains[domain]["mean"], places=12)
                    self.assertAlmostEqual(statistics.median(values), domains[domain]["median"], places=12)

    def test_html_generated_from_summary(self):
        page = (SITE / "index.html").read_text()
        block = page.split(BUILD.BEGIN)[1].split(BUILD.END)[0].strip()
        self.assertEqual(block, BUILD.render_section(self.summary).strip())
        self.assertIn('href="#normalization"', page)
        self.assertEqual(page.count('id="normalization"'), 1)

    def test_no_private_paths_or_audio_in_release(self):
        for path in ROOT.iterdir():
            self.assertNotIn(path.suffix.lower(), (".wav", ".flac", ".mp3", ".pt", ".ckpt"))
            if path.suffix in (".json", ".csv", ".md"):
                content = path.read_text()
                for private_root in ("/data/workspace/", "/data2/", "/root/", "PRIVATE KEY", "github_pat_"):
                    self.assertNotIn(private_root, content, path.name)


if __name__ == "__main__":
    unittest.main()
