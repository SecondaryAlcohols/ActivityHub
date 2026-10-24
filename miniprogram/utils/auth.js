const { MOCK_LOGIN, MOCK_USER } = require('../config')
const request = require('./request')

let loginPromise = null

function login() {
  if (loginPromise) return loginPromise

  loginPromise = new Promise((resolve, reject) => {
    const finish = (code) => {
      request
        .post('/api/mp/auth/login', { code }, { withAuth: false })
        .then((data) => {
          wx.setStorageSync('mp_token', data.access_token)
          wx.setStorageSync('mp_attendee', data.attendee)
          resolve(data)
        })
        .catch(reject)
    }

    if (MOCK_LOGIN) {
      finish(`mock:${MOCK_USER}`)
      return
    }

    wx.login({
      success(res) {
        if (!res.code) {
          reject(new Error('微信登录失败'))
          return
        }
        finish(res.code)
      },
      fail: reject,
    })
  })

  loginPromise.then(
    () => {
      loginPromise = null
    },
    () => {
      loginPromise = null
    },
  )
  return loginPromise
}

function ensureLogin() {
  if (wx.getStorageSync('mp_token')) {
    return Promise.resolve({ attendee: wx.getStorageSync('mp_attendee') })
  }
  return login()
}

function logout() {
  wx.removeStorageSync('mp_token')
  wx.removeStorageSync('mp_attendee')
}

module.exports = { login, ensureLogin, logout }
