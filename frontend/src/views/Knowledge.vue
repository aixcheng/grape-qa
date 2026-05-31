<template>
  <div class="knowledge-page">
    <h2 class="page-title">📚 知识百科</h2>

    <div class="search-bar">
      <el-input v-model="search" placeholder="搜索病虫害名称..." clearable @clear="fetchList" @keydown.enter="fetchList" />
      <el-button type="primary" @click="fetchList">搜索</el-button>
    </div>

    <div class="filter-tags">
      <span :class="['tag', { active: category === '' }]" @click="category = ''; fetchList()">全部</span>
      <span :class="['tag', { active: category === 'disease' }]" @click="category = 'disease'; fetchList()">🦠 病害</span>
      <span :class="['tag', { active: category === 'pest' }]" @click="category = 'pest'; fetchList()">🐛 虫害</span>
    </div>

    <div v-if="loading" class="loading-area">
      <el-skeleton :rows="3" animated />
    </div>

    <div v-else-if="items.length" class="carousel-wrap">
      <div class="arrow left" @click="prev">◀</div>

      <div class="carousel-track">
        <KnowledgeCard
          v-for="(item, i) in displayedItems"
          :key="item.name"
          :name="item.name"
          :category="item.category"
          :summary="item.summary"
          :active="i === centerIndex"
          :photo="getPhoto(item.name)"
          @click="goDetail(item.name)"
        />
      </div>

      <div class="arrow right" @click="next">▶</div>
    </div>

    <div v-if="items.length" class="dots">
      <span v-for="(_, i) in items" :key="i" :class="['dot', { active: i === currentIndex }]" @click="currentIndex = i"></span>
    </div>

    <el-empty v-if="!loading && !items.length" description="未找到匹配的病虫害" />
  </div>
</template>

<script>
import axios from 'axios'
import KnowledgeCard from '@/components/KnowledgeCard.vue'

export default {
  name: 'Knowledge',
  components: { KnowledgeCard },
  data() {
    return { items: [], category: '', search: '', currentIndex: 0, loading: false }
  },
  computed: {
    centerIndex() { return 1 },
    displayedItems() {
      const len = this.items.length
      if (len === 0) return []
      if (len === 1) return this.items
      if (len === 2) return [...this.items, ...this.items].slice(0, 3)
      const prev = (this.currentIndex - 1 + len) % len
      const next = (this.currentIndex + 1) % len
      return [
        this.items[prev],
        this.items[this.currentIndex],
        this.items[next],
      ]
    },
  },
  async mounted() { await this.fetchList() },
  methods: {
    async fetchList() {
      this.loading = true
      try {
        const params = {}
        if (this.category) params.category = this.category
        if (this.search) params.search = this.search
        const res = await axios.get('http://localhost:5000/api/knowledge/list', { params })
        this.items = res.data
        this.currentIndex = 0
      } catch {
        this.$message.error('获取知识列表失败')
      } finally {
        this.loading = false
      }
    },
    prev() {
      const len = this.items.length
      this.currentIndex = (this.currentIndex - 1 + len) % len
    },
    next() {
      const len = this.items.length
      this.currentIndex = (this.currentIndex + 1) % len
    },
    getPhoto(name) {
      return `/photos/${encodeURIComponent(name)}.jpg`
    },
    goDetail(name) {
      this.$router.push(`/knowledge/${encodeURIComponent(name)}`)
    },
  },
}
</script>

<style scoped>
.knowledge-page { max-width: 1000px; margin: 0 auto; }
.page-title { font-size: 22px; color: #fff; margin-bottom: 20px; }
.search-bar { display: flex; gap: 10px; margin-bottom: 16px; }
.filter-tags { display: flex; gap: 10px; justify-content: center; margin-bottom: 32px; }
.tag {
  padding: 6px 20px;
  border-radius: 20px;
  background: rgba(255,255,255,.06);
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 14px;
  transition: all .2s;
}
.tag.active { background: var(--grape-purple); color: #fff; }
.tag:hover:not(.active) { background: rgba(255,255,255,.12); }

.carousel-wrap { position: relative; display: flex; align-items: center; justify-content: center; min-height: 440px; }
.carousel-track { display: flex; gap: 20px; align-items: center; justify-content: center; }
.arrow {
  position: absolute;
  z-index: 10;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: rgba(255,255,255,.1);
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: #fff;
  font-size: 16px;
  transition: background .2s;
}
.arrow:hover { background: rgba(255,255,255,.2); }
.arrow.left { left: -20px; }
.arrow.right { right: -20px; }

.dots { display: flex; gap: 8px; justify-content: center; margin-top: 20px; }
.dot { width: 8px; height: 8px; border-radius: 50%; background: rgba(255,255,255,.15); cursor: pointer; transition: all .2s; }
.dot.active { width: 24px; border-radius: 4px; background: var(--grape-purple); }

.loading-area { padding: 40px; }
</style>
