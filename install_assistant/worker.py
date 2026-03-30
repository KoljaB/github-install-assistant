from __future__ import annotations

import shlex
import subprocess
import sys
import time
from pathlib import Path

from .ansi import WORKER_THEME, enable_ansi, paint
from .models import CommandResult, CommandTask
from .session_io import append_event, read_json, write_json


POLL_INTERVAL_SECONDS = 0.10


def run_worker(config_path: Path) -> int:
    enable_ansi()
    config = read_json(config_path)
    commands_dir = Path(config["commands_dir"])
    results_dir = Path(config["results_dir"])
    artifacts_dir = Path(config["artifacts_dir"])
    events_path = Path(config["events_path"])
    status_path = Path(config["status_path"])
    execution_environment = config.get("execution_environment", "native")
    wsl_distribution = config.get("wsl_distribution", "")

    next_step = 1
    while True:
        task_path = commands_dir / f"{next_step:04d}.json"
        if task_path.exists():
            task = CommandTask.from_dict(read_json(task_path))
            _execute_task(
                task,
                results_dir=results_dir,
                artifacts_dir=artifacts_dir,
                events_path=events_path,
                execution_environment=execution_environment,
                wsl_distribution=wsl_distribution,
            )
            next_step += 1
            continue

        if status_path.exists():
            status = read_json(status_path)
            state = status.get("state", "running")
            if state != "running":
                append_event(events_path, "worker_complete", {"state": state, "message": status.get("message", "")})
                return 0

        time.sleep(POLL_INTERVAL_SECONDS)


def _execute_task(
    task: CommandTask,
    *,
    results_dir: Path,
    artifacts_dir: Path,
    events_path: Path,
    execution_environment: str,
    wsl_distribution: str,
) -> None:
    output_path = artifacts_dir / f"{task.step_number:04d}.log"
    output_path.write_text("", encoding="utf-8")

    if execution_environment != "wsl2":
        cwd = Path(task.cwd)
        cwd.mkdir(parents=True, exist_ok=True)

    _write_command(f"[{task.step_number:02d}] {task.command}\n")
    append_event(
        events_path,
        "command_started",
        {
            "step_number": task.step_number,
            "command": task.command,
            "cwd": task.cwd,
            "reason": task.reason,
            "expectation": task.expectation,
        },
    )

    def on_output(text: str) -> None:
        _write_output(text)
        with output_path.open("a", encoding="utf-8", errors="replace") as handle:
            handle.write(text)
        append_event(
            events_path,
            "command_output",
            {
                "step_number": task.step_number,
                "text": text,
            },
        )

    if execution_environment == "wsl2":
        completed = _stream_wsl_command(task.command, cwd=task.cwd, distro=wsl_distribution, on_line=on_output)
    else:
        completed = _stream_native_command(task.command, cwd=Path(task.cwd), on_line=on_output)

    result = CommandResult(
        step_number=task.step_number,
        command=task.command,
        cwd=task.cwd,
        reason=task.reason,
        expectation=task.expectation,
        exit_code=completed["exit_code"],
        output=completed["output"],
        duration_seconds=completed["duration_seconds"],
    )
    write_json(results_dir / f"{task.step_number:04d}.json", result.to_dict())
    append_event(
        events_path,
        "command_finished",
        {
            "step_number": task.step_number,
            "exit_code": result.exit_code,
            "duration_seconds": result.duration_seconds,
        },
    )
    _write_output(f"\nExit code: {result.exit_code}\n\n")


def _stream_native_command(command: str, *, cwd: Path, on_line) -> dict[str, object]:
    return _stream_process(command, cwd=str(cwd), on_line=on_line, shell=True)


def _stream_wsl_command(command: str, *, cwd: str, distro: str, on_line) -> dict[str, object]:
    quoted_cwd = shlex.quote(cwd)
    bash_command = f"cd {quoted_cwd} && {command}"
    args = ["wsl.exe"]
    if distro:
        args.extend(["--distribution", distro])
    args.extend(["bash", "-lc", bash_command])
    return _stream_process(args, cwd=None, on_line=on_line, shell=False)


def _stream_process(command, *, cwd: str | None, on_line, shell: bool) -> dict[str, object]:
    started = time.monotonic()
    popen_kwargs = {
        "cwd": cwd,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.STDOUT,
        "stdin": subprocess.DEVNULL,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "bufsize": 1,
        "shell": shell,
    }
    process = subprocess.Popen(command, **popen_kwargs)

    output_chunks: list[str] = []
    assert process.stdout is not None
    for line in iter(process.stdout.readline, ""):
        output_chunks.append(line)
        on_line(line)

    trailing = process.stdout.read()
    if trailing:
        output_chunks.append(trailing)
        on_line(trailing)

    process.stdout.close()
    exit_code = process.wait()
    return {
        "exit_code": exit_code,
        "output": "".join(output_chunks),
        "duration_seconds": time.monotonic() - started,
    }


def _write_command(text: str) -> None:
    sys.stdout.write(paint(text, WORKER_THEME.command, bold=True))
    sys.stdout.flush()


def _write_output(text: str) -> None:
    sys.stdout.write(paint(text, WORKER_THEME.output))
    sys.stdout.flush()
