#
from openai import OpenAI
from flask import Flask, request, jsonify
from flask_cors import CORS
from py2neo import Graph
import ollama
import chromadb
from sentence_transformers import SentenceTransformer
import os
import re
import glob
from langchain_text_splitters import RecursiveCharacterTextSplitter
import bcrypt
from db import init_db, create_user, get_user_by_username, save_chat, get_history
from auth import create_token, require_auth
from knowledge import list_knowledge, get_knowledge

#
app = Flask(__name__)
CORS(app)

# Neo4j
graph = Graph("neo4j://127.0.0.1:7687", auth=("neo4j", "xjcdllg666@"))

# 
chroma_client = chromadb.PersistentClient(path="./chroma_db")
collection = chroma_client.get_or_create_collection(name="grape_knowledge")

# 
embedding_model = SentenceTransformer("BAAI/bge-large-zh-v1.5")

# 
ENTITY_LIST = []           # [(name, type), ...] type ∈ Disease|Pest|Alias|Symptom|Part
REVERSE_MAP = {}           # {Symptom/Part name: [Disease/Pest name, ...]}  
ENTITY_EMBEDDINGS = {}     # {name: numpy_vector}   fallback

def load_entities_from_neo4j():
    """ Neo4j """
    global ENTITY_LIST, REVERSE_MAP, ENTITY_EMBEDDINGS
    try:
        # 1.  (Disease, Pest, Alias, Symptom, Part)
        result = graph.run(
            "MATCH (n) WHERE n:Disease OR n:Pest OR n:Alias OR n:Symptom OR n:Part "
            "RETURN n.name AS name, labels(n) AS labels"
        ).data()

        entities = []
        for record in result:
            name = record['name']
            if not name:
                continue
            labels = record['labels']
            if 'Disease' in labels:
                typ = 'Disease'
            elif 'Pest' in labels:
                typ = 'Pest'
            elif 'Alias' in labels:
                typ = 'Alias'
            elif 'Symptom' in labels:
                typ = 'Symptom'
            elif 'Part' in labels:
                typ = 'Part'
            else:
                continue
            entities.append((name, typ))

        # """"
        entities.sort(key=lambda x: len(x[0]), reverse=True)
        ENTITY_LIST = entities

        # 2. Symptom → Disease/Pest, Part → Disease/Pest
        REVERSE_MAP = {}
        rev_result = graph.run(
            "MATCH (s)-[:SYMPTOM_OF|PART_AFFECTED_BY]->(e) "
            "WHERE (s:Symptom OR s:Part) AND (e:Disease OR e:Pest) "
            "RETURN s.name AS symptom_or_part, collect(e.name) AS entities"
        ).data()
        for row in rev_result:
            key = row['symptom_or_part']
            if key and row['entities']:
                REVERSE_MAP[key] = row['entities']

        # 3.  fallback
        if ENTITY_LIST:
            names = [e[0] for e in ENTITY_LIST]
            vectors = embedding_model.encode(names, show_progress_bar=False)
            ENTITY_EMBEDDINGS = {names[i]: vectors[i] for i in range(len(names))}

        print(f"[OK]  {len(ENTITY_LIST)}  (Disease/Pest/Alias/Symptom/Part)")
        print(f"[OK]  {len(REVERSE_MAP)}  (Symptom/Part → Disease/Pest)")
        print(f"[OK]  {len(ENTITY_EMBEDDINGS)} ")
    except Exception as e:
        print(f"[ERR] : {e}")
        ENTITY_LIST = []
        REVERSE_MAP = {}


def match_entities(question, top_k=5):
    """
    
    1. ACO(n*m)
    2.  fallback BGE 
    : [(entity_name, entity_type, match_score), ...]
    """
    matches = []

    # 
    # 
    matched_positions = set()
    for name, typ in ENTITY_LIST:
        start = 0
        while True:
            idx = question.find(name, start)
            if idx == -1:
                break
            # 
            positions = set(range(idx, idx + len(name)))
            if not positions & matched_positions:
                matches.append((name, typ, 1.0))
                matched_positions |= positions
                break
            start = idx + 1

    # 
    if not matches:
        try:
            q_vec = embedding_model.encode(question)
            best_score = 0
            best_match = None
            for name, vec in ENTITY_EMBEDDINGS.items():
                #  Disease/Pest/Alias Symptom/Part 
                score = float(sum(q_vec[i] * vec[i] for i in range(len(q_vec))))
                if score > best_score and score > 0.6:
                    best_score = score
                    # 
                    for n, t in ENTITY_LIST:
                        if n == name:
                            best_match = (name, t, round(score, 2))
                            break
            if best_match:
                matches.append(best_match)
        except Exception:
            pass

    return matches[:top_k]




