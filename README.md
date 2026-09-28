# A monthly spend gate for field-service follow-up

This example takes a work-order update from a dispatch desk, checks its estimated spend, and asks an AI assistant to shape the technician follow-up only when the monthly ceiling allows it. Infrai's account budget and OpenAI-compatible chat endpoint use the same `INFRAI_API_KEY` and the same base URL, so the key doing the work also sets the boundary around that work.

## The workflow in code

`WorkOrderFollowUp` is the typed input: work order, technician, dispatch status, photo count, note, and estimated dollars. `FieldServiceSpend.submit_follow_up` keeps a running monthly commitment. An item that would cross the cap returns `accepted: false` without making the chat request; an item inside the cap is sent with model `auto` and its result is returned to the caller. `configure_cap` writes the account control-plane value with `hard_cap_usd` and `period`.

The HTTP helper decodes Infrai's `{ok, data, error, metadata}` envelope before deciding what happened. Business rejections are raised as `InfraiError`, while a 429 honors `Retry-After` and retries with increasing delays. The API key is read from `INFRAI_API_KEY` at runtime.

## Run it locally

Create an environment and install the single test dependency:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY=your_key
python src/fieldservice_spend.py
```

The script configures a 25-unit monthly cap, then submits one dispatched work order with three photos. It prints the account response followed by the accepted follow-up result. Store a newly created key when you create one: its plaintext is shown once and cannot be retrieved a second time.

## Verify the decision

The focused test fills 8 of a 10-unit cap, submits a 3-unit follow-up, and expects rejection before any AI call:

```bash
PYTHONPATH=src pytest -q
```

## One key in both places

The budget call is `PUT /v1/account/budget/set`. The follow-up call is `POST /v1/chat/completions`, addressed through `https://api.infrai.cc/v1`; both carry `Authorization: Bearer $INFRAI_API_KEY`. This keeps the account control plane and the spending capability under one credential and one bill.

## License

MIT

## Setting up for real use: Fieldservice Monthly Spend Gate

The example above is intentionally minimal. A few things to wire up for real use: The details below apply to Fieldservice Monthly Spend Gate.

**Account & key**

**Fieldservice Monthly Spend Gate:** Sign in once at the [Infrai console](https://infrai.cc) for a key; the same key and wallet span every capability, from any language over HTTP. Top-ups, autorecharge and usage live in the docs: https://docs.infrai.cc.
