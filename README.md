# 财富管理智能持仓分析助手（WM Portfolio Agent）

## 项目介绍

面向**个人财富管理（Wealth Management）**场景的多智能体持仓分析助手。覆盖持仓概览与资产配置查询、损益（P&L）解读、风险度量与集中度诊断、组合变动归因，以及合规范畴/产品条款类知识问答等核心能力。

原云平台客服系统在多轮对话中缺乏长短期记忆继承，用户需反复提供上下文；同时高频标准问题长期占用大模型算力，响应慢且成本高；面对复杂产品参数与关联关系，单纯大模型易出现“幻觉”。本项目在**保留原有 Agent 骨架与通信基础设施**的前提下，将上层业务重构为 WM 持仓助手：基于 **LangGraph 多智能体编排**、**Milvus 语义缓存**与**图向量混合检索（Hybrid RAG）**，实现按业务意图自动路由、高频问题毫秒级缓存直返、复杂问题经专属 Agent 检索增强并调用 **MCP 工具链**对接持仓库 / 流水 / 风险指标，给出可审计的事实性回答（不做荐股、不承诺收益）。

**技术栈：** Python · FastAPI · LangGraph · LangChain · Milvus · Neo4j · Redis · MySQL · MCP (Model Context Protocol) · Gemini（OpenAI 兼容接口）/ DashScope Embedding

---

## 职责描述（可选）

1. **多 Agent 协作编排与 MCP 工具化集成**
  基于 LangGraph 状态机按业务域拆分核心专家 Agent（知识问答 / 持仓 / 业绩 / 归因 / 风险），由 Orchestrator 统一意图路由，通过全局 `AgentState` 共享跨节点上下文；采用 MCP 协议将底层 MySQL 持仓与流水查询、风险代理指标、标的检索与说明书等封装为标准化 Server，实现工具能力解耦与跨 Agent 复用。风险场景支持 `holdings_agent → risk_agent` 状态接力（State Handoff）。
2. **L1/L2 双层语义缓存设计**
  针对“什么是资产配置”“TWR 与 XIRR 区别”“集中度风险含义”等高频标准问题，设计基于 Milvus 的 L1/L2 语义缓存层。在网关层计算 Query 向量：L1 高置信命中（距离 ≤ 0.08）直接返回预设答案；L2 降级或未命中则进入后置 Agent 推理流程，降低无效 Token 消耗与推理延迟。
3. **图向量混合检索（Hybrid RAG）构建**
  为支撑合规范畴、业绩指标释义、集中度与资产配置等教育类问答，构建 Milvus 向量检索 + Neo4j 知识图谱双路召回。Milvus 覆盖模糊概念与长文本；Neo4j 适合结构化关系与属性查询（可按需扩展 WM 产品图谱）。向量库 collection 为 `wm_portfolio_docs`，文档源为 `mock_data/` 下 WM 说明文档。
4. **基于 FastMCP 的工具化封装与业务闭环**
  使用 FastMCP 将异构后台能力统一封装为 MCP Server，实现大模型与业务系统解耦及 `user_id` 注入鉴权隔离。业务闭环示例：持仓查询调用 `get_portfolio_holdings`；业绩解读调用 `get_portfolio_transactions`；风险审查在持仓上下文上调用 `analyze_position_risk`；归因结合持仓权重与流水贡献进行叙事。。
5. **长短期多级记忆系统（Memory System）**
  Redis 会话级短期记忆（TTL 与窗口压缩）+ Milvus 用户级长期偏好记忆。会话开始前融合记忆注入 System Prompt，会话结束可异步抽取偏好，支撑跨会话连贯服务（基础设施与原先一致，偏好语义可扩展为风险偏好、关注行业等）。

---

## 项目成果（供选择）

▸ 基于 LangGraph 状态机编排的多 Agent 协作体系（knowledge / holdings / performance / attribution / risk），复杂场景下按意图路由至专属节点，跨会话记忆机制减少重复陈述背景。  
▸ Milvus + Neo4j Hybrid RAG，面向 WM 教育与披露文档召回，抑制知识问答场景下的编造与幻觉。  
▸ 上线基于 Milvus 的 L1 语义缓存后，资产配置/风险释义等高频标准问可毫秒级直返，降低无效推理成本。  
▸ 风险审查长流程：Orchestrator 触发 risk workflow → Holdings 取仓 → Risk 调 MCP 输出 `RISK_NORMAL / WATCH / ELEVATED` 等诊断，分钟级人工排查压缩为秒级工具化分析。  
▸ Redis + Milvus 多级记忆，长周期对话中减少用户重复补充账户背景。  
▸ FastMCP 协议将持仓/流水/风险/标的说明书工具化，新增工具以小时级完成注册联调。

