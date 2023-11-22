"""
Contains code to generate pydantic v2 models from json schemas.
Since the used tool doesn't support all features we need, we monkey patch some functions.
"""
import json
import os
import re
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any, DefaultDict, Dict, List, Tuple, Union

import datamodel_code_generator.parser.base
import datamodel_code_generator.reference
from datamodel_code_generator import DataModelType, PythonVersion
from datamodel_code_generator.model import DataModelSet, get_data_model_types
from datamodel_code_generator.model.enum import Enum as _Enum
from datamodel_code_generator.parser.jsonschema import JsonSchemaParser
from pydantic.v1.fields import FieldInfo

from bo4e_generator.schema import SchemaMetadata, SchemaType


def get_bo4e_data_model_types(
    data_model_type: DataModelType,
    target_python_version: PythonVersion,
    namespace: dict[str, SchemaMetadata],
    monkey_patch_enum_type: bool = True,
) -> DataModelSet:
    """
    Get the data model types for the data model parser.
    In the first place, it overrides functions such that the namespace of the bo4e-package will be recreated instead of
    "put everything in one file".
    """
    data_model_types = get_data_model_types(data_model_type, target_python_version=target_python_version)

    @property  # type: ignore[misc]
    # "property" used with a non-method
    def _module_path(self) -> list[str]:
        if self.name not in namespace:
            raise ValueError(f"Model not in namespace: {self.name}")
        return [namespace[self.name].pkg, namespace[self.name].module_name]

    @property  # type: ignore[misc]
    # "property" used with a non-method
    def _module_name(self) -> str:
        return ".".join(self.module_path)

    class BO4EDataModel(data_model_types.data_model):  # type: ignore[name-defined]
        # Name "data_model_types.data_model" is not defined
        """Override the data model to use create the namespace."""

        module_path = _module_path
        module_name = _module_name

    if monkey_patch_enum_type:
        setattr(_Enum, "module_path", _module_path)
        setattr(_Enum, "module_name", _module_name)

    return DataModelSet(
        data_model=BO4EDataModel,
        root_model=data_model_types.root_model,
        field_model=data_model_types.field_model,
        data_type_manager=data_model_types.data_type_manager,
        dump_resolve_reference_action=data_model_types.dump_resolve_reference_action,
        known_third_party=data_model_types.known_third_party,
    )


def monkey_patch_relative_import():
    """
    Function taken from datamodel_code_generator.parser.base.
    This function is used to create the relative imports if a referenced model is used in the file.
    Originally, this function would create something like "from ..enum import typ" and a field definition like
    "typ: Annotated[typ.Typ | None, Field(alias='_typ')] = None".
    This is in general a valid way to do it, but pydantic somehow doesn't like it. It will throw an error if you
    attempt to import an enum this way. Looks something like "'Typ' has no attribute 'Typ'".
    Anyway, this monkey patch changes the imports to "from ..enum.typ import Typ" which resolves the issue.
    """

    def relative(current_module: str, reference: str) -> Tuple[str, str]:
        """Find relative module path."""

        current_module_path = current_module.split(".") if current_module else []
        *reference_path, name = reference.split(".")

        if current_module_path == reference_path:
            return "", ""

        i = 0
        for x, y in zip(current_module_path, reference_path):
            if x != y:
                break
            i += 1

        left = "." * (len(current_module_path) - i)
        right = ".".join([*reference_path[i:], name])

        if not left:
            left = "."
        if not right:
            right = name
        elif "." in right:
            extra, right = right.rsplit(".", 1)
            left += extra

        return left, right

    datamodel_code_generator.parser.base.relative = relative


def bo4e_init_file_content(version: str) -> str:
    """
    Create __init__.py files in all subdirectories of the given output directory and in the directory itself.
    """
    return f'""" Contains information about the bo4e version """\n\n__version__ = "{version}"\n'


def remove_future_import(python_code: str, sql_model: bool) -> str:
    """
    Remove the future import from the generated code.
    """
    if sql_model:
        python_code = re.sub(r"from pydantic import (.*?)Field(.*?)\n", r"from pydantic import \1\2\n", python_code)
        python_code = re.sub(r"from pydantic import (.*?)(,|\n)", r"from pydantic import \1\n", python_code)
        python_code = re.sub(r",,", "", python_code)
        python_code = re.sub(r"\.\.", "borm.models.", python_code)
    return re.sub(r"from __future__ import annotations\n\n", "", python_code)


