from collections.abc import AsyncGenerator
from typing import Annotated
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.pdf_schema import Document, Chunk
from app.lib.alchemy_db import get_db, SessionLocal
import asyncio


if __name__ == "__main__":

    # item = [False, True, True, True, False] 
    # print(sum(item))
    # item1 = "# Concurrency and async / await { #concurrency-and-async-await }"
    # for i, it in enumerate(list(item1[0:50])):
    #     if i < 30:
    #         continue
    #     print(i)

    # hello = {"name":"venkat", "age":21}
    # print(hello.get('name33', "vee"), hello['name'])

    async def main():
        
        sources=('authors.md', 'ddfdf')

        async with SessionLocal() as session:
            documents = (await session.scalars(select(Document).where(Document.source.in_(sources)))).all()
            for doc in documents:
                # print({key:value for key, value in doc.__dict__.items() if not key.startswith('_')})
                continue

        # [print(i) for i in source]
        hi = {"name":"venkat"}

        hello = hi
        hello["name"] = "sarathi"

        # print(hi, hello)

        a = "hello world venkat"
        b = 'o world'

        print(a.find(b))

        return

        

    asyncio.run(main())

