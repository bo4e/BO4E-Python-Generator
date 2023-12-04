"""
This module contains functionality to retrieve information about the schemas.
"""
import json
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel

SchemaType = dict[str, Any]


class SchemaMetadata(BaseModel):
    """
    Metadata about a schema.
    """

    schema_text: str
    schema_parsed: SchemaType
    class_name: str
    pkg: str
    "e.g. 'bo'"
    input_file: Path
    output_file: Path
    "The output file will be a relative path"
    module_name: str
    "e.g. 'preisblatt_netznutzung"

    def save(self, content: str):
        """
        Save the content to the file defined by `output_file`. Creates parent directories if needed.
        """
        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        self.output_file.write_text(content)

    def __str__(self):
        return f"{self.pkg}.{self.class_name}"


def camel_to_snake(name: str) -> str:
    """
    Convert a camel case string to snake case. Credit to https://stackoverflow.com/a/1176023/21303427
    """
    name = re.sub("([^_])([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", name).lower()


def get_namespace(input_directory: Path) -> dict[str, SchemaMetadata]:
    """
    Create a namespace for the bo4e classes.
    """

    namespace: dict[str, SchemaMetadata] = {}
    for file_path in input_directory.rglob("*.json"):
        schema_text = file_path.read_text()
        schema_parsed = json.loads(schema_text)
        class_name = schema_parsed["title"].replace(" ", "_")
        module_name = camel_to_snake(class_name)

        namespace[class_name] = SchemaMetadata(
            pkg=file_path.parent.name,
            module_name=module_name,
            input_file=file_path,
            output_file=file_path.relative_to(input_directory).with_name(f"{module_name}.py"),
            schema_text=schema_text,
            schema_parsed=schema_parsed,
            class_name=class_name,
        )
    return namespace


def get_version(namespace: dict[str, SchemaMetadata]) -> str:
    """
    Get the version of the bo4e schemas.
    """
    # The chosen class is arbitrary. All bo's and com's should contain the same version information.
    try:
        return namespace["Angebot"].schema_parsed["properties"]["_version"]["default"]
    except KeyError:
        return "unknown"
