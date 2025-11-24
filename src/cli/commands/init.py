import typer
from pathlib import Path

def init():
    Path("intelligensi.yml").write_text(
        "# Intelligensi Deploy Config\nprovider: lambda-gpu\n"
    )
    typer.echo("✨ Created intelligensi.yml")
