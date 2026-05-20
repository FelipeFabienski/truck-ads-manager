"""
Gerador de copy/headline baseado em templates fixos — sem dependências externas.

É o gerador padrão do sistema. Não requer ANTHROPIC_API_KEY nem nenhuma API externa.
"""
from __future__ import annotations

from .ai_generator import AIGeneratorService
from .schemas import AIGeneratedContent, TruckAdCreateRequest


class TemplateAdGenerator(AIGeneratorService):
    """Gera copy e headline a partir de templates fixos com os dados do caminhão."""

    def generate(self, request: TruckAdCreateRequest) -> AIGeneratedContent:
        city = f"{request.cidade}, {request.estado}"
        km_part = f", com {request.km} km" if request.km else ""
        preco_part = f", disponível por R$ {request.preco}" if request.preco else ""

        copy = (
            f"{request.modelo} {request.ano} à venda em {city}. "
            f"Caminhão na cor {request.cor}{km_part}{preco_part}. "
            f"Entre em contato pelo WhatsApp e saiba mais."
        )
        headline = f"{request.modelo} {request.ano} em oferta"

        return AIGeneratedContent(copy=copy, headline=headline)
