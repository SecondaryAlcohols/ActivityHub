<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { fetchActivity } from '@/api/attendee'
import { isLoggedIn } from '@/auth'
import { toast } from '@/toast'
import type { ActivityDetail } from '@/types'
import { REASON_TEXT, formatDateTime } from '@/utils/format'

const route = useRoute()
const router = useRouter()
const activityId = Number(route.params.id)

const activity = ref<ActivityDetail | null>(null)
const loading = ref(true)
const failed = ref(false)

const startText = computed(() =>
  formatDateTime(activity.value?.start_at),
)
const endText = computed(() => formatDateTime(activity.value?.end_at))
const signupText = computed(() => {
  if (!activity.value) return ''
  return `${formatDateTime(activity.value.signup_start_at)} 至 ${formatDateTime(activity.value.signup_end_at)}`
})
const reasonText = computed(() =>
  activity.value?.signup_state.reason
    ? REASON_TEXT[activity.value.signup_state.reason] || ''
    : '',
)
const activeRegistration = computed(() => {
  const registration = activity.value?.my_registration
  return Boolean(
    registration && ['pending', 'approved'].includes(registration.status),
  )
})
const actionText = computed(() => {
  if (activeRegistration.value) return '查看报名'
  if (activity.value?.signup_state.can_signup) return '立即报名'
  return reasonText.value || '暂不可报名'
})
const actionDisabled = computed(
  () => !activeRegistration.value && !activity.value?.signup_state.can_signup,
)

async function load() {
  loading.value = true
  failed.value = false
  try {
    activity.value = await fetchActivity(activityId)
  } catch {
    failed.value = true
  } finally {
    loading.value = false
  }
}

function handleAction() {
  const current = activity.value
  if (!current) return

  const registration = current.my_registration
  if (
    registration &&
    ['pending', 'approved'].includes(registration.status)
  ) {
    router.push(`/registrations/${registration.id}`)
    return
  }

  if (!current.signup_state.can_signup) {
    toast(reasonText.value || '当前不可报名', 'info')
    return
  }

  if (!isLoggedIn.value) {
    router.push({
      name: 'login',
      query: { redirect: `/activities/${activityId}/signup` },
    })
    return
  }
  router.push(`/activities/${activityId}/signup`)
}

function goBack() {
  router.push('/')
}

onMounted(load)
</script>

