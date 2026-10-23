from sqlalchemy.orm import Session
from tests.conftest import SampleItem


def test_audit_base_generates_id_and_timestamps(db_session: Session):
    """Verify AuditBase automatically populates id, created_at, and updated_at."""
    item = SampleItem(name="Test Item 1")
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)

    # 1. Primary key must be populated automatically
    assert item.id is not None
    assert len(str(item.id)) > 0

    # 2. Timestamps must be auto-populated
    assert item.created_at is not None
    assert item.updated_at is not None

    # 3. Query back from database to verify persistence
    queried = db_session.query(SampleItem).filter_by(id=item.id).first()
    assert queried is not None
    assert queried.name == "Test Item 1"