const request = require('../../utils/request')
const auth = require('../../utils/auth')
const { MOCK_LOGIN, MOCK_USER } = require('../../config')

Page({
  data: {
    attendee: null,
    nickname: '',
    initial: '微',
    isMock: MOCK_LOGIN,
    mockUser: MOCK_USER,
    loading: true,
    saving: false,
  },

  onShow() {
    this.load()
  },

  load() {
    this.setData({ loading: true })
    auth
      .ensureLogin()
      .then(() => {
        const cached = wx.getStorageSync('mp_attendee') || null
        if (cached) {
          this.setData({
            attendee: cached,
            nickname: cached.nickname || '',
            initial: (cached.nickname || '微').slice(0, 1),
          })
        }
        return request.get('/api/mp/auth/me')
      })
      .then((attendee) => {
        wx.setStorageSync('mp_attendee', attendee)
        this.setData({
          attendee,
          nickname: attendee.nickname || '',
          initial: (attendee.nickname || '微').slice(0, 1),
        })
      })
      .catch(() => {})
      .then(() => {
        this.setData({ loading: false })
      })
  },

  onNicknameInput(event) {
    this.setData({ nickname: event.detail.value })
  },

  saveNickname() {
    const nickname = this.data.nickname.trim()
    if (!nickname) {
      wx.showToast({ title: '请输入昵称', icon: 'none' })
      return
    }
    if (this.data.saving) return

    this.setData({ saving: true })
    request
      .put('/api/mp/auth/profile', { nickname })
      .then((attendee) => {
        wx.setStorageSync('mp_attendee', attendee)
        this.setData({
          attendee,
          nickname: attendee.nickname,
          initial: (attendee.nickname || '微').slice(0, 1),
        })
        wx.showToast({ title: '已保存', icon: 'success' })
      })
      .catch(() => {})
      .then(() => {
        this.setData({ saving: false })
      })
  },

  openRegistrations() {
    wx.navigateTo({ url: '/pages/registration-list/index' })
  },
})
