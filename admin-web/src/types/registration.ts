import type { FormField } from './activity'

export type RegistrationStatus = 'pending' | 'approved' | 'rejected' | 'cancelled'

export interface Registration {
  id: number
  activity_id: number
  status: RegistrationStatus
  applicant_name: string
  applicant_phone: string
  answers: Record<string, unknown>
  reviewed_at: string | null
  review_note: string | null
  cancelled_at: string | null
  created_at: string
  updated_at: string
}

export interface AdminRegistrationItem extends Registration {
  attendee_nickname: string
}

export interface ActivityBrief {
  id: number
  title: string
  cover_url: string | null
  location_name: string
  start_at: string
  end_at: string
  capacity: number
  taken_count: number
  need_review: boolean
  status: string
}

export interface AttendeeBrief {
  id: number
  nickname: string
  avatar_url: string | null
  phone: string | null
}

export interface AdminRegistrationDetail extends AdminRegistrationItem {
  activity: ActivityBrief | null
  form_schema: FormField[]
  attendee: AttendeeBrief | null
}

export interface RegistrationStats {
  total: number
  pending: number
  approved: number
  rejected: number
  cancelled: number
  capacity: number
  remaining: number
  signup_rate: number
}

export interface BatchReviewResult {
  approved: number
  rejected: number
  skipped: number
}
