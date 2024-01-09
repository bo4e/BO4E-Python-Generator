"""
Contains code to generate pydantic v2 models from json schemas.
Since the used tool doesn't support all features we need, we monkey patch some functions.
"""
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, DefaultDict, Union

import black
import isort
from jinja2 import Environment, FileSystemLoader

from bo4e_generator.schema import SchemaMetadata


def adapt_parse_for_sql(
    input_directory: Path, namespace: dict[str, SchemaMetadata]
) -> tuple[dict[str, SchemaMetadata], dict[str, Any], Path, dict[str, str]]:
    """
    Scans fields of parsed classes to modify them to meet the SQLModel specifics and to introduce relationships.
    Returns additional information, an input path with modified json schemas and arguments for the parser
    """
    additional_arguments: dict[str, Any] = {}
    additional_sql_data: DefaultDict[str, Any] = defaultdict(dict)
    add_relation: DefaultDict[str, dict[str, Any]] = defaultdict(dict)
    relation_imports: DefaultDict[str, dict[str, str]] = defaultdict(dict)

    for schema_metadata in namespace.values():
        if schema_metadata.pkg != "enum":
            # list of fields which will be replaced by modified versions
            del_fields = []
            for field, val in schema_metadata.schema_parsed["properties"].items():
                if "$ref" in str(val) or "array" in str(val):
                    del_fields.append(field)
            for field in del_fields:
                add_relation, relation_imports = create_sql_field(
                    field, schema_metadata.class_name, namespace, add_relation, relation_imports
                )

                del schema_metadata.schema_parsed["properties"][field]
            # store the reduced version. The modified fields will be added in the BaseModel.jinja2 schema
            schema_metadata.schema_text = json.dumps(schema_metadata.schema_parsed, indent=2, ensure_ascii=False)

            # add primary key
            additional_sql_data[schema_metadata.class_name]["SQL"] = {
                "primary": schema_metadata.class_name.lower()
                + "_sqlid: uuid_pkg.UUID = Field( default_factory=uuid_pkg.uuid4, primary_key=True, index=True, "
                "nullable=False )"
            }
    # pass additional fields and imports to dictionary for parser
    for schema_metadata in namespace.values():
        if schema_metadata.class_name in add_relation:
            additional_sql_data[schema_metadata.class_name]["SQL"]["relations"] = add_relation[
                schema_metadata.class_name
            ]
        if schema_metadata.class_name in relation_imports:
            additional_sql_data[schema_metadata.class_name]["SQL"]["relationimports"] = relation_imports[
                schema_metadata.class_name
            ]
        if schema_metadata.class_name + "ADD" in relation_imports:
            additional_sql_data[schema_metadata.class_name]["SQL"]["imports"] = relation_imports[
                schema_metadata.class_name + "ADD"
            ]
    additional_arguments["extra_template_data"] = additional_sql_data
    additional_arguments["additional_imports"] = ["sqlmodel.Field", "uuid as uuid_pkg", "sqlmodel.Relationship"]
    additional_arguments["base_class"] = "sqlmodel.SQLModel"
    additional_arguments["custom_template_dir"] = Path(__file__).resolve().parent / Path("custom_templates")

    # save intermediate jsons
    for schema in namespace.values():
        file_path = input_directory / Path("intermediate") / Path(schema.pkg) / Path(schema.class_name + ".json")
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(schema.schema_text, encoding="utf-8")
    input_directory = input_directory / Path("intermediate")

    links: dict[str, str] = {}
    # write linking classes for SQLModel
    if "MANY" in add_relation:
        links = add_relation["MANY"]

    return namespace, additional_arguments, input_directory, links


def return_ref(dictionary: dict[str, Union[str, dict]], target_key: str) -> str:
    """
    returns name of class which is referenced
    """
    for key, value in dictionary.items():
        if key == target_key and isinstance(value, str):
            return (value.split("/")[-1]).split(".json")[0]
        if isinstance(value, dict):
            return return_ref(value, target_key)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    return return_ref(item, target_key)
    return ""


