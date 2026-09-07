import type { MetaOut } from "./types";

// The SPA is served by the same FastAPI process it talks to (spec C5 --
// one process), so relative /api/... URLs always resolve correctly
// without a base-URL config, both under `npm run dev`'s own port (proxied
// -- see vite.config.ts's server.fs note; dev-server proxying is added
// once a real page needs it) and once built and served by uvicorn itself.
export async function fetchMeta(): Promise<MetaOut> {
  const response = await fetch("/api/meta");
  if (!response.ok) {
    throw new Error(`GET /api/meta failed: ${response.status}`);
  }
  return (await response.json()) as MetaOut;
}
