# 📱 社交平台推送稿 / Social Drafts — Serenity Chokepoint

> **本期主题(v0.5→v0.9):自我证伪。** 大多数量化项目晒回测、藏缺陷;
> 这一期的传播内核是反过来的——**给自己的项目做严格统计检验,诚实公布
> 「打脸」结果**。在满屏「稳赚牛股」里,「敢自我证伪」就是最强的差异化。
>
> 统一叙事:**亮眼回测 → 主动统计检验 → 诚实打脸 → 公开局限。**
>
> ⚠️ 每条都内置免责声明。请用**你自己的账号**、以本人口吻发布。
> 链接(发布前可替换为独立仓库 `github.com/SevenBlues/serenity-chokepoint`):
> `github.com/SevenBlues/ai-hedge-fund/tree/main/serenity-chokepoint`

真实数据素材(发布前如重跑请核对,实时数据会微动):
- 样本外回测:选股 **143.9%** 年化 vs 半导体板块 SOXX **54.1%**;夏普 **1.95 vs 1.40**
- 因子信息系数:平均 IC **+0.0145**,p 值 **0.54**(不显著)
- 因子电池:**8** 个因子 + Bonferroni 多重检验校正 → **无一显著**
- 结构分:原始 IC **+0.44** → 剔除动量后塌掉(t **-0.16**)
- 一键体检:`serenity audit` → **OOS=PASS | 因子=FAIL | 结构=WEAK** → 总评 **WEAK/SUGGESTIVE**
- 统计量从零实现、对照 scipy 验证到 **1e-11**;**23** 个测试

---

## 1. X / Twitter — 中文 thread

```
1/ 三个月前我把一个网红散户的「AI供应链咽喉理论」做成了开源工具,
回测跑出 143% 年化,漂亮得我自己都不敢信。

于是这周我做了件大多数量化项目不会做的事:
给它做了一套严格的统计检验,主动证伪自己。

结果——打了我的脸。我把打脸过程也开源了 🧵
```
```
2/ 先说那个漂亮数字。

样本外回测:选股组合 143.9% 年化,跑赢半导体板块(SOXX 54.1%)
近 90 个点,夏普 1.95 对 1.40。

看着像 alpha 吧?我也这么以为——
直到我做了因子有效性检验。
```
```
3/ 我算了因子的信息系数(IC):
平均 IC = +0.0145,p 值 = 0.54。

人话:这个因子的预测力,统计上和「扔硬币」区分不开。

我又一口气测了 8 个因子,加了多重检验校正(Bonferroni)。
没有一个过显著门槛。
```
```
4/ 最扎心的一刀:我把「咽喉评分」本身拿来检验。

原始相关性 IC +0.44,看着不错。
但一旦剔除「动量」这个变量——评分的解释力直接塌了(t = -0.16)。

结论:那个 143%,大部分是动量和板块beta,
不是可证明的「结构性 alpha」。
```
```
5/ 三条检验,一个命令汇总:

  serenity audit
  → OOS=PASS | 因子显著性=FAIL | 结构分=WEAK
  → 总评:WEAK / SUGGESTIVE

一个量化工具,自己给自己出具了「证据不足」。
统计量全部从零实现、对照 scipy 验证到小数点后 11 位。
```
```
6/ 为什么要公开打脸?

因为「评级低 ≠ 理论错」。它说的是:咽喉评分没有历史数据,
我做不了真正的样本外检验——而我拒绝用伪造数据去凑一个好看的结论。

诚实 > 一个讨好你的数字。

⚠️ 教育/研究用途,内置占位数据,非投资建议。
来 GitHub 把我的方法批判一遍 👇
github.com/SevenBlues/ai-hedge-fund/tree/main/serenity-chokepoint
```

---

## 2. X / Twitter — English thread

