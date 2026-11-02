# Safety
- Only ever connect to the local docker-compose database. Never use staging or production credentials.
- Ask before: deleting files, running a migration downward, installing a new dependency, or running any command that calls the network.
- Never log tokens, passwords or full location trails in plain application logs.
- Never commit secrets, `.env` files, or client data files (employee names, salaries). Use fictional seed data.
- The mobile contract (`docs/09-mobile-sync-contract.md`) is shared with another team. Do not rename or remove a published field without a version bump, a changelog entry and my approval.
