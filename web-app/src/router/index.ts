import { createRouter, createWebHistory } from 'vue-router'

import { token } from '@/auth'

const router = createRouter({
  history: createWebHistory(),
  scrollBehavior: () => ({ top: 0 }),
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('@/views/ActivityListView.vue'),
      meta: { title: '活动报名' },
    },
    {
      path: '/activities/:id',
      name: 'activity-detail',
      component: () => import('@/views/ActivityDetailView.vue'),
      meta: { title: '活动详情' },
    },
    {
      path: '/activities/:id/signup',
      name: 'signup',
      component: () => import('@/views/SignupView.vue'),
      meta: { title: '填写报名', requiresAuth: true },
    },
    {
      path: '/signup/result/:id',
      name: 'signup-result',
      component: () => import('@/views/SignupResultView.vue'),
      meta: { title: '报名结果', requiresAuth: true },
    },
    {
      path: '/my',
      name: 'my',
      component: () => import('@/views/MyRegistrationsView.vue'),
      meta: { title: '我的报名' },
    },
    {
      path: '/registrations/:id',
      name: 'registration-detail',
      component: () => import('@/views/RegistrationDetailView.vue'),
      meta: { title: '报名详情', requiresAuth: true },
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { title: '登录' },
    },
    {
      path: '/register',
      name: 'register',
      component: () => import('@/views/RegisterView.vue'),
      meta: { title: '注册' },
    },
    {
      path: '/:pathMatch(.*)*',
      name: 'not-found',
      component: () => import('@/views/NotFoundView.vue'),
      meta: { title: '页面不存在' },
    },
  ],
})

router.beforeEach((to) => {
  if (to.meta.requiresAuth && !token.value) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if ((to.name === 'login' || to.name === 'register') && token.value) {
    return { name: 'home' }
  }
  return true
})

router.afterEach((to) => {
  const title = typeof to.meta.title === 'string' ? to.meta.title : ''
  document.title = title ? `${title} · 活动报名` : '活动报名'
})

export default router
