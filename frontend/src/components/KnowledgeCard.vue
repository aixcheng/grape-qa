<template>
  <div class="k-card glass-card" :class="{ active: active }" @click="$emit('click')">
    <div class="k-card-bg" :class="category" :style="photo ? { backgroundImage: 'url(' + photo + ')' } : {}"></div>
    <div class="k-card-overlay"></div>
    <div class="k-card-body">
      <span class="k-tag" :class="category">{{ category === 'disease' ? '🦠 病害' : '🐛 虫害' }}</span>
      <h3>{{ name }}</h3>
      <p v-if="summary">{{ summary }}</p>
      <div class="k-hint">点击查看详情 →</div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'KnowledgeCard',
  props: { name: String, category: String, summary: String, active: Boolean, photo: String },
  emits: ['click'],
}
</script>

<style scoped>
.k-card {
  position: relative;
  width: 320px;
  height: 400px;
  border-radius: 20px;
  overflow: hidden;
  cursor: pointer;
  flex-shrink: 0;
  transition: all 0.4s ease;
}
.k-card:not(.active) {
  transform: scale(0.85);
  opacity: 0.5;
  filter: blur(1px);
}
.k-card-bg {
  position: absolute;
  inset: 0;
  background-size: cover;
  background-position: center;
}
.k-card-bg.disease {
  background: linear-gradient(135deg, #2d1b3a, #4a2040, #6b2a4a);
}
.k-card-bg.pest {
  background: linear-gradient(135deg, #1a2a1e, #1e3a2a, #2a4a30);
}
.k-card-bg::after {
  content: '';
  position: absolute;
  inset: 0;
  background:
    radial-gradient(ellipse at 30% 30%, rgba(255,255,255,.05) 0%, transparent 60%),
    radial-gradient(ellipse at 70% 70%, rgba(255,255,255,.03) 0%, transparent 60%);
}
.k-card-overlay {
  position: absolute;
  inset: 0;
  background: rgba(0,0,0,.55);
}
.k-card-body {
  position: relative;
  z-index: 2;
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  padding: 28px 22px;
  color: #fff;
}
.k-tag {
  display: inline-block;
  padding: 4px 14px;
  border-radius: 14px;
  font-size: 12px;
  align-self: flex-start;
  margin-bottom: 12px;
}
.k-tag.disease { background: rgba(245,108,108,.3); }
.k-tag.pest { background: rgba(64,158,255,.3); }
.k-card-body h3 { font-size: 22px; font-weight: 700; margin-bottom: 8px; }
.k-card-body p {
  font-size: 13px;
  line-height: 1.6;
  opacity: .85;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.k-hint { font-size: 12px; opacity: .5; margin-top: 12px; }
</style>