# ——
def index_documents():
    # 1. 
    docs_dir = r"C:\grape_qa\data\texts"
    
    # 2. 
    if not os.path.exists(docs_dir):
        print(f"[ERR] : {docs_dir}")
        return
    
    # 3.  .txt 
    txt_files = glob.glob(os.path.join(docs_dir, "*.txt"))
    if not txt_files:
        print(f"[ERR]  {docs_dir}  .txt ")
        return
    
    print(f"[FILE]  {len(txt_files)} ")
    
    # 4. 50050
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=700,
        chunk_overlap=50,
        separators=["\n\n", "\n", "", "", "", " ", ""]
    )
    
    # 5.  collection
    # 
    existing_ids = collection.get()['ids']
    if existing_ids:
        collection.delete(ids=existing_ids)
        print("[DEL] ")
    
    # 6. 
    total_chunks = 0
    for file_path in txt_files:
        file_name = os.path.basename(file_path).replace(".txt", "")
        print(f"[DOC] : {file_name}")
        
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # 
        if not content.strip():
            print(f"   [WARN] ")
            continue
        
        # 
        chunks = text_splitter.split_text(content)
        print(f"   →  {len(chunks)} ")
        
        # 
        for i, chunk in enumerate(chunks):
            # ID_
            doc_id = f"{file_name}_{i}"
            # 
            vector = embedding_model.encode(chunk).tolist()
            # ChromaDB
            collection.upsert(
                ids=[doc_id],
                embeddings=[vector],
                documents=[chunk],
                metadatas=[{"source": file_name, "chunk_index": i}]
            )
            total_chunks += 1
    
    print(f"[OK]  {total_chunks}  {len(txt_files)} ")


# ——


