const form = document.querySelector("#assessment-form");
const steps = [...document.querySelectorAll(".form-step")];

const nextButton = document.querySelector("#next-button");
const backButton = document.querySelector("#back-button");
const submitButton = document.querySelector("#submit-button");

const formError = document.querySelector("#form-error");
const progressBar = document.querySelector("#progress-bar");
const progressPercent = document.querySelector("#progress-percent");
const stepLabel = document.querySelector("#step-label");

const assessmentCard = document.querySelector("#assessment-card");
const reportCard = document.querySelector("#report-card");
const reportContent = document.querySelector("#report-content");
const startOverButton = document.querySelector(
  "#start-over-button",
);

const conciergeForm = document.querySelector("#concierge-form");
const conciergeQuestion = document.querySelector("#concierge-question");
const conciergeSubmit = document.querySelector("#concierge-submit");
const conciergeError = document.querySelector("#concierge-error");
const conciergeAnswer = document.querySelector("#concierge-answer");
const conciergeAnswerCopy = document.querySelector("#concierge-answer-copy");
const conciergeStatus = document.querySelector("#concierge-status");
const conciergeFollowups = document.querySelector("#concierge-followups");
const conciergeFollowupButtons = document.querySelector(
  "#concierge-followup-buttons",
);
const conciergeAction = document.querySelector("#concierge-action");
const conciergeSources = document.querySelector("#concierge-sources");
const conciergeSourceList = document.querySelector("#concierge-source-list");
const conciergeDisclaimer = document.querySelector("#concierge-disclaimer");
const conciergeTrace = document.querySelector("#concierge-trace");
const conciergeCharacterCount = document.querySelector(
  "#concierge-character-count",
);

const checkoutLinks =
  window.PARADISE_PARK_CHECKOUT_LINKS ?? {};

let currentStep = 1;
let latestPayload = null;
let latestResult = null;
let selectedAlternativePackageId = null;
let latestActions = {};
let latestConciergeTraceId = null;
const leadId = globalThis.crypto?.randomUUID?.()
  ?? `lead-${Date.now()}-${Math.random().toString(16).slice(2)}`;
let cartAddonIds = [];
let cartUpgradeIds = [];


function showStep(stepNumber) {
  currentStep = stepNumber;

  steps.forEach((step) => {
    const isActive =
      Number(step.dataset.step) === currentStep;

    step.classList.toggle("active", isActive);
  });

  const percentage = Math.round(
    (currentStep / steps.length) * 100,
  );

  progressBar.style.width = `${percentage}%`;
  progressPercent.textContent = `${percentage}%`;
  stepLabel.textContent =
    `Step ${currentStep} of ${steps.length}`;

  backButton.hidden = currentStep === 1;
  nextButton.hidden = currentStep === steps.length;
  submitButton.hidden = currentStep !== steps.length;

  formError.textContent = "";
}


function selectedValue(name) {
  return document.querySelector(
    `input[name="${name}"]:checked`,
  )?.value;
}


function updateBudgetOptions() {
  const groupSize = Number(
    document.querySelector("#group-size")?.value ?? 1,
  );
  const experience = selectedValue("experience");
  const groupMode = groupSize >= 6 || experience === "team_connection";
  const individual = document.querySelector("#individual-budget-options");
  const group = document.querySelector("#group-budget-options");

  individual.hidden = groupMode;
  group.hidden = !groupMode;

  individual.querySelectorAll('input[name="budget"]').forEach((input) => {
    input.disabled = groupMode;
    if (groupMode) input.checked = false;
  });
  group.querySelectorAll('input[name="budget"]').forEach((input) => {
    input.disabled = !groupMode;
    if (!groupMode) input.checked = false;
  });

  const durationDays = Number(
    document.querySelector("#duration-days")?.value ?? 1,
  );
  const guidance = document.querySelector(
    "#duration-investment-guidance",
  );
  if (guidance) {
    guidance.hidden = groupMode || durationDays === 1;
    if (durationDays <= 1) {
      guidance.textContent = "";
    } else if (budget > 0 && budget <= 500) {
      guidance.textContent = "Your selected investment aligns with one Express Reset session. Multi-day lodging and retreat services are not included at this level.";
    } else if (budget > 500 && budget < 1800) {
      guidance.textContent = "Your selected investment aligns with one Rapid Reset experience. Multi-day lodging is not included at this level.";
    } else {
      guidance.textContent = `${durationDays} service days call for an immersive level of support. Executive Reset is the personalized multi-day path.`;
    }
  }

  updateEnhancementOptions();
}


function updateEnhancementOptions() {
  const durationDays = Number(
    document.querySelector("#duration-days")?.value ?? 1,
  );
  const budget = Number(selectedValue("budget") ?? 0);
  const enhancementSection = document.querySelector("#enhancement-section");
  const serviceEnhancements = document.querySelector(".service-enhancements");
  const includedNotice = document.querySelector(
    "#included-enhancement-notice",
  );
  const experience = selectedValue("experience");
  // Final package eligibility is known only after the server recommendation.
  // The actionable enhancement cart is rendered on the results page.
  const enhancementEligible = false;

  if (!enhancementSection || !serviceEnhancements || !includedNotice) return;

  enhancementSection.hidden = !enhancementEligible;
  serviceEnhancements.hidden = !enhancementEligible;
  includedNotice.hidden = true;

  if (!enhancementEligible) {
    enhancementSection
      .querySelectorAll('input[name="service_addon"], input[name="upgrade"]')
      .forEach((input) => {
        input.checked = false;
      });
    cartAddonIds = [];
    cartUpgradeIds = [];
    const status = document.querySelector("#enhancement-cart-status");
    if (status) status.textContent = "";
  }
}


function parseLocalDate(value) {
  return new Date(`${value}T12:00:00`);
}


function formatLocalDate(date) {
  return [
    date.getFullYear(),
    String(date.getMonth() + 1).padStart(2, "0"),
    String(date.getDate()).padStart(2, "0"),
  ].join("-");
}


function weekOfMonth(date) {
  return Math.floor((date.getDate() - 1) / 7) + 1;
}


