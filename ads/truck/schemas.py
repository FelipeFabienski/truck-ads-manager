from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class TruckAdCreateRequest(BaseModel):
    """DTO exato que espelha o formulário do frontend."""

    # Dados do caminhão
    modelo: str = Field(..., min_length=2)
    cor: str = Field(..., min_length=2)
    ano: str = Field(..., pattern=r"^\d{4}$")
    preco: str | None = None
    km: str | None = None

    # Configuração da campanha
    budget: float = Field(..., gt=0, description="Orçamento diário em BRL")
    duracao: int = Field(default=0, ge=0, description="Duração em dias; 0 = contínuo")

    # Dados do vendedor
    vendedor_nome: str = Field(..., min_length=2)
    vendedor_wpp: str = Field(..., description="Número WhatsApp (só dígitos)")

    # Localização
    cidade: str = Field(..., min_length=2)
    estado: str = Field(..., min_length=2, max_length=2)

    # Segmentação de público
    publico_idade_min: int = Field(default=18, ge=18, le=65)
    publico_idade_max: int = Field(default=65, ge=18, le=65)
    publico_raio: int = Field(default=50, ge=1, le=500)
    publico_genero: str = Field(default="all")
    publico_interesses: str = Field(default="", description="CSV de interesses")
    publico_posicionamentos: list[str] = Field(default_factory=list)

    @field_validator("estado")
    @classmethod
    def estado_upper(cls, v: str) -> str:
        return v.upper()

    @field_validator("publico_genero")
    @classmethod
    def genero_valid(cls, v: str) -> str:
        allowed = {"all", "male", "female"}
        if v not in allowed:
            raise ValueError(f"publico_genero must be one of {allowed}")
        return v

    @field_validator("vendedor_wpp")
    @classmethod
    def wpp_digits_only(cls, v: str) -> str:
        digits = "".join(c for c in v if c.isdigit())
        if len(digits) < 10:
            raise ValueError("vendedor_wpp must contain at least 10 digits")
        return digits

    @model_validator(mode="after")
    def idade_range_valid(self) -> "TruckAdCreateRequest":
        if self.publico_idade_min >= self.publico_idade_max:
            raise ValueError("publico_idade_min must be less than publico_idade_max")
        return self


class AIGeneratedContent(BaseModel):
    """Conteúdo gerado pela IA para um anúncio.

    O campo Python é `ad_copy`; o alias `copy` preserva o contrato de API/JSON.
    """

    model_config = ConfigDict(populate_by_name=True)

    ad_copy: str = Field(alias="copy")
    headline: str
    roteiro: str


class TruckAdPublishResponse(BaseModel):
    """Resposta achatada retornada ao frontend após a publicação."""

    model_config = ConfigDict(populate_by_name=True)

    id: int = Field(description="ID baseado em timestamp (ms) para o frontend")
    campaign_id: str = Field(description="ID interno da campanha")
    status: str = "rascunho"

    # Dados do caminhão (lidos do banco após persistência)
    modelo: str
    cor: str
    ano: str
    cidade: str
    preco: str = ""
    km: str = ""

    # Conteúdo gerado pela IA
    ad_copy: str = Field(alias="copy")
    headline: str
    roteiro: str

    # Configuração
    budget: float
    created: str = Field(description="Data de criação no formato DD/MM/AAAA")
