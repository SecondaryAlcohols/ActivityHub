<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import {
  closeActivity,
  deleteActivity,
  fetchActivities,
  finishActivity,
  publishActivity,
} from '@/api/activity'
import type { ActivityListItem, ActivityStatus } from '@/types/activity'

type ActionKey = 'publish' | 'close' | 'finish' | 'delete'
type TagType = 'primary' | 'success' | 'info' | 'warning' | 'danger'

const router = useRouter()

const loading = ref(false)
const items = ref<ActivityListItem[]>([])
const total = ref(0)

const query = reactive({
  keyword: '',
  status: '' as ActivityStatus | '',
  page: 1,
  page_size: 10,
})

const statusMeta: Record<ActivityStatus, { label: string; tag: TagType }> = {
  draft: { label: '草稿', tag: 'info' },
  published: { label: '已发布', tag: 'success' },
  closed: { label: '已下架', tag: 'warning' },
  finished: { label: '已结束', tag: 'info' },
}

const statusOptions: { value: ActivityStatus; label: string }[] = [
  { value: 'draft', label: '草稿' },
  { value: 'published', label: '已发布' },
  { value: 'closed', label: '已下架' },
  { value: 'finished', label: '已结束' },
]

const actionLabels: Record<ActionKey, string> = {
  publish: '发布',
  close: '下架',
  finish: '结束',
  delete: '删除',
}

const actionMap: Record<ActionKey, (id: number) => Promise<unknown>> = {
  publish: publishActivity,
  close: closeActivity,
  finish: finishActivity,
  delete: deleteActivity,
}

function formatDateTime(value: string) {
  return value.slice(0, 16).replace('T', ' ')
}

function signupPercent(row: unknown) {
  const item = row as ActivityListItem
  if (!item.capacity) return 0
  return Math.min(100, Math.round((item.taken_count / item.capacity) * 100))
}

async function load() {
  loading.value = true
  try {
    const data = await fetchActivities({
      keyword: query.keyword.trim() || undefined,
      status: query.status || undefined,
      page: query.page,
      page_size: query.page_size,
    })
    items.value = data.items
    total.value = data.total
  } catch {
    // 错误提示由请求拦截器统一处理
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  query.page = 1
  load()
}

function handleReset() {
  query.keyword = ''
  query.status = ''
  query.page = 1
  load()
}

function handlePageChange() {
  load()
}

function handleSizeChange() {
  query.page = 1
  load()
}

async function runAction(action: ActionKey, row: unknown) {
  const item = row as ActivityListItem
  const tips =
    action === 'delete'
      ? `删除后不可恢复，确定删除草稿活动「${item.title}」吗？`
      : `确定要${actionLabels[action]}活动「${item.title}」吗？`

  try {
    await ElMessageBox.confirm(tips, '操作确认', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: action === 'delete' ? 'warning' : 'info',
    })
  } catch {
    return
  }

  try {
    await actionMap[action](item.id)
    ElMessage.success(`已${actionLabels[action]}`)
    await load()
  } catch {
    // 请求错误已统一提示
  }
}

onMounted(load)
</script>

<template>
  <div class="activity-page">
    <div class="page-head">
      <div>
        <h2>活动管理</h2>
        <p class="muted">创建并发布活动，管理报名与现场签到。</p>
      </div>
      <el-button type="primary" :icon="Plus" @click="router.push('/activities/new')">
        新建活动
      </el-button>
    </div>

    <el-card shadow="never" class="panel filter-panel">
      <el-form :inline="true" class="filter-form" @submit.prevent="handleSearch">
        <el-form-item label="关键词">
          <el-input
            v-model="query.keyword"
            placeholder="活动标题或地点"
            clearable
            style="width: 220px"
            @keyup.enter="handleSearch"
          />
        </el-form-item>
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
        <el-form-item class="filter-actions">
          <el-button type="primary" @click="handleSearch">查询</el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never" class="panel">
      <el-table v-loading="loading" :data="items" row-key="id" class="activity-table">
        <el-table-column label="活动" min-width="240">
          <template #default="{ row }">
            <div class="activity-cell">
              <div class="activity-title">{{ row.title }}</div>
              <div class="activity-meta">{{ row.location_name }}</div>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="活动时间" min-width="190">
          <template #default="{ row }">
            <div class="time-cell">
              <span>{{ formatDateTime(row.start_at) }}</span>
              <span class="muted">至 {{ formatDateTime(row.end_at) }}</span>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="报名情况" width="150">
          <template #default="{ row }">
            <div class="capacity-cell">
              <span><strong>{{ row.taken_count }}</strong> / {{ row.capacity }}</span>
              <el-progress
                :percentage="signupPercent(row)"
                :show-text="false"
                :stroke-width="5"
              />
            </div>
          </template>
        </el-table-column>

        <el-table-column label="审核" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.need_review" type="warning" effect="plain" size="small">
              需审核
            </el-tag>
            <span v-else class="muted">无需审核</span>
          </template>
        </el-table-column>

        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusMeta[row.status as ActivityStatus].tag" size="small">
              {{ statusMeta[row.status as ActivityStatus].label }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <div class="row-actions">
              <el-button
                v-if="row.status === 'draft' || row.status === 'published'"
                link
                type="primary"
                @click="router.push(`/activities/${row.id}/edit`)"
              >
                编辑
              </el-button>
              <el-button
                v-if="row.status !== 'draft'"
                link
                type="primary"
                @click="router.push(`/activities/${row.id}/registrations`)"
              >
                报名
              </el-button>
              <el-button
                v-if="row.status === 'draft'"
                link
                type="primary"
                @click="runAction('publish', row)"
              >
                发布
              </el-button>
              <el-button
                v-if="row.status === 'published'"
                link
                type="warning"
                @click="runAction('close', row)"
              >
                下架
              </el-button>
              <el-button
                v-if="row.status === 'published'"
                link
                type="info"
                @click="runAction('finish', row)"
              >
                结束
              </el-button>
              <el-button
                v-if="row.status === 'draft'"
                link
                type="danger"
                @click="runAction('delete', row)"
              >
                删除
              </el-button>
            </div>
          </template>
        </el-table-column>

        <template #empty>
          <el-empty description="还没有活动" :image-size="90">
            <el-button type="primary" @click="router.push('/activities/new')">
              创建第一场活动
            </el-button>
          </el-empty>
        </template>
      </el-table>

      <div class="table-footer">
        <span class="muted">共 {{ total }} 场活动</span>
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
  </div>
</template>

<style scoped>
.activity-page {
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

.page-head h2 {
  margin: 0 0 6px;
  font-size: 22px;
  font-weight: 600;
  letter-spacing: -0.3px;
}

.page-head p {
  margin: 0;
  font-size: 13px;
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

.activity-table :deep(.el-table__header th) {
  background: #f9fafc;
  color: #64748b;
  font-weight: 500;
}

.activity-table :deep(.el-table__row) {
  height: 64px;
}

.activity-cell {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.activity-title {
  font-weight: 600;
  color: #1f2937;
}

.activity-meta {
  font-size: 12px;
  color: var(--app-muted);
}

.time-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 13px;
}

.time-cell .muted {
  font-size: 12px;
}

.capacity-cell {
  display: flex;
  flex-direction: column;
  gap: 7px;
  font-size: 13px;
}

.capacity-cell :deep(.el-progress-bar__outer) {
  background: #eef1f6;
}

.row-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 2px;
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

@media (max-width: 760px) {
  .page-head {
    flex-direction: column;
  }

  .filter-actions {
    margin-left: 0;
  }

  .table-footer {
    justify-content: flex-end;
  }
}
</style>
