import os
from pathlib import Path

from bo4e_generator.schema import camel_to_snake, get_namespace, get_version

INPUT_DIR = Path("unittests/test_data/bo4e_schemas")
BASE_DIR = Path(__file__).parents[1]


class TestSchema:
    def test_camel_to_snake(self) -> None:
        camelcasestring = "LastgangKompakt"
        snakecasestring = "lastgang_kompakt"
        assert snakecasestring == camel_to_snake(camelcasestring)

    def test_get_namespace(self):
        os.chdir(BASE_DIR)
        namespace = get_namespace(INPUT_DIR)
        keywords = ["Kosten", "Rechnung", "Zaehler"]
        assert all(any(substring in key for key in namespace) for substring in keywords)

    def test_get_version(self):
        os.chdir(BASE_DIR)
        namespace = get_namespace(INPUT_DIR)
        version = get_version(namespace)
        assert version == "0.6.1rc13"
