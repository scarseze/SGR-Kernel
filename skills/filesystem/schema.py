from pydantic import BaseModel, Field


class ReadFileInput(BaseModel):
    file_path: str = Field(description="The absolute or relative path to the file to read.")
    max_lines: int = Field(default=500, description="Maximum number of lines to read to avoid memory overload.")


class ListDirInput(BaseModel):
    dir_path: str = Field(description="The absolute or relative path to the directory to list.")


class WriteFileInput(BaseModel):
    file_path: str = Field(description="The absolute path to the file to create or overwrite.")
    content: str = Field(description="The full content to write to the file. Example: 'C:/Users/macht/SA'")
