<template>
  <el-menu
    :default-active="currentRoute"
    mode="horizontal"
    :ellipsis="false"
    class="navbar"
    background-color="#1a1a2e"
    text-color="#a0a0a0"
    active-text-color="#d4a017"
  >
    <div class="nav-brand" @click="$router.push('/')">
      <span class="logo-icon"><img src="/grape-doctor-nobg.png" alt="logo" /></span> 葡萄医生
    </div>
    <div class="nav-links">
      <el-menu-item index="/chat" @click="$router.push('/chat')">💬 智能问答</el-menu-item>
      <el-menu-item index="/knowledge" @click="$router.push('/knowledge')">📚 知识区</el-menu-item>
      <el-menu-item v-if="isLoggedIn" index="/history" @click="$router.push('/history')">📋 历史记录</el-menu-item>
    </div>
    <div class="nav-user">
      <template v-if="isLoggedIn">
        <el-dropdown>
          <span class="username">{{ username }}</span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="logout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </template>
      <template v-else>
        <span class="guest-tag">游客模式</span>
        <el-button type="primary" size="small" @click="$router.push('/login')">登录</el-button>
      </template>
    </div>
  </el-menu>
</template>

<script>
export default {
  inject: ['auth', 'logout'],
  computed: {
    currentRoute() {
      return this.$route.path
    },
    isLoggedIn() {
      return this.auth?.user
    },
    username() {
      return this.auth?.user?.username
    },
  },
}
</script>

<style scoped>
.navbar {
  display: flex;
  align-items: center;
  padding: 0 24px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06) !important;
}
.logo-icon img {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  vertical-align: middle;
  margin-right: 6px;
}
.nav-brand {
  font-size: 16px;
  font-weight: 700;
  color: #fff;
  cursor: pointer;
  margin-right: 32px;
  white-space: nowrap;
}
.nav-links {
  display: flex;
  flex: 1;
  border-bottom: none !important;
}
.nav-user {
  display: flex;
  align-items: center;
  gap: 12px;
}
.username {
  color: #d4a017;
  cursor: pointer;
  font-size: 14px;
}
.guest-tag {
  color: #909399;
  font-size: 13px;
}
</style>
