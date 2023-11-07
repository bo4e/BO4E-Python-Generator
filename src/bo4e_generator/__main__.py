"""
This module is the entry point for the CLI bo4e-generator.
"""
from pathlib import Path

import click

from bo4e_generator.parser import create_init_files, generate_bo4e_schema
from bo4e_generator.schema import get_namespace


def generate_bo4e_schemas(input_directory: Path, output_directory: Path):
    """
    Generate all BO4E schemas from the given input directory and save them in the given output directory.
    """
    namespace = get_namespace(input_directory, output_directory)
    for schema_metadata in namespace.values():
        result = generate_bo4e_schema(schema_metadata, namespace)
        schema_metadata.save(result)
        print(f"Generated {schema_metadata}")
    create_init_files(output_directory)
    print(f"Generated __init__.py files in {output_directory}")


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
@click.help_option()
@click.version_option(package_name="BO4E-Python-Generator")
def main(input_dir: Path, output_dir: Path):
    """
    CLI entry point for the bo4e-generator.
    """
    generate_bo4e_schemas(input_dir, output_dir)


if __name__ == "__main__":
    # pylint: disable=no-value-for-parameter
    main()
