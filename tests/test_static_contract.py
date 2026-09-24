from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_assessment_exposes_peak_performance_choice() -> None:
    page = (PROJECT_ROOT / "static" / "index.html").read_text(encoding="utf-8")

    assert 'value="9987"' in page
    assert "Peak Performance Pivot" in page


def test_browser_uses_server_side_checkout() -> None:
    script = (PROJECT_ROOT / "static" / "app.js").read_text(encoding="utf-8")

    assert 'fetch("/v1/checkout"' in script
    assert "payment_option" in script
    assert "amount_due_now:" not in script


def test_assessment_collects_dates_and_duration() -> None:
    page = (PROJECT_ROOT / "static" / "index.html").read_text(encoding="utf-8")

    assert 'id="requested-start-date"' in page
    assert 'id="duration-days"' in page


def test_group_budget_ranges_and_ambassador_link_are_present() -> None:
    page = (PROJECT_ROOT / "static" / "index.html").read_text(encoding="utf-8")

    assert 'value="2200"' in page
    assert 'value="10000"' in page
    assert 'value="40000"' in page
    assert 'id="ambassador-chat-link"' in page
    assert 'target="_blank"' in page


def test_product_interest_does_not_replace_retreat_checkout() -> None:
    script = (PROJECT_ROOT / "static" / "app.js").read_text(encoding="utf-8")

    assert "unpriced product never blocks your retreat" in script
    assert "actions.product_shop_url" in script
    assert "paymentChoices" in script


def test_payment_cards_have_visible_gold_separation() -> None:
    styles = (PROJECT_ROOT / "static" / "styles.css").read_text(
        encoding="utf-8"
    )

    assert ".payment-card {" in styles
    assert "border: 2px solid rgba(184, 138, 59, 0.56);" in styles


def test_assessment_places_value_and_challenges_before_investment() -> None:
    page = (PROJECT_ROOT / "static" / "index.html").read_text(encoding="utf-8")
    script = (PROJECT_ROOT / "static" / "app.js").read_text(encoding="utf-8")

    assert 'id="wellness-challenge-options"' in page
    assert 'id="investment-section"' in page
    assert "priorityStep.append(investmentSection)" in script


def test_service_addons_are_sent_inside_assessment_contract() -> None:
    script = (PROJECT_ROOT / "static" / "app.js").read_text(encoding="utf-8")

    assessment_start = script.index("assessment: {")
    request_date = script.index("requested_start_date:")
    addon_field = script.index("selected_addon_ids: [...cartAddonIds]")
    assert assessment_start < addon_field < request_date


def test_secondary_is_directly_below_primary_and_checkout_precedes_reflections() -> None:
    script = (PROJECT_ROOT / "static" / "app.js").read_text(encoding="utf-8")

    checkout = script.index('<div class="cta-box">')
    secondary = script.index('<section class="secondary-recommendations">')
    reflection = script.index('<section class="wellness-reflection">')
    assert secondary < checkout < reflection


def test_only_personal_and_group_retreat_modes_are_present() -> None:
    page = (PROJECT_ROOT / "static" / "index.html").read_text(encoding="utf-8")

    assert 'value="venue_rental"' not in page
    assert "Cabin Only Overnight Stay" not in page
    assert "Personal reset" in page
    assert "Group or team retreat" in page


def test_non_refundable_acceptance_is_sent_to_checkout() -> None:
    script = (PROJECT_ROOT / "static" / "app.js").read_text(encoding="utf-8")

    assert 'id="non-refundable-policy-acceptance"' in script
    assert "non_refundable_policy_accepted: true" in script


def test_contact_recovery_and_ai_concierge_are_prominent() -> None:
    page = (PROJECT_ROOT / "static" / "index.html").read_text(encoding="utf-8")
    script = (PROJECT_ROOT / "static" / "app.js").read_text(encoding="utf-8")

    for field_id in (
        "contact-name",
        "contact-email",
        "contact-phone",
        "referral-source",
        "instagram-handle",
    ):
        assert f'id="{field_id}"' in page
    assert 'class="floating-concierge"' in page
    assert 'fetch("/v1/leads/capture"' in script
    assert "Add selected enhancements to cart" in page
    assert 'packageInfo.package_id === "rapid_reset"' in script
    assert 'name="result_service_addon"' in script


def test_conversion_feedback_and_concierge_lead_context_are_present() -> None:
    script = (PROJECT_ROOT / "static" / "app.js").read_text(encoding="utf-8")

    assert 'fetch("/v1/feedback"' in script
    assert 'name="checkout_readiness"' in script
    assert "recommendation_helpfulness" in script
    assert "lead_id: latestPayload?.lead_id ?? leadId" in script
