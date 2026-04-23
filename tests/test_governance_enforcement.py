"""Tests for AX-7/8/9 governance enforcement validators (Session F).

Validates tetradic self-knowledge, constructed polis, and triple-reference
invariant — the three axioms that were declared in governance-rules.json
but had no validator implementations.
"""

from __future__ import annotations

from pathlib import Path

from organvm_engine.governance.dictums import (
    validate_constructed_polis,
    validate_effect_obligation,
    validate_tetradic_self_knowledge,
    validate_triple_reference,
)

# ── Helpers ──────────────────────────────────────────────────────


def _make_registry(
    repos: list[dict],
    organ_key: str = "ORGAN-I",
) -> dict:
    """Build a minimal registry with the given repos under one organ."""
    return {
        "version": "2.0",
        "organs": {
            organ_key: {
                "name": "Test",
                "repositories": repos,
            },
        },
    }


def _repo(
    name: str = "test-repo",
    org: str = "organvm-i-theoria",
    status: str = "ACTIVE",
    promotion: str = "PUBLIC_PROCESS",
) -> dict:
    return {
        "name": name,
        "org": org,
        "implementation_status": status,
        "promotion_status": promotion,
    }


def _create_repo_dir(tmp_path: Path, org: str, name: str) -> Path:
    """Create and return the repo directory in the tmp workspace."""
    d = tmp_path / org / name
    d.mkdir(parents=True, exist_ok=True)
    return d


# ── AX-7: Tetradic Self-Knowledge ───────────────────────────────


class TestTetradicSelfKnowledge:
    def test_no_workspace_returns_empty(self):
        registry = _make_registry([_repo()])
        violations = validate_tetradic_self_knowledge(registry, workspace=None)
        assert violations == []

    def test_logos_files_pass(self, tmp_path):
        """All 4 logos files present → no AX-7 violations."""
        r = _repo()
        registry = _make_registry([r])
        repo_dir = _create_repo_dir(tmp_path, r["org"], r["name"])

        logos = repo_dir / "docs" / "logos"
        logos.mkdir(parents=True)
        for dim in ("telos", "pragma", "praxis", "receptio"):
            (logos / f"{dim}.md").write_text(f"# {dim}\n")

        violations = validate_tetradic_self_knowledge(registry, workspace=tmp_path)
        ax7 = [v for v in violations if v.dictum_id == "AX-7"]
        assert ax7 == []

    def test_missing_logos_warns(self, tmp_path):
        """No logos files and no seed.yaml fields → 4 AX-7 violations."""
        r = _repo()
        registry = _make_registry([r])
        _create_repo_dir(tmp_path, r["org"], r["name"])

        violations = validate_tetradic_self_knowledge(registry, workspace=tmp_path)
        ax7 = [v for v in violations if v.dictum_id == "AX-7"]
        assert len(ax7) == 4
        dims = {v.message.split(" — ")[0].replace("Missing ", "") for v in ax7}
        assert dims == {"telos", "pragma", "praxis", "receptio"}

    def test_seed_tetradic_fields_pass(self, tmp_path):
        """seed.yaml with all 4 fields → no violations even without logos files."""
        r = _repo()
        registry = _make_registry([r])
        repo_dir = _create_repo_dir(tmp_path, r["org"], r["name"])

        (repo_dir / "seed.yaml").write_text(
            "organ: ORGAN-I\n"
            "telos: The dream.\n"
            "pragma: What exists.\n"
            "praxis: The plan.\n"
            "receptio: How it was received.\n",
        )

        violations = validate_tetradic_self_knowledge(registry, workspace=tmp_path)
        ax7 = [v for v in violations if v.dictum_id == "AX-7"]
        assert ax7 == []

    def test_archived_skipped(self, tmp_path):
        """ARCHIVED repos produce no AX-7 violations."""
        r = _repo(status="ARCHIVED")
        registry = _make_registry([r])
        _create_repo_dir(tmp_path, r["org"], r["name"])

        violations = validate_tetradic_self_knowledge(registry, workspace=tmp_path)
        ax7 = [v for v in violations if v.dictum_id == "AX-7"]
        assert ax7 == []

    def test_partial_coverage_warns(self, tmp_path):
        """Has telos.md and pragma.md but not praxis.md/receptio.md → 2 violations."""
        r = _repo()
        registry = _make_registry([r])
        repo_dir = _create_repo_dir(tmp_path, r["org"], r["name"])

        logos = repo_dir / "docs" / "logos"
        logos.mkdir(parents=True)
        (logos / "telos.md").write_text("# telos\n")
        (logos / "pragma.md").write_text("# pragma\n")

        violations = validate_tetradic_self_knowledge(registry, workspace=tmp_path)
        ax7 = [v for v in violations if v.dictum_id == "AX-7"]
        assert len(ax7) == 2
        dims = {v.message.split(" — ")[0].replace("Missing ", "") for v in ax7}
        assert dims == {"praxis", "receptio"}

    def test_mixed_evidence_passes(self, tmp_path):
        """seed.yaml has telos+pragma, logos files have praxis+receptio → passes."""
        r = _repo()
        registry = _make_registry([r])
        repo_dir = _create_repo_dir(tmp_path, r["org"], r["name"])

        (repo_dir / "seed.yaml").write_text(
            "organ: ORGAN-I\n"
            "telos: The dream.\n"
            "pragma: What exists.\n",
        )
        logos = repo_dir / "docs" / "logos"
        logos.mkdir(parents=True)
        (logos / "praxis.md").write_text("# praxis\n")
        (logos / "receptio.md").write_text("# receptio\n")

        violations = validate_tetradic_self_knowledge(registry, workspace=tmp_path)
        ax7 = [v for v in violations if v.dictum_id == "AX-7"]
        assert ax7 == []


