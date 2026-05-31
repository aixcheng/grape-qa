"""
安全迁移脚本：将文本文件内容直连到 Disease/Pest，删除空白桥接节点

执行前自动备份空白节点的关系数据到 migrate_backup.json
"""
import os
import re
import glob
import json
from py2neo import Graph
import os

NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
graph = Graph("neo4j://127.0.0.1:7687", auth=("neo4j", NEO4J_PASSWORD))
DATA_DIR = os.path.join(os.path.dirname(__file__), "data", "texts")


def backup():
    """备份所有空白节点及其关系"""
    print("📦 备份空白节点数据...")
    blanks = graph.run(
        "MATCH (n) WHERE size(labels(n)) = 0 "
        "RETURN id(n) AS nid"
    ).data()

    backup_data = {"nodes": [], "rels": []}
    for b in blanks:
        nid = b["nid"]
        # 获取节点的出入关系
        out = graph.run(
            "MATCH (x)-[r]->(m) WHERE id(x) = $nid "
            "RETURN type(r) AS rel, labels(m) AS target_labels, "
            "coalesce(m.name, m.id, toString(id(m))) AS target_name",
            nid=nid
        ).data()
        inp = graph.run(
            "MATCH (m)-[r]->(x) WHERE id(x) = $nid "
            "RETURN labels(m) AS source_labels, type(r) AS rel, "
            "coalesce(m.name, m.id, toString(id(m))) AS source_name",
            nid=nid
        ).data()
        backup_data["nodes"].append({
            "neo4j_id": nid,
            "outgoing": [{"rel": o["rel"], "target": o["target_name"], "target_labels": o["target_labels"]} for o in out],
            "incoming": [{"rel": i["rel"], "source": i["source_name"], "source_labels": i["source_labels"]} for i in inp],
        })

    with open("migrate_backup.json", "w", encoding="utf-8") as f:
        json.dump(backup_data, f, ensure_ascii=False, indent=2)
    print(f"  已备份 {len(backup_data['nodes'])} 个空白节点 → migrate_backup.json")
    return backup_data


def parse_text_file(filepath):
    """解析文本文件，返回 {name, category, sections: [{title, statements}]}"""
    name = os.path.basename(filepath).replace(".txt", "")
    category = "Disease" if "病" in name else "Pest"
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # 按编号标题分割
    sections = []
    parts = re.split(r"\n(?=\d+\.\s)", content)
    for part in parts:
        m = re.match(r"(\d+)\.\s*(.+?)[：:]", part)
        if not m:
            continue
        sec_num = int(m.group(1))
        title = m.group(2).strip()
        body = part[m.end():].strip()

        # 拆分为单句（按句号、分号、换行拆分）
        sentences = re.split(r"[。；;]\s*|\n+", body)
        statements = [s.strip() for s in sentences if len(s.strip()) > 8 and not re.match(r"^[①②③④⑤⑥⑦⑧⑨⑩（(]", s.strip())]

        sections.append({"num": sec_num, "title": title, "body": body, "statements": statements})

    return {"name": name, "category": category, "sections": sections}


def find_entity_node(name, label):
    """查找指定标签和名称的节点（多策略模糊匹配）"""
    # 策略1: 精确匹配
    r = graph.run(
        f"MATCH (n:{label}) WHERE n.name = $name RETURN n.name AS name",
        name=name
    ).data()
    if r:
        return r[0]["name"]

    # 策略2: 加"葡萄"前缀
    if not name.startswith("葡萄"):
        r = graph.run(
            f"MATCH (n:{label}) WHERE n.name = $name RETURN n.name AS name",
            name="葡萄" + name
        ).data()
        if r:
            return r[0]["name"]

    # 策略3: 去"葡萄"前缀
    if name.startswith("葡萄"):
        r = graph.run(
            f"MATCH (n:{label}) WHERE n.name = $name RETURN n.name AS name",
            name=name[2:]
        ).data()
        if r:
            return r[0]["name"]

    # 策略4: 子串匹配（eg. "霉霜" in "霜霉"）
    r = graph.run(
        f"MATCH (n:{label}) WHERE n.name CONTAINS $short OR $name CONTAINS n.name "
        f"RETURN n.name AS name LIMIT 1",
        short=name[:3], name=name
    ).data()
    if r:
        return r[0]["name"]

    # 策略5: 用前4个字模糊查
    if len(name) >= 4:
        short = name[:4]
        for i in range(len(short) - 1):
            swapped = short[:i] + short[i+1] + short[i] + short[i+2:]
            r = graph.run(
                f"MATCH (n:{label}) WHERE n.name CONTAINS $sw RETURN n.name AS name LIMIT 1",
                sw=swapped[1:3]
            ).data()
            if r:
                return r[0]["name"]

    return None


