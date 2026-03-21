"""Tests for ontologia runbook generator."""



from organvm_engine.ontologia.runbooks import (
    RUNBOOK_TEMPLATES,
    generate_all_runbooks,
    generate_runbook,
    verify_runbooks,
)


class TestRunbookTemplates:
    def test_six_templates(self):
        assert len(RUNBOOK_TEMPLATES) == 6

    def test_all_have_required_fields(self):
        for t in RUNBOOK_TEMPLATES:
            assert "id" in t
            assert "title" in t
            assert "trigger" in t
            assert "checks" in t
            assert "actions" in t
            assert "verification" in t

    def test_unique_ids(self):
        ids = [t["id"] for t in RUNBOOK_TEMPLATES]
        assert len(ids) == len(set(ids))


class TestGenerateRunbook:
    def test_generates_markdown(self):
        template = RUNBOOK_TEMPLATES[0]
        md = generate_runbook(template)
        assert f"# {template['title']}" in md
        assert template["id"] in md
        assert "## Trigger" in md
        assert "## Pre-Checks" in md
        assert "## Actions" in md
        assert "## Verification" in md

    def test_includes_source_policy(self):
        template = RUNBOOK_TEMPLATES[0]
        md = generate_runbook(template)
        if template.get("source_policy"):
            assert template["source_policy"] in md

    def test_includes_checklist(self):
        template = RUNBOOK_TEMPLATES[0]
        md = generate_runbook(template)
        assert "- [ ]" in md  # Markdown checkboxes


class TestGenerateAllRunbooks:
    def test_generates_all(self, tmp_path):
        result = generate_all_runbooks(tmp_path)
        assert result["count"] == 6
        assert len(result["runbooks"]) == 6

    def test_creates_files(self, tmp_path):
        generate_all_runbooks(tmp_path)
        for template in RUNBOOK_TEMPLATES:
            assert (tmp_path / f"{template['id']}.md").is_file()

    def test_creates_index(self, tmp_path):
        generate_all_runbooks(tmp_path)
        index = tmp_path / "INDEX.md"
        assert index.is_file()
        content = index.read_text()
        assert "Operational Runbooks" in content
        for t in RUNBOOK_TEMPLATES:
            assert t["id"] in content


class TestVerifyRunbooks:
    def test_missing_runbooks(self, tmp_path):
        result = verify_runbooks(tmp_path)
        assert not result["valid"]
        assert len(result["missing"]) == 6

    def test_all_present(self, tmp_path):
        generate_all_runbooks(tmp_path)
        result = verify_runbooks(tmp_path)
        assert result["valid"]
        assert result["missing"] == []

    def test_nonexistent_dir(self, tmp_path):
        result = verify_runbooks(tmp_path / "nonexistent")
        assert not result["valid"]
