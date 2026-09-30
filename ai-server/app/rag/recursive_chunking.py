
from app.rag.chunking import TextChunk, _ENCODING

RECURSIVE_CHUNK_SIZE = 1000
RECURSIVE_CHUNK_OVERLAP = 150
RECURSIVE_STRATEGY_LABEL = f"recursive_c{RECURSIVE_CHUNK_SIZE}_o{RECURSIVE_CHUNK_OVERLAP}"

_SEPARATORS = ["\n\n","\n", ". ", " "]

Span = tuple[int, int]


def _split_recursive(text:str, start:int, end:int, separators:list[str])->list[Span]:

    size = RECURSIVE_CHUNK_SIZE

    if end - start < size:
        return [(start, end)]

    if not separators:
        return [(c, min(c + size, end)) for c in range(start, end, size)]

    sep, rest = separators[0], separators[1:]

    cut_points = []
    i = text.find(sep, start)

    while i !=-1 and i < end -  len(sep):
        cut_points.append(i + len(sep))
        i = text.find(sep, i + len(sep))

    if not cut_points:
        return _split_recursive(text, start, end, rest)
    print(cut_points, "cup")
    spans:list[Span] = []
    piece_start = start
    for cut in [*cut_points, end]:
        if cut <= piece_start:
            continue
        if cut - piece_start <= size:
            spans.append((piece_start, cut))
        else:
            spans.extend(_split_recursive(text, piece_start, cut, rest))
        piece_start = cut

    return spans

def _merge_spans(spans:list[Span], size:int, overlap:int):

    chunks: list[Span] = []
    i = 0
    while i < len(spans):
        chunk_start = spans[i][0]
        j = i
        # extend while the next span still fits in the budget
        while j + 1 < len(spans) and spans[j + 1][1] - chunk_start <= size:
            j += 1
        chunk_end = spans[j][1]
        chunks.append((chunk_start, chunk_end))
        if j + 1 >= len(spans):
            break
        # step back over trailing spans that fit in the overlap window
        next_i = j + 1
        while next_i - 1 > i and spans[next_i - 1][0] >= chunk_end - overlap:
            next_i -= 1
        i = next_i
    return chunks


def chunk_recursive(text:str, size: int = RECURSIVE_CHUNK_SIZE, overlap:int = RECURSIVE_CHUNK_OVERLAP):
    if size <= 0:
        raise ValueError(f"size must be positive, got {size}")
    if not (0 <= overlap < size):
        raise ValueError(f"overlap must be in [0, size), got {overlap}")
    if not text:
        return []

    atomic = _split_recursive(text, 0, len(text), _SEPARATORS)
    merged = _merge_spans(atomic, size, overlap)

    # [print(i, text[f[0]:f[1]]) for i, f in enumerate(merged[0:201])]
    # [print(i, text[f[0]:f[1]]) for i, f in enumerate(atomic[0:201])]
    # print(len(merged))

    chunks: list[TextChunk] = []
    index = 0
    for start, end in merged:
        content = text[start:end]
        if not content.strip():  # skip whole, never trim
            continue
        chunks.append(
            TextChunk(
                index=index,
                char_start=start,
                char_end=end,
                content=content,
                token_count=len(_ENCODING.encode(content)),
            )
        )
        index += 1
 
    for c in chunks:
        assert text[c.char_start : c.char_end] == c.content, (
            f"offset rule violated at chunk {c.index}"
        )
    return chunks


    return


if __name__ == "__main__":
    from pathlib import Path
    import sys

    raw = Path(sys.argv[1]).read_text(encoding="utf-8")
    result = chunk_recursive(raw)
    sizes = [c.char_end - c.char_start for c in result]
    print(f"{len(result)} chunks | min {min(sizes)} / avg {sum(sizes)//len(sizes)} / max {max(sizes)} chars\n")
    for c in result[:5]:
        print(f"--- chunk {c.index} [{c.char_start}:{c.char_end}] ---")
        print(c.content[:300])
        print("...\n" if len(c.content) > 300 else "\n")

