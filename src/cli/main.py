import typer
from .commands.deploy import deploy
from .commands.status import status
from .commands.destroy import destroy
from .commands.init import init

app = typer.Typer(help="Intelligensi AI Deployment Engine")

app.command()(deploy)
app.command()(status)
app.command()(destroy)
app.command()(init)

def main():
    app()

if __name__ == "__main__":
    main()
