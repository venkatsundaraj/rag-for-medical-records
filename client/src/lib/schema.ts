import { pgTableCreator, text } from "drizzle-orm/pg-core";

const createTable = pgTableCreator((name) => `hello_${name}`);
export const person = createTable("user", {
  id: text("id").primaryKey(),
  name: text("name").notNull(),
});
