import os
import uuid
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from paradise_park_sales_agent.square_client import build_square_client


CENT = Decimal("0.01")


@dataclass(frozen=True)
class CheckoutLink:
    """Safe checkout information returned to the website."""

    payment_link_id: str
    order_id: str
    url: str
    amount_cents: int


def dollars_to_cents(amount: Decimal) -> int:
    """Convert a dollar amount into Square's integer-cent format."""

    normalized = amount.quantize(CENT, rounding=ROUND_HALF_UP)

    if normalized <= 0:
        raise ValueError("Checkout amount must be greater than zero.")

    return int(normalized * 100)


def create_square_payment_link(
    *,
    name: str,
    amount: Decimal,
    trace_id: str,
    event_dates: str,
    purchase_details: str,
    client: Any | None = None,
) -> CheckoutLink:
    """Create a single-use Square-hosted payment link."""

    location_id = os.getenv("SQUARE_LOCATION_ID")
    currency = os.getenv("SQUARE_CURRENCY", "USD")

    if not location_id:
        raise RuntimeError(
            "SQUARE_LOCATION_ID is missing from the local environment."
        )

    if not name.strip():
        raise ValueError("Checkout name cannot be empty.")

    if not trace_id.strip():
        raise ValueError("A trace ID is required.")

    amount_cents = dollars_to_cents(amount)

    idempotency_source = (
        f"paradise-park:{trace_id}:{name}:{amount_cents}:{location_id}"
    )
    idempotency_key = str(
        uuid.uuid5(uuid.NAMESPACE_URL, idempotency_source)
    )

    square_client = client or build_square_client()

    line_item_name = f"{name} — {event_dates}"[:255]
    order_note = (
        f"{purchase_details}\nEvent dates: {event_dates}\n"
        "Payment policy: Non-refundable.\n"
        f"Paradise Park reference: {trace_id}"
    )[:500]

    response = square_client.checkout.payment_links.create(
        idempotency_key=idempotency_key,
        order={
            "location_id": location_id,
            "line_items": [
                {
                    "name": line_item_name,
                    "quantity": "1",
                    "base_price_money": {
                        "amount": amount_cents,
                        "currency": currency,
                    },
                    "note": order_note,
                }
            ],
        },
        payment_note=order_note,
    )

    payment_link = response.payment_link

    if not payment_link or not payment_link.url:
        raise RuntimeError("Square did not return a payment link.")

    return CheckoutLink(
        payment_link_id=payment_link.id,
        order_id=payment_link.order_id,
        url=payment_link.url,
        amount_cents=amount_cents,
    )
