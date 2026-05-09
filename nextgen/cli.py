"""CLI entrypoint."""

import asyncio
from pathlib import Path

import typer
from loguru import logger

from nextgen.bootstrap import load_builtin_actions
from nextgen.core.planner import validate_testcase
from nextgen.core.scheduler import Scheduler
from nextgen.core.result import StepResult, StepStatus, TestResult, TestStatus
from nextgen.parser.loader import load_testcase
from nextgen.reporter.json_reporter import JsonReporter

app = typer.Typer(
    name="nextgen",
    help="Next-Gen API Test Engine",
    add_completion=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)


def render_terminal_summary(result: TestResult) -> str:
    """Render a compact human-readable result summary for stderr."""
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
    file: Path = typer.Argument(..., help="Testcase YAML file path"),
    parallel: int = typer.Option(10, "--parallel", "-p", help="Maximum concurrency"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show verbose logs"),
) -> None:
    """Run a testcase."""
    if not verbose:
        logger.remove()
        logger.add(lambda m: None, level="WARNING")

    try:
        load_builtin_actions()

        # Load testcase.
        testcase = load_testcase(file)

        # Validate DAG.
        validate_testcase(testcase)

        # Execute.
        scheduler = Scheduler(testcase, max_concurrency=parallel)
        result = asyncio.run(scheduler.run())
        result.testcase = str(file)

        # Output report.
        print(JsonReporter().render(result))
        typer.echo(render_terminal_summary(result), err=True)

        # Exit code.
        if result.status == TestStatus.FAILED:
            raise typer.Exit(code=1)

    except FileNotFoundError as e:
        logger.error(str(e))
        raise typer.Exit(code=2)
    except ValueError as e:
        logger.error(f"Invalid testcase format: {e}")
        raise typer.Exit(code=2)


if __name__ == "__main__":
    app()
