# Testing evidence (APPLY)

Only `/root/tester` authors tests, fixtures, test configuration and gate checks.
Application implementation belongs exclusively to `/root/implementation`.
The orchestrator owns task completion decisions; verify and archive are separate roles.

## Sequential evidence

1. Read proposal, design, tasks and all four specification documents before authoring tests.
2. Agreed money/tag API with implementation before testing. Added unit tests while implementation was paused before DB work.
3. ` .venv/bin/python -m unittest discover -s tests/unit -v`: 6 tests passed. Includes accepted/rejected ASCII money forms, zero, 4096-character positive amount, leading zeroes, exact values beyond int64, formatting, normalization and blank names.
4. Added ruff as dev dependency after orchestrator approval. No application code modified by tester.

## Full gate

Pending completion of subsequent implementation slices; mandatory unit, integration and e2e suites will fail if empty, skipped or expected-failure tests are present.

## Scenario map

Initial slice: transaction-management «Допустимые формы», «Недопустимая сумма» (parser portion), «Большая сумма» (parser portion) → `tests.unit.test_money_tags.MoneyTests`.
Tag normalization/blank-name requirements → `tests.unit.test_money_tags.TagNameTests`.
Persistence and UI portions are pending subsequent slices and must not be counted complete yet.
