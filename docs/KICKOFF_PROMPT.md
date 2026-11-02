# Prompts for the agent (Antigravity)

Open the project folder (containing `AGENTS.md`, `.agents/`, `docs/`) and start a **new conversation for every phase**.

## Phase prompt (use for every phase; change the number)
```
Work on PHASE-NN of the Field Worker Tracker (see docs/phases/README.md).
Use the start-phase skill. Read AGENTS.md, .agents/rules/*, the phase file docs/phases/PHASE-NN-*.md,
and ONLY the files listed in its Context section. Do not read or change unrelated modules or documents.
Step 1: summarise what you will build and what is out of scope.
Step 2: ask me up to 10 questions about anything unclear or contradictory. Wait for my answers.
Step 3: write a plan (files, order, how each checklist item will be verified). Wait for my approval before writing any file.
Step 4: build on a branch, tick the checklist honestly, update docs and CHANGELOG, open a pull request. Never merge.
Use the finish-phase skill at the end. Do not mark the phase done; I will after review.
```

## First prompt (Phase 00)
Use the phase prompt with `PHASE-00`. In Step 3 also propose how you will verify every dependency in `docs/17-dependencies.md` (latest release date, maintenance, licence, compatibility) before pinning versions.

## Notes
- If the agent proposes a change to the stack or module layout, ask it to write an ADR first.
- Review every plan before approving: this is the cheapest place to fix a wrong assumption.
- If your Antigravity version looks for `.agent/` instead of `.agents/`, rename the folder.
- Add MCP servers (GitHub, read-only local Postgres, library docs) after Phase 00, following `docs/15-dev-process.md` section 10. Keep credentials in environment variables.
