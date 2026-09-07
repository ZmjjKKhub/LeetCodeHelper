import { Navigate, Route, Routes } from "react-router-dom";

import { HistoryPage } from "./pages/History";
import { TodayPage } from "./pages/Today";

// Mounted at the root (see main.tsx -- no basename) -- FastAPI's catch-all
// (leetcode_helper/web/app_factory.py) serves index.html for any path that
// isn't /api or /assets, so this router owns the whole origin: Today lives
// at "/" and History at "/history", matching the design artboards' page
// structure directly. GET /today (the old Jinja page's URL) is redirected
// server-side to "/" by app_factory.py before it ever reaches this router.
export default function App() {
  return (
    <Routes>
      <Route path="/" element={<TodayPage />} />
      <Route path="/history" element={<HistoryPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
