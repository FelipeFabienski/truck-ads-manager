from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from db.models.meta_credential import MetaCredential


class MetaCredentialRepository:
    def __init__(self, db: Session, user_id: int) -> None:
        self.db = db
        self._user_id = user_id

    def _base_query(self):  # type: ignore[no-untyped-def]
        return (
            self.db.query(MetaCredential)
            .filter(MetaCredential.user_id == self._user_id)
        )

    def get_all(self) -> list[MetaCredential]:
        return self._base_query().order_by(MetaCredential.created_at.desc()).all()

    def get_by_id(self, credential_id: int) -> MetaCredential | None:
        return (
            self._base_query()
            .filter(MetaCredential.id == credential_id)
            .first()
        )

    def create(self, data: dict) -> MetaCredential:
        record = MetaCredential(**data, user_id=self._user_id)
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def update(self, record: MetaCredential, data: dict) -> MetaCredential:
        for key, value in data.items():
            setattr(record, key, value)
        self.db.commit()
        self.db.refresh(record)
        return record

    def delete(self, record: MetaCredential) -> None:
        self.db.delete(record)
        self.db.commit()

    def mark_validated(self, credential_id: int) -> MetaCredential:
        """Mark a credential as valid and record the validation timestamp."""
        record = self._base_query().filter(MetaCredential.id == credential_id).first()
        assert record is not None
        record.is_valid = True
        record.last_validated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(record)
        return record

    def mark_invalid(self, credential_id: int) -> None:
        """Mark a credential as invalid (e.g. after a failed validation)."""
        record = self._base_query().filter(MetaCredential.id == credential_id).first()
        if record:
            record.is_valid = False
            self.db.commit()

    def set_active(self, credential_id: int) -> MetaCredential:
        """Deactivate all credentials for this user, then activate the specified one."""
        self.db.query(MetaCredential).filter(
            MetaCredential.user_id == self._user_id
        ).update({"is_active": False}, synchronize_session="fetch")
        self.db.commit()

        record = self._base_query().filter(MetaCredential.id == credential_id).first()
        assert record is not None
        record.is_active = True
        self.db.commit()
        self.db.refresh(record)
        return record
