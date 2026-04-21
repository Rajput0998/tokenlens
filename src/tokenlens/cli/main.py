"""TokenLens CLI — entry point."""

from __future__ import annotations

import typer

app = typer.Typer(
    name="tokenlens",
    help="Token monitoring and prediction platform for AI coding tools.",
    no_args_is_help=True,
)

# Sub-command groups
agent_app = typer.Typer(help="Manage the background collection daemon.")
app.add_typer(agent_app, name="agent")


@app.command()
def version() -> None:
    """Show TokenLens version."""
    from tokenlens import __version__

    typer.echo(f"tokenlens {__version__}")


# Register command modules — import after app/agent_app are defined
from tokenlens.cli.commands.agent import register as register_agent  # noqa: E402
from tokenlens.cli.commands.compare import register as register_compare  # noqa: E402
from tokenlens.cli.commands.data import register as register_data  # noqa: E402
from tokenlens.cli.commands.export import register as register_export  # noqa: E402
from tokenlens.cli.commands.init import register as register_init  # noqa: E402
from tokenlens.cli.commands.mcp import register as register_mcp  # noqa: E402
from tokenlens.cli.commands.ml import register as register_ml  # noqa: E402
from tokenlens.cli.commands.optimize import register as register_optimize  # noqa: E402
from tokenlens.cli.commands.predict import register as register_predict  # noqa: E402
from tokenlens.cli.commands.report import register as register_report  # noqa: E402
from tokenlens.cli.commands.serve import register as register_serve  # noqa: E402
from tokenlens.cli.commands.shell_hook import register as register_shell_hook  # noqa: E402
from tokenlens.cli.commands.status import register as register_status  # noqa: E402
from tokenlens.cli.commands.why import register as register_why  # noqa: E402

register_init(app)
register_agent(agent_app)
register_status(app)
register_mcp(app)
register_ml(app)
register_serve(app)
register_report(app)
register_predict(app)
register_compare(app)
register_why(app)
register_optimize(app)
register_export(app)
register_shell_hook(app)
register_data(app)


@app.command()
def live() -> None:
    """Launch real-time TUI dashboard (requires tokenlens[tui])."""
    try:
        from tokenlens.cli.live import run_live_tui

        run_live_tui()
    except ImportError:
        import typer as _typer

        _typer.echo(
            "Error: The 'textual' package is required for `tokenlens live`.\n"
            "Install it with: pip install tokenlens[tui]"
        )
        raise _typer.Exit(code=1) from None


if __name__ == "__main__":
    app()
