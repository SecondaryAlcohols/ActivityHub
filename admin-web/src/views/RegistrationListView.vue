<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Refresh } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { fetchActivity } from '@/api/activity'
import {
  batchReviewRegistrations,
  cancelRegistration,
  fetchRegistrations,
  fetchRegistrationStats,
  reviewRegistration,
} from '@/api/registration'
import RegistrationDetailDrawer from '@/components/RegistrationDetailDrawer.vue'
import type { Activity } from '@/types/activity'
import type {
  AdminRegistrationItem,
  RegistrationStats,
  RegistrationStatus,
} from '@/types/registration'

type TagType = 'primary' | 'success' | 'info' | 'warning' | 'danger'

const route = useRoute()
const router = useRouter()
const activityId = computed(() => Number(route.params.id))

const activity = ref<Activity | null>(null)
const stats = ref<RegistrationStats | null>(null)
const items = ref<AdminRegistrationItem[]>([])
const total = ref(0)
const loading = ref(false)
const selectedIds = ref<number[]>([])
const tableRef = ref<{ clearSelection: () => void }>()
const drawerVisible = ref(false)
const activeRegistrationId = ref<number | null>(null)

const query = reactive({
  status: '' as RegistrationStatus | '',
  keyword: '',
  page: 1,
  page_size: 20,
})

const statusMeta: Record<
  RegistrationStatus,
  { label: string; tag: TagType }
> = {
  pending: { label: '待审核', tag: 'warning' },
  approved: { label: '已通过', tag: 'success' },
  rejected: { label: '已拒绝', tag: 'danger' },
  cancelled: { label: '已取消', tag: 'info' },
}

const statusOptions: { value: RegistrationStatus; label: string }[] = [
  { value: 'pending', label: '待审核' },
  { value: 'approved', label: '已通过' },
  { value: 'rejected', label: '已拒绝' },
  { value: 'cancelled', label: '已取消' },
]

const pendingSelectedCount = computed(
  () =>
    items.value.filter(
      (item) =>
        selectedIds.value.includes(item.id) && item.status === 'pending',
    ).length,
)

const isDraft = computed(() => activity.value?.status === 'draft')

function formatDateTime(value: string | null | undefined) {
  if (!value) return '—'
  return value.slice(0, 16).replace('T', ' ')
}

async function loadActivity() {
  try {
    activity.value = await fetchActivity(activityId.value)
  } catch {
    await router.replace('/activities')
  }
}

async function loadList() {
  if (isDraft.value) {
    items.value = []
    total.value = 0
    return
  }
  const page = await fetchRegistrations(activityId.value, { ...query })
  items.value = page.items
  total.value = page.total
}

async function loadStats() {
  stats.value = await fetchRegistrationStats(activityId.value)
}

