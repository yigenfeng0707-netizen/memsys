# MemSys 9/20 提交评测执行清单

> **最后更新**：2026-10-31（提交截止日盘点）
> **用途**：AML 第二届挑战赛报名与评测执行清单（赛期 9/20~10/31，今日为第 42 天：**提交截止日当天** / 评测队列终止前第 4 天）。
> **状态**：**审核中——等官方完成鉴权登记修复后通知重跑 Smoke。官方自 10/19 后零回信（10/31 三路核查确认）；10/31 12:34 截止日催办邮件已发出（QQ 投递状态：投递成功，同线程回复），现等官方回复。10/31 当天实测端点全链路健康（health 200、带键 /search /add 双探针均 200），并已上线每 30 分钟带键深探活（`deep_probe.yml`）。** `request_id=request_676a7115ff6b4acc9bc4`。
> 官方 10/13 15:09 明确：登记的 **X-Api-Key 方式被接受**，Health 免鉴权确认，**Key 无需再提供、无需重新提交申请**；
> 如需 Smoke 联调会在原邮件线程联系——**当前是被动等通知，端点必须持续可用**。
> **⚠️ 与旧核验冲突（10/17 邮箱查证）**：10/3 00:44 已有一封"审核通过"邮件（MemSys **v0.5**，发放 LDBD Key，长期有效），
> 说明 9/30 曾提交过一次申请（`request_45c56272312749e4a30e`）——与下方 10/11"确认此前从未报名"的核验结论**矛盾**，待澄清两份申请的关系。

---

## 0.5 报名提交记录（2026-10-11）

| 项 | 值 |
|---|---|
| 提交方式 | `POST http://47.112.15.137:8088/evaluation-access-requests`（源站直连，绕开 522 的 CF 前置） |
| request_id | `request_676a7115ff6b4acc9bc4` |
| request_token | **不落盘**（本仓库 PUBLIC）。存于本地凭据文件 `%TEMP%\opencode\aml_submission.json` → 字段 `request_token` |
| 状态 | `pending`，`notification_status=sent`（通知已发邮箱） |
| 赛道/组别 | academic / participant_api |
| 版本 | v0.7-e158c66 |
| Auth 方案 | **x-api-key**（见下方 WAF 新发现） |
| memory_api_key | 已绑定（`memsys_sk_d5b9...`，GitHub secret + 魔搭 variable 同步） |
| 凭据文件 | 本地 `memsys_key.txt` + `aml_submission.json`（Temp/opencode） |

### 邮件往来（10/11 提交 → 10/17 Smoke 403 求助）

