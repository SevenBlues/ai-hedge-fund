# Serenity Chokepoint Engine 瓶颈/咽喉量化引擎

复刻网红交易员 **Serenity (@aleabitoreddit)** 的 *Chokepoint Theory（咽喉理论）*。
**这个策略只做一件事**：靠深度投研，在 AI 算力供应链里挑出一个**高确定性、高收益**的股票池——
**在胜率尽量确定的前提下，把收益率做到最大**。

> ⚠️ **免责声明 / Disclaimer**：本模块是对一套**公开描述**的投资框架的**教育性复刻**。
> `chokepoint_data.py` 里的数据是根据公开报道（Serenity 的 X/Substack、
> singularityresearchfund、archetype-research、semiconstocks tracker、公司财报等，截至 ~2026-05）
> **手工整理的近似估计值**，用于演示方法论，**不是实时财务数据，也不构成任何投资建议**。

---

## 产品就是这个股票池 / The product = the pool (`pool.py`)

```bash
python -m src.serenity.run_screen            # 默认输出：高确定性股票池
python -m src.serenity.run_screen --live     # 用实时行情收紧股票池
```

流程三步，对应 Serenity 真实选股逻辑：

```
深度投研（供应链建图 + 瓶颈评分的 universe）
   → 确定性闸门  : 只留胜率尽量确定的（瓶颈分高 + 扛得住对抗红队 + 蒙特卡洛 P(EV>0) 高）
   → 收益最大化  : 在闸门内，按 win_prob × 上行 给仓位，把收益压在最高确定性的名字上
```

样例输出（curated，8 只；`--live` 收紧到 6 只）：

```
TIER 1 CORE   SIVE  win 68% P(EV>0)100% 上行5.0x exp.return+253% 权重23%  CW激光CPO咽喉/并购期权
              AXTI  win 72% P(EV>0)100% 上行3.8x exp.return+191% 权重17%  InP衬底「霍尔木兹海峡」
TIER 2 BUILD  POET / AEHR / VNP ...
TIER 3 WATCH  IQE / INPACT / SOI ...
POOL BLEND: 加权胜率 67%   加权期望收益 +153%（每 $1，若 thesis 在建模周期内兑现）
```

每个名字都给出：所在供应链层、一句话 thesis、催化剂、**最强反方风险**（来自对抗红队）、胜率、上行倍数、期望收益、确定性仓位。

> 下面的评分/对抗/回测都是**支撑这个股票池的证据链**，不是要做一个多维交易系统。

## 核心思想 / Core idea

不追「鱼肚」（NVIDIA、TSMC），去找寿司里那片不可或缺的「紫苏叶」——
物理上不可替代、供给高度集中、认证周期极长、机构尚未发现的小市值「螺丝钉」环节。
就像全球 20% 石油必经霍尔木兹海峡，AXTI 之于光子学 InP 衬底就是同一种咽喉。

## 引擎做了什么 / What it computes

对每个供应链节点输出两类东西，对应 Serenity 的流程：

1. **Chokepoint Score (0–100)** — *这是不是真瓶颈？* 六大支柱加权（`scoring.py`）：

   | 支柱 | 权重 | 含义 |
   |------|-----:|------|
   | supply_concentration | 22 | Top1–3 份额，>70% 为硬门槛，超过后非线性加分 |
   | irreplaceability | 22 | 材料/物理替代难度 × 认证周期长度 |
   | demand_supply_gap | 16 | 终端 AI 需求 CAGR 远超该节点产能 CAGR |
   | qualification_barrier | 16 | 已被 hyperscaler/NVDA 认证 + 12–24 月周期 |
   | information_asymmetry | 14 | 小市值 + 低机构持股 + 少分析师覆盖（alpha 来源）|
   | catalyst_optionality | 10 | 内部增持、高 short interest、并购溢价、垂直整合 |

2. **Asymmetric payoff（不对称赔率）** — *这是不是高赔率赌注？*
   把结构性护城河映射成**胜率 win_prob**，对 ramp 倍数（venture-style，非 TTM P/S）建模**上行 upside**，
   对稀释/估值/技术路线/流动性风险建模**下行 downside**，得到：
   - `odds_ratio = upside / downside`（赔率）
   - `expected_value`（每 1 美元的期望收益）
   - `kelly_weight`（1/10 分数 Kelly + 10% 上限的建议仓位，Step 5 仓位管理）

此外：
- `supply_chain.py` 用 **NetworkX** 构建依赖图（A→B 表示 A 依赖上游 B），用 betweenness /
  反向 PageRank / 后代数等**拓扑中心性独立佐证**哪些节点真的是咽喉（而非仅靠手工标注）。
