# 登录系统 + 知识区 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-step. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给 grape_qa 添加 JWT 登录系统（游客/用户）和轮播卡片知识区。

**Architecture:** 后端新增 SQLite 用户表 + JWT 认证 + 知识解析模块；前端新增 Vue Router 多页面架构，App.vue 改为 NavBar + router-view 壳结构，用 provide/inject 管理认证状态。

**Tech Stack:** Flask + SQLite + PyJWT + bcrypt (后端), Vue 3 + Element Plus + Vue Router (前端)

---

### Task 1: 安装缺失依赖

**Files:**
- Modify: `C:\grape_qa\frontend\package.json` (implicit, npm install)

- [ ] **Step 1: 安装后端依赖 PyJWT**

```bash
cd /c/grape_qa && source venv/Scripts/activate && pip install pyjwt && deactivate
```

- [ ] **Step 2: 安装前端依赖 vue-router**

```bash
cd /c/grape_qa/frontend && npm install vue-router@4
```

- [ ] **Step 3: 验证安装**

```bash
cd /c/grape_qa && source venv/Scripts/activate && python -c "import jwt; print('PyJWT OK')" && deactivate
cd /c/grape_qa/frontend && node -e "require('vue-router'); console.log('vue-router OK')"
```

---

### Task 2: 创建 db.py — SQLite 数据库层

**Files:**
- Create: `C:\grape_qa\db.py`

- [ ] **Step 1: 创建 db.py**

```python
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "users.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            sources TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    conn.close()


def create_user(username, password_hash):
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, password_hash),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def get_user_by_username(username):
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return dict(row) if row else None


def save_chat(user_id, question, answer, sources):
    import json
    conn = get_conn()
    conn.execute(
        "INSERT INTO chat_history (user_id, question, answer, sources) VALUES (?, ?, ?, ?)",
        (user_id, question, answer, json.dumps(sources, ensure_ascii=False)),
    )
    conn.commit()
    conn.close()


def get_history(user_id):
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, question, answer, sources, created_at FROM chat_history WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,),
    ).fetchall()
    conn.close()
    import json
    return [
        {
            "id": r["id"],
            "question": r["question"],
            "answer": r["answer"],
            "sources": json.loads(r["sources"]) if r["sources"] else [],
            "created_at": r["created_at"],
        }
        for r in rows
    ]
```

- [ ] **Step 2: 验证数据库创建**

```bash
cd /c/grape_qa && source venv/Scripts/activate && python -c "from db import init_db; init_db(); print('DB OK')" && deactivate
```

---

### Task 3: 创建 auth.py — JWT 认证

**Files:**
- Create: `C:\grape_qa\auth.py`

- [ ] **Step 1: 创建 auth.py**

```python
import jwt
import os
import datetime
from functools import wraps
from flask import request, jsonify

SECRET_KEY = os.environ.get("JWT_SECRET", "grape-qa-secret-key-change-in-production")


def create_token(user_id, username):
    payload = {
        "user_id": user_id,
        "username": username,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(days=7),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def decode_token(token):
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return jsonify({"error": "未提供认证令牌"}), 401
        token = header[7:]
        payload = decode_token(token)
        if payload is None:
            return jsonify({"error": "令牌无效或已过期"}), 401
        request.user = payload
        return f(*args, **kwargs)

    return decorated
```

---

### Task 4: 添加注册/登录 API

**Files:**
- Modify: `C:\grape_qa\app.py`

- [ ] **Step 1: 在 app.py 顶部添加导入**

在 `app.py` 现有 import 之后（`from langchain_text_splitters import RecursiveCharacterTextSplitter` 之后），添加：

```python
import bcrypt
from db import init_db, create_user, get_user_by_username
from auth import create_token, require_auth
```

- [ ] **Step 2: 在 `__main__` 块中添加 `init_db()` 调用**

在 `if __name__ == '__main__':` 下方，`load_entities_from_neo4j()` 之前添加：

```python
init_db()
```

- [ ] **Step 3: 添加注册端点**

在 `def health()` 之后，`if __name__ == '__main__':` 之前添加：

```python
@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'error': '用户名和密码不能为空'}), 400
    if len(username) < 2 or len(username) > 20:
        return jsonify({'error': '用户名长度 2-20 个字符'}), 400
    if len(password) < 6:
        return jsonify({'error': '密码至少 6 位'}), 400

    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    ok = create_user(username, password_hash)
    if not ok:
        return jsonify({'error': '用户名已存在'}), 409

    user = get_user_by_username(username)
    token = create_token(user['id'], user['username'])
    return jsonify({'token': token, 'username': username})


@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'error': '用户名和密码不能为空'}), 400

    user = get_user_by_username(username)
    if not user:
        return jsonify({'error': '用户名或密码错误'}), 401
    if not bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
        return jsonify({'error': '用户名或密码错误'}), 401

    token = create_token(user['id'], user['username'])
    return jsonify({'token': token, 'username': username})
```

