from tools.write_file import write_file
from tools.edit_file import edit_file
from tools.read_file import read_file
from tools.list_files import list_files
from tools.shell import run_command, stop_job, list_jobs

ALL_TOOLS = [
    write_file,
    edit_file,
    read_file,
    list_files,
    run_command,
    stop_job,
    list_jobs,
]

def tool_catalog() -> list[dict[str, str]]:
    """Name + Description for all tools"""
    return [{"name": tool.name, "description": tool.description} for tool in ALL_TOOLS]