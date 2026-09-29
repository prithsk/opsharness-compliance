# Tasks

Each task ends with a gate. Log results in FINDINGS.md.

## 1. Baseline
Run two models from different families on seeds 0:10 (see CLAUDE.md).
Gate: every failing trace is sorted in FINDINGS.md as harness, prompt, model or scorer. Harness problems go to the opsharness repo as issues.

## 2. Fix prompt and scorer problems
Edit world.md for prompt problems. Fix scorer bugs with a failing test first. Rerun the baseline on the same seeds.
Gate: the cross-model spread shrinks, or FINDINGS.md explains why it did not.

## 3. Ablate the rules
Run `--ablate "<section>"` once per section of world.md with the stronger model.
Gate: FINDINGS.md lists which sections moved the score. Delete sections that changed nothing and confirm.

## 4. Live run on the test world
Run `python -m opsharness.agent --project compliance --policy <best model>` with the cli approver, and read every approval request.
Gate: the run finishes with a score, and FINDINGS.md notes any request that looked wrong.

## 5. First real system
Swap the sim server in mcp.json for one real MCP server on a sandbox account (a communications archive, the order management system and a case tracker (keep this one read-mostly)). Run with `--approver deny` first, then with the cli approver.
Gate: the dry run shows only reads going through.

## 6. Harder cases
If every model scores above 0.95, add harder near-misses, each with a wrong-agent test.
Gate: tests pass and the best model drops below 0.95.
