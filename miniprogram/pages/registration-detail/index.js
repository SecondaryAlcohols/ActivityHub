const request = require('../../utils/request')
const auth = require('../../utils/auth')
const { formatDateTime } = require('../../utils/date')
const { API_BASE } = require('../../config')

const STATUS_META = {
  pending: { label: '待审核', className: 'tag-warn' },
  approved: { label: '已通过', className: 'tag-success' },
  rejected: { label: '已拒绝', className: 'tag-danger' },
  cancelled: { label: '已取消', className: 'tag-muted' },
}

function formatValue(value) {
  if (value === null || value === undefined || value === '') return '—'
  if (Array.isArray(value)) return value.join('、')
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

Page({
  data: {
    id: null,
    detail: null,
    ticket: null,
    qrUrl: '',
    answerRows: [],
    statusLabel: '',
    statusClass: '',
    canCancel: false,
    loading: true,
    cancelling: false,
  },

  onLoad(options) {
    this.setData({ id: Number(options.id) })
  },

  onShow() {
    this.load()
  },

  load() {
    this.setData({ loading: true })
    auth
      .ensureLogin()
      .then(() => request.get(`/api/mp/registrations/${this.data.id}`))
      .then((detail) => {
        const meta = STATUS_META[detail.status] || {
          label: detail.status,
          className: 'tag-muted',
        }
        const schema = detail.form_schema || []
        const rows = schema.map((field) => ({
          key: field.key,
          label: field.label,
          value: formatValue((detail.answers || {})[field.key]),
        }))
        const known = new Set(schema.map((field) => field.key))
        Object.keys(detail.answers || {}).forEach((key) => {
          if (!known.has(key)) {
            rows.push({
              key,
              label: key,
              value: formatValue(detail.answers[key]),
            })
          }
        })

        const active = ['pending', 'approved'].includes(detail.status)
        const activity = detail.activity
        const deadline =
          activity && (activity.cancel_deadline || activity.signup_end_at)
        const beforeDeadline =
          !deadline || Date.now() <= new Date(deadline).getTime()
        const canCancel =
          active && activity && activity.allow_cancel !== false && beforeDeadline

        detail.createdText = formatDateTime(detail.created_at)
        if (detail.activity) {
          detail.activity.startText = formatDateTime(detail.activity.start_at)
          detail.activity.endText = formatDateTime(detail.activity.end_at)
        }

        this.setData({
          detail,
          answerRows: rows,
          statusLabel: meta.label,
          statusClass: meta.className,
          canCancel,
          loading: false,
        })

        if (detail.status === 'approved') {
          this.loadTicket()
        } else {
          this.setData({ ticket: null, qrUrl: '' })
        }
      })
      .catch(() => {
        this.setData({ loading: false })
      })
  },

  loadTicket() {
    request
      .get(`/api/mp/registrations/${this.data.id}/ticket`)
      .then((ticket) => {
        this.setData({
          ticket: {
            ...ticket,
            startText: formatDateTime(ticket.start_at),
            endText: formatDateTime(ticket.end_at),
          },
          qrUrl: `${API_BASE}/api/mp/tickets/${ticket.token}.png`,
        })
      })
      .catch(() => {})
  },

  openActivity() {
    const detail = this.data.detail
    if (!detail || !detail.activity) return
    wx.navigateTo({
      url: `/pages/activity-detail/index?id=${detail.activity.id}`,
    })
  },

  cancel() {
    if (!this.data.canCancel || this.data.cancelling) return
    wx.showModal({
      title: '取消报名',
      content: '取消后会释放名额，确定要取消吗？',
      confirmText: '取消报名',
      confirmColor: '#b45309',
      success: (res) => {
        if (res.confirm) {
          this.doCancel()
        }
      },
    })
  },

  doCancel() {
    this.setData({ cancelling: true })
    request
      .post(`/api/mp/registrations/${this.data.id}/cancel`)
      .then(() => {
        wx.showToast({ title: '已取消报名', icon: 'success' })
        this.load()
      })
      .catch(() => {})
      .then(() => {
        this.setData({ cancelling: false })
      })
  },
})
