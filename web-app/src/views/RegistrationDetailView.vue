<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import {
  cancelRegistration,
  fetchRegistration,
  fetchTicket,
} from '@/api/attendee'
import StatusTag from '@/components/StatusTag.vue'
import { toast } from '@/toast'
import type { RegistrationDetail, Ticket } from '@/types'
import { formatDateTime, valueText } from '@/utils/format'

const route = useRoute()
const router = useRouter()
const registrationId = Number(route.params.id)

const detail = ref<RegistrationDetail | null>(null)
const ticket = ref<Ticket | null>(null)
const qrUrl = ref('')
const answerRows = ref<{ key: string; label: string; value: string }[]>([])
const loading = ref(true)
const cancelling = ref(false)

const canCancel = computed(() => {
  const current = detail.value
  if (!current) return false
  if (!['pending', 'approved'].includes(current.status)) return false
  if (current.activity.allow_cancel === false) return false
  const deadline =
    current.activity.cancel_deadline || current.activity.signup_end_at
  return !deadline || Date.now() <= new Date(deadline).getTime()
})

function buildAnswerRows(current: RegistrationDetail) {
  const schema = current.form_schema || []
  const rows = schema.map((field) => ({
    key: field.key,
    label: field.label,
    value: valueText(current.answers[field.key]),
  }))
  const known = new Set(schema.map((field) => field.key))
  Object.entries(current.answers || {}).forEach(([key, value]) => {
    if (!known.has(key)) {
      rows.push({ key, label: key, value: valueText(value) })
    }
  })
  return rows
}

async function load() {
  loading.value = true
  try {
    const current = await fetchRegistration(registrationId)
    detail.value = current
    answerRows.value = buildAnswerRows(current)
    if (current.status === 'approved') {
      await loadTicket()
    } else {
      ticket.value = null
      qrUrl.value = ''
    }
  } catch {
    // 错误提示由请求拦截器处理
  } finally {
    loading.value = false
  }
}

async function loadTicket() {
  try {
    const data = await fetchTicket(registrationId)
    ticket.value = data
    qrUrl.value = `/api/mp/tickets/${data.token}.png`
  } catch {
    // 错误提示由请求拦截器处理
  }
}

async function cancel() {
  if (!canCancel.value || cancelling.value) return
  if (!window.confirm('取消后会释放名额，确定要取消报名吗？')) return

  cancelling.value = true
  try {
    await cancelRegistration(registrationId)
    toast('已取消报名', 'success')
    await load()
  } catch {
    // 错误提示由请求拦截器处理
  } finally {
    cancelling.value = false
  }
}

function openActivity() {
  if (detail.value) {
    router.push(`/activities/${detail.value.activity.id}`)
  }
}

onMounted(load)
</script>

<template>
  <div class="page registration-page">
    <div v-if="loading" class="loading">加载中…</div>
    <div v-else-if="!detail" class="empty">报名记录不存在</div>

    <template v-else>
      <div class="status-card">
        <div class="status-top">
          <div>
            <div class="status-name">{{ detail.applicant_name }}</div>
            <div class="status-phone">{{ detail.applicant_phone }}</div>
          </div>
          <StatusTag :status="detail.status" />
        </div>
        <div class="status-meta">
          报名编号 #{{ detail.id }} · {{ formatDateTime(detail.created_at) }}
        </div>

        <div v-if="detail.status === 'pending'" class="notice">
          报名已提交，管理员审核通过后即可查看电子票。
        </div>
        <div v-if="detail.status === 'rejected'" class="notice danger">
          报名未通过审核<template v-if="detail.review_note">：{{ detail.review_note }}</template>
        </div>
        <div v-if="detail.status === 'cancelled'" class="notice">
          该报名已取消，名额已释放。
        </div>
      </div>

      <div v-if="detail.status === 'approved' && ticket" class="ticket-card">
        <div class="ticket-title">电子票</div>
        <img class="qr" :src="qrUrl" alt="电子票二维码" />
        <div class="ticket-tip">入场时请出示此二维码</div>
        <div class="ticket-info">
          <div class="ticket-activity">{{ ticket.activity_title }}</div>
          <div class="ticket-meta">{{ ticket.location_name }}</div>
          <div class="ticket-meta">
            {{ formatDateTime(ticket.start_at) }} 至
            {{ formatDateTime(ticket.end_at) }}
          </div>
        </div>
      </div>

      <div class="section clickable" @click="openActivity">
        <div class="section-head">
          <h2>活动信息</h2>
          <span class="link">查看活动 →</span>
        </div>
        <div class="activity-title">{{ detail.activity.title }}</div>
        <div class="activity-meta">{{ detail.activity.location_name }}</div>
        <div class="activity-meta">
          {{ formatDateTime(detail.activity.start_at) }} 至
          {{ formatDateTime(detail.activity.end_at) }}
        </div>
      </div>

      <div class="section">
        <h2>报名信息</h2>
        <div class="answer-list">
          <div v-for="row in answerRows" :key="row.key" class="answer-row">
            <span class="answer-label">{{ row.label }}</span>
            <span class="answer-value">{{ row.value }}</span>
          </div>
        </div>
      </div>

      <div class="actions">
        <button
          v-if="canCancel"
          type="button"
          class="ghost-btn danger-btn"
          :disabled="cancelling"
          @click="cancel"
        >
          {{ cancelling ? '取消中…' : '取消报名' }}
        </button>
        <button type="button" class="ghost-btn" @click="openActivity">
          查看活动
        </button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.registration-page {
  padding-top: 4px;
}

