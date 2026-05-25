from __future__ import annotations

import io

from astrid.threads.attribute import AttributionDecision
from astrid.threads.prefix import emit_prefix, format_prefix_lines


def test_prefix_order_thread_variants_notice_blank_line() -> None:
    decision = AttributionDecision(
        thread_id="01ARZ3NDEKTSV4RRFFQ69G5FAV",
        source="reopened_active",
        label="Logo",
        run_number=3,
        notice="Reopened the recently archived active thread.",
    )

    lines = format_prefix_lines(decision, variants=4)
    stream = io.StringIO()
    emit_prefix(lines, stream=stream)

    assert lines[0].startswith("[lineage] Logo")
    assert lines[1] == "[variants] requested 4; record keepers only as non-binding lineage after reviewing outputs."
    assert lines[2].startswith("Notice:")
    assert stream.getvalue().splitlines() == lines + [""]
