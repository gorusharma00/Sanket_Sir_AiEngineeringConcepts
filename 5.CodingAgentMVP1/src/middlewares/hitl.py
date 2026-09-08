from langchain.agents.middleware import HumanInTheLoopMiddleware

def build_hitl_middleware() -> HumanInTheLoopMiddleware:
    return HumanInTheLoopMiddleware(
        interrupt_on={
            "read_file": False, # no hitl for read_file tool
            "list_files": False, # no hitl for list_files tool
            "write_file": {
                "allowed_decisions": ["approve", "edit", "reject"],
                "description": "Write or overwrite a file on disk"
            },
            "edit_file": {
                "allowed_decisions": ["approve", "edit", "reject"],
                "description": "Edit an existing file on the disk"
            }
        },
        description_prefix="Coding agent needs your approval to move ahead"
    )