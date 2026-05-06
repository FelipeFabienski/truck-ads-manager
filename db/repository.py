from __future__ import annotations

from sqlalchemy.orm import Session

from ads.exceptions import CampaignNotFound
from db.models import CampaignModel


class CampaignRepository:
    """Isola todas as queries SQLAlchemy da lógica de negócio.

    Recebe uma Session por request (injetada via FastAPI Depends) e expõe
    apenas a interface necessária para o TruckAdService — sem SQL avulso
    fora desta classe.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # ── Write ─────────────────────────────────────────────────────────────────

    def create(self, data: dict) -> CampaignModel:
        """Persiste um novo registro e retorna o objeto atualizado do banco."""
        record = CampaignModel(**data)
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def update_status(self, campaign_id: str, status: str) -> CampaignModel:
        record = self._require(campaign_id)
        record.status = status
        self.db.commit()
        self.db.refresh(record)
        return record

    def update_external_id(self, campaign_id: str, external_id: str) -> None:
        """Salva o ID retornado pela plataforma de anúncios após a publicação."""
        record = self.get_by_id(campaign_id)
        if record:
            record.external_id = external_id
            self.db.commit()

    def delete(self, campaign_id: str) -> None:
        record = self._require(campaign_id)
        self.db.delete(record)
        self.db.commit()

    # ── Read ──────────────────────────────────────────────────────────────────

    def get_all(
        self,
        status: str | None = None,
        nome: str | None = None,
    ) -> list[CampaignModel]:
        q = self.db.query(CampaignModel)
        if status:
            q = q.filter(CampaignModel.status == status)
        if nome:
            q = q.filter(CampaignModel.modelo.ilike(f"%{nome}%"))
        return q.order_by(CampaignModel.created_at.desc()).all()

    def get_by_id(self, campaign_id: str) -> CampaignModel | None:
        return (
            self.db.query(CampaignModel)
            .filter(CampaignModel.campaign_id == campaign_id)
            .first()
        )

    # ── Private ───────────────────────────────────────────────────────────────

    def _require(self, campaign_id: str) -> CampaignModel:
        record = self.get_by_id(campaign_id)
        if not record:
            raise CampaignNotFound(campaign_id)
        return record
