from submitiq.tables.local import match_header
from submitiq.tables.textract import blocks_from_response
from submitiq.tables.vocab import LOSS_COLUMNS, SOV_COLUMNS
from submitiq.textlayout import Word


def _words(spec):
    out, x = [], 20.0
    for t in spec.split():
        out.append(Word(t, x, x + 6 * len(t), 100, 108))
        x += 6 * len(t) + 4
    return out


def test_header_prefers_exact_phrase_over_fuzzy():
    cols = match_header(_words("Loc # Address City State Sprinklered % Sprk TIV"), SOV_COLUMNS)
    fields = [c.field for c in cols if not c.field.startswith("_")]
    assert fields == ["loc_number", "street", "city", "state", "sprinklered", "sprinkler_pct", "tiv"]


def test_header_tolerates_one_letter_ocr_slip():
    cols = match_header(_words("Loc Address City Bidg Limit TIV"), SOV_COLUMNS)
    assert "building_value" in [c.field for c in cols]


def test_unknown_header_gets_its_own_band():
    cols = match_header(_words("Claim No. Date of Loss Adjuster Paid Reserve Total Incurred"), LOSS_COLUMNS)
    assert [c.field for c in cols][2].startswith("_unknown")


def _bbox(top):
    return {"BoundingBox": {"Top": top, "Left": 0.1, "Width": 0.1, "Height": 0.01}}


def test_textract_response_to_blocks():
    words = {f"w{i}": t for i, t in enumerate(["Loc", "City", "TIV", "1", "Austin", "$500,000", "Prepared", "by", "X"])}
    blocks = [{"Id": k, "BlockType": "WORD", "Text": v} for k, v in words.items()]
    cells = []
    for i, (r, c) in enumerate([(1, 1), (1, 2), (1, 3), (2, 1), (2, 2), (2, 3)]):
        cells.append({"Id": f"c{i}", "BlockType": "CELL", "RowIndex": r, "ColumnIndex": c, "Confidence": 97.0,
                      "Geometry": _bbox(0.2 + 0.05 * r), "Relationships": [{"Type": "CHILD", "Ids": [f"w{i}"]}]})
    blocks += cells
    blocks.append({"Id": "t", "BlockType": "TABLE", "Relationships": [{"Type": "CHILD", "Ids": [c["Id"] for c in cells]}]})
    blocks.append({"Id": "l1", "BlockType": "LINE", "Text": "Prepared by X", "Confidence": 99.0, "Geometry": _bbox(0.1),
                   "Relationships": [{"Type": "CHILD", "Ids": ["w6", "w7", "w8"]}]})
    out = blocks_from_response({"Blocks": blocks}, 1, {"loc_number": ["loc"], "city": ["city"], "tiv": ["tiv"]})
    assert [b.kind for b in out] == ["text", "header", "row"]
    assert out[2].cells == {"loc_number": "1", "city": "Austin", "tiv": "$500,000"}
    assert abs(out[2].conf - 0.97) < 1e-9
