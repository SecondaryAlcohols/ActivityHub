export function formatDateTime(value?: string | null) {
  if (!value) return '—'
  return value.slice(0, 16).replace('T', ' ')
}

export function formatDate(value?: string | null) {
  if (!value) return '—'
  return value.slice(0, 10)
}

export const STATUS_META = {
  pending: { label: '待审核', className: 'tag-warn' },
  approved: { label: '已通过', className: 'tag-success' },
  rejected: { label: '已拒绝', className: 'tag-danger' },
  cancelled: { label: '已取消', className: 'tag-muted' },
} as const

export const REASON_TEXT: Record<string, string> = {
  activity_closed: '活动已下架或结束',
  already_registered: '你已报名该活动',
  not_started: '报名尚未开始',
  closed: '报名已截止',
  full: '名额已满',
}

export function valueText(value: unknown) {
  if (value === null || value === undefined || value === '') return '—'
  if (Array.isArray(value)) return value.join('、')
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}
