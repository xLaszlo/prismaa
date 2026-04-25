import click


@click.group()
def main() -> None:
    """Prismaa — Python Prisma client generator."""


@main.command()
@click.option("--schema", default="schema.prisma", show_default=True, help="Path to schema.prisma")
@click.option("--output", default=None, help="Output directory (overrides schema generator.output)")
def generate(schema: str, output: str | None) -> None:
    """Generate the Python client from a Prisma schema."""
    raise NotImplementedError("Generator not yet implemented — see PLAN.md Phase 3")
