`github_install_assistant.py` is a platform-aware installer assistant for GitHub repositories.

What it does:

- Probes the local machine first: OS, Python, Git, GPU, VRAM, NVIDIA driver, CUDA runtime, CUDA toolkit, WSL2 availability on Windows, and processor count.
- Sends the installation goal, repository URL, and detected system profile to the OpenAI Responses API.
- Uses a planner model to research the install path, then runs installation commands in a second visible terminal window.
- Mirrors every command and its output back into the original terminal with ANSI colors, including the exact prompt text sent to the LLM.
- Re-queries the LLM after each command result to decide the next command.
- Requires a dedicated virtual environment for dependency installation and pushes the planner toward explicit venv-aware commands.
- If the repository appears to need PyTorch, CUDA inference, RealtimeTTS, faster-whisper, faster-qwen, or similar GPU stacks, it probes `nvidia-smi`, `nvcc --version`, and `CUDA_PATH`, then asks the LLM to research a compatible torch wheel instead of blindly using the newest CUDA build.
- On Windows, it now lets the planner choose between native execution and WSL2 when Linux is the safer install target. WSL2 commands are executed through `wsl.exe`, while the original terminal still receives the same detailed mirrored output and final documentation.
- Prints a final structured installation report with successful commands, virtual environment details, test/example discovery, and useful follow-up notes.

Requirements:

- Python
- `OPENAI_API_KEY` in the environment
- Network access for the OpenAI API and the repository being installed
- A terminal launcher supported by your platform
  Windows: `cmd.exe`
  macOS: Terminal.app via `open`
  Linux: one of `x-terminal-emulator`, `gnome-terminal`, `konsole`, or `xterm`
- If the planner chooses WSL2 on Windows, a working WSL2 distribution must be installed and accessible via `wsl.exe`

Usage:

```powershell
$env:OPENAI_API_KEY="sk-..."
python .\github_install_assistant.py https://github.com/owner/repo
python .\github_install_assistant.py https://github.com/owner/repo --goal "Install RealtimeTTS with faster-qwen3-tts support and CUDA-enabled PyTorch. Create a new venv. Install torch first via the correct CUDA index URL before other dependencies."
python .\github_install_assistant.py https://github.com/owner/repo --goal "Install this repository, and if it is Linux-first or more reliable there, use WSL2 on this Windows machine."
python .\github_install_assistant.py https://github.com/owner/repo --target-dir .\installed_repositories\repo --max-steps 25
```

Notes:

- The worker window is intentionally limited to install commands and command output.
- The assistant only treats the installation as finished after a verification command succeeds and the LLM returns `finish`.
- There is also a hard stop via `--max-steps`, plus a repeated-command guard to avoid infinite loops.
- When torch is required, the planner must return a researched `torch_install_command`, and the orchestrator will force that command to happen before later dependency-install commands.
- When WSL2 is selected, the planner returns Linux paths and Linux commands, but the final report still tries to point back to a host-visible install root when the repository lives under a mounted Windows path.
- After the last step, the original window shows a detailed documentation block describing what succeeded and how to continue using the installed repository.
