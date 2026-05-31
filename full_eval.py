"""
全维度评价引擎：问答准确率 + 检索性能 + 答案质量
"""
import os
import re
import json
import time
import sys
import glob
import csv
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
API_BASE = "http://localhost:5000"
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "docs", "superpowers")

# ========================= 测试集构建 =========================

def load_csv_testset(path):
    """加载 CSV 测试集"""
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    questions = []
    for row in rows:
        qtype = row.get("case_type", "")
        # 分类
        if qtype in ("symptom",):
            cat = "single_forward"
        elif qtype in ("method",):
            cat = "single_forward"
        elif qtype in ("treatment_dosage",):
            cat = "numerical"
        elif "reverse" in qtype or "diagnosis" in qtype:
            cat = "single_reverse"
        elif "compare" in qtype or "multi" in qtype:
            cat = "multi_hop"
        else:
            cat = "single_forward"

        keywords = [k.strip() for k in row.get("expected_keywords", "").split("|") if k.strip()]
        questions.append({
            "id": row["id"],
            "question": row["question"],
            "type": cat,
            "expected_keywords": keywords,
            "min_keyword_hits": int(row.get("min_keyword_hits") or 1),
            "expected_entity": row.get("expected_entity", ""),
            "source": "csv",
        })
    return questions


