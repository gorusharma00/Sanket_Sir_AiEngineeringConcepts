import json
import os
from pathlib import Path
from langchain.tools import tool

from config.config import get_work_dir
from tools.paths import resolve_work_path

@tool
def list_files(path: str = ".") -> str:
    """
    List files and directories under a given path in the working directory.

    Args:
        path: Relative directory to list. Default to the working-dorectory root. 
    """

    work_dir = get_work_dir()

    try:
        base_path = resolve_work_path(path)
    except ValueError as err:
        return json.dumps({"error": f"Path escapes working directory: {err}"})

    if not base_path.exists():
        return json.dumps({"error": f"Path {path!r} does not exist"})
    if not base_path.is_dir():
        return json.dumps({"error": f"Path {path!r} is not a directory"})

    result: list[str] = []

    for root, dirs, files in os.walk(base_path):
        root_path = Path(root)
        rel_root = root_path.relative_to(work_dir)

        for dir_name in sorted(dirs):
            result.append(f"{(rel_root / dir_name).as_posix()}/")
        for file_name in sorted(files):
            result.append(f"{(rel_root / file_name).as_posix()}")


    return json.dumps(result)

list_files()
    