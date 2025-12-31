"""
Production LightRAG configuration.

Configures PostgreSQL (KV + Vector) and Neo4j (Graph) storage backends.
"""
import os
from typing import Dict, Any

# Environment variables
POSTGRES_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_PORT", "5432")),
    "user": os.getenv("POSTGRES_USER", "postgres"),
    "password": os.getenv("POSTGRES_PASSWORD"),
    "database": os.getenv("POSTGRES_DATABASE", "lightrag_prod"),
    "max_connections": int(os.getenv("POSTGRES_MAX_CONNECTIONS", "20")),
    "embedding_batch_num": int(os.getenv("LIGHTRAG_EMBEDDING_BATCH_NUM", "100")),
    "max_async": int(os.getenv("LIGHTRAG_MAX_ASYNC", "16")),
    "max_tokens": int(os.getenv("LIGHTRAG_MAX_TOKENS", "32768")),
    # Vector storage specific settings (nested in vector_db_storage_cls_kwargs)
    "vector_db_storage_cls_kwargs": {
        "cosine_better_than_threshold": float(os.getenv("LIGHTRAG_COSINE_THRESHOLD", "0.2"))
    }
}

NEO4J_CONFIG = {
    "uri": os.getenv("NEO4J_URI"),
    "username": os.getenv("NEO4J_USERNAME", "neo4j"),
    "password": os.getenv("NEO4J_PASSWORD"),
}

WORKSPACE = os.getenv("LIGHTRAG_WORKSPACE", "telegram_bot")
EMBEDDING_DIMENSION = int(os.getenv("LIGHTRAG_EMBEDDING_DIM", "1536"))  # text-embedding-3-small


def get_storage_config(storage_type: str, topic_name: str = None) -> Dict[str, Any]:
    """
    Get storage configuration for a specific storage type.

    Args:
        storage_type: One of "kv", "vector", "graph", "doc_status"
        topic_name: Optional topic name for namespace isolation

    Returns:
        Storage configuration dict
    """
    namespace = f"{storage_type}_{topic_name}" if topic_name else storage_type

    if storage_type in ["kv", "vector", "doc_status"]:
        return {
            "config": POSTGRES_CONFIG,
            "namespace": namespace,
            "workspace": WORKSPACE
        }
    elif storage_type == "graph":
        return {
            "config": NEO4J_CONFIG,
            "namespace": namespace,
            "workspace": WORKSPACE
        }
    else:
        raise ValueError(f"Unknown storage type: {storage_type}")


# Storage class imports (conditional - only import if dependencies available)
def get_kv_storage(topic_name: str, embedding_func):
    """
    Get production KV storage (PostgreSQL).

    Args:
        topic_name: Topic name for workspace isolation
        embedding_func: Embedding function from LightRAG

    Returns:
        PGKVStorage instance
    """
    try:
        from lightrag.kg.postgres_impl import PGKVStorage
        from lightrag.namespace import NameSpace

        # Use standard namespace, topic isolation via workspace
        return PGKVStorage(
            namespace=NameSpace.KV_STORE_FULL_DOCS,
            workspace=f"{WORKSPACE}_{topic_name}",
            global_config=POSTGRES_CONFIG,
            embedding_func=embedding_func
        )
    except ImportError as e:
        raise ImportError(
            "PostgreSQL storage dependencies not installed. "
            "Run: pip install psycopg2-binary asyncpg pgvector"
        ) from e


def get_vector_storage(topic_name: str, embedding_func):
    """
    Get production vector storage (pgvector).

    Args:
        topic_name: Topic name for workspace isolation
        embedding_func: Embedding function from LightRAG

    Returns:
        PGVectorStorage instance
    """
    try:
        from lightrag.kg.postgres_impl import PGVectorStorage
        from lightrag.namespace import NameSpace

        # Use standard namespace, topic isolation via workspace
        return PGVectorStorage(
            namespace=NameSpace.VECTOR_STORE_CHUNKS,
            workspace=f"{WORKSPACE}_{topic_name}",
            global_config=POSTGRES_CONFIG,
            embedding_func=embedding_func
        )
    except ImportError as e:
        raise ImportError(
            "pgvector storage dependencies not installed. "
            "Run: pip install psycopg2-binary asyncpg pgvector"
        ) from e


def get_graph_storage(topic_name: str, embedding_func):
    """
    Get production graph storage (Neo4j).

    Args:
        topic_name: Topic name for workspace isolation
        embedding_func: Embedding function from LightRAG

    Returns:
        Neo4JStorage instance
    """
    try:
        from lightrag.kg.neo4j_impl import Neo4JStorage
        from lightrag.namespace import NameSpace

        # Use standard namespace, topic isolation via workspace
        return Neo4JStorage(
            namespace=NameSpace.GRAPH_STORE_CHUNK_ENTITY_RELATION,
            workspace=f"{WORKSPACE}_{topic_name}",
            global_config=NEO4J_CONFIG,
            embedding_func=embedding_func
        )
    except ImportError as e:
        raise ImportError(
            "Neo4j storage dependencies not installed. "
            "Run: pip install neo4j"
        ) from e


def get_doc_status_storage(topic_name: str, embedding_func):
    """
    Get production document status storage (PostgreSQL).

    Args:
        topic_name: Topic name for workspace isolation
        embedding_func: Embedding function from LightRAG

    Returns:
        PGDocStatusStorage instance
    """
    try:
        from lightrag.kg.postgres_impl import PGDocStatusStorage
        from lightrag.namespace import NameSpace

        # Use standard namespace, topic isolation via workspace
        return PGDocStatusStorage(
            namespace=NameSpace.DOC_STATUS,
            workspace=f"{WORKSPACE}_{topic_name}",
            global_config=POSTGRES_CONFIG,
            embedding_func=embedding_func
        )
    except ImportError as e:
        raise ImportError(
            "PostgreSQL storage dependencies not installed. "
            "Run: pip install psycopg2-binary asyncpg"
        ) from e


def validate_config():
    """
    Validate production configuration.

    Raises:
        ValueError: If required environment variables are missing
    """
    errors = []

    # PostgreSQL validation
    if not POSTGRES_CONFIG["password"]:
        errors.append("POSTGRES_PASSWORD not set")
    if not POSTGRES_CONFIG["host"]:
        errors.append("POSTGRES_HOST not set")

    # Neo4j validation
    if not NEO4J_CONFIG["uri"]:
        errors.append("NEO4J_URI not set")
    if not NEO4J_CONFIG["password"]:
        errors.append("NEO4J_PASSWORD not set")

    if errors:
        raise ValueError(
            f"Production configuration incomplete:\n" +
            "\n".join(f"  - {err}" for err in errors)
        )

    return True
