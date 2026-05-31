<template>
  <div class="login-page">
    <div class="login-card glass-card">
      <h2>🍇 欢迎</h2>
      <el-tabs v-model="mode" class="tabs">
        <el-tab-pane label="登录" name="login" />
        <el-tab-pane label="注册" name="register" />
      </el-tabs>
      <el-form :model="form" label-position="top">
        <el-form-item label="用户名">
          <el-input v-model="form.username" placeholder="请输入用户名" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" show-password placeholder="请输入密码" />
        </el-form-item>
        <el-form-item v-if="mode === 'register'" label="确认密码">
          <el-input v-model="form.confirm" type="password" show-password placeholder="请再次输入密码" />
        </el-form-item>
        <el-button type="primary" :loading="loading" class="submit-btn" @click="submit">
          {{ mode === 'login' ? '登 录' : '注 册' }}
        </el-button>
      </el-form>
      <div class="guest-link" @click="guestEnter">游客模式：直接进入系统</div>
    </div>
  </div>
</template>

<script>
import axios from 'axios'

export default {
  name: 'Login',
  inject: ['login', 'register'],
  data() {
    return {
      mode: 'login',
      loading: false,
      form: { username: '', password: '', confirm: '' },
    }
  },
  methods: {
    async submit() {
      if (!this.form.username || !this.form.password) {
        this.$message.warning('请填写用户名和密码')
        return
      }
      if (this.mode === 'register') {
        if (this.form.password.length < 6) {
          this.$message.warning('密码至少 6 位')
          return
        }
        if (this.form.password !== this.form.confirm) {
          this.$message.warning('两次密码不一致')
          return
        }
      }
      this.loading = true
      try {
        const url = this.mode === 'login' ? '/api/login' : '/api/register'
        const res = await axios.post(`http://localhost:5000${url}`, {
          username: this.form.username,
          password: this.form.password,
        })
        const { token, username } = res.data
        if (this.mode === 'login') {
          this.login(token, username)
        } else {
          this.register(token, username)
        }
        this.$message.success(this.mode === 'login' ? '登录成功' : '注册成功')
        this.$router.push('/chat')
      } catch (err) {
        const msg = err.response?.data?.error || '操作失败'
        this.$message.error(msg)
      } finally {
        this.loading = false
      }
    },
    guestEnter() {
      this.$router.push('/chat')
    },
  },
}
</script>

<style scoped>
.login-page {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: calc(100vh - 140px);
}
.login-card {
  width: 400px;
  padding: 40px;
}
.login-card h2 { text-align: center; margin-bottom: 8px; color: #fff; }
.tabs { margin-bottom: 8px; }
.submit-btn { width: 100%; margin-top: 8px; }
.guest-link {
  text-align: center;
  margin-top: 16px;
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 13px;
}
.guest-link:hover { color: var(--grape-purple); }
</style>