- `demand_model.py` 用「算力 CAGR × CPO 光学强度提升」投影光学需求 vs 供给产能的缺口。

## 可视化报告 / Visual report

![Serenity Chokepoint Report](sample_report.png)

四象限：①供应链依赖图（节点大小/颜色=拓扑关键度）②瓶颈分数条形图
③赔率 vs 信念散点图（右上为高赔率区，气泡=Kelly 仓位）④需求 vs 产能缺口投影。

## 用法 / Usage

```bash
# 默认：直接输出高确定性股票池（产品本体）
python -m src.serenity.run_screen
python -m src.serenity.run_screen --live              # 实时行情收紧股票池

# 以下都是「证据链」，按需打开：
python -m src.serenity.run_screen --full --png out/report.png --json out/scores.json  # 完整评分表+供应链图
python -m src.serenity.run_screen --live --adversarial # 对抗红队明细

# 真·多模型对抗验证（需配置 OPENAI/ANTHROPIC/GOOGLE API key）
python -m src.serenity.run_screen --adversarial --llm

# 按不同维度排序
python -m src.serenity.run_screen --top 10 --sort odds_ratio
```

依赖：`pandas numpy networkx matplotlib scipy yfinance`（已在 `pyproject.toml`）。

## 活数据版 / Live data (`live_data.py`)

`--live` 用 Yahoo Finance **只刷新市场派生字段**（市值、机构持股、分析师覆盖数、
做空比例、trailing EV/Sales），而**保留手工的结构性字段**（Top3 份额、不可替代性、
认证周期、需求/产能 CAGR、ramp 倍数）——因为后者是分析师领域判断，没有任何公开数据源能机械抓取。

- 离线/被墙时**自动降级**回 curated 数据（`live=False`），不会 hang、不会报错；
- 非美股自动映射 Yahoo 后缀（`SIVE.ST`、`IQE.L`、`SOIT.PA`、`VNP.TO` …）；
- 返回**变更日志**，逐字段审计 live vs curated。

> 实测：接活数据后 AXTI 从 ~$0.85B 涨到 ~$6.7B、机构持股升到 ~58%、trailing EV/Sales ~58x —
> 「未被发现」的 alpha 已部分兑现，引擎据此把它从 #2 下调，并触发估值警报。

## 对抗性验证 / Adversarial validation (`adversarial.py`, Step 3)

复刻 Serenity 的「红蓝对抗」：重仓前用最严苛的 Devil's Advocate 攻击 thesis，只有多轮存活才给高信念。

1. **确定性攻击向量**（离线可跑，9 类）：估值已 price-in、供给弹性/二供、技术路线（CPO vs 可插拔）、
   已被发现（机构持股/覆盖度过高 → 没有 alpha）、稀释融资、流动性/微盘、客户集中、地缘（中国镓/铟/稀土管制）。
   每个给出 severity(0-1)+具体反方论点+蓝方反驳 → 汇总成 **resilience（韧性）** 和 **adversarial_ev（折价后期望值）**。
2. **蒙特卡洛**：对胜率/上行/下行加噪声 4000 次，报告 **P(EV>0)** —— 对「假设本身」的对抗测试。
3. **存活判定**：韧性≥0.45 且 无单点致命漏洞(severity≥0.8) 且 P(EV>0)≥55% 且 基准 EV>0。
4. **`--llm`**：可选，把 thesis 路由给 GPT/Claude/Gemini 多模型独立红队并汇总反对意见，无 key 时优雅降级。

样例（活数据）：

```
TKR      Resil  AdjEV  P(EV>0)  Survive  Strongest objection
SIVE      0.64   0.94      99%      YES  [valuation_priced_in] Implied EV/Sales ~60x ...
AXTI      0.67   0.51      97%      YES  [valuation_priced_in] Implied EV/Sales ~58x ...
POET      0.55   0.39      96%       no !valuation_priced_in  Implied EV/Sales ~1677x（接近无营收）
COHR      0.65   0.07      66%       no !already_discovered   机构持股 89% / 21 家覆盖 → 没有信息差
NVDA      0.67  -0.06      28%       no !already_discovered   机构持股 71% / 58 家覆盖
SURVIVORS: SIVE, VNP, IQE, INPACT, AAOI, AXTI, XFAB, SOI
```

只有 survivors 才进高信念仓位，其余仅入观察名单。

### 作为对冲基金 agent 运行 / As a hedge-fund agent

引擎也被包装成 `serenity_chokepoint_agent`，已注册进 `src/utils/analysts.py`，
可在主程序中和巴菲特、Cathie Wood 等 persona 一起投票：

```bash
poetry run python src/main.py --tickers AXTI,SIVE,AAOI,POET
# 然后在分析师列表里勾选 "Serenity (Chokepoint)"
```

