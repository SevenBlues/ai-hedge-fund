# 复现指南 / Reproduction Guide

这份文档说明如何**从零跑通**本引擎、**把占位数据换成真实数据**、以及**复现每一张图表和回测**。

> ⚠️ 再次强调：`chokepoint_data.py` 里的结构性字段是**手工估计的占位值**，仅用于演示方法论。
> 任何严肃使用都必须先按本指南替换成可核实的真实数据。**本项目非投资建议。**

---

## 0. 环境 / Setup

```bash
# 方式 A：poetry（跟随上游项目）
poetry install
poetry run python -m src.serenity.run_screen

# 方式 B：只跑 serenity 引擎所需的最小依赖
pip install pandas numpy networkx scipy matplotlib yfinance pytest
python -m src.serenity.run_screen
```

无需任何 API key 即可离线跑出股票池;`--live` 才需要联网(yfinance)。

## 1. 一键复现所有产物 / Reproduce everything

```bash
# 产品本体：高确定性股票池
python -m src.serenity.run_screen                       # 离线、curated
python -m src.serenity.run_screen --live                # 实时行情收紧

# 证据链（可选）
python -m src.serenity.run_screen --full   --png out/report.png --json out/scores.json
python -m src.serenity.run_screen --live   --adversarial         # 对抗红队明细
python -m src.serenity.run_screen --backtest --period 2y --png out/r.png   # 样本内回测
python -m src.serenity.run_screen --oos      --period 8y --png out/r.png   # 真·样本外 + 稳健性

# 测试（全部离线）
pytest tests/test_serenity.py -q
```

生成的图(`sample_*.png`)和上面命令一一对应，可逐一比对。

## 2. 把占位数据换成真实数据 / Replace placeholders with real data

`chokepoint_data.py` 每个 `Node` 的字段分两类。**市场派生字段** `--live` 已能自动刷新；
**结构性字段**才是需要你做投研去核实的核心。

### 2a. 市场派生字段(已自动化，见 `live_data.py`)

| 字段 | 来源 | 备注 |
|---|---|---|
| `market_cap_b` | Yahoo `marketCap` | `--live` 自动 |
| `inst_ownership` | Yahoo `heldPercentInstitutions` | `--live` 自动 |
| `analyst_coverage` | Yahoo `numberOfAnalystOpinions` | `--live` 自动 |
| `short_interest` | Yahoo `shortPercentOfFloat` | `--live` 自动 |
| `fwd_ev_sales` | Yahoo `enterpriseToRevenue` ÷ `ramp_rev_mult` | `--live` 自动 |

想换更权威的数据源(本仓库已内置 financialdatasets.ai 客户端 `src/tools/api.py`)：
在 `live_data.fetch_live_quote` 里把 yfinance 换成 `get_market_cap` / `get_financial_metrics` 即可，
评分逻辑无需改动。

### 2b. 结构性字段(需人工投研 —— 这才是「深度投研」的部分)

| 字段 | 含义 | 怎么核实(建议来源) |
|---|---|---|
| `top3_share` | Top1-3 供应商份额 | TrendForce / Yole / SemiAnalysis 行业报告、公司 10-K 市占披露 |
| `irreplaceability` | 物理/材料替代难度 | 专利数据库、材料科学文献、是否唯一认证供应商 |
| `qual_cycle_months` | hyperscaler/NVDA 认证周期 | 公司财报电话会、供应链访谈、历史认证案例 |
| `qualified` | 是否已被设计导入 | 公司公告、客户披露、订单新闻 |
| `demand_cagr` / `capacity_cagr` | 终端需求 vs 该节点产能增速 | 第三方市场预测、公司扩产 capex 指引 |
| `ramp_rev_mult` | 2028-29 营收 / 今天(倍数) | 自建 venture-style 模型(见下) |
| `depends_on` | 上游依赖(图的边) | 供应链拆解、BOM、招股书 |

> 字段都是 0..1 归一或物理量，含义在 `chokepoint_data.py` 顶部 docstring 有逐条说明。
> 改完后重跑命令即可——**评分、对抗、图、回测全部自动跟随你的新数据**。

## 3. 复现/检验回测的口径 / Backtest methodology to reproduce

- **样本内回测**(`backtest.py`)：固定权重 constant-mix 日度再平衡；事件研究用 +12% 单日跳涨代理「认证/放量重估」，测 60 日前向收益 vs 无条件基线。
- **样本外**(`oos_backtest.py`)：固定一份非事后选的 ~40 只供应链 universe；point-in-time 信号 = 12-1 动量 + ≥20% 大涨月的放量标记;train/test 时间切分,参数只在 train 固定;月度不重叠持有。
- **稳健性**：分 regime(含 2022 熊市)+ 24 折滚动窗口的超额分布。
- 所有口径与已知**局限**(幸存者偏差、样本内、本地币种、纯多头)都打印在报告末尾,请连同结果一起读。

调参入口集中在 `oos_backtest.py` 顶部常量(`MOM_LOOKBACK / JUMP_THRESHOLD / TOP_K / TRAIN_FRACTION` …)和
`scoring.py` 的 `WEIGHTS` —— 改这些就能做你自己的敏感性分析。

## 4. 怎么批判这个引擎 / How to attack it

最有价值的 critique 方向(欢迎 PR / issue)：
1. **数据**：拿真实 top3_share / 认证周期推翻某个节点的瓶颈定级。
2. **评分**：论证某个 pillar 权重或非线性曲线不合理。
3. **赔率模型**：质疑 win_prob 映射、上下行假设、Kelly 上限。
4. **回测**：指出仍残留的前视/幸存者偏差，或提供含退市股的更干净 universe。
5. **对抗向量**：补充缺失的攻击向量(如客户集中度的量化、专利悬崖)。

跑 `pytest tests/test_serenity.py -q` 确认你的改动没破坏既有不变量。