async function loadAll() {
  loading.value = true
  try {
    await loadStats()
    await loadList()
  } catch {
    // 错误提示由请求拦截器统一处理
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  query.page = 1
  loadAll()
}

function handleReset() {
  query.status = ''
  query.keyword = ''
  query.page = 1
  loadAll()
}

function handlePageChange() {
  loadList()
}

function handleSizeChange() {
  query.page = 1
  loadList()
}

function handleSelectionChange(rows: unknown[]) {
  selectedIds.value = (rows as AdminRegistrationItem[]).map((row) => row.id)
}

function clearSelection() {
  selectedIds.value = []
  tableRef.value?.clearSelection()
}

function openDetail(row: unknown) {
  const item = row as AdminRegistrationItem
  activeRegistrationId.value = item.id
  drawerVisible.value = true
}

async function runReview(row: unknown, action: 'approve' | 'reject') {
  const item = row as AdminRegistrationItem
  if (action === 'approve') {
    try {
      await ElMessageBox.confirm(
        `确定通过「${item.applicant_name}」的报名吗？`,
        '审核确认',
        {
          confirmButtonText: '通过',
          cancelButtonText: '取消',
          type: 'success',
        },
      )
    } catch {
      return
    }
    try {
      await reviewRegistration(item.id, 'approve')
      ElMessage.success('已通过报名')
      await loadAll()
    } catch {
      // 错误提示由请求拦截器统一处理
    }
    return
  }

  let reason: string
  try {
    const result = await ElMessageBox.prompt(
      `请输入拒绝「${item.applicant_name}」报名的原因`,
      '拒绝报名',
      {
        inputType: 'textarea',
        inputPlaceholder: '请说明拒绝原因',
        inputValidator: (value) =>
          value && value.trim() && value.length <= 500
            ? true
            : '请填写拒绝原因（不超过 500 字）',
        confirmButtonText: '拒绝',
        cancelButtonText: '取消',
      },
    )
    reason = result.value.trim()
  } catch {
    return
  }

  try {
    await reviewRegistration(item.id, 'reject', reason)
    ElMessage.success('已拒绝报名')
    await loadAll()
  } catch {
    // 错误提示由请求拦截器统一处理
  }
}

async function runBatchReview(action: 'approve' | 'reject') {
  const ids = items.value
    .filter(
      (item) =>
        item.status === 'pending' && selectedIds.value.includes(item.id),
    )
    .map((item) => item.id)
  if (ids.length === 0) {
    ElMessage.warning('请选择待审核的报名')
    return
  }

  let note = ''
  if (action === 'approve') {
    try {
      await ElMessageBox.confirm(
        `确定批量通过选中的 ${ids.length} 条报名吗？`,
        '批量审核',
        {
          confirmButtonText: '通过',
          cancelButtonText: '取消',
          type: 'success',
        },
      )
    } catch {
      return
    }
  } else {
    try {
      const result = await ElMessageBox.prompt(
        `请输入拒绝选中的 ${ids.length} 条报名的原因`,
        '批量拒绝',
        {
          inputType: 'textarea',
          inputPlaceholder: '请说明拒绝原因',
          inputValidator: (value) =>
            value && value.trim() && value.length <= 500
              ? true
              : '请填写拒绝原因（不超过 500 字）',
          confirmButtonText: '拒绝',
          cancelButtonText: '取消',
        },
      )
      note = result.value.trim()
    } catch {
      return
    }
  }

  try {
    const result = await batchReviewRegistrations(ids, action, note)
    ElMessage.success(
      `批量审核完成：通过 ${result.approved} 条，拒绝 ${result.rejected} 条，跳过 ${result.skipped} 条`,
    )
    clearSelection()
    await loadAll()
  } catch {
    // 错误提示由请求拦截器统一处理
  }
}

async function runCancel(row: unknown) {
  const item = row as AdminRegistrationItem
  try {
    await ElMessageBox.confirm(
      `确定取消「${item.applicant_name}」的报名吗？取消后会释放名额。`,
      '取消报名',
      {
        confirmButtonText: '取消报名',
        cancelButtonText: '返回',
        type: 'warning',
      },
    )
  } catch {
    return
  }

  try {
    await cancelRegistration(item.id)
    ElMessage.success('已取消报名')
    await loadAll()
  } catch {
    // 错误提示由请求拦截器统一处理
  }
}

onMounted(async () => {
  await loadActivity()
  if (activity.value) {
    await loadAll()
  }
})
</script>

<template>
  <div class="registration-page">
    <div class="page-head">
      <div class="head-left">
        <el-button text :icon="ArrowLeft" @click="router.push('/activities')">
          返回
        </el-button>
        <div>
          <h2>报名管理</h2>
          <p v-if="activity" class="muted">
            {{ activity.title }} ·
            {{ formatDateTime(activity.start_at) }} ·
            {{ activity.location_name }}
          </p>
          <p v-else class="muted">正在加载活动信息…</p>
        </div>
      </div>
      <el-button :icon="Refresh" :loading="loading" @click="loadAll">
        刷新
      </el-button>
    </div>

    <el-alert
      v-if="isDraft"
      type="info"
      title="草稿活动还没有报名记录，发布后即可查看和管理报名。"
      :closable="false"
      show-icon
      class="draft-alert"
    />

    <div v-if="stats" class="stats-grid">
      <el-card shadow="never" class="stat-card">
        <div class="stat-label">报名总数</div>
        <div class="stat-value">{{ stats.total }}</div>
        <div class="stat-hint">含全部状态</div>
      </el-card>
      <el-card shadow="never" class="stat-card stat-card--pending">
        <div class="stat-label">待审核</div>
        <div class="stat-value">{{ stats.pending }}</div>
        <div class="stat-hint">需要管理员处理</div>
      </el-card>
      <el-card shadow="never" class="stat-card">
        <div class="stat-label">已通过</div>
        <div class="stat-value">{{ stats.approved }}</div>
        <div class="stat-hint">有效报名</div>
      </el-card>
      <el-card shadow="never" class="stat-card">
        <div class="stat-label">剩余名额</div>
        <div class="stat-value">{{ stats.remaining }}</div>
        <div class="stat-hint">共 {{ stats.capacity }} 个名额</div>
      </el-card>
    </div>

    <el-card shadow="never" class="panel filter-panel">
      <el-form :inline="true" class="filter-form" @submit.prevent="handleSearch">
        <el-form-item label="状态">
          <el-select
            v-model="query.status"
            placeholder="全部状态"
            clearable
            style="width: 140px"
          >
            <el-option
              v-for="option in statusOptions"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="关键词">
          <el-input
            v-model="query.keyword"
            placeholder="姓名或手机号"
            clearable
            style="width: 220px"
            @keyup.enter="handleSearch"
          />
        </el-form-item>
        <el-form-item class="filter-actions">
          <el-button type="primary" @click="handleSearch">查询</el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never" class="panel">
      <div v-if="selectedIds.length" class="batch-bar">
        <span>
          已选 {{ selectedIds.length }} 项
          <span v-if="pendingSelectedCount" class="muted">
            （待审核 {{ pendingSelectedCount }} 项）
          </span>
        </span>
        <div class="batch-actions">
          <el-button
            type="success"
            plain
            size="small"
            :disabled="pendingSelectedCount === 0"
            @click="runBatchReview('approve')"
          >
            批量通过
          </el-button>
          <el-button
            type="danger"
            plain
            size="small"
            :disabled="pendingSelectedCount === 0"
            @click="runBatchReview('reject')"
          >
            批量拒绝
          </el-button>
          <el-button link @click="clearSelection">清空选择</el-button>
        </div>
      </div>

      <el-table
        ref="tableRef"
        v-loading="loading"
        :data="items"
        row-key="id"
        class="registration-table"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="46" />

        <el-table-column label="报名人" min-width="180">
          <template #default="{ row }">
            <div class="applicant-cell">
              <span class="applicant-name">{{ row.applicant_name }}</span>
              <span class="muted">{{ row.applicant_phone }}</span>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="微信昵称" width="130">
          <template #default="{ row }">
            {{ row.attendee_nickname || '—' }}
          </template>
        </el-table-column>

        <el-table-column label="报名时间" width="160">
          <template #default="{ row }">
            {{ formatDateTime(row.created_at) }}
          </template>
        </el-table-column>

        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag
              :type="statusMeta[row.status as RegistrationStatus].tag"
              size="small"
            >
              {{ statusMeta[row.status as RegistrationStatus].label }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="审核信息" min-width="170">
          <template #default="{ row }">
            <div v-if="row.review_note" class="review-note">
              {{ row.review_note }}
            </div>
            <span v-else-if="row.reviewed_at" class="muted">
              {{ formatDateTime(row.reviewed_at) }}
            </span>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="230" fixed="right">
          <template #default="{ row }">
            <div class="row-actions">
              <el-button link type="primary" @click="openDetail(row)">
                详情
              </el-button>
              <template v-if="row.status === 'pending'">
                <el-button link type="success" @click="runReview(row, 'approve')">
                  通过
                </el-button>
                <el-button link type="danger" @click="runReview(row, 'reject')">
                  拒绝
                </el-button>
              </template>
              <el-button
                v-if="row.status === 'pending' || row.status === 'approved'"
                link
                type="warning"
                @click="runCancel(row)"
              >
                取消报名
              </el-button>
            </div>
          </template>
        </el-table-column>

        <template #empty>
          <el-empty description="还没有报名记录" :image-size="90" />
        </template>
      </el-table>

      <div class="table-footer">
        <span class="muted">共 {{ total }} 条报名</span>
        <el-pagination
          v-model:current-page="query.page"
          v-model:page-size="query.page_size"
          :total="total"
          :page-sizes="[10, 20, 50]"
          layout="sizes, prev, pager, next"
          @current-change="handlePageChange"
          @size-change="handleSizeChange"
        />
      </div>
    </el-card>

    <RegistrationDetailDrawer
      v-model="drawerVisible"
      :registration-id="activeRegistrationId"
    />
  </div>
</template>

<style scoped>
.registration-page {
  max-width: 1280px;
  margin: 0 auto;
}

.page-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 20px;
}

.head-left {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.head-left h2 {
  margin: 0 0 6px;
  font-size: 22px;
  font-weight: 600;
  letter-spacing: -0.3px;
}

.head-left p {
  margin: 0;
  font-size: 13px;
}

.draft-alert {
  margin-bottom: 16px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 16px;
}

.stat-card {
  border: 1px solid var(--app-border);
  border-radius: 12px;
}

.stat-label {
  font-size: 13px;
  color: var(--app-muted);
}

.stat-value {
  margin: 8px 0 4px;
  font-size: 26px;
  font-weight: 600;
  line-height: 1;
}

.stat-hint {
  font-size: 12px;
  color: #9ca3af;
}

.stat-card--pending .stat-value {
  color: #d97706;
}

.panel {
  border: 1px solid var(--app-border);
  border-radius: 12px;
}

.filter-panel {
  margin-bottom: 16px;
}

.filter-panel :deep(.el-card__body) {
  padding: 18px 20px 2px;
}

.filter-form :deep(.el-form-item) {
  margin-bottom: 16px;
}

.filter-actions {
  margin-left: auto;
}

.batch-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 14px;
  margin-bottom: 12px;
  border: 1px solid #dbe4ff;
  border-radius: 8px;
  background: #f4f7ff;
  font-size: 13px;
}

.batch-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.registration-table :deep(.el-table__header th) {
  background: #f9fafc;
  color: #64748b;
  font-weight: 500;
}

.applicant-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.applicant-name {
  font-weight: 600;
  color: #1f2937;
}

.review-note {
  color: #b45309;
  font-size: 13px;
}

.row-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
}

.row-actions :deep(.el-button + .el-button) {
  margin-left: 6px;
}

.table-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding-top: 18px;
  flex-wrap: wrap;
}

.table-footer .muted {
  font-size: 13px;
}

@media (max-width: 980px) {
  .stats-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 760px) {
  .page-head {
    flex-direction: column;
  }

  .stats-grid {
    grid-template-columns: 1fr;
  }

  .filter-actions {
    margin-left: 0;
  }

  .batch-bar {
    align-items: flex-start;
    flex-direction: column;
  }

  .table-footer {
    justify-content: flex-end;
  }
}
</style>
