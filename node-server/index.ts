import express from "express";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { join } from "path";

const app = express();

const filePath = join(import.meta.dir, "./data/async.md");

app.get("/", async (req, res) => {
  const file = await readFile(filePath, "utf-8");
  // for (let i = 0; i < 4; i++) {
  //   for (let j = 0; j < i; j++) {
  //     console.log(i, j);
  //   }
  // }
  const original = {
    name: "Alice",
    skills: ["JavaScript", "React"], // Nested array
  };

  // Creating a shallow copy
  const shallowCopy = structuredClone(original);

  // 1. Modifying top-level property (Safe)
  shallowCopy.name = "Bob";
  console.log(original.name); // "Alice" (Original is unchanged)

  // 2. Modifying nested property (Unsafe!)
  shallowCopy.skills.push("Node.js");
  console.log(original.skills); // ["JavaScript", "React", "Node.js"] (Original changed!)

  return res.json("hello world");
});

app.listen(3002, () => {
  console.log("the server started");
});

// bun index.ts