- [ ] **Step 4: 测试注册 API**

```bash
cd /c/grape_qa && source venv/Scripts/activate && python app.py &
sleep 3
curl -s -X POST http://localhost:5000/api/register -H "Content-Type: application/json" -d '{"username":"test","password":"123456"}'
# Expected: {"token":"...", "username":"test"}
```

测试完成后停止 Flask 进程。

---

### Task 5: 创建 knowledge.py — 知识解析

**Files:**
- Create: `C:\grape_qa\knowledge.py`

- [ ] **Step 1: 创建 knowledge.py**

```python
import os
import re
import glob

DATA_DIR = os.path.join(os.path.dirname(__file__), "data", "texts")
_cache = None  # {name: {name, category, summary, sections}}


def _parse_all():
    global _cache
    if _cache is not None:
        return _cache

    _cache = {}
    if not os.path.exists(DATA_DIR):
        return _cache

    for file_path in glob.glob(os.path.join(DATA_DIR, "*.txt")):
        name = os.path.basename(file_path).replace(".txt", "")
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        category = "disease" if "病" in name else "pest"
        lines = content.strip().split("\n")
        summary = ""
        for line in lines:
            line = line.strip()
            if line and not re.match(r"^\d+\.", line):
                summary = line[:120]
                break

        sections = []
        parts = re.split(r"\n(?=\d+\.\s)", content)
        for part in parts:
            m = re.match(r"(\d+)\.\s*(.+?)[：:]", part)
            if m:
                title = m.group(2).strip()
                body = part[m.end():].strip()
                sections.append({"title": title, "content": body})

        _cache[name] = {
            "name": name,
            "category": category,
            "summary": summary,
            "sections": sections,
        }

    return _cache


def list_knowledge(category=None, search=None):
    all_data = _parse_all()
    result = []
    for item in all_data.values():
        if category and item["category"] != category:
            continue
        if search and search.lower() not in item["name"].lower():
            continue
        result.append({
            "name": item["name"],
            "category": item["category"],
            "summary": item["summary"],
        })
    return result


def get_knowledge(name):
    all_data = _parse_all()
    return all_data.get(name)
```

---

### Task 6: 添加知识 API 端点

**Files:**
- Modify: `C:\grape_qa\app.py`

- [ ] **Step 1: 添加导入**

在 app.py 现有导入区域添加：

```python
from knowledge import list_knowledge, get_knowledge
```

- [ ] **Step 2: 添加端点**

在 login 端点之后，`if __name__` 之前添加：

```python
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
        return jsonify({'error': '未找到该病虫害信息'}), 404
    return jsonify(item)
```

- [ ] **Step 3: 测试知识 API**

```bash
cd /c/grape_qa && source venv/Scripts/activate && python app.py &
sleep 3
curl -s http://localhost:5000/api/knowledge/list | python -m json.tool | head -20
# Expected: JSON array with disease/pest items
```

测试完成后停止 Flask 进程。

---

### Task 7: 添加历史 API + 聊天记录保存

**Files:**
- Modify: `C:\grape_qa\app.py`

- [ ] **Step 1: 添加导入**

```python
from db import save_chat, get_history
```

- [ ] **Step 2: 添加历史端点**

在 knowledge_detail 之后添加：

```python
@app.route('/api/history', methods=['GET'])
@require_auth
def chat_history():
    user_id = request.user['user_id']
    records = get_history(user_id)
    return jsonify(records)
```

- [ ] **Step 3: 修改 `/api/chat` 端点，在回答后保存历史**

在 `answer_question_with_sources` 调用返回之后、`return jsonify(...)` 之前，检查用户是否登录，若是则保存记录。

修改后的 chat 端点：

```python
@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json()
    question = data.get('question', '')
    history = data.get('history', [])

    if not question:
        return jsonify({'error': '请输入问题'}), 400

    answer, sources = answer_question_with_sources(question, history)

    # 如果是登录用户，保存对话历史
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
```

---

### Task 8: 前端基础 — Router + Theme

**Files:**
- Create: `C:\grape_qa\frontend\src\router\index.js`
- Create: `C:\grape_qa\frontend\src\styles\theme.css`
- Modify: `C:\grape_qa\frontend\src\main.js`

- [ ] **Step 1: 创建 theme.css**

