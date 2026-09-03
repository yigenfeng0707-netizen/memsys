# MemSys 9/20 提交评测执行清单

> **最后更新**：2026-09-03
> **用途**：9 月 20 日 AML 第二届挑战赛报名开放后，按此清单逐步执行评测提交。
> **状态**：v0.5 已固化，线上端点已部署，等待 9/20 开放提交。

---

## 0. 速查卡（贴在屏幕边）

| 项目 | 值 |
|---|---|
| 赛事 | AML 第二届 Agent Memory Challenge · 文本赛道 · 开源方法榜 |
| 报名开放 | **2026-09-20 00:00（UTC+8）** |
| 提交截止 | 2026-10-31 23:59（UTC+8） |
| 评测队列终止 | 2026-11-04 23:59（UTC+8） |
| 成绩发布 | 2026 年 11 月中旬（预计） |
| 提交入口 | https://agentmemoryleaderboard.ai/evaluation |
| Add URL | `https://gsym236998-memsys-api.ms.show/add` |
| Search URL | `https://gsym236998-memsys-api.ms.show/search` |
| Health URL | `https://gsym236998-memsys-api.ms.show/health` |
| 鉴权 | Bearer token（`Authorization: Bearer <MEMSYS_AUTH_TOKEN>`） |
| GitHub 仓库 | https://github.com/yigenfeng0707-netizen/memsys |
| 提交 commit | `a8f5de2`（v0.5 submission config） |
| 内部模型 | gpt-4o-mini（Add 抽取）+ text-embedding-3-small（向量化） |
| 本地基线 | LoCoMo 全量 1542 题 · **67.8%**（Official answer=gpt-4o-mini / judge=gpt-4o） |
| Full 评测次数 | 本期最多 **2 次**，受理后版本冻结 30 天冷却 |
| 平台答疑邮箱 | contactus@agentmemoryleaderboard.ai（2 个工作日内响应） |

### WAF 一句话

> 魔搭 ms.show 的 WAF 拦截 `python-httpx/*`、`curl`、空 UA → **403**。
> 浏览器 UA（`Mozilla/5.0 ...`）可过。平台评测请求的 UA 未知，是核心风险。
> **全部自测命令必须带浏览器 UA**。

### CI/CD 自动化（GitHub Actions）

> **已部署**：push 到 main 自动触发 deploy + 每 10 分钟 keepalive 心跳保活。

| Workflow | 文件 | 触发 | 作用 |
|---|---|---|---|
| Deploy | `.github/workflows/deploy.yml` | push main / 手动 | 同步 env vars → 推送代码 → 部署 → health check |
| Keepalive | `.github/workflows/keepalive.yml` | cron `*/10 * * * *` | ping health → 不健康自动 redeploy |

**关键发现（踩坑）**：
- 魔搭 Studio **secrets 不会注入 Docker 环境变量**，只有 **variables（明文）才会**。
- `OPENAI_API_KEY` 必须设为 variable，不能设为 secret。
- GitHub Secret 中存储 key 值（安全），CI/CD 同步时推送到魔搭 variable（明文）。
- variables API：POST 创建（409=已存在）→ PUT 更新（404=不存在）→ 需先 DELETE secret 再 POST variable。

---

## 1. T-17d ~ T-1d 预检（9/3 ~ 9/19，建议 9/18 做一次完整预检）

### 1.1 线上端点存活确认

```bash
# 带浏览器 UA 测 health（期望 200 + {"status":"ok"}）
curl -sS -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36" \
  https://gsym236998-memsys-api.ms.show/health
```

```bash
# 不带 UA（模拟平台默认行为，预期 403 → 确认 WAF 仍在生效）
curl -sS -o /dev/null -w "%{http_code}" \
  https://gsym236998-memsys-api.ms.show/health
```

- [ ] health 返回 200 + `{"status":"ok"}`
- [ ] 裸 curl 返回 403（确认 WAF 规则未变）

### 1.2 keepalive 工作流确认

```bash
gh run list --workflow keepalive.yml --limit 3
```

- [ ] 最近一次状态为 success
- [ ] 无超过 12h 的间隔（每 6h 触发一次）

### 1.3 本地代码与线上一致性

