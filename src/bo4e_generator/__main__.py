"""
This module is the entry point for the CLI bo4e-generator.
"""
from pathlib import Path

import click

from bo4e_generator.parser import bo4e_init_file_content, parse_bo4e_schemas
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


def generate_bo4e_schemas(input_directory: Path, output_directory: Path, pydantic_v1: bool = False):
    """
    Generate all BO4E schemas from the given input directory and save them in the given output directory.
    """
    input_directory, output_directory = resolve_paths(input_directory, output_directory)
    namespace = get_namespace(input_directory)
    file_contents = parse_bo4e_schemas(input_directory, namespace, pydantic_v1)
    file_contents[Path("__init__.py")] = bo4e_init_file_content(get_version(namespace))
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
@click.help_option()
@click.version_option(package_name="BO4E-Python-Generator")
def main(input_dir: Path, output_dir: Path, pydantic_v1: bool):
    """
    CLI entry point for the bo4e-generator.
    """
    generate_bo4e_schemas(input_dir, output_dir, pydantic_v1)


if __name__ == "__main__":
    # pylint: disable=no-value-for-parameter
    main()
