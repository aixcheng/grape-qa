<template>
  <div class="sw-page">
    <div class="back-link" @click="$router.push('/')">← 返回首页</div>
    <h2 class="page-title">🔍 智能检索流程</h2>
    <p class="page-desc">双路检索架构：知识图谱 + 向量语义，融合后由大模型生成答案</p>

    <div class="flow-area glass-card">
      <svg viewBox="0 0 900 600" class="sw-svg">
        <!-- 箭头标记 -->
        <defs>
          <marker id="arrow" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
            <polygon points="0 0, 8 3, 0 6" fill="rgba(255,255,255,.4)"/>
          </marker>
          <marker id="arrowGold" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
            <polygon points="0 0, 8 3, 0 6" fill="#d4a017"/>
          </marker>
        </defs>

        <!-- 输入 -->
        <rect x="330" y="20" width="240" height="50" rx="12" fill="rgba(114,46,209,.25)" stroke="var(--grape-purple)" stroke-width="2"/>
        <text x="450" y="50" text-anchor="middle" fill="white" font-size="15" font-weight="600">💬 用户问题</text>

        <line x1="450" y1="70" x2="450" y2="100" stroke="rgba(255,255,255,.4)" stroke-width="2" marker-end="url(#arrow)"/>

        <!-- 实体匹配 -->
        <rect x="290" y="105" width="320" height="60" rx="10" fill="rgba(212,160,23,.1)" stroke="rgba(212,160,23,.5)" stroke-width="1.5"/>
        <text x="450" y="132" text-anchor="middle" fill="#d4a017" font-size="14" font-weight="600">实体识别与匹配</text>
        <text x="450" y="152" text-anchor="middle" fill="rgba(255,255,255,.45)" font-size="11">AC 自动机多实体匹配 + BGE 向量兜底</text>

        <!-- 分叉 -->
        <line x1="450" y1="165" x2="450" y2="185" stroke="rgba(255,255,255,.4)" stroke-width="2"/>
        <line x1="200" y1="185" x2="700" y2="185" stroke="rgba(255,255,255,.4)" stroke-width="2"/>
        <line x1="200" y1="185" x2="200" y2="210" stroke="rgba(255,255,255,.4)" stroke-width="2" marker-end="url(#arrow)"/>
        <line x1="700" y1="185" x2="700" y2="210" stroke="rgba(255,255,255,.4)" stroke-width="2" marker-end="url(#arrow)"/>

        <!-- 左路：图谱检索 -->
        <rect x="70" y="215" width="260" height="90" rx="10" fill="rgba(245,108,108,.08)" stroke="rgba(245,108,108,.4)" stroke-width="1.5"/>
        <text x="200" y="242" text-anchor="middle" fill="#f56c6c" font-size="14" font-weight="600">🕸️ 知识图谱检索</text>
        <text x="200" y="262" text-anchor="middle" fill="rgba(255,255,255,.5)" font-size="11">Cypher 查询 Neo4j</text>
        <text x="200" y="280" text-anchor="middle" fill="rgba(255,255,255,.5)" font-size="11">返回结构化属性 + description 文本</text>

        <!-- 右路：向量检索 -->
        <rect x="570" y="215" width="260" height="90" rx="10" fill="rgba(64,158,255,.08)" stroke="rgba(64,158,255,.4)" stroke-width="1.5"/>
        <text x="700" y="242" text-anchor="middle" fill="#409eff" font-size="14" font-weight="600">📊 向量语义检索</text>
        <text x="700" y="262" text-anchor="middle" fill="rgba(255,255,255,.5)" font-size="11">BGE-Large-Zh 嵌入模型</text>
        <text x="700" y="280" text-anchor="middle" fill="rgba(255,255,255,.5)" font-size="11">ChromaDB Top-5 相似文本</text>

        <!-- 汇合 -->
        <line x1="200" y1="305" x2="200" y2="330" stroke="rgba(255,255,255,.4)" stroke-width="2"/>
        <line x1="700" y1="305" x2="700" y2="330" stroke="rgba(255,255,255,.4)" stroke-width="2"/>
        <line x1="200" y1="330" x2="700" y2="330" stroke="rgba(255,255,255,.4)" stroke-width="2"/>
        <line x1="450" y1="330" x2="450" y2="355" stroke="rgba(255,255,255,.4)" stroke-width="2" marker-end="url(#arrow)"/>

        <!-- 融合 -->
        <rect x="310" y="360" width="280" height="50" rx="10" fill="rgba(45,140,74,.1)" stroke="rgba(45,140,74,.5)" stroke-width="1.5"/>
        <text x="450" y="385" text-anchor="middle" fill="#2d8c4a" font-size="14" font-weight="600">🔗 上下文融合</text>
        <text x="450" y="400" text-anchor="middle" fill="rgba(255,255,255,.45)" font-size="11">图谱结果 + 向量文本 → 统一上下文</text>

        <line x1="450" y1="410" x2="450" y2="440" stroke="rgba(255,255,255,.4)" stroke-width="2" marker-end="url(#arrow)"/>

        <!-- LLM -->
        <rect x="300" y="445" width="300" height="60" rx="10" fill="rgba(114,46,209,.2)" stroke="var(--grape-purple)" stroke-width="2"/>
        <text x="450" y="472" text-anchor="middle" fill="white" font-size="14" font-weight="600">🤖 大模型生成</text>
        <text x="450" y="492" text-anchor="middle" fill="rgba(255,255,255,.5)" font-size="11">DeepSeek-Chat (DeepSeek API)</text>

        <line x1="450" y1="505" x2="450" y2="535" stroke="#d4a017" stroke-width="2.5" marker-end="url(#arrowGold)"/>

        <!-- 输出 -->
        <rect x="345" y="540" width="210" height="45" rx="12" fill="rgba(212,160,23,.15)" stroke="#d4a017" stroke-width="2"/>
        <text x="450" y="568" text-anchor="middle" fill="#d4a017" font-size="15" font-weight="600">✨ 生成答案</text>

        <!-- 左侧标注 -->
        <text x="35" y="265" fill="rgba(255,255,255,.3)" font-size="10" transform="rotate(-90 35 265)">路 一</text>
        <text x="35" y="640" fill="rgba(255,255,255,.3)" font-size="10" transform="rotate(-90 35 640)">路 二</text>
      </svg>
    </div>

    <div class="tech-stack glass-card">
      <h3>技术栈</h3>
      <div class="tech-grid">
        <div class="tech"><span class="t-name">Neo4j</span><span class="t-role">知识图谱存储与查询</span></div>
        <div class="tech"><span class="t-name">ChromaDB</span><span class="t-role">向量数据库</span></div>
        <div class="tech"><span class="t-name">BGE-Large-Zh</span><span class="t-role">中文文本嵌入模型</span></div>
        <div class="tech"><span class="t-name">AC 自动机</span><span class="t-role">多模式实体匹配</span></div>
        <div class="tech"><span class="t-name">DeepSeek-Chat</span><span class="t-role">大语言模型</span></div>
        <div class="tech"><span class="t-name">Flask + Vue 3</span><span class="t-role">前后端框架</span></div>
      </div>
    </div>
  </div>
</template>

<script>
export default { name: 'SearchWorkflow' }
</script>

<style scoped>
.sw-page { max-width: 960px; margin: 0 auto; }
.back-link { color: var(--grape-purple); cursor: pointer; margin-bottom: 16px; font-size: 14px; }
.page-title { font-size: 22px; color: #fff; margin-bottom: 4px; }
.page-desc { color: var(--text-secondary); margin-bottom: 24px; font-size: 14px; }
.flow-area { padding: 24px; margin-bottom: 24px; overflow-x: auto; }
.sw-svg { width: 100%; max-width: 900px; display: block; margin: 0 auto; }
.tech-stack { padding: 28px 32px; }
.tech-stack h3 { color: #fff; font-size: 16px; margin-bottom: 16px; }
.tech-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.tech { display: flex; justify-content: space-between; padding: 10px 14px; background: rgba(255,255,255,.04); border-radius: 8px; }
.t-name { color: var(--gold); font-weight: 600; font-size: 13px; }
.t-role { color: var(--text-secondary); font-size: 12px; }
</style>
