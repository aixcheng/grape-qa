"""
消融实验脚本 — 独立运行，不修改 app.py
"""
import os
import re
import json
import time
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "docs", "superpowers")

# 从 app 导入底层组件
from app import (
    match_entities, ENTITY_LIST, REVERSE_MAP,
    graph, embedding_model, collection,
)
from app import answer_question_with_sources as full_answer
from openai import OpenAI


def _get_client():
    return OpenAI(api_key=os.getenv("DEEPSEEK_API_KEY"), base_url="https://api.deepseek.com")

# 测试集加载
from full_eval import build_merged_testset


def call_llm_direct(question):
    """F: 纯 LLM，无任何检索"""
    prompt = f"""你是葡萄病虫害防治专家。请回答以下问题。

问题：{question}

如果没有相关知识，请如实说明。"""
    start = time.time()
    resp = _get_client().chat.completions.create(
        model='deepseek-chat',
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1024,
        temperature=0.7,
    )
    elapsed = round((time.time() - start) * 1000)
    return resp.choices[0].message.content, [], elapsed
    return "API error", [], elapsed


def ablation_kg_only(question):
    """C: 仅 KG，无向量检索"""
    # 复用现有匹配 + KG 查询逻辑，去掉向量检索
    matched = match_entities(question)
    kg_answer_parts = []
    kg_sources = []
    queried = set()

    for entity_name, entity_type, score in matched:
        resolved_name, resolved_type = entity_name, entity_type
        if entity_type == 'Alias':
            alias_res = graph.run(
                "MATCH (a:Alias {name: $name})-[r:ALIAS_OF]->(e) RETURN e.name AS n, labels(e) AS l",
                name=entity_name
            ).data()
            if alias_res:
                resolved_name = alias_res['n']
                resolved_type = 'Disease' if 'Disease' in alias_res[0]['l'] else 'Pest'
            else:
                continue

        if entity_type in ('Symptom', 'Part'):
            revs = REVERSE_MAP.get(entity_name, [])
            for rev_name in revs[:2]:
                if rev_name in queried: continue
                queried.add(rev_name)
                for n, t in ENTITY_LIST:
                    if n == rev_name and t in ('Disease', 'Pest'):
                        rel_data = graph.run(
                            f"MATCH (e:{t} {{name: $name}})-[r]->(n) RETURN type(r) AS rel, n.name AS related",
                            name=rev_name
                        ).data()
                        if rel_data:
                            rel_texts = [f"{r['rel']} {r['related']}" for r in rel_data]
                            kg_answer_parts.append(f"【{rev_name}】{'，'.join(rel_texts)}")
                            for r in rel_data:
                                kg_sources.append(f"KG: {r['rel']} -> {r['related']}")
                break
            continue

        if resolved_type in ('Disease', 'Pest') and resolved_name not in queried:
            queried.add(resolved_name)
            rel_data = graph.run(
                f"MATCH (e:{resolved_type} {{name: $name}})-[r]->(n) RETURN type(r) AS rel, n.name AS related",
                name=resolved_name
            ).data()
            if rel_data:
                rel_texts = [f"{r['rel']} {r['related']}" for r in rel_data]
                kg_answer_parts.append(f"【{resolved_name}】{'，'.join(rel_texts)}")
                for r in rel_data:
                    kg_sources.append(f"KG: {r['rel']} -> {r['related']}")

    context = "\n".join(kg_answer_parts) or "No KG knowledge found."

    prompt = f"""你是葡萄病虫害防治专家。请基于以下知识回答。

【知识】
{context}

【问题】{question}

【要求】列出全部相关知识，引用具体数值。不知道的说无法回答。"""

    start = time.time()
    resp = _get_client().chat.completions.create(
        model='deepseek-chat',
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1024,
        temperature=0.7,
    )
    elapsed = round((time.time() - start) * 1000)
    return resp.choices[0].message.content, kg_sources, elapsed
    return "API error", kg_sources, elapsed


def ablation_vector_only(question):
    """B: 仅向量检索，无 KG"""
    query_vector = embedding_model.encode(question).tolist()
    results = collection.query(query_embeddings=[query_vector], n_results=3)
    texts = results['documents'][0] if results['documents'] else []
    context = "\n".join([f"【文本】{t}" for t in texts]) or "No text found."
    sources = []
    metadatas = results['metadatas'][0] if results['metadatas'] else []
    for meta in metadatas:
        sources.append(f"Vector: {meta.get('source', 'unknown')}")

    prompt = f"""你是葡萄病虫害防治专家。请基于以下知识回答。

【知识】
{context}

【问题】{question}

【要求】列出全部相关知识，引用具体数值。不知道的说无法回答。"""

    start = time.time()
    resp = _get_client().chat.completions.create(
        model='deepseek-chat',
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1024,
        temperature=0.7,
    )
    elapsed = round((time.time() - start) * 1000)
    return resp.choices[0].message.content, sources, elapsed
    return "API error", sources, elapsed


