import { RouterProvider } from 'react-router'
import { AuthProvider } from './auth/AuthContext'
import { router } from './routes'

export function App() {
  return (
    <AuthProvider>
      <RouterProvider router={router} />
    </AuthProvider>
  )
}
