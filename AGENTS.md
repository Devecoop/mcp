# Project Rules

These rules are mandatory for every agent working in this repository.

## Implementation scope

- Implement only the use cases defined in `docs/project-guidelines.md`.
- Do not add speculative defensive code, extra transports, flags, or helpers for hypothetical future needs.
- Prefer the smallest code that solves the current requirement.
- If a new requirement appears, adapt the code at that point.

## Naming and reuse

- Use expressive names. Never use abbreviations such as `t`, `md`, or `txn`.
- Do not duplicate logic. Extract reusable logic into a helper in the appropriate module.

## Structure

- Respect the folder structure and contracts defined in `docs/project-guidelines.md`.
- Do not create new folders or break a documented contract without explicit approval.

## Tests

- Write only necessary tests. Do not add exhaustive or speculative unit tests.
- Keep the test suite fast; CI runtime matters.
- Test defined behavior and critical edge cases, not internals or hypothetical cases.

## Git

- Never commit without explicit approval. Leave changes staged and wait.
- Never push.
