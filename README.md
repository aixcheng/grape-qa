# Grape QA — 基于 GraphRAG 的葡萄病虫害智能问答系统

基于 HybridRAG（知识图谱 + 向量检索）的葡萄病虫害知识问答系统。

## 技术栈

- **RAG 架构**: HybridRAG 双路检索 — Neo4j 知识图谱 Cypher 图查询 + ChromaDB BGE-large 向量语义检索
- **实体匹配**: 自研 AC 自动机前缀贪心匹配 + BGE 余弦相似度兜底，匹配率 100%
- **大模型**: DeepSeek API，LLM-as-Judge 评估体系
- **后端**: Python Flask + JWT 鉴权 + SQLite
- **前端**: Vue 3（Composition API + Vite）+ Element Plus + Cytoscape.js 图可视化
- **评估**: 93 题五维度测试集，总体准确率 82.8%，拒答准确率 95%，6 组消融实验

## 项目结构

```
├── app.py               # Flask 主后端（实体匹配、双路检索、问答生成）
├── bridge_graph.py      # 知识图谱空白节点嫁接算法
├── full_eval.py         # 全维度评测
├── ablation.py          # 消融实验
├── auth.py / db.py      # JWT 认证 / SQLite 数据库
├── knowledge.py         # 知识百科解析
├── testsets/            # 93 题标准测试集
├── frontend/            # Vue 3 前端
└── data/texts/          # 原始知识文本
```

## 核心算法

1. **AC 自动机实体匹配**: 最长前缀贪心 + BGE 语义相似度兜底（阈值 0.6）
2. **反向诊断**: Symptom/Part → REVERSE_MAP → Disease/Pest 候选评分
3. **双路检索融合**: Cypher 图查询（关系推理）+ ChromaDB 向量（语义匹配）→ DeepSeek 生成

## 启动

```bash
# 1. 启动 Neo4j
# 2. 后端
venv/Scripts/python.exe app.py    # :5000
# 3. 前端
cd frontend && npm run dev
```

## 作者

肖杰成 (aixcheng) — 独立完成 · 毕业论文课题
