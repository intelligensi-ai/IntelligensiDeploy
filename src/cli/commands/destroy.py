import typer

def destroy(target: str = typer.Argument(..., help="Deployment target to destroy")):
    typer.echo(f"🧹 Destroying {target} (placeholder)")
