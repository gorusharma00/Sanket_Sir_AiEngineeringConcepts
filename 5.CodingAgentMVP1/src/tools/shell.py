import re
import shlex 
import sys
import os
import subprocess
import time

from langchain.tools import tool

from config.config import get_work_dir
from tools.jobs import is_alive, now_iso, register, BackgroundJob, read_log_tail, stop_pid, all_jobs

MAX_OUTPUT_CHARS = 10000

BLOCKED_COMMAND_PATTERNS = (
    r"\bsudo\b",
    r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f\b",
    r"\bmkfs\b",
    r"\bshutdown\b",
    r"\breboot\b",
    r":\(\)\s*\{",
    r"\bdd\s+if=",
    r"curl\s+[^|]*\|\s*(ba)?sh",
    r"wget\s+[^|]*\|\s*(ba)?sh",
    r"\bchmod\s+777\b",
)

SERVER_PATTERNS = (
    r"\bflask(\s+--app)?\s+run\b",
    r"\buvicorn\b",
    r"\bgunicorn\b",
    r"\bhypercorn\b",
    r"\bpython[0-9.]*\s+\S*app\.py\b",
    r"\bnpm\s+start\b",
    r"\bnpx\s+(serve|next|vite|nuxt)\b",
    r"\bstreamlit\s+run\b",
)


_PIP_PREFIX = re.compile(
    r"^(?:pip[0-9.]*|python[0-9.]*\s+-m\s+pip)\b",
    re.IGNORECASE,
)
_PYTHON_PREFIX = re.compile(r"^python[0-9.]*\b", re.IGNORECASE)
_FLASK_PREFIX = re.compile(r"^flask\b", re.IGNORECASE)


def deny_command(command: str) -> str | None:
    stripped = command.strip()

    if not stripped:
        return "Blocked by middleware: command is empty"

    for pattern in BLOCKED_COMMAND_PATTERNS:
        if re.search(pattern, stripped, flags=re.IGNORECASE):
            return f"Blocked by middleware: {command} is dangerous according to our security policy"

    return None

def looks_like_server(command: str) -> bool:
    return any(re.search(pattern, command, flags=re.IGNORECASE) for pattern in SERVER_PATTERNS)



def rewrite_command(command: str) -> str:
    stripped = command.strip()
    exec = shlex.quote(sys.executable)
    if _PIP_PREFIX.match(stripped):
        return _PIP_PREFIX.sub(f"{exec} -m pip", stripped, count=1)
    if _PYTHON_PREFIX.match(stripped):
        return _PYTHON_PREFIX.sub(exec, stripped, count=1)
    if _FLASK_PREFIX.match(stripped):
        return _FLASK_PREFIX.sub(f"{exec} -m flask", stripped, count=1)
    return command


def _clip(text: str) -> str:
    if len(text) <= MAX_OUTPUT_CHARS:
        return text 
    return text[:MAX_OUTPUT_CHARS] + "\n .....(truncated)"

def _run_foreground(command: str, timeout: int) -> str:
    cwd = get_work_dir()
    cwd.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")

    try:
        completed = subprocess.run(
            ["/bin/bash", "-lc", command],
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or "") + (e.stderr or "")
        return (
            f"Timed out after {timeout}s (process killed).\n"
            "If this is a server, rerun with background=true.\n"
            f"{_clip(str(out))}"
        )
    
    chunks = []
    if completed.stdout:
        chunks.append(completed.stdout.rstrip())
    if completed.stderr:
        chunks.append(completed.stderr.rstrip())
    body = "\n".join(chunks) if chunks else "No output"
    return f"exit_code={completed.returncode}\ncwd={cwd}\n{_clip(body)}"

def _run_background(command: str) -> str:
    cwd = get_work_dir()
    cwd.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    log_dir = cwd / ".agent_jobs"
    log_dir.mkdir(parents=True, exist_ok=True)

    stamp = now_iso().replace(":", "").replace("+", "")
    tmp_log = log_dir / f"pending-{stamp}.log"
    log_file = tmp_log.open("w", encoding="utf-8")

    try: 
        proc = subprocess.Popen(
            ["/bin/bash", "-lc", command],
            cwd=cwd,
            env=env,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    finally:
        log_file.close()
    
    log_path = log_dir / f"{proc.pid}.log"
    tmp_log.rename(log_path)
    register(
        BackgroundJob(
            pid=proc.pid,
            command=command,
            log_path=log_path,
            started_at=now_iso(),
            proc=proc
        )
    )
    time.sleep(1)
    tail = read_log_tail(log_path)
    if proc.poll() is not None:
        stop_pid(proc.pid)
        return (
            f"Background command exited immediately with pid={proc.pid} code {proc.returncode}.\n"
            f"{_clip(tail)}"
        )
    urls = re.findall(r"https?://[^\s]+", tail)
    url_line = f"Open in the browser: {urls[0]}\n" if urls else (
        "No URLs found in the log. Check the logs for URLs or check list_jobs if it is blank.\n"
    )

    return (
        f"{url_line}\n"
        f"Started background job with pid={proc.pid} command={command}.\n"
        f"cwd={cwd}\n"
        f"log={log_path}\n"
        f"Use list_jobs / stop_job to manage it"
        f"-------------Output so far-------------:\n"
        f"{_clip(tail)}"
        f"----------------------------------------"
    )


def run_shell_command(command: str, background: bool = False) -> str:
    command = rewrite_command(command)
    if not background:
        return _run_foreground(command, timeout=60)
    return _run_background(command)

@tool
def stop_job(pid: int) -> str:
    """
    Stop a background job previously started by run_command

    Args:
        pid: The process ID of the job to stop
    """

    return stop_pid(pid)

@tool 
def list_jobs() -> str:
    """
    List background processed started by run _command (mainly servers and long jobs).
    """

    jobs = all_jobs()

    if not jobs:
        return "No background jobs found" 
    lines = []
    for job in jobs:
        state = "running" if is_alive(job.pid) else "exited"
        lines.append(
            f"pid={job.pid} state={state} started_at={job.started_at} cmd={job.command}"
        )

        tail = read_log_tail(job.log_path, max_chars=1000)
        if tail:
            lines.append(tail.rstrip())
            lines.append("----------------------------------------")
    
    return "\n".join(lines)

@tool 
def run_command(command: str, background: bool = False, timeout_seconds: int = 0) -> str:
    """
    Run a bash command in the current working directory (host machine not a sandbox).

    Foregorund commands wait for completion. Set background=True to run in the background mainly for servers (flask, uvicorn, npm start etc)
    so they keep running. Server like commands are auto background even if you forget to set background=True.

    Args:
        command: Bash command to run, e.g. "python3 -m http.server 8000"
        baclground: Run in the background (default: False) If true, start the process and return a pid immediately.
        timeout_seconds: Foreground timeout. 0 uses the default 30s timeout.

    """

    blocked = deny_command(command)
    if blocked:
        return blocked

    timeout = timeout_seconds if timeout_seconds > 0 else 30
    background = bool(background) or looks_like_server(command)
    command = rewrite_command(command)
    if background:
        return _run_background(command)
    return _run_foreground(command, timeout=timeout)