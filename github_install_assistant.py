from __future__ import annotations

import argparse
from pathlib import Path

from install_assistant.orchestrator import AssistantConfig, InstallationOrchestrator
from install_assistant.worker import run_worker


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Plan and perform a GitHub repository installation in a visible second "
            "CLI window while mirroring every step back into the original terminal."
        )
    )
    parser.add_argument("repository_url", nargs="?", help="GitHub repository URL to install.")
    parser.add_argument(
        "--goal",
        default="Clone the repository, create a dedicated virtual environment, install its dependencies, and verify that the installation works on this system.",
        help="Desired installation goal that is passed to the planner model.",
    )
    parser.add_argument(
        "--target-dir",
        type=Path,
        help="Optional absolute or relative target directory for the cloned repository.",
    )
    parser.add_argument(
        "--planner-model",
        default="gpt-5.4-mini",
        help="OpenAI model used for the initial research and installation plan.",
    )
    parser.add_argument(
        "--loop-model",
        default="gpt-5.4-nano",
        help="OpenAI model used for iterative next-step decisions.",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=20,
        help="Hard stop for how many installation commands may be executed.",
    )
    parser.add_argument(
        "--worker",
        type=Path,
        help=argparse.SUPPRESS,
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.worker:
        return run_worker(args.worker)
    if not args.repository_url:
        raise SystemExit("repository_url is required unless --worker is used")

    config = AssistantConfig(
        repository_url=args.repository_url,
        install_goal=args.goal,
        target_dir=args.target_dir,
        planner_model=args.planner_model,
        loop_model=args.loop_model,
        max_steps=args.max_steps,
    )
    return InstallationOrchestrator(config).run()


if __name__ == "__main__":
    raise SystemExit(main())