```
1/ I built an open-source tool from a retail "AI supply-chain chokepoint" theory.
The backtest printed 143% CAGR. Gorgeous.

So this week I did what most quant repos won't:
I ran rigorous significance tests to falsify my own work.

It backfired. I open-sourced the backfire 🧵
```
```
2/ The pretty number: out-of-sample, the stock-picking book did
+143.9% CAGR vs the semi sector (SOXX) +54.1% — Sharpe 1.95 vs 1.40.

Looks like alpha. I thought so too —
until I tested the factor's Information Coefficient.
```
```
3/ Mean IC +0.0145, p = 0.54.

Plain English: the factor's predictive power is
statistically indistinguishable from a coin flip.

I tested 8 factors with Bonferroni multiple-testing correction.
None cleared the bar.
```
```
4/ The key test: does the chokepoint SCORE itself explain returns?

Raw correlation IC +0.44 — promising.
Control for momentum, and it vanishes (t = -0.16).

Honest read: the 143% is mostly momentum + sector beta,
NOT a demonstrable structural alpha.
```
```
5/ One command rolls it all up:

  serenity audit
  → OOS=PASS | Factor-significance=FAIL | Structural=WEAK
  → Verdict: WEAK / SUGGESTIVE

A quant tool grading itself "insufficient evidence."
Every statistic implemented from scratch, verified vs scipy to 1e-11.
```
```
6/ Why publish the backfire?

Because a low grade is NOT proof the thesis is wrong. It says:
the score has no point-in-time history, so I can't test it out-of-sample —
and I refuse to fabricate data to manufacture a prettier result.

Honesty > a flattering number.

⚠️ Educational, placeholder data, not financial advice.
Come prove me wrong 👇
github.com/SevenBlues/ai-hedge-fund/tree/main/serenity-chokepoint
```

---

## 3. 微信公众号 — 长文

**标题(推荐第一个):**
- 《我的量化项目回测跑出 143%,然后我亲手把它证伪了》
- 《一个敢自己打脸的开源量化工具》
- 《143% 年化的背后:一次诚实的统计检验》

**正文:**

```
(开头免责:本文为教育/研究用途的开源项目分享,内置数据为演示占位估计,
不构成任何投资建议。小盘股风险极高。)

一、一个漂亮得让我警惕的数字

三个月前,我把网红散户(Serenity)讲的「AI 供应链咽喉理论」复现成了一个
开源命令行工具。思路很迷人:别买 NVDA、台积电这种明牌,去找整个 AI 建设
「必须流经」、物理上又换不掉的小瓶颈——比如光互联用的 InP 衬底,我把它
叫做「光子学的霍尔木兹海峡」。

工具跑出来的样本外回测很亮眼:选股组合 143.9% 年化,跑赢半导体板块
(SOXX 的 54.1%)近 90 个百分点,夏普 1.95 对 1.40。

但正是这个数字让我警惕。量化里有句老话:越漂亮的回测越可疑。于是这周我
做了一件大多数「晒收益」的项目不会做的事——给它做一套严格的统计检验,
主动去证伪自己。

二、第一刀:这个因子,真有预测力吗?

回测曲线是最容易造假、也最不说明问题的东西。真正的问题是:这个因子的
预测力,能不能和「运气」区分开?

我算了它的「信息系数」(IC)——每个月,因子打分和下个月真实回报的横截面
相关性:
· 平均 IC = +0.0145(低于 0.02 的「可用」线)
· t 统计量对应的 p 值 = 0.54

p=0.54 是什么概念?意味着这个因子的预测力,统计上和扔硬币区分不开。

我不死心,又一口气测了 8 个因子(不同周期的动量、低波动、残差动量……),
还加了多重检验校正(Bonferroni——测得越多越要收紧门槛,否则容易「蒙」
出假信号)。结果:没有一个因子过显著门槛。

三、最扎心的一刀:咽喉评分本身

前面测的是价格类因子。但这个项目的灵魂,是那套人工研究的「结构性咽喉
评分」。于是我直接拿它来检验:评分越高的票,回报真的越好吗?

· 原始相关性:IC = +0.44,看着相当不错。
· 但我做了关键一步——剔除「动量」这个变量,再看评分还剩多少解释力。
· 结果:评分的预测力直接塌了(t = -0.16,p = 0.90)。

结论很残酷也很诚实:那个 143% 的亮眼回报,大部分其实是动量和板块beta
驱动的,而不是一个能被统计证明的、独立的「结构性 alpha」。高分的票同时
也是高动量的票;把动量拿掉,评分本身就没什么了。

四、我把这一切汇总成一个命令

  serenity audit
  → OOS=PASS | 因子显著性=FAIL | 结构分=WEAK
  → 总评:WEAK / SUGGESTIVE(弱 / 暗示性)

一个量化工具,自己给自己出具了一份「证据不足」的体检报告。
(所有统计量——t 分布 p 值、OLS、Spearman、Newey-West——都是从零实现,
不依赖 scipy,并逐一对照 scipy 验证到小数点后 11 位。)

五、那为什么还要做、还要公开?

因为「评级低」不等于「理论错了」。

它说的是:这套方法最独特的「结构性评分」,没有历史数据可供回溯检验——
而我拒绝为了一个好看的结论去伪造历史数据。我只检验能诚实检验的部分,
其余局限,原样写在 README 和 VALIDATION.md 里。

在一个满是「稳赚」「牛股」的环境里,我更想做一个敢说「我的证据还不够」
的工具。诚实,比一个讨好你的数字重要。

六、它现在能帮你做什么

如果你想分析自己看好的票,新加的 serenity proxy <代码> 会给一个诚实的
初筛:它只算唯一能从市场数据客观衡量的维度——「信息不对称」(是不是
够小、够冷门、够少人覆盖),其余 4 个结构维度明确标注「需要你人工研究」。
比如一只 600 亿市值、83% 机构持股的票,它直接告诉你「已经被发现了,别
浪费时间」;一只冷门小盘,它会说「符合画像,值得深入研究」。

它不替你下结论,只告诉你该把研究时间花在哪。

——
项目完全开源(MIT),pip install serenity-chokepoint 即可运行。
方法、代码、缺陷全部公开,就是想让大家来批判讨论的。
GitHub:https://github.com/SevenBlues/ai-hedge-fund/tree/main/serenity-chokepoint

⚠️ 再次声明:教育/研究用途,非投资建议,内置数据为演示占位估计。
```

