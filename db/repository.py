from __future__ import annotations

from sqlalchemy.orm import Session

from db.models.campaign import CampaignModel


class CampaignRepository:
    def __init__(self, db: Session, user_id: int | None = None) -> None:
        self.db = db
        self._user_id = user_id

    # ── Write ─────────────────────────────────────────────────────────────────

    def create(self, data: dict) -> CampaignModel:
        if self._user_id is not None:
            data = {**data, "user_id": self._user_id}
        record = CampaignModel(**data)
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def update_record_status(self, record: CampaignModel, status: str) -> None:
        record.status = status
        self.db.commit()

    def update_status_result(
        self,
        record: CampaignModel,
        status: str,
        meta_status: str,
    ) -> CampaignModel:
        """Update status + meta_status atomically after a confirmed Meta API call."""
        record.status = status
        record.meta_status = meta_status
        self.db.commit()
        self.db.refresh(record)
        return record

    def update_record_external_id(self, record: CampaignModel, external_id: str) -> None:
        record.external_id = external_id
        self.db.commit()

    def delete_record(self, record: CampaignModel) -> None:
        self.db.delete(record)
        self.db.commit()

    def update_publish_result(
        self,
        record: CampaignModel,
        meta_credential_id: int,
        meta_campaign_id: str | None,
        meta_adset_id: str | None,
        meta_creative_id: str | None,
        meta_ad_id: str | None,
        meta_status: str,
    ) -> CampaignModel:
        from datetime import datetime, timezone

        record.meta_credential_id = meta_credential_id
        record.meta_campaign_id = meta_campaign_id
        record.meta_adset_id = meta_adset_id
        record.meta_creative_id = meta_creative_id
        record.meta_ad_id = meta_ad_id
        record.meta_status = meta_status
        record.status = "pausado"
        record.published_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(record)
        return record

    # ── Read ──────────────────────────────────────────────────────────────────

    def get_all(
        self,
        status: str | None = None,
        nome: str | None = None,
    ) -> list[CampaignModel]:
        q = self.db.query(CampaignModel)
        if self._user_id is not None:
            q = q.filter(CampaignModel.user_id == self._user_id)
        if status:
            q = q.filter(CampaignModel.status == status)
        if nome:
            q = q.filter(CampaignModel.modelo.ilike(f"%{nome}%"))
        return q.order_by(CampaignModel.created_at.desc()).all()

    def get_by_id(self, campaign_id: str) -> CampaignModel | None:
        q = self.db.query(CampaignModel).filter(
            CampaignModel.campaign_id == campaign_id
        )
        if self._user_id is not None:
            q = q.filter(CampaignModel.user_id == self._user_id)
        return q.first()
