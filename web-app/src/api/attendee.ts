import { get, post, put } from './http'

import type {
  ActivityDetail,
  ActivityItem,
  Attendee,
  LoginResult,
  Page,
  Registration,
  RegistrationDetail,
  RegistrationItem,
  RegistrationStatus,
  Ticket,
} from '@/types'

export function webLogin(nickname: string, phone: string) {
  return post<LoginResult>('/attendee/auth/login', { nickname, phone })
}

export function fetchMe() {
  return get<Attendee>('/attendee/auth/me')
}

export function updateProfile(nickname: string) {
  return put<Attendee>('/attendee/auth/profile', { nickname })
}

export function fetchActivities(params: {
  tab?: string
  page?: number
  page_size?: number
}) {
  return get<Page<ActivityItem>>('/mp/activities', params)
}

export function fetchActivity(id: number) {
  return get<ActivityDetail>(`/mp/activities/${id}`)
}

export function createRegistration(
  activityId: number,
  answers: Record<string, unknown>,
) {
  return post<Registration>(`/mp/activities/${activityId}/registrations`, {
    answers,
  })
}

export function fetchMyRegistrations(params: {
  status?: RegistrationStatus | ''
  page?: number
  page_size?: number
}) {
  return get<Page<RegistrationItem>>('/mp/registrations', params)
}

export function fetchRegistration(id: number) {
  return get<RegistrationDetail>(`/mp/registrations/${id}`)
}

export function cancelRegistration(id: number) {
  return post<Registration>(`/mp/registrations/${id}/cancel`)
}

export function fetchTicket(id: number) {
  return get<Ticket>(`/mp/registrations/${id}/ticket`)
}
