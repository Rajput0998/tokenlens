"""tokenlens init — initialize configuration and discover adapters."""

from __future__ import annotations

import typer  # noqa: TC002
from rich.console import Console

console = Console()


def register(app: typer.Typer) -> None:
    """Register the init command on the top-level app."""
    app.command(name="init")(init_command)


def init_command() -> None:
    """Initialize TokenLens: create config, discover adapters."""
    from tokenlens.adapters.registry import AdapterRegistry
    from tokenlens.core.config import CONFIG_PATH, DEFAULT_CONFIG_TEMPLATE, ensure_dirs

    # Step 1: Create directory structure
    ensure_dirs()
    console.print("[green]✓[/green] Created ~/.tokenlens/ directory structure")

    # Step 2: Write default config if it doesn't exist
    if CONFIG_PATH.exists():
        console.print(f"[yellow]⏭[/yellow] Config already exists at {CONFIG_PATH}")
    else:
        CONFIG_PATH.write_text(DEFAULT_CONFIG_TEMPLATE)
        console.print(f"[green]✓[/green] Generated default config at {CONFIG_PATH}")

    # Step 3: Discover adapters
    registry = AdapterRegistry()
    registry.load_builtins()
    registry.discover_entry_points()

    available = registry.get_available()
    all_adapters = registry.get_all()

    console.print()
    console.print("[bold]Adapter Discovery:[/bold]")
    for adapter in all_adapters:
        if adapter in available:
            # Show the log path for discovered adapters
            log_paths = adapter.get_log_paths()
            if log_paths:
                parent = log_paths[0].parent
                console.print(f"  [green]✓[/green] {adapter.name} adapter found at {parent}")
            else:
                console.print(f"  [green]✓[/green] {adapter.name} adapter available")
        else:
            console.print(f"  [dim]✗ {adapter.name} adapter not found[/dim]")

    # Step 4: Check for Kiro (future MCP integration)
    kiro_adapter = registry.get("kiro")
    if kiro_adapter and kiro_adapter in available:
        console.print()
        console.print("[bold]Kiro MCP Configuration:[/bold]")
        console.print("  Add this to .kiro/settings/mcp.json:")
        console.print()
        console.print('  {')
        console.print('    "mcpServers": {')
        console.print('      "tokenlens": {')
        console.print('        "command": "tokenlens",')
        console.print('        "args": ["mcp-serve"],')
        console.print('        "disabled": false')
        console.print("      }")
        console.print("    }")
        console.print("  }")

    # Step 5: Success message
    console.print()
    console.print("[bold green]TokenLens initialized![/bold green]")
    console.print()
    console.print("[bold]Next steps:[/bold]")
    console.print("  1. Start the agent:  [cyan]tokenlens agent start --foreground[/cyan]")
    console.print("  2. Check status:     [cyan]tokenlens status[/cyan]")
    console.print("  3. Edit config:      [cyan]~/.tokenlens/config.toml[/cyan]")