function isAllowedServiceDate(value) {
  const date = parseLocalDate(value);
  const monthWeek = weekOfMonth(date);

  /*
   * JavaScript weekdays:
   * Sunday = 0
   * Monday = 1
   * Tuesday = 2
   * Wednesday = 3
   * Thursday = 4
   * Friday = 5
   * Saturday = 6
   */
  const allowedWeekdays = new Set([
    0,
    2,
    4,
    5,
    6,
  ]);

  const isAllowedWeek = [2, 4].includes(monthWeek);
  const isAllowedWeekday =
    allowedWeekdays.has(date.getDay());

  return isAllowedWeek && isAllowedWeekday;
}


function validateRequestedSchedule() {
  const startDateInput = document.querySelector(
    "#requested-start-date",
  );

  const durationInput = document.querySelector(
    "#duration-days",
  );

  if (!startDateInput || !durationInput) {
    return (
      "The booking fields are unavailable. "
      + "Please refresh the page."
    );
  }

  const startValue = startDateInput.value;
  const durationDays = Number(durationInput.value);

  if (!startValue) {
    startDateInput.focus();
    return "Please select your requested start date.";
  }

  if (
    !Number.isInteger(durationDays)
    || durationDays < 1
    || durationDays > 7
  ) {
    durationInput.focus();

    return (
      "Please select a retreat duration "
      + "between one and seven days."
    );
  }

  const startDate = parseLocalDate(startValue);

  for (
    let offset = 0;
    offset < durationDays;
    offset += 1
  ) {
    const serviceDate = new Date(startDate);

    serviceDate.setDate(
      startDate.getDate() + offset,
    );

    const localValue = formatLocalDate(serviceDate);

    if (!isAllowedServiceDate(localValue)) {
      return (
        "Every retreat date must fall in the second "
        + "or fourth week of the month and be a "
        + "Tuesday, Thursday, Friday, Saturday or "
        + "Sunday. Please choose another start date "
        + "or a shorter retreat."
      );
    }
  }

  return "";
}


function validateCurrentStep() {
  if (currentStep === 1) {
    const nameInput = document.querySelector(
      "#contact-name",
    );

    const groupSizeInput = document.querySelector(
      "#group-size",
    );

    if (!nameInput.value.trim()) {
      nameInput.focus();
      return "Please enter your name.";
    }

    const email = document.querySelector("#contact-email");
    const phone = document.querySelector("#contact-phone");
    const referral = document.querySelector("#referral-source");
    if (!email.value.trim() || !email.checkValidity()) {
      email.focus();
      return "Please enter a valid email address.";
    }
    if (phone.value.trim().length < 7) {
      phone.focus();
      return "Please enter your phone number.";
    }
    if (!referral.value) {
      referral.focus();
      return "Please tell us how you heard about Paradise Park.";
    }

    if (Number(groupSizeInput.value) < 1) {
      groupSizeInput.focus();
      return "Please enter at least one guest.";
    }
  }

  if (currentStep === 2) {
    const scheduleError =
      validateRequestedSchedule();

    if (scheduleError) {
      return scheduleError;
    }

    if (!selectedValue("experience")) {
      return (
        "Please choose the type of experience "
        + "you are considering."
      );
    }

    if (
      selectedValue("experience") === "team_connection"
      && Number(document.querySelector("#group-size").value) < 6
    ) {
      document.querySelector("#group-size").focus();
      return "Paradise Park group retreats begin with a minimum of 6 guests.";
    }

  }

  if (currentStep === 3) {
    const priorities = document.querySelectorAll(
      'input[name="priority"]:checked',
    );

    if (priorities.length === 0) {
      return (
        "Choose at least one priority "
        + "for your experience."
      );
    }

    if (!selectedValue("budget")) {
      return (
        "After considering the change you want, please choose the level "
        + "of investment that feels aligned."
      );
    }
  }

  if (currentStep === 4) {
    const selectedPrivateEnhancements = getCheckedValues(
      "service_addon",
    ).filter((addonId) => addonId !== "farm_to_table_individual");

    if (selectedPrivateEnhancements.length > 1) {
      return (
        "Choose one private one-on-one enhancement for Express or Rapid "
        + "Reset. Executive and Peak experiences curate two private services per day."
      );
    }
  }

  return "";
}


function validateCompleteForm() {
  const originalStep = currentStep;

  for (
    let stepNumber = 1;
    stepNumber <= steps.length;
    stepNumber += 1
  ) {
    currentStep = stepNumber;

    const error = validateCurrentStep();

    if (error) {
      showStep(stepNumber);
      return error;
    }
  }

  currentStep = originalStep;

  return "";
}


function getCheckedValues(name) {
  return [
    ...document.querySelectorAll(
      `input[name="${name}"]:checked`,
    ),
  ].map((input) => input.value);
}


function buildPayload() {
  const priorityInputs = [
    ...document.querySelectorAll(
      'input[name="priority"]:checked',
    ),
  ];

  const experience = selectedValue("experience");
  const priorityCodes = priorityInputs.map(
    (input) => input.value,
  );

  const selectedUpgrades = [...cartUpgradeIds];

  return {
    assessment: {
      assessment_mode: "retreat_planner",
      contact_name: document
        .querySelector("#contact-name")
        .value
        .trim(),
      contact_email: document.querySelector("#contact-email").value.trim(),
      contact_phone: document.querySelector("#contact-phone").value.trim(),
      referral_source: document.querySelector("#referral-source").value,
      instagram_handle: document.querySelector("#instagram-handle").value.trim() || null,
      organization_name:
        document
          .querySelector("#organization-name")
          .value
          .trim() || null,
      group_size: Number(
        document.querySelector("#group-size").value,
      ),
      booking_mode: experience === "team_connection"
        ? "team_retreat"
        : "personal_reset",
      budget: selectedValue("budget"),
      preferred_package_id: selectedAlternativePackageId,
      goals: [
        ...new Set([
          experience,
          ...priorityCodes,
        ]),
      ],
      signals: priorityInputs.map((input) => ({
        code: input.value,
        source: "explicit",
        guest_statement: input.dataset.statement,
      })),
      selected_addon_ids: [...cartAddonIds],
      consent: {
        deliver_report: document.querySelector(
          "#deliver-report",
        ).checked,
        marketing: document.querySelector(
          "#marketing-consent",
        ).checked,
      },
    },
    requested_start_date: document.querySelector(
      "#requested-start-date",
    ).value,
    duration_days: Number(
      document.querySelector(
        "#duration-days",
      ).value,
    ),
    selected_upgrades: selectedUpgrades,
    additional_text: document
      .querySelector("#additional-text")
      .value
      .trim(),
    lead_id: leadId,
  };
}