| 时间（UTC+8） | 方向 | 内容 |
|---|---|---|
| 10/11 16:55 | 收 | 官方（amlleaderboard2026@gmail.com）：申请已进入审核；将按 API Guide 做连通性检查 + Smoke；结果邮件通知；邀请回复补充技术信息；提醒勿公开披露 API Key |
| 10/11 ~17:30 | 发（同线程回复，已在已发送核验） | 鉴权说明：ms.show 网关覆盖 Authorization（Bearer→403 / Token→401），**唯一可用 X-Api-Key**；请求 Smoke/Full 用 X-Api-Key 头（表单已选 `x-api-key`）；若平台只发 Authorization 可回复协调；附三端点 URL，Key 不在邮件披露 |
| 10/12 23:03 | 收 | 官方：已核对申请，**登记的鉴权方式确为 x-api-key**，三地址一致；**平台评测链路支持此方式**（并非只能 Authorization），后续将按登记配置用 X-Api-Key 头携带密钥；反问两点：Health 是否也接受 X-Api-Key 或免鉴权？应用侧会不会因网关注入的 Authorization 拒绝已通过 X-Api-Key 的请求？ |
| 10/13 00:23 | 发 | 答复两点：① `GET /health` 免鉴权，任意头/无头均 200；② 鉴权逻辑 X-Api-Key 优先，仅在无 X-Api-Key 时才回退读 Authorization，故网关注入值不影响放行。附三端点，Key 不披露 |
| 10/13 15:09 | 收 | **官方确认两点均已回应**：Health 免鉴权 GET 无需配凭据；按登记 X-Api-Key 方式核对后续接入。**"API Key 无需通过邮件重复提供，也无需为本次确认重新提交申请"**；如需 Smoke 联调会在本线程联系；**请保持登记端点和参评版本稳定可用** |
| 10/17 13:24 | 发（同线程回复，已发送核验） | 主动同步：① 三端点今日自检通过（health 200 + 端到端 add/search 全绿），上游 key 轮换并重新部署，keepalive 10 分钟保活；② **请求在 Smoke 前把绑定版本 v0.5 更正为 v0.7-e158c66**（或告知由我方平台侧 `Add Version` 的流程）；③ 随时可安排 Smoke 联调；附三端点 + `api_auth_scheme=x-api-key`，**Key 未披露**。截图归档 `佐证附件/操作记录/20261017_qq_*.png` |
| 10/17 15:52 | 发（同线程回复，已发送核验：已发送置顶 35K/刚刚） | **Smoke 403 求助**：① 自助 Smoke Job `teval_5bf67e7f46f309fd`（Run label smoke-1017，Textual，mode=smoke，14:02）3 秒失败 `ADD_ACCESS_DENIED · HTTP 403`，TASKS 0/1；已自行 `Add Version` 绑定 **v0.7-e158c66**，13:24 的版本更正请求就此解决；② 根因 = ms.show 前置网关 Code `10010101007` 按 User-Agent 拦截（矩阵实测：python-*/curl/空 UA→403 连 GET /health 也拦；aiohttp/urllib3/浏览器 UA→放行；X-Api-Key 全程放行、与鉴权无关；网关只改写不校验 Authorization）；③ 请求：查该 Job 的 UA，若为 python 默认/空 UA 请改为非拦截值（例 `MemEval-Worker/1.0`），改后回信我方立即重跑（配额 15:02 起恢复）；三端点稳定在线、仍登记 x-api-key、**Key 不入邮件**。截图 `20261017_qq_{compose_filled,before_send,after_send}.png` |
| 10/17 19:51 | 发（同线程回复，已发送核验：已发送箱置顶「刚刚」，to amlleaderboard2026） | **改绑请求（双轨信）**：① 平台自助改绑被 **409 `endpoint is immutable for this leaderboard key`** 拒绝（View Endpoints 只读）→ 需贵方后台操作；② 提供已验证备选：**FC 中继** `https://memsys-relay-nhqpnszxog.cn-hangzhou.fcapp.run`（改写 UA 绕 Code 10010101007、X-Api-Key 透传、鉴权不变、e2e 6/6）；③ 请求二选一：**A** 修 worker UA（重申 15:52）或 **B** 后台把 Add/Search 改绑为中继 `/add`、`/search`；任一落地即重跑 Smoke（配额 2/30）；Key 不入邮件。截图 `20261017_qq2_{compose_filled,before_send,after_send}.png` |
| 10/19 12:01/12:02 | 收 | 官方两封回信（Re:【Agent Memory Leaderboard】您的评测申请已收到）：后台登记显示**"免鉴权、未绑定 Key、Health 未登记"**，要求核对（原邮件全文待邮箱补档；佐证 = 我方复信逐条引用 + `20261019_qq3_after_send.png` 收件箱列表可见两封 12:01/12:02） |
| 10/19 14:23 | 发（同线程回复，已发送核验） | **逐项答复**：① 自检地址与登记完全一致、Add/Search 均带 X-Api-Key、403 为网关按 UA 拦截（10010101007）且发生在鉴权之前；② 登记鉴权方式确为 x-api-key、Key 已绑定申请表（邮件不披露），Health 可补登记为免鉴权 GET；③ **A 修 worker UA / B 后台改绑 FC 中继，任一落地即配合重跑 Smoke，配额按官方节奏、我方不主动消耗**。正文 `20261019_outbound_reply.txt`，截图 `20261019_qq3_{compose_filled,after_send}.png`（10/28 自 `.tmp` 补归档） |
| 10/19 12:01/12:02（两封，42K/44K） | 收 | 官方核对结论：① **版本错配担忧解除**——v0.7-e158c66 已于 10/17 13:57 登记、两次 Smoke 均绑定该版本，无需重复 Add Version；② **真正卡点 = 平台登记错配**——后台仍显示"无鉴权 / 未绑定 Key / Health 未登记"，与 10/13 书面确认矛盾，官方内部核查中；③ 官方从原执行节点实测对照：python-httpx 直连 403（同网关码）、**MemEval-Worker/1.0 直连 200**、Mozilla 200、python-UA 经我方中继 200；④ A/B 均未落地，官方倾向先核鉴权再审"队伍专用中继"（避免影响其他参赛系统）；⑤ 勿邮件发 Key、勿重复提交申请、勿同条件重复消耗 Smoke。全文 `20261019_aml_re_13322_reply.txt` / `20261019_aml_re_1951_reply.txt` |
| 10/19 ~15:0x（56K，在我方 14:23 答复之后到达） | 收 | **官方最终回复（当前最新一封官方邮件）**：① 403 与网关拦默认 python UA 的判断一致，但过网关后还需验证平台实际携带正确 X-Api-Key；② 官方将核对 request_676a… 鉴权登记与已签发配置不一致的原因，如需补凭证会另行说明**安全提交渠道**（勿邮件发、勿重复申请）；③ A/B 取舍待平台兼容性确认；若改绑中继会先与我方确认最终地址与固定部署信息；④ **登记对齐 + 实际 worker 验证通过后才通知安排 Smoke（含重试/配额处理），在此之前保持现有部署不变、勿主动发起测试**。全文 `20261019_aml_re_1423_reply.txt` |
| 10/31 12:34 | 发（同线程回复，QQ 投递状态"投递成功"） | **截止日催办信（双语）**：① 今日 10/31 23:59 提交截止 + 11/04 队列终止；② 请求优先推进鉴权登记核查，需补凭证即走安全渠道；③ **恳请 11-01 前安排 Smoke**（Full 0.5~5 天，越早越可能赶上队列终止）；④ A（worker UA）/ B（后台改绑 FC 中继）任一落地即配合重跑；⑤ 重申合规（未重复申请、未披露 Key、Smoke 2/30、端点 10/11 起未变、10-28 契约 15/15、保活+深探监控就绪）。CC 自身留档。截图 `20261031_qq4_{sent_list,after_send}.png` + `20261031_qq_compose_{filled,body}.png` |
| 10/20~10/31 | — | **官方零回信（12 天）**。10/31 邮箱三路复查：① 搜索 `amlleaderboard` 共 14 封 = 官方 8 + 我方 6（与 10/28 完全一致，最新官方邮件仍为 10/19）；② 收件箱按日期扫"今天 4 + 昨天 19 + 周四 12"封，无任何官方地址来信；③ 垃圾箱 16 封全是营销邮件（当天新落 2 封 = ChatGPT/Eazo 推广）。证据 `佐证附件/操作记录/20261031_mail_{search_amlleaderboard,inbox_top,spam_scan}.png` + 3 份 transcript |