---

## 一、项目背景与定位

### 1.1 业务痛点

在财富管理客户服务场景中，持仓结构复杂、指标口径不一，传统客服与早期单体 LLM 问答面临：

1. **上下文遗忘**：用户问“我最近为什么亏了”，系统不知道当前持仓与流水，需反复说明账户情况。
2. **高频基础问题耗费算力**：“什么是资产配置”“TWR 和 XIRR 有何区别”等标准答案每次都走大模型，慢且贵。
3. **指标与产品说明易幻觉**：权重、诊断、说明书必须来自工具与文档；纯靠模型容易编造净值、年化或虚假披露。
4. **工具调用散乱、扩展性差**：查持仓要调 DB，查风险要调指标表，查说明书要调产品主数据；硬编码耦合高，换业务线成本大。

### 1.2 产品定位

本系统是一款面向财富管理、基于 **Multi-Agent** 协作架构的智能持仓分析助手。强调**事实查询与解读**，不提供个性化买卖建议或收益承诺。


| 能力维度 | 传统单体 RAG 客服          | 本系统（当前架构）                              |
| ---- | -------------------- | -------------------------------------- |
| 意图处理 | 单一闲聊或固定问答            | LangGraph 动态多 Agent 路由（知识/持仓/业绩/归因/风险） |
| 缓存机制 | 无或简单 Redis K-V       | Milvus L1/L2 语义向量缓存，毫秒级拦截              |
| 检索能力 | 纯向量检索                | Milvus（长文本）+ Neo4j（图谱）混合检索             |
| 外部交互 | 硬编码 Function Calling | FastMCP 标准化工具封装，能力即插即用                 |
| 记忆继承 | 单次会话                 | Redis 短期窗口 + Milvus 长期偏好               |
| 业务闭环 | 只能“说”                | 从持仓查询 → 流水/P&L → 风险诊断 → 变动归因的端到端工具链    |


---

## 二、系统架构详解

### 2.1 整体架构图

系统自上而下分为四层：**接入层、编排层、记忆层、工具层**。

```text
┌─────────────────────────────────────────────────────────────┐
│ 接入层 Access                                                │
│  Vue 前端 SSE 聊天  │  FastAPI /api/chat  │  CLI main.py     │
│  L1 语义缓存拦截（Milvus qa_semantic_cache / preload_cache） │
└────────────────────────────┬────────────────────────────────┘
                             │ miss / bypass
┌────────────────────────────▼────────────────────────────────┐
│ 编排层 Orchestration (LangGraph)                             │
│  START → Orchestrator →                                      │
│    knowledge_agent │ holdings_agent │ performance_agent │     │
│    attribution_agent │ (risk_agent_trigger → holdings→risk) │
│  AgentState: messages / user_id / session_id / memory / meta │
└───────────────┬─────────────────────────────┬───────────────┘
                │                             │
┌───────────────▼───────────────┐ ┌───────────▼───────────────┐
│ 记忆层 Memory                   │ │ 工具层 Tools / RAG         │
│ Redis 短期会话                  │ │ FastMCP wm_portfolio       │
│ Milvus 长期偏好                 │ │ MySQL 持仓/流水/风险表      │
│ PreferenceExtractor 异步抽取    │ │ Milvus wm_portfolio_docs   │
└───────────────────────────────┘ │ Neo4j 知识图谱（可选）       │
                                  └───────────────────────────┘
```

**请求主路径简述：**

1. 用户问题进入 FastAPI（或 CLI），携带 `user_id` / `session_id`。
2. 网关侧尝试 L1 语义缓存；命中则 SSE 直返，不进入 Agent。
3. 未命中则拉取 Redis/Milvus 记忆，组装 `AgentState`，进入 LangGraph。
4. Orchestrator（英文 System Prompt）输出唯一路由标签。
5. 对应专家 Agent 使用 `create_react_agent` + 白名单 MCP/RAG 工具完成推理。
6. 风险意图走 `is_risk_workflow`：先 holdings 取仓，再 risk 调 `analyze_position_risk`。
7. 最终回答经 SSE 流式返回；对话写入短期记忆，可按策略触发长期偏好抽取。

### 2.2 多智能体路由映射


