# 3-minute pitch — Agency 2026 demo

Outline tied directly to the four scoring axes. Adjust numbers/names after the real pipeline run produces actual findings.

## 0:00 — 0:30  The problem (Impact axis)
> "Every year Canadians give over $300 billion through charitable receipts and government grants. We trust that money flows to real public good. But what if some of it is just moving in circles between related charities, generating tax receipts and inflating reported revenues without actually funding any service? Our job today: build an agentic AI investigator that can spot those circular flows automatically, at scale, with names and dollar amounts a Minister can act on."

Keep it concrete. End with: "And we found `<N>` cases worth `<$X>` in the data."

## 0:30 — 2:00  Watch the agents work (Agent Autonomy axis)
> "I'll click one button. Four agents take over."
- Click **Run Investigation** on the dashboard.
- As events stream, narrate:
  - "Discovery agent: scanning 5,808 pre-detected cycles in CRA charity gift data — picking the 20 with the highest dollar flow."
  - "Investigation agent: for each cycle, it autonomously queries 5 different tables — charity identities, gift edges, directors, cross-dataset funding from federal and Alberta grants. It builds a NetworkX graph for cycle metrics."
  - "Validator agent: this is where it gets interesting. It rules out legitimate denominational hierarchies, parent-subsidiary structures. It scores severity on five axes."
  - "Narrative agent: writes a Minister-ready brief. Hard constraint — every number must trace to a database row. No hallucinations."

The point judges should hear: "no human in the loop after the click."

## 2:00 — 2:45  The top finding (Innovation + Presentation axes)
> "Here's the top finding the agents surfaced." — read out the **lead_sentence** of the highest-scoring brief verbatim:
> "$X.XM flowed in a closed loop between charities A, B, C, D between 20YY and 20ZZ. They share N directors. Together they received $Y.YM in federal and AB grants outside the loop. Recommended: trigger CRA T3010 audit on all 4 charities for FY 20YY-20ZZ."

Then explain the *innovation*:
> "The novelty isn't cycle detection — that's classical graph theory. The novelty is the autonomous *judgment chain*: an agent decided this wasn't denominational, wasn't parent-subsidiary, wasn't trivial. It scored director overlap. It pulled cross-dataset taxpayer exposure. It wrote a brief whose every number is queryable. That's what a tax investigator would do — but in 90 seconds, on every cycle in the database."

## 2:45 — 3:00  The close (Presentation + What's next)
> "We picked Ch. 3 because the data has 4,526 detected cycles worth $4.34B in flow. We could ship this to CRA tomorrow as an audit-prioritization tool. The 4-agent pattern generalizes — swap the Discovery prompt and you're hunting amendment creep, vendor concentration, or director networks instead. One architecture, many accountability problems."

End slide / dashboard view: the top 3 Minister Briefs as cards with verdict badges.

---

## Demo backup plan
- If the live agent run fails or is slow on stage: tick **fake-events mode** in the UI to show the architecture; then narrate the cached top findings from a previous run (saved to `data/last_good_run.json`).
- If the network drops: dashboard is still local; only the LLM call needs network. The cached run is fully offline.

## Cheat sheet — answers to likely judge questions
- **"How do you avoid false positives?"** → Validator's rule-out logic (denominational name prefixes, parent-subsidiary BN matching, trivial-amount filter). We mark `medium_concern` when uncertain instead of `high_concern`.
- **"What if the LLM hallucinates a number?"** → Narrative agent's prompt forbids any number not in the input dossier. Briefs include `evidence_refs` linking back to query results.
- **"Could you scale this to all 23M rows?"** → Discovery agent already operates on the full corpus via aggregation queries. Investigation+Validator scale linearly per candidate; we cap at 20 per run for demo speed but the agent loop is parallelizable.
- **"Why Strands + Bedrock?"** → Production-grade agent framework with built-in tool use + streaming. Bedrock for security + sponsor parity. Same code runs unchanged against Anthropic API for dev.
- **"Why this specific challenge over the other 9?"** → empirical scorecard (analysis/scorecard.md): Ch.3 had the cleanest signal, fastest queries, most defensible math, most demo-able output. We probed all 10 before deciding.
