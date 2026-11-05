"""The .NET service reads the field registry exported from Python: it must not go stale."""
import json

from scripts.export_contracts import OUT, python_decisions, registry


def test_exported_field_registry_matches_python():
    exported = json.loads((OUT / "field_registry.json").read_text())
    assert exported == registry(), "run: python scripts/export_contracts.py"


def test_exported_python_decisions_match_the_python_engine():
    exported = json.loads((OUT / "python_decisions.json").read_text())
    assert len(exported) == 120
    assert exported == python_decisions(), "run: python scripts/export_contracts.py"
