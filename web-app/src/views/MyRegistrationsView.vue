<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { fetchMe, fetchMyRegistrations, updateProfile } from '@/api/attendee'
import { isLoggedIn, updateUser, user } from '@/auth'
import StatusTag from '@/components/StatusTag.vue'
import { toast } from '@/toast'
import type { RegistrationItem, RegistrationStatus } from '@/types'
import { formatDateTime } from '@/utils/format'

const tabs: { key: RegistrationStatus | ''; label: string }[] = [
  { key: '', label: '全部' },
  { key: 'pending', label: '待审核' },
  { key: 'approved', label: '已通过' },
  { key: 'rejected', label: '已拒绝' },
  { key: 'cancelled', label: '已取消' },
]

const activeStatus = ref<RegistrationStatus | ''>('')
const items = ref<(RegistrationItem & { startText: string; endText: string })[]>([])
const page = ref(1)
const pageSize = 10
const total = ref(0)
const hasMore = ref(true)
const loading = ref(false)
const editing = ref(false)
const nicknameDraft = ref('')
const saving = ref(false)

const initial = () => (user.value?.nickname || '微').slice(0, 1)

async function load(reset = true) {
  if (!isLoggedIn.value || loading.value) return
  loading.value = true
  const nextPage = reset ? 1 : page.value + 1
  try {
    const data = await fetchMyRegistrations({
      status: activeStatus.value || undefined,
      page: nextPage,
      page_size: pageSize,
    })
    const list = data.items.map((item) => ({
      ...item,
      startText: formatDateTime(item.activity.start_at),
      endText: formatDateTime(item.activity.end_at),
    }))
    items.value = reset ? list : items.value.concat(list)
    page.value = nextPage
    total.value = data.total
    hasMore.value = items.value.length < data.total
  } catch {
    // 错误提示由请求拦截器处理
  } finally {
    loading.value = false
  }
}

async function loadUser() {
  if (!isLoggedIn.value) return
  try {
    const attendee = await fetchMe()
    updateUser(attendee)
  } catch {
    // 错误提示由请求拦截器处理
  }
}

function switchTab(key: RegistrationStatus | '') {
  if (key === activeStatus.value) return
  activeStatus.value = key
  items.value = []
  hasMore.value = true
  load(true)
}

function startEdit() {
  nicknameDraft.value = user.value?.nickname || ''
  editing.value = true
}

async function saveNickname() {
  const nickname = nicknameDraft.value.trim()
  if (!nickname) {
    toast('请输入昵称', 'info')
    return
  }
  saving.value = true
  try {
    const attendee = await updateProfile(nickname)
    updateUser(attendee)
    editing.value = false
    toast('昵称已更新', 'success')
  } catch {
    // 错误提示由请求拦截器处理
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  await loadUser()
  await load(true)
})
</script>

<template>
  <div class="page my-page">
    <template v-if="!isLoggedIn">
      <div class="login-prompt">
        <div class="prompt-icon">签</div>
        <h1>登录后查看报名</h1>
        <p>使用昵称和手机号体验登录，查看报名状态与电子票。</p>
        <router-link
          to="/login?redirect=/my"
          class="primary-btn prompt-btn"
        >
          体验登录
        </router-link>
      </div>
    </template>

    <template v-else>
      <section class="profile-card">
        <div class="profile-avatar">{{ initial() }}</div>
        <div class="profile-info">
          <template v-if="!editing">
            <div class="profile-name">
              {{ user?.nickname || '微信用户' }}
              <button type="button" class="edit-link" @click="startEdit">
                修改
              </button>
            </div>
          </template>
          <template v-else>
            <div class="nickname-edit">
              <input
                v-model="nicknameDraft"
                class="nickname-input"
                maxlength="64"
                placeholder="请输入昵称"
                @keyup.enter="saveNickname"
              />
              <button
                type="button"
                class="save-btn"
                :disabled="saving"
                @click="saveNickname"
              >
                保存
              </button>
              <button
                type="button"
                class="cancel-btn"
                @click="editing = false"
              >
                取消
              </button>
            </div>
          </template>
          <div class="profile-phone">{{ user?.phone || '未填写手机号' }}</div>
        </div>
      </section>

      <div class="tabs">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          type="button"
          class="tab"
          :class="{ active: activeStatus === tab.key }"
          @click="switchTab(tab.key)"
        >
          {{ tab.label }}
        </button>
      </div>

      <section class="registration-list">
        <article
          v-for="item in items"
          :key="item.id"
          class="registration-card"
          @click="$router.push(`/registrations/${item.id}`)"
        >
          <div class="card-top">
            <h2>{{ item.activity.title }}</h2>
            <StatusTag :status="item.status" />
          </div>
          <div class="meta-row">
            {{ item.startText }} 至 {{ item.endText }}
          </div>
          <div class="meta-row">{{ item.activity.location_name }}</div>
          <div class="card-footer">
            <span>{{ item.applicant_name }} · {{ item.applicant_phone }}</span>
            <span class="detail-link">查看详情 →</span>
          </div>
        </article>

        <div v-if="loading" class="loading">加载中…</div>
        <div v-else-if="!items.length" class="empty">
          <div>还没有报名记录</div>
          <div class="empty-hint">去活动广场看看有没有感兴趣的活动</div>
        </div>
        <button
          v-else-if="hasMore"
          type="button"
          class="load-more"
          @click="load(false)"
        >
          加载更多
        </button>
        <div v-else class="list-end">共 {{ total }} 条报名</div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.login-prompt {
  margin-top: 30px;
  padding: 40px 26px 30px;
  text-align: center;
  border-radius: 22px;
  background: #fff;
  box-shadow: var(--shadow);
}

