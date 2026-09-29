# opsharness-compliance

Trade surveillance agent, open source, running on the [opsharness](https://github.com/prithsk/opsharness) agent harness. It reviews trader communications for front-running, MNPI sharing and off-channel requests without flagging the allowed near-misses, and it reconstructs a client order's timeline across time zones.

It is inspired by how TovenAI (YC S26) describes its product publicly. It is not their code and has no connection to them.

## Quick start

```
pip install -e .
python -m opsharness.agent --project compliance --policy anthropic:claude-haiku-4-5-20251001
```

That starts the servers listed in `mcp.json`, gives the model the rules in `opsharness_compliance/world.md` plus `AGENT.md`, and stops at your terminal before any action that needs approval. Out of the box, `mcp.json` serves this repo's test world, so it runs with no accounts and reports a score. Each run writes `runs/live/compliance/<stamp>/summary.md` and `trace.json`.

Useful flags: `--task "..."` sets the job, `--approver file` writes each request to `approvals/*.md` and waits for you to change `decision: pending` to `approved` or `denied`, `--approver deny` makes a dry run, and `--backend sim` runs the test world in-process.

The model keys come from `ANTHROPIC_API_KEY`, or from `OPENAI_API_KEY` plus `OPENAI_BASE_URL` for any OpenAI-compatible provider such as OpenRouter (`--policy openai:<model-id>`).

## Connect real systems

Replace the `sim` server in `mcp.json` with MCP servers for a communications archive, the order management system and a case tracker (keep this one read-mostly). Any tool its server does not mark `readOnlyHint: true` needs approval by default, and the `approve` patterns override that per `server/tool`. The business rules in `world.md` stay the same. Keep tokens in environment variables and write them in mcp.json as `${NAME}`, never as the literal value. See SECURITY.md before connecting anything real.

## The test world

`opsharness_compliance/world.py` generates a fresh instance per seed with a hidden answer key, so every run gets a score with no grader model. Every violation type has a near-miss next to it: public news, approved channels, and prop trades after the client fill. Chat is UTC and the order system is New York time, so sorting raw timestamps gives the wrong order.

Run the tests with `python -m unittest discover -s tests -t .`. The contract tests from the core check that the correct plan scores 1.0, doing nothing scores 0.0, approvals get enforced, the harness survives injected model slips, and the world still scores 1.0 over MCP. The wrong-agent tests check that realistic mistakes lose points.

To use the world from Claude Desktop or Claude Code, add it as an MCP server with `python -m opsharness.mcp_serve --env compliance --seed 3`.

## Status

The scorers and the harness path are verified. No real model has run against this world yet, and no real system is connected yet. TASKS.md lists what comes next.
