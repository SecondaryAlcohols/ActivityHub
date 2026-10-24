const request = require('../../utils/request')
const auth = require('../../utils/auth')

const PHONE_RE = /^1[3-9]\d{9}$/
const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/

Page({
  data: {
    activityId: null,
    activity: null,
    fields: [],
    loading: true,
    submitting: false,
  },

  onLoad(options) {
    this.setData({ activityId: Number(options.activityId) })
    this.init()
  },

  init() {
    auth
      .ensureLogin()
      .then(() => request.get(`/api/mp/activities/${this.data.activityId}`))
      .then((activity) => {
        if (!activity.signup_state.can_signup) {
          wx.showToast({
            title: '当前不可报名',
            icon: 'none',
          })
          setTimeout(() => wx.navigateBack(), 800)
          return
        }

        const attendee = wx.getStorageSync('mp_attendee') || {}
        const previous =
          (activity.my_registration && activity.my_registration.answers) || {}

        const fields = (activity.form_schema || []).map((field) => {
          const options = field.options || []
          let value = ''

          if (field.type === 'multi_select') {
            value = Array.isArray(previous[field.key])
              ? previous[field.key]
              : []
          } else if (previous[field.key] !== undefined) {
            value = previous[field.key]
          } else if (field.key === 'phone') {
            value = attendee.phone || ''
          }

          return {
            ...field,
            options,
            value,
            selectedIndex: Math.max(0, options.indexOf(value)),
            choices: options.map((label) => ({
              label,
              selected: Array.isArray(value) && value.includes(label),
            })),
          }
        })

        this.setData({ activity, fields, loading: false })
      })
      .catch(() => {
        this.setData({ loading: false })
      })
  },

  onInput(event) {
    const index = Number(event.currentTarget.dataset.index)
    this.setData({
      [`fields[${index}].value`]: event.detail.value,
    })
  },

  onPickerChange(event) {
    const index = Number(event.currentTarget.dataset.index)
    const selectedIndex = Number(event.detail.value)
    const field = this.data.fields[index]
    this.setData({
      [`fields[${index}].value`]: field.options[selectedIndex],
      [`fields[${index}].selectedIndex`]: selectedIndex,
    })
  },

  onDateChange(event) {
    const index = Number(event.currentTarget.dataset.index)
    this.setData({
      [`fields[${index}].value`]: event.detail.value,
    })
  },

  toggleMulti(event) {
    const index = Number(event.currentTarget.dataset.index)
    const choiceIndex = Number(event.currentTarget.dataset.choiceIndex)
    const field = this.data.fields[index]
    const choices = field.choices.map((choice, currentIndex) =>
      currentIndex === choiceIndex
        ? { ...choice, selected: !choice.selected }
        : choice,
    )
    const value = choices
      .filter((choice) => choice.selected)
      .map((choice) => choice.label)

    this.setData({
      [`fields[${index}].choices`]: choices,
      [`fields[${index}].value`]: value,
    })
  },

  submit() {
    if (this.data.submitting) return

    const answers = {}
    for (const field of this.data.fields) {
      const value = field.value
      const isArray = Array.isArray(value)
      const empty = isArray ? value.length === 0 : !String(value || '').trim()

      if (field.required && empty) {
        wx.showToast({ title: `请填写${field.label}`, icon: 'none' })
        return
      }
      if (empty) continue

      if (field.type === 'phone' && !PHONE_RE.test(value)) {
        wx.showToast({ title: '手机号格式不正确', icon: 'none' })
        return
      }
      if (field.type === 'email' && !EMAIL_RE.test(value)) {
        wx.showToast({ title: '邮箱格式不正确', icon: 'none' })
        return
      }
      if (field.type === 'number' && Number.isNaN(Number(value))) {
        wx.showToast({ title: `${field.label}必须是数字`, icon: 'none' })
        return
      }

      answers[field.key] = value
    }

    this.setData({ submitting: true })
    request
      .post(`/api/mp/activities/${this.data.activityId}/registrations`, {
        answers,
      })
      .then((registration) => {
        wx.redirectTo({
          url: `/pages/signup-result/index?id=${registration.id}&status=${registration.status}`,
        })
      })
      .catch(() => {})
      .then(() => {
        this.setData({ submitting: false })
      })
  },
})
