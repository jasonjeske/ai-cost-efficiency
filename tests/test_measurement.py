import csv
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from ace.measurement import HEADER, compare

class MeasurementTests(unittest.TestCase):
    def _csv(self, path, spend=110, completed=8, rows=10, dates=True, tier="mid", task="single-file-change", cohort="pre"):
        with open(path,"w",newline="",encoding="utf-8") as f:
            out=csv.DictWriter(f,fieldnames=HEADER); out.writeheader()
            first=date(2026,1 if cohort == "pre" else 2,1)
            for i in range(rows):
                when=first+timedelta(days=i*2 if dates else 0)
                out.writerow({"date":when.isoformat(),"task_id":cohort+"-secret-%s" % i,"task_class":task,"model_tier":tier,"sessions":"1","turns_total":"1","attempts":"2" if i == rows-1 else "1","input_tokens":str(spend),"cached_input_tokens":"0","output_tokens":"0","completed_to_standard":"y" if i < completed else "n","cost_usd":"","notes":"ACE_SECRET_CANARY sk-should-not-escape /Users/fake/home"})
    def _compare(self, directory, **kwargs):
        d=Path(directory); self._csv(d/"pre", **kwargs.pop("pre", {})); self._csv(d/"post", cohort="post", **kwargs.pop("post", {})); (d/"standard").write_text("done")
        return compare(d/"pre",d/"post",d/"standard","fixed", "measured","measured")
    def test_cpct_exact_and_abandoned_spend_included(self):
        with tempfile.TemporaryDirectory() as d:
            r=self._compare(d, pre={"spend":110,"completed":8}, post={"spend":90,"completed":9})
            c=r["classes"][0]; self.assertEqual(c["pre"]["cpct"],"137.5"); self.assertEqual(c["post"]["cpct"],"100"); self.assertEqual(r["outcome_claim"],"improved")
    def test_user_labels_are_opaque_and_stable_in_public_comparison(self):
        with tempfile.TemporaryDirectory() as d:
            raw_task="UNKNOWN_TASK_CANARY /Users/fake/home"; raw_tier="UNKNOWN_TIER_CANARY sk-secret"
            r=self._compare(d, pre={"task":raw_task,"tier":raw_tier}, post={"task":raw_task,"tier":raw_tier})
            rendered=__import__('json').dumps(r,sort_keys=True)
            self.assertNotIn("UNKNOWN_",rendered)
            cohort=r["classes"][0]["pre"]
            self.assertRegex(cohort["task_class"],r"^task-[0-9a-f]{16}$")
            self.assertRegex(cohort["model_tiers"][0],r"^tier-[0-9a-f]{16}$")

    def test_improved_claim_requires_ratified_thresholds(self):
        with tempfile.TemporaryDirectory() as d:
            r=self._compare(d, pre={"spend":110,"completed":8}, post={"spend":100,"completed":8})
            self.assertEqual(r["outcome_claim"],"not_improved")
    def test_each_ratified_gate_isolated(self):
        cases=(
            ("minimum", {"pre":{"rows":9,"spend":110,"completed":8},"post":{"spend":90,"completed":9}}, "fewer than 10"),
            ("duration", {"pre":{"dates":False,"spend":110,"completed":8},"post":{"spend":90,"completed":9}}, "two weeks"),
            ("tier", {"pre":{"spend":110,"completed":8},"post":{"spend":90,"completed":9,"tier":"high"}}, "model tiers differ"),
            ("denominator", {"pre":{"spend":110,"completed":0},"post":{"spend":90,"completed":9}}, "zero completed"),
            ("completion-rate", {"pre":{"spend":110,"completed":9},"post":{"spend":90,"completed":8}}, "completion rate declined"),
            ("completion-volume", {"pre":{"spend":110,"completed":9},"post":{"spend":90,"completed":8}}, "completion volume declined"),
        )
        for name, kwargs, reason in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as d:
                result=self._compare(d, **kwargs)
                self.assertTrue(any(reason in item for item in result["reasons"]))
                self.assertNotEqual(result["outcome_claim"],"improved")

    def test_duplicate_replayed_and_overlapping_cohorts_never_improve(self):
        with tempfile.TemporaryDirectory() as d:
            duplicate=Path(d)/"duplicate"; self._csv(duplicate)
            with duplicate.open(encoding="utf-8") as handle: rows=list(csv.DictReader(handle))
            rows[1]["task_id"]=rows[0]["task_id"]
            with duplicate.open("w",newline="",encoding="utf-8") as handle:
                out=csv.DictWriter(handle,fieldnames=HEADER); out.writeheader(); out.writerows(rows)
            standard=Path(d)/"standard"; standard.write_text("done")
            with self.assertRaisesRegex(ValueError,"invalid row"): compare(duplicate,duplicate,standard,"fixed","measured","measured")
        with tempfile.TemporaryDirectory() as d:
            pre,post=Path(d)/"pre",Path(d)/"post"; self._csv(pre); self._csv(post,spend=90,completed=9,cohort="post")
            with post.open(encoding="utf-8") as handle: rows=list(csv.DictReader(handle))
            rows[0]["task_id"]="pre-secret-0"; rows[0]["date"]="2026-01-19"
            with post.open("w",newline="",encoding="utf-8") as handle:
                out=csv.DictWriter(handle,fieldnames=HEADER); out.writeheader(); out.writerows(rows)
            standard=Path(d)/"standard"; standard.write_text("done")
            result=compare(pre,post,standard,"fixed","measured","measured")
            self.assertEqual(result["outcome_claim"],"pending_insufficient_evidence")
            self.assertEqual(result["classes"][0]["status"],"pending")
            self.assertTrue(any("task IDs overlap" in x for x in result["reasons"]))
            self.assertTrue(any("date windows overlap" in x for x in result["reasons"]))

if __name__ == "__main__": unittest.main()