def find_or_create_attr_node(text, labels, embedding_model=None):
    """查找匹配的属性节点，找不到则创建"""
    if not text or len(text) < 5:
        return None, None

    # 策略1: 精确匹配
    for label in labels:
        r = graph.run(
            f"MATCH (n:{label} {{name: $text}}) RETURN n.name AS name",
            text=text
        ).data()
        if r:
            return r[0]["name"], label

    # 策略2: 子串模糊匹配
    for label in labels:
        short = text[:15]
        r = graph.run(
            f"MATCH (n:{label}) WHERE n.name CONTAINS $short OR $short CONTAINS n.name "
            f"RETURN n.name AS name LIMIT 1",
            short=short
        ).data()
        if r:
            return r[0]["name"], label

    # 策略3: 向量语义匹配（如果有 embedding_model）
    if embedding_model and len(text) > 5:
        # 获取所有同标签节点的名字和向量
        for label in labels:
            candidates = graph.run(
                f"MATCH (n:{label}) RETURN n.name AS name"
            ).data()
            if not candidates:
                continue
            cnames = [c["name"] for c in candidates]
            try:
                cvecs = embedding_model.encode(cnames, show_progress_bar=False)
                tvec = embedding_model.encode([text], show_progress_bar=False)
                scores = [float(sum(tvec[0][i] * cvecs[j][i] for i in range(len(tvec[0])))) for j in range(len(cnames))]
                best_idx = scores.index(max(scores))
                if max(scores) > 0.7:
                    return cnames[best_idx], label
            except Exception:
                pass

    # 策略4: 创建新节点
    for label in labels[:1]:  # 只用第一个标签
        try:
            graph.run(
                f"CREATE (n:{label} {{name: $text}})",
                text=text[:200]
            )
            return text[:200], label
        except Exception:
            return None, None

    return None, None


def migrate():
    """主迁移流程"""
    print("=" * 60)
    print("  图谱关系迁移脚本")
    print("=" * 60)

    # Step 0: 加载嵌入模型
    print("\n🧠 加载 BGE 嵌入模型...")
    from sentence_transformers import SentenceTransformer
    emb_model = SentenceTransformer("BAAI/bge-large-zh-v1.5")
    print("  模型就绪")

    # Step 1: 备份
    backup()

    # Step 2: 解析文本文件，建立关系
    txt_files = sorted(glob.glob(os.path.join(DATA_DIR, "*.txt")))
    print(f"\n📄 处理 {len(txt_files)} 个文本文件...")

    created_count = 0
    linked_count = 0
    skipped_count = 0
    skipped_files = []

    section_label_map = {
        "为害症状": ["Symptom"],
        "形态特征": ["Characteristic", "Symptom"],
        "病原": ["Pathogen"],
        "发病规律": ["Rule"],
        "发生规律": ["Rule"],
        "防治方法": ["Method"],
        "为害部位": ["Part"],
    }

    for fp in txt_files:
        info = parse_text_file(fp)
        entity_name = info["name"]
        entity_type = info["category"]

        # 检查 Disease/Pest 节点是否存在
        entity_node = find_entity_node(entity_name, entity_type)
        if not entity_node:
            # 尝试用 coalesce 查找
            r = graph.run(
                f"MATCH (n) WHERE (n:{entity_type}) AND (n.name = $name OR n.id = $name) "
                f"RETURN coalesce(n.name, n.id) AS name",
                name=entity_name
            ).data()
            if r:
                entity_node = r[0]["name"]
            else:
                print(f"  ⚠️ 未找到节点: {entity_name} ({entity_type})")
                skipped_files.append(entity_name)
                continue

        file_linked = 0
        for sec in info["sections"]:
            labels = section_label_map.get(sec["title"])
            if not labels:
                continue

            for stmt in sec["statements"]:
                matched_name, matched_label = find_or_create_attr_node(stmt, labels, emb_model)
                if matched_name:
                    # 确定关系类型
                    rel_map = {
                        "Symptom": ("HAS_SYMPTOM", "SYMPTOM_OF"),
                        "Characteristic": ("HAS_CHARACTERISTIC", None),
                        "Pathogen": ("HAS_PATHOGEN", None),
                        "Rule": ("HAS_RULE", None),
                        "Method": ("HAS_METHOD", None),
                        "Part": ("AFFECTS_PART", "PART_AFFECTED_BY"),
                    }
                    rel_info = rel_map.get(matched_label)
                    if not rel_info:
                        continue
                    forward_rel, reverse_rel = rel_info

                    # 检查关系是否已存在（避免重复）
                    existing = graph.run(
                        f"MATCH (e)-[:{forward_rel}]->(a:{matched_label} {{name: $aname}}) "
                        f"WHERE coalesce(e.name, e.id) = $ename RETURN count(*) AS c",
                        ename=entity_node, aname=matched_name
                    ).data()
                    if existing and existing[0]["c"] > 0:
                        continue  # 已存在，跳过

                    # 创建正向关系
                    graph.run(
                        f"MATCH (e), (a:{matched_label} {{name: $aname}}) "
                        f"WHERE (e:{entity_type}) AND (coalesce(e.name, e.id) = $ename) "
                        f"CREATE (e)-[:{forward_rel}]->(a)",
                        ename=entity_node, aname=matched_name
                    )
                    file_linked += 1

                    # 创建反向关系（如果定义过）
                    if reverse_rel:
                        graph.run(
                            f"MATCH (e), (a:{matched_label} {{name: $aname}}) "
                            f"WHERE (e:{entity_type}) AND (coalesce(e.name, e.id) = $ename) "
                            f"CREATE (a)-[:{reverse_rel}]->(e)",
                            ename=entity_node, aname=matched_name
                        )
                    linked_count += 1
                else:
                    skipped_count += 1

        if file_linked > 0:
            print(f"  ✅ {entity_name}: {file_linked} 条关系")
            created_count += 1
        else:
            print(f"  ⚠️ {entity_name}: 0 条关系（可能已存在或无匹配）")
            skipped_files.append(entity_name)

    print(f"\n📊 迁移统计:")
    print(f"  处理文件: {len(txt_files)}")
    print(f"  成功关联的实体: {created_count}")
    print(f"  新建关系数: {linked_count}")
    print(f"  跳过的语句: {skipped_count}")

    if skipped_files:
        print(f"\n⚠️ 以下文件未创建任何关系:")
        for f in skipped_files:
            print(f"  - {f}")

    # Step 3: 验证
    verify()

    # Step 4: 提示删除空白节点
    print(f"\n{'=' * 60}")
    print(f"  下一步：删除 {len(backup_data.get('nodes', [])) if 'backup_data' in dir() else '?'} 个空白节点？")
    print(f"  运行 delete_blanks() 执行删除")


