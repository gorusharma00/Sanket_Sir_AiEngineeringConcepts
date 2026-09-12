from tools.paths import resolve_work_path
from langchain.tools import tool

@tool
def read_file(path: str) -> str:
    """
    Reads a UTF-8 text file from the working directory.

    Args:
        path: Relative path of the file, e.g. 'src/App.js' or 'README.md' or 'data/example.json'
    """

    try:
        file_path = resolve_work_path(path) # We are checking if the path given to read is a valid path inside the working directory -> workspace or not
    except ValueError as err:
        raise ValueError(f"Path escapes working directory: {err}")

    try:
        return file_path.read_text(encoding="utf-8") # go and read the file
    except FileNotFoundError:
        raise FileNotFoundError(f"File not found: {path}")
    except PermissionError:
        raise PermissionError(f"Permission denied: {path}")
    except Exception as err:
        raise Exception(f"Error reading file: {err}")