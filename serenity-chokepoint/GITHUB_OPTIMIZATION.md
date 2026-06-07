# 🔧 GitHub 可发现性优化清单 / Discoverability Checklist

这是所有推广流量的**落地页**,先做好它再外发。逐项打勾即可,大多在网页上点几下就能完成。

## A. About（仓库右上角 ⚙️ Edit）
- [ ] **Description**:
  `An auditable, open-source method for finding AI supply-chain chokepoints. Educational; not financial advice.`
- [ ] **Website**: 填 PyPI 页 `https://pypi.org/project/serenity-chokepoint/`
- [ ] 勾选 **Releases**、**Packages** 让它们显示在侧栏。

## B. Topics（About 里的 🏷️,搜索曝光的关键）
建议添加(GitHub 按 topic 推荐项目):
```
python  cli  investing  quant  quantitative-finance  stock-screener
semiconductors  ai  supply-chain  photonics  fintech  yfinance  backtesting
```

## C. 徽章(README 顶部，已有 License/Python/Tests/NFA，建议补 PyPI)
```markdown
[![PyPI](https://img.shields.io/pypi/v/serenity-chokepoint.svg)](https://pypi.org/project/serenity-chokepoint/)
[![Downloads](https://img.shields.io/pypi/dm/serenity-chokepoint.svg)](https://pypi.org/project/serenity-chokepoint/)
```

## D. 安装说明对齐
- [ ] README 现在写 `pipx install serenity-chokepoint`——确认和 PyPI 实际包名一致(已发布为 `serenity-chokepoint` ✅)。
- [ ] 也给一行 `pip install serenity-chokepoint`(很多人没装 pipx)。

## E. Release
- [ ] 打 `v0.4.0` tag 并写 Release notes(列出 thesis/growth/scan 三个新命令)。
  让"最近有 Release"成为项目在维护的信号。

## F. 视觉
- [ ] README 顶部放一张 `serenity thesis AXTI` 的终端截图/动图(见下方 demo 素材)。
  GitHub 社交分享卡片会抓 README 首图,直接影响别人点不点进来。

## G. 社交预览图(Settings → General → Social preview)
- [ ] 传一张 1280×640 的图(可用 thesis 输出截图加标题)。分享到 X/即刻时显示的就是它。

---

## 可复用的工作流图(贴 README / 任何帖子)

```
 serenity scan            ① 雷达:动量排序,看什么在动(明确标注"非方法")
        │                    Radar: momentum ranking — what's moving
        ▼
 serenity thesis <T>      ② 总论证:三个镜头合成一句裁决
   ├─ 🏰 MOAT   结构性咽喉评分(6支柱)        what you bet on
   ├─ 📈 TIMING 成长/放量拐点                  whether the ramp started
   └─ 🔴 RISK   对抗红队 + 蒙特卡洛            whether it survives attack
        │        → 🎯 PRIME SETUP / ⏳ POSITIONED EARLY / ⛔ FAILS VALIDATION
        ▼
 serenity pool            ③ 组合:对高信念标的定仓
        │                    Size the survivors into a pool
        ▼
 serenity backtest --oos  ④ 检验:样本外回测(承认局限)
                             Validate out-of-sample (limitations disclosed)
```
