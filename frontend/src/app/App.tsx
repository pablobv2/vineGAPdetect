import { RouterProvider } from 'react-router'
import { AuthProvider } from './auth/AuthContext'
import { DashboardStateProvider } from './hooks/DashboardStateContext'
import { router } from './routes'

/**
* Compone autenticacion, estado del dashboard y enrutado principal de la aplicacion web.
* El arbol raiz garantiza que todas las pantallas accedan a la sesion activa y
* al estado compartido del analisis sin duplicar logica entre rutas.
*/
export function App() {
  return (
    <AuthProvider>
      <DashboardStateProvider>
        <RouterProvider router={router} />
      </DashboardStateProvider>
    </AuthProvider>
  )
}
