# Phase workflow
- The project is built in phases (`docs/phases/README.md`). Work on **one phase per conversation**. If the user does not name a phase, ask which one.
- Read only: `AGENTS.md`, `.agents/rules/*`, the phase file, and the files listed in its Context section. Do not read or modify unrelated documents or modules.
- First ask clarifying questions, then write a plan (files to create, order, how it will be verified) and **wait for approval**.
- Build exactly the phase's Deliverables. Anything listed under Out of scope is not built, even if it looks easy.
- Tick the phase checklist honestly; list anything not done. Do not mark a phase done yourself: the owner does after review.
- Update docs, the decision register status if a decision was resolved, and CHANGELOG in the same change.
- If the phase is too large for one session, propose a split of its Deliverables to the user rather than skipping items.
