"""Validated access to the Paradise Park service catalog.

This module is the boundary between business-owned catalog data and application
logic. Pricing, eligibility, agenda generation and Gemini explanations should
read catalog data through this module rather than opening JSON independently.
"""

from __future__ import annotations

import json
import os
from paradise_park_sales_agent.runtime_paths import DATA_DIR
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


PriceStatus = Literal[
    "fixed",
    "starts_at",
    "custom",
    "tbd",
    "unknown",
    "low_overhead",
]


class PriceRule(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: PriceStatus
    amount: float | None = None
    basis: str

    @model_validator(mode="after")
    def require_known_amount(self) -> "PriceRule":
        if self.status in {"fixed", "starts_at"} and self.amount is None:
            raise ValueError(f"{self.status} pricing requires a numeric amount")
        return self


class PublicOutputPolicy(BaseModel):
    never_expose_fields: list[str]
    never_invent_missing_prices: bool
    unknown_price_display: str
    medical_disclaimer_required: bool
    separate_report_and_marketing_consent: bool


class PackageDefinition(BaseModel):
    id: str
    name: str
    price: PriceRule
    sales_promise: str
    guest_fit_copy: str
    default_agenda_service_ids: list[str] = Field(min_length=3)
    agenda_commercial_treatment: str
    maximum_high_overhead_included: int = Field(ge=0)
    eligible_paid_upgrade_ids: list[str] = Field(default_factory=list)
    minimum_recommended_services: int = Field(default=3, ge=3)
    primary_cta: str


class ServiceDefinition(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    internal_name: str | None = None
    category: str
    delivery_modes: list[str] = Field(min_length=1)
    client_price: PriceRule
    internal_cost: PriceRule
    overhead_tier: str
    recommendation_tags: list[str]
    approved_benefits: list[str] = Field(min_length=1)
    agenda_copy: str
    auto_recommend: bool
    requires_human_confirmation: bool
    human_only: bool = False

    @model_validator(mode="after")
    def prevent_automatic_human_only_service(self) -> "ServiceDefinition":
        if self.human_only and self.auto_recommend:
            raise ValueError(
                f"{self.id} cannot be both human_only and auto_recommend=true"
            )
        return self

    def guest_safe_dict(self) -> dict:
        """Return fields that may be used by an API response or Gemini prompt."""

        return self.model_dump(
            exclude={"internal_cost", "overhead_tier", "internal_name"}
        )


class ServiceCatalog(BaseModel):
    catalog_version: str
    currency: str
    status: str
    public_output_policy: PublicOutputPolicy
    packages: list[PackageDefinition]
    services: list[ServiceDefinition]

    @model_validator(mode="after")
    def validate_references_and_uniqueness(self) -> "ServiceCatalog":
        package_ids = [package.id for package in self.packages]
        service_ids = [service.id for service in self.services]

        if len(package_ids) != len(set(package_ids)):
            raise ValueError("Package IDs must be unique")
        if len(service_ids) != len(set(service_ids)):
            raise ValueError("Service IDs must be unique")

        known_service_ids = set(service_ids)
        for package in self.packages:
            references = (
                package.default_agenda_service_ids
                + package.eligible_paid_upgrade_ids
            )
            unknown = sorted(set(references) - known_service_ids)
            if unknown:
                raise ValueError(
                    f"{package.id} references unknown services: {', '.join(unknown)}"
                )
            if (
                len(package.default_agenda_service_ids)
                < package.minimum_recommended_services
            ):
                raise ValueError(
                    f"{package.id} does not have enough default agenda services"
                )
        return self

    @property
    def packages_by_id(self) -> dict[str, PackageDefinition]:
        return {package.id: package for package in self.packages}

    @property
    def services_by_id(self) -> dict[str, ServiceDefinition]:
        return {service.id: service for service in self.services}

    def require_package(self, package_id: str) -> PackageDefinition:
        try:
            return self.packages_by_id[package_id]
        except KeyError as error:
            raise ValueError(f"Unknown package: {package_id}") from error

    def require_service(self, service_id: str) -> ServiceDefinition:
        try:
            return self.services_by_id[service_id]
        except KeyError as error:
            raise ValueError(f"Unknown service: {service_id}") from error


def default_catalog_path() -> Path:
    """Resolve the catalog without depending on the current terminal folder."""

    configured = os.getenv("PARADISE_PARK_CATALOG_PATH")
    if configured:
        return Path(configured).expanduser().resolve()

    return DATA_DIR / "service_catalog.json"


@lru_cache(maxsize=4)
def load_catalog(path: str | Path | None = None) -> ServiceCatalog:
    catalog_path = Path(path).resolve() if path else default_catalog_path()
    if not catalog_path.exists():
        raise FileNotFoundError(
            f"Paradise Park service catalog was not found at {catalog_path}"
        )
    with catalog_path.open(encoding="utf-8") as source:
        raw_catalog = json.load(source)
    return ServiceCatalog.model_validate(raw_catalog)


def clear_catalog_cache() -> None:
    """Used by tests and controlled catalog reload workflows."""

    load_catalog.cache_clear()
