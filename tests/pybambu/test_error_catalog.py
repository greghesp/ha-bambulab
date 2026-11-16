"""Validate generated HMS catalogs and the H3C source mapping."""
import ast
import gzip
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_generator_includes_h3c():
    tree = ast.parse((ROOT / "scripts/update_error_text.py").read_text(encoding="utf-8"))
    mapping = next(ast.literal_eval(node.value) for node in tree.body
                   if isinstance(node, ast.Assign)
                   and any(isinstance(target, ast.Name) and target.id == "_DEVICE_TYPES"
                           for target in node.targets))
    assert mapping["H3C"] == "32X"


def test_runtime_catalogs_match_reviewable_sources():
    for source in (ROOT / "scripts/hms_error_text").glob("hms_*.json"):
        runtime = ROOT / "custom_components/bambu_lab/pybambu/hms_error_text" / (source.name + ".gz")
        with gzip.open(runtime, "rt", encoding="utf-8") as stream:
            assert json.load(stream) == json.loads(source.read_text(encoding="utf-8")), source.name
