<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'

import ToastHost from '@/components/ToastHost.vue'
import { useAuth } from '@/auth'
import { toast } from '@/toast'

const router = useRouter()
const { user, isLoggedIn, clearSession } = useAuth()

const displayName = computed(() => user.value?.nickname || '微信用户')
const initial = computed(() => displayName.value.slice(0, 1))

function handleLogout() {
  clearSession()
  toast('已退出登录', 'success')
  router.push('/')
}
</script>

<template>
  <div class="app-shell">
    <header class="app-header">
      <router-link to="/" class="brand">
        <span class="brand-mark">签</span>
        <span class="brand-name">活动报名</span>
      </router-link>

      <nav class="app-nav">
        <router-link to="/" class="nav-link" exact-active-class="active">
          活动
        </router-link>
        <router-link to="/my" class="nav-link" active-class="active">
          我的
        </router-link>
        <button
          v-if="isLoggedIn"
          class="user-chip"
          type="button"
          title="退出登录"
          @click="handleLogout"
        >
          <span class="user-avatar">{{ initial }}</span>
          <span class="user-name">{{ displayName }}</span>
        </button>
        <router-link v-else to="/login" class="login-link">登录</router-link>
      </nav>
    </header>

    <main class="app-main">
      <router-view />
    </main>

    <footer class="app-footer">活动报名与签到管理系统 · 网页版</footer>
    <ToastHost />
  </div>
</template>