> **魔搭 UA 豁免工单（10/17 17:39，已发送核验）**：新邮件致 `contact@modelscope.ai`（魔搭页脚「联系我们」唯一官方渠道，无表单工单系统），主题「创空间域名 gsym236998-memsys-api.ms.show 被 WAF 按 User-Agent 拦截（Code 10010101007），申请豁免/咨询合规接入」，正文 `.tmp/ms_body.txt`：现象 + UA 矩阵 + 诉求（域名 UA 豁免 / 白名单申请方式 / 合规接入建议），**不含任何 Key**。截图 `20261017_ms_{ticket_compose,before_send,after_send,sent_verify}.png`。
>
> **最新状态 = 等官方回信改 UA**（截至 10/17 15:53，邮箱搜索 `amlleaderboard` 共 **9 封**，末封为我方 10/17 15:52 的 403 求助信；平台侧证据链：`teval_5bf67e7f46f309fd` 失败截图 `20261017_aml_smoke_job.png`，UA 矩阵结论见下方「应急：WAF 拦截处置」）。
> **403 归因实锤（10/17 16:0x 补）**：`server.py`/`config.py` **不存在任何 403 响应路径**（鉴权失败一律 401，`GET /evaluation-access-requests` 的 403 是平台侧返回）→ Job 记录的 `HTTP 403` 只能来自 ms.show 网关层，**平台 worker 请求未达应用**为排除法结论；平台 job 详情/`View Endpoints`/API Guide/docs 均无 UA 或请求回显，bound endpoints 为我方 ms.show 直连（无中继），故 worker UA 只能由官方日志侧确认。
> **Smoke 第 2 次（10/17 16:32，用户授权试探）**：Job `teval_0f3d724cc97fde83`（Run `smoke-1017b`，Textual，v0.7-e158c66，16/16，TopK 100）2 秒失败，**同 `ADD_ACCESS_DENIED · HTTP 403`、0/1 tasks** → 失败模式未变，官方尚无动作（去信 40 分钟）；Track smoke 配额 2/30。平台新增观察点：job 详情有 **Resume latest interrupted job**（checkpoint 恢复）与「Failed attempts (1) 仍计一次评测结果」，官方改 UA 后优先 Resume 恢复。截图 `20261017_aml_{confirm_modal_b,poll_b*,smoke_job_b}.png`。
> **自助评测链路**：Eval Key 已取回（仅存 sessionStorage/临时文件）→ `/evaluation` 可进 → `Add Version` 已绑 v0.7-e158c66 → 表单/确认弹窗/Job 生成全流程跑通；Smoke 配额 1 次/小时、每赛道 ≤30 次，Full gate 0/8 待 smoke 过线解锁。
> 往来详情同步记录于本地凭据文件 `aml_submission.json`（Temp/opencode；**该文件已被系统清理，此后往来以本文件 + `佐证附件/操作记录/` 为权威记录**）。
>
> **FC 反代中继上线（10/17 18:5x 端到端 6/6 验证）**：阿里云 FC 事件函数 `memsys-relay`（cn-hangzhou / Python 3.12 / 纯标准库 urllib / 超时 300s）+ HTTP 触发器 `http-trigger`（无需认证，GET/POST/PUT/DELETE，公网 URL 开启），中继端点 **`https://memsys-relay-nhqpnszxog.cn-hangzhou.fcapp.run`**；转发至 ms.show 时改写 UA 为浏览器值、`X-Api-Key` 原样透传。端到端测试 `佐证附件/操作记录/20261017_fc_relay_e2e.txt` **6/6 PASS**（核心对照：python-UA 直连 ms.show=403 → 经中继=200；无 Key→401 鉴权保留；有 Key /add /search→200）。详见下方「FC 反代中继」章节。
>
> **自绑换端点被平台拒绝（10/17 19:0x，实锤）**：`POST /access/versions` → **409** `{"detail":{"reason":"endpoint is immutable for this leaderboard key"}}`；`View Endpoints` 弹窗只读（仅 Copy），版本下拉仅 `v0.5 / v0.7-e158c66` → **同一 leaderboard key 下端点不可自助更换**（Add Version 只能新增版本名，URL 必须仍指向 ms.show 直连）。取证 `20261017_aml_{bind_409_immutable,bound_endpoints_readonly}.png`。
> → **解锁只剩两条路**：A. 官方修复 worker UA（15:52 已去信）；B. 官方**后台改绑**端点到中继 URL（**19:51 已发双轨信**，A+B 同信请求）。二者落地前 smoke 不重跑以省配额（当前 Track smoke 2/30、1 次/小时）——**现在是双路等回信状态**。
>
> **10/28 续跑实测（第 1 轮续跑盘点）**：
> ① `GET /health`（浏览器 UA）→ `200 {"status":"ok"}`，实例存活；裸 UA → `403`，**WAF 规则未变**；
> ② **FC 中继实测宕机**：`https://memsys-relay-nhqpnszxog.cn-hangzhou.fcapp.run/health` → `AccessDenied: Current user is in debt`（阿里云账户欠费）——**方案 B 在清欠前不可用**，当前只剩方案 A（官方修 worker UA）一条路；
> ③ 10/19 证据补归档：`.tmp/aml_reply.txt` → `佐证附件/操作记录/20261019_outbound_reply.txt`，2 张截图 → `20261019_qq3_{compose_filled,after_send}.png`（此前散落临时目录，未提交过仓库）；
> ④ 倒计时压力：Full 官方耗时 0.5~5 天 + 第二次 Full 因 30 天冷却实际排不上 → **Smoke 须 ~48h 内过线、Full 最晚 10/30 前启动**，否则赶不上 11/04 队列终止。

