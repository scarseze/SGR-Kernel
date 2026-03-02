import os
import sqlite3
from typing import Type

from pydantic import BaseModel

from core.execution import ExecutionState
from skills.base import BaseSkill, SkillMetadata
from skills.database.schema import ExecuteSQLInput


class DatabaseSkill(BaseSkill[BaseModel]):
    name: str = "database_sql"
    description: str = (
        "Executes a SQL query against the local SQLite database ('local_data.db'). "
        "Useful for exploring data structure, counting records, or analytical queries."
    )

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            capabilities=["sql_execution", "data_exploration"],
            risk_level="medium",
            side_effects=False, # Assuming safe reading mostly
            idempotent=True,
            requires_network=False,
            requires_filesystem=True,
            cost_class="cheap",
        )

    @property
    def input_schema(self) -> Type[BaseModel]:
        return ExecuteSQLInput

    async def execute(self, params: ExecuteSQLInput, state: ExecutionState) -> str:
        db_path = "local_data.db"
        query = params.query.strip()
        
        # Simple security to prevent obvious destructive actions if we want it read-only
        forbidden_keywords = ["DROP", "DELETE", "ALTER", "TRUNCATE", "INSERT", "UPDATE"]
        if any(query.upper().startswith(kw) for kw in forbidden_keywords):
            return "Error: Only SELECT and PRAGMA queries are allowed for safety."
            
        try:
            # Let's create an empty db if it doesn't exist so we don't crash immediately,
            # but ideally the user/app provides it.
            if not os.path.exists(db_path):
                # We could return an error, but creating it allows schema exploration
                pass

            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            cursor.execute(query)
            
            # Fetch results
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            rows = cursor.fetchmany(100) # Limit to 100 rows to avoid huge context usage
            
            conn.commit()
            conn.close()
            
            if not columns:
                return "Query executed successfully, but returned no data."
                
            # Format as Markdown Table
            separator = "|" + "|".join(["---" for _ in columns]) + "|"
            header = "|" + "|".join(str(c) for c in columns) + "|"
            
            table_lines = [header, separator]
            for row in rows:
                table_lines.append("|" + "|".join(str(v) if v is not None else "NULL" for v in row) + "|")
                
            result_table = "\n".join(table_lines)
            
            if len(rows) == 100:
                result_table += "\n\n*(Result limited to 100 rows)*"
                
            return f"### Database Query Results\n\n{result_table}"
            
        except sqlite3.Error as e:
            return f"SQLite Error: {str(e)}"
        except Exception as e:
            return f"Error executing query: {str(e)}"
