# Integration steps for Shaquita

These files are complete replacements. Keep the current project as a Git checkpoint before copying them.

## 1. Make a safety checkpoint

Run these commands from the current Paradise Park repository:

```bash
cd "$HOME/AI Work/paradise-park-sales-agent"
git status --short
git add .
git commit -m "Checkpoint before commercial policy integration"
```

If Git says there is nothing to commit, continue.

## 2. Unzip the integration package

Assuming the downloaded zip is in Downloads:

```bash
mkdir -p "$HOME/Downloads/paradise-park-integration-v2"
unzip -o "$HOME/Downloads/paradise-park-commercial-integration-v2.zip" \
  -d "$HOME/Downloads/paradise-park-integration-v2"
```

## 3. Copy the complete replacement files

```bash
cp -R "$HOME/Downloads/paradise-park-integration-v2/data/." \
  "$HOME/AI Work/paradise-park-sales-agent/data/"

cp -R "$HOME/Downloads/paradise-park-integration-v2/src/paradise_park_sales_agent/." \
  "$HOME/AI Work/paradise-park-sales-agent/src/paradise_park_sales_agent/"

cp -R "$HOME/Downloads/paradise-park-integration-v2/static/." \
  "$HOME/AI Work/paradise-park-sales-agent/static/"

cp -R "$HOME/Downloads/paradise-park-integration-v2/tests/." \
  "$HOME/AI Work/paradise-park-sales-agent/tests/"

cp "$HOME/Downloads/paradise-park-integration-v2/.env.example" \
  "$HOME/AI Work/paradise-park-sales-agent/.env.example"

cp "$HOME/Downloads/paradise-park-integration-v2/.gitignore" \
  "$HOME/AI Work/paradise-park-sales-agent/.gitignore"

cp "$HOME/Downloads/paradise-park-integration-v2/README.md" \
  "$HOME/AI Work/paradise-park-sales-agent/README.md"
```

Do not replace the real `.env` file with `.env.example`.

## 4. Configure environment values

Open `.env` in VS Code and confirm it contains real sandbox values for:

- `SQUARE_ACCESS_TOKEN`
- `SQUARE_LOCATION_ID`
- `EXPRESS_RESET_CALENDAR_URL`
- `WELLNESS_CONSULT_URL`

Keep `SQUARE_ENVIRONMENT=sandbox` until test purchases succeed.

## 5. Synchronize and test

```bash
cd "$HOME/AI Work/paradise-park-sales-agent"
uv sync
uv run python -m py_compile src/paradise_park_sales_agent/*.py
uv run pytest -q
```

Expected result: all tests pass.

## 6. Run and manually verify the experience

```bash
uv run uvicorn paradise_park_sales_agent.api:app --reload
```

Open `http://127.0.0.1:8000` and test these five scenarios:

1. Under $997: Express Reset, one activation, calendar button, no deposit.
2. $997–$1,799: Rapid Reset, four included activations and one paid private suggestion.
3. $1,800–$4,999: Executive Reset with correct one-to-three-day price.
4. $9,987: Peak Performance Pivot with 12 guided and six private sessions across three days.
5. Group of 10 or more: approved group tier and per-person pricing.

Use Square sandbox test payment details only.

## 7. Commit the milestone

```bash
git status --short
git add .gitignore .env.example README.md pyproject.toml uv.lock
git add data src static tests
git commit -m "Integrate profit-aware Paradise Park sales experience"
```

Never add `.env` to Git.