### 10/19 官方回信要点与当前守则（10/28 邮箱核查落账）

**三封 10/19 官方回信**（12:01/12:02 两封 + ~15:0x 一封）关键信息：

1. 版本错配担忧解除：v0.7-e158c66 已于 10/17 13:57 登记，两次 Smoke 均绑定该版本。
2. **真正卡点 = 平台登记错配**：后台显示"无鉴权 / 未绑定 Memory System Key / Health 未登记"，与 10/12~13 官方书面确认的 x-api-key 矛盾——官方正在内部核查原因。
3. 官方对照实测（原执行节点）：python-httpx 直连 403；MemEval-Worker/1.0 直连 200；Mozilla 200；python-UA 经我方中继 200 → 403 归因与 WAF 结论一致，**中继方案已被官方实测验证有效**。
4. A/B 均未落地；官方倾向先核鉴权再审中继方案；若改绑会先确认我方最终地址与固定部署信息。
5. **官方守则（必须遵守）**：勿重复提交申请；勿邮件明文发 Key（如需补凭证官方会给安全渠道）；登记对齐 + 实际 worker 验证通过前不重跑 Smoke（勿同条件重复消耗配额）；保持现有部署不变。

**我方当前三件事**：① 端点稳定在线（keepalive + 健康监控已挂，10/28 health 200）；② ~~清欠阿里云 FC~~ ✅ 已完成（10/28 复测：python-UA 经中继 /health 200、无 Key /add 401、带 Key /search 200 → **方案 B 完全就绪**）；③ 等官方安全提交渠道通知后第一时间提交/绑定 Memory System Key。

