import os
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any, DefaultDict

from bo4e_generator.schema import get_namespace
from bo4e_generator.sqlparser import (
    adapt_parse_for_sql,
    create_sql_field,
    format_code,
    remove_pydantic_field_import,
    return_ref,
    write_many_many_links,
)

INPUT_DIR = Path("unittests/test_data/bo4e_schemas")
CLASSNAME = "Angebot"
FIELDNAME = "_typ"
BASE_DIR = Path(__file__).parents[1]


class TestSQLParser:
    def test_remove_pydantic_field_import(self) -> None:
        assert "from pydantic import BaseModel\n" == remove_pydantic_field_import(
            "from pydantic import BaseModel, Field\n"
        )
        assert "from pydantic import BaseModel\n" == remove_pydantic_field_import(
            "from pydantic import Field, BaseModel\n"
        )
        assert "" == remove_pydantic_field_import("from pydantic import Field\n")

    def test_adapt_parse_for_sql(self) -> None:
        os.chdir(BASE_DIR)
        namespace = get_namespace(INPUT_DIR)
        additional_arguments: dict[str, Any] = {}
        links: dict[str, str] = {}
        namespace, additional_arguments, input_directory, links = adapt_parse_for_sql(INPUT_DIR, namespace)
        assert input_directory == (INPUT_DIR.joinpath("intermediate"))
        os.chdir(BASE_DIR)
        shutil.rmtree(input_directory)
        keywords = ["extra_template_data", "additional_imports", "base_class", "custom_template_dir"]
        assert all(any(substring in key for key in additional_arguments) for substring in keywords)
        keywords = ["Kosten", "Rechnung", "Zaehler"]
        assert all(any(substring in key for key in links) for substring in keywords)

    def test_return_ref(self) -> None:
        namespace = get_namespace(INPUT_DIR)
        field_from_json = namespace[CLASSNAME].schema_parsed["properties"][FIELDNAME]
        reference_name = return_ref(field_from_json, "$ref")
        assert reference_name == "Typ"

    def test_create_sql_field(self) -> None:
        namespace = get_namespace(INPUT_DIR)
        add_relation: DefaultDict[str, dict[str, Any]] = defaultdict(dict)
        relation_imports: DefaultDict[str, dict[str, str]] = defaultdict(dict)
        add_relation_comp: DefaultDict[str, dict[str, Any]] = defaultdict(dict)
        relation_imports_comp: DefaultDict[str, dict[str, Any]] = defaultdict(dict)
        add_relation, relation_imports = create_sql_field(
            FIELDNAME, CLASSNAME, namespace, add_relation, relation_imports
        )
        add_relation_comp.update({"Angebot": {"typ": "Typ| None= Field(Typ.ANGEBOT)"}})
        relation_imports_comp.update({"AngebotADD": {"Typ": "enum.typ"}})
        assert add_relation == add_relation_comp
        assert relation_imports == relation_imports_comp

    def test_write_many_many_links(self) -> None:
        links: dict[str, str] = {}
        namespace = get_namespace(INPUT_DIR)
        add_relation: DefaultDict[str, dict[str, Any]] = defaultdict(dict)
        relation_imports: DefaultDict[str, dict[str, str]] = defaultdict(dict)
        add_relation, relation_imports = create_sql_field(
            "zusatzAttribute", CLASSNAME, namespace, add_relation, relation_imports
        )
        links = add_relation["MANY"]
        file_contents = write_many_many_links(links)
        keywords = ["AngebotzusatzAttributeLink", "angebot_id", "zusatzattribut_id"]
        assert all(substring in file_contents for substring in keywords)