| 路由节点                | 职责                     | 主要工具                                                    |
| ------------------- | ---------------------- | ------------------------------------------------------- |
| `knowledge_agent`   | 资产配置、风险释义、指标口径等教育/披露问答 | `query_vector_db` / `query_knowledge_graph`             |
| `holdings_agent`    | 当前持仓、权重、资产类别与行业        | `get_portfolio_holdings` / `get_portfolio_transactions` |
| `performance_agent` | 区间流水与 P&L 叙事           | `get_portfolio_transactions` 等                          |
| `attribution_agent` | 为何变动、谁贡献损益             | holdings + transactions + factsheet                     |
| `risk_agent`        | 波动/权重代理指标与诊断标签         | `analyze_position_risk`（常接在 holdings 后）                 |


### 2.3 MCP 工具契约（业务层）


| Tool                                               | 说明                           |
| -------------------------------------------------- | ---------------------------- |
| `get_portfolio_holdings(user_id, limit)`           | 当前持仓列表（position_id、权重、市值等）   |
| `get_portfolio_transactions(user_id, limit)`       | 成交/流水（Buy/Sell/Dividend/Fee） |
| `analyze_position_risk(position_id, user_id)`      | 近 7 日风险代理指标 + `diagnosis`    |
| `list_instruments` / `search_instruments`          | 标的目录与模糊检索                    |
| `get_instrument_factsheet(instrument_id, user_id)` | 说明书/披露摘要                     |


统一返回 JSON 字符串外壳：`status` / `data` / `message`；`user_id` 由 `UserIdInjector` 强制注入，防止越权。

### 2.4 数据与 Mock

- MySQL 初始化脚本：`agent/database/init_mock_data.sql`  
  - `portfolio_holdings` / `portfolio_transactions` / `position_risk_daily`
- 教育文档：`mock_data/*.md` → 向量库 `wm_portfolio_docs`  
- 语义缓存预热：`app/preload_cache.py`（WM FAQ）

---

## 三、快速开始（摘要）

```bash
# 1. 配置 agent/.env（LLM：DASHSCOPE_API_KEY + BASE_URL + MODEL；以及 MYSQL_*）
#    Gemini 工具调用建议 MODEL=gemini-2.5-flash（OpenAI 兼容）

# 2. 灌入持仓 Mock
mysql -u root -p <库名> < agent/database/init_mock_data.sql

# 3. 安装依赖并跑 CLI
cd agent && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python main.py --user user_1001 --query "Show my current holdings and weights."

# 4. API + 前端（可选）
cd app && python app_main.py          # :5000
cd front/cloud_agent && npm run dev
```

冒烟建议：

- Holdings：`Show my current holdings and weights.`  
- Performance：`How is my portfolio P&L looking recently?`  
- Risk：`Is my portfolio too concentrated? Review risk.`  
- Attribution：`Why did my portfolio move recently?`  
- Knowledge：`What is asset allocation?`（需 Milvus 文档入库时效果最佳）

---

## 四、合规与产品边界

- 仅查询**当前登录客户**本人数据；拒绝替查他人账户。  
- 回答必须基于工具/文档事实；禁止编造净值、年化、Brinson 数字。  
- **不提供**买卖建议、收益保证或投资推荐话术。  
- 风险诊断标签（如 `RISK_ELEVATED`）为系统代理指标结论，需结合正式风控口径解读。

---

## 五、与原 CloudAgent 的关系

本仓库由企业级云平台智能客服（产品咨询 / 账单 / FinOps / 推广）**业务层重构**而来：

- **保留**：LangGraph 编排骨架、`AgentState`、Memory、MCP 客户端、FastAPI SSE、语义缓存框架。  
- **替换**：Agent 路由与英文 Prompt、MCP 工具语义与表结构、mock 文档、前端场景文案、预热 FAQ。  
- **移除**：云产品推广生图（`generate_ai_poster`）等与 WM 无关能力。

---

## 六、目录速览

```text
agent/
  agents/
    orchestrator.py
    knowledge_agent.py
    holdings_agent.py
    performance_agent.py
    attribution_agent.py
    risk_agent.py
    user_id_injector.py
  mcp_servers/wm_portfolio_server.py
  core/workflow/graph_manager.py
app/            # FastAPI 接入与语义缓存预热
front/          # Vue 聊天前端
mock_data/      # WM 教育/披露 Markdown
```

---

*本文档由原 CloudAgent 项目介绍改写，业务域对齐财富管理持仓分析助手。*