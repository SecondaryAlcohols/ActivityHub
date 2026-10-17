export interface ApiResponse<T> {
  code: number
  message: string
  data: T
}

export interface Page<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export interface Admin {
  id: number
  username: string
  display_name: string
  role: string
  status: boolean
}

export interface LoginResult {
  access_token: string
  token_type: string
  admin: Admin
}
