<template>
  <div class="kg-page">
    <div class="back-link" @click="$router.push('/')">← 返回首页</div>
    <h2 class="page-title">🧠 知识图谱可视化</h2>
    <p class="page-desc">基于 Neo4j 的葡萄病虫害知识图谱 — 拖拽/缩放探索，点击节点查看关联</p>

    <div v-if="error" class="error-bar">
      <el-alert type="error" :title="error" show-icon :closable="false" />
    </div>

    <div class="graph-layout">
      <!-- 左侧筛选面板 -->
      <div class="filter-panel glass-card">
        <h3>实体筛选</h3>
        <div v-for="g in groups" :key="g.key" class="filter-row">
          <el-checkbox v-model="g.visible" @change="toggleGroup(g)" :label="g.key">
            <span :class="['dot', g.key]"></span>
            <span class="g-name">{{ g.label }}</span>
            <span class="g-count">{{ g.count }}</span>
          </el-checkbox>
        </div>
        <div class="filter-actions">
          <el-button size="small" text @click="selectAll">全选</el-button>
          <el-button size="small" text @click="deselectAll">反选</el-button>
        </div>
      </div>

      <!-- 图谱画布 -->
      <div class="graph-area glass-card">
        <div class="graph-toolbar">
          <div class="mode-switcher">
            <el-radio-group v-model="viewMode" size="small" @change="switchMode">
              <el-radio-button value="force">力导向全览</el-radio-button>
              <el-radio-button value="core">核心实体</el-radio-button>
            </el-radio-group>
          </div>
          <div class="search-box">
            <el-input
              v-model="searchQuery"
              size="small"
              placeholder="搜索节点名称..."
              clearable
              @input="doSearch"
              @clear="clearSearch"
              style="width: 200px;"
            >
              <template #prefix>🔍</template>
            </el-input>
            <span v-if="searchQuery" class="search-count">{{ searchMatchCount }} 个匹配</span>
          </div>
          <el-button size="small" @click="fitGraph">重置视图</el-button>
          <span class="stats-inline">{{ statsText }}</span>
        </div>
        <div v-if="loading" class="loading-state">
          <el-icon class="is-loading" :size="32"><Loading /></el-icon>
          <p>正在加载知识图谱...</p>
        </div>
        <div ref="cyContainer" class="cy-container"></div>
      </div>
    </div>

    <!-- 节点详情弹窗 -->
    <div v-if="selectedNode" class="node-tooltip glass-card" :style="tooltipStyle">
      <div class="t-header">
        <span :class="['t-dot', selectedNode.group]"></span>
        <strong>{{ selectedNode.label }}</strong>
        <span class="t-type">{{ selectedNode.group }}</span>
      </div>
      <div class="t-info">关联节点：{{ selectedNode.degree }} 个</div>
      <div class="t-info">来源：知识图谱 (Neo4j)</div>
    </div>
  </div>
</template>

<script>
import cytoscape from 'cytoscape'
import coseBilkent from 'cytoscape-cose-bilkent'
import axios from 'axios'

cytoscape.use(coseBilkent)

const GROUP_COLORS = {
  Disease: '#f56c6c',
  Pest: '#409eff',
  Alias: '#e6a23c',
  Symptom: '#ff9800',
  Part: '#67c23a',
  Rule: '#00bcd4',
  Method: '#9b59ff',
  Drug: '#17becf',
  Treatment: '#ff69b4',
  Pathogen: '#c62828',
  Characteristic: '#64b5f6',
  Condition: '#fdd835',
  Period: '#8bc34a',
  Vector: '#78909c',
  Other: '#909399',
}

const GROUP_LABELS = {
  Disease: '病害',
  Pest: '虫害',
  Alias: '别名',
  Symptom: '症状',
  Part: '为害部位',
  Rule: '发病规律',
  Method: '防治方法',
  Drug: '防治药剂',
  Treatment: '治疗方案',
  Pathogen: '病原',
  Characteristic: '形态特征',
  Condition: '环境条件',
  Period: '发生时期',
  Vector: '传播媒介',
  Other: '其他',
}