async function captureLeadProgress() {
  const payload = {
    lead_id: leadId,
    name: document.querySelector("#contact-name").value.trim(),
    email: document.querySelector("#contact-email").value.trim(),
    phone: document.querySelector("#contact-phone").value.trim(),
    referral_source: document.querySelector("#referral-source").value,
    instagram_handle: document.querySelector("#instagram-handle").value.trim() || null,
  };
  try {
    await fetch("/v1/leads/capture", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload),
      keepalive: true,
    });
  } catch (error) {
    console.warn("Lead progress could not be preserved.", error);
  }
}


function escapeHtml(value) {
  const span = document.createElement("span");

  span.textContent = String(value ?? "");

  return span.innerHTML;
}


function readableStatus(value) {
  const labels = {
    proposed_included:
      "Included in your proposed experience",
    included:
      "Included in your proposed experience",
    paid_upgrade:
      "Optional enhancement",
    custom_quote:
      "Ambassador-confirmed option",
    human_review:
      "Ambassador confirmation",
  };

  return (
    labels[value]
    ?? String(value).replaceAll("_", " ")
  );
}


function readableUpgrade(value) {
  const labels = {
    pamper_collection: "Pamper Collection",
    soil_to_soul_products:
      "Soil to Soul products",
  };

  return (
    labels[value]
    ?? String(value).replaceAll("_", " ")
  );
}


function readableExperience(goals) {
  const labels = {
    deep_rest: "Personal reset",
    team_connection: "Group or team retreat",
  };

  const selectedGoal = (goals ?? []).find(
    (goal) => Object.hasOwn(labels, goal),
  );

  return labels[selectedGoal] ?? "Paradise Park wellness experience";
}


function readableBudget(value, groupSize) {
  const amount = Number(value);

  if (groupSize >= 6) {
    if (amount >= 40000) return "$40,000+";
    if (amount >= 10000) return "$10,000–$39,999";
    if (amount >= 5000) return "$5,000–$9,999";
    return "$2,200–$4,999";
  }

  if (amount >= 9987) return "$9,987 Peak Performance Pivot";
  if (amount >= 5000) return "$5,000–$9,986";
  if (amount >= 1801) return "$1,801–$4,999";
  if (amount >= 501) return "$501–$1,800";
  return "Under $500";
}


function validCheckoutUrl(packageId) {
  const value = checkoutLinks[packageId];

  if (typeof value !== "string") {
    return "";
  }

  const trimmed = value.trim();

  if (!trimmed.startsWith("https://")) {
    return "";
  }

  return trimmed;
}


function formatApiError(errorBody, statusCode) {
  if (
    errorBody
    && Array.isArray(errorBody.detail)
  ) {
    const messages = errorBody.detail.map(
      (item) => item.msg,
    );

    return messages.join(" ");
  }

  if (
    errorBody
    && typeof errorBody.detail === "string"
  ) {
    return errorBody.detail;
  }

  if (statusCode === 422) {
    return (
      "Please review your assessment and booking "
      + "details before trying again."
    );
  }

  return (
    "We could not prepare your recommendation. "
    + "Please try again."
  );
}


function renderHumanReview(result) {
  latestActions = result.actions ?? {};
  latestConciergeTraceId = result.trace_id ?? latestConciergeTraceId;
  const booking = result.booking;

  reportContent.innerHTML = `
    <div class="review-box">
      <p class="eyebrow">
        Wellness Ambassador support
      </p>

      <h2>
        Thank you for sharing your preferences
      </h2>

      <p>
        A Paradise Park Wellness Ambassador will
        thoughtfully review what you shared and
        contact you to confirm the most appropriate
        experience, agenda and secure purchase option.
      </p>

      <p>
        Your requested start date is
        <strong>
          ${escapeHtml(
            booking.requested_start_date,
          )}
        </strong>
        for
        <strong>
          ${escapeHtml(booking.duration_days)}
          service day(s)
        </strong>.
      </p>
    </div>

    <p class="disclaimer">
      Reference:
      ${escapeHtml(result.trace_id)}
    </p>
  `;
}


function formatMoney(value) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(Number(value));
}


async function sendConversionFeedback({
  readiness,
  barrier = null,
  helpfulness = null,
  additionalComment = "",
} = {}) {
  const recommendation = latestResult?.recommendation;
  if (!latestPayload || !recommendation || !readiness) return false;

  const response = await fetch("/v1/feedback", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    keepalive: true,
    body: JSON.stringify({
      lead_id: latestPayload.lead_id,
      trace_id: latestResult.trace_id,
      primary_package_id: recommendation.package.package_id,
      secondary_package_id: recommendation.alternatives?.[0]?.package_id ?? null,
      investment_target: latestPayload.assessment.budget,
      quoted_total: recommendation.pricing_breakdown?.order_total ?? null,
      group_size: latestPayload.assessment.group_size,
      readiness,
      barrier,
      helpfulness,
      additional_comment: additionalComment,
    }),
  });
  return response.ok;
}


async function beginCheckout(paymentOption, button) {
  if (!latestPayload) {
    formError.textContent = "Please start the assessment again.";
    return;
  }

  const policyAcceptance = document.querySelector(
    "#non-refundable-policy-acceptance",
  );
  if (!policyAcceptance?.checked) {
    window.alert(
      "Please acknowledge the non-refundable payment policy before checkout.",
    );
    policyAcceptance?.focus();
    return;
  }

  const originalLabel = button.textContent;
  void sendConversionFeedback({readiness: "ready_to_checkout"});
  button.disabled = true;
  button.textContent = "Preparing secure checkout…";

  try {
    const response = await fetch("/v1/checkout", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        ...latestPayload,
        payment_option: paymentOption,
        non_refundable_policy_accepted: true,
      }),
    });
    const body = await response.json();
    if (!response.ok) {
      throw new Error(formatApiError(body, response.status));
    }
    window.location.assign(body.checkout_url);
  } catch (error) {
    button.disabled = false;
    button.textContent = originalLabel;
    window.alert(
      error instanceof Error
        ? error.message
        : "Secure checkout is temporarily unavailable.",
    );
  }
}


