import { computed, ref } from 'vue'

import type { Attendee, LoginResult } from '@/types'

const TOKEN_KEY = 'web_token'
const USER_KEY = 'web_user'

function readUser(): Attendee | null {
  const raw = localStorage.getItem(USER_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw) as Attendee
  } catch {
    return null
  }
}

export const token = ref(localStorage.getItem(TOKEN_KEY) ?? '')
export const user = ref<Attendee | null>(readUser())
export const isLoggedIn = computed(() => Boolean(token.value))

export function setSession(data: LoginResult) {
  token.value = data.access_token
  user.value = data.attendee
  localStorage.setItem(TOKEN_KEY, data.access_token)
  localStorage.setItem(USER_KEY, JSON.stringify(data.attendee))
}

export function updateUser(next: Attendee) {
  user.value = next
  localStorage.setItem(USER_KEY, JSON.stringify(next))
}

export function clearSession() {
  token.value = ''
  user.value = null
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
}

export function useAuth() {
  return { token, user, isLoggedIn, setSession, updateUser, clearSession }
}
