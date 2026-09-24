from paradise_park_sales_agent import telemetry_repository


def test_telemetry_defaults_to_lead_storage_switch(monkeypatch) -> None:
    monkeypatch.delenv("TELEMETRY_STORAGE_ENABLED", raising=False)
    monkeypatch.setenv("LEAD_STORAGE_ENABLED", "true")
    assert telemetry_repository.telemetry_storage_enabled() is True


def test_disabled_telemetry_is_a_safe_noop(monkeypatch) -> None:
    monkeypatch.setenv("TELEMETRY_STORAGE_ENABLED", "false")
    assert telemetry_repository.record_event_safely(
        collection_environment_name="TEST_COLLECTION",
        default_collection="events",
        record_id="event-1",
        values={"value": "test"},
    ) is False


def test_event_document_id_is_stable_and_safe() -> None:
    value = telemetry_repository.event_document_id("lead/123")
    assert value == telemetry_repository.event_document_id("lead/123")
    assert "/" not in value