def ablation_no_reverse(question):
    """D: 移除反向诊断 — 过滤掉 Symptom/Part 实体匹配"""
    matched = match_entities(question)
    filtered = [(n, t, s) for n, t, s in matched if t not in ('Symptom', 'Part')]
    return run_with_matches(question, filtered, use_vector=True)


def ablation_single_entity(question):
    """E: 单实体正则匹配"""
    matched = []
    if ENTITY_LIST:
        for name, typ in ENTITY_LIST:
            if typ in ('Disease', 'Pest', 'Alias') and name in question:
                matched.append((name, typ, 1.0))
                break

    return run_with_matches(question, matched, use_vector=True)


def run_with_matches(question, matched, use_vector=True):
    """用指定的 matched 列表运行 KG + LLM"""
    kg_answer_parts = []
    kg_sources = []
    queried = set()

    for entity_name, entity_type, score in matched:
        resolved_name, resolved_type = entity_name, entity_type
        if entity_type == 'Alias':
            alias_res = graph.run(
                "MATCH (a:Alias {name: $name})-[r:ALIAS_OF]->(e) RETURN e.name AS n, labels(e) AS l",
                name=entity_name
            ).data()
            if alias_res:
                resolved_name = alias_res[0]['n']
                resolved_type = 'Disease' if 'Disease' in alias_res[0]['l'] else 'Pest'
            else:
                continue

        if entity_type in ('Symptom', 'Part'):
            revs = REVERSE_MAP.get(entity_name, [])
            for rev_name in revs[:2]:
                if rev_name in queried: continue
                queried.add(rev_name)
                for n, t in ENTITY_LIST:
                    if n == rev_name and t in ('Disease', 'Pest'):
                        rel_data = graph.run(
                            f"MATCH (e:{t} {{name: $name}})-[r]->(n) RETURN type(r) AS rel, n.name AS related",
                            name=rev_name
                        ).data()
                        if rel_data:
                            rel_texts = [f"{r['rel']} {r['related']}" for r in rel_data]
                            kg_answer_parts.append(f"【{rev_name}】{'，'.join(rel_texts)}")
                            for r in rel_data:
                                kg_sources.append(f"KG: {r['rel']} -> {r['related']}")
                break
            continue

        if resolved_type in ('Disease', 'Pest') and resolved_name not in queried:
            queried.add(resolved_name)
            rel_data = graph.run(
                f"MATCH (e:{resolved_type} {{name: $name}})-[r]->(n) RETURN type(r) AS rel, n.name AS related",
                name=resolved_name
            ).data()
            if rel_data:
                rel_texts = [f"{r['rel']} {r['related']}" for r in rel_data]
                kg_answer_parts.append(f"【{resolved_name}】{'，'.join(rel_texts)}")
                for r in rel_data:
                    kg_sources.append(f"KG: {r['rel']} -> {r['related']}")

    context_parts = kg_answer_parts[:]
    if use_vector:
        query_vector = embedding_model.encode(question).tolist()
        results = collection.query(query_embeddings=[query_vector], n_results=3)
        texts = results['documents'][0] if results['documents'] else []
        for t in texts:
            context_parts.append(f"【文本】{t}")
        metadatas = results['metadatas'][0] if results['metadatas'] else []
        for meta in metadatas:
            kg_sources.append(f"Vector: {meta.get('source', 'unknown')}")

    context = "\n".join(context_parts) or "No knowledge found."

    prompt = f"""你是葡萄病虫害防治专家。请基于以下知识回答。

【知识】
{context}

【问题】{question}

【要求】列出全部相关知识，引用具体数值。不知道的说无法回答。"""

    start = time.time()
    resp = _get_client().chat.completions.create(
        model='deepseek-chat',
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1024,
        temperature=0.7,
    )
    elapsed = round((time.time() - start) * 1000)
    return resp.choices[0].message.content, kg_sources, elapsed
    return "API error", kg_sources, elapsed


def call_ablation_via_api(question, skip_reverse=False):
    """通过 /api/chat 调用（用于 A 和 D）"""
    import requests
    start = time.time()
    try:
        resp = requests.post(
            "http://localhost:5000/api/chat",
            json={"question": question, "history": []},
            timeout=60,
        )
        elapsed = round((time.time() - start) * 1000)
        data = resp.json()
        return data.get("answer", ""), data.get("sources", []), elapsed
    except Exception as e:
        return f"Error: {e}", [], 0


# ==================== 评判 ====================