export default {
  name: 'KnowledgeGraph',
  data() {
    return {
      loading: true,
      error: '',
      cy: null,
      graphData: { nodes: [], edges: [] },
      groups: [],
      selectedNode: null,
      tooltipStyle: {},
      viewMode: 'force',
      searchQuery: '',
      searchMatchCount: 0,
    }
  },
  computed: {
    statsText() {
      const d = this.graphData
      return `${d.nodes.length} 个节点 · ${d.edges.length} 条关系`
    },
  },
  async mounted() {
    await this.fetchGraph()
  },
  beforeUnmount() {
    if (this.cy) {
      this.cy.destroy()
      this.cy = null
    }
  },
  methods: {
    async fetchGraph() {
      this.loading = true
      this.error = ''
      try {
        const res = await axios.get('http://localhost:5000/api/graph')
        this.graphData = res.data
        const counts = {}
        res.data.nodes.forEach(n => {
          counts[n.group] = (counts[n.group] || 0) + 1
        })
        this.groups = Object.keys(GROUP_COLORS).map(key => ({
          key,
          label: GROUP_LABELS[key] || key,
          color: GROUP_COLORS[key],
          count: counts[key] || 0,
          visible: true,
        }))
        this.$nextTick(() => this.initCytoscape())
      } catch (e) {
        this.error = '加载图谱数据失败，请确认 Neo4j 和后端服务已启动'
      } finally {
        this.loading = false
      }
    },
    initCytoscape() {
      if (this.cy) {
        this.cy.destroy()
        this.cy = null
      }

      const { nodes, edges } = this.graphData

      const elements = []
      nodes.forEach(n => {
        elements.push({
          data: { id: n.id, label: n.label, group: n.group },
        })
      })
      edges.forEach(e => {
        elements.push({
          data: {
            id: e.id,
            source: e.source,
            target: e.target,
            label: e.label,
          },
        })
      })

      this.cy = cytoscape({
        container: this.$refs.cyContainer,
        elements,
        style: this.buildStyle(),
        layout: this.getLayoutConfig(),
        wheelSensitivity: 0.5,
        minZoom: 0.08,
        maxZoom: 4,
        motionBlur: true,
        hideEdgesOnViewport: true,
        pixelRatio: 'auto',
        boxSelectionEnabled: false,
        autoungrabify: false,
        autounselectify: false,
      })

      this.bindEvents()
      setTimeout(() => this.cy.fit(this.cy.elements(), 30), 800)
    },
    buildStyle() {
      const nodeStyles = []
      Object.entries(GROUP_COLORS).forEach(([group, color]) => {
        nodeStyles.push({
          selector: `node[group="${group}"]`,
          style: {
            'background-color': color,
            'label': 'data(label)',
            'color': '#fff',
            'font-size': '11px',
            'font-family': '"PingFang SC","Microsoft YaHei",sans-serif',
            'text-valign': 'bottom',
            'text-halign': 'center',
            'text-margin-y': 6,
            'text-outline-color': 'rgba(0,0,0,0.5)',
            'text-outline-width': 2,
            'shape': group === 'Alias' ? 'diamond' : 'ellipse',
            'width': group === 'Disease' || group === 'Pest' ? 40 : 24,
            'height': group === 'Disease' || group === 'Pest' ? 40 : 24,
            'border-width': 2,
            'border-color': color,
            'border-opacity': 0.6,
          },
        })
      })

      return [
        ...nodeStyles,
        {
          selector: 'node:selected',
          style: {
            'border-width': 3,
            'border-color': '#fff',
            'border-opacity': 1,
            'shadow-blur': 12,
            'shadow-color': '#fff',
            'shadow-opacity': 0.4,
          },
        },
        {
          selector: 'node.highlight',
          style: {
            'border-width': 3,
            'border-color': '#d4a017',
            'border-opacity': 1,
          },
        },
        {
          selector: 'node.dimmed',
          style: { 'opacity': 0.08 },
        },
        {
          selector: 'edge',
          style: {
            'width': 0.8,
            'line-color': 'rgba(255,255,255,0.12)',
            'target-arrow-color': 'rgba(255,255,255,0.12)',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
          },
        },
        {
          selector: 'edge.highlight',
          style: {
            'width': 2.5,
            'line-color': 'rgba(212,160,23,0.6)',
            'target-arrow-color': 'rgba(212,160,23,0.6)',
            'label': 'data(label)',
            'color': '#d4a017',
            'font-size': '10px',
            'text-rotation': 'autorotate',
          },
        },
        {
          selector: 'edge.dimmed',
          style: { 'opacity': 0.02 },
        },
      ]
    },
    getLayoutConfig() {
      return { name: 'cose-bilkent', animate: true, idealEdgeLength: 160, nodeRepulsion: 80000, gravity: 0.1, numIter: 3000 }
    },
    switchMode(val) {
      this.clearHighlight()
      this.selectedNode = null
      this.searchQuery = ''
      this.searchMatchCount = 0

      this.cy.elements().style('display', 'element')
      this.groups.forEach(g => { g.visible = true })

      if (val === 'core') {
        this.applyCore()
      } else {
        this.cy.layout(this.getLayoutConfig()).run()
      }
    },
    applyCore() {
      const coreTypes = ['Disease', 'Pest', 'Alias']
      this.groups.forEach(g => {
        if (!coreTypes.includes(g.key)) {
          g.visible = false
          this.cy.nodes(`[group="${g.key}"]`).style('display', 'none')
        }
      })
      this.cy.edges().style('display', 'element')
      this.cy.edges().forEach(e => {
        const s = e.source().data('group')
        const t = e.target().data('group')
        if (!coreTypes.includes(s) || !coreTypes.includes(t)) {
          e.style('display', 'none')
        }
      })
      this.cy.layout(this.getLayoutConfig()).run()
    },
    doSearch() {
      const q = this.searchQuery.trim().toLowerCase()
      if (!q) {
        this.clearSearch()
        return
      }
      this.clearHighlight()
      const matched = this.cy.nodes().filter(n =>
        n.data('label').toLowerCase().includes(q)
      )
      const neighborhood = matched.closedNeighborhood()
      this.cy.elements().style('display', 'none')
      matched.style('display', 'element')
      neighborhood.style('display', 'element')
      this.searchMatchCount = matched.length
    },
    clearSearch() {
      this.searchQuery = ''
      this.searchMatchCount = 0
      this.cy.elements().style('display', 'element')
    },
    bindEvents() {
      this.cy.on('tap', (evt) => {
        const node = evt.target
        if (node === this.cy) {
          this.clearHighlight()
          this.selectedNode = null
          return
        }
        if (node.isNode()) {
          this.highlightNeighbors(node)
          const pos = node.renderedPosition()
          const degree = node.neighborhood().length
          this.selectedNode = {
            label: node.data('label'),
            group: node.data('group'),
            degree,
          }
          this.tooltipStyle = {
            left: `${pos.x + 30}px`,
            top: `${pos.y - 20}px`,
          }
        }
      })

      this.cy.on('drag pan', () => {
        this.selectedNode = null
      })
    },
    highlightNeighbors(node) {
      this.cy.elements().stop(true, false)
      const neighborhood = node.closedNeighborhood()
      this.cy.elements().removeClass('highlight dimmed')
      this.cy.elements().difference(neighborhood).animate({
        style: { 'opacity': 0.08 },
        duration: 200,
      })
      neighborhood.animate({
        style: { 'opacity': 1 },
        duration: 200,
      })
      neighborhood.addClass('highlight')
    },
    clearHighlight() {
      this.cy.elements().stop(true, false)
      this.cy.elements().removeClass('highlight dimmed')
      this.cy.elements().animate({
        style: { 'opacity': 1 },
        duration: 200,
      })
    },
    toggleGroup(g) {
      const nodes = this.cy.nodes(`[group="${g.key}"]`)
      if (g.visible) {
        nodes.style('display', 'element')
        nodes.connectedEdges().style('display', 'element')
      } else {
        nodes.style('display', 'none')
        nodes.connectedEdges().style('display', 'none')
      }
    },
    selectAll() {
      this.groups.forEach(g => { g.visible = true })
      this.cy.elements().style('display', 'element')
    },
    deselectAll() {
      this.groups.forEach(g => { g.visible = false })
      this.cy.elements().style('display', 'none')
    },
    fitGraph() {
      if (this.cy) {
        this.cy.fit(this.cy.elements(), 30)
      }
    },
  },
}
</script>