.prompt-icon {
  display: grid;
  place-items: center;
  width: 58px;
  height: 58px;
  margin: 0 auto 18px;
  border-radius: 16px;
  background: linear-gradient(135deg, #4f6ef7, #7c5cff);
  color: #fff;
  font-size: 24px;
  font-weight: 700;
}

.login-prompt h1 {
  margin: 0;
  font-size: 21px;
  font-weight: 650;
}

.login-prompt p {
  margin: 10px auto 22px;
  max-width: 280px;
  color: var(--muted);
  font-size: 12.5px;
  line-height: 1.7;
}

.prompt-btn {
  width: 220px;
  margin: 0 auto;
}

.profile-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 20px;
  border-radius: 20px;
  color: #fff;
  background:
    radial-gradient(circle at 90% 0%, rgba(124, 92, 255, 0.55), transparent 45%),
    linear-gradient(140deg, #1c2650, #2f46a8 62%, #5a3fd6);
  box-shadow: 0 14px 38px rgba(47, 70, 168, 0.22);
}

.profile-avatar {
  display: grid;
  place-items: center;
  width: 48px;
  height: 48px;
  flex-shrink: 0;
  border: 1px solid rgba(255, 255, 255, 0.3);
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.15);
  font-size: 19px;
  font-weight: 600;
}

.profile-info {
  flex: 1;
  min-width: 0;
}

.profile-name {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 17px;
  font-weight: 600;
}

.edit-link {
  padding: 2px 8px;
  border: 1px solid rgba(255, 255, 255, 0.25);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.1);
  color: rgba(255, 255, 255, 0.8);
  font-size: 10px;
}

.profile-phone {
  margin-top: 5px;
  color: rgba(255, 255, 255, 0.65);
  font-size: 12px;
}

.nickname-edit {
  display: flex;
  align-items: center;
  gap: 6px;
}

.nickname-input {
  width: 130px;
  height: 30px;
  padding: 0 10px;
  border: 1px solid rgba(255, 255, 255, 0.3);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.14);
  color: #fff;
  font-size: 12px;
  outline: none;
}

.nickname-input::placeholder {
  color: rgba(255, 255, 255, 0.5);
}

.save-btn,
.cancel-btn {
  height: 30px;
  padding: 0 10px;
  border: none;
  border-radius: 8px;
  font-size: 11px;
}

.save-btn {
  background: #fff;
  color: var(--primary);
}

.cancel-btn {
  background: rgba(255, 255, 255, 0.14);
  color: rgba(255, 255, 255, 0.8);
}

.tabs {
  display: flex;
  gap: 8px;
  margin: 18px 0 14px;
  overflow-x: auto;
  scrollbar-width: none;
}

.tabs::-webkit-scrollbar {
  display: none;
}

.tab {
  flex-shrink: 0;
  padding: 8px 15px;
  border: 1px solid transparent;
  border-radius: 999px;
  background: #fff;
  color: var(--muted);
  font-size: 12.5px;
  box-shadow: 0 4px 14px rgba(31, 41, 55, 0.04);
}

.tab.active {
  background: var(--primary);
  color: #fff;
}

.registration-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.registration-card {
  padding: 17px 18px;
  border-radius: 17px;
  background: #fff;
  box-shadow: var(--shadow);
  cursor: pointer;
  transition: transform 0.15s ease;
}

.registration-card:hover {
  transform: translateY(-1px);
}

.card-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.card-top h2 {
  flex: 1;
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  line-height: 1.45;
}

.meta-row {
  margin-top: 7px;
  color: var(--muted);
  font-size: 12px;
}

.card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 13px;
  padding-top: 11px;
  border-top: 1px solid #f0f2f6;
  color: var(--soft);
  font-size: 11.5px;
}

.detail-link {
  color: var(--primary);
}
</style>
