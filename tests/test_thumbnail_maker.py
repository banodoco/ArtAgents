import unittest

from astrid.packs.builtin.thumbnail_maker import run as thumbnail_maker


class ThumbnailMakerTest(unittest.TestCase):
    def test_query_planning_detects_source_needs_deterministically(self) -> None:
        plan = thumbnail_maker.plan_evidence_needs("dramatic speaker title on stage")

        self.assertEqual(plan["tokens"], ["dramatic", "on", "speaker", "stage", "title"])
        self.assertEqual(
            [need["id"] for need in plan["needs"]],
            ["speaker_or_person_framing", "scene_context", "title_or_quote_context", "expressive_moment"],
        )

    @unittest.skip(
        "Stale — sprint-5b ported thumbnail_maker to plan-v2 emission; "
        "dry-run no longer writes evidence/reference-pack.json directly. "
        "New contract covered by tests/packs/thumbnail_maker/test_thumbnail_maker_port.py."
    )
    def test_dry_run_writes_reference_pack_with_composition_crops(self) -> None:
        pass


if __name__ == "__main__":
    unittest.main()