async function selectAlternativePackage(packageId, button) {
  if (!latestPayload) {
    window.alert("Please start the assessment again.");
    return;
  }

  const nextPayload = JSON.parse(JSON.stringify(latestPayload));
  nextPayload.assessment.preferred_package_id = packageId;

  if (["express_reset", "rapid_reset"].includes(packageId)) {
    nextPayload.duration_days = 1;
  }

  if (
    packageId === "peak_performance_pivot"
    && nextPayload.duration_days < 3
  ) {
    window.alert(
      "Peak Performance Pivot requires three approved service days. "
      + "Please start over and select a three-day experience.",
    );
    return;
  }

  const originalLabel = button.textContent;
  button.disabled = true;
  button.textContent = "Building this option…";

  try {
    const response = await fetch("/v1/recommendations", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(nextPayload),
    });
    const body = await response.json();
    if (!response.ok) {
      throw new Error(formatApiError(body, response.status));
    }

    latestPayload = nextPayload;
    selectedAlternativePackageId = packageId;
    renderRecommendation(body);
    reportCard.scrollIntoView({behavior: "smooth", block: "start"});
  } catch (error) {
    button.disabled = false;
    button.textContent = originalLabel;
    window.alert(
      error instanceof Error
        ? error.message
        : "We could not rebuild this option. Please try again.",
    );
  }
}