```css
:root {
  --grape-purple: #722ed1;
  --vine-green: #2d8c4a;
  --gold: #d4a017;
  --bg-dark: #1a1a2e;
  --surface-dark: rgba(255, 255, 255, 0.06);
  --text-primary: #e0e0e0;
  --text-secondary: #a0a0a0;
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  background: var(--bg-dark);
  color: var(--text-primary);
  font-family: 'Helvetica Neue', Helvetica, 'PingFang SC', 'Microsoft YaHei', sans-serif;
}

/* Route transition */
.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: all 0.3s ease;
}
.fade-slide-enter-from {
  opacity: 0;
  transform: translateX(20px);
}
.fade-slide-leave-to {
  opacity: 0;
  transform: translateX(-20px);
}

/* Glass card */
.glass-card {
  background: rgba(255, 255, 255, 0.06);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 16px;
  transition: transform 0.3s ease, box-shadow 0.3s ease;
}
.glass-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.3);
}
```

- [ ] **Step 2: 创建 router/index.js**

```javascript
import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', name: 'Home', component: () => import('@/views/Home.vue') },
  { path: '/login', name: 'Login', component: () => import('@/views/Login.vue') },
  { path: '/chat', name: 'Chat', component: () => import('@/views/Chat.vue') },
  { path: '/knowledge', name: 'Knowledge', component: () => import('@/views/Knowledge.vue') },
  { path: '/knowledge/:name', name: 'KnowledgeDetail', component: () => import('@/views/KnowledgeDetail.vue') },
  { path: '/history', name: 'History', component: () => import('@/views/History.vue'), meta: { requiresAuth: true } },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
```

- [ ] **Step 3: 修改 main.js 添加 router 和主题**

```javascript
import { createApp } from 'vue'
import App from './App.vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import 'element-plus/theme-chalk/dark/css-vars.css'
import router from './router'
import './styles/theme.css'

const app = createApp(App)
app.use(ElementPlus)
app.use(router)
app.mount('#app')
```

---

### Task 9: 重构 App.vue + 创建 NavBar

**Files:**
- Modify: `C:\grape_qa\frontend\src\App.vue`
- Create: `C:\grape_qa\frontend\src\components\NavBar.vue`

- [ ] **Step 1: 创建 NavBar.vue**

```vue
<template>
  <el-menu
    :default-active="currentRoute"
    mode="horizontal"
    :ellipsis="false"
    class="navbar"
    background-color="#1a1a2e"
    text-color="#a0a0a0"
    active-text-color="#d4a017"
  >
    <div class="nav-brand" @click="$router.push('/')">
      🍇 葡萄病虫害知识系统
    </div>
    <div class="nav-links">
      <el-menu-item index="/chat" @click="$router.push('/chat')">💬 智能问答</el-menu-item>
      <el-menu-item index="/knowledge" @click="$router.push('/knowledge')">📚 知识区</el-menu-item>
      <el-menu-item v-if="user" index="/history" @click="$router.push('/history')">📋 历史记录</el-menu-item>
    </div>
    <div class="nav-user">
      <template v-if="user">
        <el-dropdown>
          <span class="username">{{ user.username }}</span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="logout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </template>
      <template v-else>
        <span class="guest-tag">游客模式</span>
        <el-button type="primary" size="small" @click="$router.push('/login')">登录</el-button>
      </template>
    </div>
  </el-menu>
</template>

<script>
export default {
  inject: ['user', 'logout'],
  computed: {
    currentRoute() {
      return this.$route.path
    },
  },
}
</script>

<style scoped>
.navbar {
  display: flex;
  align-items: center;
  padding: 0 24px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06) !important;
}
.nav-brand {
  font-size: 16px;
  font-weight: 700;
  color: #fff;
  cursor: pointer;
  margin-right: 32px;
  white-space: nowrap;
}
.nav-links {
  display: flex;
  flex: 1;
  border-bottom: none !important;
}
.nav-user {
  display: flex;
  align-items: center;
  gap: 12px;
}
.username {
  color: #d4a017;
  cursor: pointer;
  font-size: 14px;
}
.guest-tag {
  color: #909399;
  font-size: 13px;
}
</style>
```

- [ ] **Step 2: 重写 App.vue 为壳结构**

```vue
<template>
  <el-config-provider>
    <div id="app-shell">
      <NavBar />
      <main class="main-content">
        <router-view v-slot="{ Component }">
          <transition name="fade-slide" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>
    </div>
  </el-config-provider>
</template>

<script>
import NavBar from './components/NavBar.vue'

export default {
  components: { NavBar },
  provide() {
    return {
      user: this.user,
      token: this.token,
      login: this.login,
      logout: this.logout,
      register: this.register,
    }
  },
  data() {
    const saved = JSON.parse(localStorage.getItem('grape_user') || 'null')
    return {
      user: saved,
      token: localStorage.getItem('grape_token') || '',
    }
  },
  watch: {
    $route(to) {
      if (to.meta.requiresAuth && !this.user) {
        this.$router.push('/login')
      }
    },
  },
  methods: {
    login(token, username) {
      this.token = token
      this.user = { username }
      localStorage.setItem('grape_token', token)
      localStorage.setItem('grape_user', JSON.stringify({ username }))
    },
    logout() {
      this.token = ''
      this.user = null
      localStorage.removeItem('grape_token')
      localStorage.removeItem('grape_user')
      this.$router.push('/')
    },
    register(token, username) {
      this.login(token, username)
    },
  },
}
</script>

<style>
#app-shell {
  min-height: 100vh;
  background: var(--bg-dark);
}
.main-content {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
}
</style>
```

