<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { fetchRegistration } from '@/api/attendee'
import type { RegistrationDetail } from '@/types'
import { STATUS_META } from '@/utils/format'

const route = useRoute()
const router = useRouter()
const registrationId = Number(route.params.id)

const detail = ref<RegistrationDetail | null>(null)
const loading = ref(true)

const meta = computed(() =>
  detail.value ? STATUS_META[detail.value.status] : null,
)
const isPending = computed(() => detail.value?.status === 'pending')
const title = computed(() => {
  if (!detail.value) return '报名结果'
  if (detail.value.status === 'approved') return '报名成功'
  if (detail.value.status === 'pending') return '报名已提交'
  if (detail.value.status === 'rejected') return '报名未通过'
  return '报名已取消'
})
const description = computed(() => {
  if (!detail.value) return ''
  if (detail.value.status === 'approved') {
    return '已为你保留名额，请按时参加活动。'
  }
  if (detail.value.status === 'pending') {
    return '管理员审核通过后，即可在报名详情中查看电子票。'
  }
  if (detail.value.status === 'rejected') {
    return detail.value.review_note || '很遗憾，本次报名未通过审核。'
  }
  return '该报名已取消。'
})

async function load() {
  loading.value = true
  try {
    detail.value = await fetchRegistration(registrationId)
  } catch {
    // 错误提示由请求拦截器处理
  } finally {
    loading.value = false
  }
}

function viewDetail() {
  router.replace(`/registrations/${registrationId}`)
}

function viewMy() {
  router.replace('/my')
}

onMounted(load)
</script>

<template>
  <div class="page result-page">
    <div v-if="loading" class="loading">加载中…</div>

    <div v-else-if="detail" class="result-card">
      <div
        class="result-icon"
        :class="isPending ? 'pending' : detail.status === 'approved' ? 'success' : 'danger'"
      >
        {{ isPending ? '待' : detail.status === 'approved' ? '✓' : '!' }}
      </div>
      <h1>{{ title }}</h1>
      <p class="result-desc">{{ description }}</p>
      <div class="result-meta">
        报名编号 #{{ detail.id }}
        <span class="dot"></span>
        {{ meta?.label }}
      </div>

      <div class="result-activity">
        <div class="result-activity-title">{{ detail.activity.title }}</div>
        <div class="result-activity-meta">
          {{ detail.activity.location_name }}
        </div>
      </div>

      <button type="button" class="primary-btn" @click="viewDetail">
        查看报名详情
      </button>
      <button type="button" class="ghost-btn" @click="viewMy">
        我的报名
      </button>
    </div>

    <div v-else class="empty">报名记录不存在</div>
  </div>
</template>

<style scoped>
.result-page {
  padding-top: 20px;
}

.result-card {
  padding: 36px 24px 28px;
  text-align: center;
  border-radius: 22px;
  background: #fff;
  box-shadow: var(--shadow);
}

.result-icon {
  display: grid;
  place-items: center;
  width: 68px;
  height: 68px;
  margin: 0 auto 20px;
  border-radius: 50%;
  font-size: 30px;
  font-weight: 650;
}

.result-icon.success {
  background: var(--success-soft);
  color: var(--success);
}

.result-icon.pending {
  background: var(--warning-soft);
  color: var(--warning);
}

.result-icon.danger {
  background: var(--danger-soft);
  color: var(--danger);
}

.result-card h1 {
  margin: 0;
  font-size: 23px;
  font-weight: 650;
}

.result-desc {
  margin: 12px auto 0;
  max-width: 300px;
  color: var(--muted);
  font-size: 13px;
  line-height: 1.7;
}

.result-meta {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  margin-top: 14px;
  color: #9ca3af;
  font-size: 12px;
}

.dot {
  width: 3px;
  height: 3px;
  border-radius: 50%;
  background: #c4c9d4;
}

.result-activity {
  margin: 22px 0;
  padding: 14px;
  border-radius: 12px;
  background: #f8f9fc;
}

.result-activity-title {
  font-size: 14px;
  font-weight: 600;
}

.result-activity-meta {
  margin-top: 5px;
  color: var(--muted);
  font-size: 12px;
}

.result-card .ghost-btn {
  margin-top: 10px;
}
</style>
