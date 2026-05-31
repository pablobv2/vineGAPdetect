import { useNavigate, useLocation } from "react-router";
import { useAuth } from "../../auth/AuthContext";
import { useTheme } from "../../hooks/useTheme";
import { LogoutIcon, MoonIcon, SunIcon } from "../Glyphs";

const ROLE_LABELS: Record<string, string> = { admin: "administrador", operator: "operario" };

interface Props {
  project?: string;
}

export function TopBar({ project }: Props) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const { theme, toggle } = useTheme();

  const isAdmin    = location.pathname.startsWith("/admin");
  const isHistory  = location.pathname.startsWith("/history");
  const isDashboard = !isAdmin && !isHistory;
  const displayName = user?.full_name || user?.username || "Usuario";
  const initials = displayName.split(" ").map(p => p[0]).join("").slice(0, 2).toUpperCase();
  const handleLogout = async () => {
    await logout();
    void navigate("/", { replace: true });
  };

  return (
    <header style={{
      display: "flex", alignItems: "stretch",
      borderBottom: "1px solid var(--vg-line)",
      background: "var(--vg-panel)",
      height: 54, flexShrink: 0,
    }}>
      {/* Logo */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "0 24px", borderRight: "1px solid var(--vg-line)", flexShrink: 0 }}>
        <img
          src={theme === "dark" ? "/logo_vinegapdetect_dark.png" : "/logo_vinegapdetect.png"}
          alt="vineGAPdetect"
          style={{ height: 28, width: "auto", display: "block" }}
          draggable={false}
        />
        <span style={{ fontSize: 11, color: "var(--vg-ink-lo)", fontFamily: "var(--vg-mono)", letterSpacing: "0.04em", marginLeft: 4 }}>v0.9.1</span>
      </div>

      {/* Project breadcrumb */}
      <div style={{ flex: 1, display: "flex", alignItems: "center", padding: "0 22px", gap: 14, color: "var(--vg-ink-md)", fontSize: 14, minWidth: 0 }}>
        <span style={{ color: "var(--vg-ink-lo)" }}>Proyecto</span>
        <span style={{ color: "var(--vg-ink-hi)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {project ?? (isAdmin ? "Gestión de usuarios" : isHistory ? "Mis parcelas" : "— sin ortomosaico cargado")}
        </span>
      </div>

      {/* Nav buttons */}
      {user && (
        <div style={{ display: "flex", alignItems: "stretch", borderLeft: "1px solid var(--vg-line)" }}>
          <button
            className={`nav-btn${isDashboard ? " active" : ""}`}
            onClick={() => void navigate("/dashboard")}
          >
            Análisis
          </button>
          <button
            className={`nav-btn${isHistory ? " active" : ""}`}
            onClick={() => void navigate("/history")}
          >
            Mis parcelas
          </button>
          {user.role === "admin" && (
            <button
              className={`nav-btn${isAdmin ? " active" : ""}`}
              onClick={() => void navigate("/admin/users")}
            >
              Gestión
            </button>
          )}
        </div>
      )}

      {/* User + controls */}
      <div style={{ display: "flex", alignItems: "center", gap: 14, padding: "0 22px", borderLeft: "1px solid var(--vg-line)", flexShrink: 0 }}>
        <span style={{ fontSize: 12, fontFamily: "var(--vg-mono)", color: "var(--vg-ink-lo)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
          {user ? ROLE_LABELS[user.role] : ""}
        </span>
        <span style={{ fontSize: 14, color: "var(--vg-ink-hi)" }}>{displayName}</span>
        <span style={{
          width: 24, height: 24, borderRadius: "50%",
          background: "var(--vg-accent-soft)", color: "var(--vg-accent)",
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 11, fontWeight: 600, fontFamily: "var(--vg-mono)",
          flexShrink: 0,
        }}>{initials}</span>
        <span style={{ width: 1, height: 18, background: "var(--vg-line)", flexShrink: 0 }} />
        <button className="btn-icon" onClick={toggle} title="Cambiar tema">{theme === "dark" ? <SunIcon /> : <MoonIcon />}</button>
        <button className="btn-icon" onClick={() => void handleLogout()} title="Salir"><LogoutIcon /></button>
      </div>
    </header>
  );
}
