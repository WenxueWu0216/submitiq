"""The .NET service reads the field registry exported from Python: it must not go stale."""
import json

from scripts.export_contracts import OUT, registry


def test_exported_field_registry_matches_python():
    exported = json.loads((OUT / "field_registry.json").read_text())
    assert exported == registry(), "run: python scripts/export_contracts.py"
