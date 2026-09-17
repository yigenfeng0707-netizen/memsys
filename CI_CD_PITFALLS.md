# 魔搭 Studio + GitHub Actions CI/CD 避坑清单

> 本文档记录在 memsys 项目 CI/CD 搭建过程中遇到的所有坑及其解决方案，供后续项目复用。
> 最后更新：2026-09-03

---

## 一、魔搭 Studio 环境变量

### 1. Secrets 不注入 Docker 环境变量

**现象**：通过 `POST /studios/{o}/{r}/secrets` 设置的 secret，容器内 `os.environ.get()` 取不到值，返回空字符串。

**根因**：魔搭 Studio 的 secrets 仅用于 SDK 模式（Gradio/Streamlit），**Docker 模式下 secrets 不会注入容器环境变量**。只有 variables（明文）才会注入。

**解决**：所有需要容器内读取的环境变量（包括 API Key），一律使用 variables API，不要用 secrets API。

```bash
# 正确：POST /studios/{o}/{r}/variables
curl -X POST "https://modelscope.cn/openapi/v1/studios/$OWNER/$REPO/variables" \
  -H "Authorization: Bearer $MS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"key":"OPENAI_API_KEY","value":"sk-xxx"}'
```

**代价**：variable 值在魔搭控制台可见（明文）。敏感 key 的安全性依赖 GitHub Secret 存储 + CI/CD 同步时传输，而非魔搭侧加密。

### 2. Variables API 字段名是 `key` 不是 `name`

**现象**：`POST /studios/{o}/{r}/variables` 返回 400 `InputParameterError: Field validation for 'key' failed on the 'required' tag`。

**根因**：魔搭 OpenAPI 的 secrets 和 variables 端点，body 中字段名是 `key`，不是 `name`。

**解决**：
```json
// 正确
{"key":"OPENAI_API_KEY","value":"sk-xxx"}

// 错误（400）
{"name":"OPENAI_API_KEY","value":"sk-xxx"}
```

### 3. Variables upsert 需要 POST → PUT 两步

**现象**：首次 POST 创建 variable 返回 200；第二次 POST 同一 key 返回 409 `DuplicateEntity`；改用 PUT 更新返回 200。但若该 key 之前是 secret，PUT variable 返回 404 `ResourceNotFound`。

**根因**：POST = 创建（已存在则 409），PUT = 更新（不存在则 404）。secret 和 variable 共享 key 命名空间但类型不同，secret 占用的 key 无法直接 PUT 为 variable。

**解决**：upsert 逻辑需要三段式：
```bash
upsert_var() {
  # 1. 尝试 POST 创建
  CODE=$(curl ... -X POST .../variables -d "$BODY")
  if [ "$CODE" = "409" ]; then
    # 2. 已存在，尝试 PUT 更新
    CODE=$(curl ... -X PUT .../variables -d "$BODY")
    if [ "$CODE" = "404" ]; then
      # 3. secret 占用了 key，先 DELETE secret 再 POST variable
      curl ... -X DELETE .../secrets -d "{\"key\":\"$KEY\"}"
      CODE=$(curl ... -X POST .../variables -d "$BODY")
    fi
  fi
}
```

### 4. Secret 和 Variable 共享 key 命名空间

**现象**：同一个 key（如 `OPENAI_API_KEY`）不能同时作为 secret 和 variable 存在。先创建 secret 后再创建同名 variable 返回 409。

**解决**：同一个 key 只选一种类型。Docker 模式下一律用 variable。

---

## 二、魔搭 Studio 部署与重建

### 5. 更新环境变量后需手动触发 redeploy

**现象**：通过 API 更新 variables 后，容器内环境变量未立即生效，`/add` 仍返回旧值的 401。

**根因**：更新 variables 不会自动重建容器。需手动调用 deploy API 触发重建。

**解决**：
```bash
curl -X POST "https://modelscope.cn/openapi/v1/studios/$OWNER/$REPO/deploy" \
  -H "Authorization: Bearer $MS_TOKEN"
```

重建后等待 60-120 秒，轮询 `/health` 确认 200 后再测试业务端点。

### 6. 代码无变更时 push 不会触发重建

**现象**：CI/CD 中 `git push` 到魔搭仓库返回 "No changes to deploy"，即使环境变量已更新，容器也不重建。

**解决**：deploy.yml 中在 push 代码之后显式调用 deploy API，无论代码是否有变更：
```yaml
- name: Trigger deployment
  run: |
    curl -sS -X POST "$BASE/deploy" \
      -H "Authorization: Bearer $MS_TOKEN"
```

### 7. 容器重建后 health check 有 401 → 503 → 200 三阶段

**现象**：redeploy 后前几次 health check 返回 401（旧容器），然后 503（新容器启动中），最后 200（就绪）。

**解决**：health check 轮询至少 12 次，每次间隔 15 秒，覆盖完整启动周期（约 2-3 分钟）。

---

## 三、魔搭 ms.show WAF

### 8. WAF 拦截非浏览器 UA

**现象**：`curl`（默认 UA）、`python-httpx/*`、空 UA 访问 `*.ms.show` 端点返回 403。

**根因**：魔搭 ms.show 前置 WAF 按 UA 过滤，非浏览器 UA 被拦截。

**解决**：所有请求必须带浏览器 UA：
```bash
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
curl -A "$UA" https://xxx.ms.show/health
```

**风险**：AML 评测平台的请求 UA 未知，若被 WAF 拦截将导致评测失败。这是 9/20 提交的核心风险。

### 9. api-inference 端点双鉴权冲突

