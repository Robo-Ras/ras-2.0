import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";
import { componentTagger } from "lovable-tagger";

// Instância só do controle (start.sh --controle): a raiz abre direto o /controle no celular
const controleOnly = {
  name: "ras-controle-only",
  configureServer(server: import("vite").ViteDevServer) {
    if (!process.env.RAS_CONTROLE_ONLY) return;
    server.middlewares.use((req, res, next) => {
      if (req.url === "/") {
        res.statusCode = 302;
        res.setHeader("Location", "/controle");
        res.end();
        return;
      }
      next();
    });
  },
};

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => ({
  // duas instâncias do vite (painel e controle) não podem dividir o mesmo cache
  cacheDir: process.env.VITE_CACHE_DIR || undefined,
  server: {
    host: "::",
    port: 8080,
  },
  plugins: [
    react(),
    controleOnly,
    mode === 'development' &&
    componentTagger(),
  ].filter(Boolean),
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
}));
