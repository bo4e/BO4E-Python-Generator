import os
from pathlib import Path
from traceback import format_tb

from click.testing import CliRunner
from pydantic import BaseModel

from bo4e_generator.__main__ import main, resolve_paths

BASE_DIR = Path(__file__).parents[1]
OUTPUT_DIR = Path("unittests/output/bo4e")
INPUT_DIR = Path("unittests/test_data/bo4e_schemas")


class TestMain:
    def test_main(self):
        os.chdir(BASE_DIR)
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["--input-dir", str(INPUT_DIR), "--output-dir", str(OUTPUT_DIR), "-ot", "pydantic_v2", "--clear-output"],
        )

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
        assert "datetime.datetime" in str(Angebot.model_fields["angebotsdatum"].annotation)

        from .output.bo4e import __version__  # type: ignore[import-not-found]

        assert __version__ == "0.6.1rc13"

    def test_resolve_paths(self) -> None:
        relative_path_input = Path(INPUT_DIR)
        absolute_path_input = relative_path_input.resolve()
        relative_path_output = Path(OUTPUT_DIR)
        absolute_path_output = relative_path_output.resolve()
        assert (absolute_path_input, absolute_path_output) == resolve_paths(INPUT_DIR, OUTPUT_DIR)
