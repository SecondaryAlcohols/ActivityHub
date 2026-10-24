<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

import { fetchRegistrationDetail } from '@/api/registration'
import type {
  AdminRegistrationDetail,
  RegistrationStatus,
} from '@/types/registration'

const props = defineProps<{
  modelValue: boolean
  registrationId: number | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const loading = ref(false)
const detail = ref<AdminRegistrationDetail | null>(null)

const statusMeta: Record<
  RegistrationStatus,
  { label: string; tag: 'warning' | 'success' | 'danger' | 'info' }
> = {
  pending: { label: '待审核', tag: 'warning' },
  approved: { label: '已通过', tag: 'success' },
  rejected: { label: '已拒绝', tag: 'danger' },
  cancelled: { label: '已取消', tag: 'info' },
}

const answerRows = computed(() => {
  if (!detail.value) return []
  const rows = detail.value.form_schema.map((field) => ({
    key: field.key,
    label: field.label,
    value: formatValue(detail.value?.answers?.[field.key]),
  }))
  const known = new Set(detail.value.form_schema.map((field) => field.key))
  for (const [key, value] of Object.entries(detail.value.answers || {})) {
    if (!known.has(key)) {
      rows.push({ key, label: key, value: formatValue(value) })
    }
  }
  return rows
})

function formatValue(value: unknown) {
  if (value === null || value === undefined || value === '') return '—'
  if (Array.isArray(value)) return value.join('、')
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

function formatDateTime(value: string | null | undefined) {
  if (!value) return '—'
  return value.slice(0, 16).replace('T', ' ')
}

async function load(id: number) {
  loading.value = true
  detail.value = null
  try {
    detail.value = await fetchRegistrationDetail(id)
  } catch {
    ElMessage.error('报名详情加载失败')
    emit('update:modelValue', false)
  } finally {
    loading.value = false
  }
}

watch(
  [() => props.modelValue, () => props.registrationId],
  ([open, id]) => {
    if (open && id) {
      load(id)
    }
  },
)
</script>

<template>
  <el-drawer
    :model-value="modelValue"
    title="报名详情"
    size="520px"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <div v-loading="loading" class="drawer-body">
      <template v-if="detail">
        <div class="applicant-head">
          <el-avatar :size="44" :src="detail.attendee?.avatar_url || undefined">
            {{ (detail.applicant_name || '?').slice(0, 1) }}
          </el-avatar>
          <div>
            <div class="applicant-name">{{ detail.applicant_name }}</div>
            <div class="muted">{{ detail.applicant_phone }}</div>
          </div>
          <el-tag :type="statusMeta[detail.status].tag" class="status-tag">
            {{ statusMeta[detail.status].label }}
          </el-tag>
        </div>

        <el-descriptions title="报名信息" :column="1" border class="section">
          <el-descriptions-item label="报名编号">
            #{{ detail.id }}
          </el-descriptions-item>
          <el-descriptions-item label="报名时间">
            {{ formatDateTime(detail.created_at) }}
          </el-descriptions-item>
          <el-descriptions-item label="审核时间">
            {{ formatDateTime(detail.reviewed_at) }}
          </el-descriptions-item>
          <el-descriptions-item v-if="detail.review_note" label="审核备注">
            {{ detail.review_note }}
          </el-descriptions-item>
          <el-descriptions-item v-if="detail.cancelled_at" label="取消时间">
            {{ formatDateTime(detail.cancelled_at) }}
          </el-descriptions-item>
          <el-descriptions-item label="微信昵称">
            {{ detail.attendee?.nickname || '未设置' }}
          </el-descriptions-item>
        </el-descriptions>

        <div class="section">
          <div class="section-title">活动</div>
          <div v-if="detail.activity" class="activity-box">
            <div class="activity-title">{{ detail.activity.title }}</div>
            <div class="muted">
              {{ formatDateTime(detail.activity.start_at) }} ·
              {{ detail.activity.location_name }}
            </div>
          </div>
          <span v-else class="muted">活动不存在</span>
        </div>

        <div class="section">
          <div class="section-title">报名表单内容</div>
          <el-descriptions :column="1" border>
            <el-descriptions-item
              v-for="row in answerRows"
              :key="row.key"
              :label="row.label"
            >
              {{ row.value }}
            </el-descriptions-item>
          </el-descriptions>
        </div>
      </template>
      <el-empty v-else-if="!loading" description="暂无报名详情" />
    </div>
  </el-drawer>
</template>

<style scoped>
.drawer-body {
  min-height: 200px;
}

.applicant-head {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 4px 0 20px;
}

.applicant-name {
  font-size: 17px;
  font-weight: 600;
}

.status-tag {
  margin-left: auto;
}

.section {
  margin-bottom: 22px;
}

.section-title {
  margin-bottom: 10px;
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.activity-box {
  padding: 12px 14px;
  border: 1px solid var(--app-border);
  border-radius: 8px;
  background: #fafbfc;
}

.activity-title {
  margin-bottom: 5px;
  font-weight: 600;
}

.activity-box .muted {
  font-size: 12px;
}
</style>
