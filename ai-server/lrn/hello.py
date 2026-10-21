import asyncio
from dataclasses import dataclass

async def main():
    async def add(a, b):
        return a+b
    items = {"a":(3, 4), "b":(6, 8)}
    res = await asyncio.gather(*(add(items[i][0], items[i][1]) for i in items))
    print(res)

@dataclass(frozen=True, slots=True)
class Hello:
    name:str
    age:int
if __name__ == "__main__":

     item = [False, True, True, True, False] 
     asyncio.run(main())
    # print(sum(item))
    # item1 = "# Concurrency and async / await { #concurrency-and-async-await }"
    # for i, it in enumerate(list(item1[0:50])):
    #     if i < 30:
    #         continue
    #     print(i)
     hello = {"name":"venkat", "age":21}
     h = (2, 3, 4, 5, 1)
    # print(hello.get('name33', "vee"), hello['name'])
    # hi = (0, 1)
    # for i in range(6):
    #     if i == 4:
    #         print(i)
    #         # break
    #         continue
    #     if i > 0:
    #         print('hello')
        # if i == 5:
        #     print(i)
    #  print([any(range(4) or range(3))])

    #  answers:dict[tuple[int, int], tuple[int, int]] = {}
    #  for i in range(4):
    #      answers[i, i+1] = (i, i+1)

     answers = sorted(zip(h, item),key=lambda p: p[0])
         
     
     ev = Hello(name=hello["name"], age=hello['age'])

     c = {"hello", "hi", "hello"}
    #  print(c)
     ans_value:dict[tuple[str, str], tuple[str, str]] = {('a','b'):('c','d'),('e','f'):('g','h')}

    #  for k,i in enumerate(ans_value):
    #     #  print(i)
    #      print(i[k], ans_value[i])

     h = [1, 2, 3]
     f = (1, 2, 3)
     c = " "
    #  print(1 in h, "hello" in c, "name" in hello, 2 in f, bool(c))
    #  print(h.extend([2]))

     

    #  print(hello.name, hello['name'], hello.get('name', "ddd"))
       
            

    # asyncio.run(main())
    


# [74] score=+0.993  alternatives.md — Alternatives, Inspiration and Comparisons { #alternatives-inspiration-and-comparisons }
#     Test client built on HTTPX. * CORS, GZip, Static Files, Streaming responses. * Session and Cookie support. * 100% test coverage. * 100% type annotated codebase
# [73] score=+0.045  alternatives.md — Alternatives, Inspiration and Comparisons { #alternatives-inspiration-and-comparisons }
#    mallow in benchmarks. And as it is based on the same Python type hints, the editor support is great.  /// tip | **FastAPI** uses it to  Handle all the data vali
# [51] score=+0.004  alternatives.md — Alternatives, Inspiration and Comparisons { #alternatives-inspiration-and-comparisons }
#    tools }  ### [Django](https://www.djangoproject.com/) { #django }  It's the most popular Pythonframework and is widely trusted. It is used to build systems lik
# [75] score=+0.000  alternatives.md — Alternatives, Inspiration and Comparisons { #alternatives-inspiration-and-comparisons }
#     of doing that.  Nevertheless, it is already being used as a "standard" by several tools. This greatly improves interoperability, as you could switch Uvicorn fo
# [212] score=+0.000  tutorial.md — Tutorial
#    e`, behavioral flags, and migration guide - **[Django integration](integrations.md)** — auto-discovery, `MachineMixin` with Django models - **[Diagrams](diagram