import {
  Activity,
  BarChart3,
  ChevronRight,
  FlaskConical,
  LayoutDashboard,
  Plus,
} from "lucide-react";
import { NavLink, Outlet, useLocation } from "react-router-dom";

const pageMeta = [
  {
    match: (path: string) => path === "/",
    eyebrow: "Workspace",
    title: "评测概览",
  },
  {
    match: (path: string) => path === "/runs/new",
    eyebrow: "New evaluation",
    title: "创建评测",
  },
  {
    match: (path: string) => path.endsWith("/report"),
    eyebrow: "Analysis",
    title: "模型对比报告",
  },
  {
    match: (path: string) => path.startsWith("/runs/"),
    eyebrow: "Evaluation run",
    title: "评测运行详情",
  },
];

export function AppLayout() {
  const location = useLocation();
  const current =
    pageMeta.find((item) => item.match(location.pathname)) ??
    pageMeta[0];

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">
            <FlaskConical size={22} strokeWidth={2.2} />
          </div>
          <div>
            <div className="brand-name">EvalFlow</div>
            <div className="brand-subtitle">LLM Quality Lab</div>
          </div>
        </div>

        <nav className="primary-nav" aria-label="主导航">
          <NavLink
            to="/"
            end
            className={({ isActive }) =>
              `nav-item ${isActive ? "active" : ""}`
            }
          >
            <LayoutDashboard size={18} />
            <span>评测概览</span>
          </NavLink>
          <NavLink
            to="/runs/new"
            className={({ isActive }) =>
              `nav-item ${isActive ? "active" : ""}`
            }
          >
            <Plus size={18} />
            <span>创建评测</span>
          </NavLink>
        </nav>

        <div className="sidebar-section">
          <div className="sidebar-label">评测闭环</div>
          <div className="flow-map">
            <div>
              <Activity size={16} />
              <span>模型生成</span>
            </div>
            <ChevronRight size={14} />
            <div>
              <FlaskConical size={16} />
              <span>质量评估</span>
            </div>
            <ChevronRight size={14} />
            <div>
              <BarChart3 size={16} />
              <span>问题分析</span>
            </div>
          </div>
        </div>

        <div className="sidebar-note">
          <span className="live-dot" />
          <div>
            <strong>真实数据模式</strong>
            <p>数据来自本地 FastAPI 与 SQLite</p>
          </div>
        </div>
      </aside>

      <div className="app-main">
        <header className="topbar">
          <div>
            <div className="topbar-eyebrow">{current.eyebrow}</div>
            <div className="topbar-title">{current.title}</div>
          </div>
          <div className="environment-chip">
            <span />
            Local workspace
          </div>
        </header>
        <main className="page-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
