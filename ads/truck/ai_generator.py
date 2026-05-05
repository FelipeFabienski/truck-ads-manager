from __future__ import annotations

import json
from abc import ABC, abstractmethod

from .schemas import AIGeneratedContent, TruckAdCreateRequest


class AIGeneratorService(ABC):
    """Interface de geração de copy para anúncios de caminhões."""

    @abstractmethod
    def generate(self, request: TruckAdCreateRequest) -> AIGeneratedContent: ...


class MockAIGenerator(AIGeneratorService):
    """
    Gerador determinístico para desenvolvimento e testes.
    Retorna copy baseada em templates sem chamadas externas.
    """

    def generate(self, request: TruckAdCreateRequest) -> AIGeneratedContent:
        label = f"{request.modelo} {request.ano}"
        price_part = f" por {request.preco}" if request.preco else ""
        km_part = f" com {request.km}" if request.km else ""
        local = f"{request.cidade}, {request.estado}"

        copy = (
            f"🚛 {label}{price_part}{km_part}. "
            f"Caminhão em excelente estado, pronto para trabalhar! "
            f"Fale com {request.vendedor_nome} e feche negócio hoje."
        )
        headline = f"{request.modelo} {request.ano} — {request.cor} | {local}"
        roteiro = (
            f"[ABERTURA] Imagem em movimento do {request.modelo} na estrada.\n"
            f"[TEXTO] {copy}\n"
            f"[CTA] Fale com {request.vendedor_nome} no WhatsApp!\n"
            f"[LINK] wa.me/{request.vendedor_wpp}"
        )
        return AIGeneratedContent(copy=copy, headline=headline, roteiro=roteiro)


class ClaudeAIGenerator(AIGeneratorService):
    """
    Gerador de copy usando a API do Claude (Anthropic).

    Usa prompt caching no system prompt — o contexto de negócio é idêntico
    para todos os caminhões, então só os dados do veículo viajam na mensagem.
    Isso reduz latência e custo em ~80% em chamadas repetidas.

    Requer: pip install anthropic
    """

    _SYSTEM_PROMPT = (
        "Você é um especialista em marketing de caminhões no Brasil. "
        "Seu objetivo é criar anúncios altamente persuasivos para Facebook e Instagram "
        "que gerem leads qualificados de compradores de caminhões. "
        "Escreva em português brasileiro informal, direto ao ponto. "
        "Use emojis de caminhão com moderação. "
        "O copy deve ter no máximo 150 caracteres. "
        "O headline deve ter no máximo 60 caracteres. "
        "O roteiro deve descrever um vídeo curto de 15-30 segundos ou um carrossel. "
        "Retorne SOMENTE um objeto JSON válido, sem markdown, sem explicações extras."
    )

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-6",
    ) -> None:
        try:
            import anthropic as _anthropic
            self._client = _anthropic.Anthropic(api_key=api_key)
        except ImportError as exc:
            raise ImportError(
                "ClaudeAIGenerator requires the 'anthropic' package. "
                "Install it with: pip install anthropic"
            ) from exc
        self._model = model

    def generate(self, request: TruckAdCreateRequest) -> AIGeneratedContent:
        import anthropic

        message = self._client.messages.create(
            model=self._model,
            max_tokens=512,
            system=[
                {
                    "type": "text",
                    "text": self._SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[
                {
                    "role": "user",
                    "content": self._build_user_message(request),
                }
            ],
        )
        return self._parse_response(message.content[0].text)

    @staticmethod
    def _build_user_message(r: TruckAdCreateRequest) -> str:
        return (
            f"Gere um anúncio para o seguinte caminhão:\n\n"
            f"Modelo: {r.modelo}\n"
            f"Cor: {r.cor}\n"
            f"Ano: {r.ano}\n"
            f"Preço: {r.preco or 'a consultar'}\n"
            f"Quilometragem: {r.km or 'não informada'}\n"
            f"Vendedor: {r.vendedor_nome}\n"
            f"WhatsApp: {r.vendedor_wpp}\n"
            f"Localização: {r.cidade}, {r.estado}\n\n"
            'Retorne exatamente este JSON:\n'
            '{"copy": "...", "headline": "...", "roteiro": "..."}'
        )

    @staticmethod
    def _parse_response(text: str) -> AIGeneratedContent:
        try:
            data = json.loads(text.strip())
            return AIGeneratedContent(**data)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise ValueError(
                f"Claude returned an unexpected format. Raw response:\n{text}"
            ) from exc