def parse_bo4e_schemas(
    input_directory: Path, namespace: dict[str, SchemaMetadata], pydantic_v1: bool = False, sql_model: bool = False
) -> dict[Path, str]:
    """
    Generate all BO4E schemas from the given input directory. Returns all file contents as dictionary:
    file path (relative to arbitrary output directory) => file content.
    """
    data_model_types = get_bo4e_data_model_types(
        DataModelType.PydanticBaseModel if pydantic_v1 else DataModelType.PydanticV2BaseModel,
        target_python_version=PythonVersion.PY_311,
        namespace=namespace,
    )
    monkey_patch_relative_import()

    additional_arguments: Dict[str, Any] = {}

    if sql_model:
        additional_sql_data: DefaultDict[str, Any] = defaultdict(dict)
        add_relation: Dict[str, Dict[str, str]] = defaultdict(dict)
        relation_imports: Dict[str, Dict[str, str]] = defaultdict(dict)
        for schema_metadata in namespace.values():
            if schema_metadata.pkg != "enum":
                del_prop = []
                for prop, val in schema_metadata.schema_parsed["properties"].items():
                    if "$ref" in str(val):  # and "enum" not in str(val):
                        del_prop.append(prop)
                for prop in del_prop:
                    add_relation, relation_imports = create_sql_field(
                        prop, schema_metadata.class_name, namespace, add_relation, relation_imports
                    )
                    # if schema_metadata.class_name not in add_relation:
                    #     add_relation[schema_metadata.class_name] = {}
                    # ref, relation_dict = transform_schema_dict_sql(prop, schema_metadata)
                    # add_relation[schema_metadata.class_name].update(relation_dict)
                    # if ref not in add_relation:
                    #     add_relation[ref] = {}
                    # add_relation[ref][
                    #     f"{schema_metadata.class_name.lower()}_{prop.lower()}"
                    # ] = f'List["{schema_metadata.class_name}"] = Relationship(back_populates="{prop.lower()}")'
                    # relation_imports[schema_metadata.class_name][ref] = f"{namespace[ref].pkg}.{ref.lower()}"
                    # relation_imports[ref][
                    #     schema_metadata.class_name
                    # ] = f"{schema_metadata.pkg}.{schema_metadata.class_name.lower()}"
                    del schema_metadata.schema_parsed["properties"][prop]
                schema_metadata.schema_text = json.dumps(schema_metadata.schema_parsed, indent=2, ensure_ascii=False)
                additional_sql_data[schema_metadata.class_name]["SQL"] = {
                    "primary": schema_metadata.class_name.lower()
                    + "_sqlid: uuid_pkg.UUID = Field( default_factory=uuid_pkg.uuid4, primary_key=True, index=True, nullable=False )"
                }
        for schema_metadata in namespace.values():
            if schema_metadata.class_name in add_relation:
                additional_sql_data[schema_metadata.class_name]["SQL"]["relations"] = add_relation[
                    schema_metadata.class_name
                ]
            if schema_metadata.class_name in relation_imports:
                additional_sql_data[schema_metadata.class_name]["SQL"]["relationimports"] = relation_imports[
                    schema_metadata.class_name
                ]
            if schema_metadata.class_name + "ENUM" in relation_imports:
                additional_sql_data[schema_metadata.class_name]["SQL"]["imports"] = relation_imports[
                    schema_metadata.class_name + "ENUM"
                ]
        additional_arguments["extra_template_data"] = additional_sql_data
        additional_arguments["additional_imports"] = ["sqlmodel.Field", "uuid as uuid_pkg", "sqlmodel.Relationship"]
        additional_arguments["base_class"] = "sqlmodel.SQLModel"
        additional_arguments["custom_template_dir"] = Path.cwd() / Path("custom_templates")

        # save intermediate jsons
        for schema in namespace.values():
            file_path = input_directory / Path("intermediate") / Path(schema.pkg) / Path(schema.class_name + ".json")
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(schema.schema_text, encoding="utf-8")
        input_directory = input_directory / Path("intermediate")

    parser = JsonSchemaParser(
        input_directory,
        data_model_type=data_model_types.data_model,
        data_model_root_type=data_model_types.root_model,
        data_model_field_type=data_model_types.field_model,
        data_type_manager_type=data_model_types.data_type_manager,
        dump_resolve_reference_action=data_model_types.dump_resolve_reference_action,
        use_annotated=not pydantic_v1,
        use_double_quotes=True,
        use_schema_description=True,
        use_subclass_enum=True,
        use_standard_collections=True,
        use_union_operator=True,
        set_default_enum_member=True,
        snake_case_field=True,
        field_constraints=True,
        capitalise_enum_members=True,
        base_path=input_directory,
        remove_special_field_name_prefix=True,
        allow_extra_fields=False,
        **additional_arguments,
    )
    parse_result = parser.parse()
    if not isinstance(parse_result, dict):
        raise ValueError(f"Unexpected type of parse result: {type(parse_result)}")
    file_contents = {}
    for schema_metadata in namespace.values():
        if schema_metadata.module_name.startswith("_"):
            # Because somehow the generator uses the prefix also on the module name. Don't know why.
            module_path = (schema_metadata.pkg, f"field{schema_metadata.module_name}.py")
        else:
            module_path = (schema_metadata.pkg, f"{schema_metadata.module_name}.py")

        if module_path not in parse_result:
            raise KeyError(
                f"Could not find module {'.'.join(module_path)} in results: "
                f"{list(parse_result.keys())}"  # type: ignore[union-attr]
                # Item "str" of "str | dict[tuple[str, ...], Result]" has no attribute "keys"
                # Somehow, mypy is not good enough to understand the instance-check above
            )

        file_contents[schema_metadata.output_file] = remove_future_import(parse_result.pop(module_path).body, sql_model)

    file_contents.update({Path(*module_path): result.body for module_path, result in parse_result.items()})

    if sql_model:
        shutil.rmtree(input_directory)

    return file_contents