universe 内的票直接用结构性评分；universe 外的任意票则用实时基本面
（小市值 + 高毛利 + 高研发 + 营收集中）做瓶颈代理评分。

## 当前样例输出（节选）

```
 # TKR     L  CPscore  Win%    Up  Down  Odds   E[V]  Kelly  Flags
 1 SIVE    3     74.4   68%  5.0x   68%   7.4  +2.52   9.3%  UNDISCOVERED, MOAT:LONG-QUAL, M&A-TARGET ...
 2 AXTI    4     82.7   72%  3.8x   50%   7.6  +1.91  10.0%  CONCENTRATED(>70%), MOAT:LONG-QUAL
 3 POET    3     63.5   64%  3.8x   69%   5.5  +1.50   7.9%  UNDISCOVERED, MOAT:LONG-QUAL ...
```

排名与 Serenity 实际重仓（AXTI、SIVE）一致，且图拓扑佐证 AXTI 有最多下游依赖。

## 回测层 / Backtest (`backtest.py`)

`--backtest` 用真实 Yahoo Finance 历史价格检验「认证 → 放量 → 重估」这条因子到底赚不赚钱，三个测试：

1. **组合回测**：把引擎的 Kelly 加权 survivor 组合（constant-mix 日度再平衡）对比等权 universe、NVDA、QQQ。
2. **因子回测**：高 Chokepoint Score 篮子 vs 低分篮子的多空价差——「咽喉度」本身是不是个付费因子。
3. **事件研究**（最贴近用户问题）：用 **单日 +12% 跳涨** 代理「认证/放量重估」事件，测量事件后 **60 日前向收益** vs 无条件基线——如果咽喉真的会放量，跳涨后应是**延续**而非均值回归。

```bash
python -m src.serenity.run_screen --backtest --period 2y --png out/r.png
```

![Backtest](sample_backtest.png)

实测结果（2 年窗口，截至 ~2026-05）：

```
1) PORTFOLIO
   Engine survivors (Kelly)   ret=+1506%  CAGR=58.2%  Sharpe=1.77  maxDD=-33.9%
   Equal-weight universe      ret=+1140%  CAGR=51.4%  Sharpe=1.67  maxDD=-38.4%
   NVDA                       ret=  +91%  CAGR=11.3%  Sharpe=0.53           <- 「鱼肚」远远跑输
   QQQ                        ret=  +65%  CAGR= 8.7%  Sharpe=0.74
2) FACTOR  high-chokepoint CAGR 126%  vs  low-chokepoint 67%（咽喉度是付费因子）
3) EVENT STUDY  +12% 跳涨后 60 日前向 +58.7%  vs 基线 +28.4%  =>  EDGE +30.3%
                （ramp-continuation CONFIRMED，227 次事件，命中率 63%）
```

> **诚实声明**：组合/因子测试是**样本内 + 幸存者偏差**（universe 是事后选的），且赶上 2024-26 AI/光子学大牛市，
> 数字会被放大；事件研究是其中最接近 point-in-time 的检验，仍显示明确正向 edge。本地货币计价（忽略汇率）。
> **仅供学习，不是真实业绩，不构成投资建议。**

## 真·样本外回测 / Out-of-sample walk-forward (`oos_backtest.py`)

`--oos` 修掉上面回测的三个泄漏，给出**真正样本外**的结论：

1. **非事后选股的 universe**：固定一份 ~40 只 AI 硬件/半导体/光学/材料供应链股票，**故意混入落后股和非咽喉股**
   （INTC、TXN、MCHP、SWKS…）。每月**由因子选股**，不是我手选赢家。
2. **point-in-time 信号**：每个再平衡日只用**当时已知的价格**算分——12-1 动量（无前视的经典因子）+「重估延续」标记
   （上月是否出现 ≥20% 大涨 = 认证/放量缺口的价格代理）。这就是事件研究验证过的咽喉「放量」因子的纯价格、机械版。
3. **训练/测试切分**：规则（回看期、top-K、跳涨阈值）**只在早期 train 窗口固定**，held-out test 窗口从不用于调参或选股。
   月度不重叠持有 → 无收益重叠泄漏；某股 IPO 前自动排除 → 无上市前的幸存者前视。

```bash
python -m src.serenity.run_screen --oos --period 8y --png out/r.png
```

![OOS walk-forward](sample_oos.png)

实测结果（8 年，39 只可取到的标的，train/test 切在 2023-05）：

