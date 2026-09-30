import { Config } from "drizzle-kit";

const defineConfig = {
  dialect: "postgresql",
  dbCredentials: {
    url: process.env.DATABASE_URL,
  },
  //   schema: "",
} as Config;

export default defineConfig;
