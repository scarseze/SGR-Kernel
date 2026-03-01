from pydantic import BaseModel, Field

class SearchKnowledgeBase(BaseModel):
    query: str = Field(
        ...,
        description="The semantic search query to look up in the vector database. Provide a detailed natural language question or keywords.",
    )
    top_k: int = Field(
        default=3,
        description="The maximum number of document chunks to retrieve.",
    )
