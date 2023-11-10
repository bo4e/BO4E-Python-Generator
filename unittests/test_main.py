import os
from pathlib import Path
from traceback import format_tb

from click.testing import CliRunner
from pydantic import BaseModel

from bo4e_generator.__main__ import main
from bo4e_generator.parser import generate_bo4e_schema
from bo4e_generator.schema import get_namespace

BASE_DIR = Path(__file__).parents[1]
OUTPUT_DIR = Path("unittests/output/bo4e")
INPUT_DIR = Path("unittests/test_data/bo4e_schemas")


class TestMain:
    def test_main(self):
        os.chdir(BASE_DIR)
        runner = CliRunner()
        result = runner.invoke(main, ["--input-dir", str(INPUT_DIR), "--output-dir", str(OUTPUT_DIR), "-p2"])

        assert (
            result.exit_code == 0
        ), f"{result.exc_info[0].__name__}: {result.exc_info[1]}\n{''.join(format_tb(result.exc_info[2]))}"
        assert (OUTPUT_DIR / "bo" / "angebot.py").exists()
        assert (OUTPUT_DIR / "bo" / "preisblatt_netznutzung.py").exists()
        assert (OUTPUT_DIR / "com" / "com.py").exists()
        assert (OUTPUT_DIR / "enum" / "typ.py").exists()

        # pylint: disable=import-outside-toplevel, import-error
        from .output.bo4e.bo.angebot import Angebot  # type: ignore[import-not-found]

        assert issubclass(Angebot, BaseModel)
        assert "typ" in Angebot.model_fields

        from .output.bo4e import __version__  # type: ignore[import-not-found]

        assert __version__ == "0.6.1rc13"

    def test_single(self):
        os.chdir(BASE_DIR)
        namespace = get_namespace(INPUT_DIR.resolve(), OUTPUT_DIR.resolve())
        schema_metadata = namespace["Angebot"]
        result = generate_bo4e_schema(schema_metadata, namespace)

        assert "class Angebot(BaseModel):" in result
        assert "    typ: Annotated[Typ" in result
