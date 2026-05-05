from __future__ import annotations

from datetime import datetime, timezone

# ── Tabelas de tradução de status ──────────────────────────────────────────────

_EN_TO_PT: dict[str, str] = {
    "draft": "rascunho",
    "active": "ativo",
    "paused": "pausado",
    "deleted": "removido",
}

_PT_TO_EN: dict[str, str] = {pt: en for en, pt in _EN_TO_PT.items()}


def translate_status_to_pt(status_en: str) -> str:
    """Traduz status interno (EN) para o status exibido no frontend (PT)."""
    return _EN_TO_PT.get(status_en, status_en)


def translate_status_to_en(status_pt: str) -> str:
    """Traduz status do frontend (PT) para o status interno (EN)."""
    return _PT_TO_EN.get(status_pt, status_pt)


# ── Adapter principal ──────────────────────────────────────────────────────────

def to_frontend_dto(campaign: dict, metrics: dict | None = None) -> dict:
    """
    Converte um campaign dict bruto (do AdsProvider) + métricas no JSON exato
    que a função renderCampanhas() do frontend consome.

    Contrato de saída:
    {
        "id": <int, timestamp-ms>,
        "campaign_id": <str, ID interno do provider>,
        "modelo": str,
        "cor": str,
        "ano": str,
        "cidade": str,   # "Curitiba, PR"
        "preco": str,
        "km": str,
        "status": str,   # "ativo" | "pausado" | "rascunho"
        "leads": int,
        "spend": float,
        "created": str,  # "DD/MM/AAAA"
    }
    """
    extra: dict = campaign.get("extra") or {}
    m: dict = metrics or {}

    # ── Derived id and date from created_at ───────────────────────────────────
    frontend_id, created_str = _parse_created(campaign.get("created_at", ""))

    # ── Localização ───────────────────────────────────────────────────────────
    cidade = extra.get("cidade", "")
    estado = extra.get("estado", "")
    cidade_display = f"{cidade}, {estado}".strip(", ") if (cidade or estado) else ""

    return {
        "id": frontend_id,
        "campaign_id": campaign.get("id", ""),
        "modelo": extra.get("modelo") or campaign.get("name", ""),
        "cor": extra.get("cor", ""),
        "ano": extra.get("ano", ""),
        "cidade": cidade_display,
        "preco": extra.get("preco", ""),
        "km": extra.get("km", ""),
        "status": translate_status_to_pt(campaign.get("status", "draft")),
        "leads": int(m.get("leads", 0)),
        "spend": round(float(m.get("spent", 0.0)), 2),
        "created": created_str,
    }


def _parse_created(created_at_raw: str) -> tuple[int, str]:
    """Returns (frontend_id_ms, 'DD/MM/AAAA') from an ISO datetime string."""
    try:
        dt = datetime.fromisoformat(created_at_raw)
    except (ValueError, TypeError):
        dt = datetime.now(timezone.utc)
    return int(dt.timestamp() * 1000), dt.strftime("%d/%m/%Y")
