<template>
  <el-config-provider>
    <div id="app-shell">
      <NavBar />
      <main class="main-content">
        <router-view v-slot="{ Component }">
          <transition name="fade-slide" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>
    </div>
  </el-config-provider>
</template>

<script>
import { reactive } from 'vue'
import NavBar from './components/NavBar.vue'

const authState = reactive({
  user: JSON.parse(localStorage.getItem('grape_user') || 'null'),
  token: localStorage.getItem('grape_token') || '',
})

export default {
  components: { NavBar },
  provide() {
    return {
      auth: authState,
      login: this.login,
      logout: this.logout,
      register: this.register,
    }
  },
  watch: {
    $route(to) {
      if (to.meta.requiresAuth && !authState.user) {
        this.$router.push('/login')
      }
    },
  },
  methods: {
    login(token, username) {
      authState.token = token
      authState.user = { username }
      localStorage.setItem('grape_token', token)
      localStorage.setItem('grape_user', JSON.stringify({ username }))
    },
    logout() {
      authState.token = ''
      authState.user = null
      localStorage.removeItem('grape_token')
      localStorage.removeItem('grape_user')
      this.$router.push('/')
    },
    register(token, username) {
      this.login(token, username)
    },
  },
}
</script>

<style>
#app-shell {
  min-height: 100vh;
  position: relative;
  background: var(--bg-dark);
}
#app-shell::before {
  content: '';
  position: fixed;
  inset: 0;
  background: url('/grape-garden.jpg') center/cover no-repeat;
  opacity: 0.15;
  z-index: 0;
  pointer-events: none;
}
#app-shell > * {
  position: relative;
  z-index: 1;
}
.main-content {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
}
</style>