function renderRecommendation(result) {
  latestResult = result;
  const recommendation = result.recommendation;
  const packageInfo = recommendation.package;
  const booking = result.booking;
  const actions = result.actions ?? {};
  latestActions = actions;
  latestConciergeTraceId = result.trace_id ?? latestConciergeTraceId;
  const assessment = latestPayload?.assessment ?? {};

  const reflections =
    (recommendation.fit_signals ?? recommendation.reflected_statements)
      .map(
        (statement) => `
          <li>${escapeHtml(statement)}</li>
        `,
      )
      .join("");

  const agendaDays = recommendation.agenda_items.reduce((days, item) => {
    const day = Number(item.day || 1);
    days[day] = days[day] ?? [];
    days[day].push(item);
    return days;
  }, {});
  const agenda = Object.entries(agendaDays)
    .sort(([dayA], [dayB]) => Number(dayA) - Number(dayB))
    .map(([day, items]) => `
      <section class="itinerary-day" aria-labelledby="itinerary-day-${escapeHtml(day)}">
        <div class="day-heading">
          <p class="eyebrow">Your proposed itinerary</p>
          <h3 id="itinerary-day-${escapeHtml(day)}">Day ${escapeHtml(day)}</h3>
        </div>
        <div class="agenda-grid">
        ${items.map((item) => `
        <article class="agenda-item">
          <div class="agenda-topline">
            <div>
              <span class="agenda-number">
                Day ${escapeHtml(item.day || 1)} · ${escapeHtml(
                  item.service_class === "one_on_one" ? "Private experience" : "Guided experience",
                )}
              </span>

              <h3>
                ${escapeHtml(item.name)}
              </h3>

              ${item.quantity > 1 ? `
                <p class="quantity-copy">
                  ${escapeHtml(item.quantity)} sessions across the experience
                </p>
              ` : ""}
            </div>

            <span class="status-badge">
              ${escapeHtml(
                readableStatus(
                  item.commercial_status,
                ),
              )}
            </span>
          </div>

          <p>
            ${escapeHtml(
              item.guest_description,
            )}
          </p>

          <p>
            <strong>Why you may enjoy it:</strong>
            ${escapeHtml(item.why_helpful)}
          </p>

          <p>
            <strong>Pricing:</strong>
            ${escapeHtml(item.price_statement)}
          </p>
        </article>
        `).join("")}
        </div>
      </section>
    `).join("");

  const insights = (recommendation.wellness_insights ?? [])
    .map((insight) => `
      <article class="agenda-item insight-card">
        <p class="eyebrow">
          ${escapeHtml(insight.pathway.replaceAll("_", " "))}
        </p>
        <h3>${escapeHtml(insight.title)}</h3>
        <p>${escapeHtml(insight.observation)}</p>
        <p>
          <strong>A gentle practice to try:</strong>
          ${escapeHtml(insight.practice_tip)}
        </p>
      </article>
    `)
    .join("");

  const paymentChoices = (recommendation.payment_choices ?? [])
    .map((choice) => `
      <article class="agenda-item payment-card">
        <h3>${escapeHtml(choice.label)}</h3>
        <p class="price-line">
          ${escapeHtml(formatMoney(choice.amount_due_now))} due now
        </p>
        <p>
          Order total: ${escapeHtml(formatMoney(choice.order_total))}
          ${Number(choice.remaining_balance) > 0
            ? ` · Remaining balance: ${escapeHtml(formatMoney(choice.remaining_balance))}`
            : ""}
        </p>
        <p>${escapeHtml(choice.description)}</p>
        <button
          class="button primary payment-button"
          type="button"
          data-payment-option="${escapeHtml(choice.payment_option)}"
        >
          Continue to secure Square checkout
        </button>
      </article>
    `)
    .join("");

  const alternatives = (recommendation.alternatives ?? [])
    .map((option) => {
      let optionAction = "";

      if (option.qualification_note) {
        optionAction = `
          <a class="button secondary alternative-action" target="_blank" rel="noopener noreferrer" href="${escapeHtml(actions.questions_url || "https://www.paradiseislife.biz/contact-8")}">
            Ask about this option
          </a>
        `;
      } else if (
        option.package_id === "express_reset"
        && actions.express_calendar_url
      ) {
        optionAction = `
          <a class="button secondary alternative-action" target="_blank" rel="noopener noreferrer" href="${escapeHtml(actions.express_calendar_url)}">
            View Express wellness sessions
          </a>
        `;
      } else {
        optionAction = `
          <button class="button secondary alternative-action alternative-select-button" type="button" data-package-id="${escapeHtml(option.package_id)}">
            Build this option
          </button>
        `;
      }

      return `
      <article class="agenda-item alternative-card">
        <p class="eyebrow">Another valid path</p>
        <h3>${escapeHtml(option.name)}</h3>
        <p class="price-line">${escapeHtml(option.price_statement)}</p>
        <p>${escapeHtml(option.why_consider)}</p>
        ${option.qualification_note ? `
          <p><strong>Please note:</strong> ${escapeHtml(option.qualification_note)}</p>
        ` : ""}
        <p>${escapeHtml(option.action)}</p>
        ${optionAction}
      </article>
    `;
    })
    .join("");
  const secondaryHeading = ["express_reset", "rapid_reset"].includes(
    packageInfo.package_id,
  )
    ? "Optional deeper level"
    : "A more flexible path";

  const selectedUpgradeCopy =
    booking.selected_upgrades.length > 0
      ? booking.selected_upgrades
        .map(readableUpgrade)
        .join(", ")
      : "No product enhancements selected";

  const coreExperiences = (recommendation.core_experiences ?? [])
    .map((item) => `
      <article class="core-experience">
        <span class="gold-mark" aria-hidden="true">✦</span>
        <div><h4>${escapeHtml(item.name)}</h4><p>${escapeHtml(item.description)}</p></div>
      </article>
    `).join("");

  const pricing = recommendation.pricing_breakdown;
  const pricingBreakdown = pricing ? `
    <section class="pricing-ledger" aria-labelledby="pricing-heading">
      <p class="eyebrow">Transparent investment</p>
      <h3 id="pricing-heading">Your program calculation</h3>
      <div><span>Package base</span><strong>${escapeHtml(formatMoney(pricing.package_base_subtotal))}</strong></div>
      ${Number(pricing.additional_service_days) > 0 ? `
        <div><span>${escapeHtml(pricing.additional_service_days)} additional day(s) × ${escapeHtml(pricing.guest_count)} guest(s) × ${escapeHtml(formatMoney(pricing.additional_day_rate_per_person))}</span><strong>${escapeHtml(formatMoney(pricing.extended_program_subtotal))}</strong></div>
      ` : ""}
      <div class="pricing-total"><span>Program total</span><strong>${escapeHtml(formatMoney(pricing.order_total))}</strong></div>
    </section>
  ` : "";

  const canAddEnhancements = packageInfo.package_id === "rapid_reset";
  const enhancementCart = canAddEnhancements ? `
    <section class="result-enhancement-cart" aria-labelledby="result-enhancement-heading">
      <p class="eyebrow">Optional enhancements</p>
      <h3 id="result-enhancement-heading">Personalize this ${escapeHtml(packageInfo.name)}</h3>
      <p>These upgrades are not included in the package base. Choose what you want, then add it to the cart to recalculate your recommendation before checkout.</p>
      <div class="choice-grid two-column">
        ${[
          ["farm_to_table_individual", "Farm-to-Table Vegan Culinary Experience · $295"],
          ["assisted_stretch", "Assisted Deep Stretch · $175"],
          ["somatic_release", "Somatic Release · $275"],
          ["womb_wellness", "Womb Wellness · $225"],
        ].map(([id, label]) => `
          <label class="choice-card">
            <input type="checkbox" name="result_service_addon" value="${id}" ${cartAddonIds.includes(id) ? "checked" : ""} />
            <span class="choice-title">${label}</span>
          </label>
        `).join("")}
      </div>
      <button class="button secondary report-add-enhancements" type="button">Add selected enhancements to cart</button>
      <p class="enhancement-cart-status" role="status">${cartAddonIds.length ? `${cartAddonIds.length} enhancement selection${cartAddonIds.length === 1 ? "" : "s"} currently in your cart.` : "No paid enhancements are currently in your cart."}</p>
    </section>
  ` : "";

  const isExpress = packageInfo.checkout_mode === "express_calendar";
  const expressAction = isExpress && actions.express_calendar_url
    ? `
      <a class="button primary express-checkout-action" target="_blank" rel="noopener noreferrer" href="${escapeHtml(actions.express_calendar_url)}">
        View Express wellness sessions and dates
      </a>
    `
    : "";
  const consultAction = actions.consultation_url
    ? `
      <a class="button secondary" target="_blank" rel="noopener noreferrer" href="${escapeHtml(actions.consultation_url)}">
        Speak with a Paradise Park Wellness Ambassador
      </a>
    `
    : "";
  // An unpriced product never blocks your retreat checkout.
  const pamperSelected = booking.selected_upgrades.includes("pamper_collection");
  const productAction = pamperSelected ? `
      <div class="product-action selected-product">
        <p><strong>You selected the Pamper Collection.</strong> It is purchased separately and is not included in the retreat total.</p>
        <a class="button product" target="_blank" rel="noopener noreferrer" href="https://square.link/u/FGnBH1yz">
          Purchase your Pamper Collection
        </a>
      </div>
    ` : `
      <div class="product-action">
        <p>
          Add Paradise Park natural skin care, Pamper Collection or Soil to
          Soul products without delaying your retreat reservation.
        </p>
        <a class="button secondary" target="_blank" rel="noopener noreferrer" href="${escapeHtml(actions.product_shop_url)}">
          Explore natural products
        </a>
      </div>
    `;
  const questionsAction = `
    <a class="button secondary" target="_blank" rel="noopener noreferrer" href="${escapeHtml(actions.questions_url || "https://www.paradiseislife.biz/contact-8")}">
      Questions? Chat with a Wellness Ambassador
    </a>
  `;

  const ambassadorChatLink = document.querySelector("#ambassador-chat-link");
  if (ambassadorChatLink && actions.questions_url) {
    ambassadorChatLink.href = actions.questions_url;
  }

  reportContent.innerHTML = `
    <div class="report-hero">
      <p class="eyebrow">
        Your Paradise Park recommendation
      </p>

      <h2>
        ${escapeHtml(packageInfo.name)}
      </h2>

      <p class="price-line">
        ${escapeHtml(
          packageInfo.price_statement,
        )}
      </p>

      <p>
        ${escapeHtml(recommendation.personalized_narrative || packageInfo.why_it_fits)}
      </p>

      <p><strong>Level of care:</strong> ${escapeHtml(packageInfo.care_level)}</p>
      <p><strong>Experience length:</strong> ${escapeHtml(packageInfo.duration_statement)}</p>
      <p><strong>What is included:</strong> ${escapeHtml(packageInfo.included_summary)}</p>
      <p><strong>Hospitality:</strong> ${escapeHtml(packageInfo.hospitality_summary)}</p>

      <p class="fit-heading"><strong>Why this experience fits you</strong></p>
      <ul class="reflection-list fit-signals">
        ${reflections}
      </ul>
    </div>

    ${alternatives ? `
      <section class="secondary-recommendations">
        <p class="eyebrow">Your next best option</p>
        <h3>${secondaryHeading}</h3>
        <p>This option is shown directly beside your primary recommendation so
        you can compare the additional depth and investment before deciding.</p>
        <div class="agenda-grid">${alternatives}</div>
      </section>
    ` : ""}

    <section class="selection-recap" aria-labelledby="selection-recap-heading">
      <p class="eyebrow">Your selections</p>
      <h3 id="selection-recap-heading">Your retreat at a glance</h3>
      <div class="recap-grid">
        <div><span>Guests</span><strong>${escapeHtml(booking.group_size)}</strong></div>
        <div><span>Experience</span><strong>${escapeHtml(readableExperience(assessment.goals))}</strong></div>
        <div><span>Duration</span><strong>${escapeHtml(booking.duration_days)} service day(s)</strong></div>
        <div><span>Requested dates</span><strong>${escapeHtml(booking.requested_start_date)} through ${escapeHtml(booking.requested_end_date)}</strong></div>
        <div><span>Investment comfort</span><strong>${escapeHtml(readableBudget(assessment.budget, booking.group_size))}</strong></div>
        <div><span>Enhancements</span><strong>${escapeHtml(selectedUpgradeCopy)}</strong></div>
      </div>
      <p class="recap-note">
        Experiences are offered during the second and fourth weeks on approved
        service days. Your Wellness Ambassador will confirm the final agenda
        and availability after purchase.
      </p>
    </section>

    <h3>Your proposed experience</h3>

    ${coreExperiences ? `
      <section class="signature-inclusions">
        <p class="eyebrow">Included beyond your five daily services</p>
        <h3>Paradise Park signature core experiences</h3>
        <div class="core-grid">${coreExperiences}</div>
      </section>
    ` : ""}

    ${agenda}

    ${pricingBreakdown}

    ${enhancementCart}

    <p class="price-line">
      ${escapeHtml(
        recommendation.price_summary,
      )}
    </p>

    <div class="cta-box">
      <h3>Your next step</h3>

      <p>
        ${escapeHtml(
          recommendation.call_to_action,
        )}
      </p>

      ${!isExpress ? `
        <label class="payment-policy-acceptance">
          <input id="non-refundable-policy-acceptance" type="checkbox" />
          <span>I understand that Paradise Park payments are non-refundable and
          that any remaining balance is due 14 days before my event date.</span>
        </label>
      ` : ""}

      ${isExpress ? expressAction : paymentChoices}

      <p class="confirmation-copy">
        Within 24–48 hours after checkout, you will receive a digital welcome
        package. A Paradise Park Wellness Ambassador will then confirm
        scheduling and finalize your actual agenda.
        Your confirmed agenda will remain aligned
        with the package you purchased, your stated
        priorities and service availability.
      </p>
    </div>

    <section class="conversion-feedback" aria-labelledby="conversion-feedback-heading">
      <p class="eyebrow">One quick question</p>
      <h3 id="conversion-feedback-heading">Are you ready to reserve this experience?</h3>
      <p>Your answer helps us understand whether the timing, information and services feel right.</p>
      <form id="conversion-feedback-form">
        <div class="feedback-options">
          <label><input type="radio" name="checkout_readiness" value="ready_to_checkout" required /> Yes, I’m ready to checkout</label>
          <label><input type="radio" name="checkout_readiness" value="interested_not_ready" /> I’m interested, but not ready yet</label>
          <label><input type="radio" name="checkout_readiness" value="recommendation_not_right" /> This recommendation is not right for me</label>
        </div>
        <div id="feedback-barrier-wrap" hidden>
          <label for="feedback-barrier"><strong>What is the main reason?</strong></label>
          <select id="feedback-barrier" name="feedback_barrier">
            <option value="">Choose one</option>
            <option value="needs_more_information">I need more information</option>
            <option value="needs_ambassador">I want to speak with a Wellness Ambassador</option>
            <option value="timing_not_right">The timing is not right</option>
            <option value="investment_mismatch">The investment does not fit right now</option>
            <option value="services_mismatch">These are not the right services</option>
            <option value="coordinating_guests">I need to coordinate with other guests</option>
            <option value="comparing_options">I am comparing my options</option>
            <option value="technical_problem">I had a technical problem</option>
            <option value="other">Another reason</option>
          </select>
        </div>
        <fieldset class="feedback-helpfulness">
          <legend>Was this recommendation helpful?</legend>
          <label><input type="radio" name="recommendation_helpfulness" value="very_helpful" /> Very helpful</label>
          <label><input type="radio" name="recommendation_helpfulness" value="somewhat_helpful" /> Somewhat helpful</label>
          <label><input type="radio" name="recommendation_helpfulness" value="not_helpful" /> Not helpful</label>
        </fieldset>
        <label for="feedback-comment"><strong>Anything else you would like us to know?</strong></label>
        <textarea id="feedback-comment" maxlength="1000" rows="3" placeholder="Optional comment"></textarea>
        <button class="button secondary" type="submit">Share my response</button>
        <p id="conversion-feedback-status" class="feedback-status" role="status"></p>
      </form>
    </section>

    <section class="wellness-reflection">
      <p class="eyebrow">A complementary reflection</p>
      <h3>Your (W)holistic living reflection</h3>
      <p>Paradise Park's Savauna-founded approach considers internal work,
      external care and the restorative influence of environment.</p>
      <div class="agenda-grid">${insights}</div>
    </section>

    <section class="post-checkout-actions">
      <h3>Additional Paradise Park paths</h3>
      <div class="supplemental-actions">
        ${productAction}
        ${consultAction}
        ${questionsAction}
      </div>
    </section>

    <p class="disclaimer">
      ${escapeHtml(
        recommendation.wellness_disclaimer,
      )}
      <br />
      Reference:
      ${escapeHtml(result.trace_id)}
    </p>
  `;

  reportContent.querySelectorAll(".payment-button").forEach((button) => {
    button.addEventListener("click", () => {
      beginCheckout(button.dataset.paymentOption, button);
    });
  });

  reportContent.querySelector(".express-checkout-action")?.addEventListener(
    "click",
    () => {
      void sendConversionFeedback({readiness: "ready_to_checkout"});
    },
  );

  const feedbackForm = reportContent.querySelector("#conversion-feedback-form");
  const feedbackBarrierWrap = reportContent.querySelector(
    "#feedback-barrier-wrap",
  );
  const feedbackBarrier = reportContent.querySelector("#feedback-barrier");
  feedbackForm?.querySelectorAll('input[name="checkout_readiness"]')
    .forEach((input) => {
      input.addEventListener("change", () => {
        const needsReason = input.checked && input.value !== "ready_to_checkout";
        feedbackBarrierWrap.hidden = !needsReason;
        feedbackBarrier.required = needsReason;
        if (!needsReason) feedbackBarrier.value = "";
      });
    });
  feedbackForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const submitter = event.submitter;
    const status = reportContent.querySelector("#conversion-feedback-status");
    const readiness = feedbackForm.querySelector(
      'input[name="checkout_readiness"]:checked',
    )?.value;
    if (!readiness) return;

    submitter.disabled = true;
    status.textContent = "Saving your response…";
    try {
      const saved = await sendConversionFeedback({
        readiness,
        barrier: feedbackBarrier.value || null,
        helpfulness: feedbackForm.querySelector(
          'input[name="recommendation_helpfulness"]:checked',
        )?.value ?? null,
        additionalComment: feedbackForm.querySelector("#feedback-comment").value,
      });
      if (!saved) throw new Error("Feedback was not accepted.");
      status.textContent = "Thank you—your response has been saved.";
      feedbackForm.querySelectorAll("input, select, textarea, button")
        .forEach((control) => { control.disabled = true; });
    } catch (error) {
      submitter.disabled = false;
      status.textContent = "We could not save that response. Please try again.";
    }
  });

  reportContent.querySelector(".report-add-enhancements")?.addEventListener(
    "click",
    async (event) => {
      const button = event.currentTarget;
      cartAddonIds = [
        ...reportContent.querySelectorAll('input[name="result_service_addon"]:checked'),
      ].map((input) => input.value);
      latestPayload.assessment.selected_addon_ids = [...cartAddonIds];
      button.disabled = true;
      button.textContent = "Recalculating your cart…";
      try {
        const response = await fetch("/v1/recommendations", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify(latestPayload),
        });
        const body = await response.json();
        if (!response.ok) throw new Error(formatApiError(body, response.status));
        renderRecommendation(body);
      } catch (error) {
        button.disabled = false;
        button.textContent = "Add selected enhancements to cart";
        window.alert(error instanceof Error ? error.message : "The cart could not be recalculated.");
      }
    },
  );

  reportContent.querySelectorAll(".alternative-select-button").forEach((button) => {
    button.addEventListener("click", () => {
      selectAlternativePackage(button.dataset.packageId, button);
    });
  });
}


