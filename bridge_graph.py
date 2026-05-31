"""
嫁接脚本：利用空白节点已有连接 + 文本文件，建立 Disease/Pest → 属性节点的直连关系
只新增关系，不删不改现有节点
"""
import os
import re
import glob
import json
from py2neo import Graph

NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
graph = Graph("neo4j://127.0.0.1:7687", auth=("neo4j", NEO4J_PASSWORD))
DATA_DIR = os.path.join(os.path.dirname(__file__), "data", "texts")

REL_MAP = {
    "HAS_SYMPTOM":    ("Symptom",        "SYMPTOM_OF"),
    "AFFECTS_PART":   ("Part",           "PART_AFFECTED_BY"),
    "HAS_RULE":       ("Rule",           None),
    "HAS_METHOD":     ("Method",         None),
    "FAVORED_BY":     ("Condition",      None),
    "OCCURS_IN":      ("Period",         None),
    "TRANSMITTED_BY": ("Vector",         None),
    "HAS_CHARACTERISTIC": ("Characteristic", None),
    "HAS_PATHOGEN":   ("Pathogen",       None),
}


def load_text_files():
    """读取所有文本文件 → {disease_name: full_text}"""
    print("📄 加载文本文件...")
    texts = {}
    for fp in sorted(glob.glob(os.path.join(DATA_DIR, "*.txt"))):
        name = os.path.basename(fp).replace(".txt", "")
        with open(fp, "r", encoding="utf-8") as f:
            texts[name] = f.read()
    print(f"  已加载 {len(texts)} 个文件")
    return texts


def load_blank_bridges():
    """
    获取每个空白节点的连接信息：
    {blank_nid: {
        outgoing: [(rel_type, target_name, target_labels), ...],
        incoming: [(source_name, source_labels, rel_type), ...]
    }}
    """
    print("📊 加载空白节点桥接信息...")
    blanks = graph.run("MATCH (n) WHERE size(labels(n)) = 0 RETURN id(n) AS nid").data()

    bridges = {}
    for b in blanks:
        nid = b["nid"]
        out = graph.run(
            "MATCH (x)-[r]->(m) WHERE id(x) = $nid "
            "RETURN type(r) AS rel, labels(m) AS tl, coalesce(m.name, m.id, m.title) AS tname",
            nid=nid
        ).data()
        inp = graph.run(
            "MATCH (m)-[r]->(x) WHERE id(x) = $nid "
            "RETURN coalesce(m.name, m.id, m.title) AS sname, labels(m) AS sl, type(r) AS rel",
            nid=nid
        ).data()
        bridges[nid] = {
            "outgoing": [(o["rel"], o["tname"], o["tl"]) for o in out if o["tname"]],
            "incoming": [(i["sname"], i["sl"], i["rel"]) for i in inp if i["sname"]],
        }
    print(f"  已加载 {len(bridges)} 个空白节点")
    return bridges


def find_entity_in_texts(name, texts):
    """在文本中查找对应的 Disease/Pest（多策略）"""
    # 精确匹配
    if name in texts:
        return name
    # 加/去葡萄前缀
    prefixed = "葡萄" + name
    if prefixed in texts:
        return prefixed
    if name.startswith("葡萄") and name[2:] in texts:
        return name[2:]
    # 子串匹配（eg. 白纹羽 in 葡萄白纹羽烂根病）
    for tname in texts:
        if len(name) >= 4 and name[:4] in tname:
            return tname
        if len(tname) >= 4 and tname[:4] in name:
            return tname
    return None


def get_entity_type(name):
    """判断是 Disease 还是 Pest"""
    r = graph.run(
        "MATCH (n) WHERE coalesce(n.name, n.id) = $name AND (n:Disease OR n:Pest) "
        "RETURN labels(n) AS l LIMIT 1",
        name=name
    ).data()
    if not r:
        return None
    return "Disease" if "Disease" in r[0]["l"] else "Pest"


