"""Typed data structures for infrastructure audit findings."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Severity(str, Enum):
    """Finding severity levels."""

    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


@dataclass
class Finding:
    """A single audit finding."""

    severity: Severity
    layer: str
    organ: str
    repo: str
    message: str
    suggestion: str = ""

    def to_dict(self) -> dict:
        return {
            "severity": self.severity.value,
            "layer": self.layer,
            "organ": self.organ,
            "repo": self.repo,
            "message": self.message,
            "suggestion": self.suggestion,
        }


@dataclass
class LayerReport:
    """Results from a single audit layer."""

    layer: str
    findings: list[Finding] = field(default_factory=list)

    @property
    def critical_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.CRITICAL)

    @property
    def warning_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.WARNING)

    @property
    def info_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.INFO)

    def by_severity(self, severity: Severity) -> list[Finding]:
        return [f for f in self.findings if f.severity == severity]

    def by_organ(self, organ: str) -> list[Finding]:
        return [f for f in self.findings if f.organ == organ]

    def to_dict(self) -> dict:
        return {
            "layer": self.layer,
            "critical": self.critical_count,
            "warnings": self.warning_count,
            "info": self.info_count,
            "findings": [f.to_dict() for f in self.findings],
        }


@dataclass
class InfrastructureAuditReport:
    """Full infrastructure audit report across all layers."""

    layers: dict[str, LayerReport] = field(default_factory=dict)
    scope_organ: str | None = None
    scope_repo: str | None = None

    @property
    def all_findings(self) -> list[Finding]:
        results: list[Finding] = []
        for lr in self.layers.values():
            results.extend(lr.findings)
        return results

    @property
    def critical_count(self) -> int:
        return sum(lr.critical_count for lr in self.layers.values())

    @property
    def warning_count(self) -> int:
        return sum(lr.warning_count for lr in self.layers.values())

    @property
    def info_count(self) -> int:
        return sum(lr.info_count for lr in self.layers.values())

    def findings_for_organ(self, organ: str) -> list[Finding]:
        return [f for f in self.all_findings if f.organ == organ]

    def findings_for_repo(self, repo: str) -> list[Finding]:
        return [f for f in self.all_findings if f.repo == repo]

    def organs_with_findings(self) -> list[str]:
        return sorted({f.organ for f in self.all_findings if f.organ})

    def to_dict(self) -> dict:
        return {
            "scope_organ": self.scope_organ,
            "scope_repo": self.scope_repo,
            "summary": {
                "critical": self.critical_count,
                "warnings": self.warning_count,
                "info": self.info_count,
                "total_findings": len(self.all_findings),
            },
            "layers": {k: v.to_dict() for k, v in self.layers.items()},
        }
