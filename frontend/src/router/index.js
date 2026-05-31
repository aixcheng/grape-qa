import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', name: 'Home', component: () => import('@/views/Home.vue') },
  { path: '/login', name: 'Login', component: () => import('@/views/Login.vue') },
  { path: '/chat', name: 'Chat', component: () => import('@/views/Chat.vue') },
  { path: '/knowledge', name: 'Knowledge', component: () => import('@/views/Knowledge.vue') },
  { path: '/knowledge/:name', name: 'KnowledgeDetail', component: () => import('@/views/KnowledgeDetail.vue') },
  { path: '/history', name: 'History', component: () => import('@/views/History.vue'), meta: { requiresAuth: true } },
  { path: '/graph', name: 'KnowledgeGraph', component: () => import('@/views/KnowledgeGraph.vue') },
  { path: '/workflow', name: 'SearchWorkflow', component: () => import('@/views/SearchWorkflow.vue') },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
