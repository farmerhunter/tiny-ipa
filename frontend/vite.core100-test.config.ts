import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
const port = Number(process.env.CORE100_REAL_BACKEND_PORT ?? "8035");
if (!Number.isInteger(port) || port < 1024 || port > 65535) throw new Error("Invalid test port");
export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": `http://127.0.0.1:${port}`, "/audio": `http://127.0.0.1:${port}` } },
});