```
                          收益      CAGR    Sharpe   vs SOXX
IN-SAMPLE  (train 19-23)
  strategy               +116%    22.2%    0.71    -3.0pts  ← 训练期不但没占便宜，还略输（证明没过拟合）
  SOXX                   +137%    25.2%    0.89
OUT-OF-SAMPLE (test 23-26)
  strategy             +1351%   143.9%    1.95   +89.9pts  ← held-out 窗口大幅跑赢半导体板块本身
  SOXX                  +266%    54.1%    1.40
裁决：HOLDS OUT-OF-SAMPLE (test Sharpe 1.95 vs SOXX 1.40)
```

**为什么这个结论可信**：训练期因子**略微跑输** → 说明 test 的超额收益**不是**在同一段数据上调参调出来的；
而且基准是 **SOXX（半导体板块本身）**，所以这不是「半导体都涨了」——是**在半导体内部用放量因子选股**赢过了整体持有。

> **诚实声明**：① test 窗口恰好是 2023+ AI capex 大爆发期，也正是咽喉理论预言重估发生的 regime（既是验证也是顺风）；
> ② universe 是 2026 年画的、Yahoo 会丢掉多数退市股 → 残留幸存者偏差；③ 月度纯多头。**仅供学习，非真实业绩，不构成投资建议。**

### 稳健性检验 / Robustness（regime + 滚动多折）

`--oos` 还会输出两项稳健性检验，把「一次切分的运气」压实成「跨 regime / 多窗口的分布」：

![OOS robustness](sample_oos_robust.png)

```
1) 分 regime（factor vs SOXX）—— 关键压力测试是 2022 熊市
   regime              strat CAGR  Sharpe   SOXX CAGR   excess
   2020 COVID rebound      50.1%    1.24       52.9%    -2.8%
   2021 bull               41.4%    1.63       44.1%    -2.7%
   2022 BEAR              -30.9%   -0.45      -35.1%    +4.2%   ← 熊市里反而比板块少跌
   2023 AI ramp            63.6%    1.35       67.3%    -3.6%
   2024                    46.0%    1.82       13.0%   +33.0%
   2025-26                319.1%    2.56       99.8%  +219.4%
2) 滚动 12 个月、24 折
   hit-rate vs SOXX:  62% 的窗口跑赢板块
   median excess:     +6.2 pts（mean +39.3，区间 -41..+653）
   median Sharpe:     strategy 1.01  vs  SOXX 1.27
   => edge CONSISTENT（hit-rate≥60% 且 中位超额>0）
```

**诚实的细节解读**（这才是关键）：
- **2022 熊市站得住**：纯多头动量+放量因子在 2022 反而比 SOXX **少跌 4.2 个点**——没有出现动量崩盘，因为信号当时已轮出最差动量股。
- **超额收益高度集中在 2024+**：2020/2021/2023 这些牛市年它**略输** SOXX（-3 点左右），edge 几乎全部来自 **2024(+33) 和 2025-26(+219)**——恰好是咽喉理论说的「放量重估加速」阶段。
- **赢在收益、不赢在 Sharpe**：滚动中位 Sharpe（1.01）其实**低于** SOXX（1.27）——因子是**高收益、高波动**，超额收益住在右尾（fat tail），不是每个窗口都稳赢。62% 胜率 + 右尾 = 「赔率」型策略，和 Serenity 的高波动小盘集中打法一致。

> 结论：因子的 alpha 是**真实但 regime 依赖**的——它在 AI 放量期把板块 beta 显著放大，熊市里不比板块差，但代价是更高波动。
> 这与「赌高赔率瓶颈、容忍波动、等放量验证」的框架自洽。**仍是说明性回测，非真实业绩，不构成投资建议。**

## 局限 / Limitations（框架自己也强调）

- 数据为手工整理估计值；接入实时数据前不要据此交易。
- 小盘股流动性差、高波动、强相关于单一 AI capex 因子。
- 技术路线风险（CPO vs 传统可插拔光模块）可能证伪 thesis。
- **模型只能辅助，核心仍需人工领域判断**（材料科学、专利解读）+ 对抗性验证（多模型红蓝对抗）。

## 如何扩展 / Extending

1. 在 `chokepoint_data.py` 增删 `Node`、调整 `depends_on` 边即可改写供应链图与评分。
2. 在 `scoring.py` 调权重 `WEIGHTS` 或改 `_payoff` 的胜率/上下行假设。
3. 接实时数据：替换 `Node` 字段来源为 `src.tools.api` 或 yfinance，保留评分逻辑不变。

## 复现与测试 / Reproduce & test

- **复现指南**：见 [`REPRODUCE.md`](REPRODUCE.md) —— 如何跑通、**把占位数据换成真实数据**(逐字段来源表)、复现每张图/回测、以及「怎么批判这个引擎」。
- **测试**(全部离线、无需联网/API key)：
  ```bash
  pytest tests/test_serenity.py -q     # 16 项不变量：评分边界、确定性闸门、图拓扑、对抗、live 降级 …
  ```
