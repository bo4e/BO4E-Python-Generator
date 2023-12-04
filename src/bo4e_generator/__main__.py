"""
This module is the entry point for the CLI bo4e-generator.
"""
import shutil
from pathlib import Path

import click

from bo4e_generator.parser import bo4e_init_file_content, bo4e_version_file_content, parse_bo4e_schemas
from bo4e_generator.schema import get_namespace, get_version


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
    input_directory: Path, output_directory: Path, pydantic_v1: bool = False, clear_output: bool = False
):
    """
    Generate all BO4E schemas from the given input directory and save them in the given output directory.
    """
    input_directory, output_directory = resolve_paths(input_directory, output_directory)
    namespace = get_namespace(input_directory)
    file_contents = parse_bo4e_schemas(input_directory, namespace, pydantic_v1)
    version = get_version(namespace)
    file_contents[Path("__version__.py")] = bo4e_version_file_content(version)
    file_contents[Path("__init__.py")] = bo4e_init_file_content(namespace, version)
    if clear_output and output_directory.exists():
        shutil.rmtree(output_directory)

    for relative_file_path, file_content in file_contents.items():
        file_path = output_directory / relative_file_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(file_content)
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
    "--pydantic-v1/--pydantic-v2",
    "-p1/-p2",
    is_flag=True,
    help="Generate pydantic v1 models instead of pydantic v2 models.",
    required=False,
    default=False,
)
@click.option(
    "--clear-output",
    help="Clear the output directory before saving the schemas. "
    "Otherwise, if e.g. schemas got deleted, they will not be removed from the output directory. "
    "Note: Generated output files will always overwrite existing files.",
    is_flag=True,
    default=False,
)
@click.version_option(package_name="BO4E-Python-Generator")
def main(input_dir: Path, output_dir: Path, pydantic_v1: bool, clear_output: bool):
    """
    CLI entry point for the bo4e-generator.
    """
    generate_bo4e_schemas(input_dir, output_dir, pydantic_v1, clear_output)


if __name__ == "__main__":
    # pylint: disable=no-value-for-parameter
    main()
