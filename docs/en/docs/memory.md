# 🔄 RAG Development Flow

This document describes the RAG (Retrieval-Augmented Generation) development pipeline within the SGR Kernel platform.

## 1. Data Collection & Cleaning (Data Engineer)
1. **Source:** Parsing or exporting documents.
2. **PII Removal:** Processing data through an automated PII removal script (Sandboxed).
3. **Storage:** Saving RAW and CLEANED data into S3 buckets with versioning.

## 2. Chunking & Embeddings (RAG Specialist)
1. **Chunking Strategy:** Implementing a script for text splitting, fixing chunk size and overlap.
2. **Embedding Model:** Selecting the optimal embedding model. 
3. **Execution:** Initializing a job inside SGR Kernel to process CLEANED documents through the Embedding Model. Results are uploaded to the vector database (Milvus/Qdrant).

## 3. Prompt Engineering (RAG Specialist & MLOps)
1. Creating a base prompt in `templates/prompt_template.json`.
2. Defining Capability for SGR Kernel R7. The agent is granted Read-access to the vector database.

## 4. Evaluation (LLM Evaluator & AI Product Owner)
1. Running experimental `manifest.json` with a test dataset.
2. Metric calculation: Context Relevance, Answer Faithfulness (using a strong model as a judge).
3. Quality and cost acceptance (AI Product Owner).

## 5. Deployment (MLOps)
1. Merging the pull request with updated prompts and weights into `main`.
2. SGR Kernel updates the Swarm configuration for Production.
