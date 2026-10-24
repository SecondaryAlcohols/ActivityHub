<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { register } from '@/api/attendee'
import { setSession } from '@/auth'
import { toast } from '@/toast'

const route = useRoute()
const router = useRouter()

const form = reactive({
  username: '',
  password: '',
  confirmPassword: '',
  nickname: '',
  phone: '',
})
const loading = ref(false)

function validate() {
  const username = form.username.trim()
  if (!/^[A-Za-z0-9_]{3,32}$/.test(username)) {
    return '用户名需为 3-32 位字母、数字或下划线'
  }
  if (form.password.length < 8) {
    return '密码至少需要 8 位'
  }
  if (form.password !== form.confirmPassword) {
    return '两次输入的密码不一致'
  }
  const phone = form.phone.trim()
  if (phone && !/^1[3-9]\d{9}$/.test(phone)) {
    return '请输入有效的手机号'
  }
  return null
}

async function submit() {
  const error = validate()
  if (error) {
    toast(error, 'info')
    return
  }
  if (loading.value) return

  loading.value = true
  try {
    const result = await register({
      username: form.username.trim(),
      password: form.password,
      nickname: form.nickname.trim() || undefined,
      phone: form.phone.trim() || undefined,
    })
    setSession(result)
    toast('注册成功，已自动登录', 'success')
    const redirect =
      typeof route.query.redirect === 'string'
        ? route.query.redirect
        : '/'
    router.replace(redirect)
  } catch {
    // 错误提示由请求拦截器处理
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="page register-page">
    <section class="register-visual">
      <div class="eyebrow">JOIN US</div>
      <h1>创建账号<br />开始你的活动之旅</h1>
      <p>注册后即可报名活动、查看审核状态与电子票。</p>
    </section>

    <section class="register-card">
      <h2>注册账号</h2>
      <p class="register-desc">用户名用于登录，昵称用于展示。</p>

      <form class="register-form" @submit.prevent="submit">
        <label class="form-item">
          <span>用户名 <em>*</em></span>
          <input
            v-model="form.username"
            class="input"
            maxlength="32"
            placeholder="3-32 位字母、数字或下划线"
            autocomplete="username"
          />
        </label>

        <label class="form-item">
          <span>密码 <em>*</em></span>
          <input
            v-model="form.password"
            class="input"
            type="password"
            maxlength="128"
            placeholder="至少 8 位"
            autocomplete="new-password"
          />
        </label>

        <label class="form-item">
          <span>确认密码 <em>*</em></span>
          <input
            v-model="form.confirmPassword"
            class="input"
            type="password"
            maxlength="128"
            placeholder="再次输入密码"
            autocomplete="new-password"
            @keyup.enter="submit"
          />
        </label>

        <label class="form-item">
          <span>昵称</span>
          <input
            v-model="form.nickname"
            class="input"
            maxlength="64"
            placeholder="选填，默认使用用户名"
          />
        </label>

        <label class="form-item">
          <span>手机号</span>
          <input
            v-model="form.phone"
            class="input"
            type="tel"
            maxlength="11"
            placeholder="选填，用于报名信息"
            autocomplete="tel"
          />
        </label>

        <button
          type="submit"
          class="primary-btn register-btn"
          :disabled="loading"
        >
          {{ loading ? '注册中…' : '注册并登录' }}
        </button>
      </form>

      <div class="register-links">
        <span class="muted">已有账号？</span>
        <router-link
          :to="{ name: 'login', query: route.query }"
          class="text-link"
        >
          去登录
        </router-link>
        <router-link to="/" class="text-link muted-link">
          先逛逛 →
        </router-link>
      </div>
    </section>
  </div>
</template>

<style scoped>
.register-page {
  padding-top: 4px;
}

.register-visual {
  position: relative;
  padding: 30px 24px 28px;
  overflow: hidden;
  color: #fff;
  border-radius: 22px;
  background:
    radial-gradient(circle at 88% 0%, rgba(124, 92, 255, 0.6), transparent 48%),
    linear-gradient(140deg, #1c2650, #2f46a8 58%, #5a3fd6);
  box-shadow: 0 16px 44px rgba(47, 70, 168, 0.22);
}

.register-visual::after {
  content: '';
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(255, 255, 255, 0.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.05) 1px, transparent 1px);
  background-size: 32px 32px;
  mask-image: linear-gradient(to bottom, rgba(0, 0, 0, 0.7), transparent 90%);
  pointer-events: none;
}

.eyebrow {
  position: relative;
  z-index: 1;
  font-size: 10px;
  letter-spacing: 3px;
  color: rgba(255, 255, 255, 0.6);
}

.register-visual h1 {
  position: relative;
  z-index: 1;
  margin: 14px 0 0;
  font-size: 27px;
  line-height: 1.38;
  font-weight: 600;
  letter-spacing: -0.5px;
}

.register-visual p {
  position: relative;
  z-index: 1;
  margin: 14px 0 0;
  max-width: 300px;
  color: rgba(255, 255, 255, 0.68);
  font-size: 13px;
  line-height: 1.7;
}

.register-card {
  margin-top: 18px;
  padding: 24px 20px;
  border-radius: 20px;
  background: #fff;
  box-shadow: var(--shadow);
}

.register-card h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 650;
}

.register-desc {
  margin: 6px 0 20px;
  color: var(--muted);
  font-size: 12.5px;
}

.register-form {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.form-item {
  display: flex;
  flex-direction: column;
  gap: 7px;
  font-size: 13px;
  font-weight: 500;
}

.form-item em {
  color: #e5484d;
  font-style: normal;
}

.register-btn {
  margin-top: 4px;
}

.register-links {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 18px;
  font-size: 12.5px;
}

.text-link {
  color: var(--primary);
}

.muted-link {
  margin-left: auto;
  color: #9ca3af;
}
</style>