.status-card {
  padding: 20px;
  border-radius: 20px;
  background: #fff;
  box-shadow: var(--shadow);
}

.status-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
}

.status-name {
  font-size: 21px;
  font-weight: 650;
}

.status-phone {
  margin-top: 6px;
  color: var(--muted);
  font-size: 13px;
}

.status-meta {
  margin-top: 13px;
  color: #9ca3af;
  font-size: 11.5px;
}

.notice {
  margin-top: 15px;
  padding: 11px 13px;
  border-radius: 10px;
  background: var(--warning-soft);
  color: var(--warning);
  font-size: 12px;
  line-height: 1.6;
}

.notice.danger {
  background: var(--danger-soft);
  color: var(--danger);
}

.ticket-card {
  margin-top: 16px;
  padding: 24px 20px;
  text-align: center;
  border-radius: 20px;
  background: #fff;
  box-shadow: var(--shadow);
}

.ticket-title {
  font-size: 17px;
  font-weight: 650;
}

.qr {
  display: block;
  width: 220px;
  height: 220px;
  margin: 16px auto 10px;
}

.ticket-tip {
  color: #9ca3af;
  font-size: 11.5px;
}

.ticket-info {
  margin-top: 18px;
  padding-top: 16px;
  border-top: 1px dashed var(--border);
}

.ticket-activity {
  font-size: 14px;
  font-weight: 600;
}

.ticket-meta {
  margin-top: 6px;
  color: var(--muted);
  font-size: 12px;
}

.section {
  margin-top: 16px;
  padding: 18px;
  border-radius: 17px;
  background: #fff;
  box-shadow: var(--shadow);
}

.section.clickable {
  cursor: pointer;
}

.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.section h2 {
  margin: 0;
  font-size: 14.5px;
  font-weight: 600;
}

.section-head h2 {
  margin: 0;
}

.link {
  color: var(--primary);
  font-size: 12px;
}

.activity-title {
  margin-top: 13px;
  font-size: 15px;
  font-weight: 600;
}

.activity-meta {
  margin-top: 6px;
  color: var(--muted);
  font-size: 12px;
}

.answer-list {
  margin-top: 8px;
}

.answer-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  padding: 13px 0;
  border-bottom: 1px solid #f0f2f6;
}

.answer-row:last-child {
  border-bottom: none;
}

.answer-label {
  flex-shrink: 0;
  width: 82px;
  color: var(--soft);
  font-size: 12px;
}

.answer-value {
  flex: 1;
  text-align: right;
  font-size: 13px;
  line-height: 1.55;
}

.actions {
  display: flex;
  gap: 10px;
  margin-top: 20px;
}

.actions .ghost-btn {
  height: 44px;
  font-size: 13px;
}

.danger-btn {
  border-color: #f3c7c7;
  color: var(--danger);
}
</style>
