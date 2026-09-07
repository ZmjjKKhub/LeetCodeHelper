import { Navigate, Route, Routes } from "react-router-dom";

import { TodayPage } from "./pages/Today";

// Mounted at basename="/app" (see main.tsx) -- FastAPI's catch-all
// (leetcode_helper/web/app_factory.py) serves index.html for any path that
// isn't /api, /today, /history or /static, but "/today" and "/history"
// exact-match the still-live Jinja pages *first* (registered before the
// catch-all) and so never reach this SPA at all. "/app" is therefore the
// SPA's own root: Today lives at its "/" (-> served at /app), matching the
// design artboard one level down from where a browser actually loads it,
// without touching app_factory.py's routing or the Jinja pages it still
// serves untouched at /today and /history. History joins at "/history" in
// a follow-up commit.
export default function App() {
  return (
    <Routes>
      <Route path="/" element={<TodayPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