def judge(question, keywords, answer, sources):
    """LLM 评判"""
    if not os.getenv('DEEPSEEK_API_KEY'):
        return "SKIP"
    kg_count = len([s for s in sources if "KG:" in s or "图谱" in s])
    prompt = f"""评估答案质量。问题：{question}
期望关键词：{', '.join(keywords[:6])}
回答：{answer[:500]}

只回复 PASS / PARTIAL / FAIL。PASS=核心事实正确，PARTIAL=部分正确但缺关键信息，FAIL=错误或拒答。"""

    try:
        resp = _get_client().chat.completions.create(
            model='deepseek-chat',
            messages=[{"role": "user", "content": prompt}],
            max_tokens=32,
            temperature=0.1,
        )
        raw = resp.choices[0].message.content.strip().upper()
        if "PASS" in raw: return "PASS"
        if "PARTIAL" in raw: return "PARTIAL"
        return "FAIL"
    except:
        pass
    return "SKIP"


# ==================== 主流程 ====================

EXPERIMENTS = {
    "A_full":       ("完整系统",     lambda q: call_ablation_via_api(q)),
    "B_vector_only":("仅向量检索",   ablation_vector_only),
    "C_kg_only":    ("仅KG检索",     ablation_kg_only),
    "D_no_reverse": ("移除反向诊断", ablation_no_reverse),
    "E_single_ent": ("单实体匹配",   ablation_single_entity),
    "F_llm_only":   ("纯LLM",        call_llm_direct),
}


def main():
    print("=" * 60)
    print("  消融实验")
    print("=" * 60)

    testset = build_merged_testset()
    print(f"测试集: {len(testset)} 题\n")

    all_results = {}

    for exp_key, (exp_name, exp_func) in EXPERIMENTS.items():
        print(f"\n{'='*60}")
        print(f"  {exp_key}: {exp_name}")
        print(f"{'='*60}")

        results = []
        stats = {"total": 0, "pass": 0, "partial": 0, "fail": 0, "elapsed": []}

        for i, q in enumerate(testset):
            qid = q["id"]
            print(f"  [{i+1}/{len(testset)}] {qid} {q['question'][:40]}...", end=" ")

            answer, sources, elapsed = exp_func(q["question"])
            verdict = judge(q["question"], q["expected_keywords"], answer, sources)

            stats["total"] += 1
            stats[verdict.lower()] = stats.get(verdict.lower(), 0) + 1
            stats["elapsed"].append(elapsed)

            print(f"{verdict} ({elapsed}ms)")

            results.append({
                **q,
                "answer": answer[:300],
                "verdict": verdict,
                "elapsed_ms": elapsed,
                "source_count": len(sources),
            })

        # 按类型统计
        type_stats = {}
        for r in results:
            t = r["type"]
            if t not in type_stats:
                type_stats[t] = {"total": 0, "pass": 0, "partial": 0, "fail": 0}
            type_stats[t]["total"] += 1
            type_stats[t][r["verdict"].lower()] = type_stats[t].get(r["verdict"].lower(), 0) + 1

        overall = (stats["pass"] + stats["partial"] * 0.5) / stats["total"] * 100 if stats["total"] else 0
        avg_time = sum(stats["elapsed"]) / len(stats["elapsed"]) if stats["elapsed"] else 0

        print(f"\n  总体: {overall:.1f}%  平均耗时: {avg_time:.0f}ms")
        for t in ["single_forward", "single_reverse", "multi_hop", "numerical", "rejection"]:
            ts = type_stats.get(t)
            if ts:
                r = (ts["pass"] + ts["partial"] * 0.5) / ts["total"] * 100
                print(f"    {t}: {r:.1f}%")

        all_results[exp_key] = {
            "name": exp_name,
            "overall": round(overall, 1),
            "avg_time_ms": round(avg_time),
            "type_breakdown": {t: round((ts["pass"] + ts["partial"] * 0.5) / ts["total"] * 100, 1)
                               for t, ts in type_stats.items()},
            "results": results,
        }

    # 汇总对比表
    print("\n" + "=" * 80)
    print("  消融实验汇总")
    print("=" * 80)
    header = f"{'实验':16s} {'总体':>6s} {'正向':>6s} {'反向':>6s} {'多跳':>6s} {'数值':>6s} {'耗时':>8s}"
    print(header)
    print("-" * 80)
    for exp_key, data in all_results.items():
        tb = data["type_breakdown"]
        print(f"{data['name']:16s} {data['overall']:5.1f}% {tb.get('single_forward',0):5.1f}% "
              f"{tb.get('single_reverse',0):5.1f}% {tb.get('multi_hop',0):5.1f}% "
              f"{tb.get('numerical',0):5.1f}% {data['avg_time_ms']:7.0f}ms")

    # 保存
    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    path = os.path.join(OUTPUT_DIR, f"ablation_{ts}.json")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"\n报告: {path}")


if __name__ == "__main__":
    main()
