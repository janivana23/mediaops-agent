---
name: generate-campaign
description: Run a batch of marketing asset generations for a client campaign through the MediaOps MCP server, respecting budget limits and approval checkpoints. Use when asked to produce a set of campaign assets (e.g. "generate the Summer Sale assets for Acme") rather than a single one-off image.
---

# Generate campaign assets

This skill drives the MediaOps MCP server (see `backend/mcp_server.py`) to
turn a campaign brief into a batch of generated assets, without bypassing
the business rules the server enforces. Those rules are enforced
server-side, not by this skill — nothing here can force a job through a
closed budget or approval gate, and it should not try to.

## Inputs you need before starting

- `client_id` — call `list_clients` if you don't have it.
- A list of shots/assets to generate: each needs a `prompt`, a `kind`
  (`image` or `video`), and optionally a `resolution` and
  `reference_image_path` (required for character-consistency campaigns —
  ask the user for this path if the brief implies a recurring
  character/mascot/product and none was given).

## Procedure

1. Call `get_usage(client_id)` first. If remaining budget looks too small
   for the number of assets requested, say so before generating anything —
   don't discover it one job at a time.
2. For each asset in the brief, call `generate_asset(client_id, campaign,
   prompt, resolution, kind, reference_image_path)` one at a time (not in
   parallel — each call re-reads the client's remaining budget, and
   generating serially is what makes that check meaningful).
3. Read the status of each result:
   - `delivered` — note the cost, QA scores, and output path. Continue.
   - `awaiting_approval` — **stop generating further assets in this
     campaign that also look like they'd exceed the threshold**, and tell
     the user which job(s) need a human to call `approve_job` or
     `reject_job`. Do not attempt to "fix" this by asking for a lower
     resolution unless the user explicitly says to — that's a scope
     decision for the human, not the agent.
   - `qa_failed` — report the identity/brand scores that failed and the
     reference image used. Ask the user whether to retry (which spends
     budget again) or accept the output as-is.
   - `rejected` (budget_exceeded) — stop. Report exactly how much budget is
     left and how many more assets (if any) fit in it, so the user can
     decide what to cut rather than you guessing.
4. After the batch, summarize: total spend, cost-per-delivered-asset,
   how many needed approval, how many failed QA. This is the number the
   founder actually cares about (turnaround / cost-per-deliverable) — lead
   with it, not with a list of individual job IDs.

## What this skill must never do

- Never split one expensive request into several cheaper ones to duck
  under the approval threshold — the threshold exists so a human sees
  spend above a line, and gaming it defeats the point.
- Never retry a `qa_failed` job silently more than once without telling
  the user each attempt also spends budget.
- Never invent a `client_id` or `reference_image_path` — ask if missing.
