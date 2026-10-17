import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { fetchMe, login as loginRequest } from '@/api/auth'
import type { Admin } from '@/types/api'

const TOKEN_KEY = 'admin_token'
const ADMIN_KEY = 'admin_info'

function readAdmin(): Admin | null {
  const raw = localStorage.getItem(ADMIN_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw) as Admin
  } catch {
    return null
  }
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem(TOKEN_KEY) ?? '')
  const admin = ref<Admin | null>(readAdmin())
  const isLoggedIn = computed(() => Boolean(token.value))

  async function login(username: string, password: string) {
    const result = await loginRequest(username, password)
    token.value = result.access_token
    admin.value = result.admin
    localStorage.setItem(TOKEN_KEY, result.access_token)
    localStorage.setItem(ADMIN_KEY, JSON.stringify(result.admin))
  }

  async function refreshAdmin() {
    if (!token.value) return
    admin.value = await fetchMe()
    localStorage.setItem(ADMIN_KEY, JSON.stringify(admin.value))
  }

  function logout() {
    token.value = ''
    admin.value = null
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(ADMIN_KEY)
  }

  return { token, admin, isLoggedIn, login, refreshAdmin, logout }
})
