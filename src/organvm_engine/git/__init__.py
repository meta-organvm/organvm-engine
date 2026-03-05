"""Git module — hierarchical superproject management for the organvm workspace."""

from organvm_engine.git.reproduce import clone_organ, reproduce_workspace
from organvm_engine.git.status import diff_pinned, show_drift
from organvm_engine.git.superproject import add_submodule, init_superproject, sync_organ

__all__ = [
    "init_superproject",
    "add_submodule",
    "sync_organ",
    "show_drift",
    "diff_pinned",
    "reproduce_workspace",
    "clone_organ",
]
