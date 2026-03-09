"""Tests for the SystemOrganism module."""


from organvm_engine.metrics.organism import (
    GateStats,
    SystemOrganism,
    clear_organism_cache,
    compute_organism,
    get_organism,
)


class TestComputeOrganism:
    def test_returns_system_organism(self, registry):
        org = compute_organism(registry)
        assert isinstance(org, SystemOrganism)

    def test_total_repos(self, registry):
        org = compute_organism(registry)
        assert org.total_repos == 6

    def test_organ_count(self, registry):
        org = compute_organism(registry)
        assert len(org.organs) == 4

    def test_organ_order(self, registry):
        org = compute_organism(registry)
        ids = [o.organ_id for o in org.organs]
        assert ids.index("ORGAN-I") < ids.index("ORGAN-II")
        assert ids.index("ORGAN-II") < ids.index("ORGAN-III")

    def test_organ_repos(self, registry):
        org = compute_organism(registry)
        organ_i = org.find_organ("ORGAN-I")
        assert organ_i is not None
        assert organ_i.count == 2

    def test_sys_pct(self, registry):
        org = compute_organism(registry)
        assert 0 <= org.sys_pct <= 100

    def test_find_repo(self, registry):
        org = compute_organism(registry)
        repo = org.find_repo("recursive-engine")
        assert repo is not None
        assert repo.organ == "ORGAN-I"

    def test_find_repo_missing(self, registry):
        org = compute_organism(registry)
        assert org.find_repo("nonexistent") is None

    def test_profile_counts(self, registry):
        org = compute_organism(registry)
        profiles = org.profile_counts()
        assert isinstance(profiles, dict)
        assert sum(profiles.values()) == 6

    def test_promo_counts(self, registry):
        org = compute_organism(registry)
        promos = org.promo_counts()
        assert sum(promos.values()) == 6

    def test_gate_stats(self, registry):
        org = compute_organism(registry)
        stats = org.gate_stats()
        assert len(stats) == 10
        assert all(isinstance(gs, GateStats) for gs in stats)
        assert stats[0].name == "SEED"

    def test_to_dict(self, registry):
        org = compute_organism(registry)
        d = org.to_dict()
        assert d["total_repos"] == 6
        assert "organs" in d
        assert "gate_stats" in d
        assert "generated" in d

    def test_with_omega(self, registry, tmp_path):
        # omega requires soak dir — provide empty one
        org = compute_organism(registry, include_omega=True)
        assert org.omega is not None
        assert "score" in org.omega


class TestOrganOrganism:
    def test_avg_pct(self, registry):
        org = compute_organism(registry)
        organ = org.find_organ("ORGAN-I")
        assert organ is not None
        assert 0 <= organ.avg_pct <= 100

    def test_to_dict(self, registry):
        org = compute_organism(registry)
        organ = org.find_organ("ORGAN-I")
        d = organ.to_dict()
        assert d["organ_id"] == "ORGAN-I"
        assert d["count"] == 2
        assert isinstance(d["repos"], list)


class TestGateStats:
    def test_rate_calculation(self):
        gs = GateStats(name="CI", applicable=10, passed=7)
        assert gs.rate == 70
        assert gs.failed == 3

    def test_rate_zero_applicable(self):
        gs = GateStats(name="CI")
        assert gs.rate == 0

    def test_to_dict(self):
        gs = GateStats(name="SEED", applicable=6, passed=5)
        d = gs.to_dict()
        assert d["name"] == "SEED"
        assert d["rate"] == 83


class TestGetOrganismCached:
    def test_caching(self, registry):
        clear_organism_cache()
        org1 = get_organism(registry=registry, ttl=60)
        org2 = get_organism(registry=registry, ttl=60)
        # Same object due to caching
        assert org1 is org2

    def test_cache_clear(self, registry):
        clear_organism_cache()
        org1 = get_organism(registry=registry, ttl=60)
        clear_organism_cache()
        org2 = get_organism(registry=registry, ttl=60)
        assert org1 is not org2
