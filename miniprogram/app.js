const auth = require('./utils/auth')

App({
  globalData: {
    attendee: null,
  },
  onLaunch() {
    auth
      .ensureLogin()
      .then((data) => {
        this.globalData.attendee = data.attendee
      })
      .catch(() => {
        // 首页仍可浏览公开活动，登录会在报名时再次触发
      })
  },
})
