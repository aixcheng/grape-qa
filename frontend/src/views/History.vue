<template>
  <div class="history-page">
    <h2 class="page-title">📋 问答历史</h2>

    <div v-if="loading"><el-skeleton :rows="5" animated /></div>

    <div v-else-if="records.length">
      <div v-for="r in records" :key="r.id" class="record glass-card">
        <div class="record-q">
          <span class="label">Q</span>
          {{ r.question }}
        </div>
        <div class="record-a">
          <span class="label">A</span>
          <span v-html="r.answer.replace(/\n/g, '<br>')"></span>
        </div>
        <div class="record-meta">{{ r.created_at }}</div>
      </div>
    </div>

    <el-empty v-else description="暂无问答记录" />
  </div>
</template>

<script>
import axios from 'axios'
import { useAuth } from '@/composables/useAuth'

export default {
  name: 'History',
  data() { return { records: [], loading: false } },
  async mounted() {
    this.loading = true
    try {
      const { token } = useAuth()
      const res = await axios.get('http://localhost:5000/api/history', {
        headers: { Authorization: `Bearer ${token}` },
      })
      this.records = res.data
    } catch {
      this.$message.error('获取历史记录失败')
    } finally {
      this.loading = false
    }
  },
}
</script>

<style scoped>
.history-page { max-width: 800px; margin: 0 auto; }
.page-title { font-size: 22px; color: #fff; margin-bottom: 20px; }
.record { padding: 20px 24px; margin-bottom: 16px; }
.record-q { margin-bottom: 12px; line-height: 1.6; color: #e0e0e0; }
.record-a { color: var(--text-secondary); line-height: 1.6; }
.label { display: inline-block; width: 24px; height: 24px; border-radius: 50%; background: var(--grape-purple); color: #fff; text-align: center; line-height: 24px; font-size: 12px; font-weight: 700; margin-right: 8px; vertical-align: top; }
.record-meta { font-size: 12px; color: #666; margin-top: 12px; }
</style>
