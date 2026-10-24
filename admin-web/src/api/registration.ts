import { get, post } from './http'

import type { Page } from '@/types/api'
import type {
  AdminRegistrationDetail,
  AdminRegistrationItem,
  BatchReviewResult,
  Registration,
  RegistrationStats,
  RegistrationStatus,
} from '@/types/registration'

export interface RegistrationQuery {
  status?: RegistrationStatus | ''
  keyword?: string
  page?: number
  page_size?: number
}

export function fetchRegistrations(activityId: number, params: RegistrationQuery) {
  return get<Page<AdminRegistrationItem>>(
    `/admin/activities/${activityId}/registrations`,
    {
      ...params,
      status: params.status || undefined,
      keyword: params.keyword?.trim() || undefined,
    },
  )
}

export function fetchRegistrationStats(activityId: number) {
  return get<RegistrationStats>(`/admin/activities/${activityId}/stats`)
}

export function fetchRegistrationDetail(id: number) {
  return get<AdminRegistrationDetail>(`/admin/registrations/${id}`)
}

export function reviewRegistration(
  id: number,
  action: 'approve' | 'reject',
  note?: string,
) {
  return post<Registration>(`/admin/registrations/${id}/review`, {
    action,
    note: note || null,
  })
}

export function batchReviewRegistrations(
  ids: number[],
  action: 'approve' | 'reject',
  note?: string,
) {
  return post<BatchReviewResult>('/admin/registrations/batch-review', {
    ids,
    action,
    note: note || null,
  })
}

export function cancelRegistration(id: number) {
  return post<Registration>(`/admin/registrations/${id}/cancel`)
}
