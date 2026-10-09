import json
from pathlib import Path

import jsonschema
import pytest

from budget_core.io.yamlio import load_yaml_text
from budget_core.model import CURRENT_VERSIONS
from budget_core.schemas import SCHEMA_DIR, SCHEMA_MODELS, json_schema, schema_text
from tests.helpers import write_valid_project


def test_every_kind_has_a_schema_and_version() -> None:
    assert set(SCHEMA_MODELS) == set(CURRENT_VERSIONS)


@pytest.mark.parametrize("kind", sorted(CURRENT_VERSIONS))
def test_committed_schemas_are_up_to_date(kind: str) -> None:
    committed = (SCHEMA_DIR / f"{kind}.schema.json").read_text(encoding="utf-8")
    assert committed == schema_text(kind), "run `budget export-schemas src/budget_core/schemas`"


@pytest.mark.parametrize("kind", sorted(CURRENT_VERSIONS))
def test_schemas_are_valid_json_schema(kind: str) -> None:
    jsonschema.Draft202012Validator.check_schema(json_schema(kind))


def test_schemas_require_header_fields() -> None:
    for kind in CURRENT_VERSIONS:
        assert {"schema_version", "kind"} <= set(json_schema(kind)["required"])


def test_generated_project_files_validate_against_schemas(tmp_path: Path) -> None:
    write_valid_project(tmp_path)
    for path in sorted(tmp_path.rglob("*.yaml")):
        data = load_yaml_text(path.read_text(encoding="utf-8")).data
        schema = json.loads(json.dumps(json_schema(data["kind"])))
        jsonschema.validate(data, schema, cls=jsonschema.Draft202012Validator)
