"""
重连孤立节点：严格精确匹配属性节点名到文本文件
"""
import os
import re
import glob
from py2neo import Graph

graph = Graph("neo4j://127.0.0.1:7687", auth=("neo4j", "xjcdllg666@"))
DATA_DIR = os.path.join(os.path.dirname(__file__), "data", "texts")

# 关系映射：属性标签 → (正向关系, 反向关系)
REL_MAP = {
    "Symptom":        ("HAS_SYMPTOM",       "SYMPTOM_OF"),
    "Part":           ("AFFECTS_PART",      "PART_AFFECTED_BY"),
    "Rule":           ("HAS_RULE",          None),
    "Method":         ("HAS_METHOD",        None),
    "Characteristic": ("HAS_CHARACTERISTIC", None),
    "Pathogen":       ("HAS_PATHOGEN",      None),
    "Condition":      ("FAVORED_BY",        None),
    "Period":         ("OCCURS_IN",         None),
    "Drug":           ("USES_DRUG",         None),
}


def get_entity_type(name):
    """查找实体名对应的类型（Disease/Pest）"""
    r = graph.run(
        "MATCH (n) WHERE (n:Disease OR n:Pest) AND (n.name = $name OR n.id = $name) "
        "RETURN labels(n) AS l LIMIT 1",
        name=name
    ).data()
    return "Disease" if r and "Disease" in r[0]["l"] else ("Pest" if r and "Pest" in r[0]["l"] else None)


def find_exact_match(attr_name, texts):
    """严格精确匹配：属性名必须作为子串出现在文本中，返回匹配的文件名列表"""
    matches = []
    for fname, content in texts.items():
        if attr_name in content:
            matches.append(fname)
    return matches


def main():
    print("=" * 60)
    print("  孤立节点精确重连")
    print("=" * 60)

    # 1. 加载文本文件
    print("\n[1/4] 加载文本文件...")
    texts = {}
    for fp in sorted(glob.glob(os.path.join(DATA_DIR, "*.txt"))):
        name = os.path.basename(fp).replace(".txt", "")
        with open(fp, "r", encoding="utf-8") as f:
            texts[name] = f.read()
    print(f"  已加载 {len(texts)} 个文件")

    # 2. 获取孤立节点
    print("\n[2/4] 获取孤立节点...")
    orphans = graph.run(
        "MATCH (n) WHERE NOT (n)--() "
        "RETURN id(n) AS nid, labels(n) AS labels, coalesce(n.name, n.id) AS name"
    ).data()
    print(f"  孤立节点: {len(orphans)}")

    # 3. 匹配
    print("\n[3/4] 精确匹配中...")
    matches = []   # (orphan_name, orphan_label, entity_name, entity_type, fwd_rel, rev_rel)
    skipped_multi = []
    skipped_none = []

    for o in orphans:
        name = o["name"]
        if not name or len(name) < 3:
            skipped_none.append(f"{name}（名称太短）")
            continue

        labels = o["labels"]
        # 找这个节点的标签中哪个在 REL_MAP 里
        orphan_label = None
        for lbl in labels:
            if lbl in REL_MAP:
                orphan_label = lbl
                break
        if not orphan_label:
            skipped_none.append(f"{name} [{labels}]（不在 REL_MAP 中）")
            continue

        # 严格精确匹配到文本文件
        matched_files = find_exact_match(name, texts)

        if len(matched_files) == 0:
            skipped_none.append(f"{name} [{orphan_label}]（未匹配任何文件）")
            continue
        elif len(matched_files) > 1:
            skipped_multi.append(f"{name} [{orphan_label}]（匹配多个: {', '.join(matched_files[:3])}）")
            continue

        # 唯一匹配
        entity_name = matched_files[0]
        entity_type = get_entity_type(entity_name)
        if not entity_type:
            skipped_none.append(f"{name} -> {entity_name}（找不到 Disease/Pest 节点）")
            continue

        fwd_rel, rev_rel = REL_MAP[orphan_label]
        matches.append((name, orphan_label, entity_name, entity_type, fwd_rel, rev_rel))

    print(f"  唯一匹配: {len(matches)}")
    print(f"  多匹配跳过: {len(skipped_multi)}")
    print(f"  无匹配跳过: {len(skipped_none)}")

    # 4. 创建关系
    print(f"\n[4/4] 创建 {len(matches)} 条关系...")
    created = 0
    skipped_exist = 0

    for attr_name, attr_label, entity_name, entity_type, fwd_rel, rev_rel in matches:
        # 检查是否已存在（避免重复）
        exist = graph.run(
            f"MATCH (e:{entity_type})-[r:{fwd_rel}]->(a:{attr_label} {{name: $aname}}) "
            f"WHERE coalesce(e.name, e.id) = $ename "
            f"RETURN count(r) AS c",
            ename=entity_name, aname=attr_name
        ).data()
        if exist and exist[0]["c"] > 0:
            skipped_exist += 1
            continue

        # 创建正向关系
        graph.run(
            f"MATCH (e:{entity_type}) WHERE coalesce(e.name, e.id) = $ename "
            f"MATCH (a:{attr_label} {{name: $aname}}) "
            f"CREATE (e)-[:{fwd_rel}]->(a)",
            ename=entity_name, aname=attr_name
        )
        created += 1

        # 创建反向关系
        if rev_rel:
            graph.run(
                f"MATCH (e:{entity_type}) WHERE coalesce(e.name, e.id) = $ename "
                f"MATCH (a:{attr_label} {{name: $aname}}) "
                f"CREATE (a)-[:{rev_rel}]->(e)",
                ename=entity_name, aname=attr_name
            )

    print(f"  新建关系: {created}")
    print(f"  已存在跳过: {skipped_exist}")

    # 5. 总结
    remaining = graph.run("MATCH (n) WHERE NOT (n)--() RETURN count(n) AS c").data()
    print(f"\n{'=' * 60}")
    print(f"  剩余孤立节点: {remaining[0]['c']}/{len(orphans)}")
    if skipped_multi:
        print(f"\n  多匹配节点（前10个）:")
        for s in skipped_multi[:10]:
            print(f"    {s}")
    if skipped_none:
        print(f"\n  无匹配节点（前10个）:")
        for s in skipped_none[:10]:
            print(f"    {s}")


if __name__ == "__main__":
    main()
