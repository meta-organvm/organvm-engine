"""Tests for sop.inventory module."""

from pathlib import Path

from organvm_engine.sop.discover import SOPEntry
from organvm_engine.sop.inventory import AuditResult, audit_sops, parse_inventory


def _entry(
    filename: str,
    org: str = "meta-organvm",
    repo: str = "praxis-perpetua",
    canonical: bool = False,
    has_canonical_header: bool = False,
) -> SOPEntry:
    return SOPEntry(
        path=Path(f"/ws/{org}/{repo}/{filename}"),
        org=org,
        repo=repo,
        filename=filename,
        title=None,
        doc_type="SOP",
        canonical=canonical,
        has_canonical_header=has_canonical_header,
    )


class TestParseInventory:
    def test_extracts_filenames_from_table(self, tmp_path):
        metadoc = tmp_path / "METADOC--sop-ecosystem.md"
        metadoc.write_text(
            "## 3.1\n\n"
            "| # | File | Type |\n"
            "|---|------|------|\n"
            "| 1 | `SOP--alpha.md` | SOP |\n"
            "| 2 | `METADOC--beta.md` | METADOC |\n"
        )
        result = parse_inventory(metadoc)
        assert result == {"SOP--alpha.md", "METADOC--beta.md"}

    def test_empty_file(self, tmp_path):
        metadoc = tmp_path / "METADOC--sop-ecosystem.md"
        metadoc.write_text("# No tables here\n")
        result = parse_inventory(metadoc)
        assert result == set()

    def test_missing_file(self, tmp_path):
        result = parse_inventory(tmp_path / "nonexistent.md")
        assert result == set()

    def test_multiple_sections(self, tmp_path):
        metadoc = tmp_path / "METADOC--sop-ecosystem.md"
        metadoc.write_text(
            "## 3.1\n| 1 | `SOP--a.md` | SOP |\n\n"
            "## 3.2\n| 1 | `template.md` | Template |\n\n"
            "## 3.6\n| 1 | `sop-external.md` | SOP |\n"
        )
        result = parse_inventory(metadoc)
        assert "SOP--a.md" in result
        assert "sop-external.md" in result
        # Non-SOP-pattern files are excluded from inventory
        assert "template.md" not in result


class TestAuditSops:
    def test_tracked_entry(self, tmp_path):
        metadoc = tmp_path / "inv.md"
        metadoc.write_text("| 1 | `SOP--alpha.md` | SOP |\n")
        discovered = [_entry("SOP--alpha.md")]
        result = audit_sops(discovered, metadoc)
        assert len(result.tracked) == 1
        assert len(result.untracked) == 0

    def test_untracked_entry(self, tmp_path):
        metadoc = tmp_path / "inv.md"
        metadoc.write_text("| 1 | `SOP--alpha.md` | SOP |\n")
        discovered = [_entry("SOP--unknown.md")]
        result = audit_sops(discovered, metadoc)
        assert len(result.untracked) == 1
        assert result.untracked[0].filename == "SOP--unknown.md"

    def test_reference_copy(self, tmp_path):
        metadoc = tmp_path / "inv.md"
        metadoc.write_text("| 1 | `SOP--alpha.md` | SOP |\n")
        discovered = [_entry("SOP--alpha.md", has_canonical_header=True)]
        result = audit_sops(discovered, metadoc)
        assert len(result.reference_copy) == 1
        assert len(result.tracked) == 0

    def test_missing_entry(self, tmp_path):
        metadoc = tmp_path / "inv.md"
        metadoc.write_text("| 1 | `SOP--alpha.md` | SOP |\n| 2 | `SOP--gone.md` | SOP |\n")
        discovered = [_entry("SOP--alpha.md")]
        result = audit_sops(discovered, metadoc)
        assert result.missing == ["SOP--gone.md"]

    def test_mixed_scenario(self, tmp_path):
        metadoc = tmp_path / "inv.md"
        metadoc.write_text(
            "| 1 | `SOP--tracked.md` | SOP |\n"
            "| 2 | `SOP--missing.md` | SOP |\n"
        )
        discovered = [
            _entry("SOP--tracked.md"),
            _entry("SOP--refcopy.md", has_canonical_header=True),
            _entry("sop-external.md", org="organvm-v-logos", repo="pub"),
        ]
        result = audit_sops(discovered, metadoc)
        assert len(result.tracked) == 1
        assert len(result.reference_copy) == 1
        assert len(result.untracked) == 1
        assert result.missing == ["SOP--missing.md"]

    def test_empty_discovered(self, tmp_path):
        metadoc = tmp_path / "inv.md"
        metadoc.write_text("| 1 | `SOP--alpha.md` | SOP |\n")
        result = audit_sops([], metadoc)
        assert len(result.tracked) == 0
        assert result.missing == ["SOP--alpha.md"]
