from app.services.chunking import MAX_CHARS, MAX_TOKENS, MIN_TOKENS, chunk_pages


def para(label: str, chars: int) -> str:
    return (f"{label} " * (chars // (len(label) + 1)))[:chars].strip()


def test_small_text_is_one_chunk_without_pages():
    chunks = chunk_pages([(None, "Hello.\n\nWorld.")])
    assert len(chunks) == 1
    assert chunks[0].chunk_index == 0
    assert chunks[0].text == "Hello.\n\nWorld."
    assert chunks[0].page_start is None and chunks[0].page_end is None


def test_empty_input_gives_no_chunks():
    assert chunk_pages([(1, "  \n\n "), (2, "")]) == []


def test_breaks_on_paragraph_boundaries_and_respects_max():
    paragraphs = [para(f"p{i}", 1500) for i in range(10)]
    chunks = chunk_pages([(None, "\n\n".join(paragraphs))])
    assert len(chunks) > 1
    for c in chunks:
        assert len(c.text) <= MAX_CHARS
        # every chunk is made of whole paragraphs
        assert all(p in paragraphs for p in c.text.split("\n\n"))
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
    assert "\n\n".join(c.text for c in chunks) == "\n\n".join(paragraphs)


def test_page_ranges_are_recorded():
    pages = [(n, para(f"page{n}", 1500)) for n in range(1, 7)]  # 6 pages, ~1500 chars each
    chunks = chunk_pages(pages)
    assert len(chunks) >= 2
    assert chunks[0].page_start == 1
    assert chunks[-1].page_end == 6
    for c in chunks:
        assert c.page_start <= c.page_end
    # chunks cover pages in order without going backwards
    for a, b in zip(chunks, chunks[1:], strict=False):
        assert a.page_end <= b.page_start


def test_chunk_spanning_pages_has_a_range():
    chunks = chunk_pages([(3, "short one"), (4, "short two")])
    assert (chunks[0].page_start, chunks[0].page_end) == (3, 4)


def test_oversized_paragraph_is_split_on_sentences():
    sentence = "This is a sentence about joins. "
    big = sentence * (MAX_CHARS // len(sentence) * 3)
    chunks = chunk_pages([(None, big)])
    assert len(chunks) >= 3
    assert all(len(c.text) <= MAX_CHARS for c in chunks)
    assert all(c.text.endswith("joins.") for c in chunks)


def test_chunks_land_in_the_target_token_range():
    text = "\n\n".join(para(f"p{i}", 1500) for i in range(9))
    chunks = chunk_pages([(None, text)])
    assert len(chunks) > 1
    for c in chunks[:-1]:  # the last chunk may be shorter
        assert MIN_TOKENS <= c.token_count <= MAX_TOKENS


def test_token_count_is_chars_over_four_and_nul_removed():
    chunks = chunk_pages([(None, "a" * 400 + "\x00")])
    assert chunks[0].token_count == 100
    assert "\x00" not in chunks[0].text
