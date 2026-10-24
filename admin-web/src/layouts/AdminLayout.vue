<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowDown, Calendar } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const activeMenu = computed(() =>
  route.path.startsWith('/activities') ? '/activities' : route.path,
)

const pageTitle = computed(() => {
  if (route.name === 'activity-create') return '新建活动'
  if (route.name === 'activity-edit') return '编辑活动'
  if (route.name === 'activity-registrations') return '报名管理'
  return '活动管理'
})

const displayName = computed(
  () => auth.admin?.display_name || auth.admin?.username || '管理员',
)

const initials = computed(() => displayName.value.slice(0, 1))

onMounted(() => {
  auth.refreshAdmin().catch(() => {
    // 401 已由请求拦截器统一处理
  })
})

async function handleCommand(command: string) {
  if (command !== 'logout') return
  auth.logout()
  ElMessage.success('已退出登录')
  await router.replace('/login')
}
</script>

<template>
  <el-container class="admin-shell">
    <el-aside width="224px" class="sidebar">
      <div class="brand">
        <div class="brand-mark">签</div>
        <div class="brand-text">
          <div class="brand-name">活动管理平台</div>
          <div class="brand-sub">EVENT OPS</div>
        </div>
      </div>

      <el-menu :default-active="activeMenu" router class="side-menu">
        <el-menu-item index="/activities">
          <el-icon><Calendar /></el-icon>
          <span>活动管理</span>
        </el-menu-item>
      </el-menu>

      <div class="sidebar-footer">v0.1.0 · 骨架版</div>
    </el-aside>

    <el-container class="main-shell">
      <el-header class="topbar">
        <div class="page-title">{{ pageTitle }}</div>
        <el-dropdown trigger="click" @command="handleCommand">
          <span class="user-chip">
            <el-avatar :size="30" class="user-avatar">{{ initials }}</el-avatar>
            <span class="user-name">{{ displayName }}</span>
            <el-icon><ArrowDown /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="logout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </el-header>

      <el-main class="content">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.admin-shell {
  height: 100vh;
  overflow: hidden;
}

.sidebar {
  display: flex;
  flex-direction: column;
  background: #1d2433;
  color: #e5e7eb;
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 22px 20px 18px;
}

.brand-mark {
  display: grid;
  place-items: center;
  width: 38px;
  height: 38px;
  border-radius: 10px;
  background: linear-gradient(135deg, #4f6ef7, #7c5cff);
  color: #fff;
  font-weight: 700;
  font-size: 18px;
  box-shadow: 0 6px 16px rgba(79, 110, 247, 0.35);
}

.brand-text {
  min-width: 0;
}

.brand-name {
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 0.5px;
}

.brand-sub {
  margin-top: 2px;
  font-size: 10px;
  letter-spacing: 1.6px;
  color: #8b96ad;
}

.side-menu {
  flex: 1;
  border-right: none;
  background: transparent;
  padding: 8px 12px;
}

.side-menu :deep(.el-menu-item) {
  height: 44px;
  margin-bottom: 4px;
  border-radius: 8px;
  color: #aeb8cc;
}

.side-menu :deep(.el-menu-item:hover) {
  background: rgba(255, 255, 255, 0.06);
  color: #fff;
}

.side-menu :deep(.el-menu-item.is-active) {
  background: rgba(91, 116, 255, 0.18);
  color: #fff;
}

.sidebar-footer {
  padding: 16px 20px 20px;
  font-size: 11px;
  color: #6f7a90;
}

.main-shell {
  min-width: 0;
  background: var(--app-bg);
}

.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 64px;
  padding: 0 24px;
  background: #fff;
  border-bottom: 1px solid var(--app-border);
}

.page-title {
  font-size: 16px;
  font-weight: 600;
}

.user-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 6px 10px;
  border-radius: 999px;
  transition: background 0.15s ease;
}

.user-chip:hover {
  background: #f3f5f9;
}

.user-avatar {
  background: linear-gradient(135deg, #4f6ef7, #7c5cff);
  color: #fff;
  font-size: 13px;
}

.user-name {
  font-size: 14px;
  color: #374151;
}

.content {
  padding: 24px;
  overflow-y: auto;
}

@media (max-width: 760px) {
  .sidebar {
    width: 72px !important;
  }

  .brand {
    justify-content: center;
    padding: 18px 8px;
  }

  .brand-text,
  .sidebar-footer,
  .side-menu :deep(.el-menu-item span) {
    display: none;
  }

  .side-menu :deep(.el-menu-item) {
    justify-content: center;
    padding: 0;
  }

  .content {
    padding: 16px;
  }

  .user-name {
    display: none;
  }
}
</style>
