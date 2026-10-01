#!/usr/bin/env python3
"""Validate the standalone plugin manifest against the bundled Cursor schema."""
import json
from pathlib import Path
from jsonschema import validators

root = Path(__file__).resolve().parent.parent
schema = json.loads((root / "schemas/plugin.schema.json").read_text())
manifest = json.loads((root / ".cursor-plugin/plugin.json").read_text())
validator = validators.validator_for(schema)
validator.check_schema(schema)
validator(schema).validate(manifest)
print("OK: Cursor plugin manifest schema")
