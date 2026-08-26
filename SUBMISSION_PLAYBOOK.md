# MemSys v0.6 收官提交手册（9-20 执行）

> 本文件是 2026-08-26 准备的"到点即跑"执行清单。报名开放后即按顺序执行。
> 当前已知事实见底部"已知事实"节。

## 0. 执行前置（9-20 00:00 前确认）

- [ ] 确认 `https://gsym236998-memsys-api.ms.show/health` 仍返回 `{"status":"ok"}`（200）
      curl 请用浏览器 UA：`-A "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"`
- [ ] 确认魔搭 keepalive 工作流最近一次为 success（`gh run list --workflow keepalive.yml`）
- [ ] 准备提交参数（见 §1），把 MEMSYS_AUTH_TOKEN 的值准备好

## 1. 提交参数（报名表单要填的）

| 字段 | 值 |
|---|---|
| 参赛赛道 | 文本赛道 (Textual) |
| 参赛组别 | 开源方法榜 (Academic) — 有公开仓库 |
| Add URL | `https://gsym236998-memsys-api.ms.show/add` |
| Search URL | `https://gsym236998-memsys-api.ms.show/search` |
| Health URL | `https://gsym236998-memsys-api.ms.show/health` |
| Auth 方式 | Bearer token（`Authorization: Bearer <MEMSYS_AUTH_TOKEN>`） |
| Key 值 | `MEMSYS_AUTH_TOKEN` 的值（线上魔搭环境变量） |
| 仓库 | `https://github.com/yigenfeng0707-netizen/memsys` |
| 固定版本 commit | `a8f5de2`（v0.5 submission config；本地 master 另有 `0f4e885` 测试改动，未 push） |
| 内部模型 | gpt-4o-mini（Add 抽取）+ text-embedding-3-small |
| 本地基线 | LoCoMo 全量 67.8%（官方 answer/gpt-4o-mini + judge/gpt-4o） |

备选端点（如 ms.show 被拦可切换，需魔搭 SDK Token）：
`https://studio-gsym236998-memsys-api.api-inference.modelscope.net/...`
（但此地址要求 SDK Token 鉴权，与平台 Bearer 鉴权叠加，不建议用作正式提交端点）

## 2. 执行步骤

### Step A — 平台确认（2 分钟）
1. 打开 `https://agentmemoryleaderboard.ai/evaluation`
2. 确认页面已从"提交评测申请"入口变为可填写表单（2026-09-20 00:00 起）
3. 确认当前显示为第二届 / Textual 赛道

### Step B — 提交评测申请、获取 Key（浏览器操作）
1. 选择 Textual + 开源方法榜
2. 填写 §1 参数（Add/Search/Health URL、Auth 方式与 Key 值、仓库地址、commit）
3. 提交，获取 Leaderboard Key（即时发放则继续；需人工审核则记录审核渠道，等待后续跑）
4. 截图留存（Key、提交成功页）

### Step C — 公网契约终验（终端，1 分钟）
```bash
BASE="https://gsym236998-memsys-api.ms.show"
TOKEN="<MEMSYS_AUTH_TOKEN>"
MEMSYS_TEST_BASE="$BASE" MEMSYS_TEST_TOKEN="$TOKEN" \
  python -m pytest --no-header -q   # 或用：MEMSYS_TEST_BASE="$BASE" MEMSYS_TEST_TOKEN="$TOKEN" python test_contract.py
```
若 test_contract.py 15 项全过 → 继续。任何失败 → 停止并排障，不进入 smoke。

### Step D — 官方 Smoke 测试（不计分、可无限重跑）
1. 在 Evaluation 页面用 Key 发起 smoke
2. 监控：平台调 Add/Search。若全量 403 / 超时 → **命中 UA 过滤风险**，见 §4 应急
3. smoke 全绿 → 继续

### Step E — Full 评测（本期最多 2 次，版本冻结）
1. 再次确认端点 200 + smoke 全绿
2. 发起 Full（**启动前截图**：端点健康 + smoke 结果页）
3. 记录 run id / job id
4. 全周期保持端点公网可访问（48h 内调度启动，完整运行约 2-10 天）
5. 全程 keepalive 工作流正常 → 无需额外操作
6. 完成后在 Evaluation 页面查看私有结果

## 3. 结果固化（Full 出分后）
- [ ] `memsys/README.md`：v0.6 版本记录补"官方 Full 成绩 <X>%"、补提交 commit 与 run id
- [ ] `eval_runs/EXPERIMENTS.md`：追加官方结果行（对比本地 67.8%）
- [ ] `git commit` 固化上述文档

