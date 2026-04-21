"""CLI command: tokenlens serve — starts the FastAPI server."""

from __future__ import annotations

import typer


def register(app: typer.Typer) -> None:
    """Register the serve command on the main app."""

    @app.command()
    def serve(
        port: int = typer.Option(7890, "--port", "-p", help="Port to listen on."),
        host: str = typer.Option("127.0.0.1", "--host", help="Host to bind to."),
        ui: bool = typer.Option(False, "--ui", help="Serve built React UI static files."),
    ) -> None:
        """Start the TokenLens API server (runs alongside daemon)."""
        import uvicorn

        from tokenlens.api.app import create_app

        app_instance = create_app()

        if ui:
            # Mount static files if available
            from pathlib import Path

            from fastapi.staticfiles import StaticFiles

            ui_dist = Path(__file__).parent.parent.parent.parent.parent / "ui" / "dist"
            if ui_dist.exists():
                app_instance.mount("/", StaticFiles(directory=str(ui_dist), html=True), name="ui")
                typer.echo(f"Serving UI from {ui_dist}")
            else:
                typer.echo("Warning: UI dist not found. Run `npm run build` in ui/ first.")

        typer.echo(f"Starting TokenLens API on {host}:{port}")
        typer.echo(f"Docs: http://{host}:{port}/docs")
        typer.echo(f"Health: http://{host}:{port}/health")

        uvicorn.run(app_instance, host=host, port=port, log_level="info")