---

### Task 10: 创建 useAuth composable

**Files:**
- Create: `C:\grape_qa\frontend\src\composables\useAuth.js`

- [ ] **Step 1: 创建 useAuth.js**

```javascript
import { inject } from 'vue'

export function useAuth() {
  const user = inject('user')
  const token = inject('token')
  const login = inject('login')
  const logout = inject('logout')
  const register = inject('register')
  return { user, token, login, logout, register }
}
```

---

### Task 11: 创建 Home.vue — 首页

**Files:**
- Create: `C:\grape_qa\frontend\src\views\Home.vue`

- [ ] **Step 1: 创建 Home.vue**

```vue
<template>
  <div class="home">
    <div class="hero">
      <div class="hero-icon">🍇</div>
      <h1>葡萄病虫害知识系统</h1>
      <p class="hero-desc">基于知识图谱的智能农业问答与病虫害科普平台</p>
      <div class="hero-actions">
        <el-button type="primary" size="large" @click="$router.push('/knowledge')">📚 开始探索</el-button>
        <el-button size="large" @click="$router.push('/chat')">💬 智能问答</el-button>
      </div>
    </div>
    <div class="features">
      <div class="feature glass-card">
        <div class="feature-icon">🧠</div>
        <h3>知识图谱</h3>
        <p>基于 Neo4j 构建的葡萄病虫害关系网络，精准定位问题答案</p>
      </div>
      <div class="feature glass-card">
        <div class="feature-icon">🔍</div>
        <h3>智能检索</h3>
        <p>向量语义检索 + 图谱关系检索，双路召回确保答案质量</p>
      </div>
      <div class="feature glass-card">
        <div class="feature-icon">📖</div>
        <h3>科普百科</h3>
        <p>覆盖 40 种葡萄病虫害的完整知识库，症状、病原、防治一应俱全</p>
      </div>
    </div>
  </div>
</template>

<script>
export default { name: 'Home' }
</script>

<style scoped>
.home { text-align: center; }
.hero { padding: 60px 20px 40px; }
.hero-icon { font-size: 64px; margin-bottom: 16px; }
.hero h1 { font-size: 32px; font-weight: 700; color: #fff; margin-bottom: 8px; }
.hero-desc { color: var(--text-secondary); font-size: 16px; margin-bottom: 32px; }
.hero-actions { display: flex; gap: 16px; justify-content: center; }
.features { display: grid; grid-template-columns: repeat(3, 1fr); gap: 24px; margin-top: 48px; }
.feature { padding: 32px 24px; text-align: center; }
.feature-icon { font-size: 36px; margin-bottom: 12px; }
.feature h3 { color: #fff; margin-bottom: 8px; font-size: 18px; }
.feature p { color: var(--text-secondary); font-size: 14px; line-height: 1.6; }
@media (max-width: 768px) {
  .features { grid-template-columns: 1fr; }
}
</style>
```

---

### Task 12: 创建 Login.vue — 登录/注册

**Files:**
- Create: `C:\grape_qa\frontend\src\views\Login.vue`

- [ ] **Step 1: 创建 Login.vue**