```bash
# 确认提交 commit 仍在仓库历史中
git log --oneline a8f5de2 -1
```

- [ ] commit `a8f5de2` 存在且内容为 v0.5 submission config
- [ ] 本地 master 无未 push 的改动影响提交版本

### 1.4 test_contract.py UA 补丁准备

`test_contract.py` 第 22 行使用 `httpx.Client` 默认 UA（`python-httpx/0.27.x`），对线上端点会被 WAF 拦截。**9/20 前准备好以下任一方案**：

**方案 A（推荐）：临时环境变量注入 UA**

在 `test_contract.py` 第 21-22 行之间插入：
```python
headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
```

或用一行 sed 打补丁（不修改源文件）：
```bash
python -c "
import httpx, os, sys
# Monkey-patch: 让所有 httpx.Client 默认带浏览器 UA
_orig_init = httpx.Client.__init__
def _patched_init(self, *a, **kw):
    h = kw.setdefault('headers', {})
    h.setdefault('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
    _orig_init(self, *a, **kw)
httpx.Client.__init__ = _patched_init
exec(open('test_contract.py').read())
"
```

**方案 B：直接用 curl 手动验证 15 项契约的关键路径**

见下方 §3 Step D 的 curl 速验命令。

- [ ] 已确定使用方案 A 或 B，并本地验证可行

### 1.5 预检清单总结

| 检查项 | 预期 | 实际 |
|---|---|---|
| health 200（浏览器 UA） | ✅ | ______ |
| 裸 curl 403（WAF 生效） | ✅ | ______ |
| keepalive 最近 success | ✅ | ______ |
| commit a8f5de2 在仓库 | ✅ | ______ |
| test_contract UA 方案已备 | ✅ | ______ |

---

## 2. 提交参数表（报名表单要填的）

| 表单字段 | 填入值 |
|---|---|
| 参赛赛道 | 文本赛道 (Textual) |
| 参赛组别 | 开源方法榜 (Academic) |
| Add URL | `https://gsym236998-memsys-api.ms.show/add` |
| Search URL | `https://gsym236998-memsys-api.ms.show/search` |
| Health URL | `https://gsym236998-memsys-api.ms.show/health` |
| Auth 方式 | Bearer token |
| Key 值 | `<AML 发放的 issued key>`（拿到后填入，见 Step B） |
| 仓库地址 | `https://github.com/yigenfeng0707-netizen/memsys` |
| 固定版本 commit | `a8f5de2` |
| 内部模型 | gpt-4o-mini + text-embedding-3-small |

**备选端点**（WAF 命中时切换，需魔搭 SDK Token）：
`https://studio-gsym236998-memsys-api.api-inference.modelscope.net/...`
> ⚠️ 此地址要求 SDK Token 鉴权，与平台 Bearer 鉴权叠加，需实测兼容性，不建议首选。

---

## 3. 9/20 当日执行步骤

> 每步标注预计耗时和**通过条件**。任何一步未通过 → 停止，转对应应急章节。

### Step A — 平台确认（2 分钟）

**操作**：
1. 打开 https://agentmemoryleaderboard.ai/evaluation
2. 确认页面已从"即将开放"变为**可填写表单**
3. 确认显示为**第二届 / Textual 赛道**

**通过条件**：表单可填写且赛道正确。

**未通过**：页面未开放 → 等待并每小时刷新一次；确认 UTC+8 时间已到 00:00。

---

### Step B — 提交评测申请、获取 Key（5 分钟，浏览器操作）

**操作**：
1. 选择 Textual + 开源方法榜 (Academic)
2. 按 §2 参数表逐项填写
3. Key 值先留空或填占位符（拿到 Key 后回填）
4. 提交评测申请
5. 获取 AML 发放的 **Leaderboard Key**（issued key）
6. **截图留存**：提交成功页 + Key 值

**通过条件**：拿到 issued key 字符串。

**未通过（需人工审核）**：记录审核渠道，等待通知，不继续后续步骤。

**未通过（提交报错）**：检查 URL 格式、commit 是否存在、仓库是否公开。

---

### Step C — 设置线上 AUTH_TOKEN（3 分钟）

