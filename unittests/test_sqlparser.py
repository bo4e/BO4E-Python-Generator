from collections import defaultdict
from pathlib import Path
from typing import Any, DefaultDict

from bo4e_generator.schema import get_namespace
from bo4e_generator.sqlparser import create_sql_field, return_ref, write_many_many_links

INPUT_DIR = Path("unittests/test_data/bo4e_schemas")
CLASSNAME = "Angebot"
FIELDNAME = "_typ"


class TestSQLParser:
    def test_return_ref(self):
        namespace = get_namespace(INPUT_DIR)
        field_from_json = namespace[CLASSNAME].schema_parsed["properties"][FIELDNAME]
        reference_name = return_ref(field_from_json, "$ref")
        assert reference_name == "Typ"

    def test_create_sql_field(self):
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

    def test_write_many_many_links(self):
        links: dict[str, str] = {}
        namespace = get_namespace(INPUT_DIR)
        add_relation: DefaultDict[str, dict[str, Any]] = defaultdict(dict)
        relation_imports: DefaultDict[str, dict[str, str]] = defaultdict(dict)
        add_relation, relation_imports = create_sql_field(
            "externeReferenzen", CLASSNAME, namespace, add_relation, relation_imports
        )
        links = add_relation["MANY"]
        file_contents = write_many_many_links(links)
        keywords = ["AngebotExterneReferenzLink", "angebot_id", "externereferenz_id"]
        assert all(substring in file_contents for substring in keywords)
