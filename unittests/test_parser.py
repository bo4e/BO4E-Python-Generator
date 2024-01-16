from pathlib import Path

from datamodel_code_generator import DataModelType, PythonVersion
from datamodel_code_generator.model import get_data_model_types

from bo4e_generator.parser import OutputType, get_bo4e_data_model_types, remove_future_import
from bo4e_generator.schema import get_namespace

INPUT_DIR = Path("unittests/test_data/bo4e_schemas")


class TestParser:
    def test_get_bo4e_data_model_types(self) -> None:
        namespace = get_namespace(INPUT_DIR)
        data_model_types = get_bo4e_data_model_types(
            DataModelType.PydanticV2BaseModel, target_python_version=PythonVersion.PY_311, namespace=namespace
        )
        data_model_types_compare = get_data_model_types(
            DataModelType.PydanticV2BaseModel, target_python_version=PythonVersion.PY_311
        )
        assert (data_model_types.root_model) == data_model_types_compare.root_model
        assert (data_model_types.field_model) == data_model_types_compare.field_model
        assert (
            data_model_types.dump_resolve_reference_action
        ) == data_model_types_compare.dump_resolve_reference_action
        assert (data_model_types.known_third_party) == data_model_types_compare.known_third_party

    def test_remove_future_import(self) -> None:
        assert ("") == remove_future_import("from __future__ import annotations\n\n", OutputType.PYDANTIC_V2)
