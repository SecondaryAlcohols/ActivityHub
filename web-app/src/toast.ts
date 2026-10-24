import { reactive } from 'vue'

export interface ToastItem {
  id: number
  message: string
  type: 'error' | 'success' | 'info'
}

export const toasts = reactive<ToastItem[]>([])

let nextId = 1

export function toast(
  message: string,
  type: ToastItem['type'] = 'error',
  duration = 3000,
) {
  const id = nextId++
  toasts.push({ id, message, type })
  window.setTimeout(() => {
    const index = toasts.findIndex((item) => item.id === id)
    if (index >= 0) toasts.splice(index, 1)
  }, duration)
}