<style scoped>
.kg-page { max-width: 1300px; margin: 0 auto; }
.back-link { color: var(--grape-purple); cursor: pointer; margin-bottom: 12px; font-size: 14px; display: inline-block; }
.back-link:hover { color: #9b59ff; }
.page-title { font-size: 22px; color: #fff; margin-bottom: 4px; }
.page-desc { color: var(--text-secondary); margin-bottom: 20px; font-size: 14px; }

.error-bar { margin-bottom: 16px; }

.graph-layout {
  display: flex;
  gap: 16px;
  margin-bottom: 16px;
}

.filter-panel {
  width: 170px;
  flex-shrink: 0;
  padding: 16px;
}
.filter-panel h3 { color: #fff; font-size: 14px; margin-bottom: 12px; }
.filter-row { margin-bottom: 4px; }
.filter-row .dot {
  display: inline-block;
  width: 10px; height: 10px;
  border-radius: 50%;
  margin-right: 6px;
  vertical-align: middle;
}
.dot.Disease { background: #f56c6c; }
.dot.Pest { background: #409eff; }
.dot.Alias { background: #e6a23c; }
.dot.Symptom { background: #ff9800; }
.dot.Part { background: #67c23a; }
.dot.Rule { background: #00bcd4; }
.dot.Method { background: #9b59ff; }
.dot.Drug { background: #17becf; }
.dot.Treatment { background: #ff69b4; }
.dot.Pathogen { background: #c62828; }
.dot.Characteristic { background: #64b5f6; }
.dot.Condition { background: #fdd835; }
.dot.Period { background: #8bc34a; }
.dot.Vector { background: #78909c; }
.dot.Other { background: #909399; }
.g-name { color: #ccc; font-size: 12px; vertical-align: middle; }
.g-count { color: #666; font-size: 11px; margin-left: 4px; }
.filter-actions { margin-top: 12px; display: flex; gap: 4px; }

.graph-area {
  flex: 1;
  padding: 0;
  min-height: 550px;
  position: relative;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.graph-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: rgba(255,255,255,.03);
  border-bottom: 1px solid rgba(255,255,255,.06);
  flex-wrap: wrap;
  flex-shrink: 0;
}
.mode-switcher { display: flex; align-items: center; gap: 8px; }
.search-box { display: flex; align-items: center; gap: 8px; }
.search-count { color: var(--gold); font-size: 12px; white-space: nowrap; }
.stats-inline { color: var(--text-secondary); font-size: 13px; margin-left: auto; }
.cy-container {
  width: 100%;
  height: 850px;
  flex: 1;
}
.loading-state {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  z-index: 5;
}
.loading-state p { margin-top: 12px; font-size: 14px; }

.node-tooltip {
  position: fixed;
  z-index: 1000;
  padding: 12px 16px;
  pointer-events: none;
}
.t-dot {
  display: inline-block;
  width: 10px; height: 10px;
  border-radius: 50%;
  margin-right: 6px;
  vertical-align: middle;
}
.t-header strong { color: #fff; font-size: 14px; }
.t-type { color: var(--text-secondary); font-size: 11px; margin-left: 8px; }
.t-info { color: var(--text-secondary); font-size: 12px; margin-top: 4px; }
</style>
