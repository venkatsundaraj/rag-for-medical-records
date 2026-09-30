import express from "express";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { join } from "path";

const app = express();

const filePath = join(import.meta.dir, "./data/async.md");

app.get("/", async (req, res) => {
  const file = await readFile(filePath, "utf-8");
  console.log(file);
  return res.json("hello world");
});

app.listen(3002, () => {
  console.log("the server started");
});
