import unittest

from astrid.packs.video_editing.orchestrators.thumbnail_maker import run as thumbnail_maker


class ThumbnailMakerTest(unittest.TestCase):
    def test_query_planning_detects_source_needs_deterministically(self) -> None:
        plan = thumbnail_maker.plan_evidence_needs("dramatic speaker title on stage")

        self.assertEqual(plan["tokens"], ["dramatic", "on", "speaker", "stage", "title"])
        self.assertEqual(
            [need["id"] for need in plan["needs"]],
            ["speaker_or_person_framing", "scene_context", "title_or_quote_context", "expressive_moment"],
        )


if __name__ == "__main__":
    unittest.main()
