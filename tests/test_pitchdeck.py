"""Tests for the pitchdeck module."""

from pathlib import Path

import pytest

from organvm_engine.pitchdeck import PITCH_MARKER, PITCH_VERSION
from organvm_engine.pitchdeck.data import (
    PitchDeckData,
    assemble,
    _humanize_name,
    _extract_cards_from_text,
    _extract_list_items,
)
from organvm_engine.pitchdeck.themes import PitchTheme, resolve_theme, ORGAN_PALETTES
from organvm_engine.pitchdeck.generator import generate_pitch_deck
from organvm_engine.pitchdeck.readme_parser import parse_readme, extract_first_paragraph
from organvm_engine.pitchdeck.animations import generate_hero_canvas


FIXTURES = Path(__file__).parent / "fixtures"


# ── Constants ────────────────────────────────────────────────────────


class TestConstants:
    def test_pitch_marker_format(self):
        assert PITCH_MARKER.startswith("<!-- ORGANVM:PITCH:AUTO")

    def test_pitch_version(self):
        assert PITCH_VERSION == "1.0"


# ── Name humanization ────────────────────────────────────────────────


class TestHumanizeName:
    def test_simple_name(self):
        assert _humanize_name("recursive-engine") == "Recursive Engine"

    def test_double_hyphen(self):
        result = _humanize_name("peer-audited--behavioral-blockchain")
        assert result == "Peer Audited: Behavioral Blockchain"

    def test_single_word(self):
        assert _humanize_name("dashboard") == "Dashboard"

    def test_multiple_double_hyphens(self):
        # Only splits on first --, second -- becomes spaces via replace
        result = _humanize_name("a--b--c")
        assert result == "A: B  C"


# ── README parser ────────────────────────────────────────────────────


class TestReadmeParser:
    def test_parse_nonexistent(self, tmp_path):
        assert parse_readme(tmp_path / "nonexistent.md") == {}

    def test_parse_sections(self, tmp_path):
        readme = tmp_path / "README.md"
        readme.write_text(
            "# Title\n\nIntro text\n\n"
            "## Problem\n\nThis is the problem.\n\n"
            "## Features\n\n- Feature A\n- Feature B\n"
        )
        sections = parse_readme(readme)
        assert "problem" in sections
        assert "This is the problem." in sections["problem"]
        assert "features" in sections
        assert "Feature A" in sections["features"]

    def test_parse_h3_headings(self, tmp_path):
        readme = tmp_path / "README.md"
        readme.write_text("### Architecture\n\nMicroservices based.\n")
        sections = parse_readme(readme)
        assert "architecture" in sections

    def test_extract_first_paragraph(self):
        text = "First line.\nSecond line.\n\nSecond paragraph."
        assert extract_first_paragraph(text) == "First line. Second line."

    def test_extract_skips_code_blocks(self):
        text = "```python\ncode\n```\n\nActual content."
        assert extract_first_paragraph(text) == "Actual content."


# ── Card extraction ──────────────────────────────────────────────────


class TestCardExtraction:
    def test_extract_bullet_cards(self):
        text = "- **Static Archives** — Files are flat\n- **Frozen Text** — Never evolves"
        cards = _extract_cards_from_text(text, max_cards=3)
        assert len(cards) == 2
        assert cards[0]["title"] == "Static Archives"

    def test_extract_paragraph_fallback(self):
        text = "Problem one is important.\n\nProblem two is also important."
        cards = _extract_cards_from_text(text, max_cards=3)
        assert len(cards) == 2

    def test_max_cards_respected(self):
        text = "- A\n- B\n- C\n- D\n- E"
        cards = _extract_cards_from_text(text, max_cards=2)
        assert len(cards) == 2

    def test_extract_list_items(self):
        text = "- **Fast** — Very quick\n- **Reliable** — Never fails\n- Plain item"
        items = _extract_list_items(text, max_items=6)
        assert len(items) == 3
        assert items[0]["title"] == "Fast"
        assert items[2]["title"] == "Plain item"


# ── Theme resolution ─────────────────────────────────────────────────


