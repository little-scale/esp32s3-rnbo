#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Generate original reviewed RNBO fixture graphs, never exported RNBO C++.

Recipe validation is deliberately closed. Adding an operator requires a
reviewed construction/model contract; registry membership alone is insufficient.
"""
from __future__ import annotations
import argparse
import copy
import json
import os
from pathlib import Path
import re
import shutil
import tempfile

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RECIPES = ROOT / "tests/fixtures/objects/wave4/recipes.json"
FORMAT = "rnbo-original-object-recipes-v1"
PATCHER = {
    "abs~": ("abs~", "absolute", 1),
    "minimum~": ("minimum~", "minimum", 2), "min~": ("minimum~", "minimum", 2),
    "maximum~": ("maximum~", "maximum", 2), "max~": ("maximum~", "maximum", 2),
    "sub~": ("sub~", "subtract", 2), "-~": ("sub~", "subtract", 2),
    "eq~": ("eq~", "equal", 2), "==~": ("eq~", "equal", 2),
    "lt~": ("lt~", "less", 2), "<~": ("lt~", "less", 2),
}
# Original programs. Keeping these separate from the mathematical models
# allows model mutation tests and avoids deriving truth from generated C++.
CODEBOX = {
    "arithmetic": {
        "program": "out1 = in1 + in2;\nout2 = in1 - in2;\n",
        "model": "sum-and-difference",
        "entries": ["codebox:+", "codebox:-"],
    },
    "delta-state": {
        "program": "@state difference = new delta();\nout1 = difference.next(in1);\nout2 = in2;\n",
        "model": "delta-left-observer-right",
        "entries": ["codebox:delta", "codebox-member:delta.next"],
    },
}
INPUTS = ("signed-grid-v1", "dense-binary32-v1", "vector-boundaries-v1")


def canonical(value) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def _object(value, keys: set[str], where: str):
    if type(value) is not dict or set(value) != keys:
        raise ValueError(f"{where}: unexpected or missing fields")


def validate_recipes(value: dict) -> dict:
    """Validate all recipes before producing any files; never coerce booleans."""
    _object(value, {"format", "format_version", "license", "rnbo_version", "sample_rate", "block_frames", "recipes"}, "catalog")
    for key, expected in {"format": FORMAT, "format_version": 1, "license": "MIT", "rnbo_version": "1.4.4", "sample_rate": 44100, "block_frames": 256}.items():
        if type(value[key]) is not type(expected) or value[key] != expected:
            raise ValueError(f"catalog: unsupported {key}")
    recipes = value["recipes"]
    if type(recipes) is not list or not 1 <= len(recipes) <= 64:
        raise ValueError("catalog: expected 1..64 explicit recipes")
    ids = set()
    identities = set()
    for recipe in recipes:
        _object(recipe, {"id", "source", "role", "audio_inputs", "audio_outputs", "domain", "model", "cases", "reference_sources"}, "recipe")
        id = recipe["id"]
        if type(id) is not str or not re.fullmatch(r"[a-z][a-z0-9-]{0,79}", id) or id in ids:
            raise ValueError("recipe: invalid or duplicate id")
        ids.add(id)
        if recipe["role"] != "fx" or type(recipe["role"]) is not str:
            raise ValueError("recipe: initial role is FX only")
        if any(type(recipe[k]) is not int or recipe[k] != 2 for k in ("audio_inputs", "audio_outputs")):
            raise ValueError("recipe: exactly two input/output planes are required")
        _object(recipe["domain"], {"input_type", "finite", "minimum", "maximum", "zero_sign"}, "domain")
        expected_domain = {"input_type": "binary32", "finite": True, "minimum": -1.0, "maximum": 1.0, "zero_sign": "numeric-equality-with-separate-bit-observation"}
        if any(type(recipe["domain"][k]) is not type(v) or recipe["domain"][k] != v for k, v in expected_domain.items()):
            raise ValueError("recipe: unsupported input domain or zero policy")
        source = recipe["source"]
        if type(source) is not dict:
            raise ValueError("recipe: source must be an object")
        if source.get("surface") == "patcher":
            _object(source, {"surface", "spelling", "canonical", "arity", "wiring"}, "patcher source")
            spec = PATCHER.get(source["spelling"]) if type(source["spelling"]) is str else None
            if spec is None:
                raise ValueError("recipe: spelling has no reviewed construction")
            name, model, arity = spec
            if source["canonical"] != name or type(source["arity"]) is not int or source["arity"] != arity:
                raise ValueError("recipe: canonical name/ports do not match the exact spelling")
            if source["wiring"] != ("independent-planes" if arity == 1 else "reversed-binary-operands"):
                raise ValueError("recipe: unsupported port relationship")
            identity = ("patcher", source["spelling"])
        elif source.get("surface") == "codebox":
            _object(source, {"surface", "program", "exact_entries", "wrapper_spelling"}, "codebox source")
            spec = CODEBOX.get(source["program"]) if type(source["program"]) is str else None
            if spec is None or source["exact_entries"] != spec["entries"] or source["wrapper_spelling"] != "codebox~":
                raise ValueError("recipe: unknown codebox program, entries or wrapper")
            model = spec["model"]
            identity = ("codebox", source["program"])
        else:
            raise ValueError("recipe: unsupported surface")
        if identity in identities:
            raise ValueError("recipe: duplicate exact surface identity")
        identities.add(identity)
        _object(recipe["model"], {"kind", "maximum_absolute_error", "rounding", "independent_truth"}, "model")
        if recipe["model"] != {"kind": model, "maximum_absolute_error": 0.0, "rounding": "once-binary32-per-output-operation", "independent_truth": "mathematical-operation-and-explicit-input-history"} or type(recipe["model"]["maximum_absolute_error"]) is not float:
            raise ValueError("recipe: model or fixed exact numerical gate differs")
        cases = recipe["cases"]
        if type(cases) is not list or len(cases) != len(INPUTS):
            raise ValueError("recipe: missing boundary/dense/history case")
        for case, input_kind in zip(cases, INPUTS):
            _object(case, {"id", "input", "blocks", "warmup_blocks", "lifecycles", "events"}, "case")
            if case["id"] != input_kind or case["input"] != {"kind": input_kind}:
                raise ValueError("recipe: unknown input program or case order")
            if any(type(case[k]) is not int or case[k] != v for k, v in {"blocks": 64, "warmup_blocks": 4, "lifecycles": 2}.items()) or case["events"] != []:
                raise ValueError("recipe: undeclared duration, warmup, lifetime or event mode")
        refs = recipe["reference_sources"]
        if type(refs) is not list or not refs:
            raise ValueError("recipe: primary semantic references required")
        for ref in refs:
            _object(ref, {"url", "local_package_path", "sha256", "version_scope"}, "reference")
            if type(ref["url"]) is not str or not ref["url"].startswith("https://rnbo.cycling74.com/"):
                raise ValueError("recipe: expected a first-party reference")
            if type(ref["local_package_path"]) is not str or ref["local_package_path"].startswith("/") or ".." in Path(ref["local_package_path"]).parts:
                raise ValueError("recipe: unsafe primary metadata path")
            if type(ref["sha256"]) is not str or not re.fullmatch(r"[0-9a-f]{64}", ref["sha256"]):
                raise ValueError("recipe: invalid primary metadata fingerprint")
            if type(ref["version_scope"]) is not str or not ref["version_scope"]:
                raise ValueError("recipe: reference version scope required")
    return copy.deepcopy(value)


def _box(id: str, text: str, index: int, **extra) -> dict:
    return {"box": {"id": id, "maxclass": "newobj", "text": text, "rnbo_uniqueid": id,
                    "patching_rect": [20 + (index % 4) * 240, 25 + (index // 4) * 90, 220, 22], **extra}}


def _wire(source, outlet, destination, inlet):
    return {"patchline": {"source": [source, outlet], "destination": [destination, inlet]}}


def _render_recipe(recipe: dict) -> dict:
    source = recipe["source"]
    boxes = [_box("left", "in~ 1", 0), _box("right", "in~ 2", 1)]
    if source["surface"] == "patcher":
        boxes += [_box("operator-left", source["spelling"], 2), _box("operator-right", source["spelling"], 3)]
        lines = [_wire("left", 0, "operator-left", 0), _wire("right", 0, "operator-right", 0)]
        if source["arity"] == 2:
            lines += [_wire("right", 0, "operator-left", 1), _wire("left", 0, "operator-right", 1)]
        lines += [_wire("operator-left", 0, "out-left", 0), _wire("operator-right", 0, "out-right", 0)]
    else:
        boxes += [_box("program", "codebox~", 2, rnbo_extra_attributes={"code": CODEBOX[source["program"]]["program"]})]
        lines = [_wire("left", 0, "program", 0), _wire("right", 0, "program", 1), _wire("program", 0, "out-left", 0), _wire("program", 1, "out-right", 0)]
    boxes += [_box("out-left", "out~ 1", 4), _box("out-right", "out~ 2", 5)]
    return {"patcher": {"fileversion": 1, "classnamespace": "rnbo", "rect": [0, 0, 1024, 720], "boxes": boxes, "lines": lines}}


def render(value: dict, fixture_ids: list[str] | None = None) -> dict[str, bytes]:
    value = validate_recipes(value)
    ids = [r["id"] for r in value["recipes"]]
    if fixture_ids is not None:
        if type(fixture_ids) is not list or not fixture_ids or any(type(x) is not str for x in fixture_ids) or len(set(fixture_ids)) != len(fixture_ids) or any(x not in ids for x in fixture_ids):
            raise ValueError("Unknown, empty or duplicate fixture selection")
        selected = set(fixture_ids)
    else:
        selected = set(ids)
    files = {}
    fixtures = []
    for recipe in value["recipes"]:
        if recipe["id"] not in selected:
            continue
        patch = recipe["id"] + ".rnbopat"
        files[patch] = canonical(_render_recipe(recipe))
        source = recipe["source"]
        fixtures.append({"id": recipe["id"], "patch": patch, "surface": source["surface"],
                         "exact_entries": ["patcher:" + source["spelling"]] if source["surface"] == "patcher" else source["exact_entries"],
                         "source": source, "role": "fx", "audio_inputs": 2, "audio_outputs": 2,
                         "domain": recipe["domain"], "semantic": recipe["model"], "cases": recipe["cases"],
                         "reference_sources": recipe["reference_sources"], "aliases_inherit_qualification": False,
                         "qualification": "authored fixture and independent model; execution results must be recorded separately"})
    files["catalog.json"] = canonical({"format": "rnbo-original-wave4-fixtures-v1", "format_version": 1,
                                      "license": "MIT", "rnbo_version": "1.4.4", "sample_rate": 44100,
                                      "block_frames": 256, "seed": 305419896,
                                      "warmup_input": "two zero planes", "input_format": "binary32 planes",
                                      "event_order": "no events in this initial exact mode",
                                      "fixtures": fixtures, "hardware_qualified": False,
                                      "performance_measured": False})
    return files


def generate(value: dict, output: Path, fixture_ids: list[str] | None = None) -> dict[str, bytes]:
    """Validate completely, then atomically publish into a fresh directory."""
    files = render(value, fixture_ids)
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise ValueError("Use a new output directory")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".rnbo-original-fixtures-", dir=output.parent))
    try:
        for name, data in files.items():
            (temporary / name).write_bytes(data)
        if output.exists() or output.is_symlink():
            raise ValueError("Output appeared during generation")
        os.rename(temporary, output)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recipes", type=Path, default=DEFAULT_RECIPES)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--fixture", action="append", dest="fixture_ids")
    args = parser.parse_args()
    try:
        files = generate(json.loads(args.recipes.read_text()), args.out, args.fixture_ids)
    except (ValueError, OSError) as exc:
        parser.exit(1, f"Fixture generation failed: {exc}\n")
    print(json.dumps({"output": str(args.out.resolve()), "original_fixtures": len(files)-1,
                      "generated_RNBO_CPP": False, "execution_qualified": False}))


if __name__ == "__main__":
    main()