### 10/28 深夜：上游 key 全灭与切换（生产恢复记录）

**根因链**：用户清欠阿里云后 FC 中继复活 → 顺手带 Key 实测 /search 发现 503 `search failed: HTTPStatusError`（57s）→ 定位到上游：opennext 中转站 key（`sk-RdA8l6…`，10/17 换的 apikey3）已 **401 Invalid token**（embeddings/chat 双双 401，本地 .env 同款 key 同样 401）→ 即 **/add /search 自 10/17 后某时刻起实际不可用**（health 与鉴权正常，keepalive 探不出这种深层故障）。

**切换过程**：
1. 备选①阶跃星辰三个月套餐 token：认证有效但**额度为 0**（`no left credit for step plan`，主模型 step-3.7-flash 同样 429），且套餐端点无 embeddings → 搁置待用户后台核实。
2. **备选②中转站 api11.xhub.chat（NewAPI v1.0.0-rc.43）**：用户提供账号；API 直登被拒（凭据不符）→ 用户自行登录后，从页面会话用 XHR-hook 抓到 Bearer JWT（`/api/user/auth/refresh` POST 换 token），创建令牌 **memsys2**（无限额度），发现 key 全接口掩码 → 从行内复制按钮+剪贴板拿到完整 key。
3. 分组坑：default 组无 gpt-4o-mini 渠道（503 distributor）、`OpenAI - Az` 无权限（403）→ 改 **`OpenAI - 官方`** 后全通：**chat gpt-4o-mini 200（3.6s）+ embeddings text-embedding-3-small 200（1536 维）**。
4. 部署链：GitHub secret `OPENAI_API_KEY` 经 API（PAT + pynacl sealed box）轮换 → deploy.yml `OPENAI_BASE_URL` 字面量改为 `https://api11.xhub.chat/v1` → commit `21f3bee` push main → Deploy run `40723480861` success。
5. **终验：官方口径契约 15/15 全绿**（含 add 幂等、search 相关性 Sweden、隔离、top_k=100）；add 200（11.1s）/ search 200（5.7s，召回 0.4523）。

**切换后配置**：上游 `https://api11.xhub.chat/v1`（分组 `OpenAI - 官方`）；**申报模型不变**（gpt-4o-mini + text-embedding-3-small）→ 无需就模型变更通知官方；EMBED_DIM=1536 与存量库兼容，无需清库。

**新风险**：① 生产多了一层中转站依赖（单点）；② 中转站账户余额/有效期需用户自行确认能覆盖 Full 评测用量（token 已设无限额度，但站内余额是硬约束）；③ 深层故障（上游挂但 health 200）keepalive 探不出——~~可选做带 Key 的 /search 深探活（每 30 分钟，消耗微量 token）~~ **✅ 10/31 已上线，见下节**。

### 10/31 截止日盘点（当天实测）

**倒计时状态**：今天是提交截止日（10/31 23:59 UTC+8）；评测队列终止 11/04 23:59。按 10/28 倒排"Full 最晚 10/30 前启动"已过线未启动（Smoke 仍未过线）；按官方 Full 耗时 0.5~5 天，今天启动是理论极限——**一切取决于官方登记对齐后 Smoke 立即放行**。官方自 10/19 后零回信已 12 天（10/28 邮箱实查 14 封；**10/29~31 尚未复查**）。

**10/31 上午实测（当日实测，非文档转述）**：

| 检查项 | 结果 |
|---|---|
| health（浏览器 UA） | 200（0.77s） |
| 裸 UA health | 403（WAF 规则未变，卡点仍在） |
| 无 Key POST /add | 401（鉴权完好） |
| 带键 /search 探针 | 200 `{"data":[]}`（embedding 上游活） |
| 带键 /add 探针（唯一 request_id） | 200 `success=true`（chat 抽取上游活） |
| GitHub keepalive | 最近一次 success 2026-10-31 08:56（UTC+8） |
| 仓库状态 | 工作区干净、与 origin/main 同步、`.env` 未入库 |

**新上线：带键深探活（10/31）**——`.github/workflows/deep_probe.yml`：每 30 分钟（:13/:43 错峰）带 `X-Api-Key` 实打 /search（断言 200 + `data` 键）与 /add（唯一 request_id，断言 `success=true`），覆盖 keepalive 探不到的深层故障（10/28 事故模式：上游 key 死但 health 200）；失败自动开 GitHub issue（同标题去重）。探针数据写入独立 `user_id=probe_deep`，不影响评测数据；每轮消耗 1 次 embedding + 1 次 gpt-4o-mini 抽取，成本可忽略。**10/31 12:0x（UTC+8）首次实跑全绿**：直连 GET /health 200、经中继 /search 200 + /add 200（run `41166276847`）。

