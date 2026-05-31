import { RouterProvider } from 'react-router'
import { AuthProvider } from './auth/AuthContext'
import { DashboardStateProvider } from './hooks/DashboardStateContext'
import { router } from './routes'

export function App() {
  return (
    <AuthProvider>
      <DashboardStateProvider>
        <RouterProvider router={router} />
      </DashboardStateProvider>
    </AuthProvider>
  )
}
