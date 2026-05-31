<template>
  <div class="home">
    <div class="hero">
      <div class="hero-icon">
        <img src="/grape-doctor-nobg.png" alt="葡萄医生" class="hero-logo" />
      </div>
      <h1>葡萄医生</h1>
      <p class="hero-desc">基于GraphRAG的葡萄病虫害知识问答系统</p>
      <div class="chat-box glass-card">
        <div class="chat-input-row">
          <el-input
            v-model="question"
            type="textarea"
            :rows="2"
            placeholder="输入葡萄病虫害问题，例如：葡萄黑痘病怎么防治？"
            @keydown.ctrl.enter="ask"
            class="chat-textarea"
          />
          <el-button type="primary" :loading="loading" class="ask-btn" @click="ask">提问</el-button>
        </div>
        <div v-if="answer" class="answer-area">
          <div class="answer-text" v-html="formatAnswer(answer)"></div>
          <div v-if="sources.length" class="answer-sources">
            <el-tag v-for="(s, i) in sources" :key="i" size="small" class="src-tag">{{ s }}</el-tag>
          </div>
        </div>
      </div>
    </div>
    <div class="features">
      <div class="feature glass-card clickable" @click="$router.push('/graph')">
        <div class="feature-icon">🧠</div>
        <h3>知识图谱</h3>
        <p>基于 Neo4j 构建的葡萄病虫害关系网络，精准定位问题答案</p>
      </div>
      <div class="feature glass-card clickable" @click="$router.push('/workflow')">
        <div class="feature-icon">🔍</div>
        <h3>智能检索</h3>
        <p>向量语义检索 + 图谱关系检索，双路召回确保答案质量</p>
      </div>
      <div class="feature glass-card clickable" @click="$router.push('/knowledge')">
        <div class="feature-icon">📖</div>
        <h3>知识科普</h3>
        <p>覆盖 40 种葡萄病虫害的完整知识库，症状、病原、防治一应俱全</p>
      </div>
    </div>
  </div>
</template>

<script>
import axios from 'axios'
import { useAuth } from '@/composables/useAuth'

export default {
  name: 'Home',
  data() {
    return {
      question: '',
      loading: false,
      answer: '',
      sources: [],
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
      const q = this.question
      this.question = ''
      this.loading = true
      this.answer = ''
      this.sources = []
      try {
        const headers = {}
        const { token } = useAuth()
        if (token) headers['Authorization'] = `Bearer ${token}`
        const res = await axios.post('http://localhost:5000/api/chat', {
          question: q,
          history: [],
        }, { headers })
        this.answer = res.data.answer
        this.sources = res.data.sources || []
      } catch {
        this.$message.error('请求失败，请检查后端服务')
      } finally {
        this.loading = false
      }
    },
  },
}
</script>

<style scoped>
.home { text-align: center; }
.hero { padding: 50px 20px 20px; }
.hero-icon { margin-bottom: 16px; }
.hero-logo { width: 100px; height: 100px; border-radius: 20px; }
.hero h1 { font-size: 32px; font-weight: 700; color: #fff; margin-bottom: 8px; }
.hero-desc { color: var(--text-secondary); font-size: 16px; margin-bottom: 24px; }
.chat-box { max-width: 640px; margin: 0 auto 48px; padding: 20px 24px; text-align: left; }
.chat-input-row { display: flex; gap: 10px; align-items: flex-end; }
.chat-textarea { flex: 1; }
.ask-btn { flex-shrink: 0; }
.answer-area { margin-top: 16px; padding-top: 16px; border-top: 1px solid rgba(255,255,255,.08); }
.answer-text { color: #e0e0e0; line-height: 1.7; font-size: 14px; }
.answer-sources { margin-top: 12px; display: flex; flex-wrap: wrap; gap: 6px; }
.src-tag { opacity: .7; font-size: 11px; }
.features { display: grid; grid-template-columns: repeat(3, 1fr); gap: 24px; margin-top: 48px; }
.feature { padding: 32px 24px; text-align: center; }
.feature-icon { font-size: 36px; margin-bottom: 12px; }
.feature h3 { color: #fff; margin-bottom: 8px; font-size: 18px; }
.feature.clickable { cursor: pointer; }
.feature.clickable:hover { border-color: var(--grape-purple); }
.feature p { color: var(--text-secondary); font-size: 14px; line-height: 1.6; }
@media (max-width: 768px) {
  .features { grid-template-columns: 1fr; }
}
</style>
