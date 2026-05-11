"""CLI entrypoint."""

import asyncio
from pathlib import Path
import sys

import typer
from loguru import logger

from nextgen.bootstrap import load_builtin_actions
from nextgen.core.errors import NextgenError
from nextgen.core.planner import validate_testcase
from nextgen.core.scheduler import Scheduler
from nextgen.core.suite import SuiteRunner
from nextgen.core.result import StepResult, StepStatus, SuiteResult, TestResult, TestStatus
from nextgen.core.model import Suite
from nextgen.parser.env_loader import load_env_files
from nextgen.parser.loader import FileKind, classify_file, load_suite, load_testcase
from nextgen.reporter.json_reporter import JsonReporter

app = typer.Typer(
    name="nextgen",
    help="Next-Gen API Test Engine",
    add_completion=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)


def render_terminal_summary(result: TestResult | SuiteResult) -> str:
    """Render a compact human-readable result summary for stderr."""
    if isinstance(result, SuiteResult):
        return render_suite_terminal_summary(result)

    summary = result.summary
    lines = [
        "-- result --",
        f"  {Path(result.testcase).name}  {result.status.value}  {result.total_duration_ms}ms",
        (
            "  steps: "
            f"{summary['success']} passed, "
            f"{summary['failed']} failed, "
            f"{summary['skipped']} skipped"
        ),
    ]

    failed_steps = [step for step in result.steps if step.status == StepStatus.FAILED]
    if failed_steps:
        lines.append("")
        lines.extend(f"  {format_failed_step(step)}" for step in failed_steps)

    return "\n".join(lines)


def render_suite_terminal_summary(result: SuiteResult) -> str:
    """Render a compact human-readable suite result summary for stderr."""
    summary = result.summary
    lines = [
        "-- suite result --",
        f"  {result.suite}  {result.status.value}  {result.total_duration_ms}ms",
        (
            "  testcases: "
            f"{summary['success']} passed, "
            f"{summary['failed']} failed, "
            f"{summary['skipped']} skipped"
        ),
    ]

    failed_tests = [test for test in result.tests if test.status == TestStatus.FAILED]
    if failed_tests:
        lines.append("")
        lines.extend(
            f"  FAILED  {Path(test.testcase).name}"
            for test in failed_tests
        )

    skipped_tests = [test for test in result.tests if test.status == TestStatus.SKIPPED]
    if skipped_tests:
        lines.append("")
        lines.extend(
            f"  SKIPPED  {Path(test.testcase).name}"
            for test in skipped_tests
        )

    return "\n".join(lines)


def format_failed_step(step: StepResult) -> str:
    parts = [
        "FAILED",
        step.name,
        step.action_summary,
    ]

    if step.metric is not None:
        parts.append(f"{step.metric['label']}={step.metric['value']}")
    if step.error:
        parts.append(step.error)

    return "  ".join(parts)


@app.command()
def run(
    files: list[Path] = typer.Argument(..., help="Testcase or suite YAML/JSON file path"),
    env_files: list[Path] | None = typer.Option(
        None,
        "--env",
        "-e",
        help="Environment variable file, YAML or JSON. Can be passed multiple times.",
    ),
    parallel: int = typer.Option(10, "--parallel", "-p", help="Maximum concurrency"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show verbose logs"),
) -> None:
    """Run a testcase or suite."""
    if not verbose:
        logger.remove()
        logger.add(sys.stderr, level="WARNING")

    try:
        load_builtin_actions()

        result = asyncio.run(run_inputs(files, env_files or [], parallel))

        # Output report.
        print(JsonReporter().render(result))
        typer.echo(render_terminal_summary(result), err=True)

        # Exit code.
        if result.status == TestStatus.FAILED:
            raise typer.Exit(code=1)

    except FileNotFoundError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=2)
    except NextgenError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=2)
    except ValueError as e:
        typer.echo(f"Invalid testcase format: {e}", err=True)
        raise typer.Exit(code=2)
    except RuntimeError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=2)


async def run_inputs(
    files: list[Path],
    env_files: list[Path],
    parallel: int,
) -> TestResult | SuiteResult:
    """Run CLI inputs and return either a testcase or suite result."""
    if not files:
        raise ValueError("at least one file is required")

    if len(files) == 1:
        kind = classify_file(files[0])
        if kind == FileKind.SUITE:
            return await SuiteRunner(
                load_suite(files[0]),
                cli_env_files=env_files,
                max_concurrency=parallel,
            ).run()
        return await run_single_testcase(files[0], env_files, parallel)

    kinds = [classify_file(file) for file in files]
    if any(kind == FileKind.SUITE for kind in kinds):
        raise ValueError("suite files cannot be mixed with other CLI inputs")

    resolved_files = dedupe_paths(files)
    suite = Suite(
        name="cli",
        tests=[str(path) for path in resolved_files],
        source_path=None,
        base_dir=None,
    )
    return await SuiteRunner(
        suite,
        cli_env_files=env_files,
        max_concurrency=parallel,
    ).run()


async def run_single_testcase(
    file: Path,
    env_files: list[Path],
    parallel: int,
) -> TestResult:
    """Run one testcase file."""
    testcase = load_testcase(file)
    testcase.vars = {
        **testcase.vars,
        **load_env_files(env_files),
    }
    validate_testcase(testcase)

    result = await Scheduler(testcase, max_concurrency=parallel).run()
    result.testcase = str(file)
    return result


def dedupe_paths(files: list[Path]) -> list[Path]:
    """De-duplicate paths by resolved location while preserving first occurrence."""
    seen: set[Path] = set()
    deduped: list[Path] = []
    for file in files:
        resolved = file.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        deduped.append(resolved)
    return deduped


if __name__ == "__main__":
    app()
