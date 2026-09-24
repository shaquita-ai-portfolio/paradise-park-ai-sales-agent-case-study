from decimal import Decimal
from types import SimpleNamespace

import pytest

from paradise_park_sales_agent.square_checkout import (
    create_square_payment_link,
    dollars_to_cents,
)


class FakePaymentLinks:
    def __init__(self) -> None:
        self.last_request = None

    def create(self, **kwargs):
        self.last_request = kwargs

        return SimpleNamespace(
            payment_link=SimpleNamespace(
                id="sandbox-link-123",
                order_id="sandbox-order-123",
                url="https://sandbox.square.link/u/test",
            )
        )


class FakeSquareClient:
    def __init__(self) -> None:
        self.payment_links = FakePaymentLinks()
        self.checkout = SimpleNamespace(
            payment_links=self.payment_links
        )


def test_dollars_to_cents() -> None:
    assert dollars_to_cents(Decimal("147.00")) == 14700
    assert dollars_to_cents(Decimal("498.50")) == 49850


def test_amount_must_be_positive() -> None:
    with pytest.raises(ValueError):
        dollars_to_cents(Decimal("0.00"))


def test_create_square_payment_link(monkeypatch) -> None:
    monkeypatch.setenv("SQUARE_LOCATION_ID", "sandbox-location")
    monkeypatch.setenv("SQUARE_CURRENCY", "USD")

    fake_client = FakeSquareClient()

    result = create_square_payment_link(
        name="Rapid Reset 50% Deposit",
        amount=Decimal("498.50"),
        trace_id="quote-rapid-001",
        event_dates="2026-09-10",
        purchase_details="Rapid Reset; 1 guest; 50% deposit",
        client=fake_client,
    )

    request = fake_client.payment_links.last_request

    assert result.amount_cents == 49850
    assert result.order_id == "sandbox-order-123"
    assert result.url.startswith("https://sandbox.square.link/")
    assert request["order"]["line_items"][0]["base_price_money"]["amount"] == 49850
    assert request["order"]["location_id"] == "sandbox-location"
    assert "Rapid Reset" in request["order"]["line_items"][0]["name"]
    assert "Non-refundable" in request["payment_note"]
    assert "quote-rapid-001" in request["payment_note"]


def test_location_is_required(monkeypatch) -> None:
    monkeypatch.delenv("SQUARE_LOCATION_ID", raising=False)

    with pytest.raises(RuntimeError):
        create_square_payment_link(
            name="Express Reset",
            amount=Decimal("147.00"),
            trace_id="quote-express-001",
            event_dates="2026-09-10",
            purchase_details="Express Reset",
            client=FakeSquareClient(),
        )
        
