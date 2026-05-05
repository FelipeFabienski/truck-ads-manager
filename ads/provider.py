from abc import ABC, abstractmethod


class AdsProvider(ABC):
    """
    Interface base para todos os provedores de anúncios.
    Qualquer novo provedor (Meta, Google, TikTok) deve implementar esta interface.
    O restante do sistema interage apenas com este contrato — nunca com implementações diretas.
    """

    # ── Campanhas ──────────────────────────────────────────────────────────────

    @abstractmethod
    def create_campaign(self, data: dict) -> dict:
        """
        Cria uma nova campanha.

        data:
            name (str)       — nome da campanha
            objective (str)  — ex: OUTCOME_LEADS, OUTCOME_TRAFFIC
            budget (float)   — orçamento diário em BRL
        returns: Campaign dict
        """

    @abstractmethod
    def update_campaign(self, campaign_id: str, data: dict) -> dict:
        """
        Atualiza campos de uma campanha existente.

        data: subset de {name, objective, budget}
        returns: Campaign dict atualizado
        raises: CampaignNotFound
        """

    @abstractmethod
    def get_campaign(self, campaign_id: str) -> dict:
        """
        Retorna os dados de uma campanha pelo ID.

        raises: CampaignNotFound
        """

    @abstractmethod
    def list_campaigns(self, filters: dict | None = None) -> list[dict]:
        """
        Lista campanhas com filtros opcionais.

        filters:
            status (str)         — ex: "active", "paused", "draft"
            name_contains (str)  — busca parcial por nome
        returns: lista de Campaign dicts
        """

    @abstractmethod
    def delete_campaign(self, campaign_id: str) -> dict:
        """
        Remove (ou arquiva) uma campanha e seus adsets/ads associados.

        returns: {"deleted": True, "campaign_id": ...}
        raises: CampaignNotFound
        """

    # ── Conjuntos de anúncios (AdSets) ─────────────────────────────────────────

    @abstractmethod
    def create_adset(self, data: dict) -> dict:
        """
        Cria um conjunto de anúncios vinculado a uma campanha.

        data:
            campaign_id (str)
            name (str)
            audience (dict)  — {locations, age_min, age_max, interests, gender}
            budget (float)
            schedule (dict)  — {start_time, end_time}
        returns: AdSet dict
        raises: CampaignNotFound, CreationError
        """

    # ── Anúncios (Ads) ─────────────────────────────────────────────────────────

    @abstractmethod
    def create_ad(self, data: dict) -> dict:
        """
        Cria um anúncio vinculado a um adset.

        data:
            campaign_id (str)
            adset_id (str)
            name (str)
            copy (str)        — texto do anúncio
            headline (str)    — título
            creative (dict)   — {type, url, caption}
            destination (str) — URL do WhatsApp ou landing page
        returns: Ad dict
        raises: CampaignNotFound, AdSetNotFound, CreationError
        """

    # ── Controle de estado ─────────────────────────────────────────────────────

    @abstractmethod
    def pause_campaign(self, campaign_id: str) -> dict:
        """
        Pausa uma campanha ativa.

        raises: CampaignNotFound, InvalidTransition (se já estiver pausada/draft)
        """

    @abstractmethod
    def activate_campaign(self, campaign_id: str) -> dict:
        """
        Ativa uma campanha (draft → active ou paused → active).

        raises: CampaignNotFound, InvalidTransition
        """

    # ── Métricas ───────────────────────────────────────────────────────────────

    @abstractmethod
    def get_metrics(self, campaign_id: str, period: str = "last_7d") -> dict:
        """
        Retorna métricas de desempenho de uma campanha.

        period: "today" | "last_7d" | "last_30d"
        returns: Metrics dict {impressions, clicks, leads, spent, cpl}
        raises: CampaignNotFound
        """

    # ── Conta ──────────────────────────────────────────────────────────────────

    @abstractmethod
    def validate_account(self, account_id: str) -> bool:
        """
        Valida se a conta de anúncios existe e está autorizada.

        returns: True
        raises: InvalidAccount
        """

    # ── Publicação orquestrada ─────────────────────────────────────────────────

    @abstractmethod
    def publish_ad(self, data: dict) -> dict:
        """
        Orquestra a criação de campanha + adset + ad em uma única operação.

        data:
            campaign (dict) — dados para create_campaign
            adset (dict)    — dados para create_adset (sem campaign_id)
            ad (dict)       — dados para create_ad (sem campaign_id/adset_id)
        returns: {success, message, campaign, adset, ad}
        """
