import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// the dev server runs on 5173, which the backend CORS already allows.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
});
