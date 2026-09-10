import csv
import hashlib
import json
import math
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "assets/results/counterfx200"


class CounterFxSpecificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads((DATA / "configuration.json").read_text())
        with (DATA / "audio_manifest.csv").open(newline="") as handle:
            cls.audio = list(csv.DictReader(handle))
        cls.targets = [json.loads(line) for line in (DATA / "target_chains.jsonl").read_text().splitlines()]

    def test_ids_and_audio_protocol(self):
        self.assertEqual(len(self.audio), 200)
        self.assertEqual([r["item_id"] for r in self.audio], [r["item_id"] for r in self.targets])
        self.assertEqual(len({r["track_id"] for r in self.audio}), 200)
        self.assertEqual(dict(Counter(r["genre"] for r in self.audio)), self.config["genre_quotas"])
        for row in self.audio:
            self.assertEqual(row["split"], "test")
            self.assertEqual(float(row["start_b_sec"]) - float(row["start_a_sec"]), 10)
            self.assertEqual(float(row["target_lufs"]), -20)
            self.assertEqual(int(row["sample_rate"]), 44100)

    def test_controls_and_accepted_targets(self):
        priors = self.config["parameter_priors"]
        self.assertEqual(sum(p["fixed"] is None for ps in priors.values() for p in ps.values()), 22)
        templates = self.config["order_templates"]
        self.assertEqual(len(templates), 4)
        for row in self.targets:
            chain = row["chain_order"]
            self.assertEqual(len(chain), len(set(chain)))
            self.assertTrue(1 <= len(chain) <= 4)
            self.assertTrue(any([e for e in template if e in chain] == chain for template in templates))
            self.assertGreaterEqual(row["source_target_ld_min"], 0.8)
            self.assertLess(max(row["render_peak_a"], row["render_peak_b"]), 1)
            for effect, params in row["continuous_params_physical"].items():
                self.assertEqual(set(params), set(priors[effect]))
                for name, value in params.items():
                    p = priors[effect][name]
                    self.assertTrue(math.isfinite(value))
                    if p["fixed"] is not None:
                        self.assertEqual(value, p["fixed"])
                    else:
                        self.assertLessEqual(p["minimum"], value)
                        self.assertLessEqual(value, p["maximum"])

    def test_checksums_and_public_only(self):
        for line in (DATA / "checksums.sha256").read_text().splitlines():
            expected, name = line.split("  ", 1)
            self.assertEqual(hashlib.sha256((DATA / name).read_bytes()).hexdigest(), expected)
        for path in DATA.iterdir():
            self.assertNotIn(path.suffix, (".wav", ".mp3", ".pt", ".ckpt"))
            if path.suffix in (".json", ".jsonl", ".csv", ".md"):
                for private in ("/data/workspace/", "/data2/", "/root/", "PRIVATE KEY"):
                    self.assertNotIn(private, path.read_text())

    def test_download_links_exist(self):
        from html.parser import HTMLParser

        class Links(HTMLParser):
            def handle_starttag(self, tag, attrs):
                if tag == "a":
                    href = dict(attrs).get("href", "")
                    if href.startswith("assets/results/counterfx200/"):
                        self.paths.append(href)

        parser = Links()
        parser.paths = []
        parser.feed((ROOT / "index.html").read_text())
        self.assertEqual(len(parser.paths), 8)
        for path in parser.paths:
            self.assertTrue((ROOT / path).is_file(), path)


if __name__ == "__main__":
    unittest.main()
