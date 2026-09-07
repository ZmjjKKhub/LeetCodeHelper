// Mirrors leetcode_helper/web/app_factory.py::format_limit -- the API only
// hands back time_limit_sec as a raw integer, so the "MM:SS" formatting
// that used to live in the Jinja `limit` filter is reproduced here.
export function formatLimit(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(rest).padStart(2, "0")}`;
}