def bridge():
    print("=" * 60)
    print("  图谱关系嫁接")
    print("=" * 60)

    texts = load_text_files()
    bridges = load_blank_bridges()

    # 关键步骤：为每个空白节点找归属
    # 逻辑：空白节点 → HAS_SYMPTOM → Symptom名
    #       在哪个文本文件中出现这个Symptom名？→ 该空白节点属于那个病害
    print("\n🔗 匹配空白节点到 Disease/Pest...")

    matches = []  # [(entity_text_name, blank_nid, score, matched_attrs)]
    for nid, bridge in bridges.items():
        # 收集空白节点连接的所有属性节点名
        attr_names = [o[1] for o in bridge["outgoing"]]
        if not attr_names:
            continue

        # 在哪个文本中这些属性名出现最多？
        best_text = None
        best_score = 0
        matched = []

        for text_name, content in texts.items():
            score = 0
            attrs_found = []
            for aname in attr_names:
                if len(aname) >= 3 and aname in content:
                    score += 1
                    attrs_found.append(aname)
            if score > best_score:
                best_score = score
                best_text = text_name
                matched = attrs_found

        if best_text and best_score >= 1:
            matches.append((best_text, nid, best_score, matched))

    print(f"  匹配到 {len(matches)} 个空白节点")
    print(f"  未匹配: {len(bridges) - len(matches)} 个")

    # 去重：每个 Disease/Pest 可能有多个空白节点
    entity_blanks = {}  # {entity_name: [blank_nid, ...]}
    for text_name, nid, score, matched in matches:
        entity_name = find_entity_in_texts(text_name, texts)
        if not entity_name:
            continue
        if entity_name not in entity_blanks:
            entity_blanks[entity_name] = []
        entity_blanks[entity_name].append((nid, score, matched))

    # 创建直连关系
    print(f"\n🔗 为 {len(entity_blanks)} 个 Disease/Pest 创建直连...")
    total_created = 0

    for entity_name, blank_list in entity_blanks.items():
        etype = get_entity_type(entity_name)
        if not etype:
            print(f"  ⚠️ 找不到节点类型: {entity_name}")
            continue

        entity_rel_count = 0
        for nid, score, matched in blank_list:
            bridge = bridges.get(nid)
            if not bridge:
                continue

            for rel_type, target_name, target_labels in bridge["outgoing"]:
                mapping = REL_MAP.get(rel_type)
                if not mapping:
                    continue
                target_label, reverse_rel = mapping

                # 已有直连则跳过
                existing = graph.run(
                    f"MATCH (e:{etype})-[r:{rel_type}]->(a:{target_label} {{name: $tname}}) "
                    f"WHERE coalesce(e.name, e.id) = $ename "
                    f"RETURN count(r) AS c",
                    ename=entity_name, tname=target_name
                ).data()
                if existing and existing[0]["c"] > 0:
                    continue

                try:
                    graph.run(
                        f"MATCH (e:{etype}) WHERE coalesce(e.name, e.id) = $ename "
                        f"MATCH (a:{target_label} {{name: $tname}}) "
                        f"CREATE (e)-[:{rel_type}]->(a)",
                        ename=entity_name, tname=target_name
                    )
                    entity_rel_count += 1

                    if reverse_rel:
                        graph.run(
                            f"MATCH (e:{etype}) WHERE coalesce(e.name, e.id) = $ename "
                            f"MATCH (a:{target_label} {{name: $tname}}) "
                            f"CREATE (a)-[:{reverse_rel}]->(e)",
                            ename=entity_name, tname=target_name
                        )
                except Exception:
                    pass

        if entity_rel_count:
            print(f"  ✅ {entity_name}: {entity_rel_count} 条")
            total_created += entity_rel_count
        else:
            print(f"  ⚠️ {entity_name}: 0 条（可能已存在）")

    print(f"\n📊 总计新建 {total_created} 条直连关系")

    # 验证
    verify()

    print(f"\n下一步: python bridge_graph.py delete  来删除空白节点")


def verify():
    print(f"\n🔍 验证...")
    r = graph.run(
        "MATCH (d)-[r]->(n) WHERE d:Disease OR d:Pest "
        "RETURN DISTINCT type(r) AS rel, count(n) AS c ORDER BY c DESC"
    ).data()
    print("  Disease/Pest 关系类型:")
    for row in r:
        print(f"    {row['rel']}: {row['c']}")

    r2 = graph.run(
        "MATCH (s:Symptom)-[:SYMPTOM_OF]->(d) WHERE d:Disease OR d:Pest RETURN count(s) AS c"
    ).data()
    print(f"  SYMPTOM_OF → Disease/Pest: {r2[0]['c']}")

    r3 = graph.run("MATCH (n) WHERE size(labels(n))=0 RETURN count(n) AS c").data()
    print(f"  剩余空白节点: {r3[0]['c']}")


def delete_blanks():
    c = graph.run("MATCH (n) WHERE size(labels(n))=0 RETURN count(n) AS c").data()
    if c[0]["c"] == 0:
        print("没有空白节点")
        return
    print(f"🗑️ 删除 {c[0]['c']} 个空白节点及其关系...")
    graph.run("MATCH (n) WHERE size(labels(n))=0 DETACH DELETE n")
    print("✅ 已删除")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "delete":
        delete_blanks()
    else:
        bridge()
