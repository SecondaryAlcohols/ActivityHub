<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { login } from '@/api/attendee'
import { setSession } from '@/auth'
import { toast } from '@/toast'

const route = useRoute()
const router = useRouter()

const form = reactive({ username: '', password: '' })
const loading = ref(false)

async function submit() {
  const username = form.username.trim()
  if (!username) {
    toast('请输入用户名', 'info')
    return
  }
  if (!form.password) {
    toast('请输入密码', 'info')
    return
  }
  if (loading.value) return

  loading.value = true
  try {
    const result = await login(username, form.password)
    setSession(result)
    toast('登录成功', 'success')
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
  <div class="page login-page">
    <section class="login-visual">
      <div class="eyebrow">WELCOME BACK</div>
      <h1>登录你的<br />活动账号</h1>
      <p>登录后即可报名、查看审核状态并出示电子票。</p>
      <div class="visual-tags">
        <span>在线报名</span>
        <span>我的报名</span>
        <span>电子票</span>
      </div>
    </section>

    <section class="login-card">
      <h2>登录</h2>
      <p class="login-desc">使用注册时的用户名和密码继续。</p>

      <form class="login-form" @submit.prevent="submit">
        <label class="form-item">
          <span>用户名</span>
          <input
            v-model="form.username"
            class="input"
            maxlength="32"
            placeholder="请输入用户名"
            autocomplete="username"
          />
        </label>
        <label class="form-item">
          <span>密码</span>
          <input
            v-model="form.password"
            class="input"
            type="password"
            maxlength="128"
            placeholder="请输入密码"
            autocomplete="current-password"
            @keyup.enter="submit"
          />
        </label>

        <button
          type="submit"
          class="primary-btn login-btn"
          :disabled="loading"
        >
          {{ loading ? '登录中…' : '登录' }}
        </button>
      </form>

      <div class="login-links">
        <router-link
          :to="{ name: 'register', query: route.query }"
          class="text-link"
        >
          还没有账号？立即注册
        </router-link>
        <router-link to="/" class="text-link muted-link">
          先随便逛逛 →
        </router-link>
      </div>
    </section>
  </div>
</template>

<style scoped>
.login-page {
  padding-top: 4px;
}

.login-visual {
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

.login-visual::after {
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

.login-visual h1 {
  position: relative;
  z-index: 1;
  margin: 14px 0 0;
  font-size: 27px;
  line-height: 1.38;
  font-weight: 600;
  letter-spacing: -0.5px;
}

.login-visual p {
  position: relative;
  z-index: 1;
  margin: 14px 0 0;
  max-width: 300px;
  color: rgba(255, 255, 255, 0.68);
  font-size: 13px;
  line-height: 1.7;
}

.visual-tags {
  position: relative;
  z-index: 1;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 20px;
}

.visual-tags span {
  padding: 5px 12px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.08);
  color: rgba(255, 255, 255, 0.78);
  font-size: 11px;
}

.login-card {
  margin-top: 18px;
  padding: 24px 20px;
  border-radius: 20px;
  background: #fff;
  box-shadow: var(--shadow);
}

.login-card h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 650;
}

.login-desc {
  margin: 6px 0 20px;
  color: var(--muted);
  font-size: 12.5px;
}

.login-form {
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

.login-btn {
  margin-top: 4px;
}

.login-links {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 18px;
}

.text-link {
  color: var(--primary);
  font-size: 12.5px;
}

.muted-link {
  color: #9ca3af;
}
</style>