---

## 4. 小红书

```
标题:我的选股工具回测143%,然后我把它当场证伪了😅

正文:
做了个开源小工具,把最近很火的AI供应链「咽喉理论」变成了能跑的代码🪢
结果这周干了件挺反常识的事——亲手把自己的项目证伪了,还开源了打脸全过程😂

📈 先说那个漂亮数字
样本外回测:选股组合 143.9% 年化,吊打半导体板块(54%),夏普1.95。
搁别人这就该开始吹了对吧?

🔪 但我做了统计检验,然后…
· 因子信息系数 IC=0.0145,p值=0.54 → 和扔硬币没区别
· 一口气测8个因子+多重检验校正 → 没一个显著
· 把「咽喉评分」剔除动量后再看 → 解释力直接塌了

💡 真相:那143%大部分是「动量+板块beta」,
不是什么独立的「结构性alpha」😮

🩺 我还把这套检验做成一个命令:
serenity audit
→ 工具自己给自己打了个「证据不足」

🤔 那为啥还公开打脸?
因为「评级低≠理论错」,而是诚实承认「我现有的数据证明不了」。
满屏都是「稳赚牛股」的时候,我更想做个敢说真话的工具。

🔭 顺手还加了个功能:输自己的票代码,
工具会告诉你「这票还冷门吗、值不值得研究」,不替你下结论~

全开源,pip就能装,欢迎来GitHub拍砖👇
github.com/SevenBlues/ai-hedge-fund/tree/main/serenity-chokepoint

⚠️重要:教育/研究用途,内置演示数据,不构成任何投资建议,
小盘股风险极高,别拿去实盘!

#量化投资 #开源项目 #AI算力 #半导体 #Python #程序员 #投资方法论
```

---

## 5. 发布心法(沿用既有 Promotion Kit)

1. **先收拾好落地页**:GitHub About / Topics / 置顶演示图 / 徽章——所有流量都落在这里。
2. **发布顺序**:技术社区(HN / r/algotrading)先行,拿到讨论后再发 X + 中文平台,引用讨论增可信度。
3. **本期钩子是「诚实」**:评论区一定会有人质疑「那这工具不就没用?」——
   正面回应:它的价值是**方法论 + 自我证伪的严谨**,不是荐股;`serenity audit`
   就是让你自己复核这份「证据不足」的结论。**承认缺陷,就是产品的一部分。**
4. **绝不承诺收益**。任何把 143% 当卖点的解读都要主动纠偏——那正是本期要
   反对的东西。
