import { NavLink } from "react-router-dom";

// Nav tabs the router actually serves. Order matches design/Main.dc.html
// and design/History.dc.html.
const ROUTED_TABS = [
  { to: "/", label: "今日" },
  { to: "/history", label: "历史" },
];

// P3/P5/P7 from the design spec (计划/模板库/统计) don't exist yet. They
// must be visibly "not yet available" rather than either a dead link that
// 404s or silently missing from the nav -- a disabled-looking, non-
// navigating label with an explanatory title does that without needing a
// route or a placeholder page.
const PLACEHOLDER_TABS = ["复习队列", "模板库", "统计"];

export function AppHeader({ topicName }: { topicName: string }) {
  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-[12px]">
        <svg
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
          className="text-muted"
        >
          <rect x="3" y="4" width="18" height="16" rx="2"></rect>
          <path d="M8 9h8M8 13h5"></path>
        </svg>
        <span className="text-[14px] font-semibold text-text-bright">{topicName}</span>
        <svg
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          className="text-dim2"
        >
          <path d="M6 9l6 6 6-6"></path>
        </svg>
      </div>
      <nav className="flex gap-1 text-[12px]">
        {ROUTED_TABS.map((tab) => (
          <NavLink
            key={tab.to}
            to={tab.to}
            end={tab.to === "/"}
            className={({ isActive }) =>
              `rounded px-[12px] py-[5px] ${
                isActive ? "bg-nav-active text-text-bright" : "text-muted hover:text-text"
              }`
            }
          >
            {tab.label}
          </NavLink>
        ))}
        {PLACEHOLDER_TABS.map((label) => (
          <span
            key={label}
            className="cursor-not-allowed rounded px-[12px] py-[5px] text-muted opacity-60"
            title="即将上线"
            aria-disabled="true"
          >
            {label}
          </span>
        ))}
      </nav>
    </div>
  );
}
