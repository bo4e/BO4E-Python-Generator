"""
This module is the entry point for the CLI bo4e-generator.
"""

import shutil
from pathlib import Path
from typing import Optional

import click

from bo4e_generator.parser import OutputType, bo4e_init_file_content, bo4e_version_file_content, parse_bo4e_schemas
from bo4e_generator.schema import get_namespace, get_version
from bo4e_generator.sqlparser import format_code


def resolve_paths(input_directory: Path, output_directory: Path) -> tuple[Path, Path]:
    """
    Resolve the input and output paths. The data-model-parser have problems with handling relative paths.
    """
    if not input_directory.is_absolute():
        input_directory = input_directory.resolve()
    if not output_directory.is_absolute():
        output_directory = output_directory.resolve()
    return input_directory, output_directory


def generate_bo4e_schemas(
    input_directory: Path,
    output_directory: Path,
    output_type: OutputType,
    clear_output: bool = False,
    target_version: Optional[str] = None,
):
    """
    Generate all BO4E schemas from the given input directory and save them in the given output directory.
    """
    input_directory, output_directory = resolve_paths(input_directory, output_directory)
    namespace = get_namespace(input_directory)
    file_contents = parse_bo4e_schemas(input_directory, namespace, output_type)
    version = get_version(target_version, namespace)
    file_contents[Path("__version__.py")] = bo4e_version_file_content(version)
    file_contents[Path("__init__.py")] = bo4e_init_file_content(namespace, version)
    if clear_output and output_directory.exists():
        shutil.rmtree(output_directory)

    for relative_file_path, file_content in file_contents.items():
        file_path = output_directory / relative_file_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_content = format_code(file_content)
        file_path.write_text(file_content, encoding="utf-8")
        print(f"Created {file_path}")
    print("Done.")


@click.command()
@click.option(
    "--input-dir",
    "-i",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Input directory which contains the JSON schemas.",
    required=True,
)
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(exists=False, file_okay=False, path_type=Path),
    help="Output directory for the generated python files.",
    required=True,
)
@click.option(
    "--output-type",
    "-ot",
    type=click.Choice(list(map(lambda x: x.name, OutputType)), case_sensitive=False),
    # Taken from https://github.com/pallets/click/issues/605#issuecomment-889462570
    help="Output type for the generated python files.",
    required=False,
    default=OutputType.PYDANTIC_V2,
)
@click.option(
    "--clear-output",
    help="Clear the output directory before saving the schemas. "
    "Otherwise, if e.g. schemas got deleted, they will not be removed from the output directory. "
    "Note: Generated output files will always overwrite existing files.",
    is_flag=True,
    default=False,
)
@click.option(
    "--target-version",
    "-t",
    help="Optionally set the target BO4E version. If not defined, it tries to read it from `_version`. "
    "If it can't be found, it will be set to 'unknown'.",
    type=str,
    default=None,
)
@click.version_option(package_name="BO4E-Python-Generator")
def main(
    input_dir: Path, output_dir: Path, clear_output: bool, output_type: OutputType, target_version: Optional[str] = None
):
    """
    CLI entry point for the bo4e-generator.
    """
    generate_bo4e_schemas(input_dir, output_dir, output_type, clear_output, target_version)


if __name__ == "__main__":
    # pylint: disable=no-value-for-parameter
    main()
