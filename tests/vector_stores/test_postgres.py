import asyncio
from typing import Any, Dict, Generator, List, Union

import pytest

from llama_index.schema import NodeRelationship, RelatedNodeInfo, TextNode
from llama_index.vector_stores import PGVectorStore
from llama_index.vector_stores.types import (
    ExactMatchFilter,
    MetadataFilters,
    NodeWithEmbedding,
    VectorStoreQuery,
    VectorStoreQueryMode,
)

# from testing find install here https://github.com/pgvector/pgvector#installation-notes


PARAMS: Dict[str, Union[str, int]] = dict(
    host="localhost", user="postgres", password="password", port=5432
)
TEST_DB = "test_vector_db"
TEST_TABLE_NAME = "lorem_ipsum"
TEST_EMBED_DIM = 2


try:
    import asyncpg  # noqa: F401
    import pgvector  # noqa: F401
    import psycopg2  # noqa: F401
    import sqlalchemy  # noqa: F401
    import sqlalchemy.ext.asyncio  # noqa: F401

    # connection check
    conn__ = psycopg2.connect(**PARAMS)  # type: ignore
    conn__.close()

    postgres_not_available = False
except (ImportError, Exception):
    postgres_not_available = True


def _get_sample_vector(num: float) -> List[float]:
    """
    Get sample embedding vector of the form [num, 1, 1, ..., 1]
    where the length of the vector is TEST_EMBED_DIM.
    """
    return [num] + [1.0] * (TEST_EMBED_DIM - 1)


@pytest.fixture(scope="session")
def conn() -> Any:
    import psycopg2

    conn_ = psycopg2.connect(**PARAMS)  # type: ignore
    return conn_


@pytest.fixture()
def db(conn: Any) -> Generator:
    conn.autocommit = True

    with conn.cursor() as c:
        c.execute(f"DROP DATABASE IF EXISTS {TEST_DB}")
        c.execute(f"CREATE DATABASE {TEST_DB}")
        conn.commit()
    yield
    with conn.cursor() as c:
        c.execute(f"DROP DATABASE {TEST_DB}")
        conn.commit()


@pytest.fixture
def pg(db: None) -> Any:
    pg = PGVectorStore.from_params(
        **PARAMS,  # type: ignore
        database=TEST_DB,
        table_name=TEST_TABLE_NAME,
        embed_dim=TEST_EMBED_DIM,
    )

    yield pg

    asyncio.run(pg.close())


@pytest.fixture
def pg_hybrid(db: None) -> Any:
    pg = PGVectorStore.from_params(
        **PARAMS,  # type: ignore
        database=TEST_DB,
        table_name=TEST_TABLE_NAME,
        hybrid_search=True,
        embed_dim=TEST_EMBED_DIM,
    )

    yield pg

    asyncio.run(pg.close())


@pytest.fixture(scope="session")
def node_embeddings() -> List[NodeWithEmbedding]:
    return [
        NodeWithEmbedding(
            embedding=_get_sample_vector(1.0),
            node=TextNode(
                text="lorem ipsum",
                id_="aaa",
                relationships={NodeRelationship.SOURCE: RelatedNodeInfo(node_id="aaa")},
            ),
        ),
        NodeWithEmbedding(
            embedding=_get_sample_vector(0.1),
            node=TextNode(
                text="dolor sit amet",
                id_="bbb",
                relationships={NodeRelationship.SOURCE: RelatedNodeInfo(node_id="bbb")},
                extra_info={"test_key": "test_value"},
            ),
        ),
    ]


@pytest.fixture(scope="session")
def hybrid_node_embeddings() -> List[NodeWithEmbedding]:
    return [
        NodeWithEmbedding(
            embedding=_get_sample_vector(0.1),
            node=TextNode(
                text="lorem ipsum",
                id_="aaa",
                relationships={NodeRelationship.SOURCE: RelatedNodeInfo(node_id="aaa")},
            ),
        ),
        NodeWithEmbedding(
            embedding=_get_sample_vector(1.0),
            node=TextNode(
                text="dolor sit amet",
                id_="bbb",
                relationships={NodeRelationship.SOURCE: RelatedNodeInfo(node_id="bbb")},
                extra_info={"test_key": "test_value"},
            ),
        ),
        NodeWithEmbedding(
            embedding=_get_sample_vector(5.0),
            node=TextNode(
                text="The quick brown fox jumped over the lazy dog.",
                id_="ccc",
                relationships={NodeRelationship.SOURCE: RelatedNodeInfo(node_id="ccc")},
            ),
        ),
        NodeWithEmbedding(
            embedding=_get_sample_vector(10.0),
            node=TextNode(
                text="The fox and the hound",
                id_="ddd",
                relationships={NodeRelationship.SOURCE: RelatedNodeInfo(node_id="ddd")},
                extra_info={"test_key": "test_value"},
            ),
        ),
    ]


