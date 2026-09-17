import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "assets/results/head-ablation"
SPEC = importlib.util.spec_from_file_location("build_head_ablation", ROOT / "scripts/build_head_ablation.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class HeadAblationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((DATA / "summary.json").read_text())

    def test_complete_ablation(self):
        rows = self.data["tables"]
        self.assertEqual(len(rows), 54)
        self.assertEqual(len(self.data["contrasts"]), 54)
        full = [r for r in rows if r["subset"] == "all_200"]
        self.assertEqual(len(full), 18)
        for r in full:
            self.assertEqual(r["n_items"], 200)
            self.assertLessEqual(r["oracle_ld_mean"], r["selected_ld_mean"])
        self.assertEqual(self.data["common_valid_counts"], {"known": 194, "unknown": 198})

    def test_no_inferred_head1_cost(self):
        for r in self.data["pool_accounting"]:
            self.assertIsNone(r["standalone_head1_attempts_mean"])
            attempts = r["full_pool_attempts_total"]
            rejected = r["full_pool_rejections_total"]
            self.assertEqual(r["unused_valid_renders_total"], attempts - rejected - 200 * 512)
            self.assertAlmostEqual(r["pooled_rejection_rate"], rejected / attempts)
            self.assertAlmostEqual(r["fallback_rate"] + r["center_acceptance_rate"], 1)

    def test_audit_csv(self):
        with (DATA / "center_audit.csv").open() as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 1200)
        rejected = [r for r in rows if r["center_accepted"] == "False"]
        self.assertEqual(len(rejected), 10)
        self.assertEqual(len({r["item_id"] for r in rejected}), 7)
        for r in rejected:
            self.assertEqual(r["raw_center_ld"], "")
            self.assertEqual(r["n1_origin"], "head_centered")

    def test_public_exports_and_checksums(self):
        for line in (DATA / "checksums.sha256").read_text().splitlines():
            expected, name = line.split()
            self.assertEqual(hashlib.sha256((DATA / name).read_bytes()).hexdigest(), expected)
        for path in DATA.iterdir():
            text = path.read_text()
            for prefix in ("/data/", "/root/", "/tmp/", "PRIVATE KEY", "deployment_condition_map"):
                self.assertNotIn(prefix, text)

    def test_html_is_generated_and_links_exist(self):
        source = (ROOT / "index.html").read_text()
        actual = source.split(MODULE.BEGIN)[1].split(MODULE.END)[0].strip()
        self.assertEqual(actual, MODULE.render(self.data))
        for name in (*MODULE.FILES, "summary.json", "checksums.sha256"):
            self.assertIn(f'assets/results/head-ablation/{name}', actual)
            self.assertTrue((DATA / name).is_file())
        self.assertIn("not standalone Head@1", actual)
        self.assertIn("do not replace", actual)


if __name__ == "__main__":
    unittest.main()
