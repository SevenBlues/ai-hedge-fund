# 📣 推广素材包 / Promotion Kit — Serenity Chokepoint

> 主打信息(所有渠道统一):这是一套**可复现、可批判**的「找 AI 供应链咽喉」的**分析方法论**——不是荐股、不是黑箱信号。
> Core message everywhere: a **reproducible, auditable analytical METHOD** for finding AI supply-chain chokepoints — not stock tips, not a black box.
>
> ⚠️ 每条文案都内置免责声明。请用**你自己的账号**发布;外部社区只认本人口吻的真实分享。

链接占位(发布前替换):
- GitHub: `https://github.com/SevenBlues/serenity-chokepoint`
- PyPI: `https://pypi.org/project/serenity-chokepoint/`
- 安装: `pip install serenity-chokepoint`

---

## 1. Hacker News — Show HN

**Title**（≤80 字符,HN 不要 emoji、不要营销腔）:
```
Show HN: Serenity – a reproducible method for finding AI supply-chain chokepoints
```

**Body / first comment:**
```
I kept seeing a retail trader (Serenity) describe a "chokepoint theory" for the
AI buildout — don't buy the obvious winners (NVDA/TSMC), buy the small,
physically irreplaceable bottlenecks everything must flow through (e.g. InP
substrates for optical interconnects). The idea was interesting but always
hand-wavy, so I tried to turn it into something you can actually run and argue
with.

It's a CLI. The interesting part isn't a stock list — it's the *method*, made
explicit and auditable:

  - a "chokepoint score" over 6 pillars (supply concentration, irreplaceability,
    demand/supply gap, qualification barrier, info asymmetry, catalysts)
  - a growth lens that scores the *ramp inflection* (margin turning up as volume
    scales), not generic "high growth"
  - an adversarial red-team + Monte-Carlo that tries to kill each thesis
  - `serenity thesis <T>` fuses all three into one verdict
    (PRIME SETUP / POSITIONED EARLY / FAILS VALIDATION / ...)

    pip install serenity-chokepoint
    serenity thesis AXTI

Honest caveats, up front: the bundled data are illustrative placeholder
estimates to demonstrate the method (you're meant to replace them with verified
sources); the backtest runs through a roaring AI bull market and has
survivorship bias. None of it is financial advice. I deliberately left the
unflattering parts in the README.

What I'd love feedback on: is the chokepoint-scoring rubric defensible, or am I
fooling myself? Where does the method break? Repo + REPRODUCE.md show every
assumption.
```
> HN 心法:标题克制、第一条评论自己先讲清局限、邀请别人"挑错"。别吹回报数字。

---

## 2. Reddit

### r/Python（重工具与代码质量)
**Title:**
```
I built a CLI that turns a vague "AI supply-chain chokepoint" investing theory into a reproducible, testable method
```
**Body:**
```
Not a stock-tip bot — the point is the *method*, made explicit so it can be
criticised. Pure-Python CLI, free data (yfinance), 16 tests, MIT.

    pip install serenity-chokepoint
    serenity thesis AXTI     # moat × timing × risk → one verdict
    serenity growth AXTI     # scores the "ramp inflection", not generic growth
    serenity scan            # (clearly labelled) momentum ranking radar

Design notes I'd like feedback on:
  - scoring rubric is data-driven dataclasses, every pillar weight is visible
  - an adversarial "red-team" module Monte-Carlos each thesis to try to break it
  - non-US tickers mapped to Yahoo symbols, graceful offline degradation

⚠️ Educational reproduction of a publicly-described framework. Bundled data are
placeholder estimates; not financial advice; backtest has survivorship bias and
a bull-market tailwind — all documented in the README. Come tell me where the
code or the method is wrong.

Repo: <github link>
```

### r/algotrading（重方法与质疑)
**Title:**
```
Reproducing "chokepoint theory" as an auditable scoring + adversarial-validation pipeline (not financial advice)
```
**Body:** 用上面 HN body 的精简版,强调:6 支柱评分 + 放量拐点 + 红队对抗 + OOS 回测的**局限**(幸存者偏差、牛市)。明确请求:`Poke holes in the methodology.`
> r/algotrading 对"晒收益"很反感、对"晒方法+承认缺陷"很欢迎。务必先认怂再求批判。

---

## 3. X / Twitter（线程 thread)

```
1/ 我把一个一直很"玄"的散户投资理论——AI供应链"咽喉理论"——做成了一个能跑、能被你挑错的开源工具。

不是荐股。重点是把"怎么找咽喉"这套分析方法写成透明、可复现的代码。

pip install serenity-chokepoint

🧵
```
```
2/ 核心思路:别买显而易见的赢家(NVDA/台积电),买整个AI建设"必须流经"的、物理上无可替代的小瓶颈。

比如光互联用的 InP 衬底——被我称作"光子学的霍尔木兹海峡"。
```
```
3/ 方法分三个镜头,每个都明码标价、可审计:

🏰 结构:6支柱"咽喉评分"(供给集中度/不可替代/供需缺口/认证壁垒/信息差/催化剂)
📈 时机:成长分,只认"放量拐点"(毛利率随量产掉头向上),不认空泛的高增长
🔴 风险:对抗红队 + 蒙特卡洛,主动尝试推翻每个论点
```
```
4/ 一行得到完整论证:

  serenity thesis AXTI
  → 🎯 PRIME SETUP / ⏳ POSITIONED EARLY / ⛔ FAILS VALIDATION

结构 × 时机 × 风险,合成一句裁决。
```
```
5/ ⚠️ 老实话:内置数据是用来演示方法的"占位估计",不是实盘信号;回测踩在AI大牛市上、有幸存者偏差。全部写在 README 里,没藏。

这不是投资建议。欢迎来把方法和代码批判一遍 👇
<github link>
```

