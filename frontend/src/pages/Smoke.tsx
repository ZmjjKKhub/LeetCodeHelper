import { useQuery } from "@tanstack/react-query";

import { fetchMeta } from "../api/client";

// Scaffolding-only proof that the full chain works: Vite build -> FastAPI
// static-serves the SPA -> browser fetches /api/meta -> React renders it,
// styled entirely from design/tokens.css's semantic Tailwind classes (see
// tests/test_frontend_no_hex_colors.py -- no hex literal is allowed in
// this file or anywhere else under src/). Not the real Today page.
export function SmokePage() {
  const { data, isPending, isError, error } = useQuery({
    queryKey: ["meta"],
    queryFn: fetchMeta,
  });

  return (
    <main className="min-h-screen bg-bg font-sans text-text px-6 py-10">
      <div className="mx-auto max-w-xl rounded-lg border border-border bg-panel p-6 shadow-sm">
        <p className="font-mono text-xs uppercase tracking-wide text-dim">
          /api/meta smoke test
        </p>

        {isPending && <p className="mt-4 text-text-soft">加载中……</p>}

        {isError && (
          <p className="mt-4 text-alert">
            请求失败：{error instanceof Error ? error.message : String(error)}
          </p>
        )}

        {data && (
          <>
            <h1 className="mt-2 text-2xl font-semibold text-text-bright">
              {data.topic.name}
            </h1>
            <p className="mt-1 font-mono text-sm text-muted">{data.topic.code}</p>

            <h2 className="mt-6 text-sm font-medium text-text-soft">
              四种结果
            </h2>
            <ul className="mt-2 space-y-2">
              {data.outcomes.map((outcome) => (
                <li
                  key={outcome.value}
                  className="rounded border border-border-soft bg-subpanel px-3 py-2"
                >
                  <span className="font-medium text-text-bright">
                    {outcome.label}
                  </span>
                  <span className="ml-2 text-sm text-text-soft">
                    {outcome.consequence}
                  </span>
                </li>
              ))}
            </ul>
          </>
        )}
      </div>
    </main>
  );
}
