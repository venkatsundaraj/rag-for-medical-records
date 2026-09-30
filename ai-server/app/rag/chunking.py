from dataclasses import dataclass
from pathlib import Path
import tiktoken


_ENCODING = tiktoken.get_encoding("cl100k_base")




FIXED_CHUNK_SIZE = 1000
FIXED_CHUNK_OVERLAP = 150
FIXED_STRATEGY_LABEL = f"fixed_c{FIXED_CHUNK_SIZE}_o{FIXED_CHUNK_OVERLAP}"

@dataclass(frozen=True, slots=True)
class TextChunk:
    """it provided the info about a particular chunk"""

    index:int
    content:str
    char_start:int
    char_end:int
    token_count:int


def chunk_text(text:str, size:int = FIXED_CHUNK_SIZE, overlap:int = FIXED_CHUNK_OVERLAP)->list[TextChunk]:

    if len(text) <= 0:
        ValueError('text count should be positive')
    if size <= 0:
        raise ValueError(f"size must be positive, got {size}")
    if overlap < 0:
        raise ValueError(f"overlap must be >= 0, got {overlap}")
    if overlap >= size:
         raise ValueError(f"overlap ({overlap}) must be smaller than size ({size})")


    start = 0
    index = 0
    result:list[TextChunk] = []

    while start < len(text):
        end = min(start + size, len(text))
        chunk = text[start:end]

        if chunk.strip():
            result.append(TextChunk(
                index=index,
                content=chunk,
                char_start=start, 
                char_end=end, 
                token_count=len(_ENCODING.encode(chunk)))
                )

            index += 1

        if end == len(text):
            break
        start = end - overlap

    for chunk in result:
        assert text[chunk.char_start : chunk.char_end] == chunk.content, (
            f"offset rule violated at chunk {chunk.index} "
            f"({chunk.char_start}:{chunk.char_end})"
        )


    return result

BASE_PATH = Path(__file__).resolve().parent.parent.parent
FILE_PATH = BASE_PATH / "data" / "corpus" / "async.md"

# print(FILE_PATH.read_text(encoding="utf-8"))




if __name__ == "__main__":
    chunk_text(FILE_PATH.read_text(encoding="utf-8"))


from app.rag.recursive_chunking import RECURSIVE_STRATEGY_LABEL, chunk_recursive

CHUNKERS = {
    FIXED_STRATEGY_LABEL: chunk_text,
    RECURSIVE_STRATEGY_LABEL: chunk_recursive,
}