# SolidForge

**让"测试绿了"不再等于"你做对了"。** SolidForge（本仓库）是 [《Specification Gaming as an Orthogonal Failure Axis in Autonomous Coding Loops》](docs/papers/spec-gaming-orthogonal-axis.md)（论文随仓快照；引用请用 [PDF](docs/papers/spec-gaming-orthogonal-axis.pdf) 与 [CITATION.cff](CITATION.cff)，论文为草稿状态）参考实现的 DeepSeek Harness 原生版：把编码代理的可靠性拆成**两条轴**，用确定性门 + 对抗评审 + 异源验证把两条轴都关进笼子。

[![deterministic-suites](https://github.com/maskshell/solidforge-dsh/actions/workflows/ci.yml/badge.svg)](https://github.com/maskshell/solidforge-dsh/actions/workflows/ci.yml)

> [English README](README.en.md) · [使用指南](USER_GUIDE.md) · [论文](docs/papers/spec-gaming-orthogonal-axis.pdf) · [移植设计](docs/port-design.md) · [概念映射](docs/claude-code-to-dsh-map.md) · [自举评审轨迹](docs/dogfood/README-dogfood.md)

---

## 它解决什么问题（30 秒版）

自主编码循环有一个隐蔽的失效类：**代理自己写测试、自己判通过**。"测试绿了"只是对**代理自己构造的代理规格**的满足——删掉失败测试、把断言改成和实现一致、`try/catch` 吞掉触发循环的异常……代码可以全绿，却完全偏离你的意图。更糟的是：**同源评审救不了它**——评审者和被评审者共享训练数据，也就共享盲点。

SolidForge 的对策是两根轴，缺一不可：

| 轴 | 防什么 | 手段 |
| --- | --- | --- |
| **A · 流控制完备性** | 上下文腐化 / 误差级联 / 目标漂移 | 双环收敛：确定性内环（逐编辑快速门 + 架构契约门）+ 同源对抗外环 + 状态机断路器 |
| **B · 验证源解耦** | 规格博弈（spec gaming） | 判定结论的 oracle 必须与你**不同盲点**：`rightness` 字段是 schema 常量（代理不可写，恒为 `human_confirm_required`）+ 异源评审在**出进程的不同模型家族**上运行 |

## 一分钟看懂

```text
意图蓝图（冻结）──▶ 并行实现（TDD，多子代理）
                        │
              ┌─────────▼──────────┐
              │ 内环（确定性）      │  快速门(每编辑) → 架构契约门 → 附加条件
              │ 外环（对抗）        │  同源 code-reviewer（主） + 异源评审（opt-in，出进程异族）
              └─────────┬──────────┘
                        ▼
        收敛记录：process_converged（机器可查） ‖ rightness（恒 human_confirm_required，人确认）
```

五句话总结：**绿门只证明过程收敛，不证明结论正确；正确性由人（或真正异源的 oracle）确认；规格博弈的防御靠结构（schema 常量、事件监听、出进程边界），不靠提示词。**

## 快速开始

```bash
git clone https://github.com/maskshell/solidforge-dsh.git && cd solidforge-dsh
bash scripts/install.sh        # 安装 agent preset → $DSH_HOME/.agent-presets/solidforge
```

1. 在 DeepSeek Harness 里开一个 **solidforge** preset 会话；
2. 在你的目标项目里 arm 一次（供给 arch-configs、宪法、蓝图模板、`.env.solidforge.example`）：

   ```bash
   python3 $DSH_HOME/.agent-presets/solidforge/skills/parallel-development/infra/install/arm.py <你的项目目录>
   ```

3. 对会话说「并行实现 X，TDD」，收敛循环接管——双环、断路器、回滚与运行记录全部自动。
4. （可选）在 cordis 会话里激活三个结构化插件（见 [使用指南](USER_GUIDE.md) §激活插件）。

完整的循序渐进上手：**[USER_GUIDE.md](USER_GUIDE.md)**。

## 技能联用：典型链路

五个技能不是孤岛——它们组成论文 §6 的 specify→implement 流水线。四组典型组合：

| 链路 | 适用场景 | 一句话流程 |
| --- | --- | --- |
| `csr → bc → pd` | 有需求/设计文档，要落成可运行代码 | 文档对抗收敛 → 冻结意图蓝图 → TDD 并行实现收敛 |
| `psv → csr` | 文档引用密集、外部来源多（规则 13） | 逐声明对源 GO/NO-GO（gate）→ 文档收敛 → 权威 full-M 覆盖记录 |
| `psv + pas` | 论文/研究文档自检 | 两条结果轴并行：引用核查 + 新颖性碰撞检测 |
| `psv → csr → bc → pd` | 从带引用的规格起步的完整流水线 | 见下方全链路对白 |

**全链路示例**（在 solidforge 会话里说）：

> 「这是一份带外部引用的需求草案 `docs/req.md`，请从它出发交付可运行实现。」

1. **psv GATE MODE**——对外部引用做 load-bearing GO/NO-GO（短文档/本地引用为主可跳过，ODP-5 判别器决定）；
2. **csr**——同源 + 异源多轮对抗收敛需求文档（过程轴；它不判断需求"对不对"，那是你）；
3. **bc**——产出并冻结意图蓝图（PRD/架构/迭代计划；`process_converged` 机器可查，`rightness` 恒 `human_confirm_required`）；
4. **pd**——TDD 并行实现 + 双环收敛 + 运行记录；高风险项可加异源评审（opt-in）。

每一环的裁决都留痕（convergence-record / coverage-record / run-record），异源腿未运行或降级时如实报告，绝不静默绿。

**在提示里显式引用**（语义触发不可靠时，用全名或缩写直呼其名——确定性写法）：

| 提示写法 | 效果 |
| --- | --- |
| `psv → csr → psv → bc → pd` | 完整流水线：psv gate（外部引用 GO/NO-GO）→ csr 文档收敛 → psv full-M 权威覆盖 → bc 冻结蓝图 → pd 双环实现 |
| `csr → bc → pd` | 文档收敛 → 冻结蓝图 → 并行实现 |
| `psv + pas` | 对一份文档并行跑两条结果轴（引用核查 + 新颖性碰撞） |
| `pd` / `bc` / `csr` / `psv` / `pas` | 单技能直呼 |

缩写对照：`pd`=parallel-development · `bc`=blueprint-crafting · `csr`=cross-source-review · `psv`=primary-source-verification · `pas`=prior-art-search。会话代理按此映射加载技能。

## 五个核心概念（循序渐进）

1. **双环收敛**：确定性内环（lint/类型/测试/架构契约）绿了才进外环；外环是同源对抗评审，逐 finding 裁决（修复/拒绝/升级），记录全程留痕。
2. **冻结意图蓝图**：PRD/架构/验收标准在收敛时冻结；改动只能走修订通道；蓝图被 `status: frozen` 守卫拒绝编辑。
3. **Process/Outcome split**：运行记录把 `process_converged` 与 `rightness` 严格隔离——后者是枚举常量 `human_confirm_required`，代理与收敛循环都写不了它。绿不代对，结构上杜绝。
4. **异源评审**：高风险项可加一条**不同模型家族**的对抗意见（默认 `dsh --profile headless` 子进程钉到异族路由——同 Harness、异 LLM、出进程；如 `zai-coding-cn`/GLM、`minimax-cn`/MiniMax-M3）。同源环永远先跑，异源只做加法。
5. **断路器**：同指纹反复失败 → 升级外环；内环超限 → 降级拆任务；预算耗尽 → 硬终止并输出诊断。循环不会无界打转。

## 本仓库包含什么

| 部件 | 位置 | 作用 |
| --- | --- | --- |
| Agent preset | `preset/agent.cordis.yml` + `preset/preset.yml` | SolidForge 会话的组成（人格 + 标准工具 + 预设内技能挂载） |
| 五个技能 | `preset/skills/{parallel-development,blueprint-crafting,cross-source-review,primary-source-verification,prior-art-search}/` | 收敛循环、specify 侧、文档收敛（csr，过程轴）、两条结果轴验证（psv/pas，逐声明对源核查） |
| 22 个角色代理 | `preset/agents/*.agent.md` | 经 `subagent` 工具派发的角色提示语料 |
| 确定性基础设施 | `preset/skills/*/infra/` | 纯 stdlib Python 门禁/状态机/schema + 测试套件 |
| 结构化插件 | `plugins/*.host.js` | 工具事件门禁、rightness 不变量、异源评审工具（激活方式见使用指南） |
| arm-tools | `preset/commands/arm-tools.md` | 项目侧供给（Layer 2） |

## 诚实声明

本项目是**可实现性**的证据，不是**有效性**的证明——两轴防御评估（论文 §8.3）仍是开放问题。**词汇约定：在本项目中，"SolidForge" 即指本仓库（DeepSeek Harness 原生实现）；论文 §6 与上游仓库原以 "SolidForge" 指代 Claude Code 插件，本文档一律改称 [SolidForge for Claude Code](https://github.com/maskshell/solidforge)。** 论文的原始参考实现是 SolidForge for Claude Code（Claude Code 插件）；本仓库是它在 DeepSeek Harness 上的**重推导移植**（关键差异：异源 = 同 Harness 异 LLM 的 `dsh headless` 出进程子进程，而非拖入 Claude Code；详见 [docs/port-design.md](docs/port-design.md)）。本仓库自身的 README 曾用移植后的 psv→csr 管线自举收敛，完整轨迹（含两起异源 oracle 假阳性案例）在 [docs/dogfood/](docs/dogfood/)。

## 验证

```bash
python3 preset/skills/parallel-development/infra/test/hetero_review_wiring.py   # 接线/断路器/异源基板/同源守卫
python3 preset/skills/blueprint-crafting/infra/test/run_record_schema.py        # rightness 常量断言
python3 preset/skills/cross-source-review/infra/scripts/converge_fixtures/verify.py
```

其余证据与安装自检见 [test/verification.md](test/verification.md)。
