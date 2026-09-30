



if __name__ == "__main__":

    item = [False, True, True, True, False] 
    print(sum(item))
    item1 = "# Concurrency and async / await { #concurrency-and-async-await }"
    for i, it in enumerate(list(item1[0:50])):
        if i < 30:
            continue
        print(i)