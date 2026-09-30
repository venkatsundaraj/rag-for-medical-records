from dataclasses import dataclass
from pathlib import Path
import hashlib

@dataclass
class LoadedDocument:
    title:str
    source:str
    content:str
    content_hash:str
    meta:dict

def load_file(path:Path,corpus_dir:Path)->LoadedDocument:
    content = path.read_text(encoding="utf-8")

    relative_path = path.relative_to(corpus_dir)
    source = relative_path.as_posix()

    title = next((line[2:].strip() for line in content.splitlines() if line.startswith("# ")), path.stem)

    content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()

    meta = {
        "source":source,
         "url": f"https://fastapi.tiangolo.com/{source.removesuffix('.md')}/",
    }


    return LoadedDocument(title=title, content=content, content_hash=content_hash, meta=meta, source=source)



BASE_DIR = Path(__file__).resolve().parent.parent.parent
FILE_PATH = BASE_DIR / "data" / "corpus" 

def load_corpus(corpus_dir:Path)->list[LoadedDocument]:
    f = [load_file(path, corpus_dir) for path in corpus_dir.rglob('*.md')]
    # helloo = [path.relative_to(corpus_dir).as_posix() for path in corpus_dir.rglob('*.md')]
    # print(helloo)
    # helloo = [path.stem for path in corpus_dir.rglob('*.md')]
    # print(helloo)
    
    return f



if __name__ == "__main__":
    load_corpus(FILE_PATH)