"""tokenlens shell-hook — output shell prompt integration snippet."""

from __future__ import annotations

import typer
from rich.console import Console

console = Console()

_BASH_HOOK = """\
# TokenLens shell prompt integration
_tokenlens_prompt() {
    local status
    status=$(tokenlens status --short 2>/dev/null)
    if [ -n "$status" ]; then
        echo " [$status]"
    fi
}
PS1="${PS1}\\$(_tokenlens_prompt)"
"""

_ZSH_HOOK = """\
# TokenLens shell prompt integration
_tokenlens_prompt() {
    local status
    status=$(tokenlens status --short 2>/dev/null)
    if [[ -n "$status" ]]; then
        echo " [$status]"
    fi
}
precmd_functions+=(_tokenlens_prompt)
RPROMPT='$(_tokenlens_prompt)'
"""

_FISH_HOOK = """\
# TokenLens shell prompt integration
function _tokenlens_prompt
    set -l status_str (tokenlens status --short 2>/dev/null)
    if test -n "$status_str"
        echo " [$status_str]"
    end
end

function fish_right_prompt
    _tokenlens_prompt
end
"""


def register(app: typer.Typer) -> None:
    """Register the shell-hook command on the top-level app."""
    app.command(name="shell-hook")(shell_hook_command)


def shell_hook_command(
    shell: str = typer.Option("bash", help="Shell type: bash, zsh, fish"),
) -> None:
    """Output a shell prompt integration snippet.

    Add the output to your shell config file (.bashrc, .zshrc, config.fish).
    """
    hooks = {
        "bash": _BASH_HOOK,
        "zsh": _ZSH_HOOK,
        "fish": _FISH_HOOK,
    }

    snippet = hooks.get(shell)
    if snippet is None:
        console.print(f"[red]Unsupported shell: {shell}. Use bash, zsh, or fish.[/red]")
        raise typer.Exit(code=1)

    # Output raw snippet (no Rich formatting) for piping
    typer.echo(snippet)
