"""
Tests for runtime configuration behavior:
- System boots without ANTHROPIC_API_KEY
- ENABLE_AI_COPY=false  → TemplateAdGenerator
- ENABLE_AI_COPY=true without key → TemplateAdGenerator (graceful fallback)
- ENABLE_AI_COPY=true with key    → ClaudeAIGenerator
"""
from __future__ import annotations

import importlib

import pytest

from ads.truck.template_generator import TemplateAdGenerator


def _reload_deps(monkeypatch, env: dict[str, str]):
    """Patch env vars then reimport api.dependencies so _get_ai_generator re-reads them."""
    for k in ("ENABLE_AI_COPY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)

    import api.dependencies as deps
    importlib.reload(deps)
    return deps


# ── Template fallback ──────────────────────────────────────────────────────────

def test_no_api_key_uses_template(monkeypatch) -> None:
    deps = _reload_deps(monkeypatch, {"ENABLE_AI_COPY": "false"})
    gen = deps._get_ai_generator()
    assert isinstance(gen, TemplateAdGenerator)


def test_enable_ai_false_uses_template(monkeypatch) -> None:
    deps = _reload_deps(monkeypatch, {"ENABLE_AI_COPY": "false", "ANTHROPIC_API_KEY": "sk-fake"})
    gen = deps._get_ai_generator()
    assert isinstance(gen, TemplateAdGenerator)


def test_enable_ai_true_without_key_falls_back_to_template(monkeypatch) -> None:
    deps = _reload_deps(monkeypatch, {"ENABLE_AI_COPY": "true"})
    gen = deps._get_ai_generator()
    assert isinstance(gen, TemplateAdGenerator)


def test_enable_ai_true_with_key_returns_claude(monkeypatch) -> None:
    pytest.importorskip("anthropic")  # skip if anthropic not installed
    deps = _reload_deps(monkeypatch, {"ENABLE_AI_COPY": "true", "ANTHROPIC_API_KEY": "sk-test-key"})
    from ads.truck.ai_generator import ClaudeAIGenerator
    gen = deps._get_ai_generator()
    assert isinstance(gen, ClaudeAIGenerator)


# ── App startup ────────────────────────────────────────────────────────────────

def test_app_creates_without_anthropic_key(monkeypatch) -> None:
    """create_app() must not raise even when ANTHROPIC_API_KEY is absent."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from api.main import create_app
    app = create_app()
    assert app is not None


def test_app_creates_without_any_ai_config(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ENABLE_AI_COPY", raising=False)
    from api.main import create_app
    app = create_app()
    assert app is not None
