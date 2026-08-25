from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from src.career_service import CareerService
from src.intent_contracts import compile_intent, resolve_intent, validate_contracts


def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_career_provider_absence_is_explicit_and_never_fake_listings():
    db = db_session()
    result = CareerService(db).overview("alice")
    assert result["status"] == "EMPTY_RESULT"
    assert result["provider"]["status"] == "NOT_CONFIGURED"
    assert result["opportunities"] == []


def test_career_intents_resolve_to_owner_scoped_read_without_approval():
    for query, action in (("Show me jobs I saved", "saved_opportunities"), ("Which applications need follow-up?", "applications"), ("What interviews do I have this week?", "interviews")):
        resolved = resolve_intent(compile_intent(query))
        assert resolved.available is True
        assert resolved.binding_name == "read_career"
        assert resolved.action_id == action
        assert resolved.action.approval.value == "none"


def test_career_opportunity_normalization_deduplicates_per_owner_and_provider():
    db = db_session(); service = CareerService(db)
    payload = {"external_id": "abc-1", "title": "Linux Infrastructure Engineer", "employer": "Example", "location": "Remote"}
    first = service.normalize_opportunity("alice", payload, "fixture")
    second = service.normalize_opportunity("alice", payload, "fixture")
    assert first["id"] == second["id"]
    assert len(service.overview("alice")["opportunities"]) == 1
    assert service.overview("bob")["opportunities"] == []


def test_career_contract_registry_is_complete():
    assert validate_contracts() == []