# ---- 全局变量缓存 backup 结果 ----
backup_data = None


def delete_blanks():
    """删除所有无标签空白节点及其关系（需先执行 migrate 或 load backup）"""
    count = graph.run("MATCH (n) WHERE size(labels(n)) = 0 RETURN count(n) AS c").data()
    if count[0]["c"] == 0:
        print("没有空白节点需要删除")
        return

    print(f"🗑️ 删除 {count[0]['c']} 个空白节点及其关系...")
    graph.run("MATCH (n) WHERE size(labels(n)) = 0 DETACH DELETE n")
    remaining = graph.run("MATCH (n) WHERE size(labels(n)) = 0 RETURN count(n) AS c").data()
    print(f"  剩余空白节点: {remaining[0]['c']}")
    print("✅ 删除完成")


def verify():
    """验证迁移结果"""
    print(f"\n🔍 验证...")

    # 检查 Disease 的直连关系
    r = graph.run(
        "MATCH (d:Disease)-[r]->(n) WHERE NOT n:TREATMENT AND NOT n:Alias AND NOT n:Pathogen "
        "RETURN DISTINCT type(r) AS rel, labels(n) AS nl, count(n) AS c LIMIT 15"
    ).data()
    print("  Disease 新增直连关系:")
    for row in r:
        print(f"    {row['rel']}: {row['c']} -> {row['nl']}")

    # 统计
    r2 = graph.run(
        "MATCH (d)-[r]->(n) WHERE d:Disease OR d:Pest "
        "RETURN DISTINCT type(r) AS rel, count(n) AS c"
    ).data()
    print(f"\n  Disease/Pest 全部关系类型:")
    for row in r2:
        print(f"    {row['rel']}: {row['c']}")

    # 检查反向关系
    r3 = graph.run(
        "MATCH (s:Symptom)-[:SYMPTOM_OF]->(d) WHERE d:Disease OR d:Pest "
        "RETURN count(s) AS c"
    ).data()
    print(f"\n  SYMPTOM_OF → Disease/Pest: {r3[0]['c']} 条")
    r4 = graph.run(
        "MATCH (p:Part)-[:PART_AFFECTED_BY]->(d) WHERE d:Disease OR d:Pest "
        "RETURN count(p) AS c"
    ).data()
    print(f"  PART_AFFECTED_BY → Disease/Pest: {r4[0]['c']} 条")


if __name__ == "__main__":
    migrate()
