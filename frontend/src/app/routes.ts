import { createBrowserRouter } from 'react-router'
import { LoginPage } from './components/LoginPage'
import { ProtectedDashboard } from './components/ProtectedDashboard'

export const router = createBrowserRouter([
  {
    path: '/',
    Component: LoginPage,
  },
  {
    path: '/dashboard',
    Component: ProtectedDashboard,
  },
])
