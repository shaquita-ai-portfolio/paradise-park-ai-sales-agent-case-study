# Paradise Park Sales Agent v6.1

## Corrected

- Moved `selected_addon_ids` inside the typed `assessment` request contract,
  eliminating the FastAPI “extra inputs are not permitted” response.
- Added visual separation between service enhancements and product
  enhancements.
- Moved the investment decision after meaningful-experience priorities and
  current wellness challenges.
- Added value-framing copy before investment selection.
- Added structured challenge signals for anxiety, trauma-aware restoration,
  relationship renewal, fear and confidence, leveling up, anti-aging and
  vitality, natural fertility, postpartum renewal, grief, high stress, burnout
  renewal and high-demand lifestyles.
- Added approved service-ranking rules for every new challenge signal.
- Changed personal multi-day selection so two or more service days recommend
  Executive Reset, with Peak Performance Pivot considered for qualifying
  three-day-plus requests.
- Added a cabin-without-wellness-services alternative for multi-day requests.
- Hid separately priced service enhancements when the assessment points to
  Executive Reset or Peak Performance Pivot, because those programs already
  curate two private services per day and include Farm-to-Table and signature
  core experiences.
- Limited Express/Rapid selection to Farm-to-Table plus one private
  enhancement to preserve duration and entitlement rules.
- Corrected group-mode detection for the `team_connection` assessment value.
- Extended browser duration validation to match the seven-day API contract.

## Verification

- 158 automated tests passed.
- JavaScript syntax passed.
- Python compilation passed.
- Recommendation-rule JSON validation passed.

