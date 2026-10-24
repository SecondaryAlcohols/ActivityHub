export interface Attendee {
  id: number
  username: string | null
  nickname: string
  avatar_url: string | null
  phone: string | null
}

export interface LoginResult {
  access_token: string
  attendee: Attendee
}

export interface Page<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export type RegistrationStatus =
  | 'pending'
  | 'approved'
  | 'rejected'
  | 'cancelled'

export interface ActivityItem {
  id: number
  title: string
  cover_url: string | null
  summary: string | null
  location_name: string
  start_at: string
  end_at: string
  signup_start_at: string
  signup_end_at: string
  capacity: number
  taken_count: number
  remaining: number
  need_review: boolean
  allow_cancel: boolean
  cancel_deadline: string | null
  status: string
}

export interface FormField {
  key: string
  label: string
  type:
    | 'text'
    | 'textarea'
    | 'phone'
    | 'email'
    | 'number'
    | 'select'
    | 'multi_select'
    | 'date'
  required: boolean
  placeholder?: string | null
  options?: string[] | null
  system?: boolean
}

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

export interface SignupState {
  can_signup: boolean
  reason:
    | 'not_started'
    | 'closed'
    | 'full'
    | 'already_registered'
    | 'activity_closed'
    | null
}

export interface ActivityDetail extends ActivityItem {
  description: string | null
  address: string | null
  form_schema: FormField[]
  my_registration: Registration | null
  signup_state: SignupState
}

export interface RegistrationItem extends Registration {
  activity: ActivityItem
}

export interface RegistrationDetail extends Registration {
  activity: ActivityItem
  form_schema: FormField[]
}

export interface Ticket {
  token: string
  registration_id: number
  activity_id: number
  activity_title: string
  applicant_name: string
  status: RegistrationStatus
  start_at: string
  end_at: string
  location_name: string
}