def transform_schema_dict_sql(prop: str, schema: SchemaMetadata) -> Tuple[str, Dict[str, str]]:
    # Extracting relevant information from the input dictionary
    #  schema.schema_parsed["properties"][prop]
    any_of_list = schema.schema_parsed["properties"][prop].get("anyOf", [])

    ref_value = return_ref(schema.schema_parsed["properties"][prop], "$ref")
    # Processing the 'anyOf' list to generate the desired output
    fields: Dict[str, str] = {}
    ref_name = (ref_value.split("/")[-1]).split(".json")[0]
    fields[
        f"{prop}_id"
    ] = f'Optional[uuid_pkg.UUID] = Field(default=None, foreign_key="{ref_name.lower()}.{ref_name.lower()}_sqlid")'
    fields[
        f"{prop}"
    ] = f'Optional[{ref_name}] = Relationship(back_populates="{schema.class_name.lower()}_{prop.lower()}")'
    # for item in any_of_list:
    #     if '$ref' in item:
    #         ref_value = item['$ref']
    #         ref_name = (ref_value.split('/')[-1]).split('.json')[0]#ref_value.split('#')[-1].split('.')[0]
    #         fields[f'{prop}_id'] = f'Optional[uuid_pkg.UUID] = Field(default=None, foreign_key="{ref_name.lower()}.{ref_name.lower()}_sqlid")'
    #         fields[f'{prop}'] = f'Optional[{ref_name}] = Relationship(back_populates="{schema.class_name.lower()}_{prop.lower()}")'

    return ref_name, fields


def return_ref(dictionary: Dict[str, Union[str, Dict]], target_key: str) -> str:
    for key, value in dictionary.items():
        if key == target_key:
            return value
        elif isinstance(value, dict):
            return return_ref(value, target_key)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    return return_ref(item, target_key)
    return ""


