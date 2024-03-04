import os
from pathlib import Path

from datamodel_code_generator import DataModelType, PythonVersion
from datamodel_code_generator.model import get_data_model_types

from bo4e_generator.parser import (
    OutputType,
    bo4e_init_file_content,
    bo4e_version_file_content,
    get_bo4e_data_model_types,
    parse_bo4e_schemas,
    remove_future_import,
)
from bo4e_generator.schema import camel_to_snake, get_namespace

INPUT_DIR = Path("unittests/test_data/bo4e_schemas")
BASE_DIR = Path(__file__).parents[1]


class TestParser:
    def test_get_bo4e_data_model_types(self) -> None:
        os.chdir(BASE_DIR)
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

    def test_bo4e_version_file_content(self) -> None:
        version = "0.6.1rc13"
        file_content = bo4e_version_file_content(version)
        assert version in file_content

    def test_bo4e_init_file_content(self) -> None:
        os.chdir(BASE_DIR)
        namespace = get_namespace(INPUT_DIR)
        version = "0.6.1rc13"
        file_content = bo4e_init_file_content(namespace, version)
        assert all(key in file_content for key in namespace)

    def test_remove_future_import(self) -> None:
        assert ("") == remove_future_import("from __future__ import annotations\n\n")

    def test_parse_boe4_schemas(self) -> None:
        os.chdir(BASE_DIR)
        namespace = get_namespace(INPUT_DIR)
        input_directory = INPUT_DIR.resolve()
        file_content = parse_bo4e_schemas(input_directory, namespace, OutputType.PYDANTIC_V2)
        assert all(any(camel_to_snake(substring) in str(key) for key in file_content) for substring in namespace)
