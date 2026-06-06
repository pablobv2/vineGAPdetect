import { useState } from "react";
import { useNavigate } from "react-router";
import { createManagedUser } from "../../api/client";
import type { UserRole } from "../../api/types";
import { TopBar } from "../dashboard/TopBar";

const ROLE_OPTIONS: UserRole[] = ["admin", "operator"];
const ROLE_LABELS: Record<UserRole, string> = {
  admin: "Administrador",
  operator: "Operario",
};

export function AdminUserCreatePage() {
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<UserRole>("operator");
  const [isActive, setIsActive] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const canSubmit = username.trim() && fullName.trim() && password.length >= 6;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;
    setSaving(true); setError("");
    try {
      await createManagedUser({ username: username.trim(), full_name: fullName.trim(), password, role, is_active: isActive });
      void navigate("/admin/users");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error creando usuario");
      setSaving(false);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
      <TopBar />
      <div style={{ flex: 1, overflow: "auto", padding: "40px", background: "var(--vg-bg)" }}>
        <div style={{ maxWidth: 480 }}>
          <div style={{ fontFamily: "var(--vg-mono)", fontSize: 10.5, color: "var(--vg-ink-lo)", letterSpacing: "0.12em", textTransform: "uppercase", marginBottom: 6 }}>
            Gestión de usuarios
          </div>
          <h2 style={{ fontSize: 24, fontWeight: 500, letterSpacing: "-0.02em", margin: "0 0 32px" }}>
            Crear nuevo usuario
          </h2>

          <form onSubmit={(e) => void handleSubmit(e)} style={{ display: "flex", flexDirection: "column", gap: 20 }}>
            <FormField label="Nombre de usuario">
              <input
                className="field-input"
                type="text"
                value={username}
                onChange={e => setUsername(e.target.value)}
                autoComplete="off"
                style={{ width: "100%" }}
                required
              />
            </FormField>

            <FormField label="Nombre completo">
              <input
                className="field-input"
                type="text"
                value={fullName}
                onChange={e => setFullName(e.target.value)}
                style={{ width: "100%" }}
                required
              />
            </FormField>

            <FormField label="Contraseña" hint="Mínimo 6 caracteres">
              <input
                className="field-input"
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                autoComplete="new-password"
                style={{ width: "100%" }}
                minLength={6}
                required
              />
            </FormField>

            <FormField label="Rol">
              <select
                className="field-input"
                value={role}
                onChange={e => setRole(e.target.value as UserRole)}
                style={{ width: "100%" }}
              >
                {ROLE_OPTIONS.map(r => <option key={r} value={r}>{ROLE_LABELS[r]}</option>)}
              </select>
            </FormField>

            <FormField label="Estado">
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <div
                  className={`vg-toggle ${isActive ? "on" : ""}`}
                  onClick={() => setIsActive(v => !v)}
                  style={{ cursor: "pointer" }}
                >
                  <div className="vg-toggle-knob" />
                </div>
                <span style={{ fontSize: 12, color: "var(--vg-ink-md)" }}>
                  {isActive ? "Activo" : "Inactivo"}
                </span>
              </div>
            </FormField>

            {error && (
              <p style={{ color: "#c0392b", fontSize: 12, margin: 0 }}>{error}</p>
            )}

            <div style={{ display: "flex", gap: 8, paddingTop: 8 }}>
              <button
                type="submit"
                className="btn btn-accent"
                disabled={saving || !canSubmit}
              >
                {saving ? "Creando…" : "Crear usuario"}
              </button>
              <button
                type="button"
                className="btn btn-quiet"
                onClick={() => void navigate("/admin/users")}
                disabled={saving}
              >
                Cancelar
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}

function FormField({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div>
      <div style={{ fontFamily: "var(--vg-mono)", fontSize: 10.5, color: "var(--vg-ink-lo)", letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 6 }}>
        {label}
        {hint && <span style={{ marginLeft: 8, fontSize: 10, color: "var(--vg-ink-lo)", textTransform: "none", letterSpacing: 0, fontFamily: "var(--vg-sans)" }}>{hint}</span>}
      </div>
      {children}
    </div>
  );
}
