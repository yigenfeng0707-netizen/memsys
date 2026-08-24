# MemSys — AML Agent Memory Challenge 参赛系统

面向 [Agent Memory Leaderboard](https://agentmemories.ai) 第二届挑战赛（文本赛道）的自研记忆系统。
只暴露 `Add` / `Search` 两个接口，符合 AML 同步接入契约；平台统一负责 Answer(gpt-4o-mini) / Eval / 榜单。

## 方法来源与改动披露（赛事合规）

按 AML 参赛规则披露本系统使用的方法来源：

| 组件 | 来源 | 本仓库改动 |
|---|---|---|
| BM25 全文检索 | SQLite FTS5 内置 bm25 | 直接使用 |
| 倒数排序融合（RRF） | Cormack et al. 2009 标准信息检索技术，公共领域 | 自行实现（k=60） |
| LLM 记忆事实抽取思想 | 受 Mem0 (Chhikara et al. 2025)、LoCoMo (Maharana et al. 2024) 等公开论文启发 | 抽取 prompt、schema、冲突判官均为本项目原创 |
| 混合检索+向量库架构 | 通用 RAG 工程实践 | 自研 SQLite 单文件实现 |
| 评测基准 | LoCoMo 数据集版权归 snap-research，仅用于本地评估 | 官方 AML pipeline.py 的 answer/judge prompt 逐字复用（平台开源契约） |
| 统一画像卡 / supersede 链 / 主题 rollup | 本项目原创 | — |

除上述外无其他复用；所有 prompt 与管线代码可在本仓库审计。

## 架构

```
Add:  messages ──▶ 时间戳标注分块 ──▶ text-embedding-3-small 向量化 ──▶ SQLite(全文FTS5+向量BLOB)
                   （同步完成持久化后才返回200，request_id 幂等去重）

Search: query(+options) ──┬─▶ 向量余弦 Top200 ──┐
                          └─▶ FTS5 BM25 Top200 ─┴─▶ RRF 融合排序 ──▶ TopK 证据返回
```

- **检索范围隔离**：所有查询强制 `user_id` 精确过滤
- **时间感知**：每条记忆内容内嵌 `[ISO时间] role:` 前缀，供回答模型解析相对时间
- **embedding 缓存**：SHA1 去重，重复内容零成本
- **幂等 Add**：`processed_requests` 表防平台超时重试导致重复写入

## 快速开始

```bash
pip install -r requirements.txt
copy .env.example .env   # 填入 OPENAI_API_KEY
python -m uvicorn server:app --host 0.0.0.0 --port 8790

# 另开终端跑契约自测（15项）
python test_contract.py
```

## 契约符合性（对照官方 api-guide）

| 要求 | 实现 |
|---|---|
| Add 同步语义：持久化且立即可检索后才 200 | ✅ await 全流程 |
| 三 ID 逐字节回显 + success:true | ✅ Pydantic 校验后原样回传 |
| Search `{data:[{id,content,score,created_at}]}` | ✅ 不包 items、不返顶层数组 |
| top_k 上限 | ✅ 截断 ≤top_k |
| Health 免鉴权 GET 返回 2xx | ✅ `/health` |
| Token/Bearer/X-Api-Key 鉴权（可选） | ✅ 设 `MEMSYS_AUTH_TOKEN` 启用 |
| 不发送/不依赖 metadata 等未声明字段 | ✅ extra=ignore |

## 版本记录

- **v0.1**：原始对话块 + 混合检索基线（向量+FTS5+RRF），契约 15 项全通过
- **v0.2**：Add 时 gpt-4o-mini 事实抽取 + supersede 冲突消解链（时序治理）
- **v0.3**：查询扩展（改写+关键词双变体）+ 多路 max-pooling 融合
- **v0.4**：本地评测闭环（LoCoMo 全量10卷，复刻官方 answer/judge prompt）；主题 rollup；错误归因工具
- **v0.5（当前）**：统一画像档案（`__profile__` 钉首位）+ 日期粒度时间戳 + LLM listwise 重排
- **v0.6（计划）**：公网部署 → 官方 smoke → Full

## 实验结论存档

| 实验 | 结果 | 教训 |
|---|---|---|
| 错误归因 | 92% 是答案失误，仅8%检索未命中 | 检索已到顶，优化方向=喂给答案模型的内容质量 |
| CAP=30 截断 | 子集 -2.3pp | 证据常在31~100位，截断=扔证据 |
| LLM 重排 | +0.4pp（噪声） | 排序不是瓶颈 |

## 部署（托管公网 API）

采用魔搭创空间 Docker 实例托管，GitHub Actions 自动部署（push main 即发布），每6小时保活。

**首次配置清单：**
1. 本仓库 → Settings → Secrets：`MODELSCOPE_TOKEN`（modelscope.cn/my/myaccesstoken 获取）、可选 `MODELSCOPE_OWNER`
2. Variables：`MS_STUDIO_NAME`（默认 `memsys-api`）
3. 魔搭创空间设置页 → 环境变量，添加：
   - `OPENAI_API_KEY` = **必需**（OpenAI 兼容端点的 key）
   - `OPENAI_BASE_URL` = 默认 `https://api.openai-next.com/v1`（按需覆盖）
   - `MEMSYS_AUTH_TOKEN` = 建议设置强随机值，作为 Memory System Key 提交给平台
4. 前置条件：魔搭账号绑定阿里云并实名认证（Docker 类型创空间要求）

**部署后验证：**
```bash
curl https://<owner>-memsys-api.ms.show/health        # 期望 2xx
```

**AML 接入参数（提交申请时填写）：**
- Add URL: `https://<owner>-memsys-api.ms.show/add`
- Search URL: `https://<owner>-memsys-api.ms.show/search`
- Health URL: `https://<owner>-memsys-api.ms.show/health`
- Auth: Bearer / X-Api-Key（与 `MEMSYS_AUTH_TOKEN` 一致）

## 关键赛事约束备忘

- 内部 LLM 必须为 gpt-4o-mini（复现不一致会废榜）
- Full 评测整届最多 2 次；成功后 30 天冷却期 → 本地评测必须充分
- 托管接口提交后须公网稳定 ≥30 天
- 记忆不得跨 user_id/task 共享；严禁硬编码/泄漏/提示注入
