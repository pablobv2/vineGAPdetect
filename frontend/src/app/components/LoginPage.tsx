import { type FormEvent, useState } from "react";
import { useNavigate } from "react-router";
import { useAuth } from "../auth/AuthContext";
import { useTheme } from "../hooks/useTheme";
import { MoonIcon, SunIcon } from "./Glyphs";

const VINEYARD_IMG_LIGHT =
  "https://images.unsplash.com/photo-1729972963275-98e458d45527?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHx2aW5leWFyZCUyMGFlcmlhbCUyMGRyb25lJTIwcm93c3xlbnwxfHx8fDE3NzE5MzY3NTV8MA&ixlib=rb-4.1.0&q=80&w=1080";

// Viñedo con racimos de uva tinta en la planta (Terra Slaybaugh, Unsplash)
const VINEYARD_IMG_DARK =
  "https://images.unsplash.com/photo-1599678695930-bfd6ad507037?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&q=80&w=1080";

export function LoginPage() {
  const { login, status } = useAuth();
  const navigate = useNavigate();
  const { theme, toggle } = useTheme();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  if (status === "loading") {
    return (
      <div style={{ width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center", background: "var(--vg-bg)" }}>
        <div className="spinner" />
      </div>
    );
  }

  if (status === "authenticated") {
    void navigate("/dashboard", { replace: true });
    return null;
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login({ username, password });
      void navigate("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al iniciar sesión");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ width: "100%", height: "100%", display: "flex", overflow: "hidden", fontFamily: "var(--vg-font)", color: "var(--vg-ink-hi)" }}>

      {/* ── Left: image pane ── */}
      <div style={{ flex: "0 0 60%", position: "relative", overflow: "hidden" }}>
        {/* Photo — light theme */}
        <img
          src={VINEYARD_IMG_LIGHT}
          alt="Viñedo aéreo"
          style={{
            position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover",
            filter: "saturate(0.86)",
            opacity: theme === "dark" ? 0 : 1,
            transition: "opacity 0.6s ease-in-out",
          }}
          draggable={false}
        />
        {/* Photo — dark theme (uva tinta) */}
        <img
          src={VINEYARD_IMG_DARK}
          alt="Viñedo de uva tinta"
          style={{
            position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover",
            filter: "saturate(0.92) brightness(0.78) contrast(1.02)",
            opacity: theme === "dark" ? 1 : 0,
            transition: "opacity 0.6s ease-in-out",
          }}
          draggable={false}
        />
        {/* Overlays */}
        <div style={{
          position: "absolute", inset: 0,
          background: theme === "dark" ? "rgba(80,55,110,0.20)" : "rgba(79,99,53,0.22)",
          mixBlendMode: "multiply",
          transition: "background 0.6s ease-in-out",
        }} />
        <div style={{ position: "absolute", inset: 0, background: "linear-gradient(to top, rgba(0,0,0,0.72) 0%, rgba(0,0,0,0.18) 40%, transparent 70%)" }} />
        <div style={{ position: "absolute", inset: 0, background: "linear-gradient(to bottom, rgba(0,0,0,0.38) 0%, transparent 30%)" }} />

        {/* Centered logo */}
        <div style={{
          position: "absolute", inset: 0, zIndex: 1,
          display: "flex", alignItems: "flex-start", justifyContent: "center",
          paddingTop: "22%",
          pointerEvents: "none",
        }}>
          <img
            src={theme === "dark" ? "/logo_vinegapdetect_dark.png" : "/logo_vinegapdetect_light.png"}
            alt="vineGAPdetect"
            style={{
              height: 140, width: "auto", display: "block",
              filter:
                "drop-shadow(0 0 8px rgba(0,0,0,0.9)) " +
                "drop-shadow(0 2px 16px rgba(0,0,0,0.75)) " +
                "drop-shadow(0 4px 32px rgba(0,0,0,0.55))",
            }}
            draggable={false}
          />
        </div>

        {/* Bottom — headline */}
        <div style={{ position: "absolute", left: 0, right: 0, bottom: 0, zIndex: 1, padding: "0 52px 56px" }}>
          <h1 style={{
            fontSize: 52, fontWeight: 500, letterSpacing: "-0.03em", lineHeight: 1.08,
            color: "#fff", margin: "0 0 20px",
            textShadow: "0 2px 4px rgba(0,0,0,0.8), 0 6px 20px rgba(0,0,0,0.5)",
          }}>
            Detección inteligente<br />de marras en viñedos
          </h1>
          <p style={{
            fontSize: 15.5, color: "rgba(255,255,255,0.9)", maxWidth: 460,
            lineHeight: 1.55, margin: "0 0 28px",
            textShadow: "0 1px 3px rgba(0,0,0,0.8)",
          }}>
            Plataforma de análisis basada en visión por computador y modelos YOLOv11-OBB
            para la detección automatizada de huecos en parcelas vitícolas.
          </p>
          <div style={{ display: "flex", gap: 24 }}>
            {["Precisión >80%", "Análisis TIFF/GeoTIFF", "XAI Eigen-CAM"].map(tag => (
              <div key={tag} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <div style={{ width: 7, height: 7, borderRadius: "50%", background: "var(--vg-accent)", flexShrink: 0, boxShadow: "0 0 4px rgba(0,0,0,0.5)" }} />
                <span style={{ fontSize: 13, color: "#fff", fontFamily: "var(--vg-mono)", letterSpacing: "0.04em", textShadow: "0 1px 3px rgba(0,0,0,0.8)" }}>
                  {tag}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── Right: form pane ── */}
      <div style={{
        flex: "0 0 40%", display: "flex", flexDirection: "column",
        background: "var(--vg-bg)", overflow: "auto",
      }}>
        {/* Top strip */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "flex-end", padding: "16px 32px", borderBottom: "1px solid var(--vg-line)", flexShrink: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
            <span style={{ fontFamily: "var(--vg-mono)", fontSize: 10.5, color: "var(--vg-ink-lo)", letterSpacing: "0.04em" }}>v0.9.1</span>
            <button className="btn-icon" onClick={toggle} title="Cambiar tema" style={{ color: "var(--vg-ink-md)" }}>
              {theme === "dark" ? <SunIcon /> : <MoonIcon />}
            </button>
          </div>
        </div>

        {/* Form centered */}
        <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", padding: "48px 56px" }}>
          <div style={{ width: "100%", maxWidth: 340 }}>
            <div style={{ fontFamily: "var(--vg-mono)", fontSize: 11, color: "var(--vg-ink-lo)", letterSpacing: "0.14em", textTransform: "uppercase", marginBottom: 10 }}>
              Acceso
            </div>
            <h2 style={{ fontSize: 26, fontWeight: 500, letterSpacing: "-0.02em", margin: "0 0 32px" }}>
              Iniciar sesión
            </h2>

            {error && (
              <div style={{
                marginBottom: 20, padding: "10px 14px", fontSize: 12.5,
                background: "color-mix(in srgb, #c0392b 10%, transparent)",
                border: "1px solid color-mix(in srgb, #c0392b 30%, transparent)",
                color: "#c0392b",
              }}>
                {error}
              </div>
            )}

            <form onSubmit={(e) => void handleSubmit(e)}>
              <label className="field-label">Usuario</label>
              <input
                type="text"
                className="field-input"
                value={username}
                onChange={e => setUsername(e.target.value)}
                autoComplete="username"
                required
                disabled={loading}
                placeholder="operario1"
                style={{ width: "100%", boxSizing: "border-box" }}
              />

              <label className="field-label" style={{ display: "block", marginTop: 20 }}>Contraseña</label>
              <input
                type="password"
                className="field-input"
                value={password}
                onChange={e => setPassword(e.target.value)}
                autoComplete="current-password"
                required
                disabled={loading}
                placeholder="••••••••••"
                style={{ width: "100%", boxSizing: "border-box" }}
              />

              <button
                type="submit"
                className="btn btn-primary btn-full"
                style={{ marginTop: 28, height: 40, fontSize: 13 }}
                disabled={loading || !username || !password}
              >
                {loading ? "Accediendo…" : "Acceder"}
              </button>
            </form>

            <div style={{ marginTop: 36, paddingTop: 16, borderTop: "1px solid var(--vg-line)", fontSize: 11, color: "var(--vg-ink-lo)", lineHeight: 1.6 }}>
              El acceso lo gestiona el administrador de tu organización.
              Roles disponibles:{" "}
              <span style={{ color: "var(--vg-ink-md)" }}>operario</span>,{" "}
              <span style={{ color: "var(--vg-ink-md)" }}>administrador</span>.
            </div>
          </div>
        </div>

        {/* Footer */}
        <div style={{ padding: "16px 32px", borderTop: "1px solid var(--vg-line)", textAlign: "center", fontSize: 10.5, color: "var(--vg-ink-lo)", fontFamily: "var(--vg-mono)", flexShrink: 0 }}>
          © 2026 vineGAPdetect · Sistema de detección de marras vitícolas
        </div>
      </div>
    </div>
  );
}
