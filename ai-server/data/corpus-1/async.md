# Concurrency and async / await { #concurrency-and-async-await }

Details about the `async def` syntax for _path operation functions_ and some background about asynchronous code, concurrency, and parallelism.

## In a hurry? { #in-a-hurry }

<abbr title="too long; didn't read"><strong>TL;DR:</strong></abbr>

If you are using third party libraries that tell you to call them with `await`, like:

```Python
results = await some_library()
```

Then, declare your _path operation functions_ with `async def` like:

```Python hl_lines="2"
@app.get('/')
async def read_results():
    results = await some_library()
    return results
```

/// note

You can only use `await` inside of functions created with `async def`.

///

---

If you are using a third party library that communicates with something (a database, an API, the file system, etc.) and doesn't have support for using `await`, (this is currently the case for most database libraries), then declare your _path operation functions_ as normally, with just `def`, like:

```Python hl_lines="2"
@app.get('/')
def results():
    results = some_library()
    return results
```

---

If your application (somehow) doesn't have to communicate with anything else and wait for it to respond, use `async def`, even if you don't need to use `await` inside.

---

If you just don't know, use normal `def`.

---

**Note**: You can mix `def` and `async def` in your _path operation functions_ as much as you need and define each one using the best option for you. FastAPI will do the right thing with them.

Anyway, in any of the cases above, FastAPI will still work asynchronously and be extremely fast.

But by following the steps above, it will be able to do some performance optimizations.

## Technical Details { #technical-details }

Modern versions of Python have support for **"asynchronous code"** using something called **"coroutines"**, with **`async` and `await`** syntax.

Let's see that phrase by parts in the sections below:

- **Asynchronous Code**
- **`async` and `await`**
- **Coroutines**

## Asynchronous Code { #asynchronous-code }
