# Testing evidence (APPLY)

Only `/root/tester` authors tests, fixtures, test configuration and gate checks.
Application implementation belongs exclusively to `/root/implementation`.
The orchestrator owns task completion decisions; verify and archive are separate roles.

## Sequential evidence

1. Read proposal, design, tasks and all four specification documents before authoring tests.
2. Agreed money/tag API with implementation before testing. Added unit tests while implementation was paused before DB work.
3. ` .venv/bin/python -m unittest discover -s tests/unit -v`: 6 tests passed. Includes accepted/rejected ASCII money forms, zero, 4096-character positive amount, leading zeroes, exact values beyond int64, formatting, normalization and blank names.
4. Added ruff as dev dependency after orchestrator approval. No application code modified by tester.
5. Agreed Store API with implementation and authored 7 real SQLite integration tests before Store was ready. Independent run `.venv/bin/python -m unittest discover -s tests/integration -v`: 7 tests passed. The tests exercise FK/unique constraints and cascade directly, exact TEXT storage beyond int64, reopening, owner boundaries, tag lifecycle, archived assignment, actual SQLite trigger failure with rollback of create and update, and Moscow day/tag filters. Additional raw schema assertions also pass. Implementation's ruff import warning was reported to its author, never edited by tester.
6. Before MVP, added 7 unit tests for Draft rules (date/token, back/next retaining values, format failure retaining stage/value, optional skip, comments and archived tag retention/removal). `.venv/bin/python -m unittest discover -s tests/unit -v`: 13 passed; ruff passed. Only then informed orchestrator that pure FSM slice was complete.

## Full gate

From repository root: `.venv/bin/python -m tests.full_gate` after `uv sync --locked --dev`.
Requires Python >=3.13 and OpenSpec CLI in PATH. Ruff is a locked dev dependency; stdlib unittest discovers all three levels separately.
Runs `openspec validate add-telegram-finance-tracker --strict`, Python compileall, ruff static checks and every unit/integration/e2e test. Empty levels, duplicate test IDs, skip decorators/results, expected failures and failing or unexpectedly successful tests fail the gate.
At the DB slice this deliberately fails pending missing e2e; it is not yet a passing apply gate.

## Scenario map

Initial slice: transaction-management «Допустимые формы», «Недопустимая сумма» (parser portion), «Большая сумма» (parser portion) → `tests.unit.test_money_tags.MoneyTests`.
Tag normalization/blank-name requirements → `tests.unit.test_money_tags.TagNameTests`.
Persistence and UI portions are pending subsequent slices and must not be counted complete yet.
