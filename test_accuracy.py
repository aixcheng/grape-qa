"""
问答系统命中率测试脚本
用法: python test_accuracy.py [--judge llm|keyword|both]
"""
import re
import json
import time
import sys
import os
import requests
from datetime import datetime

API_BASE = "http://localhost:5000"
TEST_FILE = os.path.join(os.path.dirname(__file__), "data", "test_questions.md")
REPORT_DIR = os.path.join(os.path.dirname(__file__), "docs", "superpowers")

# ---- 解析测试题 ----
def parse_questions(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    questions = []
    # 按 ### Q 分割
    blocks = re.split(r"\n(?=### Q\d+)", content)
    for block in blocks:
        if not block.startswith("### Q"):
            continue

        # 提取 Q 编号和问题文本
        title_match = re.match(r"### (Q\d+)\.\s*(.+?)(?:\n|$)", block)
        if not title_match:
            continue
        qid = title_match.group(1).strip()
        question = title_match.group(2).strip()

        # 提取类型
        type_match = re.search(r"\*\*类型\*\*[：:]\s*(.+?)(?:\n|$)", block)
        qtype = type_match.group(1).strip() if type_match else ""

        # 提取预期答案 — 从 **预期答案** 到下一个 ** 或 --- 或空行后跟非缩进行
        exp_match = re.search(r"\*\*预期答案\*\*[：:]\s*(.+?)(?=\n- \*\*|\n\*\*检索|\n---|\n###|\Z)", block, re.DOTALL)
        expected = exp_match.group(1).strip() if exp_match else ""

        # 提取检索路径
        path_match = re.search(r"\*\*检索路径\*\*[：:]\s*(.+?)(?=\n- \*\*|\n\*\*|\n---|\n###|\Z)", block, re.DOTALL)
        path = path_match.group(1).strip() if path_match else ""

        # 分类
        cat = "unknown"
        if "单跳正向" in qtype:
            cat = "single_forward"
        elif "单跳反向" in qtype:
            cat = "single_reverse"
        elif "多跳" in qtype:
            cat = "multi_hop"
        elif "混合" in qtype:
            cat = "hybrid"
        elif "边界" in qtype or "对比" in qtype or "聚合" in qtype or "多实体" in qtype or "语义" in qtype:
            cat = "edge"

        questions.append({
            "id": qid,
            "question": question,
            "type": cat,
            "expected": expected,
            "path": path,
        })

    return questions


# ---- 调用 API ----
def ask_api(question):
    try:
        resp = requests.post(
            f"{API_BASE}/api/chat",
            json={"question": question, "history": []},
            timeout=60,
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("answer", ""), data.get("sources", [])
        else:
            return f"[API ERROR {resp.status_code}]", []
    except Exception as e:
        return f"[EXCEPTION: {e}]", []


# ---- 关键词评判 ----
def judge_keyword(expected, answer):
    """基于关键词重叠的简单评判"""
    # 从预期答案中提取关键词（去掉停用词和标点）
    keywords = re.findall(r"[一-龥a-zA-Z0-9]{2,}", expected)
    keywords = [k for k in keywords if k not in ("什么", "如何", "可能", "是否", "应该", "可以", "这个", "那个", "一种", "这种", "什么病", "什么虫")]

    hits = sum(1 for k in keywords if k.lower() in answer.lower())
    score = hits / len(keywords) if keywords else 0
    return score, hits, len(keywords)


# ---- LLM 评判 ----
def judge_llm(question, expected, answer):
    """用 LLM 判断答案是否正确"""
    prompt = f"""你是一个问答质量评估专家。请判断以下回答是否正确。

【问题】
{question}

【预期答案】（核心事实）
{expected}

【系统回答】
{answer}

【评判标准】
- PASS: 回答包含了预期答案的核心事实，即使表述不同也通过
- FAIL: 回答缺少核心事实、答非所问、或明确说"无法回答"
- PARTIAL: 回答部分正确但遗漏了关键信息

请只回复一个词: PASS / FAIL / PARTIAL，然后简要说明理由（一行）。"""

    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("DEEPSEEK_API_KEY"), base_url="https://api.deepseek.com")
        if not os.getenv("DEEPSEEK_API_KEY"):
            return "SKIP", "No API key"

        resp = client.chat.completions.create(
            model='deepseek-chat',
            messages=[{"role": "user", "content": prompt}],
            max_tokens=128,
            temperature=0.1,
        )
        result = resp.choices[0].message.content.strip()
        if "PASS" in result.upper():
            return "PASS", result
        elif "PARTIAL" in result.upper():
            return "PARTIAL", result
        else:
            return "FAIL", result
    except Exception as e:
        return "SKIP", str(e)


# ---- 生成报告 ----
def generate_report(results, judge_mode):
    os.makedirs(REPORT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")

    # 按类别统计
    cats = {}
    for r in results:
        c = r["type"]
        if c not in cats:
            cats[c] = {"total": 0, "pass": 0, "partial": 0, "fail": 0, "skip": 0}
        cats[c]["total"] += 1
        verdict = r.get("verdict", "SKIP")
        cats[c][verdict.lower()] = cats[c].get(verdict.lower(), 0) + 1

    # 打印报告
    print("\n" + "=" * 70)
    print("  命中率测试报告")
    print("=" * 70)
    print(f"  评判方式: {judge_mode}")
    print(f"  测试时间: {timestamp}")
    print(f"  总题数: {len(results)}")
    print("-" * 70)

    total_pass = sum(c["pass"] + c["partial"] * 0.5 for c in cats.values())
    total_q = sum(c["total"] for c in cats.values())
    overall = total_pass / total_q * 100 if total_q else 0

    cat_labels = {
        "single_forward": "单跳正向", "single_reverse": "单跳反向",
        "multi_hop": "多跳推理", "hybrid": "文本混合", "edge": "边角测试",
    }

    for cat_key in ["single_forward", "single_reverse", "multi_hop", "hybrid", "edge"]:
        c = cats.get(cat_key)
        if c:
            p = c["pass"]
            partial = c["partial"]
            f = c["fail"]
            t = c["total"]
            rate = (p + partial * 0.5) / t * 100 if t else 0
            label = cat_labels.get(cat_key, cat_key)
            print(f"  {label:8s}  {rate:.0f}%  (Pass:{p} Partial:{partial} Fail:{f} / {t})")

    print("-" * 70)
    print(f"  {'Total':8s}  {overall:.1f}%")
    print("=" * 70)

    # 失败题目列表
    failed = [r for r in results if r.get("verdict") in ("FAIL", "PARTIAL", "SKIP")]
    if failed:
        print(f"\n  需要关注的题目 ({len(failed)} 题):")
        print("-" * 70)
        for r in failed:
            print(f"  {r['id']} [{r['verdict']}] {r['question'][:60]}...")

    # 保存 JSON 报告
    report_path = os.path.join(REPORT_DIR, f"accuracy-{judge_mode}-{timestamp}.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": timestamp,
            "judge_mode": judge_mode,
            "total_questions": len(results),
            "overall_rate": round(overall, 1),
            "category_breakdown": {
                cat_labels.get(k, k): {
                    "total": v["total"], "pass": v["pass"],
                    "partial": v["partial"], "fail": v["fail"],
                    "rate": round((v["pass"] + v["partial"] * 0.5) / v["total"] * 100, 1) if v["total"] else 0,
                }
                for k, v in cats.items()
            },
            "results": results,
        }, f, ensure_ascii=False, indent=2)

    print(f"\n  详细报告已保存: {report_path}")

    return overall


# ---- 主流程 ----
def main():
    # Fix Windows console encoding
    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    judge_mode = "keyword"
    if len(sys.argv) > 1:
        judge_mode = sys.argv[1].replace("--judge=", "").replace("--judge ", "")

    print("加载测试题...")
    questions = parse_questions(TEST_FILE)
    print(f"共解析 {len(questions)} 道题")

    if not questions:
        print("错误: 未解析到题目，检查 test_questions.md 格式")
        return

    results = []
    for i, q in enumerate(questions):
        print(f"\n[{i+1}/{len(questions)}] {q['id']}: {q['question'][:50]}...")
        start = time.time()
        answer, sources = ask_api(q["question"])
        elapsed = time.time() - start

        print(f"  耗时: {elapsed:.1f}s")
        print(f"  回答: {answer[:100]}...")

        # 评判
        if judge_mode == "llm":
            verdict, reason = judge_llm(q["question"], q["expected"], answer)
        elif judge_mode == "both":
            score, hits, total = judge_keyword(q["expected"], answer)
            kw_verdict = "PASS" if score > 0.3 else "FAIL"
            llm_verdict, reason = judge_llm(q["question"], q["expected"], answer)
            verdict = llm_verdict if llm_verdict != "SKIP" else kw_verdict
        else:  # keyword
            score, hits, total = judge_keyword(q["expected"], answer)
            verdict = "PASS" if score > 0.3 else ("PARTIAL" if score > 0.15 else "FAIL")
            reason = f"keyword score: {score:.2f} ({hits}/{total})"

        print(f"  评判: {verdict} | {reason[:80]}")

        results.append({
            **q,
            "answer": answer,
            "sources": sources,
            "verdict": verdict,
            "reason": reason,
            "elapsed": round(elapsed, 2),
        })

    # 生成报告
    overall = generate_report(results, judge_mode)

    # 如果关键词评判，建议用 LLM 再跑一次
    if judge_mode == "keyword":
        print("\n  提示: 关键词评判较粗糙，建议运行 python test_accuracy.py --judge=llm 获取更准确的评判")


if __name__ == "__main__":
    main()
