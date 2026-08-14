# SolidForge 使用指南

> [English version](USER_GUIDE.en.md)。本指南按"装上 → 跑通第一个收敛 → 按需加深"的顺序组织。阅读前提：一个可用的 DeepSeek Harness（`dsh` 在 PATH 上，`$DSH_HOME` 已初始化）。

## 目录

1. [安装与激活](#1-安装与激活)
2. [Arm 一个项目](#2-arm-一个项目)
3. [跑通第一个收敛任务](#3-跑通第一个收敛任务)
4. [运行记录与 rightness：读懂你的收敛](#4-运行记录与-rightness读懂你的收敛)
5. [配置异源评审](#5-配置异源评审)
6. [五个技能各自什么时候用](#6-五个技能各自什么时候用)
7. [调参与常见问题](#7-调参与常见问题)

---

## 1. 安装与激活

```bash
git clone https://github.com/maskshell/solidforge-dsh.git && cd solidforge-dsh
bash scripts/install.sh     # → $DSH_HOME/.agent-presets/solidforge/（幂等，可重复执行）
```

然后：

- **会话级激活**：在 DSH 中新建会话时选择 **solidforge** preset。该会话自动获得五个技能、22 个角色代理、arm-tools 命令与 SolidForge 人格。
- **结构化插件（可选但推荐）**：三个动态 Cordis 插件把门禁与不变量变成结构强制（代码在你的工作区之外，代理改不了）：
  - `loop-gates` —— 每次 edit/write 触发快速门 / 蓝图守卫 / 终态计数器（`tools/pre-execute` deny + `tools/post-execute` block 反馈）；
  - `run-record` —— `solidforge_run_record` 工具，强制 `rightness: human_confirm_required`；
  - `hetero-review` —— `solidforge_hetero_review` 工具，一键出进程异源评审。
  
  激活方式：在一个带 cordis 工具集的会话（如 cordis preset 会话）里，对
  `$DSH_HOME/.agent-presets/solidforge/plugins/*.host.js`（已烘焙绝对预设根路径）逐个
  `cordis_define` + `cordis_run`。**为什么不在 preset 里自带**：会注册进程级 provider 的那一行（`tool-cordis`）与 cordis preset 在单进程多 preset 部署下必冲突——与 standard preset 同样刻意留白。
- 不激活插件也能用：门禁脚本仍可从 `infra/` 直接调用（咨询模式），技能照常工作，只是失去逐工具调用的自动拦截。

## 2. Arm 一个项目

插件不碰宿主项目，所以每个目标项目需要一次显式供给（Layer 2）：

```bash
python3 $DSH_HOME/.agent-presets/solidforge/skills/parallel-development/infra/install/arm.py <你的项目目录>
# 可选：--with-tools 把门禁工具加进项目自身 dev deps；--scaffold-configs vale,semgrep,spectral 生成外部工具模板
```

Arm 会做（幂等，可 `--revert --apply` 撤销）：

- 为**检测到的语言**复制架构契约配置（Python/Web/Swift/Rust/Java/Go；未检测到则诚实跳过）；
- 向项目 `AGENTS.md` 追加 **L1 宪法**（不可编码红线，评审外环按 Blocker 处理）；
- 复制意图蓝图模板 + cold-start patterns 到 `docs/intent-blueprints/_templates/`；
- 向 `.gitignore` 追加循环运行态（`.solidforge/loop/`）与 `.env`/`.env.solidforge`（活密钥不提交）；
- 复制 `.env.solidforge.example`（异源配置占位，无真实密钥）；
- 打印门禁状态表（缺失工具 → 降级不静默绿）。

## 3. 跑通第一个收敛任务

在已 arm 项目的 solidforge 会话里说：

> 「并行实现 X，TDD」/ 「修这个 bug，测试先行」/ 「重构模块 Y，保持行为」

会话中的代理会：冻结意图蓝图（或消费已有蓝图）→ RED/GREEN 并行派发子代理 → 进收敛循环：**内环**（逐编辑快速门 lint/format；收敛点架构契约门 + 测试集不缩水 + 覆盖率条件）→ **外环**（同源 `code-reviewer` 子代理逐条对抗 findings，语义线 + 意图线双查）→ 按裁决收敛/重写/回滚。断路器全程看护：同指纹 ≥3 次 → 升级外环；内环 ≥8 轮 → 降级拆分；预算耗尽 → 硬终止出诊断。

进度与状态都在 `.solidforge/loop/loop-state.json`，可用 `loop_state.py summary` 查看。

## 4. 运行记录与 rightness：读懂你的收敛

任何终态（converged / suspended / hard_terminated）都应产出一份运行记录：

- 经插件：调用 `solidforge_run_record` 工具；
- 经脚本：`python3 <preset>/skills/parallel-development/infra/scripts/loop_state.py run-record`（文件落到 `.solidforge/loop/runs/`）。

记录里两个字段永远分家：

| 字段 | 含义 | 谁写 |
| --- | --- | --- |
| `process_converged` | 双环是否绿、DoD 是否满足（机器可查） | 循环/脚本 |
| `rightness` | 结论是否正确 | **没人能写**——schema 常量 `human_confirm_required`；正确性是带外的人类行为 |

**读懂纪律**：绿 ≠ 对。任何"跑完了所以是对的"的说法在本体系里没有 schema 出口。

## 5. 配置异源评审

异源 = **同 Harness、异 LLM、出进程**：wrapper 起一个新鲜无状态的 `dsh --profile headless` 子进程，用一次性 `DSH_HOME` 把 `agent-default-model` 钉到一条**不同模型家族**的 pi-ai 目录路由。三步：

1. **建 profile**（文件名 = 路由名）：`cp profiles/minimax-cn.json profiles/<路由>.json`，改 `model` 与 `_family`（模型谱系名，用于同源守卫）；
2. **填密钥**：凭证变量名由路由派生（`<UPPERCASE(路由)>_API_KEY`，pi-ai 官方约定），放进三层 env 链任一层：`shell > <project>/.env.solidforge > <project>/.env > <preset-root>/.env.solidforge`；
3. **选择**：`HETERO_PROFILE=<路由a>,<路由b>`（pd 腿）与 `HETERO_DOC_PROFILE`（csr 腿，独立）写进 `.env.solidforge`。

内置守卫：`_family` 是编排者谱系（deepseek）的 profile **直接拒绝**；双 profile 同族 → coverage 诚实注记"不加盲点多样性"；未声明 `_family` → 注记"守卫未生效"。未配置任何 provider → fail-fast 打印武装指引，**绝不静默回退**。

触发时机（协议）：异源腿是 **opt-in**，只对高风险项（ADR 级决策 / 安全-正确性敏感 / 同源低置信）开；同源环永远先跑，异源只做加法。裁决表：双报 → 采纳；仅同源 → 采纳（主）；仅异源 → 升级人审；双空 → 通过；异源降级（超时/额度）→ 采同源并留痕。

## 6. 五个技能各自什么时候用

| 技能 | 何时用 | 产出 | 特别注意 |
| --- | --- | --- | --- |
| `parallel-development` | 实现代码：feature/bugfix/重构/TDD/多代理并行 | 收敛的代码 + 运行记录 | 实现执行引擎，不是思考引擎；写 PRD/架构文档请走下一个 |
| `blueprint-crafting` | 写/重写 PRD、架构设计、迭代计划、可执行摘要、研究 | 冻结的意图蓝图（收敛校验过） | 产出的是"技术上可验收的 PRD"，产品 PRD 另说 |
| `cross-source-review` | 一份高质量文档需要对抗收敛（需求/设计/wiki） | 收敛的文档 + convergence-record | **过程轴**；它不判断文档"对不对"（结果轴，人） |
| `primary-source-verification` | 核对文档的引用/事实声明 | 逐声明判定 + coverage-record | **取回原文**当 oracle；`oracle_verified_under_known_coverage`，绝不 `correctness_converged` |
| `prior-art-search` | 核对文档的新颖性声明 | 逐声明碰撞判定 + collision-record | 向后查未引用先有技术；绝不 `novel_confirmed` |

csr 的 ODP-5 判别器：短文档 / 本地引用为主的文档**不付 psv gate 的账**（csr 单跑即可）；外部引用密集或长文档才先跑 psv GATE MODE（GO/NO-GO），csr 收敛后再跑 psv full-M 作为唯一权威覆盖记录。


### 联用链路：典型组合

单技能表之后是组合表——技能组成论文 §6 的 specify→implement 流水线：

| 链路 | 触发对话（示例） | 产物链 | 诚实边界 |
| --- | --- | --- | --- |
| `csr → bc → pd` | 「把这份设计文档收敛，然后实现它」 | convergence-record → 冻结蓝图（PRD/架构/迭代计划）→ 收敛代码 + run-record | csr 不判对错；bc 的 rightness 恒 `human_confirm_required` |
| `psv → csr` | 「这份文档引用很多外部来源，先核实再收敛」 | gate 记录（非权威）→ convergence-record → full-M coverage-record（唯一权威） | psv 绝不 `correctness_converged`；K>0 升级人审 |
| `psv + pas` | 「这篇论文的引用和新颖性都帮我查一遍」 | coverage-record + collision-record（两条结果轴并行） | pas 绝不 `novel_confirmed` |
| `psv → csr → bc → pd` | 「从带引用的规格出发，交付可运行实现」 | 四条记录全链 | 异源腿 opt-in；未运行/降级如实报告 |

**全链路对白走读**（`psv → csr → bc → pd`）：

> 「这是一份带外部引用的需求草案 `docs/req.md`，请从它出发交付可运行实现。」

1. **psv GATE MODE**——claim-extractor 抽取 load-bearing 声明 → 逐条对源裁决 → GO/NO-GO。短文档/本地引用为主时 ODP-5 判别器会跳过这一步（省 ~1.5 轮）。
2. **csr**——同源 `doc-reviewer` 多轮对抗 + 高风险项加异源（出进程异族）。每轮 finding 逐条 disposition（修复/拒绝/升级）→ `substantive_converged`。**它收敛的是过程轴；需求对不对由你确认。**
3. **bc**——plan-reviewer 外环 + 确定性内环（constraints-check）→ 产出并**冻结**意图蓝图。冻结后守卫拒绝任何编辑；改动只能走修订通道。
4. **pd**——按蓝图 RED/GREEN 并行派发子代理 → 双环收敛 → 断路器看护 → 终态产出 run-record（`process_converged` 与恒定的 `rightness` 分家）。
5. **psv full-M（收尾，仅规则 13 文档）**——csr 收敛后对最终文本做权威逐声明覆盖记录。


**显式引用写法**（把缩写直接写进提示，最可靠的触发方式）：

```
> psv → csr → psv → bc → pd       把 docs/req.md 从引用核查一路做到可运行实现
> csr → bc → pd                   收敛 docs/design.md，冻结蓝图，然后实现
> psv + pas                       对 docs/paper.md 并行做引用核查与新颖性碰撞
> pd                              直接对当前任务跑实现收敛循环
```

缩写对照（全名与缩写均可触发）：

| 缩写 | 技能 | 缩写 | 技能 |
| --- | --- | --- | --- |
| `pd` | parallel-development | `psv` | primary-source-verification |
| `bc` | blueprint-crafting | `pas` | prior-art-search |
| `csr` | cross-source-review | | |

## 7. 调参与常见问题

**调参**（`loop_state.py init` 旗标）：内环上限 `M=8`、同指纹阈值 `N=3`、token 上限 2M、时间上限 1800s、成本上限 5.0、步数上限 200。时间轴最可靠；token 是估算。

**常见问题**：

- *「no heterogeneous provider configured」*——正常：fail-fast 默认。按 §5 武装，或明确知道自己不需要异源。
- *「profile X (route Y) needs the credential env var $Z」*——三层链里没找到密钥；变量名是 route 派生的，见 §5。
- *异源腿 `hetero-subprocess-timeout`*——冷启动瞬态；按文档提高 `--timeout` 或降档重试，**不要**改路由别名规避（暖调用深度受损）。
- *门禁工具缺失*——对应门降级并如实报告（coverage 注记），绝不假装绿；`--with-tools` 补齐。
- *测试集不许缩水 / 硬编码绕过*——内环门（AC→测试名映射 + 附加条件）会拦；蓝图守卫拦冻结文档编辑。
- *我想改收敛纪律*——先读 `preset/skills/parallel-development/references/design-decisions.md`（ADR 日志），改后跑 `infra/test/` 全套自检。

**自检命令**（每个技能 `infra/test/` 都有一组；节选）：

```bash
python3 preset/skills/parallel-development/infra/test/hetero_review_wiring.py
python3 preset/skills/parallel-development/infra/test/plugin_layout.py
python3 preset/skills/blueprint-crafting/infra/test/run_record_schema.py
python3 preset/skills/cross-source-review/infra/scripts/converge_fixtures/verify.py
```

更完整的验证记录（含本仓库自举评审的两起异源假阳性案例）见 [test/verification.md](test/verification.md) 与 [docs/dogfood/](docs/dogfood/)。