```vue
<template>
  <div class="login-page">
    <div class="login-card glass-card">
      <h2>🍇 欢迎</h2>
      <el-tabs v-model="mode" class="tabs">
        <el-tab-pane label="登录" name="login" />
        <el-tab-pane label="注册" name="register" />
      </el-tabs>
      <el-form :model="form" label-position="top">
        <el-form-item label="用户名">
          <el-input v-model="form.username" placeholder="请输入用户名" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" show-password placeholder="请输入密码" />
        </el-form-item>
        <el-form-item v-if="mode === 'register'" label="确认密码">
          <el-input v-model="form.confirm" type="password" show-password placeholder="请再次输入密码" />
        </el-form-item>
        <el-button type="primary" :loading="loading" class="submit-btn" @click="submit">
          {{ mode === 'login' ? '登 录' : '注 册' }}
        </el-button>
      </el-form>
      <div class="guest-link" @click="guestEnter">游客模式：直接进入系统</div>
    </div>
  </div>
</template>

<script>
import axios from 'axios'

export default {
  name: 'Login',
  inject: ['login', 'register'],
  data() {
    return {
      mode: 'login',
      loading: false,
      form: { username: '', password: '', confirm: '' },
    }
  },
  methods: {
    async submit() {
      if (!this.form.username || !this.form.password) {
        this.$message.warning('请填写用户名和密码')
        return
      }
      if (this.mode === 'register') {
        if (this.form.password.length < 6) {
          this.$message.warning('密码至少 6 位')
          return
        }
        if (this.form.password !== this.form.confirm) {
          this.$message.warning('两次密码不一致')
          return
        }
      }
      this.loading = true
      try {
        const url = this.mode === 'login' ? '/api/login' : '/api/register'
        const res = await axios.post(`http://localhost:5000${url}`, {
          username: this.form.username,
          password: this.form.password,
        })
        const { token, username } = res.data
        if (this.mode === 'login') {
          this.login(token, username)
        } else {
          this.register(token, username)
        }
        this.$message.success(this.mode === 'login' ? '登录成功' : '注册成功')
        this.$router.push('/chat')
      } catch (err) {
        const msg = err.response?.data?.error || '操作失败'
        this.$message.error(msg)
      } finally {
        this.loading = false
      }
    },
    guestEnter() {
      this.$router.push('/chat')
    },
  },
}
</script>

