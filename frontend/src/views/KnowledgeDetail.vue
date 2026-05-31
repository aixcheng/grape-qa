<template>
  <div class="detail-page">
    <div class="back-link" @click="$router.push('/knowledge')">← 返回知识区</div>

    <div v-if="loading">
      <el-skeleton :rows="8" animated />
    </div>

    <div v-else-if="item" class="detail-content">
      <div class="detail-header glass-card">
        <span class="d-tag" :class="item.category">{{ item.category === 'disease' ? '🦠 病害' : '🐛 虫害' }}</span>
        <h2>{{ item.name }}</h2>
        <p v-if="item.summary" class="d-summary">{{ item.summary }}</p>
      </div>

      <div v-for="(sec, i) in item.sections" :key="i" class="section glass-card">
        <h3>{{ sec.title }}</h3>
        <div class="section-body">{{ sec.content }}</div>
      </div>
    </div>

    <el-empty v-else description="未找到该病虫害信息" />
  </div>
</template>

<script>
import axios from 'axios'

export default {
  name: 'KnowledgeDetail',
  data() { return { item: null, loading: false } },
  async mounted() {
    this.loading = true
    try {
      const name = decodeURIComponent(this.$route.params.name)
      const res = await axios.get(`http://localhost:5000/api/knowledge/${name}`)
      this.item = res.data
    } catch {
      this.$message.error('获取详情失败')
    } finally {
      this.loading = false
    }
  },
}
</script>

<style scoped>
.detail-page { max-width: 800px; margin: 0 auto; }
.back-link { color: var(--grape-purple); cursor: pointer; margin-bottom: 20px; font-size: 14px; }
.back-link:hover { color: #9b59ff; }
.detail-header { padding: 32px; margin-bottom: 24px; }
.d-tag { display: inline-block; padding: 4px 14px; border-radius: 14px; font-size: 12px; margin-bottom: 12px; }
.d-tag.disease { background: rgba(245,108,108,.25); color: #f56c6c; }
.d-tag.pest { background: rgba(64,158,255,.25); color: #409eff; }
.detail-header h2 { font-size: 26px; font-weight: 700; color: #fff; margin-bottom: 10px; }
.d-summary { color: var(--text-secondary); line-height: 1.6; }
.section { padding: 28px 32px; margin-bottom: 16px; }
.section h3 { font-size: 18px; color: var(--gold); margin-bottom: 14px; border-left: 3px solid var(--grape-purple); padding-left: 12px; }
.section-body { color: #ccc; line-height: 1.8; font-size: 14px; white-space: pre-wrap; }
</style>
