from decimal import Decimal

from fastapi.testclient import TestClient

import paradise_park_sales_agent.api as api_module
from paradise_park_sales_agent.api import app
from paradise_park_sales_agent.square_checkout import CheckoutLink


client = TestClient(app)


def create_payload(
    guest_statement: str = "I want unhurried rest.",
) -> dict:
    """Create a valid public API request for tests."""

    return {
        "assessment": {
            "assessment_mode": "retreat_planner",
            "contact_name": "Sample Guest",
            "contact_email": "guest@example.com",
            "contact_phone": "4045550100",
            "referral_source": "Instagram",
            "organization_name": "Example Organization",
            "group_size": 1,
            "budget": "1200",
            "goals": [
                "deep_rest",
                "body_tension",
            ],
            "signals": [
                {
                    "code": "deep_rest",
                    "source": "explicit",
                    "guest_statement": guest_statement,
                },
                {
                    "code": "body_tension",
                    "source": "explicit",
                    "guest_statement": (
                        "I often notice physical tension."
                    ),
                },
            ],
            "consent": {
                "deliver_report": True,
                "marketing": False,
            },
        },
        "requested_start_date": "2026-09-10",
        "duration_days": 1,
        "selected_upgrades": [],
        "additional_text": "",
        "lead_id": "test-lead-1234",
    }


def test_assessment_page() -> None:
    """The customer assessment interface should load."""

    response = client.get("/")

    assert response.status_code == 200
    assert "Paradise Park Experience Planner" in response.text


def test_static_stylesheet() -> None:
    """The browser should be able to load the stylesheet."""

    response = client.get("/static/styles.css")

    assert response.status_code == 200
    assert "--forest" in response.text


def test_static_javascript() -> None:
    """The browser should be able to load the application JavaScript."""

    response = client.get("/static/app.js")

    assert response.status_code == 200
    assert "buildPayload" in response.text


def test_health_endpoint() -> None:
    """The health endpoint should report that the API is available."""

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert response.json()["version"] == "0.6.6"


def test_conversion_feedback_is_accepted_and_stored(monkeypatch) -> None:
    captured = {}
    monkeypatch.setattr(
        api_module,
        "record_event_safely",
        lambda **kwargs: captured.update(kwargs) or True,
    )
    response = client.post(
        "/v1/feedback",
        json={
            "lead_id": "test-lead-1234",
            "trace_id": "trace-123",
            "primary_package_id": "express_reset",
            "secondary_package_id": "rapid_reset",
            "investment_target": "499",
            "quoted_total": "147",
            "group_size": 1,
            "readiness": "interested_not_ready",
            "barrier": "needs_more_information",
            "helpfulness": "very_helpful",
            "additional_comment": "I need availability details.",
        },
    )

    assert response.status_code == 202
    assert captured["default_collection"] == "conversion_feedback"
    assert captured["values"]["barrier"] == "needs_more_information"


def test_not_ready_feedback_requires_a_reason() -> None:
    response = client.post(
        "/v1/feedback",
        json={
            "lead_id": "test-lead-1234",
            "primary_package_id": "express_reset",
            "readiness": "interested_not_ready",
        },
    )
    assert response.status_code == 422


def test_recommendation_endpoint() -> None:
    """A valid assessment should produce a recommendation."""

    response = client.post(
        "/v1/recommendations",
        json=create_payload(),
    )

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "completed"
    assert body["recommendation"] is not None
    assert (
        body["recommendation"]["package"]["package_id"]
        == "rapid_reset"
    )
    assert len(body["recommendation"]["agenda_items"]) >= 3
    assert "cabin_reservation_url" not in body["actions"]
    assert body["actions"]["product_shop_url"] == (
        "https://square.link/u/FGnBH1yz"
    )
    assert body["actions"]["questions_url"] == (
        "https://www.paradiseislife.biz/contact-8"
    )
    assert body["actions"]["consultation_url"] == (
        "https://www.paradiseislife.biz/contact-8"
    )

    booking = body["booking"]

    assert booking["requested_start_date"] == "2026-09-10"
    assert booking["requested_end_date"] == "2026-09-10"
    assert booking["duration_days"] == 1
    assert booking["group_size"] == 1
    assert booking["selected_upgrades"] == []
    assert (
        booking["pricing_basis"]
        == "per person, per service day"
    )


