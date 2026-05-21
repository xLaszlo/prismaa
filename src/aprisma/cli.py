from __future__ import annotations

from pathlib import Path

import click

from aprisma.generator.generator import generate
from aprisma.parser import parse


@click.group()
def main() -> None:
    """Aprisma — Python Prisma client generator."""


@main.command()
@click.option("--schema", default="schema.prisma", show_default=True, help="Path to schema.prisma")
@click.option("--output", default=None, help="Output directory (overrides schema generator.output)")
def generate_cmd(schema: str, output: str | None) -> None:
    """Generate the Python client from a Prisma schema."""
    schema_path = Path(schema)
    if not schema_path.exists():
        raise click.ClickException(f"Schema file not found: {schema_path}")

    source = schema_path.read_text(encoding="utf-8")
    parsed = parse(source)

    if output:
        out_dir = Path(output)
    elif parsed.generator and parsed.generator.get("output"):
        out_dir = schema_path.parent / parsed.generator.get("output")
    else:
        raise click.ClickException("No output directory specified. Use --output or set generator.output in schema.")

    written = generate(parsed, out_dir)
    for p in written:
        click.echo(f"  wrote {p}")
    click.echo(f"Generated {len(written)} files in {out_dir}")


main.add_command(generate_cmd, name="generate")
