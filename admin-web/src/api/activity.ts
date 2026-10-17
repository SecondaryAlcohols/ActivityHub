import { del, get, post, put } from './http'

import type {
  Activity,
  ActivityListItem,
  ActivityPayload,
  ActivityUpdatePayload,
} from '@/types/activity'
import type { Page } from '@/types/api'

export interface ActivityQuery {
  status?: string
  keyword?: string
  page?: number
  page_size?: number
}

export function fetchActivities(params: ActivityQuery) {
  return get<Page<ActivityListItem>>('/admin/activities', params)
}

export function fetchActivity(id: number) {
  return get<Activity>(`/admin/activities/${id}`)
}

export function createActivity(payload: ActivityPayload) {
  return post<Activity>('/admin/activities', payload)
}

export function updateActivity(id: number, payload: ActivityUpdatePayload) {
  return put<Activity>(`/admin/activities/${id}`, payload)
}

export function deleteActivity(id: number) {
  return del<null>(`/admin/activities/${id}`)
}

export function publishActivity(id: number) {
  return post<Activity>(`/admin/activities/${id}/publish`)
}

export function closeActivity(id: number) {
  return post<Activity>(`/admin/activities/${id}/close`)
}

export function finishActivity(id: number) {
  return post<Activity>(`/admin/activities/${id}/finish`)
}
