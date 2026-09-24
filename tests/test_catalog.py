"""Tests for the Paradise Park catalog boundary."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from paradise_park_sales_agent.catalog import load_catalog


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = Path(
    os.getenv(
        "PARADISE_PARK_CATALOG_PATH",
        PROJECT_ROOT / "data" / "service_catalog.json",
    )
)


@pytest.fixture(scope="module")
def catalog():
    return load_catalog(CATALOG_PATH)


def test_catalog_has_expected_packages_and_services(catalog) -> None:
    assert len(catalog.packages) == 5
    assert "venue_rental" not in {package.id for package in catalog.packages}
    assert len(catalog.services) >= 50
    assert "express_reset" in catalog.packages_by_id
    assert "rapid_reset" in catalog.packages_by_id
    assert "executive_reset" in catalog.packages_by_id


def test_every_package_has_at_least_three_agenda_services(catalog) -> None:
    for package in catalog.packages:
        assert len(package.default_agenda_service_ids) >= 3


def test_every_package_reference_resolves(catalog) -> None:
    known_services = set(catalog.services_by_id)
    for package in catalog.packages:
        references = set(package.default_agenda_service_ids)
        references.update(package.eligible_paid_upgrade_ids)
        assert references <= known_services


def test_fixed_and_starting_prices_have_amounts(catalog) -> None:
    for package in catalog.packages:
        if package.price.status in {"fixed", "starts_at"}:
            assert package.price.amount is not None
    for service in catalog.services:
        if service.client_price.status in {"fixed", "starts_at"}:
            assert service.client_price.amount is not None


def test_guest_safe_service_never_contains_internal_cost(catalog) -> None:
    service = catalog.require_service("assisted_stretch")
    public_payload = service.guest_safe_dict()
    assert "internal_cost" not in public_payload
    assert "overhead_tier" not in public_payload
    assert "internal_name" not in public_payload


def test_unknown_ids_fail_clearly(catalog) -> None:
    with pytest.raises(ValueError, match="Unknown package"):
        catalog.require_package("invented_package")
    with pytest.raises(ValueError, match="Unknown service"):
        catalog.require_service("invented_service")