> 当前线上 `MEMSYS_AUTH_TOKEN` 未设置，端点公网开放可写。拿到 AML key 后立即设置，使 Bearer 鉴权与平台对齐。

**操作**：
1. 登录魔搭创空间 → 进入 memsys-api 应用管理
2. 在环境变量中设置 `MEMSYS_AUTH_TOKEN = <AML issued key>`
3. 保存 → 触发应用重启，等待 1-2 分钟

**验证**：
```bash
# 带 AML key 测 health（期望 200）
curl -sS -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36" \
  -H "Authorization: Bearer <AML_ISSUED_KEY>" \
  https://gsym236998-memsys-api.ms.show/health

# 不带 key 测 add（期望 401/403，确认鉴权已生效）
curl -sS -o /dev/null -w "%{http_code}" \
  -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36" \
  -X POST https://gsym236998-memsys-api.ms.show/add \
  -H "Content-Type: application/json" \
  -d '{"messages":[],"user_id":"test","session_id":"test","request_id":"test"}'
```

**通过条件**：带 key 返回 200；不带 key 返回 401/403。

**未通过**：重启未完成 → 再等 2 分钟重试；环境变量未生效 → 检查魔搭变量配置。

---

### Step D — 公网契约终验（5 分钟）

> 用 AML issued key 跑 15 项契约自测。**必须带浏览器 UA 绕过 WAF**。

**方案 A：patched test_contract.py**

```bash
export MEMSYS_TEST_BASE="https://gsym236998-memsys-api.ms.show"
export MEMSYS_TEST_TOKEN="<AML_ISSUED_KEY>"

python -c "
import httpx, os
_orig = httpx.Client.__init__
def _patched(self, *a, **kw):
    h = kw.setdefault('headers', {})
    h.setdefault('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
    _orig(self, *a, **kw)
httpx.Client.__init__ = _patched
exec(open('test_contract.py').read())
"
```

**方案 B：curl 速验关键路径**

```bash
BASE="https://gsym236998-memsys-api.ms.show"
TOKEN="<AML_ISSUED_KEY>"
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# 1. health
curl -sS -A "$UA" -H "Authorization: Bearer $TOKEN" "$BASE/health"

# 2. add（三 ID 回显 + 幂等）
curl -sS -A "$UA" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -X POST "$BASE/add" \
  -d '{"request_id":"test-rid-001","messages":[{"role":"user","timestamp":1704067200000,"content":"Hi, my name is Alice and I live in Sweden."},{"role":"assistant","content":"Nice to meet you!"}],"user_id":"test-uid-001","session_id":"test-sid-001"}'

# 3. 重复 add（幂等）
curl -sS -A "$UA" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -X POST "$BASE/add" \
  -d '{"request_id":"test-rid-001","messages":[{"role":"user","timestamp":1704067200000,"content":"Hi, my name is Alice and I live in Sweden."}],"user_id":"test-uid-001","session_id":"test-sid-001"}'

# 4. search（结构 + 相关性）
curl -sS -A "$UA" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -X POST "$BASE/search" \
  -d '{"query":"Where does Alice live?","user_id":"test-uid-001","top_k":5}'

# 5. user_id 隔离
curl -sS -A "$UA" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -X POST "$BASE/search" \
  -d '{"query":"Where does Alice live?","user_id":"test-uid-001-other","top_k":5}'

# 6. top_k=100 上限
curl -sS -A "$UA" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -X POST "$BASE/search" \
  -d '{"query":"test","options":["A. x","B. y"],"user_id":"test-uid-001","top_k":100}'
```

**通过条件**：方案 A 输出 `ALL CONTRACT TESTS PASSED`（15/15）；方案 B 全部返回正确结构和状态码。

**未通过（403）**：→ 转 §5 应急 WAF 处置。

**未通过（其他）**：记录失败项和错误信息，排查 App 层逻辑。

---

### Step E — 官方 Smoke 测试（不计分，可无限重跑）

**操作**：
1. 在 Evaluation 页面用 issued key 发起 **Smoke** 测试
2. 监控平台日志/状态：平台会调用 Add 和 Search

**通过条件**：Smoke 全绿，平台能成功调用 Add + Search。

**未通过（全量 403 / 超时）**：→ 转 §5 应急 WAF 处置。