class TestThemes:
    def test_default_theme(self):
        theme = PitchTheme()
        assert theme.accent == "#e94560"
        assert "--accent:" in theme.to_css_vars()

    def test_resolve_organ_i(self):
        theme = resolve_theme("ORGAN-I")
        assert theme.accent == "#6366f1"  # Indigo for Theoria
        assert "serif" in theme.font_heading

    def test_resolve_organ_iii(self):
        theme = resolve_theme("ORGAN-III")
        assert theme.accent == "#3b82f6"  # Blue for Ergon
        assert "sans-serif" in theme.font_heading

    def test_resolve_organ_iv(self):
        theme = resolve_theme("ORGAN-IV")
        assert theme.accent == "#22c55e"  # Terminal green for Taxis
        assert "mono" in theme.font_heading.lower()

    def test_resolve_unknown_organ(self):
        theme = resolve_theme("ORGAN-UNKNOWN")
        # Falls back to defaults
        assert theme.accent == "#e94560"

    def test_all_organs_have_palettes(self):
        for key in ("ORGAN-I", "ORGAN-II", "ORGAN-III", "ORGAN-IV",
                     "ORGAN-V", "ORGAN-VI", "ORGAN-VII", "META-ORGANVM"):
            assert key in ORGAN_PALETTES

    def test_css_vars_output(self):
        theme = resolve_theme("ORGAN-I")
        css = theme.to_css_vars()
        assert "--accent:" in css
        assert "--font-heading:" in css
        assert "--hero-bg:" in css

    def test_aesthetic_chain_override(self):
        chain = {"palette": {"accent": "#ff0000", "text": "#ffffff"}}
        theme = resolve_theme("ORGAN-UNKNOWN", aesthetic_chain=chain)
        # accent only overrides for unknown organs (not in ORGAN_PALETTES)
        assert theme.accent == "#ff0000"
        assert theme.text_primary == "#ffffff"


# ── Data assembly ────────────────────────────────────────────────────


class TestDataAssembly:
    def test_assemble_minimal(self):
        repo_entry = {
            "name": "test-repo",
            "org": "test-org",
            "tier": "standard",
            "description": "A test repository.",
        }
        data = assemble("test-repo", "ORGAN-I", repo_entry)
        assert data.repo_name == "test-repo"
        assert data.organ_key == "ORGAN-I"
        assert data.organ_name == "Theoria"
        assert data.display_name == "Test Repo"
        assert data.description == "A test repository."
        assert data.tagline == "A test repository."

    def test_assemble_with_seed(self):
        repo_entry = {"name": "test", "org": "org", "tier": "flagship"}
        seed = {
            "metadata": {"description": "Seed description", "tags": ["python", "engine"]},
            "produces": [{"artifact": "data-stream"}],
            "consumes": [{"artifact": "config"}],
        }
        data = assemble("test", "ORGAN-II", repo_entry, seed=seed)
        assert data.description == "Seed description"
        assert data.tags == ["python", "engine"]
        assert "data-stream" in data.produces
        assert "config" in data.consumes

    def test_assemble_with_readme(self, tmp_path):
        repo_dir = tmp_path / "test-repo"
        repo_dir.mkdir()
        readme = repo_dir / "README.md"
        readme.write_text(
            "# Test Repo\n\n"
            "## Problem\n\n- **Complexity** — Too complex\n- **Speed** — Too slow\n\n"
            "## Features\n\n- **Fast** — Very fast\n- **Simple** — Very simple\n\n"
            "## Architecture\n\nMicroservices-based architecture.\n"
        )
        repo_entry = {"name": "test-repo", "org": "org", "tier": "standard"}
        data = assemble("test-repo", "ORGAN-I", repo_entry, repo_path=repo_dir)
        assert len(data.problem_cards) == 2
        assert data.problem_cards[0]["title"] == "Complexity"
        assert len(data.features) == 2
        assert "Microservices" in data.architecture_text

    def test_tagline_from_description(self):
        repo_entry = {
            "name": "test",
            "org": "org",
            "tier": "standard",
            "description": "Short tagline.",
        }
        data = assemble("test", "ORGAN-I", repo_entry)
        assert data.tagline == "Short tagline."

    def test_tagline_truncation(self):
        long_desc = "A" * 200
        repo_entry = {
            "name": "test",
            "org": "org",
            "tier": "standard",
            "description": long_desc,
        }
        data = assemble("test", "ORGAN-I", repo_entry)
        assert len(data.tagline) <= 103  # 100 + "..."

    def test_assemble_organ_iii_market(self, tmp_path):
        repo_dir = tmp_path / "product"
        repo_dir.mkdir()
        readme = repo_dir / "README.md"
        readme.write_text("## Market\n\nB2B SaaS for developers.\n")
        repo_entry = {
            "name": "product",
            "org": "org",
            "tier": "standard",
            "revenue_model": "subscription",
            "revenue_status": "pre-launch",
        }
        data = assemble("product", "ORGAN-III", repo_entry, repo_path=repo_dir)
        assert data.revenue_model == "subscription"
        assert "B2B SaaS" in data.market_text

    def test_assemble_with_pitch_yaml(self, tmp_path):
        repo_dir = tmp_path / "test-repo"
        repo_dir.mkdir()
        pitch_yaml = repo_dir / "pitch.yaml"
        pitch_yaml.write_text(
            "display_name: Custom Name\n"
            "tagline: Custom tagline here.\n"
            "description: Custom description.\n"
            "tech_stack:\n  - Python\n  - FastAPI\n"
        )
        repo_entry = {"name": "test-repo", "org": "org", "tier": "standard"}
        data = assemble("test-repo", "ORGAN-I", repo_entry, repo_path=repo_dir)
        assert data.display_name == "Custom Name"
        assert data.tagline == "Custom tagline here."
        assert data.description == "Custom description."
        assert data.tech_stack == ["Python", "FastAPI"]


