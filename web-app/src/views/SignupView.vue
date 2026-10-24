<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { createRegistration, fetchActivity } from '@/api/attendee'
import { user } from '@/auth'
import { toast } from '@/toast'
import type { ActivityDetail, FormField } from '@/types'

type FormControl = HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement

const route = useRoute()
const router = useRouter()
const activityId = Number(route.params.id)

const activity = ref<ActivityDetail | null>(null)
const fields = ref<FormField[]>([])
const answers = reactive<Record<string, unknown>>({})
const multiValues = reactive<Record<string, string[]>>({})
const loading = ref(true)
const submitting = ref(false)

function fieldValue(field: FormField) {
  const value = answers[field.key]
  return value === undefined || value === null ? '' : String(value)
}

function onInput(key: string, event: Event) {
  answers[key] = (event.target as FormControl).value
}

function toggleMulti(field: FormField, option: string) {
  const current = multiValues[field.key] || []
  const next = current.includes(option)
    ? current.filter((item) => item !== option)
    : current.concat(option)
  multiValues[field.key] = next
  answers[field.key] = next
}

function isSelected(field: FormField, option: string) {
  return (multiValues[field.key] || []).includes(option)
}

function isEmpty(value: unknown) {
  if (Array.isArray(value)) return value.length === 0
  return !String(value ?? '').trim()
}

function validate() {
  for (const field of fields.value) {
    const value = answers[field.key]
    if (field.required && isEmpty(value)) {
      return `请填写「${field.label}」`
    }
    if (isEmpty(value)) continue

    if (field.type === 'phone' && !/^1[3-9]\d{9}$/.test(String(value))) {
      return '手机号格式不正确'
    }
    if (
      field.type === 'email' &&
      !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(String(value))
    ) {
      return '邮箱格式不正确'
    }
    if (field.type === 'number' && Number.isNaN(Number(value))) {
      return `「${field.label}」必须是数字`
    }
  }
  return null
}

function buildAnswers() {
  const payload: Record<string, unknown> = {}
  for (const field of fields.value) {
    const value = answers[field.key]
    if (isEmpty(value)) continue
    payload[field.key] = Array.isArray(value)
      ? value
      : String(value).trim()
  }
  return payload
}

async function submit() {
  const error = validate()
  if (error) {
    toast(error, 'info')
    return
  }
  if (submitting.value) return

  submitting.value = true
  try {
    const registration = await createRegistration(
      activityId,
      buildAnswers(),
    )
    router.replace(`/signup/result/${registration.id}`)
  } catch {
    // 错误提示由请求拦截器处理
  } finally {
    submitting.value = false
  }
}

async function load() {
  loading.value = true
  try {
    const data = await fetchActivity(activityId)
    if (!data.signup_state.can_signup) {
      toast('当前不可报名', 'info')
      router.replace(`/activities/${activityId}`)
      return
    }

    activity.value = data
    fields.value = data.form_schema
    const previous = (data.my_registration?.answers || {}) as Record<
      string,
      unknown
    >

    for (const field of data.form_schema) {
      if (field.type === 'multi_select') {
        const value = Array.isArray(previous[field.key])
          ? (previous[field.key] as string[])
          : []
        multiValues[field.key] = value
        answers[field.key] = value
      } else if (previous[field.key] !== undefined) {
        answers[field.key] = previous[field.key]
      } else if (field.key === 'phone') {
        answers[field.key] = user.value?.phone || ''
      } else {
        answers[field.key] = ''
      }
    }
  } catch {
    // 错误提示由请求拦截器处理
  } finally {
    loading.value = false
  }
}

function goBack() {
  router.push(`/activities/${activityId}`)
}

onMounted(load)
</script>

<template>
  <div class="page signup-page">
    <button type="button" class="back-link" @click="goBack">
      ← 返回活动详情
    </button>

    <div v-if="loading" class="loading">加载中…</div>
    <template v-else-if="activity">
      <div class="form-head">
        <h1>填写报名信息</h1>
        <p class="form-sub">{{ activity.title }}</p>
        <div class="form-meta">
          剩余 {{ activity.remaining }} 个名额
          <span class="dot"></span>
          {{ activity.need_review ? '提交后需管理员审核' : '提交后自动通过' }}
        </div>
      </div>

      <div class="form-card">
        <div
          v-for="field in fields"
          :key="field.key"
          class="field"
        >
          <label class="field-label">
            {{ field.label }}
            <span v-if="field.required" class="required">*</span>
          </label>

          <textarea
            v-if="field.type === 'textarea'"
            class="textarea"
            :value="fieldValue(field)"
            :placeholder="field.placeholder || '请输入'"
            maxlength="2000"
            @input="onInput(field.key, $event)"
          ></textarea>

          <select
            v-else-if="field.type === 'select'"
            class="select"
            :value="fieldValue(field)"
            @change="onInput(field.key, $event)"
          >
            <option value="" disabled>请选择</option>
            <option
              v-for="option in field.options || []"
              :key="option"
              :value="option"
            >
              {{ option }}
            </option>
          </select>

          <div
            v-else-if="field.type === 'multi_select'"
            class="choice-row"
          >
            <button
              v-for="option in field.options || []"
              :key="option"
              type="button"
              class="choice"
              :class="{ selected: isSelected(field, option) }"
              @click="toggleMulti(field, option)"
            >
              {{ option }}
            </button>
          </div>

          <input
            v-else
            class="input"
            :type="
              field.type === 'phone'
                ? 'tel'
                : field.type === 'number'
                  ? 'number'
                  : field.type === 'date'
                    ? 'date'
                    : field.type === 'email'
                      ? 'email'
                      : 'text'
            "
            :value="fieldValue(field)"
            :placeholder="field.placeholder || '请输入'"
            :maxlength="field.type === 'date' ? undefined : 200"
            @input="onInput(field.key, $event)"
          />
        </div>
      </div>

      <p class="consent">
        提交即表示同意活动主办方收集并使用以上信息，用于报名与现场签到。
      </p>

      <button
        type="button"
        class="primary-btn submit-btn"
        :disabled="submitting"
        @click="submit"
      >
        {{ submitting ? '提交中…' : '提交报名' }}
      </button>
    </template>
  </div>
</template>

<style scoped>
.signup-page {
  padding-bottom: 30px;
}

.back-link {
  margin-bottom: 14px;
  padding: 0;
  border: none;
  background: transparent;
  color: var(--muted);
  font-size: 13px;
}

.form-head h1 {
  margin: 0;
  font-size: 24px;
  font-weight: 650;
  letter-spacing: -0.4px;
}

.form-sub {
  margin: 7px 0 0;
  color: #4b5563;
  font-size: 13.5px;
}

.form-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
  color: var(--soft);
  font-size: 12px;
}

.dot {
  width: 3px;
  height: 3px;
  border-radius: 50%;
  background: #c4c9d4;
}

.form-card {
  margin-top: 16px;
  padding: 4px 18px;
  border-radius: 18px;
  background: #fff;
  box-shadow: var(--shadow);
}

.consent {
  margin: 16px 4px 18px;
  color: #a0a7b4;
  font-size: 11px;
  line-height: 1.65;
}

.submit-btn {
  height: 48px;
}
</style>
