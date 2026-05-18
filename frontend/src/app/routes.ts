import { createBrowserRouter } from 'react-router'
import { LoginPage } from './components/LoginPage'

export const router = createBrowserRouter([
  {
    path: '/',
    Component: LoginPage,
  },
])
