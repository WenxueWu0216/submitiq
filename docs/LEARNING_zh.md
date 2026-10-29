# SubmitIQ 学习笔记（中文，附英文术语）

这份笔记用中文解释项目里的每个关键概念和模块，括号里是面试时要用的英文说法。建议按顺序读：先懂业务，再懂评测，最后看系统和部署。

---

## 第一部分：业务概念（保险领域）

### 1. 谁在做什么
* **商业财产险（commercial property insurance）**：保企业的建筑、设备、存货，以及停业损失。属于 **财产与意外险（P&C, property & casualty）**。
* **经纪人（broker / producer）**：代表投保企业，把材料发给多家保险公司询价。
* **核保员（underwriter）**：保险公司里决定"接不接这个风险、什么条件接"的人。
* **投保材料包（submission package）**：经纪人发来的一整套文件。本项目把它叫 submission。
* **分诊 / 初筛（triage）**：核保员拿到材料后的第一步，判断要不要报价、要不要上报，还是直接拒绝。本项目自动化的就是这一步。

### 2. 材料包里的四种文件
* **经纪人邮件（broker email）**：自由文本，写了生效日期、报价截止日（quote needed by）、联系人。
* **投保单（application）**：业内标准表格叫 **ACORD 125**（通用商业投保单）和 **ACORD 140**（财产险部分）。项目里用的是"仿 ACORD"的合成表格，因为真表有版权。
* **出险记录 / 赔付记录（loss run）**：上一家保险公司出的过去 3–5 年理赔清单，每笔理赔有：出险日期（date of loss）、原因（cause）、已付（paid）、未决准备金（reserve）、总赔付（incurred = paid + reserve）、状态（open / closed），每个保单年度还有已赚保费（earned premium）。
* **财产明细表（SOV, statement of values）**：每个地点一行，写地址、建筑结构、建造年份、保额等。多地点客户以 SOV 为准。

### 3. 核保要看的核心数据
* **COPE**：财产险核保的四要素：
  * **C（construction，建筑结构）**：ISO 分 6 类，从差到好依次是 frame（木结构）、joisted masonry（砖墙木梁）、non-combustible（不燃）、masonry non-combustible（砖墙不燃顶）、modified fire resistive（改良耐火）、fire resistive（耐火）。
  * **O（occupancy，用途 / 行业）**：用 **NAICS 行业代码（NAICS code）** 表示，比如 332710 = 机加工车间。
  * **P（protection，消防保护）**：**消防等级（PPC, public protection class）**，1 最好，10 最差；还有是否装了 **自动喷淋（sprinklered）**。
  * **E（exposure，外部风险）**：比如是否在 **飓风区（hurricane zone）** 或 **地震区（earthquake zone）**。项目里用邮编前三位判断，这类风险叫 **巨灾风险（CAT, catastrophe）**。
* **总保额（TIV, total insured value）** = 建筑价值（building）+ 财产 / 存货（contents / BPP）+ 营业中断（BI, business income）。
* **赔付率（loss ratio）** = 5 年总赔付 ÷ 5 年已赚保费。超过 60% 要上报，超过 100% 拒绝。

### 4. 承保偏好（appetite）和三种结论
* **承保偏好 / 承保指引（appetite / underwriting guidelines）**：公司愿意承保什么样的风险。本项目写在 `rules/appetite.yaml`。
* 三种结论：**接受（accept）**、**上报（refer**，交给高级核保员或要求补资料）、**拒绝（decline）**。规则冲突时取最严的：decline > refer > accept。
* **真相来源规则（source-of-truth rules）**：文件之间矛盾时信哪个？地点数据信 SOV，主体信息信签字的投保单，理赔信 loss run。矛盾永远要标出来，不能悄悄选一个。

---

## 第二部分：评测（evals）——这个项目最重要的部分

### 5. 为什么"先做评测，再做功能"（evals before features）
没有评测，每次改动都只能凭感觉。所以先做 **数据集（dataset）** 和 **评测框架（eval harness）**，之后每一步改进都用同一把尺子量。README 里的每个数字都来自 `evals/run.py`，不手填。