## 4. 应急：UA 过滤命中（Step D smoke 全 403）

**征兆**：smoke 阶段平台请求被 ms.show 的 WAF 拦截返回 403（App 层无日志，keepalive 不受影响）。

**处置选项（按成本从低到高）**：
1. **换端点 URL 重跑 smoke**：smoke 可无限重跑，把 Add/Search/Health 改为 `api-inference.modelscope.net` 地址并配 SDK Token 鉴权——但需确认平台 Bearer key 与魔搭 SDK Token 双鉴权可叠加，风险较高，需实测。
2. **部署到无私有 WAF 的后端**：自有云主机 / Cloudflare Tunnel / 其他平台托管，重新 deploy 一份服务，报名更新 URL 再跑 smoke。
3. **联系主办方**：通过 contactus@agentmemoryleaderboard.ai 说明第三方托管的 WAF 误拦，询问是否可豁免或提供替代端点方案。

> 当前决策：接受风险，9-20 用 smoke 当场验证，不提前投入。

## 5. 已知事实（截至 2026-08-26）

- 第二届 AML 挑战赛报名 & Key 申请：**2026-09-20 00:00 起**开放（来源：官方公众号《第二届 Agent Memory Challenge 即将启动》2026-08-22）。
- 提交流程：报名申请 Key → Smoke（不计分可重跑）→ Full（本期最多 **2 次**，受理后版本冻结，30 天冷却）。
- 平台域名：`agentmemoryleaderboard.ai`（API 指南 `agentmemoryleaderboard.ai/api-guide`）。
- 官方 API 指南**未**规定 Authorization/Bearer/X-Api-Key/Health/timeout 字段——鉴权通过 "issued key" 机制，由平台发放 key 后以 Bearer 调用；与本地 server.py 兼容。
- 本地 Add/Search 实现与官方二期 API 指南**完全对齐**，无契约漂移。
- 线上端点内容 = 本地 v0.5 提交配置（8 个部署文件与远端 main d5492bd 逐一一致）。
- **ms.show WAF 规则**：拦截空 UA / `python-*` 前缀 / `curl`；放行 `httpx/`、Mozilla、okhttp、Go-http-client 及任意其他 UA。
  - 真实 httpx 默认 UA 是 `python-httpx/0.27.x` → 返回 403（被拦）。
  - POST /add 同样 403，请求未达 App。
  - 这是本期唯一未排除的上线风险，集中在 smoke 阶段暴露。
- 第二赛周期变化：Full 次数从一期"当期 1 次"放宽为"本期最多 2 次"；内部模型白名单是否放开尚未在 API 指南中明确（本地仍用 gpt-4o-mini，符合已知约束）。

## 6. 公网契约终验实测记录（2026-08-26，9-20 前预检）

对线上 `https://gsym236998-memsys-api.ms.show` 跑官方 15 项契约测试（`test_contract.py` 同逻辑，带 2s 可检索等待）：

| 客户端 UA | 结果 |
|---|---|
| 浏览器级 UA（Chrome 126） | **15/15 全过**：health、add 200 + 三 ID 回显 + 幂等重放、search 结构/相关性、user_id 隔离、top_k=100 全部通过 |
| 真实 httpx 默认 `python-httpx/0.27.0` | **12/15 失败**，全部 403：`{"Code":10010101007,"Message":"当前接口不支持通过SDK Token直接访问..."}`——请求在 ms.show WAF 层被拒，未达 App |

结论：UA 过滤风险已被**实测坐实**，而非推测。App 层逻辑在可达时完全正确。

## 7. 鉴权状态

- 线上 `MEMSYS_AUTH_TOKEN` 当前**未设置**——/add 无需鉴权即 200。
- 影响：AML 平台无论带不带 Bearer 都能调通，**不存在鉴权不匹配风险**；但端点对公网完全开放（可写）。
- 处置建议：9-20 拿到 AML 发放的 issued key 后，**在魔搭创空间设置该应用的 `MEMSYS_AUTH_TOKEN = <issued key>`**，使 Bearer 鉴权与平台 key 对齐，恢复端点受保护。设好后重跑 Step C 契约终验确认仍 15/15 通过。
- 注意：改环境变量会触发魔搭重启应用实例，改动后留 1–2 分钟再测。

## 8. 9-20 当日速查

```
curl -A "Mozilla/5.0" https://gsym236998-memsys-api.ms.show/health        # 期望 200
MEMSYS_TEST_BASE="https://gsym236998-memsys-api.ms.show" python test_contract.py   # 15 项
```
若 `test_contract.py`（默认 httpx UA）报 403 → 命中 UA 风险，转 §4 应急，不进入 smoke。

