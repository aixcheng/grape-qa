import argparse
import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TESTSET = ROOT / "tests" / "grape_qa_testset.json"
DEFAULT_CSV_TESTSET = ROOT / "tests" / "grape_qa_testset.csv"
ONTOLOGY_FILE = ROOT / "知识图谱体系.txt"
TEXT_DIR = ROOT / "data" / "texts"


def normalize(text):
    return re.sub(r"\s+", "", str(text or "")).lower()


def keyword_hits(text, keywords):
    compact = normalize(text)
    return [keyword for keyword in keywords if normalize(keyword) in compact]


def read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def read_csv_testset(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    testset = {
        "meta": {
            "name": "葡萄病虫害知识图谱 CSV 测试集",
            "version": "2.0.0",
            "description": "由 data/texts 中各病虫害章节生成，默认每个实体 2 条。",
        },
        "ontology": {
            "expected_entity_labels": [
                "Disease", "Pest", "Alias", "Symptom", "Part", "Rule", "Method",
                "Drug", "Treatment", "Pathogen", "Characteristic", "Condition",
                "Period", "Vector",
            ],
            "expected_relation_types": [
                "HAS_ALIAS", "ALIAS_OF", "HAS_SYMPTOM", "SYMPTOM_OF",
                "AFFECTS_PART", "PART_AFFECTED_BY", "HAS_RULE", "HAS_METHOD",
                "HAS_TREATMENT", "USES_DRUG", "HAS_PATHOGEN",
                "HAS_CHARACTERISTIC", "FAVORED_BY", "OCCURS_IN",
                "AGGRAVATES", "TRANSMITTED_BY",
            ],
        },
        "knowledge_detail_tests": [],
        "qa_tests": [],
    }

    detail_seen = set()
    for row in rows:
        keywords = [part.strip() for part in row.get("expected_keywords", "").split("|") if part.strip()]
        required_sections = [part.strip() for part in row.get("required_sections", "").split("|") if part.strip()]
        relation_types = [part.strip() for part in row.get("expected_relation_types", "").split("|") if part.strip()]
        min_hits = int(row.get("min_keyword_hits") or 2)

        source_file = row.get("source_file") or row.get("expected_entity")
        entity = row.get("expected_entity") or source_file
        case = {
            "id": row["id"],
            "type": row.get("case_type", ""),
            "question": row["question"],
            "expected_entity": entity if entity else None,
            "source_file": source_file,
            "expected_relation_types": relation_types,
            "expected_keywords": keywords,
            "min_keyword_hits": min_hits,
        }
        testset["qa_tests"].append(case)

        if source_file and source_file not in detail_seen:
            detail_seen.add(source_file)
            testset["knowledge_detail_tests"].append({
                "id": f"KD_{source_file}",
                "name": entity,
                "source_file": source_file,
                "category": row.get("category", ""),
                "required_sections": required_sections,
                "expected_keywords": keywords[:4],
            })

    return testset


def read_text(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def split_sections(content):
    sections = {}
    parts = re.split(r"\n(?=\d+\.\s*)", content)
    for part in parts:
        match = re.match(r"\s*(\d+)\.\s*(.+?)[：:；;]", part)
        if not match:
            continue
        title = match.group(2).strip()
        body = part[match.end():].strip()
        sections[title] = body
    return sections


def request_json(method, url, payload=None, timeout=30):
    data = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    started = time.perf_counter()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        raw = resp.read().decode("utf-8")
        return resp.status, json.loads(raw), elapsed_ms


def result(case_id, name, passed, detail=None, elapsed_ms=None):
    item = {
        "id": case_id,
        "name": name,
        "passed": bool(passed),
        "detail": detail or "",
    }
    if elapsed_ms is not None:
        item["elapsed_ms"] = elapsed_ms
    return item


def run_ontology_tests(testset):
    results = []
    if not ONTOLOGY_FILE.exists():
        return [result("ONT000", "知识图谱体系文件存在", False, f"缺少文件: {ONTOLOGY_FILE}")]

    content = read_text(ONTOLOGY_FILE)
    for label in testset["ontology"]["expected_entity_labels"]:
        results.append(result(
            f"ONT_ENTITY_{label}",
            f"实体标签 {label} 已定义",
            label in content,
            "在知识图谱体系.txt 中查找实体标签",
        ))

    for rel in testset["ontology"]["expected_relation_types"]:
        results.append(result(
            f"ONT_REL_{rel}",
            f"关系类型 {rel} 已定义",
            rel in content,
            "在知识图谱体系.txt 中查找关系类型",
        ))

    return results


def run_knowledge_file_tests(testset):
    results = []
    for case in testset["knowledge_detail_tests"]:
        source_name = case.get("source_file", case["name"])
        file_path = TEXT_DIR / f"{source_name}.txt"
        if not file_path.exists():
            results.append(result(case["id"], f"{case['name']} 文本存在", False, f"缺少文件: {file_path}"))
            continue

        content = read_text(file_path)
        sections = split_sections(content)
        missing_sections = [title for title in case["required_sections"] if title not in sections]
        hits = keyword_hits(content, case["expected_keywords"])

        passed = not missing_sections and len(hits) == len(case["expected_keywords"])
        detail = {
            "missing_sections": missing_sections,
            "keyword_hits": hits,
            "missing_keywords": [kw for kw in case["expected_keywords"] if kw not in hits],
        }
        results.append(result(case["id"], f"{case['name']} 本地知识文本完整性", passed, detail))
    return results


def run_offline_qa_source_tests(testset):
    results = []
    for case in testset["qa_tests"]:
        expected_entity = case.get("expected_entity")
        if not expected_entity:
            results.append(result(case["id"], "未知问题保护用例仅在 api 模式评测", True, "offline 模式跳过"))
            continue

        source_name = case.get("source_file", expected_entity)
        file_path = TEXT_DIR / f"{source_name}.txt"
        if not file_path.exists():
            results.append(result(case["id"], f"{expected_entity} 来源文本存在", False, f"缺少文件: {file_path}"))
            continue

        content = read_text(file_path)
        hits = keyword_hits(content, case["expected_keywords"])
        passed = len(hits) >= case["min_keyword_hits"]
        detail = {
            "question": case["question"],
            "expected_entity": expected_entity,
            "keyword_hits": hits,
            "min_keyword_hits": case["min_keyword_hits"],
        }
        results.append(result(case["id"], f"{case['type']} 来源知识覆盖", passed, detail))
    return results


def run_api_knowledge_tests(testset, base_url, timeout):
    results = []
    try:
        status, body, elapsed = request_json("GET", f"{base_url}/api/health", timeout=timeout)
        results.append(result("API_HEALTH", "后端健康检查", status == 200 and body.get("status") == "ok", body, elapsed))
    except Exception as exc:
        return [result("API_HEALTH", "后端健康检查", False, str(exc))]

    try:
        status, body, elapsed = request_json("GET", f"{base_url}/api/knowledge/list", timeout=timeout)
        names = {item.get("name") for item in body if isinstance(item, dict)}
        required = {case.get("source_file", case["name"]) for case in testset["knowledge_detail_tests"]}
        missing = sorted(required - names)
        results.append(result(
            "API_KNOWLEDGE_LIST",
            "知识列表包含核心测试实体",
            status == 200 and not missing,
            {"missing": missing, "count": len(body) if isinstance(body, list) else None},
            elapsed,
        ))
    except Exception as exc:
        results.append(result("API_KNOWLEDGE_LIST", "知识列表包含核心测试实体", False, str(exc)))

    for case in testset["knowledge_detail_tests"]:
        query_name = case.get("source_file", case["name"])
        encoded = urllib.parse.quote(query_name)
        try:
            status, body, elapsed = request_json("GET", f"{base_url}/api/knowledge/{encoded}", timeout=timeout)
            text = json.dumps(body, ensure_ascii=False)
            hits = keyword_hits(text, case["expected_keywords"])
            section_titles = [section.get("title") for section in body.get("sections", [])]
            missing_sections = [title for title in case["required_sections"] if title not in section_titles]
            passed = status == 200 and not missing_sections and len(hits) >= len(case["expected_keywords"])
            results.append(result(
                f"API_{case['id']}",
                f"{case['name']} 详情接口",
                passed,
                {"missing_sections": missing_sections, "keyword_hits": hits},
                elapsed,
            ))
        except Exception as exc:
            results.append(result(f"API_{case['id']}", f"{case['name']} 详情接口", False, str(exc)))

    return results


def run_api_chat_tests(testset, base_url, timeout):
    results = []
    for case in testset["qa_tests"]:
        payload = {"question": case["question"], "history": []}
        try:
            status, body, elapsed = request_json("POST", f"{base_url}/api/chat", payload=payload, timeout=timeout)
            answer = body.get("answer", "")
            sources = body.get("sources", [])
            hits = keyword_hits(answer, case["expected_keywords"])
            passed = status == 200 and len(hits) >= case["min_keyword_hits"]
            detail = {
                "question": case["question"],
                "answer": answer,
                "sources": sources,
                "keyword_hits": hits,
                "min_keyword_hits": case["min_keyword_hits"],
            }
            results.append(result(case["id"], f"{case['type']} 问答接口", passed, detail, elapsed))
        except Exception as exc:
            results.append(result(case["id"], f"{case['type']} 问答接口", False, str(exc)))
    return results


def summarize(results):
    total = len(results)
    passed = sum(1 for item in results if item["passed"])
    failed = total - passed
    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "pass_rate": round(passed / total, 4) if total else 0,
    }


def print_summary(summary, results):
    print("\n=== 葡萄病虫害知识图谱测试结果 ===")
    print(f"总数: {summary['total']}  通过: {summary['passed']}  失败: {summary['failed']}  通过率: {summary['pass_rate'] * 100:.2f}%")
    failed = [item for item in results if not item["passed"]]
    if not failed:
        print("所有测试通过。")
        return

    print("\n失败项:")
    for item in failed:
        print(f"- {item['id']} {item['name']}: {item['detail']}")


def main():
    parser = argparse.ArgumentParser(description="葡萄病虫害知识图谱问答系统测试脚本")
    parser.add_argument("--testset", default=str(DEFAULT_CSV_TESTSET), help="测试集路径，支持 CSV 或 JSON")
    parser.add_argument("--mode", choices=["offline", "api", "all"], default="offline", help="offline 只读本地文件；api 调接口；all 两者都跑")
    parser.add_argument("--base-url", default="http://127.0.0.1:5000", help="后端服务地址")
    parser.add_argument("--timeout", type=int, default=60, help="HTTP 请求超时时间，单位秒")
    parser.add_argument("--skip-chat", action="store_true", help="api/all 模式下跳过 /api/chat")
    parser.add_argument("--report", default=str(ROOT / "tests" / "test_report.json"), help="测试报告输出路径")
    args = parser.parse_args()

    testset_path = Path(args.testset)
    if testset_path.suffix.lower() == ".csv":
        testset = read_csv_testset(testset_path)
    else:
        testset = read_json(testset_path)
    results = []

    if args.mode in ("offline", "all"):
        results.extend(run_ontology_tests(testset))
        results.extend(run_knowledge_file_tests(testset))
        results.extend(run_offline_qa_source_tests(testset))

    if args.mode in ("api", "all"):
        results.extend(run_api_knowledge_tests(testset, args.base_url.rstrip("/"), args.timeout))
        if not args.skip_chat:
            results.extend(run_api_chat_tests(testset, args.base_url.rstrip("/"), args.timeout))

    summary = summarize(results)
    report = {
        "summary": summary,
        "mode": args.mode,
        "base_url": args.base_url,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "results": results,
    }

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print_summary(summary, results)
    print(f"\n报告已写入: {report_path}")
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