### 6. 合成数据（synthetic data）和"脏数据"
* `data/generate.py` 生成 120 个材料包，每个包都有 **标准答案（ground truth）**，即 `ground_truth.json`。
* 故意加入的"脏"：**扫描件（scanned pages）**（无文字层、倾斜、噪点、旋转 90°/180°）、**跨页表格（tables split across pages）**、**公司名变体（name variants）**（"Acme LLC" 和 "ACME Holdings"）、**经纪人缩写（abbreviations）**（"JM"、"ISO 4"、"$1.25M"）、**缺失字段（missing fields）**、**故意冲突（planted conflicts）**（投保单上的 TIV 是旧的）。
* **开发集 / 测试集（dev / test split）**：80 / 40。只在 dev 上调参，test 只用来报告结果。
* **留出模板（held-out template）**：投保单模板 C 只出现在 test。我写的解析器从没见过它，所以它能诚实地衡量 **过拟合（overfitting）**。

### 7. 指标（metrics）
* **字段级精确率 / 召回率 / F1（field-level precision / recall / F1）**：
  * TP（true positive，真阳性）：预测有值，且对了。
  * FP（false positive，假阳性）：预测有值但错了，或者标准答案为空却编了个值（**幻觉，hallucination**）。
  * FN（false negative，假阴性）：标准答案有值，但没预测出来或预测错了。
  * 错一个值同时算一个 FP 和一个 FN，这是信息抽取（information extraction）的标准算法。
* **关键字段 F1（critical-field F1）**：只算影响决策的字段（建筑结构、PPC、TIV、NAICS 等）。
* **决策准确率（decision accuracy）**：accept / refer / decline 是否等于标准答案。另外单独统计最危险的错误：**该拒却接受（declines predicted as accept）**。
* **复核队列比例（review-queue rate）**：多少比例的材料要人看。
* **静默关键错误率（silent critical-error rate）**：关键字段错了或缺了，却**没有**送人工复核的比例。这是"绝不静默失败（never fail silently）"原则的直接度量，也是本项目最重要的指标。
* **冲突检测精确率 / 召回率（conflict detection P / R）**：系统发现的跨文件矛盾和故意埋的矛盾对得上多少。
* **延迟（latency, p50 / p95）**、**每份材料成本（cost per submission）**。
* **框架自检（harness self-test）**：完美预测必须得 1.0，空预测必须得 0。确认尺子本身是准的。

### 8. CI 回归门禁（regression gate）
`evals/gate.py` + GitHub Actions：每次提交都在 120 份材料上跑一遍，F1 或决策准确率比 `evals/baseline.json` 掉了 2 个百分点以上就失败。**基准线（baseline）只能主动更新（ratchet）**。

---

## 第三部分：系统模块（按数据流顺序）

### 9. 模型后端（model backends）：`submitiq/llm/`
* 一个接口，三种实现：`anthropic`（官方 SDK）、`bedrock`（AWS 上的 Claude，用 boto3）、`replay`（**回放**：把模型的回答存在磁盘上，离线时直接读）。
* **录制模式（record mode）**：设 `SUBMITIQ_RECORD=1` 跑一次真模型，回答自动存成 **回放夹具（replay fixtures）**，之后 CI 可以完全离线、确定性地（deterministically）运行。
* **未命中就弃权（abstain on miss）**：回放里没有答案时返回"空"，绝不编造。所以离线数字只衡量非 LLM 部分。
* **手写夹具（hand-written fixtures）**：演示用的两个回答是我读文件后手写的，标记为 `hand_written`，不会被当成真模型输出。

