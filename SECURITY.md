# Security

Report a vulnerability through this repo's private security advisory form (Security tab, then "Report a vulnerability"). Please do not open a public issue for it.

This agent runs on the opsharness harness. Read the threat model in the opsharness repo's SECURITY.md before connecting real systems. The short version:

- mcp.json starts programs on your machine. Only use a config you wrote or reviewed.
- Keep tokens in environment variables and reference them in mcp.json as `${NAME}`. Never write a token into the file.
- Run against real systems with the cli or file approver, and read the exact arguments of every approval request before you say yes.
- Run logs under runs/ contain everything the agent read, which can include customer data. runs/ is gitignored, so keep it that way.