function conciergeActionMarkup(action, requiresAmbassador) {
  const ambassadorUrl = latestActions.questions_url
    || document.querySelector("#ambassador-chat-link")?.href
    || "https://www.paradiseislife.biz";

  if (requiresAmbassador || action === "contact_ambassador") {
    return `
      <a class="button secondary" target="_blank" rel="noopener noreferrer"
        href="${escapeHtml(ambassadorUrl)}">
        Connect with a Wellness Ambassador
      </a>
    `;
  }

  if (action === "view_recommendation") {
    return reportCard.hidden
      ? `<button class="button secondary" type="button" data-concierge-action="assessment">Plan my experience</button>`
      : `<button class="button secondary" type="button" data-concierge-action="report">View my recommendation</button>`;
  }

  if (action === "compare_packages") {
    return reportCard.hidden
      ? `<button class="button secondary" type="button" data-concierge-action="assessment">Compare options through the assessment</button>`
      : `<button class="button secondary" type="button" data-concierge-action="report">Review my package options</button>`;
  }

  if (action === "open_express_calendar") {
    const expressUrl = latestActions.express_calendar_url || ambassadorUrl;
    return `
      <a class="button secondary" target="_blank" rel="noopener noreferrer"
        href="${escapeHtml(expressUrl)}">
        View Express wellness sessions
      </a>
    `;
  }

  if (action === "view_products") {
    const shopUrl = latestActions.product_shop_url
      || "https://www.paradiseislife.biz";
    return `
      <a class="button secondary" target="_blank" rel="noopener noreferrer"
        href="${escapeHtml(shopUrl)}">
        Explore Paradise Park products
      </a>
    `;
  }

  return "";
}