**英文版 thread**(同结构):
```
1/ I turned a vague but fascinating retail-investing idea — "AI supply-chain
chokepoint theory" — into an open-source tool you can run AND argue with.

Not stock tips. The point is making the *method* transparent & reproducible.

  pip install serenity-chokepoint

🧵
2/ Thesis: don't buy the obvious winners (NVDA/TSMC). Buy the small, physically
irreplaceable bottlenecks the whole AI buildout MUST flow through — e.g. InP
substrates, the "Strait of Hormuz of photonics."
3/ Three lenses, every weight visible & auditable:
🏰 Structure: 6-pillar chokepoint score
📈 Timing: growth score for the *ramp inflection* (margins turning up), not
   generic high growth
🔴 Risk: adversarial red-team + Monte-Carlo that tries to kill the thesis
4/ One command for the full case:
  serenity thesis AXTI
  → PRIME SETUP / POSITIONED EARLY / FAILS VALIDATION
5/ ⚠️ Honest: bundled data are placeholder estimates to demo the method;
backtest has survivorship bias + a bull-market tailwind. All in the README.
Not financial advice. Come prove me wrong 👇  <github link>
```

---

## 4. 即刻 / 小红书 / 知乎（中文社区)

**即刻**(轻、个人口吻):
```
做了个开源小工具,把那个很火的"AI供应链咽喉理论"变成了能跑的代码 🪢

思路:别追NVDA、台积电这种明牌,去找整个AI建设绕不开、又物理上换不掉的小瓶颈(比如光模块用的InP衬底)。

重点不是给你荐股,而是把"怎么判断一个东西算不算咽喉"这套方法写透明了——6个维度打分 + 成长拐点 + 一个专门"唱反调"的红队模块来挑刺。

  pip install serenity-chokepoint
  serenity thesis AXTI

⚠️ 教育用途,内置数据是演示用的占位估计,不是投资建议。代码和缺陷都开源,欢迎来拍砖。
```

**小红书**(标题 + 正文,加话题标签):
```
标题:我把网红的"咽喉理论"做成了开源工具|附用法

正文:
最近一直看到有人讲AI供应链"咽喉理论",听着很有道理但每次都很玄。
于是我把它做成了一个真能跑、还能被你挑错的开源命令行工具👇

🪢 核心:不买显眼的赢家,买整条AI产业链"必须经过"、又换不掉的小瓶颈
🏰 结构分:6个维度给"咽喉程度"打分
📈 时机分:只认"放量拐点"(量产起来、毛利率掉头向上)
🔴 风险:内置一个专门唱反调的"红队"来推翻你的论点

一行命令出完整论证:serenity thesis AXTI

⚠️ 重要:这是教育/研究用途,内置数据是演示占位估计,不构成任何投资建议,小盘股风险极高。
方法和源码全开源,就是想让大家来批判讨论的~

#量化投资 #开源项目 #AI算力 #半导体 #Python
```

**知乎**(可发"分享创造"或回答相关问题,长文,主打方法论):
```
标题:我尝试把"AI供应链咽喉理论"复现成一套可审计的分析方法(开源)

(开头先放免责:教育复现、占位数据、非投资建议)

正文结构建议:
1. 缘起:这个理论好在哪、玄在哪
2. 我怎么把它拆成可计算的3个镜头(结构/时机/风险),每个镜头的评分逻辑
3. 一个真实例子走一遍 serenity thesis 的输出
4. 老实交代局限:幸存者偏差、牛市、占位数据
5. 邀请:来GitHub挑错、补真实数据
```

---

## 5. 一句话简介（仓库 About / 各平台 bio 统一)

- 中:`把"AI供应链咽喉理论"复现成可审计、可批判的开源分析方法。教育用途,非投资建议。`
- En:`An auditable, open-source method for finding AI supply-chain chokepoints. Educational; not financial advice.`

---

## 6. 发布节奏建议

1. **先把 GitHub 收拾好**(见 `GITHUB_OPTIMIZATION.md`):About、Topics、徽章、置顶演示图——这是所有流量的落地页,先于一切外发。
2. 打一个 `v0.4.0` Release(让 PyPI/GitHub 版本对齐,显得在维护)。
3. **工作日**发 Show HN(美西时间早 8–10 点流量好);同日发 r/Python。
4. HN/Reddit 有初步反馈后,再发 X 线程 + 中文社区,引用社区讨论增加可信度。
5. **盯评论、认真回**——开源推广的转化主要发生在你回复质疑的过程里。承认缺陷、就事论事,比涨星更重要。
```
