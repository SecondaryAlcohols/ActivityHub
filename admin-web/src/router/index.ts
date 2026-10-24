import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { public: true, title: '登录' },
    },
    {
      path: '/',
      component: () => import('@/layouts/AdminLayout.vue'),
      redirect: '/activities',
      children: [
        {
          path: 'activities',
          name: 'activities',
          component: () => import('@/views/ActivityListView.vue'),
          meta: { title: '活动管理' },
        },
        {
          path: 'activities/new',
          name: 'activity-create',
          component: () => import('@/views/ActivityEditView.vue'),
          meta: { title: '新建活动' },
        },
        {
          path: 'activities/:id/edit',
          name: 'activity-edit',
          component: () => import('@/views/ActivityEditView.vue'),
          meta: { title: '编辑活动' },
        },
        {
          path: 'activities/:id/registrations',
          name: 'activity-registrations',
          component: () => import('@/views/RegistrationListView.vue'),
          meta: { title: '报名管理' },
        },
      ],
    },
    {
      path: '/:pathMatch(.*)*',
      name: 'not-found',
      component: () => import('@/views/NotFoundView.vue'),
      meta: { public: true, title: '页面不存在' },
    },
  ],
})

router.beforeEach((to) => {
  const token = localStorage.getItem('admin_token')
  if (!to.meta.public && !token) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.name === 'login' && token) {
    return { name: 'activities' }
  }
  return true
})

router.afterEach((to) => {
  const title = typeof to.meta.title === 'string' ? to.meta.title : ''
  document.title = title ? `${title} · 活动管理平台` : '活动管理平台'
})

export default router
