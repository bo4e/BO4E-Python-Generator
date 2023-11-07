from pathlib import Path

from click.testing import CliRunner
from pydantic import BaseModel

from bo4e_generator.__main__ import main
from bo4e_generator.parser import generate_bo4e_schema
from bo4e_generator.schema import get_namespace

OUTPUT_DIR = Path(__file__).parent / "output/bo4e"
INPUT_DIR = Path(__file__).parent / "test_data/bo4e_schemas"


class TestMain:
    def test_main(self):
        runner = CliRunner()
        result = runner.invoke(main, ["--input-dir", str(INPUT_DIR), "--output-dir", str(OUTPUT_DIR)])
        # generate_bo4e_schemas(input_directory=INPUT_DIR, output_directory=OUTPUT_DIR)
        assert result.exit_code == 0, f"Error: {result.output}"
        assert (OUTPUT_DIR / "bo" / "angebot.py").exists()
        assert (OUTPUT_DIR / "bo" / "preisblatt_netznutzung.py").exists()
        assert (OUTPUT_DIR / "com" / "com.py").exists()
        assert (OUTPUT_DIR / "enum" / "typ.py").exists()

        # pylint: disable=import-outside-toplevel, import-error
        from .output.bo4e.bo.angebot import Angebot  # type: ignore[import-not-found]

        assert issubclass(Angebot, BaseModel)
        assert "typ" in Angebot.model_fields

    def test_single(self):
        namespace = get_namespace(INPUT_DIR, OUTPUT_DIR)
        schema_metadata = namespace["Angebot"]
        result = generate_bo4e_schema(schema_metadata, namespace)

        assert "class Angebot(BaseModel):" in result
        assert "    typ: Annotated[Typ" in result