<style scoped>
.login-page {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: calc(100vh - 140px);
}
.login-card {
  width: 400px;
  padding: 40px;
}
.login-card h2 { text-align: center; margin-bottom: 8px; color: #fff; }
.tabs { margin-bottom: 8px; }
.submit-btn { width: 100%; margin-top: 8px; }
.guest-link {
  text-align: center;
  margin-top: 16px;
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 13px;
}
.guest-link:hover { color: var(--grape-purple); }
</style>
```

---

### Task 13: 创建 Chat.vue — 问答页（从 App.vue 提取）

**Files:**
- Create: `C:\grape_qa\frontend\src\views\Chat.vue`

- [ ] **Step 1: 创建 Chat.vue**

```vue
<template>
  <div class="chat-page">
    <h2 class="page-title">💬 智能问答</h2>
    <div class="chat-container glass-card">
      <div class="history-area" v-if="messages.length">
        <div v-for="(msg, idx) in messages" :key="idx" :class="['message', msg.role]">
          <div class="avatar">
            <el-avatar :size="40" :src="msg.role === 'user' ? userAvatar : botAvatar" />
          </div>
          <div class="content">
            <div class="role">{{ msg.role === 'user' ? '我' : '助手' }}</div>
            <div class="text" v-html="formatAnswer(msg.content)"></div>
            <div v-if="msg.sources && msg.sources.length" class="sources">
              <el-divider content-position="left">参考来源</el-divider>
              <el-tag v-for="(src, i) in msg.sources" :key="i" size="small">{{ src }}</el-tag>
            </div>
          </div>
        </div>
      </div>
      <div class="input-area">
        <el-input
          v-model="question"
          type="textarea"
          :rows="3"
          placeholder="请输入问题，例如：葡萄黑痘病有什么症状？"
          @keydown.ctrl.enter="ask"
        />
        <el-button type="primary" :loading="loading" @click="ask" style="margin-top: 10px;">提问</el-button>
      </div>
    </div>
  </div>
</template>

<script>
import axios from 'axios'
import { useAuth } from '@/composables/useAuth'

export default {
  name: 'Chat',
  data() {
    return {
      question: '',
      loading: false,
      messages: [],
      userAvatar: 'https://cube.elemecdn.com/3/7c/3ea6beec64369c2642b92c6726f1epng.png',
      botAvatar: 'https://cube.elemecdn.com/0/88/03b0d39583f48206768a7534e55bcpng.png',
    }
  },
  methods: {
    formatAnswer(text) {
      return text.replace(/\n/g, '<br>')
    },
    async ask() {
      if (!this.question.trim()) {
        this.$message.warning('请输入问题')
        return
      }
      this.messages.push({ role: 'user', content: this.question })
      const currentQuestion = this.question
      this.question = ''
      this.loading = true
      try {
        const history = this.messages.slice(0, -1)
        const headers = {}
        const { token } = useAuth()
        if (token) headers['Authorization'] = `Bearer ${token}`
        const res = await axios.post('http://localhost:5000/api/chat', {
          question: currentQuestion,
          history,
        }, { headers })
        this.messages.push({
          role: 'assistant',
          content: res.data.answer,
          sources: res.data.sources || [],
        })
      } catch {
        this.$message.error('请求失败，请检查后端服务')
        this.messages.push({ role: 'assistant', content: '抱歉，服务暂时不可用。', sources: [] })
      } finally {
        this.loading = false
      }
    },
  },
}
</script>

<style scoped>
.chat-page { max-width: 900px; margin: 0 auto; }
.page-title { font-size: 22px; color: #fff; margin-bottom: 20px; }
.chat-container { padding: 24px; }
.history-area { max-height: 500px; overflow-y: auto; margin-bottom: 20px; }
.message { display: flex; margin-bottom: 20px; }
.message.user { flex-direction: row-reverse; }
.message .avatar { margin: 0 10px; }
.message .content { max-width: 70%; padding: 12px; border-radius: 12px; background: rgba(255,255,255,.06); color: #e0e0e0; }
.message.user .content { background: rgba(114,46,209,.25); }
.role { font-weight: bold; margin-bottom: 5px; font-size: 12px; color: var(--text-secondary); }
.text { line-height: 1.5; }
.sources { margin-top: 10px; font-size: 12px; }
.input-area { margin-top: 20px; }
</style>
```

---

### Task 14: 创建 Knowledge.vue + KnowledgeCard.vue

**Files:**
- Create: `C:\grape_qa\frontend\src\views\Knowledge.vue`
- Create: `C:\grape_qa\frontend\src\components\KnowledgeCard.vue`

- [ ] **Step 1: 创建 KnowledgeCard.vue**

```vue
<template>
  <div class="k-card glass-card" :class="{ active: active }" @click="$emit('click')">
    <div class="k-card-bg" :class="category"></div>
    <div class="k-card-overlay"></div>
    <div class="k-card-body">
      <span class="k-tag" :class="category">{{ category === 'disease' ? '🦠 病害' : '🐛 虫害' }}</span>
      <h3>{{ name }}</h3>
      <p v-if="summary">{{ summary }}</p>
      <div class="k-hint">点击查看详情 →</div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'KnowledgeCard',
  props: { name: String, category: String, summary: String, active: Boolean },
  emits: ['click'],
}
</script>

<style scoped>
.k-card {
  position: relative;
  width: 320px;
  height: 400px;
  border-radius: 20px;
  overflow: hidden;
  cursor: pointer;
  flex-shrink: 0;
  transition: all 0.4s ease;
}
.k-card:not(.active) {
  transform: scale(0.85);
  opacity: 0.5;
  filter: blur(1px);
}
.k-card-bg {
  position: absolute;
  inset: 0;
}
.k-card-bg.disease {
  background: linear-gradient(135deg, #2d1b3a, #4a2040, #6b2a4a);
}
.k-card-bg.pest {
  background: linear-gradient(135deg, #1a2a1e, #1e3a2a, #2a4a30);
}
.k-card-bg::after {
  content: '';
  position: absolute;
  inset: 0;
  background:
    radial-gradient(ellipse at 30% 30%, rgba(255,255,255,.05) 0%, transparent 60%),
    radial-gradient(ellipse at 70% 70%, rgba(255,255,255,.03) 0%, transparent 60%);
}
.k-card-overlay {
  position: absolute;
  inset: 0;
  background: rgba(0,0,0,.55);
}
.k-card-body {
  position: relative;
  z-index: 2;
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  padding: 28px 22px;
  color: #fff;
}
.k-tag {
  display: inline-block;
  padding: 4px 14px;
  border-radius: 14px;
  font-size: 12px;
  align-self: flex-start;
  margin-bottom: 12px;
}
.k-tag.disease { background: rgba(245,108,108,.3); }
.k-tag.pest { background: rgba(64,158,255,.3); }
.k-card-body h3 { font-size: 22px; font-weight: 700; margin-bottom: 8px; }
.k-card-body p {
  font-size: 13px;
  line-height: 1.6;
  opacity: .85;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.k-hint { font-size: 12px; opacity: .5; margin-top: 12px; }
</style>
```

- [ ] **Step 2: 创建 Knowledge.vue**

```vue
<template>
  <div class="knowledge-page">
    <h2 class="page-title">📚 知识百科</h2>

    <div class="search-bar">
      <el-input v-model="search" placeholder="搜索病虫害名称..." clearable @clear="fetchList" @keydown.enter="fetchList" />
      <el-button type="primary" @click="fetchList">搜索</el-button>
    </div>

    <div class="filter-tags">
      <span :class="['tag', { active: category === '' }]" @click="category = ''; fetchList()">全部</span>
      <span :class="['tag', { active: category === 'disease' }]" @click="category = 'disease'; fetchList()">🦠 病害</span>
      <span :class="['tag', { active: category === 'pest' }]" @click="category = 'pest'; fetchList()">🐛 虫害</span>
    </div>

    <div v-if="loading" class="loading-area">
      <el-skeleton :rows="3" animated />
    </div>

    <div v-else-if="items.length" class="carousel-wrap">
      <div class="arrow left" @click="prev">◀</div>

      <div class="carousel-track">
        <KnowledgeCard
          v-for="(item, i) in displayedItems"
          :key="item.name"
          :name="item.name"
          :category="item.category"
          :summary="item.summary"
          :active="i === centerIndex"
          @click="goDetail(item.name)"
        />
      </div>

      <div class="arrow right" @click="next">▶</div>
    </div>

    <div v-if="items.length" class="dots">
      <span v-for="(_, i) in items" :key="i" :class="['dot', { active: i === currentIndex }]" @click="currentIndex = i"></span>
    </div>

    <el-empty v-if="!loading && !items.length" description="未找到匹配的病虫害" />
  </div>
</template>

<script>
import axios from 'axios'
import KnowledgeCard from '@/components/KnowledgeCard.vue'

export default {
  name: 'Knowledge',
  components: { KnowledgeCard },
  data() {
    return { items: [], category: '', search: '', currentIndex: 0, loading: false }
  },
  computed: {
    centerIndex() { return 1 },  // center slot in 3-card display
    displayedItems() {
      const len = this.items.length
      if (len === 0) return []
      if (len === 1) return this.items
      if (len === 2) return [...this.items, ...this.items].slice(0, 3)
      const prev = (this.currentIndex - 1 + len) % len
      const next = (this.currentIndex + 1) % len
      return [
        this.items[prev],
        this.items[this.currentIndex],
        this.items[next],
      ]
    },
  },
  async mounted() { await this.fetchList() },
  methods: {
    async fetchList() {
      this.loading = true
      try {
        const params = {}
        if (this.category) params.category = this.category
        if (this.search) params.search = this.search
        const res = await axios.get('http://localhost:5000/api/knowledge/list', { params })
        this.items = res.data
        this.currentIndex = 0
      } catch {
        this.$message.error('获取知识列表失败')
      } finally {
        this.loading = false
      }
    },
    prev() {
      const len = this.items.length
      this.currentIndex = (this.currentIndex - 1 + len) % len
    },
    next() {
      const len = this.items.length
      this.currentIndex = (this.currentIndex + 1) % len
    },
    goDetail(name) {
      this.$router.push(`/knowledge/${encodeURIComponent(name)}`)
    },
  },
}
</script>

<style scoped>
.knowledge-page { max-width: 1000px; margin: 0 auto; }
.page-title { font-size: 22px; color: #fff; margin-bottom: 20px; }
.search-bar { display: flex; gap: 10px; margin-bottom: 16px; }
.filter-tags { display: flex; gap: 10px; justify-content: center; margin-bottom: 32px; }
.tag {
  padding: 6px 20px;
  border-radius: 20px;
  background: rgba(255,255,255,.06);
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 14px;
  transition: all .2s;
}
.tag.active { background: var(--grape-purple); color: #fff; }
.tag:hover:not(.active) { background: rgba(255,255,255,.12); }

.carousel-wrap { position: relative; display: flex; align-items: center; justify-content: center; min-height: 440px; }
.carousel-track { display: flex; gap: 20px; align-items: center; justify-content: center; }
.arrow {
  position: absolute;
  z-index: 10;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: rgba(255,255,255,.1);
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: #fff;
  font-size: 16px;
  transition: background .2s;
}
.arrow:hover { background: rgba(255,255,255,.2); }
.arrow.left { left: -20px; }
.arrow.right { right: -20px; }

.dots { display: flex; gap: 8px; justify-content: center; margin-top: 20px; }
.dot { width: 8px; height: 8px; border-radius: 50%; background: rgba(255,255,255,.15); cursor: pointer; transition: all .2s; }
.dot.active { width: 24px; border-radius: 4px; background: var(--grape-purple); }

.loading-area { padding: 40px; }
</style>
```

---

### Task 15: 创建 KnowledgeDetail.vue — 知识详情

**Files:**
- Create: `C:\grape_qa\frontend\src\views\KnowledgeDetail.vue`

- [ ] **Step 1: 创建 KnowledgeDetail.vue**

```vue
<template>
  <div class="detail-page">
    <div class="back-link" @click="$router.push('/knowledge')">← 返回知识区</div>

    <div v-if="loading">
      <el-skeleton :rows="8" animated />
    </div>

    <div v-else-if="item" class="detail-content">
      <div class="detail-header glass-card">
        <span class="d-tag" :class="item.category">{{ item.category === 'disease' ? '🦠 病害' : '🐛 虫害' }}</span>
        <h2>{{ item.name }}</h2>
        <p v-if="item.summary" class="d-summary">{{ item.summary }}</p>
      </div>

      <div v-for="(sec, i) in item.sections" :key="i" class="section glass-card">
        <h3>{{ sec.title }}</h3>
        <div class="section-body">{{ sec.content }}</div>
      </div>
    </div>

    <el-empty v-else description="未找到该病虫害信息" />
  </div>
</template>

<script>
import axios from 'axios'

export default {
  name: 'KnowledgeDetail',
  data() { return { item: null, loading: false } },
  async mounted() {
    this.loading = true
    try {
      const name = decodeURIComponent(this.$route.params.name)
      const res = await axios.get(`http://localhost:5000/api/knowledge/${name}`)
      this.item = res.data
    } catch {
      this.$message.error('获取详情失败')
    } finally {
      this.loading = false
    }
  },
}
</script>

<style scoped>
.detail-page { max-width: 800px; margin: 0 auto; }
.back-link { color: var(--grape-purple); cursor: pointer; margin-bottom: 20px; font-size: 14px; }
.back-link:hover { color: #9b59ff; }
.detail-header { padding: 32px; margin-bottom: 24px; }
.d-tag { display: inline-block; padding: 4px 14px; border-radius: 14px; font-size: 12px; margin-bottom: 12px; }
.d-tag.disease { background: rgba(245,108,108,.25); color: #f56c6c; }
.d-tag.pest { background: rgba(64,158,255,.25); color: #409eff; }
.detail-header h2 { font-size: 26px; font-weight: 700; color: #fff; margin-bottom: 10px; }
.d-summary { color: var(--text-secondary); line-height: 1.6; }
.section { padding: 28px 32px; margin-bottom: 16px; }
.section h3 { font-size: 18px; color: var(--gold); margin-bottom: 14px; border-left: 3px solid var(--grape-purple); padding-left: 12px; }
.section-body { color: #ccc; line-height: 1.8; font-size: 14px; white-space: pre-wrap; }
</style>
```

---

### Task 16: 创建 History.vue — 历史记录

**Files:**
- Create: `C:\grape_qa\frontend\src\views\History.vue`

- [ ] **Step 1: 创建 History.vue**

```vue
<template>
  <div class="history-page">
    <h2 class="page-title">📋 问答历史</h2>

    <div v-if="loading"><el-skeleton :rows="5" animated /></div>

    <div v-else-if="records.length">
      <div v-for="r in records" :key="r.id" class="record glass-card">
        <div class="record-q">
          <span class="label">Q</span>
          {{ r.question }}
        </div>
        <div class="record-a">
          <span class="label">A</span>
          <span v-html="r.answer.replace(/\n/g, '<br>')"></span>
        </div>
        <div class="record-meta">{{ r.created_at }}</div>
      </div>
    </div>

    <el-empty v-else description="暂无问答记录" />
  </div>
</template>

<script>
import axios from 'axios'
import { useAuth } from '@/composables/useAuth'

export default {
  name: 'History',
  data() { return { records: [], loading: false } },
  async mounted() {
    this.loading = true
    try {
      const { token } = useAuth()
      const res = await axios.get('http://localhost:5000/api/history', {
        headers: { Authorization: `Bearer ${token}` },
      })
      this.records = res.data
    } catch {
      this.$message.error('获取历史记录失败')
    } finally {
      this.loading = false
    }
  },
}
</script>

<style scoped>
.history-page { max-width: 800px; margin: 0 auto; }
.page-title { font-size: 22px; color: #fff; margin-bottom: 20px; }
.record { padding: 20px 24px; margin-bottom: 16px; }
.record-q { margin-bottom: 12px; line-height: 1.6; color: #e0e0e0; }
.record-a { color: var(--text-secondary); line-height: 1.6; }
.label { display: inline-block; width: 24px; height: 24px; border-radius: 50%; background: var(--grape-purple); color: #fff; text-align: center; line-height: 24px; font-size: 12px; font-weight: 700; margin-right: 8px; vertical-align: top; }
.record-meta { font-size: 12px; color: #666; margin-top: 12px; }
</style>
```

---

### Task 17: 集成测试

- [ ] **Step 1: 启动后端**

```bash
cd /c/grape_qa && source venv/Scripts/activate && python app.py &
```

- [ ] **Step 2: 启动前端**

```bash
cd /c/grape_qa/frontend && npm run dev &
```

- [ ] **Step 3: 验证功能清单**

1. 访问 `http://localhost:5173` → 看到首页 Landing
2. 点击"登录" → 进入登录页
3. 注册一个新用户 → 成功后跳转到问答页
4. 发一个问题 → 得到回答
5. 点击"历史记录" → 看到刚才的问题
6. 点击"知识区" → 看到轮播卡片
7. 点击分类标签筛选 → 卡片列表变化
8. 点击箭头切换卡片 → 轮播正常
9. 点击卡片 → 进入详情页
10. 退出登录 → 导航栏变化，历史记录不可见
11. 游客模式进入 → 可以问答和浏览知识，但看不到历史
