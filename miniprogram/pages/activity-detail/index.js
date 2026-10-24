const request = require('../../utils/request')
const auth = require('../../utils/auth')
const { formatDateTime } = require('../../utils/date')

const REASON_TEXT = {
  activity_closed: '活动已下架或结束',
  already_registered: '你已报名该活动',
  not_started: '报名尚未开始',
  closed: '报名已截止',
  full: '名额已满',
}

Page({
  data: {
    id: null,
    activity: null,
    loading: true,
    loadedOnce: false,
    actionText: '',
  },

  onLoad(options) {
    this.setData({ id: Number(options.id) })
    this.load()
  },

  onShow() {
    if (this.data.loadedOnce) {
      this.load()
    }
  },

  load() {
    this.setData({ loading: true })
    auth
      .ensureLogin()
      .catch(() => {})
      .then(() => request.get(`/api/mp/activities/${this.data.id}`))
      .then((activity) => {
        const reasonText =
          REASON_TEXT[activity.signup_state.reason] || ''
        const registration = activity.my_registration
        const activeRegistration =
          registration &&
          ['pending', 'approved'].includes(registration.status)

        let actionText = '暂不可报名'
        if (activeRegistration) {
          actionText = '查看报名'
        } else if (activity.signup_state.can_signup) {
          actionText = '立即报名'
        } else if (reasonText) {
          actionText = reasonText
        }

        this.setData({
          activity: {
            ...activity,
            startText: formatDateTime(activity.start_at),
            endText: formatDateTime(activity.end_at),
            signupText: `${formatDateTime(activity.signup_start_at)} 至 ${formatDateTime(activity.signup_end_at)}`,
            reasonText,
          },
          actionText,
          loading: false,
          loadedOnce: true,
        })
      })
      .catch(() => {
        this.setData({ loading: false, loadedOnce: true })
      })
  },

  handleAction() {
    const activity = this.data.activity
    if (!activity) return

    const registration = activity.my_registration
    if (
      registration &&
      ['pending', 'approved'].includes(registration.status)
    ) {
      wx.navigateTo({
        url: `/pages/registration-detail/index?id=${registration.id}`,
      })
      return
    }

    if (!activity.signup_state.can_signup) {
      wx.showToast({
        title: activity.reasonText || '当前不可报名',
        icon: 'none',
      })
      return
    }

    auth
      .ensureLogin()
      .then(() => {
        wx.navigateTo({
          url: `/pages/signup-form/index?activityId=${activity.id}`,
        })
      })
      .catch(() => {})
  },

  openMyRegistrations() {
    wx.navigateTo({ url: '/pages/registration-list/index' })
  },
})
