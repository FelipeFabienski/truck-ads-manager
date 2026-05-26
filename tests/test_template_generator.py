"""
Tests for TemplateAdGenerator — works entirely without ANTHROPIC_API_KEY.
"""
from __future__ import annotations

import pytest

from ads.truck.schemas import TruckAdCreateRequest
from ads.truck.template_generator import TemplateAdGenerator

_BASE = dict(
    modelo="Volvo FH 540",
    cor="Branco",
    ano="2022",
    budget=50.0,
    duracao=7,
    vendedor_nome="João Silva",
    vendedor_wpp="5541999990000",
    cidade="Curitiba",
    estado="PR",
    publico_idade_min=25,
    publico_idade_max=55,
    publico_raio=100,
    publico_genero="all",
    publico_interesses="caminhões,frete",
    publico_posicionamentos=["feed"],
)


def _req(**kwargs) -> TruckAdCreateRequest:
    return TruckAdCreateRequest(**{**_BASE, **kwargs})


@pytest.fixture()
def gen() -> TemplateAdGenerator:
    return TemplateAdGenerator()


# ── copy content ───────────────────────────────────────────────────────────────

def test_copy_contains_modelo(gen: TemplateAdGenerator) -> None:
    content = gen.generate(_req())
    assert "Volvo FH 540" in content.ad_copy


def test_copy_contains_ano(gen: TemplateAdGenerator) -> None:
    content = gen.generate(_req())
    assert "2022" in content.ad_copy


def test_copy_contains_cidade(gen: TemplateAdGenerator) -> None:
    content = gen.generate(_req())
    assert "Curitiba" in content.ad_copy


def test_copy_contains_preco_when_provided(gen: TemplateAdGenerator) -> None:
    content = gen.generate(_req(preco="350000"))
    assert "350000" in content.ad_copy


def test_copy_omits_preco_when_absent(gen: TemplateAdGenerator) -> None:
    content = gen.generate(_req(preco=None))
    assert "R$" not in content.ad_copy


def test_copy_contains_km_when_provided(gen: TemplateAdGenerator) -> None:
    content = gen.generate(_req(km="120000"))
    assert "120000" in content.ad_copy


def test_copy_omits_km_when_absent(gen: TemplateAdGenerator) -> None:
    content = gen.generate(_req(km=None))
    assert " km" not in content.ad_copy


# ── headline ───────────────────────────────────────────────────────────────────

def test_headline_contains_modelo(gen: TemplateAdGenerator) -> None:
    content = gen.generate(_req())
    assert "Volvo FH 540" in content.headline


def test_headline_contains_ano(gen: TemplateAdGenerator) -> None:
    content = gen.generate(_req())
    assert "2022" in content.headline


def test_headline_is_short(gen: TemplateAdGenerator) -> None:
    content = gen.generate(_req())
    assert len(content.headline) <= 80


# ── no external calls ──────────────────────────────────────────────────────────

def test_generate_works_without_api_key(gen: TemplateAdGenerator, monkeypatch) -> None:
    """TemplateAdGenerator must never read ANTHROPIC_API_KEY."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    content = gen.generate(_req())
    assert content.ad_copy
    assert content.headline


def test_generate_is_deterministic(gen: TemplateAdGenerator) -> None:
    req = _req()
    assert gen.generate(req).ad_copy == gen.generate(req).ad_copy


def test_generate_differs_by_modelo(gen: TemplateAdGenerator) -> None:
    a = gen.generate(_req(modelo="Volvo FH 540"))
    b = gen.generate(_req(modelo="Scania R450"))
    assert a.ad_copy != b.ad_copy
    assert a.headline != b.headline