# ── Animations ───────────────────────────────────────────────────────


class TestAnimations:
    @pytest.mark.parametrize("organ", [
        "ORGAN-I", "ORGAN-II", "ORGAN-III", "ORGAN-IV",
        "ORGAN-V", "ORGAN-VI", "ORGAN-VII", "META-ORGANVM",
    ])
    def test_each_organ_has_animation(self, organ):
        js = generate_hero_canvas(organ)
        assert "requestAnimationFrame" in js
        assert "prefers-reduced-motion" in js
        assert "hero-canvas" in js

    def test_unknown_organ_gets_default(self):
        js = generate_hero_canvas("UNKNOWN")
        assert "requestAnimationFrame" in js

    def test_organ_i_has_graph_nodes(self):
        js = generate_hero_canvas("ORGAN-I")
        assert "nodes" in js
        assert "edges" in js

    def test_organ_iv_has_state_machine(self):
        js = generate_hero_canvas("ORGAN-IV")
        assert "states" in js or "INIT" in js


# ── Generator ────────────────────────────────────────────────────────


class TestGenerator:
    def _make_data(self, **overrides) -> PitchDeckData:
        defaults = {
            "repo_name": "test-repo",
            "display_name": "Test Repo",
            "organ_key": "ORGAN-I",
            "organ_name": "Theoria",
            "org": "test-org",
            "tier": "standard",
            "tagline": "A test repo.",
            "description": "A test repository for testing.",
        }
        defaults.update(overrides)
        return PitchDeckData(**defaults)

    def test_generates_valid_html(self):
        data = self._make_data()
        theme = resolve_theme("ORGAN-I")
        html = generate_pitch_deck(data, theme)
        assert html.startswith("<!DOCTYPE html>")
        assert "</html>" in html
        assert PITCH_MARKER in html

    def test_contains_all_sections(self):
        data = self._make_data()
        theme = resolve_theme("ORGAN-I")
        html = generate_pitch_deck(data, theme)
        for section_id in ("hero", "problem", "solution", "features", "architecture", "positioning", "cta"):
            assert f'id="{section_id}"' in html

    def test_organ_theming(self):
        data = self._make_data(organ_key="ORGAN-IV", organ_name="Taxis")
        theme = resolve_theme("ORGAN-IV")
        html = generate_pitch_deck(data, theme)
        assert "#22c55e" in html  # Terminal green accent

    def test_organ_iii_has_market_section(self):
        data = self._make_data(
            organ_key="ORGAN-III", organ_name="Ergon",
            market_text="B2B SaaS.", revenue_model="subscription",
        )
        theme = resolve_theme("ORGAN-III")
        html = generate_pitch_deck(data, theme)
        assert 'id="market"' in html
        assert "B2B SaaS." in html

    def test_organ_i_no_market_section(self):
        data = self._make_data()
        theme = resolve_theme("ORGAN-I")
        html = generate_pitch_deck(data, theme)
        assert 'id="market"' not in html

    def test_hero_animation_embedded(self):
        data = self._make_data()
        theme = resolve_theme("ORGAN-I")
        html = generate_pitch_deck(data, theme)
        assert "requestAnimationFrame" in html

    def test_reduced_motion_support(self):
        data = self._make_data()
        theme = resolve_theme("ORGAN-I")
        html = generate_pitch_deck(data, theme)
        assert "prefers-reduced-motion" in html

    def test_nav_dots(self):
        data = self._make_data()
        theme = resolve_theme("ORGAN-I")
        html = generate_pitch_deck(data, theme)
        assert 'id="nav-dots"' in html

    def test_cta_github_link(self):
        data = self._make_data(github_url="https://github.com/org/repo")
        theme = resolve_theme("ORGAN-I")
        html = generate_pitch_deck(data, theme)
        assert "github.com/org/repo" in html
        assert "View on GitHub" in html

    def test_escapes_html_content(self):
        data = self._make_data(tagline="Test <script>alert(1)</script>")
        theme = resolve_theme("ORGAN-I")
        html = generate_pitch_deck(data, theme)
        assert "<script>alert(1)</script>" not in html
        assert "&lt;script&gt;" in html

    def test_problem_cards_rendered(self):
        data = self._make_data(
            problem_cards=[
                {"title": "Complexity", "text": "Too complex to use."},
                {"title": "Speed", "text": "Too slow for production."},
            ]
        )
        theme = resolve_theme("ORGAN-I")
        html = generate_pitch_deck(data, theme)
        assert "Complexity" in html
        assert "Too complex to use." in html

    def test_features_rendered(self):
        data = self._make_data(
            features=[
                {"title": "Fast", "text": "Very fast."},
                {"title": "Reliable", "text": "Never fails."},
            ]
        )
        theme = resolve_theme("ORGAN-I")
        html = generate_pitch_deck(data, theme)
        assert "Fast" in html
        assert "Never fails." in html

    def test_siblings_rendered(self):
        data = self._make_data(siblings=["sibling-a", "sibling-b"])
        theme = resolve_theme("ORGAN-I")
        html = generate_pitch_deck(data, theme)
        assert "sibling-a" in html
        assert "sibling-b" in html

    def test_positioning_shows_organ(self):
        data = self._make_data()
        theme = resolve_theme("ORGAN-I")
        html = generate_pitch_deck(data, theme)
        assert "Theoria" in html
        assert "Part of ORGANVM" in html


# ── Bespoke detection (sync module) ─────────────────────────────────


class TestBespokeDetection:
    def test_no_file_not_bespoke(self, tmp_path):
        from organvm_engine.pitchdeck.sync import _is_bespoke
        assert _is_bespoke(tmp_path / "nonexistent.html") is False

    def test_file_with_marker_not_bespoke(self, tmp_path):
        from organvm_engine.pitchdeck.sync import _is_bespoke
        f = tmp_path / "index.html"
        f.write_text(f"<html>{PITCH_MARKER} v1.0 generated 2026-01-01 --></html>")
        assert _is_bespoke(f) is False

    def test_file_without_marker_is_bespoke(self, tmp_path):
        from organvm_engine.pitchdeck.sync import _is_bespoke
        f = tmp_path / "index.html"
        f.write_text("<html><body>Hand-crafted deck</body></html>")
        assert _is_bespoke(f) is True
