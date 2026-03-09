"""Tests for the gate evaluation module."""

from pathlib import Path

from organvm_engine.metrics.gates import (
    GATE_ORDER,
    GateResult,
    RepoProgress,
    ScaffoldInfo,
    detect_profile,
    eval_gate,
    evaluate_all,
    evaluate_all_for_dashboard,
    evaluate_repo,
    find_local,
    has_code,
    next_promo,
    promo_ready,
    scaffold_info,
    stale_days,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_entry(**overrides):
    """Build a minimal registry entry with overrides."""
    base = {
        "name": "test-repo",
        "org": "organvm-i-theoria",
        "implementation_status": "ACTIVE",
        "promotion_status": "LOCAL",
        "tier": "standard",
        "description": "A test repo",
    }
    base.update(overrides)
    return base


def _make_workspace(tmp_path, repo_name="test-repo", organ_dir="organvm-i-theoria"):
    """Build a workspace with a repo dir and basic scaffold."""
    ws = tmp_path / "workspace"
    repo = ws / organ_dir / repo_name
    repo.mkdir(parents=True)
    (repo / "README.md").write_text("word " * 600)
    (repo / ".gitignore").write_text("*.pyc\n")
    (repo / "CHANGELOG.md").write_text("# Changelog\n")
    (repo / "seed.yaml").write_text("schema_version: 1\n")
    (repo / "src").mkdir()
    (repo / "src" / "main.py").write_text("print('hello')")
    (repo / "tests").mkdir()
    (repo / "tests" / "test_main.py").write_text("def test(): pass")
    ci = repo / ".github" / "workflows"
    ci.mkdir(parents=True)
    (ci / "ci.yml").write_text("name: CI\n")
    return ws


# ---------------------------------------------------------------------------
# has_code
# ---------------------------------------------------------------------------

class TestHasCode:
    def test_with_src_dir(self, tmp_path):
        repo = tmp_path / "repo"
        (repo / "src").mkdir(parents=True)
        assert has_code(repo)

    def test_with_py_file(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "main.py").write_text("x = 1")
        assert has_code(repo)

    def test_with_nested_code(self, tmp_path):
        repo = tmp_path / "repo"
        (repo / "pkg").mkdir(parents=True)
        (repo / "pkg" / "mod.ts").write_text("export const x = 1")
        assert has_code(repo)

    def test_no_code(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "README.md").write_text("hello")
        assert not has_code(repo)


# ---------------------------------------------------------------------------
# detect_profile
# ---------------------------------------------------------------------------

class TestDetectProfile:
    def test_archived(self):
        assert detect_profile({"promotion_status": "ARCHIVED"}, None) == "archived"

    def test_archive_tier(self):
        assert detect_profile({"tier": "archive"}, None) == "archived"

    def test_stub_tier(self):
        assert detect_profile({"tier": "stub"}, None) == "stub"

    def test_infrastructure_tier(self):
        assert detect_profile({"tier": "infrastructure"}, None) == "infrastructure"

    def test_design_only(self):
        e = {"implementation_status": "DESIGN_ONLY", "tier": "standard"}
        assert detect_profile(e, None) == "documentation"

    def test_governance_keyword(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "README.md").write_text("hello")
        e = {"name": "petasum-governance", "tier": "standard"}
        assert detect_profile(e, repo) == "governance"

    def test_code_full_default(self):
        assert detect_profile({"tier": "standard"}, None) == "code-full"


# ---------------------------------------------------------------------------
# scaffold_info
# ---------------------------------------------------------------------------

class TestScaffoldInfo:
    def test_with_all_files(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "README.md").write_text("one two three")
        (repo / ".gitignore").write_text("*.pyc")
        (repo / "LICENSE").write_text("MIT")
        (repo / "CHANGELOG.md").write_text("# CL")
        (repo / "CLAUDE.md").write_text("# CLAUDE")
        scaf = scaffold_info(repo)
        assert scaf.has_readme
        assert scaf.readme_words == 3
        assert scaf.has_gitignore
        assert scaf.has_license
        assert scaf.has_changelog
        assert scaf.has_claude_md

    def test_none_local(self):
        scaf = scaffold_info(None)
        assert scaf.readme_words == 0
        assert not scaf.has_readme


# ---------------------------------------------------------------------------
# stale_days
# ---------------------------------------------------------------------------

class TestStaleDays:
    def test_missing_date(self):
        assert stale_days({}) == -1

    def test_valid_date(self):
        import datetime
        yesterday = (datetime.date.today() - datetime.timedelta(days=5)).isoformat()
        assert stale_days({"last_validated": yesterday}) == 5

    def test_invalid_date(self):
        assert stale_days({"last_validated": "not-a-date"}) == -1


# ---------------------------------------------------------------------------
# Individual gate evaluation
# ---------------------------------------------------------------------------

class TestEvalGate:
    def test_seed_with_file(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "seed.yaml").write_text("schema_version: 1\n")
        g = eval_gate("SEED", {}, repo, "standard", ScaffoldInfo())
        assert g.passed

    def test_seed_missing(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        g = eval_gate("SEED", {}, repo, "standard", ScaffoldInfo())
        assert not g.passed

    def test_seed_no_local(self):
        g = eval_gate("SEED", {}, None, "standard", ScaffoldInfo())
        assert g.passed  # in-registry assumed

    def test_scaffold_pass(self):
        scaf = ScaffoldInfo(has_readme=True, has_gitignore=True, readme_words=100)
        g = eval_gate("SCAFFOLD", {}, Path("/fake"), "standard", scaf)
        assert g.passed

    def test_scaffold_fail(self):
        scaf = ScaffoldInfo(has_readme=True, has_gitignore=False)
        g = eval_gate("SCAFFOLD", {}, Path("/fake"), "standard", scaf)
        assert not g.passed

    def test_ci_with_registry_and_local(self, tmp_path):
        repo = tmp_path / "repo"
        wf = repo / ".github" / "workflows"
        wf.mkdir(parents=True)
        (wf / "ci.yml").write_text("name: CI")
        entry = {"ci_workflow": "ci.yml"}
        g = eval_gate("CI", entry, repo, "standard", ScaffoldInfo())
        assert g.passed

    def test_ci_mismatch(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        entry = {"ci_workflow": "ci.yml"}
        g = eval_gate("CI", entry, repo, "standard", ScaffoldInfo())
        assert not g.passed
        assert g.discrepancy

    def test_tests_with_files(self, tmp_path):
        repo = tmp_path / "repo"
        (repo / "tests").mkdir(parents=True)
        (repo / "tests" / "test_x.py").write_text("pass")
        g = eval_gate("TESTS", {}, repo, "standard", ScaffoldInfo())
        assert g.passed

    def test_tests_flagship_needs_10(self, tmp_path):
        repo = tmp_path / "repo"
        (repo / "tests").mkdir(parents=True)
        (repo / "tests" / "test_x.py").write_text("pass")
        g = eval_gate("TESTS", {}, repo, "flagship", ScaffoldInfo())
        assert not g.passed

    def test_proto_active(self):
        g = eval_gate("PROTO", {"implementation_status": "ACTIVE"}, None, "standard", ScaffoldInfo())
        assert g.passed

    def test_proto_skeleton(self):
        g = eval_gate("PROTO", {"implementation_status": "SKELETON"}, None, "standard", ScaffoldInfo())
        assert not g.passed

    def test_cand_candidate(self):
        g = eval_gate("CAND", {"promotion_status": "CANDIDATE"}, None, "standard", ScaffoldInfo())
        assert g.passed

    def test_cand_local(self):
        g = eval_gate("CAND", {"promotion_status": "LOCAL"}, None, "standard", ScaffoldInfo())
        assert not g.passed

    def test_deploy_with_url(self):
        g = eval_gate("DEPLOY", {"deployment_url": "https://example.com"}, None, "standard", ScaffoldInfo())
        assert g.passed

    def test_deploy_without_url(self):
        g = eval_gate("DEPLOY", {}, None, "standard", ScaffoldInfo())
        assert not g.passed

    def test_grad_graduated(self):
        g = eval_gate("GRAD", {"promotion_status": "GRADUATED"}, None, "standard", ScaffoldInfo())
        assert g.passed

    def test_grad_local(self):
        g = eval_gate("GRAD", {"promotion_status": "LOCAL"}, None, "standard", ScaffoldInfo())
        assert not g.passed

    def test_omega_platinum(self):
        g = eval_gate("OMEGA", {"platinum_status": True}, None, "standard", ScaffoldInfo())
        assert g.passed

    def test_omega_not_platinum(self):
        g = eval_gate("OMEGA", {}, None, "standard", ScaffoldInfo())
        assert not g.passed


# ---------------------------------------------------------------------------
# promo_ready / next_promo
# ---------------------------------------------------------------------------

class TestPromoReady:
    def test_local_ready(self):
        gates = [
            GateResult(name="SEED", passed=True),
            GateResult(name="SCAFFOLD", passed=True),
            GateResult(name="CI", passed=True),
        ]
        assert promo_ready(gates, "LOCAL")

    def test_local_not_ready(self):
        gates = [
            GateResult(name="SEED", passed=True),
            GateResult(name="SCAFFOLD", passed=False),
            GateResult(name="CI", passed=True),
        ]
        assert not promo_ready(gates, "LOCAL")

    def test_candidate_ready(self):
        gates = [
            GateResult(name="SEED", passed=True),
            GateResult(name="SCAFFOLD", passed=True),
            GateResult(name="CI", passed=True),
            GateResult(name="TESTS", passed=True),
            GateResult(name="DOCS", passed=True),
            GateResult(name="PROTO", passed=True),
        ]
        assert promo_ready(gates, "CANDIDATE")


class TestNextPromo:
    def test_local_to_candidate(self):
        assert next_promo("LOCAL") == "CANDIDATE"

    def test_candidate_to_public(self):
        assert next_promo("CANDIDATE") == "PUBLIC_PROCESS"

    def test_graduated_stays(self):
        assert next_promo("GRADUATED") == "GRADUATED"


# ---------------------------------------------------------------------------
# evaluate_repo
# ---------------------------------------------------------------------------

class TestEvaluateRepo:
    def test_basic_evaluation(self):
        entry = _make_entry()
        rp = evaluate_repo(entry, "ORGAN-I", "Theory")
        assert rp.repo == "test-repo"
        assert rp.organ == "ORGAN-I"
        assert len(rp.gates) == len(GATE_ORDER)
        assert rp.total > 0

    def test_with_workspace(self, tmp_path):
        ws = _make_workspace(tmp_path)
        entry = _make_entry(ci_workflow="ci.yml")
        rp = evaluate_repo(entry, "ORGAN-I", "Theory", workspace=ws)
        seed_gate = next(g for g in rp.gates if g.name == "SEED")
        assert seed_gate.passed

    def test_archived_profile(self):
        entry = _make_entry(promotion_status="ARCHIVED")
        rp = evaluate_repo(entry, "ORGAN-I", "Theory")
        assert rp.profile == "archived"
        # Most gates should be N/A
        applicable = [g for g in rp.gates if g.applicable]
        assert len(applicable) < len(GATE_ORDER)

    def test_to_dict_round_trip(self):
        entry = _make_entry()
        rp = evaluate_repo(entry, "ORGAN-I", "Theory")
        d = rp.to_dict()
        assert d["repo"] == "test-repo"
        assert isinstance(d["gates"], list)
        assert isinstance(d["scaffold"], dict)

    def test_never_validated_is_stale(self):
        """Repos with no last_validated date should be flagged as stale."""
        entry = _make_entry()
        entry.pop("last_validated", None)
        rp = evaluate_repo(entry, "ORGAN-I", "Theory")
        assert rp.stale_days == -1
        assert rp.is_stale is True


# ---------------------------------------------------------------------------
# evaluate_all / evaluate_all_for_dashboard
# ---------------------------------------------------------------------------

class TestEvaluateAll:
    def test_evaluates_all_repos(self, registry):
        results = evaluate_all(registry)
        assert len(results) == 6  # 6 repos in minimal fixture
        assert all(isinstance(r, RepoProgress) for r in results)

    def test_for_dashboard_returns_dicts(self, registry):
        results = evaluate_all_for_dashboard(registry, workspace=Path("/nonexistent"))
        assert len(results) == 6
        assert all(isinstance(r, dict) for r in results)
        assert all("repo" in r and "gates" in r for r in results)


# ---------------------------------------------------------------------------
# find_local
# ---------------------------------------------------------------------------

class TestFindLocal:
    def test_finds_by_organ_dir(self, tmp_path):
        ws = _make_workspace(tmp_path)
        entry = {"name": "test-repo", "org": "organvm-i-theoria"}
        local = find_local(entry, "ORGAN-I", ws)
        assert local is not None
        assert local.name == "test-repo"

    def test_not_found(self, tmp_path):
        ws = tmp_path / "workspace"
        ws.mkdir()
        entry = {"name": "nonexistent", "org": "organvm-i-theoria"}
        local = find_local(entry, "ORGAN-I", ws)
        assert local is None
