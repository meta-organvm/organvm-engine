"""Agent dispatch backends for the Cyclic Dispatch Protocol.

Each backend knows how to create work items for a specific agent type
and check their status. Backends are registered in the routing table
and selected by capability matching during HANDOFF.

Backends to implement:
- copilot: GitHub issue + @copilot assignment
- jules: GitHub issue + @jules assignment
- actions: workflow_dispatch event via gh CLI
- claude: worktree-isolated Claude Code subagent
- launchagent: macOS plist generation + launchctl load
- human: GitHub issue tagged needs-review
"""
