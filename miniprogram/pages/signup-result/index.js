Page({
  data: {
    id: null,
    status: 'approved',
    isPending: false,
  },

  onLoad(options) {
    const status = options.status || 'approved'
    this.setData({
      id: Number(options.id),
      status,
      isPending: status === 'pending',
    })
  },

  openDetail() {
    wx.redirectTo({
      url: `/pages/registration-detail/index?id=${this.data.id}`,
    })
  },

  openList() {
    wx.redirectTo({ url: '/pages/registration-list/index' })
  },

  back() {
    wx.navigateBack({ delta: 1 })
  },
})