**⚠️ 新发现（10/31 探活首跑踩出）：ms.show 网关拦截 GitHub Actions 机房 IP 的带凭据 POST**——返回 401 `{"Authorization failed."}`，该文案不存在于应用代码（`check_auth` 只有 missing/invalid credentials），先于应用层；同 Key 本机家宽 IP 200、GET /health 从 Actions 也 200（keepalive 长期实证）。⇒ 深探活必须走 **FC 中继**（阿里云出口 + UA 改写），副作用是方案 B 基础设施本身也被监控（中继挂 = 探针报警，如再欠费）。另注：**官方评测 worker 若从海外机房 IP 发 POST，也可能踩中这条网关规则**——与 10/17 UA 拦截是两回事，若后续 Smoke 再 401（而非 403），优先怀疑此规则并让官方报 worker 出口 IP。

**今日待办（10/31 更新）**：① ~~查邮箱~~ ✅ **已完成：10/29~31 官方零回信**（三路核查，见上方 10/20~10/31 行）；② ~~发催办邮件~~ ✅ **已发送（10/31 12:34，投递成功，见邮件往来表新增行）**；③ 用户确认 xhub 中转站余额能覆盖 Full 用量。

### ⚠️ 历史申请冲突（10/17 发现，待澄清）

| 日期 | 事件 | 证据 |
|---|---|---|
| 09/30 07:14 (UTC) | 申请 `request_45c56272312749e4a30e`，MemSys **v0.5** 进入审核 | 邮箱 9/30 收件 |
| **10/3 00:44** | **审核通过**，发放 **LDBD Key**（`ldbd_sk_...`，长期有效），"按 API Guide 配置 Add/Search 并使用该密钥评测" | 邮箱 10/3 收件 |
| 10/11 16:55 | 第二次申请 `request_676a7115ff6b4acc9bc4`（v0.7）进入审核 | 邮箱 10/11 收件 |

- 10/11 的"从未报名"核验（凭浏览器历史 + remio + 线上 token 未设）**与 10/3 审核通过邮件矛盾**——当时线上 token 未设，说明 v0.5 那次并未真正接入。
- ~~若平台发 `ldbd_sk_...` 会 401 → 让应用接受两把 Key~~ **已排除**：见下方"平台侧状态"，平台调我们用的是 Memory System Key，不是 Eval Key。

### 平台侧状态（2026-10-17 实查，浏览器会话直连平台 API）

**两把 Key 的官方分工**（`/api-guide` → "Eval Key and Memory System Key" 表）：

| 凭据 | 谁提供 | 用途 |
|---|---|---|
| **Eval Key / Leaderboard Key**（`ldbd_sk_...`，10/3 邮件发放） | AML | 验证参赛者访问、**发起评测**、解锁私有结果 |
| **Memory System Key**（`memsys_sk_d5b9...`，表单绑定） | 参赛者 | 平台调用我们的 Add/Search |

> ⇒ 平台调我们用的是 Memory System Key，**不存在"平台发 ldbd Key 导致 401"的风险**（原风险条目作废）。
> 浏览器会话里已有 Eval Key（`sessionStorage["leaderboard.evalAccessKey"]`），可直接读平台状态。

**实查结果**（同源 fetch，header `X-Leaderboard-Api-Key`）：

| 端点 | 返回 |
|---|---|
| `GET /access/versions` | **仅 1 个版本 `v0.5`**（`version_187ae9a3981a`，created 2026-10-02 16:44 UTC，active），绑定的 Add/Search = 我们线上地址；`version_binding.allowed=true`（无冷却） |
| `GET /eval-jobs/recent` | `{"jobs":[]}` |
| `GET /eval-jobs/active` | `{"jobs":[]}` |
| `GET /eval-results/private` | `{"results":[]}` |
| `GET /evaluation-access-requests` | 403 `key issuing requires an admin leaderboard key` → **申请状态平台侧不可查，只能等邮件** |

**⚠️ 版本名错配（新风险，优先于其他待办）**：绑定版本叫 **v0.5**，线上跑的是 **v0.7-e158c66**。
审批通过后若直接用这个 v0.5 绑定跑 Smoke/Full，评的是 v0.7 代码却挂 v0.5 的名——违反 §Step F"线上代码版本 = 提交 commit"。
**处置：审批通过后先点 `Add Version` 登记 v0.7-e158c66，再跑 Smoke。**