# ── AX-8: Constructed Polis ──────────────────────────────────────


class TestConstructedPolis:
    def test_no_workspace_returns_empty(self):
        registry = _make_registry([_repo()])
        violations = validate_constructed_polis(registry, workspace=None)
        assert violations == []

    def test_polis_dir_passes(self, tmp_path):
        """docs/polis/ directory present → no AX-8 violation."""
        r = _repo(promotion="GRADUATED")
        registry = _make_registry([r])
        repo_dir = _create_repo_dir(tmp_path, r["org"], r["name"])
        (repo_dir / "docs" / "polis").mkdir(parents=True)

        violations = validate_constructed_polis(registry, workspace=tmp_path)
        ax8 = [v for v in violations if v.dictum_id == "AX-8"]
        assert ax8 == []

    def test_no_polis_warns_graduated(self, tmp_path):
        """GRADUATED repo without polis evidence → AX-8 violation."""
        r = _repo(promotion="GRADUATED")
        registry = _make_registry([r])
        _create_repo_dir(tmp_path, r["org"], r["name"])

        violations = validate_constructed_polis(registry, workspace=tmp_path)
        ax8 = [v for v in violations if v.dictum_id == "AX-8"]
        assert len(ax8) == 1
        assert "polis" in ax8[0].message.lower()

    def test_local_skipped(self, tmp_path):
        """LOCAL repos produce no AX-8 violations."""
        r = _repo(promotion="LOCAL")
        registry = _make_registry([r])
        _create_repo_dir(tmp_path, r["org"], r["name"])

        violations = validate_constructed_polis(registry, workspace=tmp_path)
        ax8 = [v for v in violations if v.dictum_id == "AX-8"]
        assert ax8 == []

    def test_candidate_skipped(self, tmp_path):
        """CANDIDATE repos produce no AX-8 violations."""
        r = _repo(promotion="CANDIDATE")
        registry = _make_registry([r])
        _create_repo_dir(tmp_path, r["org"], r["name"])

        violations = validate_constructed_polis(registry, workspace=tmp_path)
        ax8 = [v for v in violations if v.dictum_id == "AX-8"]
        assert ax8 == []

    def test_receptio_counts_as_polis(self, tmp_path):
        """docs/logos/receptio.md satisfies AX-8."""
        r = _repo(promotion="PUBLIC_PROCESS")
        registry = _make_registry([r])
        repo_dir = _create_repo_dir(tmp_path, r["org"], r["name"])
        logos = repo_dir / "docs" / "logos"
        logos.mkdir(parents=True)
        (logos / "receptio.md").write_text("# Receptio\n")

        violations = validate_constructed_polis(registry, workspace=tmp_path)
        ax8 = [v for v in violations if v.dictum_id == "AX-8"]
        assert ax8 == []

    def test_reception_dir_passes(self, tmp_path):
        """docs/reception/ directory satisfies AX-8."""
        r = _repo(promotion="GRADUATED")
        registry = _make_registry([r])
        repo_dir = _create_repo_dir(tmp_path, r["org"], r["name"])
        (repo_dir / "docs" / "reception").mkdir(parents=True)

        violations = validate_constructed_polis(registry, workspace=tmp_path)
        ax8 = [v for v in violations if v.dictum_id == "AX-8"]
        assert ax8 == []


