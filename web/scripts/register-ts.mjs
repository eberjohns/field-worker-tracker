// Lets `node --test` run TypeScript and TSX tests (Batch 10 A): `node --import ./scripts/register-ts.mjs --test ...`.
// The hooks transpile with the project's own `typescript` package, so no extra dependency is needed.
import { register } from "node:module";

register("./ts-hooks.mjs", import.meta.url);
