import { Navigate, Route, Routes } from "react-router-dom";

import { SmokePage } from "./pages/Smoke";

// Scaffolding only -- the real Today/History/... pages come later (see the
// design doc's frontend/src/pages list). FastAPI's catch-all
// (leetcode_helper/web/app_factory.py) serves index.html for any path that
// isn't /api, /today, /history or /static, so this SPA is reachable
// side-by-side with the untouched Jinja pages at those same three paths --
// it deliberately does not claim "/" (the Jinja app already redirects that
// to /today) or "/today" / "/history" (still real Jinja pages) itself.
export default function App() {
  return (
    <Routes>
      <Route path="/app" element={<SmokePage />} />
      <Route path="*" element={<Navigate to="/app" replace />} />
    </Routes>
  );
}
