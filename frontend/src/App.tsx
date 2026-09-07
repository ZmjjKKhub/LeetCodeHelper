import { Navigate, Route, Routes } from "react-router-dom";

import { HistoryPage } from "./pages/History";
import { TodayPage } from "./pages/Today";

// Mounted at basename="/app" (see main.tsx) -- FastAPI's catch-all
// (leetcode_helper/web/app_factory.py) serves index.html for any path that
// isn't /api, /today, /history or /static, but "/today" and "/history"
// exact-match the still-live Jinja pages *first* (registered before the
// catch-all) and so never reach this SPA at all. "/app" is therefore the
// SPA's own root: Today lives at its "/" (-> served at /app) and History
// at its "/history" (-> served at /app/history), matching the design
// artboards' page structure one level down from where a browser actually
// loads them, without touching app_factory.py's routing or the Jinja
// pages it still serves untouched at /today and /history.
export default function App() {
  return (
    <Routes>
      <Route path="/" element={<TodayPage />} />
      <Route path="/history" element={<HistoryPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