**未通过（部分失败）**：查看平台返回的错误详情，排查具体 API 行为。

> ⏱️ Smoke 不计分且可无限重跑，是验证端点可达性的关键关卡。**Smoke 不绿不进 Full**。

---

### Step F — Full 评测（本期最多 2 次，版本冻结 30 天）

> ⚠️ **启动前务必**：
> - [ ] 截图：端点 health 200
> - [ ] 截图：Smoke 全绿结果页
> - [ ] 确认线上代码版本 = commit `a8f5de2`
> - [ ] 确认 AUTH_TOKEN 已设且鉴权生效

**操作**：
1. 在 Evaluation 页面发起 **Full 评测**
2. 记录 **run id / job id**（截图）
3. 全周期保持端点公网可访问（平台 48h 内调度启动，完整运行约 2-10 天）
4. keepalive 工作流正常运行 → 无需额外操作
5. 完成后在 Evaluation 页面查看**私有结果**

**通过条件**：Full 完成，拿到官方成绩。

**未通过**：记录失败原因；如因 WAF/超时 → 修复后用第 2 次 Full 机会；如因逻辑错误 → 30 天冷却后下期再战。

**Full 成绩记录**：
```
Official Full Score: _____%   Run ID: _____   日期: _____
```

---

## 4. 提交后监控（Full 运行期间）

Full 评测从启动到完成可能需要 2-10 天，期间需确保端点持续可用。

### 每日检查（Full 运行期间）

| 检查项 | 命令 | 频率 |
|---|---|---|
| 端点 health | `curl -sS -A "Mozilla/5.0" https://gsym236998-memsys-api.ms.show/health` | 每日 1 次 |
| keepalive 工作流 | `gh run list --workflow keepalive.yml --limit 3` | 每日 1 次 |
| Evaluation 页面状态 | 浏览器打开 https://agentmemoryleaderboard.ai/evaluation | 每日 1 次 |

- [ ] 端点持续 200
- [ ] keepalive 无失败
- [ ] Full 进度正常推进（非 stuck）

### 异常处理

| 异常 | 处置 |
|---|---|
| 端点 502/503 | 魔搭实例可能被回收 → 手动重启应用，等待 2 分钟后验证 |
| keepalive 失败 | 检查 GitHub Actions 日志 → 手动触发一次 |
| Full 长时间无进度 | 查看平台状态页 → 联系 contactus@agentmemoryleaderboard.ai |

---

## 5. 应急：WAF 拦截处置（Step D/E 全 403）

**征兆**：Smoke 或契约测试阶段，平台请求被 ms.show WAF 拦截返回 403。App 层无日志，keepalive 不受影响。

**已实测事实**（2026-08-26 预检）：
- 浏览器级 UA（Chrome 126）：**15/15 全过**
- httpx 默认 UA（`python-httpx/0.27.0`）：**12/15 失败**，全部 403
- 错误体：`{"Code":10010101007,"Message":"当前接口不支持通过SDK Token直接访问..."}`

### 处置决策树

```
Smoke 全 403？
├─ 是 → 确认平台请求 UA
│   ├─ 能获取平台 UA → 在魔搭侧配置 WAF 白名单放行该 UA
│   ├─ 不能获取平台 UA → 评估以下方案：
│   │   ├─ 方案 1：换端点到 api-inference.modelscope.net（需 SDK Token 双鉴权，需实测）
│   │   ├─ 方案 2：部署到自有云主机 / Cloudflare Tunnel（无 WAF 限制）
│   │   └─ 方案 3：联系主办方 contactus@agentmemoryleaderboard.ai 说明 WAF 误拦
│   └─ 选定方案后重跑 Smoke（可无限重跑）
└─ 否 → 正常继续
```

### 方案对比

| 方案 | 成本 | 耗时 | 风险 |
|---|---|---|---|
| 1. 换魔搭 api-inference 端点 | 低 | 30min | SDK Token + Bearer 双鉴权可能冲突 |
| 2. 自有云主机部署 | 中 | 1-2h | 需额外服务器和域名 |
| 3. 联系主办方 | 低 | 不确定 | 依赖对方响应速度 |

