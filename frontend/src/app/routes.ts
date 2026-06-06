import { createBrowserRouter } from 'react-router'
import { LoginPage } from './components/LoginPage'
import { ProtectedDashboard } from './components/ProtectedDashboard'
import { AdminUsersPage } from './components/admin/UsersPage'
import { AdminUserCreatePage } from './components/admin/UserCreatePage'

export const router = createBrowserRouter([
  {
    path: '/',
    Component: LoginPage,
  },
  {
    path: '/dashboard',
    Component: ProtectedDashboard,
  },
  {
    path: '/admin/users',
    Component: AdminUsersPage,
  },
  {
    path: '/admin/users/:userId',
    Component: AdminUsersPage,
  },
  {
    path: '/admin/users/new',
    Component: AdminUserCreatePage,
  },
])
