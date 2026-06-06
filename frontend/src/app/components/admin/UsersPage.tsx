import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router";
import { useAuth } from "../../auth/AuthContext";
import { listUsers, getManagedUser, updateManagedUser, deleteManagedUser, resetManagedUserPassword } from "../../api/client";
import type { UserPublic, UserRole } from "../../api/types";
import { TopBar } from "../dashboard/TopBar";
import { PlusIcon, ChevronRightIcon } from "../Glyphs";

const ROLE_OPTIONS: UserRole[] = ["admin", "operator"];
const ROLE_LABELS: Record<UserRole, string> = {
  admin: "Administrador",
  operator: "Operario",
};

function formatDate(iso: string | null | undefined) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("es-ES", { dateStyle: "short", timeStyle: "short" });
}

export function AdminUsersPage() {
  const { status } = useAuth();
  const navigate = useNavigate();
  const { userId } = useParams<{ userId?: string }>();

  const [users, setUsers] = useState<UserPublic[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<UserPublic | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // Edit state
  const [editFullName, setEditFullName] = useState("");
  const [editRole, setEditRole] = useState<UserRole>("operator");
  const [editActive, setEditActive] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");

  // Password reset
  const [newPassword, setNewPassword] = useState("");
  const [pwSaving, setPwSaving] = useState(false);
  const [pwError, setPwError] = useState("");
  const [pwSuccess, setPwSuccess] = useState(false);

  // Delete
  const [deleteConfirm, setDeleteConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    if (status === "anonymous") void navigate("/", { replace: true });
  }, [status, navigate]);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const data = await listUsers();
        setUsers(data);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Error cargando usuarios");
      } finally {
        setLoading(false);
      }
    };
    if (status === "authenticated") void load();
  }, [status]);

  useEffect(() => {
    if (!userId) { setSelected(null); return; }
    const fromList = users.find(u => u.id === userId);
    if (fromList) {
      setSelected(fromList);
      setEditFullName(fromList.full_name);
      setEditRole(fromList.role);
      setEditActive(fromList.is_active);
    } else if (users.length > 0) {
      setDetailLoading(true);
      getManagedUser(userId).then(u => {
        setSelected(u);
        setEditFullName(u.full_name);
        setEditRole(u.role);
        setEditActive(u.is_active);
      }).catch(e => setError(e instanceof Error ? e.message : "Error")).finally(() => setDetailLoading(false));
    }
    setDeleteConfirm(false);
    setNewPassword("");
    setPwSuccess(false);
    setSaveError("");
    setPwError("");
  }, [userId, users]);

  const selectUser = (u: UserPublic) => {
    void navigate(`/admin/users/${u.id}`);
  };

  const handleSave = async () => {
    if (!selected) return;
    setSaving(true); setSaveError("");
    try {
      const updated = await updateManagedUser(selected.id, {
        full_name: editFullName, role: editRole, is_active: editActive,
      });
      setUsers(prev => prev.map(u => u.id === updated.id ? updated : u));
      setSelected(updated);
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : "Error guardando");
    } finally {
      setSaving(false);
    }
  };

  const handlePasswordReset = async () => {
    if (!selected || !newPassword) return;
    setPwSaving(true); setPwError(""); setPwSuccess(false);
    try {
      await resetManagedUserPassword(selected.id, newPassword);
      setPwSuccess(true);
      setNewPassword("");
    } catch (e) {
      setPwError(e instanceof Error ? e.message : "Error");
    } finally {
      setPwSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!selected) return;
    setDeleting(true);
    try {
      await deleteManagedUser(selected.id);
      setUsers(prev => prev.filter(u => u.id !== selected.id));
      void navigate("/admin/users");
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : "Error eliminando");
      setDeleting(false);
    }
  };

  if (status === "loading") return null;

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
      <TopBar />
      <div style={{ flex: 1, display: "flex", minHeight: 0, overflow: "hidden" }}>

        {/* User list panel */}
        <div style={{ width: 340, flexShrink: 0, borderRight: "1px solid var(--vg-line)", background: "var(--vg-panel)", display: "flex", flexDirection: "column", overflow: "hidden" }}>
          <div className="section-label" style={{ justifyContent: "space-between" }}>
            <span>Usuarios</span>
            <button
              className="btn btn-quiet"
              style={{ gap: 4, height: 22, fontSize: 11, padding: "0 8px" }}
              onClick={() => void navigate("/admin/users/new")}
            >
              <PlusIcon /> Nuevo
            </button>
          </div>

          {error && (
            <div style={{ padding: "10px 20px", color: "#c0392b", fontSize: 12 }}>{error}</div>
          )}

          {loading ? (
            <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
              <div className="spinner" />
            </div>
          ) : (
            <div style={{ flex: 1, overflowY: "auto" }}>
              {users.map(u => (
                <UserRow
                  key={u.id}
                  user={u}
                  selected={userId === u.id}
                  onClick={() => selectUser(u)}
                />
              ))}
              {users.length === 0 && (
                <div style={{ padding: "16px 20px", fontSize: 12, color: "var(--vg-ink-lo)" }}>
                  No hay usuarios registrados.
                </div>
              )}
            </div>
          )}
        </div>

        {/* Detail panel */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "auto", background: "var(--vg-bg)", padding: "32px 40px" }}>
          {!selected && !detailLoading && (
            <div style={{ color: "var(--vg-ink-lo)", fontSize: 13 }}>
              Selecciona un usuario de la lista para ver y editar sus datos.
            </div>
          )}

          {detailLoading && (
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <div className="spinner" style={{ width: 20, height: 20 }} />
              <span style={{ color: "var(--vg-ink-lo)", fontSize: 13 }}>Cargando…</span>
            </div>
          )}

          {selected && !detailLoading && (
            <div style={{ maxWidth: 560 }}>
              <div style={{ fontFamily: "var(--vg-mono)", fontSize: 10.5, color: "var(--vg-ink-lo)", letterSpacing: "0.12em", textTransform: "uppercase", marginBottom: 6 }}>
                Editor de usuario
              </div>
              <h2 style={{ fontSize: 24, fontWeight: 500, letterSpacing: "-0.02em", margin: "0 0 28px" }}>
                {selected.username}
              </h2>

              {/* Meta */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 24px", marginBottom: 24, padding: "16px 0", borderTop: "1px solid var(--vg-line)", borderBottom: "1px solid var(--vg-line)" }}>
                <DetailMeta label="ID" value={selected.id.slice(0, 8) + "…"} mono />
                <DetailMeta label="Registrado" value={formatDate(selected.created_at)} mono />
                <DetailMeta label="Último acceso" value={formatDate(selected.last_login_at)} mono />
                <DetailMeta label="Actualizado" value={formatDate(selected.updated_at)} mono />
              </div>

              {/* Edit form */}
              <div style={{ display: "flex", flexDirection: "column", gap: 16, marginBottom: 24 }}>
                <FieldRow label="Nombre completo">
                  <input
                    className="field-input"
                    value={editFullName}
                    onChange={e => setEditFullName(e.target.value)}
                    style={{ width: "100%" }}
                  />
                </FieldRow>

                <FieldRow label="Rol">
                  <select
                    className="field-input"
                    value={editRole}
                    onChange={e => setEditRole(e.target.value as UserRole)}
                    style={{ width: "100%" }}
                  >
                    {ROLE_OPTIONS.map(r => <option key={r} value={r}>{ROLE_LABELS[r]}</option>)}
                  </select>
                </FieldRow>

                <FieldRow label="Estado">
                  <div
                    className={`vg-toggle ${editActive ? "on" : ""}`}
                    onClick={() => setEditActive(v => !v)}
                    style={{ cursor: "pointer" }}
                  >
                    <div className="vg-toggle-knob" />
                  </div>
                  <span style={{ fontSize: 12, color: "var(--vg-ink-md)", marginLeft: 8 }}>
                    {editActive ? "Activo" : "Inactivo"}
                  </span>
                </FieldRow>
              </div>

              {saveError && <p style={{ color: "#c0392b", fontSize: 12, marginBottom: 12 }}>{saveError}</p>}

              <div style={{ display: "flex", gap: 8, marginBottom: 32 }}>
                <button className="btn btn-accent" onClick={() => void handleSave()} disabled={saving}>
                  {saving ? "Guardando…" : "Guardar cambios"}
                </button>
              </div>

              {/* Password reset */}
              <div style={{ borderTop: "1px solid var(--vg-line)", paddingTop: 24, marginBottom: 32 }}>
                <div style={{ fontFamily: "var(--vg-mono)", fontSize: 10.5, color: "var(--vg-ink-lo)", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 12 }}>
                  Restablecer contraseña
                </div>
                <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  <input
                    className="field-input"
                    type="password"
                    placeholder="Nueva contraseña"
                    value={newPassword}
                    onChange={e => setNewPassword(e.target.value)}
                    style={{ flex: 1 }}
                  />
                  <button
                    className="btn btn-quiet"
                    onClick={() => void handlePasswordReset()}
                    disabled={pwSaving || !newPassword}
                  >
                    {pwSaving ? "…" : "Aplicar"}
                  </button>
                </div>
                {pwError && <p style={{ color: "#c0392b", fontSize: 12, marginTop: 6 }}>{pwError}</p>}
                {pwSuccess && <p style={{ color: "var(--vg-accent)", fontSize: 12, marginTop: 6 }}>Contraseña actualizada.</p>}
              </div>

              {/* Delete */}
              <div style={{ borderTop: "1px solid var(--vg-line)", paddingTop: 24 }}>
                <div style={{ fontFamily: "var(--vg-mono)", fontSize: 10.5, color: "var(--vg-ink-lo)", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 12 }}>
                  Zona peligrosa
                </div>
                {!deleteConfirm ? (
                  <button className="btn btn-quiet" style={{ color: "#c0392b", borderColor: "#c0392b" }} onClick={() => setDeleteConfirm(true)}>
                    Eliminar usuario
                  </button>
                ) : (
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <span style={{ fontSize: 12, color: "var(--vg-ink-md)" }}>¿Confirmar eliminación?</span>
                    <button
                      className="btn"
                      style={{ background: "#c0392b", color: "#fff", borderColor: "#c0392b" }}
                      onClick={() => void handleDelete()}
                      disabled={deleting}
                    >
                      {deleting ? "Eliminando…" : "Sí, eliminar"}
                    </button>
                    <button className="btn btn-quiet" onClick={() => setDeleteConfirm(false)}>
                      Cancelar
                    </button>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function UserRow({ user, selected, onClick }: { user: UserPublic; selected: boolean; onClick: () => void }) {
  return (
    <div
      onClick={onClick}
      style={{
        display: "flex", alignItems: "center", gap: 10, padding: "11px 20px",
        borderTop: "1px solid var(--vg-line-soft)",
        borderLeft: selected ? "3px solid var(--vg-accent)" : "3px solid transparent",
        background: selected ? "var(--vg-accent-soft)" : "transparent",
        cursor: "pointer",
      }}
    >
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 13, color: "var(--vg-ink-hi)", fontWeight: selected ? 500 : 400, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {user.full_name || user.username}
        </div>
        <div style={{ display: "flex", gap: 8, marginTop: 2 }}>
          <span style={{ fontFamily: "var(--vg-mono)", fontSize: 10.5, color: "var(--vg-ink-lo)" }}>{user.username}</span>
          <span style={{ fontFamily: "var(--vg-mono)", fontSize: 10.5, color: selected ? "var(--vg-accent)" : "var(--vg-ink-lo)", textTransform: "uppercase", letterSpacing: "0.05em" }}>{ROLE_LABELS[user.role]}</span>
          {!user.is_active && <span style={{ fontFamily: "var(--vg-mono)", fontSize: 10.5, color: "#c0392b", textTransform: "uppercase" }}>inactivo</span>}
        </div>
      </div>
      <ChevronRightIcon />
    </div>
  );
}

function DetailMeta({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div style={{ paddingBottom: 12 }}>
      <div style={{ fontFamily: "var(--vg-mono)", fontSize: 10, color: "var(--vg-ink-lo)", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 3 }}>{label}</div>
      <div style={{ fontSize: 12, color: "var(--vg-ink-hi)", fontFamily: mono ? "var(--vg-mono)" : undefined }}>{value}</div>
    </div>
  );
}

function FieldRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div style={{ fontFamily: "var(--vg-mono)", fontSize: 10.5, color: "var(--vg-ink-lo)", letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 6 }}>{label}</div>
      <div style={{ display: "flex", alignItems: "center" }}>{children}</div>
    </div>
  );
}
