<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'

import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const formRef = ref<FormInstance>()
const loading = ref(false)
const form = reactive({
  username: '',
  password: '',
})

const rules: FormRules = {
  username: [{ required: true, message: '请输入账号', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function submit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    await auth.login(form.username, form.password)
    ElMessage.success('登录成功')
    const redirect =
      typeof route.query.redirect === 'string'
        ? route.query.redirect
        : '/activities'
    await router.replace(redirect)
  } catch {
    // 错误提示由请求拦截器统一处理
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <section class="login-visual">
      <div class="brand-row">
        <div class="brand-mark">签</div>
        <span class="brand-name">EventFlow</span>
      </div>

      <div class="visual-copy">
        <p class="eyebrow">EVENT OPERATIONS</p>
        <h1>让每一场活动<br />从报名到签到<br /><span>井井有条</span></h1>
        <p class="visual-desc">
          发布活动、配置报名表、审核名单、现场扫码核销，一套后台完成。
        </p>
      </div>

      <ul class="feature-list">
        <li><span>01</span> 灵活配置报名表单</li>
        <li><span>02</span> 名额实时控制与审核</li>
        <li><span>03</span> 扫码签到与数据导出</li>
      </ul>
    </section>

    <section class="login-panel">
      <div class="login-card">
        <h2>登录管理后台</h2>
        <p class="muted login-subtitle">使用管理员账号继续</p>

        <el-form
          ref="formRef"
          :model="form"
          :rules="rules"
          size="large"
          @submit.prevent="submit"
        >
          <el-form-item prop="username">
            <el-input
              v-model="form.username"
              placeholder="管理员账号"
              autocomplete="username"
            />
          </el-form-item>
          <el-form-item prop="password">
            <el-input
              v-model="form.password"
              type="password"
              placeholder="登录密码"
              show-password
              autocomplete="current-password"
              @keyup.enter="submit"
            />
          </el-form-item>
          <el-button
            type="primary"
            size="large"
            class="login-button"
            :loading="loading"
            @click="submit"
          >
            登录
          </el-button>
        </el-form>

        <p class="login-hint">
          首次使用请先运行初始化脚本创建管理员账号，详见 README。
        </p>
      </div>

      <p class="footer-note">活动报名与签到管理系统 · v0.1</p>
    </section>
  </div>
</template>

<style scoped>
.login-page {
  display: flex;
  min-height: 100vh;
  background: #fff;
}

.login-visual {
  position: relative;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  width: 46%;
  padding: 48px 52px;
  overflow: hidden;
  color: #fff;
  background:
    radial-gradient(circle at 80% 10%, rgba(124, 92, 255, 0.55), transparent 42%),
    radial-gradient(circle at 10% 90%, rgba(79, 110, 247, 0.45), transparent 45%),
    linear-gradient(145deg, #1c2650 0%, #2f46a8 55%, #5a3fd6 100%);
}

.login-visual::after {
  content: '';
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(255, 255, 255, 0.045) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.045) 1px, transparent 1px);
  background-size: 44px 44px;
  mask-image: linear-gradient(to bottom, rgba(0, 0, 0, 0.7), transparent 85%);
  pointer-events: none;
}

.brand-row {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: 10px;
}

.brand-mark {
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.14);
  border: 1px solid rgba(255, 255, 255, 0.22);
  font-weight: 700;
  font-size: 17px;
  backdrop-filter: blur(6px);
}

.brand-name {
  font-size: 17px;
  font-weight: 600;
  letter-spacing: 0.4px;
}

.visual-copy {
  position: relative;
  z-index: 1;
  max-width: 460px;
}

.eyebrow {
  margin: 0 0 18px;
  font-size: 11px;
  letter-spacing: 3px;
  color: rgba(255, 255, 255, 0.62);
}

.visual-copy h1 {
  margin: 0;
  font-size: clamp(32px, 3.4vw, 48px);
  line-height: 1.28;
  font-weight: 600;
  letter-spacing: -0.5px;
}

.visual-copy h1 span {
  color: #c7d2ff;
  box-shadow: inset 0 -10px 0 rgba(124, 92, 255, 0.25);
}

.visual-desc {
  margin: 22px 0 0;
  max-width: 380px;
  font-size: 14px;
  line-height: 1.8;
  color: rgba(255, 255, 255, 0.68);
}

.feature-list {
  position: relative;
  z-index: 1;
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.78);
}

.feature-list li {
  display: flex;
  align-items: center;
  gap: 12px;
}

.feature-list span {
  font-size: 11px;
  letter-spacing: 1px;
  color: #a9b6ff;
}

.login-panel {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  padding: 40px 24px;
  background: #fff;
}

.login-card {
  width: 100%;
  max-width: 360px;
}

.login-card h2 {
  margin: 0;
  font-size: 26px;
  font-weight: 600;
  letter-spacing: -0.3px;
}

.login-subtitle {
  margin: 8px 0 30px;
  font-size: 14px;
}

.login-button {
  width: 100%;
  margin-top: 6px;
  height: 44px;
  font-weight: 600;
}

.login-hint {
  margin-top: 26px;
  font-size: 12px;
  line-height: 1.7;
  color: #9ca3af;
}

.footer-note {
  position: absolute;
  bottom: 24px;
  margin: 0;
  font-size: 11px;
  color: #b0b7c3;
}

@media (max-width: 900px) {
  .login-page {
    justify-content: center;
    background: var(--app-bg);
  }

  .login-visual {
    display: none;
  }

  .login-panel {
    flex: none;
    width: 100%;
    background: transparent;
  }

  .login-card {
    padding: 36px 28px;
    background: #fff;
    border-radius: 16px;
    box-shadow: 0 12px 40px rgba(31, 41, 55, 0.08);
  }
}
</style>
