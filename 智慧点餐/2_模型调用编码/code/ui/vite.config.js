import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

const proxy = {
  "/api": {
    target: process.env.AIMENU_API_TARGET || "http://127.0.0.1:8000",
    changeOrigin: true,
    rewrite: (path) => path.replace(/^\/api/, ""),
  },
};

export default defineConfig({
  plugins: [vue()],
  server: { host: "127.0.0.1", port: 3000, strictPort: true, proxy },
  preview: { host: "127.0.0.1", port: 4173, proxy },
});
