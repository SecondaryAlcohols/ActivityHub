<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { fetchActivities } from '@/api/attendee'
import type { ActivityItem } from '@/types'
import { formatDateTime } from '@/utils/format'

interface ActivityCard extends ActivityItem {
  startText: string
  endText: string
}

const router = useRouter()
const tabs = [
  { key: 'all', label: '全部' },
  { key: 'upcoming', label: '即将开始' },
  { key: 'ongoing', label: '进行中' },
  { key: 'past', label: '已结束' },
]

const activeTab = ref('all')
const activities = ref<ActivityCard[]>([])
const page = ref(1)
const pageSize = 10
const total = ref(0)
const hasMore = ref(true)
const loading = ref(false)

async function load(reset = true) {
  if (loading.value) return
  loading.value = true
  const nextPage = reset ? 1 : page.value + 1
  try {
    const data = await fetchActivities({
      tab: activeTab.value,
      page: nextPage,
      page_size: pageSize,
    })
    const items = data.items.map((item) => ({
      ...item,
      startText: formatDateTime(item.start_at),
      endText: formatDateTime(item.end_at),
    }))
    activities.value = reset
      ? items
      : activities.value.concat(items)
    page.value = nextPage
    total.value = data.total
    hasMore.value = activities.value.length < data.total
  } catch {
    // 错误提示由请求拦截器处理
  } finally {
    loading.value = false
  }
}

function switchTab(key: string) {
  if (key === activeTab.value) return
  activeTab.value = key
  activities.value = []
  hasMore.value = true
  load(true)
}

function openActivity(id: number) {
  router.push(`/activities/${id}`)
}

onMounted(() => load(true))
</script>

<template>
  <div class="page home-page">
    <section class="hero">
      <div class="hero-top">
        <div>
          <div class="eyebrow">EVENT SIGNUP</div>
          <h1>发现活动<br />遇见有意思的现场</h1>
        </div>
        <router-link to="/my" class="hero-link">我的报名</router-link>
      </div>
      <p class="hero-desc">
        浏览活动、提交报名、查看电子票。无需安装，打开网页即可参与。
      </p>
    </section>

    <div class="tabs">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        type="button"
        class="tab"
        :class="{ active: activeTab === tab.key }"
        @click="switchTab(tab.key)"
      >
        {{ tab.label }}
      </button>
    </div>

    <section class="activity-list">
      <article
        v-for="activity in activities"
        :key="activity.id"
        class="activity-card"
        @click="openActivity(activity.id)"
      >
        <div class="cover-wrap">
          <img
            v-if="activity.cover_url"
            :src="activity.cover_url"
            class="cover"
            alt=""
          />
          <div v-else class="cover cover-placeholder">
            <span>EVENT</span>
          </div>
          <span v-if="activity.need_review" class="tag tag-warn cover-tag">
            需审核
          </span>
        </div>
        <div class="card-body">
          <h2>{{ activity.title }}</h2>
          <p v-if="activity.summary" class="summary">{{ activity.summary }}</p>
          <div class="meta-row">
            <span>{{ activity.startText }}</span>
            <span class="remaining">余 {{ activity.remaining }} / {{ activity.capacity }}</span>
          </div>
          <div class="meta-row">
            <span>{{ activity.location_name }}</span>
            <span class="detail-link">查看详情 →</span>
          </div>
        </div>
      </article>

      <div v-if="loading" class="loading">加载中…</div>
      <div v-else-if="!activities.length" class="empty">
        <div>这个分类下还没有活动</div>
        <div class="empty-hint">切换到其他分类看看</div>
      </div>
      <button
        v-else-if="hasMore"
        type="button"
        class="load-more"
        @click="load(false)"
      >
        加载更多
      </button>
      <div v-else class="list-end">已经到底了 · 共 {{ total }} 场</div>
    </section>
  </div>
</template>

<style scoped>
.home-page {
  padding-top: 0;
}

.hero {
  position: relative;
  margin: 0 -20px 18px;
  padding: 28px 24px 30px;
  overflow: hidden;
  color: #fff;
  background:
    radial-gradient(circle at 85% 0%, rgba(124, 92, 255, 0.55), transparent 45%),
    linear-gradient(140deg, #1c2650, #2f46a8 60%, #5a3fd6);
  border-radius: 0 0 26px 26px;
}

.hero::after {
  content: '';
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(255, 255, 255, 0.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.05) 1px, transparent 1px);
  background-size: 34px 34px;
  mask-image: linear-gradient(to bottom, rgba(0, 0, 0, 0.65), transparent 85%);
  pointer-events: none;
}

.hero-top {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
}

.eyebrow {
  font-size: 10px;
  letter-spacing: 3px;
  color: rgba(255, 255, 255, 0.6);
}

.hero h1 {
  margin: 12px 0 0;
  font-size: 28px;
  line-height: 1.35;
  font-weight: 600;
  letter-spacing: -0.5px;
}

.hero-link {
  flex-shrink: 0;
  padding: 8px 14px;
  border: 1px solid rgba(255, 255, 255, 0.28);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.1);
  color: #fff;
  font-size: 12px;
  white-space: nowrap;
}

.hero-desc {
  position: relative;
  z-index: 1;
  margin: 16px 0 0;
  max-width: 320px;
  font-size: 13px;
  line-height: 1.7;
  color: rgba(255, 255, 255, 0.68);
}

.tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
  overflow-x: auto;
  scrollbar-width: none;
}

.tabs::-webkit-scrollbar {
  display: none;
}

.tab {
  flex-shrink: 0;
  padding: 9px 16px;
  border: 1px solid transparent;
  border-radius: 999px;
  background: #fff;
  color: var(--muted);
  font-size: 13px;
  box-shadow: 0 4px 14px rgba(31, 41, 55, 0.04);
}

.tab.active {
  background: var(--primary);
  color: #fff;
}

.activity-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.activity-card {
  overflow: hidden;
  border-radius: 18px;
  background: #fff;
  box-shadow: var(--shadow);
  cursor: pointer;
  transition: transform 0.16s ease, box-shadow 0.16s ease;
}

.activity-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 14px 40px rgba(31, 41, 55, 0.1);
}

.cover-wrap {
  position: relative;
}

.cover {
  display: block;
  width: 100%;
  height: 150px;
  object-fit: cover;
}

.cover-placeholder {
  display: grid;
  place-items: center;
  background:
    linear-gradient(120deg, rgba(255, 255, 255, 0.1) 1px, transparent 1px),
    linear-gradient(140deg, #25305e, #4f6ef7 60%, #7c5cff);
  background-size: 32px 32px, 100% 100%;
  color: rgba(255, 255, 255, 0.72);
  font-size: 15px;
  letter-spacing: 6px;
}

.cover-tag {
  position: absolute;
  top: 12px;
  right: 12px;
  backdrop-filter: blur(6px);
}

.card-body {
  padding: 16px 18px 18px;
}

.card-body h2 {
  margin: 0;
  font-size: 17px;
  font-weight: 600;
  line-height: 1.4;
}

.summary {
  margin: 7px 0 0;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  color: var(--muted);
  font-size: 12.5px;
  line-height: 1.6;
}

.meta-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 10px;
  color: var(--muted);
  font-size: 12.5px;
}

.remaining {
  color: var(--primary);
  font-weight: 500;
}

.detail-link {
  color: var(--primary);
  font-size: 12px;
}

@media (max-width: 620px) {
  .hero {
    margin: 0 -16px 16px;
    padding: 24px 20px 26px;
  }

  .hero h1 {
    font-size: 26px;
  }
}
</style>
