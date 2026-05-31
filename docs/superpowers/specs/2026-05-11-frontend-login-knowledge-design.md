# 前端功能增强：登录系统 + 知识区

2026-05-11 | 已确认

## 目标

给 grape_qa 添加两个功能模块：
1. **登录系统** — 游客（可问答+浏览知识） vs 注册用户（额外可看历史记录）
2. **知识区** — 轮播卡片浏览 40 种葡萄病虫害，数据来自 `data/texts/`

## 技术方案

- 前端：Vue 3 + Element Plus + Vue Router（已有依赖）
- 后端：Flask + SQLite + PyJWT + bcrypt
- 认证：JWT，存 localStorage，请求带 `Authorization: Bearer <token>`

## 前端路由

| 路由 | 页面 | 权限 |
|------|------|------|
| `/` | 首页 Landing | 所有人 |
| `/login` | 登录/注册 | 所有人 |
| `/chat` | 智能问答（现有功能） | 所有人 |
| `/knowledge` | 知识区 — 轮播卡片 | 所有人 |
| `/knowledge/:name` | 病虫害详情 | 所有人 |
| `/history` | 问答历史 | 仅用户 |

## 后端 API（新增）

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/register` | POST | 注册，返回 token |
| `/api/login` | POST | 登录，返回 token |
| `/api/knowledge/list` | GET | 病虫害列表，支持 `?category=&search=` |
| `/api/knowledge/<name>` | GET | 单个病虫害结构化详情 |
| `/api/history` | GET | 当前用户问答历史（需登录） |

## 数据库（SQLite）

```sql
users (id, username, password_hash, created_at)
chat_history (id, user_id, question, answer, sources, created_at)
```

## 关键设计决策

**知识区 — 轮播卡片**
- 中间大卡片（当前选中），左右缩小预览，箭头/滑动切换
- 卡片：毛玻璃效果，半透明深色遮罩 + 背景渐变（预留真实照片位置）
- 顶部搜索框 + 病害/虫害 分类标签筛选
- 点击进入详情页，内容按 症状/病原/规律/防治 四段展示

**视觉风格 — 葡萄主题**
- 主色 `#722ed1`（葡萄紫），辅色 `#2d8c4a`（藤绿），点缀 `#d4a017`（金黄）
- 默认暗色模式，Element Plus dark mode 配置
- 首页：Hero 区 + 两个 CTA 按钮（"开始探索" / "智能问答"）

**微交互**
- 卡片 hover 上浮 + 阴影增强
- 路由切换 fade+slide 过渡
- 加载态用 `<el-skeleton>` 骨架屏
- 操作结果用 `ElMessage` toast 提示

**知识数据解析**
- 文件名含"病" → 病害，其余 → 虫害
- 摘要取文件前 120 字
- 按编号标题切分四段
- 启动时解析一次，内存缓存

## 前端文件变更

```
新增：
src/router/index.js         路由配置 + 导航守卫
src/views/Home.vue          首页
src/views/Login.vue         登录/注册
src/views/Chat.vue          问答（从 App.vue 拆出）
src/views/Knowledge.vue     轮播卡片浏览
src/views/KnowledgeDetail.vue  详情页
src/views/History.vue       历史记录
src/components/NavBar.vue   导航栏
src/components/KnowledgeCard.vue  毛玻璃卡片
src/composables/useAuth.js  认证状态管理
src/styles/theme.css        葡萄主题变量

修改：
src/App.vue                 → 改为壳（NavBar + router-view）
src/main.js                 → 加 Router + 暗色模式
```

## 后端文件变更

```
新增：
db.py           SQLite 初始化 + 用户/历史 CRUD
auth.py         JWT 工具 + @require_auth 装饰器
knowledge.py    文本解析 + 知识接口

修改：
app.py          注册新路由，聊天接口写入历史记录
```

## 不做的

- 管理后台、密码找回、OAuth 登录、用户资料编辑
- 知识内容 CRUD（只读 txt 文件）
- 实际上传病虫害照片（用渐变占位，照片后续补）
