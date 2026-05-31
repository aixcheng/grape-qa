<template>
  <div class="chat-page">
    <h2 class="page-title">💬 智能问答</h2>
    <div class="chat-container glass-card">
      <div class="history-area" v-if="messages.length">
        <div v-for="(msg, idx) in messages" :key="idx" :class="['message', msg.role]">
          <div class="avatar">
            <el-avatar :size="40" :src="msg.role === 'user' ? userAvatar : botAvatar" />
          </div>
          <div class="content">
            <div class="role">{{ msg.role === 'user' ? '我' : '助手' }}</div>
            <div class="text" v-html="formatAnswer(msg.content)"></div>
            <div v-if="msg.sources && msg.sources.length" class="sources">
              <el-divider content-position="left">参考来源</el-divider>
              <el-tag v-for="(src, i) in msg.sources" :key="i" size="small">{{ src }}</el-tag>
            </div>
          </div>
        </div>
      </div>
      <div class="input-area">
        <el-input
          v-model="question"
          type="textarea"
          :rows="3"
          placeholder="请输入问题，例如：葡萄黑痘病有什么症状？"
          @keydown.ctrl.enter="ask"
        />
        <el-button type="primary" :loading="loading" @click="ask" style="margin-top: 10px;">提问</el-button>
      </div>
    </div>
  </div>
</template>

<script>
import axios from 'axios'
import { useAuth } from '@/composables/useAuth'

export default {
  name: 'Chat',
  data() {
    return {
      question: '',
      loading: false,
      messages: [],
      userAvatar: 'https://cube.elemecdn.com/3/7c/3ea6beec64369c2642b92c6726f1epng.png',
      botAvatar: 'https://cube.elemecdn.com/0/88/03b0d39583f48206768a7534e55bcpng.png',
    }
  },
  methods: {
    formatAnswer(text) {
      return text.replace(/\n/g, '<br>')
    },
    async ask() {
      if (!this.question.trim()) {
        this.$message.warning('请输入问题')
        return
      }
      this.messages.push({ role: 'user', content: this.question })
      const currentQuestion = this.question
      this.question = ''
      this.loading = true
      try {
        const history = this.messages.slice(0, -1)
        const headers = {}
        const { token } = useAuth()
        if (token) headers['Authorization'] = `Bearer ${token}`
        const res = await axios.post('http://localhost:5000/api/chat', {
          question: currentQuestion,
          history,
        }, { headers })
        this.messages.push({
          role: 'assistant',
          content: res.data.answer,
          sources: res.data.sources || [],
        })
      } catch {
        this.$message.error('请求失败，请检查后端服务')
        this.messages.push({ role: 'assistant', content: '抱歉，服务暂时不可用。', sources: [] })
      } finally {
        this.loading = false
      }
    },
  },
}
</script>

<style scoped>
.chat-page { max-width: 900px; margin: 0 auto; }
.page-title { font-size: 22px; color: #fff; margin-bottom: 20px; }
.chat-container { padding: 24px; }
.history-area { max-height: 500px; overflow-y: auto; margin-bottom: 20px; }
.message { display: flex; margin-bottom: 20px; }
.message.user { flex-direction: row-reverse; }
.message .avatar { margin: 0 10px; }
.message .content { max-width: 70%; padding: 12px; border-radius: 12px; background: rgba(255,255,255,.06); color: #e0e0e0; }
.message.user .content { background: rgba(114,46,209,.25); }
.role { font-weight: bold; margin-bottom: 5px; font-size: 12px; color: var(--text-secondary); }
.text { line-height: 1.5; }
.sources { margin-top: 10px; font-size: 12px; }
.input-area { margin-top: 20px; }
</style>
