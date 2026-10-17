export type ActivityStatus = 'draft' | 'published' | 'closed' | 'finished'

export type FieldType =
  | 'text'
  | 'textarea'
  | 'phone'
  | 'email'
  | 'number'
  | 'select'
  | 'multi_select'
  | 'date'

export interface FormField {
  key: string
  label: string
  type: FieldType
  required: boolean
  placeholder?: string | null
  options?: string[] | null
  system?: boolean
}

export interface ActivityPayload {
  title: string
  cover_url: string | null
  summary: string | null
  description: string | null
  location_name: string
  address: string | null
  start_at: string
  end_at: string
  signup_start_at: string
  signup_end_at: string
  checkin_open_at: string | null
  checkin_close_at: string | null
  capacity: number
  need_review: boolean
  allow_cancel: boolean
  cancel_deadline: string | null
  form_schema: FormField[]
}

export interface Activity extends ActivityPayload {
  id: number
  status: ActivityStatus
  version: number
  taken_count: number
  created_by: number
  published_at: string | null
  created_at: string
  updated_at: string
}

export interface ActivityUpdatePayload extends ActivityPayload {
  version: number
}

export interface ActivityListItem {
  id: number
  title: string
  cover_url: string | null
  location_name: string
  start_at: string
  end_at: string
  capacity: number
  taken_count: number
  need_review: boolean
  status: ActivityStatus
  created_at: string
}
