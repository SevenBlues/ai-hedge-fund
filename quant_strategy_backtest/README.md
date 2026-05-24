# Quant Strategy Backtest — TQQQ/SPY 双因子择时

8 年（2018-05 → 2026-05）真实数据回测，基于 VIX + 国库券收益率 + 趋势/动量
的综合评分，在 3 倍纳指 ETF (TQQQ) / 标普 500 ETF (SPY) / 现金之间切换 6 档仓位。
含硬止损、跟踪止损、参数稳健性扫描和样本内/外检验。

> 数据全部来自 Yahoo Finance（yfinance），**没有任何模拟数据；信号严格在 T-1 收盘
> 后计算，T 日开盘成交，无未来函数**。

## 快速开始

```bash
pip install yfinance pandas numpy matplotlib scipy
python src/main.py                          # 端到端回测 + 报表
python src/robustness.py                    # 参数扫描
```

主要结果见 [`reports/REPORT.md`](reports/REPORT.md)。

## 目录结构

| 路径 | 用途 |
|---|---|
| `src/data_loader.py` | 行情下载/缓存/日历对齐 |
| `src/strategy.py`    | 6 因子评分 → 6 档权重映射 |
| `src/backtest.py`    | 事件驱动回测引擎 + 硬止损 + 跟踪止损 |
| `src/analysis.py`    | 绩效指标 |
| `src/plots.py`       | 可视化 |
| `src/robustness.py`  | 单参数稳健性扫描 |
| `src/main.py`        | 端到端入口 |
| `data/`              | 原始 CSV 缓存（首次运行时下载）|
| `results/`           | 回测产物 (PNG/CSV) |
| `reports/`           | 文字报告与 JSON 汇总 |

## 关键回测结果（8 年，2018-05 → 2026-05）

| 组合 | 总收益 | CAGR | 最大回撤 | Sharpe |
|---|---:|---:|---:|---:|
| **本策略** | **+238%** | **16.5%** | **−36.6%** | 0.67 |
| SPY 买入持有 | +209% | 15.2% | −33.7% | 0.83 |
| QQQ 买入持有 | +346% | 20.6% | −35.1% | 0.90 |
| TQQQ 裸持 | +1079% | 36.2% | **−81.7%** | 0.80 |

* 总收益跑赢 SPY，但 Sharpe 略低于 SPY（用更高波动换取更高回报）。
* 相比 TQQQ 裸持，最大回撤从 −82% 降至 −37%。
* 未跑赢 QQQ，因评分系统在牛市延续阶段偏保守。
* 详细分析见 `reports/REPORT.md`。