def load_md_testset(path):
    """加载 Markdown 测试集"""
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    blocks = re.split(r"\n(?=### Q\d+)", content)
    questions = []
    for block in blocks:
        if not block.startswith("### Q"):
            continue
        m = re.match(r"### (Q\d+)\.\s*(.+?)(?:\n|$)", block)
        if not m:
            continue
        qid = m.group(1).strip()
        text = m.group(2).strip()

        type_m = re.search(r"\*\*类型\*\*[：:]\s*(.+?)(?:\n|$)", block)
        qtype = type_m.group(1).strip() if type_m else ""
        exp_m = re.search(r"\*\*预期答案\*\*[：:]\s*(.+?)(?=\n- \*\*|\n\*\*检索|\n---|\n###|\Z)", block, re.DOTALL)
        expected = exp_m.group(1).strip() if exp_m else ""

        if "单跳正向" in qtype:
            cat = "single_forward"
        elif "单跳反向" in qtype:
            cat = "single_reverse"
        elif "多跳" in qtype:
            cat = "multi_hop"
        elif "混合" in qtype:
            cat = "multi_hop"
        elif "边界" in qtype or "对比" in qtype or "聚合" in qtype:
            cat = "rejection"

        keywords = re.findall(r"[一-龥a-zA-Z0-9]{2,}", expected)
        keywords = [k for k in keywords if k not in ("什么","如何","可能","是否","应该","可以")][:8]

        questions.append({
            "id": qid,
            "question": text,
            "type": cat,
            "expected_keywords": keywords,
            "min_keyword_hits": max(1, len(keywords) // 3),
            "expected_entity": "",
            "source": "md",
        })
    return questions


def build_merged_testset():
    """合并两个测试集，去重，按类型分层"""
    csv_qs = load_csv_testset(os.path.join(os.path.dirname(__file__), "testsets", "grape_qa_testset.csv"))
    md_qs = load_md_testset(os.path.join(os.path.dirname(__file__), "data", "test_questions.md"))

    # 去重：按问题文本去重
    seen = set()
    merged = []
    for q in csv_qs + md_qs:
        key = re.sub(r"\s+", "", q["question"])
        if key not in seen:
            seen.add(key)
            merged.append(q)

    # 按类型分层，确保每种类型有合理数量
    stratified = {"single_forward": [], "single_reverse": [], "multi_hop": [], "numerical": [], "rejection": []}
    for q in merged:
        cat = q.get("type", "single_forward")
        if cat not in stratified:
            cat = "single_forward"
        stratified[cat].append(q)

    # 目标：每种类型 15-25 题，总共 80-100 题
    target_per_type = {"single_forward": 22, "single_reverse": 22, "multi_hop": 20, "numerical": 12, "rejection": 8}
    final = []
    for cat, target in target_per_type.items():
        pool = stratified.get(cat, [])
        # 取前 target 个（如果不够就全取）
        selected = pool[:target]
        final.extend(selected)

    print(f"合并测试集: CSV {len(csv_qs)} + MD {len(md_qs)} = {len(merged)} (去重) -> {len(final)} (分层)")
    for cat, target in target_per_type.items():
        pool = stratified.get(cat, [])
        print(f"  {cat}: {min(len(pool), target)}/{len(pool)}")

    return final


# ========================= API 调用 =========================

import requests


def call_chat(question):
    """调用 /api/chat 并返回完整结果"""
    start = time.time()
    try:
        resp = requests.post(
            f"{API_BASE}/api/chat",
            json={"question": question, "history": []},
            timeout=60,
        )
        elapsed = round((time.time() - start) * 1000)
        if resp.status_code == 200:
            data = resp.json()
            return {
                "answer": data.get("answer", ""),
                "sources": data.get("sources", []),
                "elapsed_ms": elapsed,
                "error": None,
            }
        return {"answer": "", "sources": [], "elapsed_ms": elapsed, "error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"answer": "", "sources": [], "elapsed_ms": 0, "error": str(e)}


# ========================= 评判引擎 =========================

def judge_answer(question, expected_keywords, answer, sources):
    """LLM 评判答案质量"""
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("DEEPSEEK_API_KEY"), base_url="https://api.deepseek.com")
    if not os.getenv("DEEPSEEK_API_KEY"):
        return {"accuracy": "SKIP", "completeness": 0, "conciseness": 0, "structure": 0, "faithfulness": 0, "reason": "No API key"}

    # 提取 KG 来源数
    kg_count = len([s for s in sources if "图谱" in s])
    vec_count = len([s for s in sources if "📄" in s or "[DOC]" in s])

    prompt = f"""评估以下问答质量。

【问题】{question}
【期望关键词】{', '.join(expected_keywords[:8])}
【系统回答】{answer[:800]}
【检索来源】KG:{kg_count}条 向量:{vec_count}条

评分（返回JSON）：
- accuracy: PASS/FAIL/PARTIAL
- completeness: 1-5（信息完整度）
- conciseness: 1-5（简洁无冗余）
- structure: 1-5（结构化程度，列表/分段加分）
- faithfulness: 1-5（基于检索内容而非编造）
- reason: 简要理由（20字以内）

只返回JSON，不要其他文字。"""

    try:
        resp = client.chat.completions.create(
            model='deepseek-chat',
            messages=[{"role": "user", "content": prompt}],
            max_tokens=256,
            temperature=0.1,
        )
        raw = resp.choices[0].message.content.strip()
        raw = re.sub(r'^```json\s*', '', raw)
        raw = re.sub(r'\s*```$', '', raw)
        result = json.loads(raw)
        return {
            "accuracy": result.get("accuracy", "SKIP"),
            "completeness": result.get("completeness", 0),
            "conciseness": result.get("conciseness", 0),
            "structure": result.get("structure", 0),
            "faithfulness": result.get("faithfulness", 0),
            "reason": result.get("reason", ""),
            "kg_sources": kg_count,
            "vec_sources": vec_count,
        }
    except Exception as e:
        return {"accuracy": "SKIP", "completeness": 0, "conciseness": 0, "structure": 0, "faithfulness": 0, "reason": str(e), "kg_sources": kg_count, "vec_sources": vec_count}

    return {"accuracy": "SKIP", "completeness": 0, "conciseness": 0, "structure": 0, "faithfulness": 0, "reason": "No response", "kg_sources": kg_count, "vec_sources": vec_count}


# ========================= 检索性能检测 =========================

def check_entity_matching(question, sources):
    """检查实体匹配情况"""
    # KG 来源格式： "HAS_SYMPTOM → xxx" 或 "图谱关系：HAS_SYMPTOM → xxx"
    # 向量来源格式： "📄 xxx" 或 "[DOC] xxx"
    kg_hits = 0
    vec_hits = 0
    for s in sources:
        s_clean = s.replace("图谱关系：", "").strip()
        if re.match(r"^(HAS_|AFFECTS_|SYMPTOM_|PART_|ALIAS_|USES_|FAVORED_|OCCURS_|TRANSMITTED_|AGGRAVATES_)", s_clean):
            kg_hits += 1
        elif "📄" in s or "[DOC]" in s or s.startswith("📄"):
            vec_hits += 1
    return {
        "kg_hits": kg_hits,
        "vec_hits": vec_hits,
        "has_match": kg_hits > 0 or vec_hits > 0,
    }


# ========================= 主流程 =========================

def run_full_evaluation():
    print("=" * 60)
    print("  全维度评价系统")
    print("=" * 60)

    # 1. 构建测试集
    print("\n[1/3] 构建测试集...")
    testset = build_merged_testset()

    # 2. 逐题测试
    print(f"\n[2/3] 测试 {len(testset)} 道题...")
    results = []
    type_stats = {}

    for i, q in enumerate(testset):
        qid = q["id"]
        qtype = q["type"]
        print(f"  [{i+1}/{len(testset)}] {qid} [{qtype}] {q['question'][:50]}...", end=" ")

        # 调 API
        api_result = call_chat(q["question"])
        if api_result["error"]:
            print(f"ERROR: {api_result['error']}")
            results.append({**q, "error": api_result["error"]})
            continue

        # 实体匹配检测
        match_info = check_entity_matching(q["question"], api_result["sources"])

        # 答案质量评判
        quality = judge_answer(q["question"], q["expected_keywords"], api_result["answer"], api_result["sources"])

        result = {
            **q,
            "answer": api_result["answer"][:500],
            "elapsed_ms": api_result["elapsed_ms"],
            "sources_count": len(api_result["sources"]),
            "kg_hits": match_info["kg_hits"],
            "has_entity_match": match_info["has_match"],
            **quality,
        }
        results.append(result)

        # 统计
        if qtype not in type_stats:
            type_stats[qtype] = {"total": 0, "pass": 0, "partial": 0, "fail": 0, "elapsed": [], "kg": [], "vec": [], "completeness": [], "faithfulness": []}
        s = type_stats[qtype]
        s["total"] += 1
        acc = quality.get("accuracy", "SKIP")
        s[acc.lower()] = s.get(acc.lower(), 0) + 1
        s["elapsed"].append(api_result["elapsed_ms"])
        s["kg"].append(match_info["kg_hits"])
        s["vec"].append(match_info["vec_hits"])
        s["completeness"].append(quality.get("completeness", 0))
        s["faithfulness"].append(quality.get("faithfulness", 0))

        print(f"{acc} ({api_result['elapsed_ms']}ms)")

    # 3. 生成报告
    print(f"\n[3/3] 生成报告...")
    generate_report(results, type_stats)


def generate_report(results, type_stats):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")

    type_labels = {
        "single_forward": "单跳正向",
        "single_reverse": "单跳反向",
        "multi_hop": "多跳推理",
        "numerical": "数值精确",
        "rejection": "拒答/边界",
    }

    print("\n" + "=" * 70)
    print("  一、问答准确率")
    print("=" * 70)

    total_pass, total_partial, total_fail = 0, 0, 0
    for cat in ["single_forward", "single_reverse", "multi_hop", "numerical", "rejection"]:
        s = type_stats.get(cat)
        if not s:
            continue
        label = type_labels.get(cat, cat)
        rate = (s["pass"] + s["partial"] * 0.5) / s["total"] * 100 if s["total"] else 0
        print(f"  {label:8s}  {rate:.1f}%  (Pass:{s['pass']} Partial:{s['partial']} Fail:{s['fail']} / {s['total']})")
        total_pass += s["pass"]
        total_partial += s["partial"]
        total_fail += s["fail"]

    total = total_pass + total_partial + total_fail
    overall = (total_pass + total_partial * 0.5) / total * 100 if total else 0
    print(f"  {'总计':8s}  {overall:.1f}%  ({total}题)")

    print("\n" + "=" * 70)
    print("  二、检索性能")
    print("=" * 70)
    for cat in ["single_forward", "single_reverse", "multi_hop", "numerical", "rejection"]:
        s = type_stats.get(cat)
        if not s or not s["elapsed"]:
            continue
        label = type_labels.get(cat, cat)
        avg_time = sum(s["elapsed"]) / len(s["elapsed"])
        avg_kg = sum(s["kg"]) / len(s["kg"])
        match_rate = len([e for e in s["elapsed"] if True]) / s["total"] * 100  # simplified
        print(f"  {label:8s}  平均耗时:{avg_time:.0f}ms  KG召回:{avg_kg:.1f}条")

    all_elapsed = [r["elapsed_ms"] for r in results if "elapsed_ms" in r]
    all_kg = [r.get("kg_hits", 0) for r in results]
    all_vec = [r.get("vec_hits", 0) for r in results if "vec_hits" in r]
    entity_match_rate = len([r for r in results if r.get("has_entity_match")]) / len(results) * 100 if results else 0
    vec_str = f"向量召回:{sum(all_vec)/len(all_vec):.1f}条" if all_vec else ""
    print(f"\n  {'总计':8s}  平均耗时:{sum(all_elapsed)/len(all_elapsed):.0f}ms  "
          f"实体匹配率:{entity_match_rate:.1f}%  KG召回:{sum(all_kg)/len(all_kg):.1f}条  {vec_str}")

    print("\n" + "=" * 70)
    print("  三、答案质量（1-5分）")
    print("=" * 70)
    for cat in ["single_forward", "single_reverse", "multi_hop", "numerical", "rejection"]:
        s = type_stats.get(cat)
        if not s:
            continue
        label = type_labels.get(cat, cat)
        comp = sum(s["completeness"]) / len(s["completeness"]) if s["completeness"] else 0
        faith = sum(s["faithfulness"]) / len(s["faithfulness"]) if s["faithfulness"] else 0
        print(f"  {label:8s}  完整性:{comp:.1f}  忠实度:{faith:.1f}")

    all_comp = [r.get("completeness", 0) for r in results if r.get("completeness")]
    all_faith = [r.get("faithfulness", 0) for r in results if r.get("faithfulness")]
    all_struct = [r.get("structure", 0) for r in results if r.get("structure")]
    all_conc = [r.get("conciseness", 0) for r in results if r.get("conciseness")]
    print(f"  {'总计':8s}  完整性:{sum(all_comp)/len(all_comp):.1f}  "
          f"忠实度:{sum(all_faith)/len(all_faith):.1f}  "
          f"结构化:{sum(all_struct)/len(all_struct):.1f}  "
          f"简洁度:{sum(all_conc)/len(all_conc):.1f}")

    # 保存报告
    report = {
        "timestamp": ts,
        "total_questions": len(results),
        "overall_accuracy": round(overall, 1),
        "category_breakdown": {
            type_labels.get(k, k): {
                "total": v["total"],
                "pass": v["pass"],
                "partial": v["partial"],
                "fail": v["fail"],
                "accuracy": round((v["pass"] + v["partial"] * 0.5) / v["total"] * 100, 1) if v["total"] else 0,
                "avg_elapsed_ms": round(sum(v["elapsed"]) / len(v["elapsed"])) if v["elapsed"] else 0,
                "avg_kg_hits": round(sum(v["kg"]) / len(v["kg"]), 1) if v["kg"] else 0,
                "avg_completeness": round(sum(v["completeness"]) / len(v["completeness"]), 1) if v["completeness"] else 0,
                "avg_faithfulness": round(sum(v["faithfulness"]) / len(v["faithfulness"]), 1) if v["faithfulness"] else 0,
            }
            for k, v in type_stats.items()
        },
        "entity_match_rate": round(entity_match_rate, 1),
        "avg_response_ms": round(sum(all_elapsed) / len(all_elapsed)) if all_elapsed else 0,
        "results": results,
    }

    path = os.path.join(OUTPUT_DIR, f"full_eval_{ts}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n报告: {path}")


if __name__ == "__main__":
    run_full_evaluation()