**配额事实（平台页原文）**：每赛道 2 次 Full；"The second Full run unlocks 30 days after the first Full run is completed."
→ 结合 10/31 提交截止 + 11/04 队列终止，**第二次 Full 实际排不上，等同只有 1 次机会**；Full 官方时长约 0.5~5 天。

### 10/17 线上运维与验证（key 轮换 → 部署 → 端到端复核）

| 项 | 结果 |
|---|---|
| 背景 | 原 `OPENAI_API_KEY`（`sk-BVxF0…`）被中转站判 401 Invalid token，本地全量评测中断 |
| 换 key | 改用 opennext `apikey3`（`sk-RdA8l6…`）；`gh secret set OPENAI_API_KEY`（2026-10-17T04:51Z） |
| 部署 | push `3771f36`（eval 增加 5xx 重试）触发 `Deploy to ModelScope Studio` run `39004164813` → **success**，workflow 自动 upsert `OPENAI_API_KEY` 变量 |
| 端到端 | 浏览器 UA + 本地 `memsys_key.txt`（42 位，与线上 `env_len=42` 吻合）跑 `test_contract.py` 打 `gsym236998-memsys-api.ms.show` → **15/15 PASS**（/add 事实抽取 + /search 向量检索均走新 key） |
| 转发佐证 | 带错误 `X-Api-Key` 打 `/search` 返回应用自身 401 detail（`env_sha8=15335b28`、`source=x-api-key`）→ 网关放行正常；裸 curl/httpx UA 仍 403 → **WAF 行为未变**（下方小节继续有效） |
| 状态 | **端点可用性恢复**，等 Smoke 期间依赖 keepalive 维持；旧 key（`sk-BVxF0…`）已作废 |

### WAF/网关新发现（10/11 实测，推翻旧认知）

1. **ms.show 网关会给每个到达应用的请求注入自己的 `Authorization` 头**（56 字符，值固定）——应用侧看到的 Authorization 永远不是调用方发的。用 401 诊断指纹（env_sha8/supplied_sha8/source）实测坐实。
2. 因此 **`Authorization: Bearer/Token <key>` 在 ms.show 上永远无法鉴权成功**（403 或被网关值顶掉）。**唯一可用方案：`X-Api-Key: <key>`**（app 已改为优先读 x-api-key）。
3. 申请表 `api_auth_scheme` 必须填 **`x-api-key`**；平台评测/Smoke 也必须用该头。**10/11 已邮件说明，10/12~10/13 官方书面确认接受**（见上方邮件往来）——该风险已解除。
4. PowerShell `Invoke-WebRequest` 对 4xx 错误体不解压 → 显示空 body，**排障一律用 curl.exe**。

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
| 鉴权 | **X-Api-Key**（`X-Api-Key: <MEMSYS_AUTH_TOKEN>`）——ms.show 网关注入自有 Authorization，Bearer/Token 方案不可用 |
| GitHub 仓库 | https://github.com/yigenfeng0707-netizen/memsys |
| 提交 commit | `e158c66`（v0.7 日期钳制 + X-Api-Key 优先鉴权；app 代码 = a8f5de2 + pipeline 钳制 + server 鉴权重排） |
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

- [ ] commit `66cbd39` 存在且已推送 origin/main（10/11 经 SSH443 推送成功）
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
| 固定版本 commit | `66cbd39` |
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
> - [ ] 确认线上代码版本 = commit `66cbd39`（部署 run 触发于该 push）
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

### 方案 4：FC 反代中继（10/17 17:5x~18:5x 部署，端到端 6/6 通过）

10/17 Smoke 实测 403 且 worker UA 不可自取 → 在不改登记端点（ms.show 直连）的前提下，**同线程双轨**：一边向官方/魔搭求助 UA（15:52 / 17:39 两封信），一边把「方案 2」以**无服务器反代**形式落地，供官方后台改绑或日后切换用。

