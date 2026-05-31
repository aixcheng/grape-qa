import { inject } from 'vue'

export function useAuth() {
  const auth = inject('auth')
  const login = inject('login')
  const logout = inject('logout')
  const register = inject('register')
  return {
    user: auth?.user,
    username: auth?.user?.username,
    token: auth?.token,
    login,
    logout,
    register,
  }
}
