# Working on opsharness-compliance

This repo is one agent on the opsharness harness. The harness itself lives in the opsharness repo, so harness bugs get fixed there, not here.

## Commands
- Tests: `python -m unittest discover -s tests -t .` (must stay green)
- Baseline: `python -m opsharness.run --env compliance --seeds 0:10 --workers 8 --policy anthropic:claude-haiku-4-5-20251001,openai:<model-id>`
- Read failures: `python -m opsharness.show runs/<stamp> --failing`
- Live run: `python -m opsharness.agent --project compliance --policy <model>`

## Rules
- Never change the scorer or answer key in world.py to make a model pass. A scorer change needs a test in tests/test_world.py that fails before the change and passes after it.
- Every new near-miss or scenario needs a wrong-agent test showing the scorer punishes the mistake.
- Business rules live in opsharness_compliance/world.md. AGENT.md only adds guidance for real systems.
- Never auto-approve against real systems. Real runs use the cli or file approver.
- Keep seeds at 0:10 unless a task says otherwise. Model runs cost money.
- Record every finding in FINDINGS.md with the run folder it came from.

Work through TASKS.md in order. Do not start a task until the previous task's gate passes.