### 10. 文本提取与 OCR：`documents.py`、`ocr.py`、`textlayout.py`
* **pdfplumber**：读 PDF 的文字层，得到每个词和它的坐标（words with positions）。
* **OCR（光学字符识别，optical character recognition）**：页面没有文字层时用 **Tesseract**。先做 **方向检测（orientation detection, OSD）**，再做 **纠偏（deskew）**：用投影轮廓法（projection profile）找让每行像素最"尖"的角度。
* **OCR 缓存（OCR cache）**：按文件哈希（hash）缓存，并记下原始耗时，这样延迟指标依然诚实。
* 文字层和 OCR 输出统一成"带坐标的词"，后面的表格解析不用区分来源。

### 11. 文档分类（document classification）：`classify.py`
关键词打分（keyword scoring）；分差太小时才调用 LLM。不看文件名，因为经纪人的文件经常叫 `scan0012.pdf`。

### 12. 基线（baseline）：`extract/baseline.py`
所有文字塞进**一个提示词（single prompt）**，让 Claude 一次输出完整 JSON 和决策。简单，但没有引用来源，也没法交叉核对。它是之后所有改进的对照组。

### 13. 表格感知解析（table-aware parsing）：`tables/`、`extract/sov.py`、`extract/loss_run.py`
* **词汇表驱动的表头识别（vocabulary-driven header detection）**：先精确匹配，再模糊匹配（fuzzy），容忍 OCR 把 "Bldg" 认成 "Bidg"。
* **列带（column bands）**：每列占一段 x 坐标范围；跨页且没有重复表头时沿用上一页的列。
* **对账校验（reconciliation checks）**：SOV 的 TIV 列加总要等于打印的合计；建筑 + 财产 + 营业中断 = TIV；paid + reserve = incurred；每年理赔数和总额要等于期末小计。这些校验既能抓 OCR 错误，又能提高置信度。
* **Textract 后端**：AWS 的表格识别服务，接口相同，可以替换。

### 14. 按文档类型抽取 + 工具调用（per-document extraction + tool use）：`extract/llm_docs.py`
* 每种文件一个提取器：**确定性的版式解析器（deterministic layout parser）**（"标签: 值"表单、邮件头），加一次 **Claude 工具调用（tool use）**。
* **严格 JSON 模式（strict JSON schema, `strict: true`）**：模型的输出必须符合模式。每个字段是 `{value, page, evidence}`，即值、页码、原文引用。
* 当前的 Claude 模型不支持强制工具调用（forced `tool_choice`），所以用 `auto` 加明确指令，没调用工具就重试一次。
* **省钱的设计**：SOV 和 loss run 的解析器自己通过了对账，就不调 LLM，只在校验失败时 **兜底（fallback）**。

### 15. 合并（assemble）：`assemble.py`
按真相来源规则选出每个字段的胜出值，其余读数保留为 **备选值（alternatives）**，供后面的一致性检查和人工复核使用。总保额等合计值从 SOV 和 loss run **推导（derived）**。

### 16. 一致性检查与实体归一化（consistency checks & entity normalization）：`consistency.py`、`normalize.py`
* **跨文件一致性检查（cross-document consistency check）**：胜出值和其他文件的读数比较；不一致就标成 `conflict`，两个来源都保留引用，**但不改值**。
* **归一化（normalization）**：同义词（"JM"→ joisted masonry）、金额（"$1.25M"→ 1250000）、日期、OCR 清洗（`a @b.com`→`a@b.com`）。
* **实体解析 / 实体匹配（entity resolution / matching）**：去掉法律后缀（LLC、Inc.）和泛词（Holdings、Group）后比较名字的核心词。"ACME Holdings" 和 "Acme LLC" 是同一实体；"Acme Distribution" 不是。
* 实测：不做归一化时 95% 的材料被送复核，其中 73% 是假警报；做了以后冲突精确率从 26.7% 升到 88.9%。

### 17. 置信度与路由（confidence scoring & routing）：`confidence.py`
* 置信度 = **提取器先验（prior）** × OCR 质量；独立读数一致就加分（noisy-OR），同一文件内两个提取器不一致、对账失败、值不合理（屋顶比建筑还老）、LLM 的原文引用在文件里找不到，都要扣分。
* **缺失的必需字段（missing required fields）** 单独标出来。
* **路由规则（routing rule）**：关键字段有问题，或任何字段有冲突 / 不合法，就进复核。阈值只在 dev 上调。
* **降级（degraded）≠ 复核（review）**：模型挂了属于基础设施问题，进重试队列并报警，不该占用核保员的时间。