def create_sql_field(
    field_name: str,
    class_name: str,
    namespace: dict[str, SchemaMetadata],
    add_fields: DefaultDict[str, Dict[str, str]],
    add_imports: DefaultDict[str, Dict[str, str]],
) -> Tuple[DefaultDict[str, Dict[str, str]], DefaultDict[str, Dict[str, str]]]:
    schema = namespace[class_name]
    field_from_json = schema.schema_parsed["properties"][field_name]
    reference = return_ref(field_from_json, "$ref")
    reference_name = (reference.split("/")[-1]).split(".json")[0]
    default = None
    is_optional = False
    is_list = False
    if "default" in field_from_json:
        default = field_from_json["default"]
    if "anyOf" in field_from_json:
        for item in field_from_json["anyOf"]:
            if "type" in item:
                if item["type"] == "null":
                    is_optional = True
                if item["type"] == "array":
                    is_list = True
    reference_is_enum = namespace[reference_name].pkg == "enum"
    if default is not None:
        default = f"{reference_name}.{default}"
    if reference_is_enum:
        if is_optional:
            if is_list:
                add_fields[class_name][
                    f"{field_name}"
                ] = f'List[{reference_name}] | None = Field({default}, sa_column=Column( ARRAY( Enum( {reference_name}, name="{reference_name.lower()}"))))'
            else:
                add_fields[class_name][f"{field_name}"] = f"{reference_name} | None = Field({default})"
        else:
            if is_list:
                add_fields[class_name][
                    f"{field_name}"
                ] = f'List[{reference_name}] = Field({default}, sa_column=Column( ARRAY( Enum( {reference_name}, name="{reference_name.lower()}"))))'
            else:
                add_fields[class_name][f"{field_name}"] = f"{reference_name} = Field({default})"
        # import enums
        if is_list:
            add_imports[class_name + "ENUM"]["Column, ARRAY, Enum"] = f"sqlalchemy"
            add_imports[class_name + "ENUM"]["List"] = f"typing"
        add_imports[class_name + "ENUM"][reference_name] = f"{namespace[reference_name].pkg}.{reference_name.lower()}"
    else:
        add_imports[class_name + "ENUM"]["List"] = f"typing"
        add_imports[reference_name + "ENUM"]["List"] = f"typing"
        if is_optional:
            if is_list:
                add_fields[class_name][
                    f"{field_name}_id"
                ] = f'uuid_pkg.UUID | None = Field(default=None, foreign_key="{reference_name.lower()}.{reference_name.lower()}_sqlid")'
                add_fields[class_name][
                    f"{field_name}"
                ] = f'List["{reference_name}"] = Relationship(back_populates="{class_name.lower()}_{field_name.lower()}")'
                add_imports[class_name + "ENUM"]["Optional"] = f"typing"
            else:
                add_fields[class_name][
                    f"{field_name}_id"
                ] = f'uuid_pkg.UUID | None = Field(default=None, foreign_key="{reference_name.lower()}.{reference_name.lower()}_sqlid")'
                add_fields[class_name][
                    f"{field_name}"
                ] = f'Optional["{reference_name}"] = Relationship(back_populates="{class_name.lower()}_{field_name.lower()}")'
                add_imports[class_name + "ENUM"]["Optional"] = f"typing"
        else:
            if is_list:
                add_fields[class_name][
                    f"{field_name}_id"
                ] = f'uuid_pkg.UUID = Field(default=None, foreign_key="{reference_name.lower()}.{reference_name.lower()}_sqlid")'
                add_fields[class_name][
                    f"{field_name}"
                ] = f'List["{reference_name}"] = Relationship(back_populates="{class_name.lower()}_{field_name.lower()}")'
            else:
                add_fields[class_name][
                    f"{field_name}_id"
                ] = f'uuid_pkg.UUID = Field(default=None, foreign_key="{reference_name.lower()}.{reference_name.lower()}_sqlid")'
                add_fields[class_name][
                    f"{field_name}"
                ] = f'"{reference_name}" = Relationship(back_populates="{class_name.lower()}_{field_name.lower()}")'
        add_fields[reference_name][
            f"{class_name.lower()}_{field_name.lower()}"
        ] = f'List["{class_name}"] = Relationship(back_populates="{field_name.lower()}")'
        # add_relation_import
        add_imports[class_name][reference_name] = f"{namespace[reference_name].pkg}.{reference_name.lower()}"
        add_imports[reference_name][class_name] = f"{schema.pkg}.{class_name.lower()}"

    return add_fields, add_imports
