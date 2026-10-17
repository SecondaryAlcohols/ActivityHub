<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ElMessage,
  type FormInstance,
  type FormRules,
} from 'element-plus'

import {
  createActivity,
  fetchActivity,
  updateActivity,
} from '@/api/activity'
import type {
  Activity,
  ActivityPayload,
  ActivityStatus,
  FieldType,
  FormField,
} from '@/types/activity'

interface ActivityForm {
  title: string
  cover_url: string
  summary: string
  description: string
  location_name: string
  address: string
  start_at: string
  end_at: string
  signup_start_at: string
  signup_end_at: string
  checkin_open_at: string | null
  checkin_close_at: string | null
  capacity: number
  need_review: boolean
  allow_cancel: boolean
  cancel_deadline: string | null
}

type FieldRow = FormField & { optionsText: string }

const route = useRoute()
const router = useRouter()

const isEdit = computed(() => route.name === 'activity-edit')
const formRef = ref<FormInstance>()
const pageLoading = ref(false)
const submitting = ref(false)
const activityStatus = ref<ActivityStatus | null>(null)
const readonly = computed(
  () => activityStatus.value === 'closed' || activityStatus.value === 'finished',
)

const fieldTypes: { value: FieldType; label: string }[] = [
  { value: 'text', label: '单行文本' },
  { value: 'textarea', label: '多行文本' },
  { value: 'phone', label: '手机号' },
  { value: 'email', label: '邮箱' },
  { value: 'number', label: '数字' },
  { value: 'select', label: '单选' },
  { value: 'multi_select', label: '多选' },
  { value: 'date', label: '日期' },
]

const rules: FormRules = {
  title: [{ required: true, message: '请输入活动标题', trigger: 'blur' }],
  location_name: [{ required: true, message: '请输入活动地点', trigger: 'blur' }],
  start_at: [{ required: true, message: '请选择活动开始时间', trigger: 'change' }],
  end_at: [{ required: true, message: '请选择活动结束时间', trigger: 'change' }],
  signup_start_at: [
    { required: true, message: '请选择报名开始时间', trigger: 'change' },
  ],
  signup_end_at: [
    { required: true, message: '请选择报名截止时间', trigger: 'change' },
  ],
  capacity: [{ required: true, message: '请设置报名名额', trigger: 'change' }],
}

const form = reactive<ActivityForm>(createForm())
const fields = ref<FieldRow[]>(defaultFields())
let fieldCounter = 1

function pad(value: number) {
  return String(value).padStart(2, '0')
}

