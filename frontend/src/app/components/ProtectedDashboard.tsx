import { useEffect } from "react";
import { useNavigate } from "react-router";
import { useAuth } from "../auth/AuthContext";
import { Dashboard } from "./Dashboard";

export function ProtectedDashboard() {
  const { status } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (status === "anonymous") void navigate("/", { replace: true });
  }, [status, navigate]);

  if (status === "loading") {
    return (
      <div style={{ height: "100%", display: "flex", alignItems: "center", justifyContent: "center", background: "var(--vg-bg)" }}>
        <div className="spinner" />
      </div>
    );
  }
  if (status !== "authenticated") return null;
  return <Dashboard />;
}