def test_selected_service_addon_is_nested_in_assessment_and_priced() -> None:
    payload = create_payload()
    payload["assessment"]["selected_addon_ids"] = ["assisted_stretch"]

    response = client.post("/v1/recommendations", json=payload)

    assert response.status_code == 200
    recommendation = response.json()["recommendation"]
    full_payment = next(
        choice
        for choice in recommendation["payment_choices"]
        if choice["payment_option"] == "pay_in_full"
    )
    assert full_payment["order_total"] == "1072.30"


def test_valid_multiday_schedule_and_upgrade() -> None:
    """A valid four-day retreat and approved upgrade should pass."""

    payload = create_payload()
    payload["requested_start_date"] = "2026-09-10"
    payload["duration_days"] = 4
    payload["selected_upgrades"] = [
        "pamper_collection"
    ]

    response = client.post(
        "/v1/recommendations",
        json=payload,
    )

    assert response.status_code == 200

    booking = response.json()["booking"]

    assert booking["requested_start_date"] == "2026-09-10"
    assert booking["requested_end_date"] == "2026-09-13"
    assert booking["duration_days"] == 4
    assert booking["selected_upgrades"] == [
        "pamper_collection"
    ]


def test_soil_to_soul_upgrade_is_accepted() -> None:
    """The controlled product upgrade should be accepted."""

    payload = create_payload()
    payload["selected_upgrades"] = [
        "soil_to_soul_products"
    ]

    response = client.post(
        "/v1/recommendations",
        json=payload,
    )

    assert response.status_code == 200
    assert response.json()["booking"]["selected_upgrades"] == [
        "soil_to_soul_products"
    ]


def test_api_never_exposes_internal_costs() -> None:
    """Guest responses must not reveal internal commercial data."""

    response = client.post(
        "/v1/recommendations",
        json=create_payload(),
    )

    assert response.status_code == 200

    serialized = response.text

    assert "internal_cost" not in serialized
    assert "overhead_tier" not in serialized
    assert "internal_name" not in serialized
    assert "guardrail_decision" not in serialized


def test_review_required_response_hides_recommendation() -> None:
    """Sensitive requests should be routed to an ambassador."""

    response = client.post(
        "/v1/recommendations",
        json=create_payload(
            "I am pregnant and would like service recommendations."
        ),
    )

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "human_review"
    assert body["recommendation"] is None
    assert body["booking"]["requested_start_date"] == (
        "2026-09-10"
    )


def test_invalid_group_size_returns_422() -> None:
    """A retreat cannot be created for zero guests."""

    payload = create_payload()
    payload["assessment"]["group_size"] = 0

    response = client.post(
        "/v1/recommendations",
        json=payload,
    )

    assert response.status_code == 422


def test_unavailable_retreat_date_returns_422() -> None:
    """Wednesday is not an approved Paradise Park service day."""

    payload = create_payload()
    payload["requested_start_date"] = "2026-09-09"

    response = client.post(
        "/v1/recommendations",
        json=payload,
    )

    assert response.status_code == 422


def test_first_week_date_returns_422() -> None:
    """Experiences are unavailable during the first week."""

    payload = create_payload()
    payload["requested_start_date"] = "2026-09-03"

    response = client.post(
        "/v1/recommendations",
        json=payload,
    )

    assert response.status_code == 422


def test_retreat_longer_than_four_days_returns_422() -> None:
    """The MVP supports no more than four service days."""

    payload = create_payload()
    payload["duration_days"] = 5

    response = client.post(
        "/v1/recommendations",
        json=payload,
    )

    assert response.status_code == 422


def test_unsupported_upgrade_returns_422() -> None:
    """Clients cannot submit an invented upgrade."""

    payload = create_payload()
    payload["selected_upgrades"] = [
        "unsupported_upgrade"
    ]

    response = client.post(
        "/v1/recommendations",
        json=payload,
    )

    assert response.status_code == 422