**现象**：魔搭 `api-inference.modelscope.cn` 端点传输层无 WAF（可过），但强制使用魔搭 SDK Token 鉴权，AML 的 Bearer Token 被 401 拒绝。

**结论**：不能通过切换到 api-inference 端点来绕过 WAF。需用 Cloudflare Tunnel 或天翼云 ECS 直连方案替代。

---

## 四、GitHub Actions

### 10. git push 到 GitHub 可能连接失败

**现象**：本地 `git push origin master:main` 报 `Connection reset by peer` 或 `Could not connect to github.com:443`。

**根因**：网络环境对 GitHub 443 端口的连接不稳定。

**解决**：改用 GitHub Contents API 上传文件（走 HTTPS API，不走 Git 协议）：
```bash
SHA=$(gh api repos/$REPO/contents/path/to/file?ref=main --jq '.sha')
B64=$(base64 -w 0 path/to/file)
gh api repos/$REPO/contents/path/to/file \
  --method PUT \
  -f message="commit message" \
  -f content="$B64" \
  -f branch="main" \
  -f sha="$SHA"
```

**注意**：更新已存在文件必须提供 `sha`（当前文件的 SHA），否则返回 422。

### 11. GitHub Secret 设置时注意多行文件

**现象**：从 `D:\奇绩算力.txt` 读取内容设置 GitHub Secret 时，文件包含两个 API key（按量 + 按次），`gh secret set` 将整个文件内容作为 secret 值，导致 secret 为 102 字符（两个 key 拼接），而非预期的 51 字符。

**根因**：`echo "$(cat file)"` 会保留文件全部内容，包括多个 key 和换行。

**解决**：精确提取单个 key 值再设置：
```bash
echo "sk-<你的key>" | gh secret set OPENAI_API_KEY
# 或从文件精确提取
KEY=$(grep -oP 'sk-[A-Za-z0-9]+' file.txt | head -1)
echo "$KEY" | gh secret set OPENAI_API_KEY
```

### 12. GitHub Actions cron 每 10 分钟可能延迟

**现象**：`cron: '*/10 * * * *'` 设定每 10 分钟执行，但 GitHub Actions 的 cron 调度不保证精确，高峰期可能延迟 5-15 分钟。

**解决**：keepalive 容忍延迟——只要容器在 30 分钟内有任意一次 ping 即可保活。魔搭 Studio 的休眠超时约为 30-60 分钟无访问。

---

## 五、API Key 验证

### 13. 先单独验证 key 有效性再排查容器

**现象**：容器内 `/add` 返回 401，不确定是 key 无效还是环境变量未注入。

**解决**：先用 curl 直接调用 API 验证 key 本身有效：
```bash
curl -sS -H "Authorization: Bearer sk-xxx" \
  -X POST "https://api.openai-next.com/v1/embeddings" \
  -d '{"model":"text-embedding-3-small","input":"test"}'
```

若返回 200 + embedding 数组 → key 有效，问题在环境变量注入。若返回 401 → key 本身无效。

### 14. 部分平台仅有 chat 无 embedding

**现象**：阶跃星辰、商汤日日新等平台的 API key 支持 chat completions，但不支持 `text-embedding-3-small`。

**结论**：memsys 需要 embedding 服务，更换 API 供应商前必须验证 embedding 端点可用性。奇绩算力（`api.openai-next.com`）同时支持 chat 和 embedding，且 Base URL 与项目 config 完全一致，可直接替换。

---

## 六、排查流程速查

遇到魔搭 Studio 端点异常时，按以下顺序排查：

```
1. curl /health（带浏览器 UA）
   ├─ 200 → 容器存活，问题在业务逻辑
   ├─ 403 → WAF 拦截，检查 UA
   ├─ 401 → 容器启动中或鉴权配置问题
   └─ 503 → 容器未就绪或已崩溃

2. 若 health=200 但 /add=503：
   ├─ 检查错误信息中的上游 URL
   ├─ 若 "401 Unauthorized for embeddings" → OPENAI_API_KEY 未注入或无效
   │   ├─ 直接 curl 测试 key 有效性
   │   ├─ 若 key 有效 → 检查魔搭 variables（不是 secrets！）
   │   └─ 若 variable 正确 → 触发 redeploy 等待重建
   └─ 若其他错误 → 查看容器日志

3. 验证变量是否正确注入：
   curl $BASE/variables -H "Authorization: Bearer $MS_TOKEN"
   确认 key 存在、值长度正确、值不为拼接
```

---

## 七、魔搭 OpenAPI 速查

| 操作 | 方法 | 端点 | Body |
|---|---|---|---|
| 列出 secrets | GET | `/studios/{o}/{r}/secrets` | - |
| 添加 secret | POST | `/studios/{o}/{r}/secrets` | `{"key":"K","value":"V"}` |
| 更新 secret | PUT | `/studios/{o}/{r}/secrets` | `{"key":"K","value":"V"}` |
| 删除 secret | DELETE | `/studios/{o}/{r}/secrets` | `{"key":"K"}` |
| 列出 variables | GET | `/studios/{o}/{r}/variables` | - |
| 添加 variable | POST | `/studios/{o}/{r}/variables` | `{"key":"K","value":"V"}` |
| 更新 variable | PUT | `/studios/{o}/{r}/variables` | `{"key":"K","value":"V"}` |
| 删除 variable | DELETE | `/studios/{o}/{r}/variables` | `{"key":"K"}` |
| 触发部署 | POST | `/studios/{o}/{r}/deploy` | - |
| 获取状态 | GET | `/studios/{o}/{r}` | - |

**Base URL**：`https://modelscope.cn/openapi/v1`
**鉴权**：`Authorization: Bearer <MODELSCOPE_SDK_TOKEN>`
