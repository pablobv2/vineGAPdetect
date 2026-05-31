import { createContext, useContext, useEffect } from "react";
import { useAuth } from "../auth/AuthContext";
import { clearPendingHistoryRestore } from "../utils/historyRestoreStore";
import { useDashboardState } from "./useDashboardState";

type DashboardStateContextValue = ReturnType<typeof useDashboardState>;

const DashboardStateContext = createContext<DashboardStateContextValue | null>(null);

export function DashboardStateProvider({ children }: { children: React.ReactNode }) {
  const value = useDashboardState();
  const { status } = useAuth();

  useEffect(() => {
    if (status !== "anonymous") return;
    clearPendingHistoryRestore();
    value.actions.closeFile();
    // Reset only when the auth boundary changes to anonymous.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status]);

  return (
    <DashboardStateContext.Provider value={value}>
      {children}
    </DashboardStateContext.Provider>
  );
}

export function useDashboardStateContext(): DashboardStateContextValue {
  const value = useContext(DashboardStateContext);
  if (!value) {
    throw new Error("useDashboardStateContext must be used inside DashboardStateProvider.");
  }
  return value;
}
