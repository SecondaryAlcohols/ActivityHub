const request = require('../../utils/request')
const { formatDateTime } = require('../../utils/date')

Page({
  data: {
    tabs: [
      { key: 'all', label: '全部' },
      { key: 'upcoming', label: '即将开始' },
      { key: 'ongoing', label: '进行中' },
      { key: 'past', label: '已结束' },
    ],
    activeTab: 'all',
    activities: [],
    page: 1,
    pageSize: 10,
    total: 0,
    hasMore: true,
    loading: false,
  },

  onLoad() {
    this.load(true)
  },

  onShow() {
    if (!this.data.activities.length) {
      this.load(true)
    }
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
    if (key === this.data.activeTab) return
    this.setData({ activeTab: key, activities: [], hasMore: true })
    this.load(true)
  },

  load(reset) {
    if (this.data.loading) return
    const page = reset ? 1 : this.data.page + 1
    this.setData({ loading: true })

    request
      .get('/api/mp/activities', {
        tab: this.data.activeTab,
        page,
        page_size: this.data.pageSize,
      })
      .then((data) => {
        const items = data.items.map((item) => ({
          ...item,
          startText: formatDateTime(item.start_at),
          endText: formatDateTime(item.end_at),
        }))
        const activities = reset
          ? items
          : this.data.activities.concat(items)
        this.setData({
          activities,
          page,
          total: data.total,
          hasMore: activities.length < data.total,
        })
      })
      .catch(() => {})
      .then(() => {
        this.setData({ loading: false })
        wx.stopPullDownRefresh()
      })
  },

  openActivity(event) {
    const id = event.currentTarget.dataset.id
    wx.navigateTo({ url: `/pages/activity-detail/index?id=${id}` })
  },

  openMine() {
    wx.navigateTo({ url: '/pages/mine/index' })
  },
})
