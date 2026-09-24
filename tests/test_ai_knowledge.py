"""Tests for guest-safe Paradise Park knowledge retrieval."""

from paradise_park_sales_agent.ai.knowledge import (
    approved_documents,
    search_approved_knowledge,
)


def test_documents_never_expose_internal_fields() -> None:
    combined_content = " ".join(
        document.content
        for document in approved_documents()
    )

    assert "internal_cost" not in combined_content
    assert "overhead_tier" not in combined_content
    assert "internal_name" not in combined_content


def test_rapid_reset_question_returns_package() -> None:
    results = search_approved_knowledge(
        "What is included in Rapid Reset?"
    )

    source_ids = [result.source_id for result in results]

    assert "package:rapid_reset" in source_ids


def test_rapid_and_executive_comparison_returns_approved_details() -> None:
    results = search_approved_knowledge(
        "What is the difference between Rapid Reset and Executive Reset?"
    )

    by_id = {result.source_id: result.content for result in results}

    assert "package:rapid_reset" in by_id
    assert "package:executive_reset" in by_id
    assert "five-to-six-hour" in by_id["package:rapid_reset"]
    assert "Pre-Glow" in by_id["package:executive_reset"]
    assert "seven wellness experiences" in by_id["package:executive_reset"]


def test_womb_wellness_question_returns_service() -> None:
    results = search_approved_knowledge(
        "Tell me about the womb wellness experience."
    )

    source_ids = [result.source_id for result in results]

    assert "service:womb_wellness" in source_ids


def test_payment_question_returns_payment_policy() -> None:
    results = search_approved_knowledge(
        "Can I reserve with a deposit?"
    )

    source_ids = [result.source_id for result in results]

    assert "policy:payments" in source_ids


def test_date_question_returns_availability_policy() -> None:
    results = search_approved_knowledge(
        "Which dates and days can I book?"
    )

    source_ids = [result.source_id for result in results]

    assert "policy:availability" in source_ids


def test_empty_question_returns_no_sources() -> None:
    assert search_approved_knowledge("   ") == []


def test_result_limit_is_enforced() -> None:
    results = search_approved_knowledge(
        "Compare package service price booking options.",
        limit=3,
    )

    assert len(results) <= 3

    
