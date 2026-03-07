"""Tests for organvm_engine.domain — shared domain fingerprinting."""

from organvm_engine.domain import domain_fingerprint, domain_set


class TestDomainFingerprint:
    def test_deterministic(self):
        tags = ["python", "fastapi"]
        refs = ["src/app.py"]
        assert domain_fingerprint(tags, refs) == domain_fingerprint(tags, refs)

    def test_length_16_hex(self):
        fp = domain_fingerprint(["python"], ["src/main.py"])
        assert len(fp) == 16
        assert all(c in "0123456789abcdef" for c in fp)

    def test_empty_inputs(self):
        fp = domain_fingerprint([], [])
        assert len(fp) == 16
        assert all(c in "0123456789abcdef" for c in fp)

    def test_case_insensitive_tags(self):
        assert domain_fingerprint(["Python"], []) == domain_fingerprint(["python"], [])

    def test_order_independent(self):
        assert domain_fingerprint(["a", "b"], []) == domain_fingerprint(["b", "a"], [])

    def test_different_content(self):
        fp1 = domain_fingerprint(["python"], ["src/a.py"])
        fp2 = domain_fingerprint(["rust"], ["src/b.rs"])
        assert fp1 != fp2

    def test_file_refs_order_independent(self):
        assert (
            domain_fingerprint([], ["b.py", "a.py"])
            == domain_fingerprint([], ["a.py", "b.py"])
        )

    def test_delegation_matches_index(self):
        """index._domain_fingerprint delegates to domain.domain_fingerprint."""
        from organvm_engine.plans.index import _domain_fingerprint

        tags = ["python", "mcp"]
        refs = ["src/server.py", "tests/test_server.py"]
        assert _domain_fingerprint(tags, refs) == domain_fingerprint(tags, refs)


class TestDomainSet:
    def test_prefixed(self):
        ds = domain_set(["python"], ["src/foo.py"])
        assert ds == {"tag:python", "ref:src/foo.py"}

    def test_empty(self):
        assert domain_set([], []) == set()

    def test_deduplicates(self):
        ds = domain_set(["python", "Python", "PYTHON"], ["a.py", "a.py"])
        assert ds == {"tag:python", "ref:a.py"}

    def test_case_insensitive_tags(self):
        ds = domain_set(["FastAPI", "PYTHON"], [])
        assert "tag:fastapi" in ds
        assert "tag:python" in ds

    def test_refs_case_preserved(self):
        ds = domain_set([], ["src/MyFile.py"])
        assert "ref:src/MyFile.py" in ds
