import { get, post } from './http'

import type { Admin, LoginResult } from '@/types/api'

export function login(username: string, password: string) {
  return post<LoginResult>('/admin/auth/login', { username, password })
}

export function fetchMe() {
  return get<Admin>('/admin/auth/me')
}
