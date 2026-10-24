const request = require('../../utils/request')
const auth = require('../../utils/auth')
const { formatDateTime } = require('../../utils/date')

const STATUS_META = {
  pending: { label: '待审核', className: 'tag-warn' },
  approved: { label: '已通过', className: 'tag-success' },
  rejected: { label: '已拒绝', className: 'tag-danger' },
  cancelled: { label: '已取消', className: 'tag-muted' },
}

Page({
  data: {
    tabs: [
      { key: '', label: '全部' },
      { key: 'pending', label: '待审核' },
      { key: 'approved', label: '已通过' },
      { key: 'rejected', label: '已拒绝' },
      { key: 'cancelled', label: '已取消' },
    ],
    activeStatus: '',
    items: [],
    page: 1,
    pageSize: 10,
    total: 0,
    hasMore: true,
    loading: false,
  },

  onShow() {
    this.load(true)
  },

  onPullDownRefresh() {
    this.load(true)
  },

  onReachBottom() {
    if (this.data.hasMore && !this.data.loading) {
      this.load(false)
    }
  },

  switchTab(event) {
    const key = event.currentTarget.dataset.key
    if (key === this.data.activeStatus) return
    this.setData({ activeStatus: key, items: [], hasMore: true })
    this.load(true)
  },

  load(reset) {
    if (this.data.loading) return
    const page = reset ? 1 : this.data.page + 1
    this.setData({ loading: true })

    auth
      .ensureLogin()
      .then(() =>
        request.get('/api/mp/registrations', {
          status: this.data.activeStatus || undefined,
          page,
          page_size: this.data.pageSize,
        }),
      )
      .then((data) => {
        const list = data.items.map((item) => {
          const meta = STATUS_META[item.status] || {
            label: item.status,
            className: 'tag-muted',
          }
          return {
            ...item,
            statusLabel: meta.label,
            statusClass: meta.className,
            startText: formatDateTime(item.activity.start_at),
            endText: formatDateTime(item.activity.end_at),
          }
        })
        const items = reset ? list : this.data.items.concat(list)
        this.setData({
          items,
          page,
          total: data.total,
          hasMore: items.length < data.total,
        })
      })
      .catch(() => {})
      .then(() => {
        this.setData({ loading: false })
        wx.stopPullDownRefresh()
      })
  },

  openDetail(event) {
    const id = event.currentTarget.dataset.id
    wx.navigateTo({ url: `/pages/registration-detail/index?id=${id}` })
  },
})