function attachConciergeActionHandlers() {
  conciergeAction
    .querySelectorAll("[data-concierge-action]")
    .forEach((button) => {
      button.addEventListener("click", () => {
        const target = button.dataset.conciergeAction;

        if (target === "report" && !reportCard.hidden) {
          reportCard.scrollIntoView({behavior: "smooth", block: "start"});
          return;
        }

        assessmentCard.hidden = false;
        assessmentCard.scrollIntoView({behavior: "smooth", block: "start"});
      });
    });
}


function updateConciergeCharacterCount() {
  const length = conciergeQuestion?.value.length ?? 0;
  conciergeCharacterCount.textContent = `${length} / 600`;
}


function fillConciergeQuestion(question) {
  conciergeQuestion.value = question.slice(0, 600);
  updateConciergeCharacterCount();
  conciergeQuestion.focus();
}


function renderConciergeResponse(result) {
  const isAnswered = result.status === "answered";

  latestConciergeTraceId = result.trace_id || latestConciergeTraceId;
  conciergeAnswer.hidden = false;
  conciergeAnswer.classList.remove("is-loading");
  conciergeStatus.textContent = isAnswered
    ? "Answered from approved information"
    : "Wellness Ambassador recommended";
  conciergeAnswerCopy.textContent = result.answer;

  const suggestedQuestions = Array.isArray(result.suggested_questions)
    ? result.suggested_questions.slice(0, 3)
    : [];

  conciergeFollowupButtons.innerHTML = suggestedQuestions
    .map(
      (question) => `
        <button class="question-chip concierge-followup" type="button"
          data-question="${escapeHtml(question)}">
          ${escapeHtml(question)}
        </button>
      `,
    )
    .join("");
  conciergeFollowups.hidden = suggestedQuestions.length === 0;

  conciergeFollowupButtons
    .querySelectorAll(".concierge-followup")
    .forEach((button) => {
      button.addEventListener("click", () => {
        fillConciergeQuestion(button.dataset.question || "");
      });
    });

  const sourceIds = Array.isArray(result.source_ids)
    ? result.source_ids
    : [];

  conciergeSourceList.innerHTML = sourceIds
    .map((sourceId) => `<li>${escapeHtml(sourceId)}</li>`)
    .join("");
  conciergeSources.hidden = sourceIds.length === 0;

  conciergeAction.innerHTML = conciergeActionMarkup(
    result.recommended_action,
    Boolean(result.requires_ambassador),
  );
  attachConciergeActionHandlers();

  conciergeDisclaimer.hidden = !result.wellness_disclaimer_required;
  conciergeTrace.textContent = result.trace_id
    ? `Reference: ${result.trace_id}`
    : "";
}