def test_unexpected_request_field_returns_422() -> None:
    """The public API should reject fields outside its schema."""

    payload = create_payload()
    payload["manual_discount"] = "90%"

    response = client.post(
        "/v1/recommendations",
        json=payload,
    )

    assert response.status_code == 422


def test_paradise_park_origin_is_allowed() -> None:
    """The production Wix website should pass the CORS check."""

    response = client.options(
        "/v1/recommendations",
        headers={
            "Origin": "https://www.paradiseislife.biz",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert (
        response.headers["access-control-allow-origin"]
        == "https://www.paradiseislife.biz"
    )


def test_express_returns_one_core_activation() -> None:
    payload = create_payload()
    payload["assessment"]["budget"] = "500"

    response = client.post("/v1/recommendations", json=payload)

    assert response.status_code == 200
    recommendation = response.json()["recommendation"]
    assert recommendation["package"]["package_id"] == "express_reset"
    assert len(recommendation["agenda_items"]) == 1
    assert recommendation["package"]["checkout_mode"] == "express_calendar"


def test_checkout_uses_server_calculated_deposit(monkeypatch) -> None:
    captured: dict = {}

    def fake_payment_link(**kwargs):
        captured.update(kwargs)
        return CheckoutLink(
            payment_link_id="sandbox-link",
            order_id="sandbox-order",
            url="https://sandbox.square.link/u/paradise",
            amount_cents=49850,
        )

    monkeypatch.setattr(
        "paradise_park_sales_agent.api.create_square_payment_link",
        fake_payment_link,
    )
    payload = create_payload()
    payload["payment_option"] = "deposit"
    payload["non_refundable_policy_accepted"] = True

    response = client.post("/v1/checkout", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["amount_due_now"] == "498.50"
    assert body["order_total"] == "997.00"
    assert captured["amount"] == Decimal("498.50")


def test_product_interest_does_not_block_base_checkout(monkeypatch) -> None:
    captured: dict = {}

    def fake_payment_link(**kwargs):
        captured.update(kwargs)
        return CheckoutLink(
            payment_link_id="sandbox-link",
            order_id="sandbox-order",
            url="https://sandbox.square.link/u/paradise",
            amount_cents=49850,
        )

    monkeypatch.setattr(
        "paradise_park_sales_agent.api.create_square_payment_link",
        fake_payment_link,
    )
    payload = create_payload()
    payload["payment_option"] = "deposit"
    payload["non_refundable_policy_accepted"] = True
    payload["selected_upgrades"] = ["pamper_collection"]

    response = client.post("/v1/checkout", json=payload)

    assert response.status_code == 200
    assert response.json()["amount_due_now"] == "498.50"
    assert captured["amount"] == Decimal("498.50")


def test_checkout_rejects_client_supplied_amount() -> None:
    payload = create_payload()
    payload["payment_option"] = "deposit"
    payload["non_refundable_policy_accepted"] = True
    payload["amount"] = "1.00"

    response = client.post("/v1/checkout", json=payload)

    assert response.status_code == 422


def test_checkout_requires_non_refundable_policy_acceptance() -> None:
    payload = create_payload()
    payload["payment_option"] = "deposit"

    response = client.post("/v1/checkout", json=payload)

    assert response.status_code == 422
    assert "non-refundable" in response.text


def test_express_checkout_uses_server_recomputed_amount(monkeypatch) -> None:
    def fake_payment_link(**kwargs):
        return CheckoutLink(
            payment_link_id="sandbox-link",
            order_id="sandbox-order",
            url="https://sandbox.square.link/u/paradise",
            amount_cents=14700,
        )

    payload = create_payload()
    payload["assessment"]["budget"] = "500"
    payload["payment_option"] = "pay_in_full"
    payload["non_refundable_policy_accepted"] = True

    monkeypatch.setattr(
        "paradise_park_sales_agent.api.create_square_payment_link",
        fake_payment_link,
    )
    response = client.post("/v1/checkout", json=payload)
    assert response.status_code == 200
    assert response.json()["amount_due_now"] == "147.00"
