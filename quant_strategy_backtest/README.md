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

| 组合 | CAGR | Max DD | Sharpe | OOS Sharpe |
|---|---:|---:|---:|---:|
| v1 (固定档位) | 16.5% | −36.6% | 0.67 | 0.96 |
| v2 (smooth+QLD) | 15.9% | −24.4% | 0.79 | 1.28 |
| v2.1b (+信用利差) | 19.2% | −25.1% | 0.93 | 1.46 |
| v2.5 InvVol 多资产 | 9.3% | −13.0% | 1.23 | 1.83 |
| **v2.6 InvVol 5-sleeve** ⭐ | 7.6% | **−8.1%** | **1.31** | **1.91** |
| **v2.6 InvVol + 3.72x 杠杆** ⭐ | **27.8%** | −30.0% | **1.22** | 1.81 |
| SPY 买入持有 | 15.2% | −33.7% | 0.83 | 1.47 |
| QQQ 买入持有 | 20.6% | −35.1% | 0.90 | 1.63 |
| TQQQ 裸持 | 36.2% | −81.7% | 0.80 | 1.43 |

* **当前推荐：v2.5 InvVol 多资产分散**（Nasdaq + Gold + Bond 各自择时 → 风险平价加权）
* 从 v1 到 v2.5：**Sharpe +0.56（+84%）、OOS Sharpe +0.87（+91%）**
* v2.5 是项目最大跃迁——分散是真正的"免费午餐"
* 详细报告：`reports/REPORT.md` (v1) · `REPORT_V2.md` (v2) · `REPORT_V21.md` (v2.1) · `REPORT_V22.md` · `REPORT_V23.md` · `REPORT_V24.md` · `REPORT_V25.md` (v2.5 多资产) · `REPORT_V3.md` (网格实验)

## 运行

```bash
python src/main_v2.py     # v1 vs v2
python src/main_v21.py    # v2 -> v2.1 信用利差
python src/main_v25.py    # v2.5 多资产分散（推荐版本）
```
