from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from echr_extractor.ECHR_text_segmenter import SECTION_NAMES, segment_echr_texts


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "segmentation_live_samples"
MANIFEST = json.loads((FIXTURE_DIR / "manifest.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "sample",
    MANIFEST["samples"],
    ids=[sample["basename"] for sample in MANIFEST["samples"]],
)
def test_segmenter_matches_real_document_goldens(sample):
    text_path = FIXTURE_DIR / "texts" / sample["text_file"]
    fulltext = text_path.read_text(encoding="utf-8")

    assert len(fulltext) == sample["fulltext_length"]

    df = pd.DataFrame(
        {
            "itemid": [sample["itemid"]],
            "languageisocode": [sample["languageisocode"]],
            "fulltext": [fulltext],
            "doctype": [sample["doctype"]],
            "doctypebranch": [sample["doctypebranch"]],
        }
    )

    result = segment_echr_texts(df).iloc[0]
    actual_sections = {
        section: result[section]
        for section in SECTION_NAMES
        if result[section] is not None
    }

    assert result["parser_mode"] == sample["parser_mode"]
    assert result["num_sections"] == sample["num_sections"]
    assert actual_sections == sample["sections"]