<template>
  <div class="page detail-page">
    <button type="button" class="back-link" @click="goBack">← 返回活动列表</button>

    <div v-if="loading" class="loading">加载中…</div>
    <div v-else-if="failed || !activity" class="empty">
      活动不存在或已下架
    </div>

    <template v-else>
      <div class="cover-wrap">
        <img
          v-if="activity.cover_url"
          :src="activity.cover_url"
          class="cover"
          alt=""
        />
        <div v-else class="cover cover-placeholder"><span>EVENT</span></div>
      </div>

      <div class="content">
        <div class="title-row">
          <h1>{{ activity.title }}</h1>
          <span v-if="activity.need_review" class="tag tag-warn">需审核</span>
          <span
            v-if="activeRegistration && activity.my_registration"
            class="tag tag-success"
          >
            已报名
          </span>
        </div>
        <p v-if="activity.summary" class="summary">{{ activity.summary }}</p>

        <div class="info-card">
          <div class="info-row">
            <span class="info-label">活动时间</span>
            <span class="info-value">{{ startText }} 至 {{ endText }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">活动地点</span>
            <span class="info-value">{{ activity.location_name }}</span>
          </div>
          <div v-if="activity.address" class="info-row">
            <span class="info-label">详细地址</span>
            <span class="info-value">{{ activity.address }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">报名时间</span>
            <span class="info-value">{{ signupText }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">剩余名额</span>
            <span class="info-value primary">
              {{ activity.remaining }} / {{ activity.capacity }}
            </span>
          </div>
        </div>

        <section v-if="activity.description" class="section">
          <h2>活动详情</h2>
          <p class="description">{{ activity.description }}</p>
        </section>

        <div v-if="activity.need_review" class="notice">
          本活动需要管理员审核，提交报名后请留意报名状态。
        </div>
      </div>

      <div class="action-bar">
        <div class="action-meta">
          <span class="action-remaining">余 {{ activity.remaining }} 个名额</span>
          <span v-if="reasonText && !activity.signup_state.can_signup" class="action-reason">
            {{ reasonText }}
          </span>
        </div>
        <button
          type="button"
          class="primary-btn action-btn"
          :disabled="actionDisabled"
          @click="handleAction"
        >
          {{ actionText }}
        </button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.detail-page {
  padding-bottom: 96px;
}

.back-link {
  margin-bottom: 14px;
  padding: 0;
  border: none;
  background: transparent;
  color: var(--muted);
  font-size: 13px;
}

.cover-wrap {
  margin: 0 -20px;
}

.cover {
  display: block;
  width: 100%;
  height: 210px;
  object-fit: cover;
}

.cover-placeholder {
  display: grid;
  place-items: center;
  background:
    linear-gradient(120deg, rgba(255, 255, 255, 0.1) 1px, transparent 1px),
    linear-gradient(140deg, #25305e, #4f6ef7 60%, #7c5cff);
  background-size: 38px 38px, 100% 100%;
  color: rgba(255, 255, 255, 0.72);
  font-size: 18px;
  letter-spacing: 8px;
}

.content {
  padding: 20px 0 0;
}

.title-row {
  display: flex;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: 8px;
}

.title-row h1 {
  flex: 1 1 100%;
  margin: 0;
  font-size: 24px;
  font-weight: 650;
  line-height: 1.4;
  letter-spacing: -0.4px;
}

.summary {
  margin: 8px 0 0;
  color: var(--muted);
  font-size: 13px;
  line-height: 1.65;
}

.info-card {
  margin-top: 18px;
  padding: 4px 18px;
  border-radius: 16px;
  background: #fff;
  box-shadow: var(--shadow);
}

.info-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  padding: 14px 0;
  border-bottom: 1px solid #f0f2f6;
}

.info-row:last-child {
  border-bottom: none;
}

.info-label {
  flex-shrink: 0;
  width: 68px;
  color: var(--soft);
  font-size: 12.5px;
}

.info-value {
  flex: 1;
  text-align: right;
  font-size: 13px;
  line-height: 1.55;
}

.info-value.primary {
  color: var(--primary);
  font-weight: 600;
}

.section {
  margin-top: 18px;
  padding: 18px;
  border-radius: 16px;
  background: #fff;
  box-shadow: var(--shadow);
}

.section h2 {
  margin: 0 0 10px;
  font-size: 15px;
  font-weight: 600;
}

.description {
  margin: 0;
  color: #4b5563;
  font-size: 13.5px;
  line-height: 1.8;
  white-space: pre-wrap;
}

.notice {
  margin-top: 16px;
  padding: 12px 14px;
  border-radius: 12px;
  background: var(--warning-soft);
  color: var(--warning);
  font-size: 12.5px;
  line-height: 1.6;
}

.action-bar {
  position: fixed;
  bottom: 0;
  left: 50%;
  z-index: 20;
  display: flex;
  align-items: center;
  gap: 14px;
  width: 100%;
  max-width: 560px;
  padding: 12px 20px calc(12px + env(safe-area-inset-bottom));
  transform: translateX(-50%);
  background: rgba(255, 255, 255, 0.96);
  border-top: 1px solid #eef1f6;
  box-shadow: 0 -8px 30px rgba(31, 41, 55, 0.06);
  backdrop-filter: blur(12px);
}

.action-meta {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 2px;
}

.action-remaining {
  font-size: 13px;
  font-weight: 600;
}

.action-reason {
  color: #9ca3af;
  font-size: 11px;
}

.action-btn {
  width: 220px;
  height: 44px;
  flex-shrink: 0;
  font-size: 14px;
}

@media (max-width: 620px) {
  .cover-wrap {
    margin: 0 -16px;
  }

  .action-bar {
    padding-left: 16px;
    padding-right: 16px;
  }
}
</style>