async function askConcierge(question) {
  conciergeError.textContent = "";
  conciergeSubmit.disabled = true;
  conciergeSubmit.textContent = "Preparing an answer…";
  conciergeAnswer.hidden = false;
  conciergeAnswer.classList.add("is-loading");
  conciergeStatus.textContent = "Reviewing approved information";
  conciergeAnswerCopy.textContent = "The concierge is preparing a grounded response.";
  conciergeFollowups.hidden = true;
  conciergeAction.innerHTML = "";
  conciergeSources.hidden = true;
  conciergeDisclaimer.hidden = true;
  conciergeTrace.textContent = "";

  try {
    const payload = {question, lead_id: latestPayload?.lead_id ?? leadId};

    if (latestConciergeTraceId) {
      payload.trace_id = latestConciergeTraceId;
    }

    const response = await fetch("/v1/concierge/answer", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload),
    });

    const body = await response.json();

    if (!response.ok) {
      throw new Error(formatApiError(body, response.status));
    }

    renderConciergeResponse(body);
  } catch (error) {
    console.error(error);
    conciergeAnswer.hidden = true;
    conciergeAnswer.classList.remove("is-loading");
    conciergeError.textContent = error instanceof Error
      ? error.message
      : "The concierge is temporarily unavailable. Please try again.";
  } finally {
    conciergeSubmit.disabled = false;
    conciergeSubmit.textContent = "Ask the concierge";
  }
}


nextButton.addEventListener("click", async () => {
  const error = validateCurrentStep();

  if (error) {
    formError.textContent = error;
    return;
  }

  if (currentStep === 1) {
    await captureLeadProgress();
  }

  showStep(
    Math.min(currentStep + 1, steps.length),
  );
});


backButton.addEventListener("click", () => {
  showStep(
    Math.max(currentStep - 1, 1),
  );
});


form.addEventListener("submit", async (event) => {
  event.preventDefault();

  formError.textContent = "";

  const validationError = validateCompleteForm();

  if (validationError) {
    formError.textContent = validationError;
    return;
  }

  submitButton.disabled = true;
  submitButton.textContent =
    "Preparing your recommendation…";

  try {
    selectedAlternativePackageId = null;
    latestPayload = buildPayload();

    const response = await fetch(
      "/v1/recommendations",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(latestPayload),
      },
    );

    const responseBody = await response.json();

    if (!response.ok) {
      throw new Error(
        formatApiError(
          responseBody,
          response.status,
        ),
      );
    }

    if (responseBody.status === "human_review") {
      renderHumanReview(responseBody);
    } else {
      renderRecommendation(responseBody);
    }

    assessmentCard.hidden = true;
    reportCard.hidden = false;

    reportCard.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
  } catch (error) {
    console.error(error);

    formError.textContent =
      error instanceof Error
        ? error.message
        : (
          "We could not prepare your recommendation. "
          + "Please try again."
        );
  } finally {
    submitButton.disabled = false;
    submitButton.textContent =
      "Create my recommendation";
  }
});


startOverButton.addEventListener("click", () => {
  form.reset();

  document.querySelector(
    "#group-size",
  ).value = "1";

  document.querySelector(
    "#duration-days",
  ).value = "1";

  document.querySelector(
    "#deliver-report",
  ).checked = true;

  selectedAlternativePackageId = null;
  latestPayload = null;
  cartAddonIds = [];
  cartUpgradeIds = [];

  updateBudgetOptions();

  assessmentCard.hidden = false;
  reportCard.hidden = true;
  reportContent.innerHTML = "";

  showStep(1);

  window.scrollTo({
    top: 0,
    behavior: "smooth",
  });
});


document.querySelector("#group-size").addEventListener(
  "input",
  updateBudgetOptions,
);
document.querySelectorAll('input[name="experience"]').forEach((input) => {
  input.addEventListener("change", () => {
    const groupInput = document.querySelector("#group-size");
    if (input.checked && input.value === "team_connection") {
      groupInput.min = "6";
      if (Number(groupInput.value) < 6) {
        groupInput.value = "6";
        formError.textContent = "Group retreats begin with a minimum of 6 guests; we updated the guest count to 6.";
      }
    } else if (input.checked) {
      groupInput.min = "1";
    }
    updateBudgetOptions();
  });
});
document.querySelector("#duration-days").addEventListener(
  "change",
  updateBudgetOptions,
);
document.querySelectorAll('input[name="budget"]').forEach((input) => {
  input.addEventListener("change", updateEnhancementOptions);
});

document.querySelector("#add-enhancements-button")?.addEventListener(
  "click",
  () => {
    cartAddonIds = getCheckedValues("service_addon");
    cartUpgradeIds = getCheckedValues("upgrade");
    const count = cartAddonIds.length + cartUpgradeIds.length;
    document.querySelector("#enhancement-cart-status").textContent = count
      ? `${count} enhancement selection${count === 1 ? "" : "s"} added. Your recommendation will show the revised eligible total.`
      : "No enhancements are currently in your cart.";
  },
);

document.querySelectorAll(".concierge-suggestions .question-chip").forEach(
  (button) => {
    button.addEventListener("click", () => {
      fillConciergeQuestion(button.textContent.trim());
    });
  },
);

conciergeQuestion.addEventListener(
  "input",
  updateConciergeCharacterCount,
);

conciergeForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const question = conciergeQuestion.value.trim();

  if (question.length < 3) {
    conciergeError.textContent = "Please enter a question using at least three characters.";
    conciergeQuestion.focus();
    return;
  }

  await askConcierge(question);
});

const priorityStep = document.querySelector('.form-step[data-step="3"]');
const investmentSection = document.querySelector("#investment-section");
if (priorityStep && investmentSection) {
  priorityStep.append(investmentSection);
}

updateBudgetOptions();
updateConciergeCharacterCount();
showStep(1);