### 18. 规则引擎（rules engine）：`rules_engine.py`
* **确定性（deterministic）**：同样的输入永远同样的结论；每条触发的规则都写明依赖了哪些字段；依赖的字段还在复核中时会注明。
* **两套实现交叉验证**：生成器里有一套独立实现的标注器（`data/synth/labels.py`）；测试保证两者在全部 120 条标准答案上结论和规则编号完全一致。
* 为什么不让 LLM 决策：**可复现（reproducible）、可审计（auditable）、业务方改 YAML 就能改规则**。受监管的行业需要这三点。

### 19. 带引用的分诊摘要（cited triage summary）：`summary.py`
LLM 只写叙述文字，每个事实要用 `[字段路径]` 标出来源。**校验器（validator）** 检查：引用的字段必须存在且有值，文中出现的每个数字都要能追溯到被引用的字段（允许 0.5% 的四舍五入误差）。不通过就换成 **模板摘要（template fallback）**。

### 20. 服务与复核界面（service & review UI）：`service/`
* **FastAPI** 接口：上传、查询、复核队列、批准 / 更正。
* **SQLAlchemy** 存储：有 `DATABASE_URL` 就用 Postgres，否则用 SQLite。
* **HTMX** 页面：每个字段显示值、置信度条、状态和原因、来源页码、原文片段、备选值；可以逐行修改。
* **人工更正变成新的测试用例（corrections → eval cases）**：`scripts/export_corrections.py`，形成 **人在回路（human-in-the-loop）** 的数据飞轮。

### 21. AWS 部署（基础设施即代码，IaC, infrastructure as code）：`infra/`
* **CDK（Cloud Development Kit，Python 版）**：用代码定义云资源；`cdk synth` 不需要 AWS 账号就能生成 CloudFormation 模板。
* 流程：**S3 收件桶（intake bucket）** → **EventBridge**（manifest.json 上传时触发）→ **Step Functions 工作流（state machine）**：classify → extract → validate → rules → summarize，每一步是一个 **Lambda**（容器镜像，因为要装 Tesseract）→ **Bedrock**（调用 Claude）→ **DynamoDB**（记录）。
* 步骤之间的状态存 S3，因为 Step Functions 单次传参上限是 256 KB。
* **KMS 加密（encryption）**、**按时间点恢复（PITR, point-in-time recovery）**、**重试与退避（retry with backoff）**、失败兜底步骤 `MarkFailed`。
* **CloudWatch EMF（embedded metric format）**：往日志里打一行结构化 JSON 就变成指标；配仪表盘（dashboard）和告警（alarms）。
* 关键测试：逐步运行并在每一步之间做 JSON 序列化，结果和本地一次跑完完全一致，即"云上跑的就是评测测过的代码"。

---

## 第四部分：面试常用表达（English phrases）

* "Evals before features: I built the dataset and harness first, then improved the system one measured step at a time."
* "The headline metric is the **silent critical-error rate**. It went from 67.5% to 0% on the held-out test set, and stayed at 0% with Claude."
* "Rules decide, the LLM explains. Decisions must be reproducible and auditable."
* "Deterministic parsers give an **independent second reading**. Agreement raises confidence; disagreement goes to a human."
* "Template C is held out. The overfitting is measured, not hidden."
* "Infrastructure failures **degrade** gracefully; they don't flood the review queue."
* "Every number in the README comes from the harness, and each live column names the model that produced it."
* "With Claude, the held-out template went from 84.5 to 99.8 F1, decision accuracy to 100%, for about seven cents a submission."
* "My first live run showed a metric that couldn't fail: 39 of 40 narratives were silently replaced by the template while the dashboard said 100%."
