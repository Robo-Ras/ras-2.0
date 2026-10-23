// Endereço do backend Python. Usa o mesmo host da página, então funciona tanto em
// http://localhost:8080 quanto no tablet acessando http://<ip-do-notebook>:8080.
// Pode ser trocado com VITE_WS_URL (ex.: VITE_WS_URL=ws://10.21.10.186:8765 npm run dev).
export const getWsUrl = () =>
  import.meta.env.VITE_WS_URL || `ws://${window.location.hostname || "localhost"}:8765`;