def answer_question_with_sources(question, history=None):
    kg_answer_parts = []
    kg_sources = []
    queried_entities = set()

    # Step 1: entity matching
    matched = match_entities(question)

    # Step 2: KG query
    for entity_name, entity_type, score in matched:
        resolved_name = entity_name
        resolved_type = entity_type

        #  → 
        if entity_type == 'Alias':
            alias_res = graph.run(
                "MATCH (a:Alias {name: $name})-[r:ALIAS_OF]->(e) "
                "RETURN e.name AS real_name, labels(e) AS labels",
                name=entity_name
            ).data()
            if alias_res:
                resolved_name = alias_res[0]['real_name']
                real_labels = alias_res[0]['labels']
                if 'Disease' in real_labels:
                    resolved_type = 'Disease'
                elif 'Pest' in real_labels:
                    resolved_type = 'Pest'
                else:
                    continue
            else:
                continue

        # Symptom/Part → Disease/Pest (reverse diagnosis)
        if entity_type in ('Symptom', 'Part'):
            reverse_entities = REVERSE_MAP.get(entity_name, [])
            scored = []
            for rev_name in reverse_entities:
                score = 1
                rev_attrs = set()
                for sn, st in ENTITY_LIST:
                    if st in ('Symptom', 'Part') and sn in REVERSE_MAP:
                        if rev_name in REVERSE_MAP[sn]:
                            rev_attrs.add(sn)
                for attr in rev_attrs:
                    if attr in question:
                        score += 2
                if rev_name in question:
                    score += 3
                scored.append((rev_name, score))
            scored.sort(key=lambda x: x[1], reverse=True)
            reverse_entities = [s[0] for s in scored[:3] if s[1] > 1]

            for rev_name in reverse_entities:
                if rev_name in queried_entities:
                    continue
                queried_entities.add(rev_name)
                #  Disease/Pest 
                rev_type = None
                for n, t in ENTITY_LIST:
                    if n == rev_name and t in ('Disease', 'Pest'):
                        rev_type = t
                        break
                if rev_type:
                    rel_data = graph.run(
                        f"MATCH (e:{rev_type} {{name: $name}})-[r]->(n) "
                        f"RETURN type(r) AS rel, n.name AS related, n.description AS desc, n.id AS nid",
                        name=rev_name
                    ).data()
                    if rel_data:
                        rel_texts = []
                        for r in rel_data:
                            related_text = r['desc'] or r['nid'] or r['related']
                            rel_texts.append(f"{r['rel']}: {related_text}")
                            kg_sources.append(f"{r['rel']} → {r['related']}")
                        kg_answer_parts.append(f"【{rev_name}】{'；'.join(rel_texts)}")
            continue  #  Symptom/Part 

        # Disease/Pest → 属性查询（带 description）
        if resolved_type in ('Disease', 'Pest') and resolved_name not in queried_entities:
            queried_entities.add(resolved_name)
            results = graph.run(
                f"MATCH (e:{resolved_type} {{name: $entity_name}})-[r]->(n) "
                f"RETURN type(r) AS rel, n.name AS related, n.description AS desc, n.id AS nid",
                entity_name=resolved_name
            ).data()
            if results:
                rel_texts = []
                for r in results:
                    related_text = r['desc'] or r['nid'] or r['related']
                    rel_texts.append(f"{r['rel']}: {related_text}")
                    kg_sources.append(f"{r['rel']} → {r['related']}")
                kg_answer_parts.append(f"【{resolved_name}】{'；'.join(rel_texts)}")

    kg_answer = "\n".join(kg_answer_parts)
    
    # ===== 第二路：向量检索 =====
    query_vector = embedding_model.encode(question).tolist()
    vector_results = collection.query(
        query_embeddings=[query_vector],
        n_results=5
    )
    retrieved_texts = vector_results['documents'][0] if vector_results['documents'] else []
    vector_answer_parts = []
    for i, t in enumerate(retrieved_texts):
        vector_answer_parts.append(f"【文本片段{i+1}】{t}")
    vector_answer = "\n".join(vector_answer_parts)

    vector_sources = []
    metadatas = vector_results['metadatas'][0] if vector_results['metadatas'] else []
    for meta in metadatas:
        source_name = meta.get('source', 'unknown')
        vector_sources.append(f"[DOC] {source_name}")

    # ===== 上下文融合（结构化分组） =====
    context_parts = []
    if kg_answer_parts:
        context_parts.append("【结构化知识图谱】")
        context_parts.append(kg_answer)
    if vector_answer_parts:
        context_parts.append("【参考资料文本】")
        context_parts.append(vector_answer)

    context = "\n".join(context_parts).strip()
    if not context:
        context = "未找到相关知识。"
    
    #  prompt
    # 
    history_text = ""
    for msg in history:
        role = "" if msg.get('role') == 'user' else ""
        content = msg.get('content', '')
        history_text += f"{role}{content}\n"
    
    # 
    current_question = f"{question}"

    prompt = f"""
你是一个葡萄病虫害防治专家。请基于以下知识回答用户的问题。

【参考知识】
{context}

【对话历史】
{history_text}

【当前问题】
{current_question}

【回答要求】
1. 如果问题问"哪些"、"几种"、"什么病/虫"，请列出所有相关知识中提到的候选项，不要只给一个。
2. 如果问题要求对比两种病虫害，请分点对比它们的差异。
3. 如果问题涉及具体数值（剂量、温度、倍数），请从知识中精确引用，找不到时明确说未找到。
4. 如果知识中不包含答案，请明确说"根据现有知识暂时无法回答"。
5. 如果知识中有多种可能性（多个病害有相似症状），请列出所有可能并简要区分。
"""

    # DeepSeek API
    deepseek_client = OpenAI(api_key=os.getenv("DEEPSEEK_API_KEY"), base_url="https://api.deepseek.com")
    if not os.getenv("DEEPSEEK_API_KEY"):
        return "Service config error: no API Key", []

    try:
        response = deepseek_client.chat.completions.create(
            model='deepseek-chat',
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2048,
            temperature=0.7,
        )
        answer = response.choices[0].message.content
        all_sources = list(set(kg_sources + vector_sources))
        return answer, all_sources
    except Exception as e:
        print(f"API call failed: {e}")
        return "Sorry, unable to answer.", []

#api

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json()
    question = data.get('question', '')
    history = data.get('history', [])   # 
    
    if not question:
        return jsonify({'error': ''}), 400
    
    answer, sources = answer_question_with_sources(question, history)  #  history

    # 
    header = request.headers.get('Authorization', '')
    if header.startswith('Bearer '):
        from auth import decode_token
        payload = decode_token(header[7:])
        if payload:
            save_chat(payload['user_id'], question, answer, sources)

    return jsonify({
        'answer': answer,
        'question': question,
        'sources': sources
    })

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

