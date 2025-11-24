import typer

def deploy(
    target: str = typer.Argument(..., help="What to deploy: image-server | weaviate | gpu-node")
):
    typer.echo(f"🚀 Deploying {target} (placeholder)")