# ── AX-9: Triple Reference Invariant ────────────────────────────


class TestTripleReference:
    def test_no_workspace_returns_empty(self):
        registry = _make_registry([_repo(promotion="GRADUATED")])
        violations = validate_triple_reference(registry, workspace=None)
        assert violations == []

    def test_graduated_with_tracking_passes(self, tmp_path):
        """seed.yaml with irf_references + tracking → passes."""
        r = _repo(promotion="GRADUATED")
        registry = _make_registry([r])
        repo_dir = _create_repo_dir(tmp_path, r["org"], r["name"])

        (repo_dir / "seed.yaml").write_text(
            "organ: ORGAN-I\n"
            "irf_references:\n"
            "  - IRF-SYS-001\n"
            "tracking:\n"
            "  github_issue: 42\n",
        )

        violations = validate_triple_reference(registry, workspace=tmp_path)
        ax9 = [v for v in violations if v.dictum_id == "AX-9"]
        assert ax9 == []

    def test_graduated_with_issue_templates_passes(self, tmp_path):
        """seed.yaml with irf_references + .github/ISSUE_TEMPLATE/ → passes."""
        r = _repo(promotion="GRADUATED")
        registry = _make_registry([r])
        repo_dir = _create_repo_dir(tmp_path, r["org"], r["name"])

        (repo_dir / "seed.yaml").write_text(
            "organ: ORGAN-I\n"
            "irf_references:\n"
            "  - IRF-SYS-042\n",
        )
        (repo_dir / ".github" / "ISSUE_TEMPLATE").mkdir(parents=True)

        violations = validate_triple_reference(registry, workspace=tmp_path)
        ax9 = [v for v in violations if v.dictum_id == "AX-9"]
        assert ax9 == []

    def test_graduated_without_tracking_warns(self, tmp_path):
        """GRADUATED repo with no IRF ref or tracking → AX-9 violation."""
        r = _repo(promotion="GRADUATED")
        registry = _make_registry([r])
        _create_repo_dir(tmp_path, r["org"], r["name"])

        violations = validate_triple_reference(registry, workspace=tmp_path)
        ax9 = [v for v in violations if v.dictum_id == "AX-9"]
        assert len(ax9) == 1
        assert "IRF reference" in ax9[0].message
        assert "external tracking" in ax9[0].message

    def test_non_graduated_skipped(self, tmp_path):
        """LOCAL/CANDIDATE/PUBLIC_PROCESS repos produce no AX-9 violations."""
        for status in ("LOCAL", "CANDIDATE", "PUBLIC_PROCESS"):
            r = _repo(promotion=status)
            registry = _make_registry([r])
            _create_repo_dir(tmp_path, r["org"], r["name"])

            violations = validate_triple_reference(registry, workspace=tmp_path)
            ax9 = [v for v in violations if v.dictum_id == "AX-9"]
            assert ax9 == [], f"Expected no AX-9 for {status}"

    def test_archived_skipped(self, tmp_path):
        """ARCHIVED repos produce no AX-9 violations even at GRADUATED."""
        r = _repo(status="ARCHIVED", promotion="GRADUATED")
        registry = _make_registry([r])
        _create_repo_dir(tmp_path, r["org"], r["name"])

        violations = validate_triple_reference(registry, workspace=tmp_path)
        ax9 = [v for v in violations if v.dictum_id == "AX-9"]
        assert ax9 == []

    def test_partial_legs_warns_only_missing(self, tmp_path):
        """Has irf_references but no tracking → warns only about tracking leg."""
        r = _repo(promotion="GRADUATED")
        registry = _make_registry([r])
        repo_dir = _create_repo_dir(tmp_path, r["org"], r["name"])

        (repo_dir / "seed.yaml").write_text(
            "organ: ORGAN-I\n"
            "irf_references:\n"
            "  - IRF-SYS-001\n",
        )

        violations = validate_triple_reference(registry, workspace=tmp_path)
        ax9 = [v for v in violations if v.dictum_id == "AX-9"]
        assert len(ax9) == 1
        assert "IRF reference" not in ax9[0].message
        assert "external tracking" in ax9[0].message