function toLocalInput(date: Date) {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}:00`
}

function createForm(): ActivityForm {
  const start = new Date()
  start.setDate(start.getDate() + 7)
  start.setHours(14, 0, 0, 0)
  const end = new Date(start)
  end.setHours(16, 0, 0, 0)

  const signupStart = new Date()
  signupStart.setSeconds(0, 0)
  const signupEnd = new Date(start)
  signupEnd.setDate(signupEnd.getDate() - 1)
  signupEnd.setHours(23, 59, 0, 0)

  const checkinOpen = new Date(start)
  checkinOpen.setHours(checkinOpen.getHours() - 1)
  const checkinClose = new Date(end)
  checkinClose.setHours(checkinClose.getHours() + 1)

  return {
    title: '',
    cover_url: '',
    summary: '',
    description: '',
    location_name: '',
    address: '',
    start_at: toLocalInput(start),
    end_at: toLocalInput(end),
    signup_start_at: toLocalInput(signupStart),
    signup_end_at: toLocalInput(signupEnd),
    checkin_open_at: toLocalInput(checkinOpen),
    checkin_close_at: toLocalInput(checkinClose),
    capacity: 100,
    need_review: false,
    allow_cancel: true,
    cancel_deadline: null,
  }
}

function defaultFields(): FieldRow[] {
  return [
    {
      key: 'name',
      label: '姓名',
      type: 'text',
      required: true,
      system: true,
      optionsText: '',
    },
    {
      key: 'phone',
      label: '手机号',
      type: 'phone',
      required: true,
      system: true,
      optionsText: '',
    },
  ]
}

function needsOptions(type: FieldType) {
  return type === 'select' || type === 'multi_select'
}

function parseOptions(text: string) {
  return text
    .split(/[,，]/)
    .map((item) => item.trim())
    .filter(Boolean)
}

function addField() {
  if (fields.value.length >= 30) {
    ElMessage.warning('最多添加 30 个报名字段')
    return
  }
  let key = `field_${fieldCounter++}`
  while (fields.value.some((row) => row.key === key)) {
    key = `field_${fieldCounter++}`
  }
  fields.value.push({
    key,
    label: '',
    type: 'text',
    required: false,
    optionsText: '',
  })
}

function removeField(index: number) {
  const row = fields.value[index]
  if (!row || row.system) return
  fields.value.splice(index, 1)
}

function validateFields(): string | null {
  const keys = new Set<string>()
  for (const row of fields.value) {
    const key = row.key.trim()
    if (!/^[a-zA-Z][a-zA-Z0-9_]*$/.test(key)) {
      return `字段标识「${row.key}」不合法，需以字母开头，只能包含字母、数字和下划线`
    }
    if (keys.has(key)) {
      return `字段标识「${key}」重复`
    }
    keys.add(key)
    if (!row.label.trim()) {
      return '报名字段的显示名称不能为空'
    }
    if (needsOptions(row.type) && parseOptions(row.optionsText).length === 0) {
      return `字段「${row.label}」需要至少一个选项`
    }
  }
  if (!keys.has('name') || !keys.has('phone')) {
    return '报名表单必须包含姓名和手机号字段'
  }
  return null
}

function nullable(value: string | null) {
  if (!value) return null
  const trimmed = value.trim()
  return trimmed || null
}

function buildPayload(): ActivityPayload {
  return {
    title: form.title.trim(),
    cover_url: nullable(form.cover_url),
    summary: nullable(form.summary),
    description: nullable(form.description),
    location_name: form.location_name.trim(),
    address: nullable(form.address),
    start_at: form.start_at,
    end_at: form.end_at,
    signup_start_at: form.signup_start_at,
    signup_end_at: form.signup_end_at,
    checkin_open_at: form.checkin_open_at,
    checkin_close_at: form.checkin_close_at,
    capacity: form.capacity,
    need_review: form.need_review,
    allow_cancel: form.allow_cancel,
    cancel_deadline: form.allow_cancel ? form.cancel_deadline : null,
    form_schema: fields.value.map((row) => ({
      key: row.key.trim(),
      label: row.label.trim(),
      type: row.type,
      required: row.required,
      placeholder: row.placeholder?.trim() || null,
      options: needsOptions(row.type) ? parseOptions(row.optionsText) : null,
      system: Boolean(row.system),
    })),
  }
}

function fillForm(data: Activity) {
  form.title = data.title
  form.cover_url = data.cover_url ?? ''
  form.summary = data.summary ?? ''
  form.description = data.description ?? ''
  form.location_name = data.location_name
  form.address = data.address ?? ''
  form.start_at = data.start_at
  form.end_at = data.end_at
  form.signup_start_at = data.signup_start_at
  form.signup_end_at = data.signup_end_at
  form.checkin_open_at = data.checkin_open_at
  form.checkin_close_at = data.checkin_close_at
  form.capacity = data.capacity
  form.need_review = data.need_review
  form.allow_cancel = data.allow_cancel
  form.cancel_deadline = data.cancel_deadline

  fields.value = data.form_schema.map((field) => ({
    ...field,
    optionsText: (field.options ?? []).join('，'),
  }))
  activityStatus.value = data.status
}

async function handleSubmit() {
  if (readonly.value) return

  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  const fieldError = validateFields()
  if (fieldError) {
    ElMessage.warning(fieldError)
    return
  }

  submitting.value = true
  try {
    const payload = buildPayload()
    if (isEdit.value) {
      await updateActivity(Number(route.params.id), payload)
      ElMessage.success('活动已保存')
    } else {
      await createActivity(payload)
      ElMessage.success('活动已创建，可在列表中发布')
    }
    await router.push('/activities')
  } catch {
    // 请求错误已统一提示
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  if (!isEdit.value) return
  pageLoading.value = true
  try {
    const data = await fetchActivity(Number(route.params.id))
    fillForm(data)
  } catch {
    await router.replace('/activities')
  } finally {
    pageLoading.value = false
  }
})
</script>

<template>
  <div v-loading="pageLoading" class="activity-edit-page">
    <div class="page-head">
      <div>
        <h2>{{ isEdit ? '编辑活动' : '新建活动' }}</h2>
        <p class="muted">
          配置活动信息与报名表单，保存后可在活动列表中发布。
        </p>
      </div>
      <el-button @click="router.push('/activities')">返回列表</el-button>
    </div>

    <el-alert
      v-if="readonly"
      class="readonly-alert"
      type="warning"
      title="该活动已下架或已结束，不能修改。"
      :closable="false"
      show-icon
    />

    <el-form
      ref="formRef"
      :model="form"
      :rules="rules"
      label-width="100px"
      :disabled="readonly"
    >
      <el-card shadow="never" class="section-card">
        <template #header>
          <div class="section-head">
            <h3>基础信息</h3>
            <p>活动名称、地点与对外展示内容</p>
          </div>
        </template>

        <el-row :gutter="20">
          <el-col :xs="24" :sm="12">
            <el-form-item label="活动标题" prop="title">
              <el-input
                v-model="form.title"
                placeholder="例如：2026 秋季技术分享会"
                maxlength="200"
              />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12">
            <el-form-item label="活动地点" prop="location_name">
              <el-input
                v-model="form.location_name"
                placeholder="例如：一号楼报告厅"
                maxlength="200"
              />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="活动摘要">
              <el-input
                v-model="form.summary"
                placeholder="显示在活动列表中的一句话介绍"
                maxlength="500"
                show-word-limit
              />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12">
            <el-form-item label="详细地址">
              <el-input
                v-model="form.address"
                placeholder="例如：XX 路 1 号一号楼 3 层"
                maxlength="500"
              />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12">
            <el-form-item label="封面图 URL">
              <el-input
                v-model="form.cover_url"
                placeholder="https://example.com/cover.jpg（首版填写图片链接）"
                maxlength="500"
              />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="活动详情">
              <el-input
                v-model="form.description"
                type="textarea"
                :rows="5"
                placeholder="介绍活动流程、嘉宾、注意事项等内容"
                maxlength="5000"
                show-word-limit
              />
            </el-form-item>
          </el-col>
        </el-row>
      </el-card>

      <el-card shadow="never" class="section-card">
        <template #header>
          <div class="section-head">
            <h3>时间设置</h3>
            <p>活动时间、报名窗口与签到开放时间</p>
          </div>
        </template>

        <el-row :gutter="20">
          <el-col :xs="24" :sm="12">
            <el-form-item label="活动开始" prop="start_at">
              <el-date-picker
                v-model="form.start_at"
                type="datetime"
                value-format="YYYY-MM-DDTHH:mm:ss"
                format="YYYY-MM-DD HH:mm"
                placeholder="选择开始时间"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12">
            <el-form-item label="活动结束" prop="end_at">
              <el-date-picker
                v-model="form.end_at"
                type="datetime"
                value-format="YYYY-MM-DDTHH:mm:ss"
                format="YYYY-MM-DD HH:mm"
                placeholder="选择结束时间"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12">
            <el-form-item label="报名开始" prop="signup_start_at">
              <el-date-picker
                v-model="form.signup_start_at"
                type="datetime"
                value-format="YYYY-MM-DDTHH:mm:ss"
                format="YYYY-MM-DD HH:mm"
                placeholder="选择报名开始时间"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12">
            <el-form-item label="报名截止" prop="signup_end_at">
              <el-date-picker
                v-model="form.signup_end_at"
                type="datetime"
                value-format="YYYY-MM-DDTHH:mm:ss"
                format="YYYY-MM-DD HH:mm"
                placeholder="选择报名截止时间"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12">
            <el-form-item label="签到开放">
              <el-date-picker
                v-model="form.checkin_open_at"
                type="datetime"
                value-format="YYYY-MM-DDTHH:mm:ss"
                format="YYYY-MM-DD HH:mm"
                placeholder="留空表示不限制"
                clearable
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12">
            <el-form-item label="签到关闭">
              <el-date-picker
                v-model="form.checkin_close_at"
                type="datetime"
                value-format="YYYY-MM-DDTHH:mm:ss"
                format="YYYY-MM-DD HH:mm"
                placeholder="留空表示不限制"
                clearable
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>
      </el-card>

      <el-card shadow="never" class="section-card">
        <template #header>
          <div class="section-head">
            <h3>报名规则</h3>
            <p>名额、审核与取消规则</p>
          </div>
        </template>

        <el-row :gutter="20">
          <el-col :xs="24" :sm="8">
            <el-form-item label="报名名额" prop="capacity">
              <el-input-number
                v-model="form.capacity"
                :min="1"
                :max="100000"
                controls-position="right"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="8">
            <el-form-item label="报名审核">
              <el-switch
                v-model="form.need_review"
                active-text="需要审核"
                inactive-text="自动通过"
              />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="8">
            <el-form-item label="允许取消">
              <el-switch
                v-model="form.allow_cancel"
                active-text="允许"
                inactive-text="不允许"
              />
            </el-form-item>
          </el-col>
          <el-col v-if="form.allow_cancel" :xs="24" :sm="12">
            <el-form-item label="取消截止">
              <el-date-picker
                v-model="form.cancel_deadline"
                type="datetime"
                value-format="YYYY-MM-DDTHH:mm:ss"
                format="YYYY-MM-DD HH:mm"
                placeholder="留空表示报名截止前均可取消"
                clearable
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>
      </el-card>

      <el-card shadow="never" class="section-card">
        <template #header>
          <div class="section-head section-head--row">
            <div>
              <h3>报名表单</h3>
              <p>姓名和手机号为系统字段，不可删除；自定义字段最多 30 个</p>
            </div>
            <el-button
              type="primary"
              plain
              :disabled="readonly"
              @click="addField"
            >
              添加字段
            </el-button>
          </div>
        </template>

        <el-table :data="fields" class="field-table">
          <el-table-column label="字段标识" width="150">
            <template #default="{ row }">
              <el-input
                v-model="row.key"
                size="small"
                :disabled="row.system || readonly"
                placeholder="英文标识"
              />
            </template>
          </el-table-column>

          <el-table-column label="显示名称" width="160">
            <template #default="{ row }">
              <el-input
                v-model="row.label"
                size="small"
                :disabled="readonly"
                placeholder="例如：所在单位"
              />
            </template>
          </el-table-column>

          <el-table-column label="类型" width="140">
            <template #default="{ row }">
              <el-select
                v-model="row.type"
                size="small"
                :disabled="row.system || readonly"
              >
                <el-option
                  v-for="item in fieldTypes"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </template>
          </el-table-column>

          <el-table-column label="选项（逗号分隔）" min-width="190">
            <template #default="{ row }">
              <el-input
                v-if="needsOptions(row.type)"
                v-model="row.optionsText"
                size="small"
                :disabled="readonly"
                placeholder="例如：是，否"
              />
              <span v-else class="muted">—</span>
            </template>
          </el-table-column>

          <el-table-column label="必填" width="80" align="center">
            <template #default="{ row }">
              <el-switch
                v-model="row.required"
                size="small"
                :disabled="row.system || readonly"
              />
            </template>
          </el-table-column>

          <el-table-column label="操作" width="80" align="center">
            <template #default="{ row, $index }">
              <el-button
                link
                type="danger"
                :disabled="row.system || readonly"
                @click="removeField($index)"
              >
                删除
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </el-form>

    <div class="form-actions">
      <el-button @click="router.push('/activities')">取消</el-button>
      <el-button
        type="primary"
        :loading="submitting"
        :disabled="readonly"
        @click="handleSubmit"
      >
        {{ isEdit ? '保存修改' : '创建活动' }}
      </el-button>
    </div>
  </div>
</template>

<style scoped>
.activity-edit-page {
  max-width: 1100px;
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

.readonly-alert {
  margin-bottom: 16px;
}

.section-card {
  margin-bottom: 16px;
  border: 1px solid var(--app-border);
  border-radius: 12px;
}

.section-card :deep(.el-card__header) {
  padding: 16px 22px;
  background: #fbfcfe;
  border-bottom: 1px solid #eef1f6;
}

.section-card :deep(.el-card__body) {
  padding: 22px 22px 4px;
}

.section-head h3 {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
}

.section-head p {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--app-muted);
}

.section-head--row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.field-table :deep(.el-table__header th) {
  background: #f9fafc;
  color: #64748b;
  font-weight: 500;
}

.field-table :deep(.el-select) {
  width: 100%;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 4px 0 32px;
}

@media (max-width: 760px) {
  .page-head {
    flex-direction: column;
  }

  .section-head--row {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
