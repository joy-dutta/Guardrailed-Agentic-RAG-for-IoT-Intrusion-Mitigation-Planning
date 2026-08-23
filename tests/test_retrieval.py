from iot_poc.retrieval import Chunk, StandardsRetriever, chunk_text_blocks, compact_excerpt


def test_chunking_is_stable_and_overlapping() -> None:
    text = "0123456789" * 4
    chunks = chunk_text_blocks(text, chunk_chars=15, chunk_overlap=5)
    assert chunks[0][-5:] == chunks[1][:5]
    assert "".join([chunks[0], chunks[1][5:], chunks[2][5:], chunks[3][5:]]) == text


def test_retriever_ranks_relevant_guidance_first() -> None:
    retriever = StandardsRetriever(
        [
            Chunk("a", "a-1", "restrict compromised IoT device network communication"),
            Chunk("b", "b-1", "password length and user interface settings"),
        ]
    )
    result = retriever.retrieve("restrict compromised IoT network communication", top_k=1)
    assert result[0]["chunk_id"] == "a-1"


def test_excerpt_centers_on_query_match_instead_of_chunk_prefix() -> None:
    text = "general introduction " * 50 + "SQL injection must be prevented by validating input data"
    excerpt = compact_excerpt(text, max_chars=180, query="SQL injection input validation")
    assert "SQL injection" in excerpt
    assert "validating input data" in excerpt
