from __future__ import annotations

from sqlalchemy.orm import Session

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

    def update_record_status(self, record: CampaignModel, status: str) -> None:
        """Updates status on an already-fetched record — avoids a second DB roundtrip."""
        record.status = status
        self.db.commit()

    def update_record_external_id(self, record: CampaignModel, external_id: str) -> None:
        """Sets external_id on an already-fetched record — avoids a second DB roundtrip."""
        record.external_id = external_id
        self.db.commit()

    def delete_record(self, record: CampaignModel) -> None:
        """Deletes an already-fetched record — avoids a second DB roundtrip."""
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

