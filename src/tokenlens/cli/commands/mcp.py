"""CLI command for starting the MCP server."""

from __future__ import annotations

import typer


def register(app: typer.Typer) -> None:
    """Register the mcp-serve command on the main app."""

    @app.command(name="mcp-serve")
    def mcp_serve() -> None:
        """Start the TokenLens MCP server in stdio mode.

        This command starts an MCP server that Kiro can connect to for
        token usage logging and monitoring.
        """
        try:
            from tokenlens.integrations.mcp_server import run_server
        except ImportError:
            typer.echo(
                "MCP dependencies not installed. Run: pip install 'tokenlens[ml]'",
                err=True,
            )
            raise typer.Exit(1) from None

        typer.echo("Starting TokenLens MCP server (stdio)...")
        run_server()