# pylint: disable=too-many-branches
# pylint: disable=too-many-statements
def create_sql_field(
    field_name: str,
    class_name: str,
    namespace: dict[str, SchemaMetadata],
    add_fields: DefaultDict[str, dict[str, Any]],
    add_imports: DefaultDict[str, dict[str, str]],
) -> tuple[DefaultDict[str, dict[str, Any]], DefaultDict[str, dict[str, str]]]:
    """
    Parses field with references to other classes, enums and lists, and converts it to SQLModel field.
    """
    field_from_json = namespace[class_name].schema_parsed["properties"][field_name]
    reference_name = return_ref(field_from_json, "$ref")
    default = None
    is_optional = ""
    is_list = False
    list_type = None
    typing_dict: dict[str, str] = {"string": "str", "integer": "int"}
    if "default" in field_from_json and field_from_json["default"] != "null" and field_from_json["default"] is not None:
        default = f'{reference_name}.{field_from_json["default"]}'
    if "anyOf" in field_from_json:
        for item in field_from_json["anyOf"]:
            if "type" in item:
                if item["type"] == "null":
                    is_optional = "| None"
                if item["type"] == "array":
                    is_list = True
                    if "type" in item["items"]:
                        list_type = item["items"]["type"]
    # get rid of underscore in fieldname
    field_name = field_name.lstrip("_")
    # transform lists to sqlalchemy arrays
    if reference_name == "":
        if list_type not in typing_dict:
            raise KeyError(f"transforming SQL list: {list_type} not known")
        type_hint = typing_dict[list_type]
        sa_type = list_type.capitalize()
        add_imports[class_name + "ADD"]["Column, ARRAY, " + sa_type] = "sqlalchemy"

        add_fields[class_name][f"{field_name}"] = (
            f"List[{type_hint}] "
            + is_optional
            + f' = Field({default}, title="{field_name}", sa_column=Column( ARRAY( {sa_type} )))'
        )

    # transform references
    else:
        if namespace[reference_name].pkg == "enum":
            if is_list:
                add_fields[class_name][f"{field_name}"] = (
                    f"List[{reference_name}]" + is_optional + f" = Field({default},"
                    f' sa_column=Column( ARRAY( Enum( {reference_name}, name="{reference_name.lower()}"))))'
                )
            else:
                add_fields[class_name][f"{field_name}"] = f"{reference_name}" + is_optional + f"= Field({default})"

            # import enums
            if is_list:
                add_imports[class_name + "ADD"]["Column, ARRAY, Enum"] = "sqlalchemy"
                add_imports[class_name + "ADD"]["List"] = "typing"
            add_imports[class_name + "ADD"][
                reference_name
            ] = f"{namespace[reference_name].pkg}.{namespace[reference_name].module_name}"
        else:
            add_imports[class_name + "ADD"]["List"] = "typing"
            add_imports[reference_name + "ADD"]["List"] = "typing"
            if is_list:
                if class_name not in add_fields["MANY"]:
                    add_fields["MANY"][class_name] = [reference_name]
                elif reference_name not in add_fields["MANY"][class_name]:
                    add_fields["MANY"][class_name].append(reference_name)
                add_fields[class_name][f"{field_name}"] = (
                    f'List["{reference_name}"] ='
                    f' Relationship(back_populates="{class_name.lower()}_link", '  # f' Relationship(back_populates="{reference_name.lower()}.{class_name.lower()}_link", '
                    f"link_model={class_name}{reference_name}Link)"
                )
                add_fields[reference_name][f"{class_name.lower()}_link"] = (
                    f'List["{class_name}"] ='
                    f' Relationship(back_populates="{field_name}", '  # f' Relationship(back_populates="{class_name.lower()}.{field_name}", '
                    f"link_model={class_name}{reference_name}Link)"
                )
                add_imports[class_name + "ADD"][f"{class_name}{reference_name}Link)"] = "Link"
                add_imports[reference_name + "ADD"][f"{class_name}{reference_name}Link)"] = "Link"
            else:
                add_fields[class_name][f"{field_name}_id"] = (
                    "uuid_pkg.UUID "
                    + is_optional
                    + f' = Field(default=None, foreign_key="{reference_name.lower()}.{reference_name.lower()}_sqlid")'
                )
                add_fields[class_name][f"{field_name}"] = (
                    f'"{reference_name}" ='
                    f' Relationship(back_populates="{class_name.lower()}_{field_name}",'
                    f' sa_relationship_kwargs=dict( foreign_keys="[{class_name}.{field_name}_id]"))'
                )
                add_imports[class_name + "ADD"]["Optional"] = "typing"

                add_fields[reference_name][f"{class_name.lower()}_{field_name}"] = (
                    f'List["{class_name}"] = Relationship(back_populates="{field_name}",'
                    f"sa_relationship_kwargs="
                    f'{{"primaryjoin":'
                    f' "{class_name}.{field_name}_id=={reference_name}.{reference_name.lower()}_sqlid",'
                    f' "lazy": "joined" }})'
                )
            # add_relation_import
            add_imports[class_name][
                reference_name
            ] = f"{namespace[reference_name].pkg}.{namespace[reference_name].module_name}"
            add_imports[reference_name][class_name] = f"{namespace[class_name].pkg}.{namespace[class_name].module_name}"

    return add_fields, add_imports


def write_many_many_links(links: dict[str, str]) -> str:
    """
    use template to write many-to-many link classes to many.py file
    """
    template_path = Path(__file__).resolve().parent / Path("custom_templates")
    environment = Environment(loader=FileSystemLoader(template_path))
    template = environment.get_template("ManyLinks.jinja2")
    python_code = template.render({"class": links})
    python_code = black.format_str(python_code, mode=black.Mode())
    python_code = isort.code(python_code)
    return python_code
