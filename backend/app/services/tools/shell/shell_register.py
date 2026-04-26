"""
Shell Tool Registration Module

This module registers all shell-related tools to the global tool registry.
Tools in this category execute shell commands and return results.
"""

from app.services.tools.registry import tool_registry
from app.services.tools.shell import ShellExecutor

# Register shell tools
shell_register = tool_registry.register_category("shell")

@shell_register("execute_command")
def execute_shell_command(command: str, cwd: str = None, timeout: int = 30) -> dict:
    """Execute a shell command and return the result.
    
    Args:
        command: Shell command to execute
        cwd: Working directory (optional)
        timeout: Timeout in seconds (default: 30)
    
    Returns:
        dict: {"stdout": str, "stderr": str, "returncode": int}
    """
    executor = ShellExecutor()
    return executor.execute(command, cwd=cwd, timeout=timeout)

@shell_register("list_directory")
def list_directory(path: str = ".") -> dict:
    """List directory contents.
    
    Args:
        path: Directory path to list
    
    Returns:
        dict: {"files": [str], "directories": [str]}
    """
    executor = ShellExecutor()
    return executor.list_dir(path)

@shell_register("get_working_directory")
def get_working_directory() -> dict:
    """Get current working directory.
    
    Returns:
        dict: {"path": str}
    """
    executor = ShellExecutor()
    return executor.get_cwd()

@shell_register("change_directory")
def change_directory(path: str) -> dict:
    """Change working directory.
    
    Args:
        path: Directory path to change to
    
    Returns:
        dict: {"success": bool, "path": str}
    """
    executor = ShellExecutor()
    return executor.cd(path)

@shell_register("check_path_exists")
def check_path_exists(path: str) -> dict:
    """Check if a path exists.
    
    Args:
        path: Path to check
    
    Returns:
        dict: {"exists": bool, "is_file": bool, "is_directory": bool}
    """
    executor = ShellExecutor()
    return executor.check_exists(path)