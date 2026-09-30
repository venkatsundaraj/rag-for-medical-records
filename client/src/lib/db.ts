import { drizzle } from "drizzle-orm/postgres-js";
import postgres from "postgres";
import * as schema from "./schema";

const globalDb = globalThis as unknown as {
  conn: postgres.Sql;
};

const conn = globalDb.conn ?? postgres(process.env.DATABASE_URL!);
if (process.env.NODE_ENV !== "production") globalDb.conn = conn;

export const db = drizzle(conn, { schema });
