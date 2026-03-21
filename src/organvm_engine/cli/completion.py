"""CLI handler for the completion command — generate shell completion scripts."""

from __future__ import annotations

import argparse
import sys

BASH_SCRIPT = """\
# organvm bash completion — add to ~/.bashrc or ~/.bash_profile
eval "$(register-python-argcomplete organvm)"
"""

ZSH_SCRIPT = """\
# organvm zsh completion — add to ~/.zshrc
autoload -U bashcompinit
bashcompinit
eval "$(register-python-argcomplete organvm)"
"""

FISH_SCRIPT = """\
# organvm fish completion — add to ~/.config/fish/config.fish
register-python-argcomplete --shell fish organvm | source
"""

SHELLS = {
    "bash": BASH_SCRIPT,
    "zsh": ZSH_SCRIPT,
    "fish": FISH_SCRIPT,
}


def cmd_completion(args: argparse.Namespace) -> int:
    """Print shell completion setup script for the requested shell."""
    shell: str = args.shell
    script = SHELLS.get(shell)
    if script is None:
        print(f"Unsupported shell: {shell}. Choose from: {', '.join(SHELLS)}", file=sys.stderr)
        return 1
    print(script, end="")
    return 0
