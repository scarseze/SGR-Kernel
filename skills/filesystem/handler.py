import os
from typing import Type

from pydantic import BaseModel

from core.execution import ExecutionState
from skills.base import BaseSkill, SkillMetadata
from skills.filesystem.schema import ListDirInput, ReadFileInput, WriteFileInput

# Security: Basic allowed paths check
ALLOWED_ROOTS = ["C:/Users/macht/SA", "C:/Users/macht/Scar", "C:\\Users\\macht\\SA", "C:\\Users\\macht\\Scar", "D:\\"]


def is_safe_path(path: str) -> bool:
    try:
        abs_path = os.path.abspath(path)
        return any(abs_path.startswith(os.path.abspath(root)) for root in ALLOWED_ROOTS)
    except Exception:
        return False


class ReadFileSkill(BaseSkill[BaseModel]):
    name: str = "read_file"
    description: str = (
        "Reads the content of a file from the local filesystem. "
        "Use this when you need to inspect existing code or configuration files."
    )

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            capabilities=["file_read", "code_browsing"],
            risk_level="low",
            side_effects=False,
            idempotent=True,
            requires_network=False,
            requires_filesystem=True,
            cost_class="cheap",
        )

    @property
    def input_schema(self) -> Type[BaseModel]:
        return ReadFileInput

    async def execute(self, params: ReadFileInput, state: ExecutionState) -> str:
        if not is_safe_path(params.file_path):
            return f"Error: Access denied. Path '{params.file_path}' is outside allowed directories."

        if not os.path.exists(params.file_path):
            return f"Error: File not found at '{params.file_path}'"

        if not os.path.isfile(params.file_path):
            return f"Error: '{params.file_path}' is not a file."

        try:
            with open(params.file_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            content = "".join(lines[: params.max_lines])
            if len(lines) > params.max_lines:
                content += f"\n\n... (Truncated. File has {len(lines)} lines, shown first {params.max_lines})"

            return f"### File Content: {params.file_path}\n```\n{content}\n```"
        except Exception as e:
            return f"Error reading file: {str(e)}"


class ListDirSkill(BaseSkill[BaseModel]):
    name: str = "list_dir"
    description: str = (
        "Lists files and subdirectories in a given directory. "
        "Use this to explore the project structure and find relevant files."
    )

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            capabilities=["file_browsing", "discovery"],
            risk_level="low",
            side_effects=False,
            idempotent=True,
            requires_network=False,
            requires_filesystem=True,
            cost_class="cheap",
        )

    @property
    def input_schema(self) -> Type[BaseModel]:
        return ListDirInput

    async def execute(self, params: ListDirInput, state: ExecutionState) -> str:
        if not is_safe_path(params.dir_path):
            return f"Error: Access denied. Path '{params.dir_path}' is outside allowed directories."

        if not os.path.exists(params.dir_path):
            return f"Error: Directory not found at '{params.dir_path}'"

        if not os.path.isdir(params.dir_path):
            return f"Error: '{params.dir_path}' is not a directory."

        try:
            items = os.listdir(params.dir_path)
            files = []
            dirs = []

            for item in items:
                full_path = os.path.join(params.dir_path, item)
                if os.path.isdir(full_path):
                    dirs.append(item + "/")
                else:
                    files.append(item)

            dirs.sort()
            files.sort()

            output = [f"### Directory Listing: {params.dir_path}"]
            if dirs:
                output.append("**Directories:**")
                output.extend([f"- {d}" for d in dirs])
            if files:
                output.append("\n**Files:**")
                output.extend([f"- {f}" for f in files])

            return "\n".join(output)
        except Exception as e:
            return f"Error listing directory: {str(e)}"


class WriteFileSkill(BaseSkill[BaseModel]):
    name: str = "write_file"
    description: str = (
        "Writes content to a file on the local filesystem. "
        "Will overwrite the file if it already exists. "
        "Useful for generating reports, code files, or Mermaid diagrams (.mmd)."
    )

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            capabilities=["file_write", "document_generation"],
            risk_level="medium",
            side_effects=True,
            idempotent=True,
            requires_network=False,
            requires_filesystem=True,
            cost_class="cheap",
        )

    @property
    def input_schema(self) -> Type[BaseModel]:
        return WriteFileInput

    async def execute(self, params: WriteFileInput, state: ExecutionState) -> str:
        if not is_safe_path(params.file_path):
            return f"Error: Access denied. Path '{params.file_path}' is outside allowed directories."

        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(params.file_path), exist_ok=True)
            
            with open(params.file_path, "w", encoding="utf-8") as f:
                f.write(params.content)
            
            return f"✅ Successfully wrote file up to {len(params.content)} characters to '{params.file_path}'"
        except Exception as e:
            return f"Error writing file: {str(e)}"