# ── RR-6: Effect Obligation ──────────────────────────────────────


class TestEffectObligation:
    def test_no_workspace_returns_empty(self):
        registry = _make_registry([_repo()])
        violations = validate_effect_obligation(registry, workspace=None)
        assert violations == []

    def test_seed_with_produces_passes(self, tmp_path):
        """Repo with produces edges → no RR-6 violation."""
        r = _repo()
        registry = _make_registry([r])
        repo_dir = _create_repo_dir(tmp_path, r["org"], r["name"])

        (repo_dir / "seed.yaml").write_text(
            "organ: ORGAN-I\n"
            "produces:\n"
            "  - type: research\n"
            "    target: ORGAN-II\n",
        )

        violations = validate_effect_obligation(registry, workspace=tmp_path)
        rr6 = [v for v in violations if v.dictum_id == "RR-9"]
        assert rr6 == []

    def test_seed_without_produces_warns(self, tmp_path):
        """Repo with seed.yaml but no produces → RR-6 violation."""
        r = _repo()
        registry = _make_registry([r])
        repo_dir = _create_repo_dir(tmp_path, r["org"], r["name"])

        (repo_dir / "seed.yaml").write_text(
            "organ: ORGAN-I\n"
            "consumes:\n"
            "  - source: meta-organvm/organvm-engine\n",
        )

        violations = validate_effect_obligation(registry, workspace=tmp_path)
        rr6 = [v for v in violations if v.dictum_id == "RR-9"]
        assert len(rr6) == 1
        assert "inert" in rr6[0].message

    def test_no_seed_skipped(self, tmp_path):
        """Repo without seed.yaml → no RR-6 violation (RR-1 handles that)."""
        r = _repo()
        registry = _make_registry([r])
        _create_repo_dir(tmp_path, r["org"], r["name"])

        violations = validate_effect_obligation(registry, workspace=tmp_path)
        rr6 = [v for v in violations if v.dictum_id == "RR-9"]
        assert rr6 == []

    def test_archived_skipped(self, tmp_path):
        """ARCHIVED repos produce no RR-6 violations."""
        r = _repo(status="ARCHIVED")
        registry = _make_registry([r])
        repo_dir = _create_repo_dir(tmp_path, r["org"], r["name"])
        (repo_dir / "seed.yaml").write_text("organ: ORGAN-I\n")

        violations = validate_effect_obligation(registry, workspace=tmp_path)
        rr6 = [v for v in violations if v.dictum_id == "RR-9"]
        assert rr6 == []

    def test_empty_produces_list_warns(self, tmp_path):
        """Explicit empty produces list → RR-6 violation."""
        r = _repo()
        registry = _make_registry([r])
        repo_dir = _create_repo_dir(tmp_path, r["org"], r["name"])
        (repo_dir / "seed.yaml").write_text("organ: ORGAN-I\nproduces: []\n")

        violations = validate_effect_obligation(registry, workspace=tmp_path)
        rr6 = [v for v in violations if v.dictum_id == "RR-9"]
        assert len(rr6) == 1
