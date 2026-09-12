from fnmatch import fnmatch
from pathlib import Path

from config.config import get_work_dir


BLOCKED_PATH_PATTERNS = [
    ".env",
    ".env.*"
    ".pem",
    ".key",
    ".secret",
    ".git",
    ".git/**",
    "*.log",
    "*.p12"
]

def normalize_path(path: str) -> str:
    normalized = Path(path).as_posix()
    if normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized

def is_blocked_path(path: str) -> bool:
    normalized = normalize_path(path)
    return any(fnmatch(normalized, pattern) for pattern in BLOCKED_PATH_PATTERNS)

def resolve_work_path(path: str) -> Path:
    work_dir = get_work_dir()
    work_dir.mkdir(parents=True, exist_ok=True)
    candidate = (work_dir / path).resolve()
    try:
        candidate.relative_to(work_dir)
    except ValueError as e:
        raise ValueError(f"Path escapes working directory")
    return candidate