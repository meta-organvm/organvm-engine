"""Git module — hierarchical superproject management for the organvm workspace."""

from organvm_engine.git.superproject import init_superproject, add_submodule, sync_organ
from organvm_engine.git.status import show_drift, diff_pinned
from organvm_engine.git.reproduce import reproduce_workspace, clone_organ

__all__ = [
    "init_superproject",
    "add_submodule",
    "sync_organ",
    "show_drift",
    "diff_pinned",
    "reproduce_workspace",
    "clone_organ",
]
