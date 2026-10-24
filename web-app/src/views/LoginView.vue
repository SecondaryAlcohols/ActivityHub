<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { webLogin } from '@/api/attendee'
import { setSession } from '@/auth'
import { toast } from '@/toast'

const route = useRoute()
const router = useRouter()

const form = reactive({ nickname: '', phone: '' })
const loading = ref(false)

async function submit() {
  const nickname = form.nickname.trim()
  const phone = form.phone.trim()
  if (!nickname) {
    toast('请输入昵称', 'info')
    return
  }
  if (!/^1[3-9]\d{9}$/.test(phone)) {
    toast('请输入有效的手机号', 'info')
    return
  }
  if (loading.value) return

  loading.value = true
  try {
    const result = await webLogin(nickname, phone)
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
      <div class="eyebrow">WELCOME</div>
      <h1>报名一场<br />值得期待的活动</h1>
      <p>登录后即可报名、查看审核状态并出示电子票。</p>
      <div class="visual-tags">
        <span>活动浏览</span>
        <span>在线报名</span>
        <span>电子票</span>
      </div>
    </section>

    <section class="login-card">
      <h2>体验登录</h2>
      <p class="login-desc">输入昵称和手机号即可进入，无需密码。</p>

      <form class="login-form" @submit.prevent="submit">
        <label class="form-item">
          <span>昵称</span>
          <input
            v-model="form.nickname"
            class="input"
            maxlength="64"
            placeholder="怎么称呼你"
            autocomplete="nickname"
          />
        </label>
        <label class="form-item">
          <span>手机号</span>
          <input
            v-model="form.phone"
            class="input"
            type="tel"
            maxlength="11"
            placeholder="用于报名信息"
            autocomplete="tel"
          />
        </label>

        <button
          type="submit"
          class="primary-btn login-btn"
          :disabled="loading"
        >
          {{ loading ? '登录中…' : '进入活动广场' }}
        </button>
      </form>

      <p class="login-note">
        这是演示用的体验登录，不验证手机号归属。正式使用时应接入微信授权或短信验证。
      </p>
      <router-link to="/" class="browse-link">先随便逛逛 →</router-link>
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

.login-note {
  margin: 18px 0 0;
  color: #a0a7b4;
  font-size: 11px;
  line-height: 1.7;
}

.browse-link {
  display: inline-block;
  margin-top: 14px;
  color: var(--primary);
  font-size: 12.5px;
}
</style>
