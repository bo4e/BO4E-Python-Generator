"""
Contains code to generate pydantic v2 models from json schemas.
Since the used tool doesn't support all features we need, we monkey patch some functions.
"""
import re
from keyword import iskeyword
from pathlib import Path
from typing import Optional, Set, Tuple

import datamodel_code_generator.parser.base
import datamodel_code_generator.reference
from datamodel_code_generator import DataModelType, PythonVersion
from datamodel_code_generator.model import DataModelSet, get_data_model_types
from datamodel_code_generator.model.enum import Enum as _Enum
from datamodel_code_generator.parser.jsonschema import JsonSchemaParser
from datamodel_code_generator.reference import camel_to_snake, snake_to_upper_camel

from bo4e_generator.schema import SchemaMetadata


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
        if self.file_path:
            return [
                *self.file_path.parts[:-1],
                self.file_path.stem,
                namespace[self.name].pkg,
                namespace[self.name].module_name,
            ]
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


def monkey_patch_field_name_resolver():
    """
    Function taken from datamodel_code_generator.reference.FieldNameResolver.
    Related issue: https://github.com/koxudaxi/datamodel-code-generator/issues/1644
    Related PR: https://github.com/koxudaxi/datamodel-code-generator/pull/1654
    The current implementation struggles if you have enum values starting with invalid characters (e.g. numbers) but
    want to be able to remove leading underscores from field names.
    This monkey patch (dirty) fixes this issue.
    """

    # pylint: disable=too-many-branches
    def _get_valid_name(
        self,
        name: str,
        excludes: Optional[Set[str]] = None,
        ignore_snake_case_field: bool = False,
        upper_camel: bool = False,
    ) -> str:
        if not name:
            name = self.empty_field_name
        if name[0] == "#":
            name = name[1:] or self.empty_field_name

        if self.snake_case_field and not ignore_snake_case_field and self.original_delimiter is not None:
            name = snake_to_upper_camel(name, delimiter=self.original_delimiter)

        name = re.sub(r"[¹²³⁴⁵⁶⁷⁸⁹]|\W", "_", name)
        if name[0].isnumeric():
            name = f"{self.special_field_name_prefix}{name}"  # Changed line by me

        # We should avoid having a field begin with an underscore, as it
        # causes pydantic to consider it as private
        while name.startswith("_"):
            if self.remove_special_field_name_prefix:
                name = name[1:]
            else:
                name = f"{self.special_field_name_prefix}{name}"
                break
        if self.capitalise_enum_members or self.snake_case_field and not ignore_snake_case_field:
            name = camel_to_snake(name)
        count = 1
        # pylint: disable=protected-access
        if iskeyword(name) or not self._validate_field_name(name):
            name += "_"
        if upper_camel:
            new_name = snake_to_upper_camel(name)
        elif self.capitalise_enum_members:
            new_name = name.upper()
        else:
            new_name = name
        while (
            not (new_name.isidentifier() or not self._validate_field_name(new_name))
            or iskeyword(new_name)
            or (excludes and new_name in excludes)
        ):
            new_name = f"{name}{count}" if upper_camel else f"{name}_{count}"
            count += 1
        return new_name

    datamodel_code_generator.reference.FieldNameResolver.get_valid_name = _get_valid_name


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


def create_init_files(output_path: Path) -> None:
    """
    Create __init__.py files in all subdirectories of the given output directory and in the directory itself.
    """
    (output_path / "__init__.py").touch()
    for directory in output_path.glob("**/"):
        (directory / "__init__.py").touch()


def remove_future_import(python_code: str) -> str:
    """
    Remove the future import from the generated code.
    """
    return re.sub(r"from __future__ import annotations\n\n", "", python_code)


def generate_bo4e_schema(schema_metadata: SchemaMetadata, namespace: dict[str, SchemaMetadata]) -> str:
    """
    Generate a pydantic v2 model from the given schema. Returns the resulting code as string.
    """
    data_model_types = get_bo4e_data_model_types(
        DataModelType.PydanticV2BaseModel, target_python_version=PythonVersion.PY_311, namespace=namespace
    )
    monkey_patch_field_name_resolver()
    monkey_patch_relative_import()

    parser = JsonSchemaParser(
        schema_metadata.schema_text,
        data_model_type=data_model_types.data_model,
        data_model_root_type=data_model_types.root_model,
        data_model_field_type=data_model_types.field_model,
        data_type_manager_type=data_model_types.data_type_manager,
        dump_resolve_reference_action=data_model_types.dump_resolve_reference_action,
        use_annotated=True,
        use_double_quotes=True,
        use_schema_description=True,
        use_subclass_enum=True,
        use_standard_collections=True,
        use_union_operator=True,
        set_default_enum_member=True,
        snake_case_field=True,
        field_constraints=True,
        class_name=schema_metadata.class_name,
        capitalise_enum_members=True,
        base_path=schema_metadata.input_file.parent,
        remove_special_field_name_prefix=True,
        special_field_name_prefix="field_",
        allow_extra_fields=False,
    )
    result = parser.parse()
    if isinstance(result, dict):
        if schema_metadata.module_name.startswith("_"):
            # Because somehow the generator uses the prefix also on the module name. Don't know why.
            module_path = (schema_metadata.pkg, f"field{schema_metadata.module_name}.py")
        else:
            module_path = (schema_metadata.pkg, f"{schema_metadata.module_name}.py")
        try:
            result = result[module_path].body
        except KeyError as error:
            raise KeyError(
                f"Could not find module {'.'.join(module_path)} in results: "
                f"{list(result.keys())}"  # type: ignore[union-attr]
                # Item "str" of "str | dict[tuple[str, ...], Result]" has no attribute "keys"
                # Somehow, mypy is not good enough to understand the instance-check above
            ) from error

    result = remove_future_import(result)
    return result
