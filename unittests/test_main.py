import os
from pathlib import Path
from traceback import format_tb

from click.testing import CliRunner
from pydantic import BaseModel

from bo4e_generator.__main__ import main

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

        from .output.bo4e import __version__  # type: ignore[import-not-found]

        assert __version__ == "0.6.1rc13"