@app.route('/api/debug', methods=['GET'])
def debug_state():
    return jsonify({
        'entity_list_size': len(ENTITY_LIST),
        'reverse_map_size': len(REVERSE_MAP),
        'embeddings_size': len(ENTITY_EMBEDDINGS),
        'entity_sample': ENTITY_LIST[:5] if ENTITY_LIST else [],
    })


@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'error': ''}), 400
    if len(username) < 2 or len(username) > 20:
        return jsonify({'error': ' 2-20 '}), 400
    if len(password) < 6:
        return jsonify({'error': ' 6 '}), 400

    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    ok = create_user(username, password_hash)
    if not ok:
        return jsonify({'error': ''}), 409

    user = get_user_by_username(username)
    token = create_token(user['id'], user['username'])
    return jsonify({'token': token, 'username': username})


@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'error': ''}), 400

    user = get_user_by_username(username)
    if not user:
        return jsonify({'error': ''}), 401
    if not bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
        return jsonify({'error': ''}), 401

    token = create_token(user['id'], user['username'])
    return jsonify({'token': token, 'username': username})


@app.route('/api/knowledge/list', methods=['GET'])
def knowledge_list():
    category = request.args.get('category', '')
    search = request.args.get('search', '')
    items = list_knowledge(
        category=category if category in ('disease', 'pest') else None,
        search=search if search else None,
    )
    return jsonify(items)


@app.route('/api/knowledge/<name>', methods=['GET'])
def knowledge_detail(name):
    item = get_knowledge(name)
    if not item:
        return jsonify({'error': ''}), 404
    return jsonify(item)


@app.route('/api/history', methods=['GET'])
@require_auth
def chat_history():
    user_id = request.user['user_id']
    records = get_history(user_id)
    return jsonify(records)







@app.route('/api/graph', methods=['GET'])
def get_graph():
    try:
        nodes_result = graph.run(
            "MATCH (n) RETURN coalesce(n.name, n.id, n.title, toString(id(n))) AS name, labels(n) AS labels, id(n) AS neo4j_id"
        ).data()
        edges_result = graph.run(
            "MATCH (a)-[r]->(b) RETURN coalesce(a.name, a.id, a.title, toString(id(a))) AS source, type(r) AS label, coalesce(b.name, b.id, b.title, toString(id(b))) AS target"
        ).data()

        nodes = []
        seen = set()
        for record in nodes_result:
            name = record['name']
            if not name or name in seen:
                continue
            seen.add(name)
            labels = record['labels']
            if 'Disease' in labels:
                group = 'Disease'
            elif 'Pest' in labels:
                group = 'Pest'
            elif 'Alias' in labels:
                group = 'Alias'
            elif 'Symptom' in labels:
                group = 'Symptom'
            elif 'Part' in labels:
                group = 'Part'
            elif 'Rule' in labels:
                group = 'Rule'
            elif 'Method' in labels:
                group = 'Method'
            elif 'Drug' in labels:
                group = 'Drug'
            elif 'Treatment' in labels:
                group = 'Treatment'
            elif 'Pathogen' in labels:
                group = 'Pathogen'
            elif 'Characteristic' in labels:
                group = 'Characteristic'
            elif 'Condition' in labels:
                group = 'Condition'
            elif 'Period' in labels:
                group = 'Period'
            elif 'Vector' in labels:
                group = 'Vector'
            else:
                group = 'Other'
            nodes.append({'id': name, 'label': name, 'group': group})

        edges = []
        edge_seen = set()
        for record in edges_result:
            sid = record['source']
            tid = record['target']
            if not sid or not tid:
                continue
            eid = f"{sid}-{record['label']}-{tid}"
            if eid in edge_seen:
                continue
            edge_seen.add(eid)
            edges.append({
                'id': eid,
                'source': sid,
                'target': tid,
                'label': record['label'],
            })

        return jsonify({'nodes': nodes, 'edges': edges})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':

    init_db()
    load_entities_from_neo4j()

    # 
    index_documents()
    
    print(" ...")
    print(" : http://localhost:5000")
    app.run(debug=True, port=5000)