@pytest.mark.skipif(postgres_not_available, reason="postgres db is not available")
@pytest.mark.asyncio
async def test_instance_creation(db: None) -> None:
    pg = PGVectorStore.from_params(
        **PARAMS,  # type: ignore
        database=TEST_DB,
        table_name=TEST_TABLE_NAME,
    )
    assert isinstance(pg, PGVectorStore)
    await pg.close()


@pytest.mark.skipif(postgres_not_available, reason="postgres db is not available")
@pytest.mark.asyncio
@pytest.mark.parametrize("use_async", [True, False])
async def test_add_to_db_and_query(
    pg: PGVectorStore, node_embeddings: List[NodeWithEmbedding], use_async: bool
) -> None:
    if use_async:
        await pg.async_add(node_embeddings)
    else:
        pg.add(node_embeddings)
    assert isinstance(pg, PGVectorStore)
    q = VectorStoreQuery(query_embedding=_get_sample_vector(1.0), similarity_top_k=1)
    if use_async:
        res = await pg.aquery(q)
    else:
        res = pg.query(q)
    assert res.nodes
    assert len(res.nodes) == 1
    assert res.nodes[0].node_id == "aaa"


@pytest.mark.skipif(postgres_not_available, reason="postgres db is not available")
@pytest.mark.asyncio
@pytest.mark.parametrize("use_async", [True, False])
async def test_add_to_db_and_query_with_metadata_filters(
    pg: PGVectorStore, node_embeddings: List[NodeWithEmbedding], use_async: bool
) -> None:
    if use_async:
        await pg.async_add(node_embeddings)
    else:
        pg.add(node_embeddings)
    assert isinstance(pg, PGVectorStore)
    filters = MetadataFilters(
        filters=[ExactMatchFilter(key="test_key", value="test_value")]
    )
    q = VectorStoreQuery(
        query_embedding=_get_sample_vector(0.5), similarity_top_k=10, filters=filters
    )
    if use_async:
        res = await pg.aquery(q)
    else:
        res = pg.query(q)
    assert res.nodes
    assert len(res.nodes) == 1
    assert res.nodes[0].node_id == "bbb"


@pytest.mark.skipif(postgres_not_available, reason="postgres db is not available")
@pytest.mark.asyncio
@pytest.mark.parametrize("use_async", [True, False])
async def test_add_to_db_query_and_delete(
    pg: PGVectorStore, node_embeddings: List[NodeWithEmbedding], use_async: bool
) -> None:
    if use_async:
        await pg.async_add(node_embeddings)
    else:
        pg.add(node_embeddings)
    assert isinstance(pg, PGVectorStore)

    q = VectorStoreQuery(query_embedding=_get_sample_vector(0.1), similarity_top_k=1)

    if use_async:
        res = await pg.aquery(q)
    else:
        res = pg.query(q)
    assert res.nodes
    assert len(res.nodes) == 1
    assert res.nodes[0].node_id == "bbb"
    pg.delete("bbb")

    if use_async:
        res = await pg.aquery(q)
    else:
        res = pg.query(q)
    assert res.nodes
    assert len(res.nodes) == 1
    assert res.nodes[0].node_id == "aaa"


@pytest.mark.skipif(postgres_not_available, reason="postgres db is not available")
@pytest.mark.asyncio
@pytest.mark.parametrize("use_async", [True, False])
async def test_sparse_query(
    pg_hybrid: PGVectorStore,
    hybrid_node_embeddings: List[NodeWithEmbedding],
    use_async: bool,
) -> None:
    if use_async:
        await pg_hybrid.async_add(hybrid_node_embeddings)
    else:
        pg_hybrid.add(hybrid_node_embeddings)
    assert isinstance(pg_hybrid, PGVectorStore)

    # text search should work when query is a sentence and not just a single word
    q = VectorStoreQuery(
        query_embedding=_get_sample_vector(0.1),
        query_str="who is the fox?",
        sparse_top_k=2,
        mode=VectorStoreQueryMode.SPARSE,
    )

    if use_async:
        res = await pg_hybrid.aquery(q)
    else:
        res = pg_hybrid.query(q)
    assert res.nodes
    assert len(res.nodes) == 2
    assert res.nodes[0].node_id == "ccc"
    assert res.nodes[1].node_id == "ddd"


