from pydantic import BaseModel, Field

class ExecuteSQLInput(BaseModel):
    query: str = Field(description="The SQL query to execute against the local SQLite database.")
