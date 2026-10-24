const { API_BASE } = require('../config')

function buildQuery(params) {
  if (!params) return ''
  const parts = Object.keys(params)
    .filter(
      (key) =>
        params[key] !== undefined &&
        params[key] !== null &&
        params[key] !== '',
    )
    .map(
      (key) =>
        `${encodeURIComponent(key)}=${encodeURIComponent(params[key])}`,
    )
  return parts.length ? `?${parts.join('&')}` : ''
}

function request(options) {
  const { path, method = 'GET', data, params, withAuth = true } = options

  return new Promise((resolve, reject) => {
    const token = wx.getStorageSync('mp_token')
    const header = { 'Content-Type': 'application/json' }
    if (withAuth && token) {
      header.Authorization = `Bearer ${token}`
    }

    wx.request({
      url: `${API_BASE}${path}${buildQuery(params)}`,
      method,
      data,
      header,
      success(res) {
        const body = res.data || {}
        if (
          res.statusCode >= 200 &&
          res.statusCode < 300 &&
          body.code === 0
        ) {
          resolve(body.data)
          return
        }

        const message = body.message || '请求失败，请稍后重试'
        if (res.statusCode === 401) {
          wx.removeStorageSync('mp_token')
          wx.removeStorageSync('mp_attendee')
        }
        wx.showToast({ title: message, icon: 'none' })
        reject(new Error(message))
      },
      fail(err) {
        wx.showToast({
          title: '网络异常，请确认后端服务已启动',
          icon: 'none',
        })
        reject(err)
      },
    })
  })
}

module.exports = {
  get(path, params, options = {}) {
    return request({ path, params, ...options })
  },
  post(path, data, options = {}) {
    return request({ path, method: 'POST', data, ...options })
  },
  put(path, data, options = {}) {
    return request({ path, method: 'PUT', data, ...options })
  },
}
