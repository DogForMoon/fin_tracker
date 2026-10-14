"""Run from repository root: .venv/bin/python -m tests.full_gate."""

import ast
import subprocess
import sys
import unittest
from pathlib import Path

from tests.scenarios import SCENARIOS


def main():
    commands = [
        ["openspec", "validate", "add-telegram-finance-tracker", "--strict"],
        [sys.executable, "-m", "compileall", "-q", "src", "tests"],
        [sys.executable, "-m", "ruff", "check", "src", "tests"],
    ]
    for command in commands:
        print("RUN", " ".join(command), flush=True)
        subprocess.run(command, check=True)
    for path in Path("tests").rglob("test_*.py"):
        if path.parts[1] not in {"unit", "integration", "e2e"}:
            raise SystemExit(f"Test outside mandatory discovery levels: {path}")
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                for decorator in node.decorator_list:
                    name = ast.unparse(decorator)
                    if "skip" in name.lower() or "expectedFailure" in name or "xfail" in name.lower():
                        raise SystemExit(f"Disabled/expected-failure test forbidden: {path}:{node.lineno}")
    all_ids = set()
    for level in ("unit", "integration", "e2e"):
        suite = unittest.defaultTestLoader.discover(f"tests/{level}", top_level_dir=".")
        count = suite.countTestCases()
        if count == 0:
            raise SystemExit(f"Mandatory test level is empty: {level}")

        def ids(tests):
            for test in tests:
                if isinstance(test, unittest.TestSuite):
                    yield from ids(test)
                else:
                    yield test.id()

        found = set(ids(suite))
        declared = set()
        for path in Path("tests", level).rglob("test_*.py"):
            module = ".".join(path.with_suffix("").parts)
            tree = ast.parse(path.read_text(), filename=str(path))
            for node in tree.body:
                if isinstance(node, ast.ClassDef):
                    for method in node.body:
                        if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)) and method.name.startswith("test"):
                            declared.add(f"{module}.{node.name}.{method.name}")
        if declared - found:
            raise SystemExit(f"Undiscovered mandatory tests: {sorted(declared - found)}")
        if len(found) != count or all_ids.intersection(found):
            raise SystemExit(f"Duplicate test discovery in {level}")
        all_ids.update(found)
        print(f"LEVEL {level}: {count} tests", flush=True)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        if not result.wasSuccessful() or result.skipped or result.expectedFailures or result.testsRun != count:
            raise SystemExit(f"Full gate failed: {level}, including skipped/expected/undiscovered checks")
    specification_root = Path("openspec/changes/add-telegram-finance-tracker/specs")
    functional = {path.name for path in specification_root.iterdir() if path.is_dir()} - {"delivery-verification"}
    if functional != set(SCENARIOS):
        raise SystemExit("Unmapped functional specification")
    scenario_count = 0
    for capability, mappings in SCENARIOS.items():
        declared = {line.removeprefix("#### Scenario: ") for line in (specification_root / capability / "spec.md").read_text().splitlines() if line.startswith("#### Scenario: ")}
        if declared != set(mappings):
            raise SystemExit(f"Scenario coverage mismatch: {capability}: {declared.symmetric_difference(mappings)}")
        for scenario, checks in mappings.items():
            if not checks or set(checks) - all_ids:
                raise SystemExit(f"Missing runnable scenario checks: {capability}/{scenario}")
        scenario_count += len(mappings)
    print(f"SCENARIOS: {scenario_count} mapped to discovered passing tests", flush=True)
    print(f"FULL GATE PASS: {len(all_ids)} tests; zero skips/expected failures", flush=True)


if __name__ == "__main__":
    main()