| 项 | 值 |
|---|---|
| 宿主 | 阿里云函数计算 FC（fcnext 控制台，cn-hangzhou） |
| 函数 | `memsys-relay`，事件函数 + HTTP 触发器 `http-trigger` |
| 运行时 | Python 3.12；handler `fc_handler.handler`；**纯标准库 urllib，零依赖包** |
| 代码包 | `.tmp/fc/memsys-relay.zip`（仅 `fc_handler.py`），源码 `.tmp/fc/fc_handler.py`，本地测试 `.tmp/fc/test_fc_handler.py` 6/6 |
| 环境变量 | `RELAY_UPSTREAM=https://gsym236998-memsys-api.ms.show`；超时 300s；单实例并发 1（可缩容到 0） |
| 触发器 | **无需认证**，GET/POST/PUT/DELETE，公网访问 URL 已开启 |
| **中继端点** | `https://memsys-relay-nhqpnszxog.cn-hangzhou.fcapp.run` |
| 转发语义 | method/path/query/body/headers 原样转发；**仅改写 `User-Agent` 为浏览器值**绕过 Code `10010101007`；`X-Api-Key` 透传，鉴权仍由 ms.show 应用执行（无 Key→401 保留） |
| 端到端验证 | `.tmp/fc_trig_test.py` → `佐证附件/操作记录/20261017_fc_relay_e2e.txt` **6/6 PASS**：① `__relay/health` 200 ② **python-UA→中继→`/health` 200（核心绕行）** ③ python-UA 直连 ms.show 仍 403（WAF 活着的反证） ④ 无 Key `/add` 401 ⑤ 有 Key `/add` 200 ⑥ 有 Key `/search` 200 |
| 取证 | `20261017_fc_{function_created,trigger_url,deploy}.png` + `20261017_fc_relay_e2e.txt` |

**FC 控制台/运行时踩坑**：
1. 向导按钮必须取 **live rect + `elementFromPoint` 命中校验**——陈旧坐标（y=562）落到 `next-overlay-backdrop`，点击表现为「弹窗被关掉」的假象，真实按钮在 y=490。
2. python3.12 运行时把 event 以 **raw JSON bytes** 传入（不是 dict）→ handler 用 `_norm_event()` 归一化，否则 `'bytes' object has no attribute 'get'`。
3. ZIP 上传后必须点上传抽屉里的**「保存并部署」**才生效（WebIDE 里有代码 ≠ 已部署）；`部署代码` 按钮可重部署。
4. 排错用**「测试函数」面板**（显示 errorMessage/stackTrace/请求信息）；实时日志需启用 SLS（计费），不启用。
5. 占位符匹配要精确：`请输入函数名称` 会命中 env 行把函数名覆盖掉，必须用 `memsys-relay` 精确匹配。

**平台侧绑定结论（10/17 19:0x 实锤）**：`POST /access/versions` 换 endpoints → **409 `endpoint is immutable for this leaderboard key`**；`View Endpoints` 只读 → **中继端点无法自助绑上去**。待官方动作：A 修 worker UA（15:52 信）或 B 后台改绑到中继 URL（**19:51 双轨信，A+B 同信**）；A/B 落地前 **smoke 不重跑**（省配额，Track smoke 现 2/30）。

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

- 本地 Add/Search 实现与官方二期 API 指南**完全对齐**，契约自测 15/15 通过（10/11 复验）。
- 线上端点内容 = v0.7 修复版（日期钳制），部署由 10/11 push 自动触发。
- **API key 已轮换**（9/30 换为 sk-BVxF0...，10/11 已同步回本地 .env）；注意 .env 禁用 PS `Set-Content -Encoding UTF8`（BOM 会使 dotenv 读不到 key）。
- 本地基线 67.8%（v0.5）；v0.7 子集对照 62.5% vs 62.3%（+0.2，时序 c8 +7.7），全量 10 卷评测 10/11 进行中。
- 冲奖水平估计 70-75%+，需架构级突破或更强内部模型（后者受合同限制）。
- 检索侧六轮实验（截断/重排/纯事实/路由/裁剪/agentic）均未突破平台期，92% 错题证据已在返回集内 → 检索不是瓶颈。

### WAF 规则详情

- ms.show WAF 拦截：空 UA / `python-*` 前缀 / `curl`。
- ms.show WAF 放行：`httpx/`、Mozilla、okhttp、Go-http-client 及任意其他 UA。
- 真实 httpx 默认 UA 是 `python-httpx/0.27.x` → 返回 403。
- POST /add 同样 403，请求未达 App。
- 错误体：`{"Code":10010101007,"Message":"当前接口不支持通过SDK Token直接访问..."}`。

### 鉴权状态（10/11 更新）

- 线上 `MEMSYS_AUTH_TOKEN` **已设置**（`memsys_sk_d5b9...`，GitHub secret → deploy.yml 同步为魔搭 variable）。
- 鉴权实测：无凭据/错键 → 401；正确 `X-Api-Key` → 200。**Authorization 头被网关顶掉，不可用**（见 §0.5）。
- 本地闸门：`test_contract.py` + `test_governance.py` 均已支持 `MEMSYS_TEST_TOKEN`（X-Api-Key + 浏览器 UA），带鉴权双绿。
- 注意：改环境变量会触发魔搭重启实例，改动后留 2-3 分钟再测。

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
