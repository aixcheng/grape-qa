# Grape QA — GraphRAG葡萄病虫害问答系统

基于HybridRAG的葡萄病虫害知识问答系统。Flask后端 + Neo4j KG + ChromaDB向量 + DeepSeek LLM + Vue前端。

## 项目约定

- **Python venv**: `venv/`，启动用 `venv/Scripts/python.exe`
- **Neo4j**: 必须先启动，`neo4j://127.0.0.1:7687`，密码通过环境变量 `NEO4J_PASSWORD` 设置
- **LLM**: DeepSeek-chat，需环境变量 `DEEPSEEK_API_KEY`
- **论文终稿**: `毕业论文/大连理工大学本科毕业论文终稿.docx`，任何内容修改必须以系统实际代码为准
- **不要无中生有**: 论文全部数据来自系统真实测试，禁止编造

## 关键文件

| 文件 | 用途 |
|------|------|
| `app.py` | 主后端，含 `match_entities`, `answer_question_with_sources`, Flask路由 |
| `bridge_graph.py` | 空白节点嫁接算法 |
| `full_eval.py` | 全维度评测 |
| `ablation.py` | 消融实验 |
| `testsets/final_testset.json` | 93题标准测试集 |
| `knowledge.py` | 知识百科解析 |
| `auth.py` / `db.py` | JWT认证 / SQLite数据库 |

## 启动命令

```
# Neo4j 先启动
venv/Scripts/python.exe app.py     # 后端 :5000
cd frontend && npm run dev         # 前端
venv/Scripts/python.exe full_eval.py   # 评测
```

## 核心算法

1. AC自动机精确实体匹配 + BGE-large-zh-v1.5 语义回退
2. 反向诊断: Symptom/Part → REVERSE_MAP → Disease/Pest 候选评分
3. 双路检索: Cypher图查询 + ChromaDB向量 → 融合 → DeepSeek生成