@pytest.mark.skipif(postgres_not_available, reason="postgres db is not available")
@pytest.mark.asyncio
@pytest.mark.parametrize("use_async", [True, False])
async def test_hybrid_query(
    pg_hybrid: PGVectorStore,
    hybrid_node_embeddings: List[NodeWithEmbedding],
    use_async: bool,
) -> None:
    if use_async:
        await pg_hybrid.async_add(hybrid_node_embeddings)
    else:
        pg_hybrid.add(hybrid_node_embeddings)
    assert isinstance(pg_hybrid, PGVectorStore)

    q = VectorStoreQuery(
        query_embedding=_get_sample_vector(0.1),
        query_str="fox",
        similarity_top_k=2,
        mode=VectorStoreQueryMode.HYBRID,
        sparse_top_k=1,
    )

    if use_async:
        res = await pg_hybrid.aquery(q)
    else:
        res = pg_hybrid.query(q)
    assert res.nodes
    assert len(res.nodes) == 3
    assert res.nodes[0].node_id == "aaa"
    assert res.nodes[1].node_id == "bbb"
    assert res.nodes[2].node_id == "ccc"

    # if sparse_top_k is not specified, it should default to similarity_top_k
    q = VectorStoreQuery(
        query_embedding=_get_sample_vector(0.1),
        query_str="fox",
        similarity_top_k=2,
        mode=VectorStoreQueryMode.HYBRID,
    )

    if use_async:
        res = await pg_hybrid.aquery(q)
    else:
        res = pg_hybrid.query(q)
    assert res.nodes
    assert len(res.nodes) == 4
    assert res.nodes[0].node_id == "aaa"
    assert res.nodes[1].node_id == "bbb"
    assert res.nodes[2].node_id == "ccc"
    assert res.nodes[3].node_id == "ddd"

    # text search should work when query is a sentence and not just a single word
    q = VectorStoreQuery(
        query_embedding=_get_sample_vector(0.1),
        query_str="who is the fox?",
        similarity_top_k=2,
        mode=VectorStoreQueryMode.HYBRID,
    )

    if use_async:
        res = await pg_hybrid.aquery(q)
    else:
        res = pg_hybrid.query(q)
    assert res.nodes
    assert len(res.nodes) == 4
    assert res.nodes[0].node_id == "aaa"
    assert res.nodes[1].node_id == "bbb"
    assert res.nodes[2].node_id == "ccc"
    assert res.nodes[3].node_id == "ddd"


@pytest.mark.skipif(postgres_not_available, reason="postgres db is not available")
@pytest.mark.asyncio
@pytest.mark.parametrize("use_async", [True, False])
async def test_add_to_db_and_hybrid_query_with_metadata_filters(
    pg_hybrid: PGVectorStore,
    hybrid_node_embeddings: List[NodeWithEmbedding],
    use_async: bool,
) -> None:
    if use_async:
        await pg_hybrid.async_add(hybrid_node_embeddings)
    else:
        pg_hybrid.add(hybrid_node_embeddings)
    assert isinstance(pg_hybrid, PGVectorStore)
    filters = MetadataFilters(
        filters=[ExactMatchFilter(key="test_key", value="test_value")]
    )
    q = VectorStoreQuery(
        query_embedding=_get_sample_vector(0.1),
        query_str="fox",
        similarity_top_k=10,
        filters=filters,
        mode=VectorStoreQueryMode.HYBRID,
    )
    if use_async:
        res = await pg_hybrid.aquery(q)
    else:
        res = pg_hybrid.query(q)
    assert res.nodes
    assert len(res.nodes) == 2
    assert res.nodes[0].node_id == "bbb"
    assert res.nodes[1].node_id == "ddd"


@pytest.mark.skipif(postgres_not_available, reason="postgres db is not available")
def test_hybrid_query_fails_if_no_query_str_provided(
    pg_hybrid: PGVectorStore, hybrid_node_embeddings: List[NodeWithEmbedding]
) -> None:
    q = VectorStoreQuery(
        query_embedding=_get_sample_vector(1.0),
        similarity_top_k=10,
        mode=VectorStoreQueryMode.HYBRID,
    )

    with pytest.raises(Exception) as exc:
        pg_hybrid.query(q)

        assert str(exc) == "query_str must be specified for a sparse vector query."