> **当前决策**：接受风险，9/20 用 Smoke 当场验证。不提前投入方案 2/3，除非 Smoke 确认 403。

---

## 6. 结果固化（Full 出分后）

- [ ] `memsys/README.md`：版本记录追加"官方 Full 成绩 ___%、run id、提交日期"
- [ ] `eval_runs/EXPERIMENTS.md`：追加官方结果行（对比本地 67.8%）
- [ ] `git commit` 固化上述文档更新
- [ ] 截图保存：Evaluation 页面成绩、排行榜位置

---

## 7. 已知事实附录（截至 2026-09-03）

### 赛事信息

- 第二届 AML 挑战赛由中国图像图形学会（CSIG）主办，南京大学、浙江大学、Datawhale 联合承办。
- 比赛时间：**2026-09-20 00:00 至 10-31 23:59（UTC+8）**，共 42 天。
- 评测队列终止：2026-11-04 23:59（UTC+8）。
- 成绩发布：2026 年 11 月中旬（预计）。
- 提交流程：报名申请 Key → Smoke（不计分可重跑）→ Full（本期最多 2 次，受理后版本冻结 30 天冷却）。
- 平台域名：`agentmemoryleaderboard.ai`。
- 平台 API 指南：`agentmemoryleaderboard.ai/api-guide`。
- 答疑邮箱：`contactus@agentmemoryleaderboard.ai`（2 个工作日内响应）。

### 技术状态

- 本地 Add/Search 实现与官方二期 API 指南**完全对齐**，契约自测 15/15 通过。
- 线上端点内容 = 本地 v0.5 提交配置（8 个部署文件与远端 main 一致）。
- 本地基线 67.8% 追平 Mem0 论文报告的 66.9%（gpt-4o-mini 条件下）。
- 冲奖水平估计 70-75%+，需架构级突破或更强内部模型（后者受合同限制）。
- 检索侧六轮实验（截断/重排/纯事实/路由/裁剪/agentic）均未突破平台期，92% 错题证据已在返回集内 → 检索不是瓶颈。

### WAF 规则详情

- ms.show WAF 拦截：空 UA / `python-*` 前缀 / `curl`。
- ms.show WAF 放行：`httpx/`、Mozilla、okhttp、Go-http-client 及任意其他 UA。
- 真实 httpx 默认 UA 是 `python-httpx/0.27.x` → 返回 403。
- POST /add 同样 403，请求未达 App。
- 错误体：`{"Code":10010101007,"Message":"当前接口不支持通过SDK Token直接访问..."}`。

### 鉴权状态

- 线上 `MEMSYS_AUTH_TOKEN` 当前**未设置** → /add 无需鉴权即 200。
- 影响：AML 平台无论带不带 Bearer 都能调通，**不存在鉴权不匹配风险**；但端点对公网完全开放（可写）。
- 处置：9/20 拿到 AML issued key 后，在魔搭设置 `MEMSYS_AUTH_TOKEN = <issued key>`，使 Bearer 鉴权与平台对齐。
- 注意：改环境变量会触发魔搭重启实例，改动后留 1-2 分钟再测。

### 第二赛周期变化

- Full 次数从一期"当期 1 次"放宽为"本期最多 2 次"。
- 内部模型白名单是否放开尚未在 API 指南中明确（本地仍用 gpt-4o-mini，符合已知约束）。

---

## 8. 公网契约终验实测记录（2026-08-26 预检）

对线上 `https://gsym236998-memsys-api.ms.show` 跑官方 15 项契约测试（`test_contract.py` 同逻辑，带 2s 可检索等待）：

| 客户端 UA | 结果 |
|---|---|
| 浏览器级 UA（Chrome 126） | **15/15 全过**：health、add 200 + 三 ID 回显 + 幂等重放、search 结构/相关性、user_id 隔离、top_k=100 全部通过 |
| 真实 httpx 默认 `python-httpx/0.27.0` | **12/15 失败**，全部 403：`{"Code":10010101007,"Message":"当前接口不支持通过SDK Token直接访问..."}`——请求在 ms.show WAF 层被拒，未达 App |

**结论**：UA 过滤风险已被**实测坐实**，而非推测。App 层逻辑在可达时完全正确。
