# GASF online-control log audit and scientific visualization

本工程只读解析七组 GASF 在线实验日志，并生成可复现的描述性统计和五类科研图表。全部新增内容位于 `visualization/`，不需要 ROS 2、Linux、GPU、外部服务或 Skill 运行时。

## Windows PowerShell 运行

在仓库根目录打开 PowerShell。建议使用 Python 3.11 或以上；本次实际验证环境为 Windows 11、Python 3.14.8。无需修改 PowerShell 执行策略，也无需激活虚拟环境：

```powershell
py -3 -m venv visualization/.venv
& ./visualization/.venv/Scripts/python.exe -m pip install -r visualization/requirements.txt
& ./visualization/.venv/Scripts/python.exe visualization/run.py
& ./visualization/.venv/Scripts/python.exe -m unittest discover -s visualization/tests -v
& ./visualization/.venv/Scripts/python.exe visualization/validate_outputs.py
```

依赖安装需要可用的 Python 包源；安装后分析与制图完全离线。本次复用了环境中已有的四个依赖，没有安装新包。`requirements.txt` 给出兼容范围；`requirements-validated.txt` 保存交付时实际安装版本，`reports/environment.json` 保存完整环境信息。在支持这些版本的 Python 环境中，需要精确复现依赖时可将安装命令替换为：

```powershell
& ./visualization/.venv/Scripts/python.exe -m pip install -r visualization/requirements-validated.txt
```

若现有 Python 已安装依赖，可直接使用：

```powershell
python visualization/run.py
python -m unittest discover -s visualization/tests -v
python visualization/validate_outputs.py
```

指定输入、输出与仅审计模式：

```powershell
python visualization/run.py --input analysis/results/online_controls --output visualization/reproduced
python visualization/validate_outputs.py --output visualization/reproduced
python visualization/run.py --input analysis/results/online_controls --output visualization/audit_only --audit-only
python visualization/run.py --help
```

默认路径相对于入口脚本解析；显式相对路径相对于当前工作目录解析。输入可以是另一位置的同格式日志目录；为遵守数据保护约束，输出必须在本 `visualization/` 工程内，并且不能与输入树、`src/` 或 `tests/` 重叠。重新运行会更新本工具的同名生成物，不清理目录或修改其他文件。`--encoding auto` 默认严格读取 UTF-8，识别 UTF-8/UTF-16 BOM；可通过 `--encoding` 显式指定其他编码，不使用替换字符掩盖解码错误。

程序报告逐组记录数、诊断摘要、阶段进度和输出路径。缺组、解码错误、Frame 逆序或 `candidate_hits > raw` 等严重问题会保留诊断/统计输出、阻止正式制图并返回退出码 2；正常完成返回 0。缺失的单个指标使用 NA，该指标的统计按有效记录计算。所有重复 Frame 的副本均保留，但排除出正式统计；Frame 逆序不通过排序掩盖，需要按真实会话拆分后分析。

## 已审计数据

7 个 `.log` 文件，845 条有效遥测记录，845 条 `---` 分隔行。编码均为 ASCII 兼容 UTF-8，CRLF 换行。九个核心字段没有缺失/非法值，无重复 Frame、零分母或超过 1 的命中比例；838 个组内相邻 Frame 间隔全部为 10。逐字段分布、异常值计数和文件哈希见 CSV。

| Experiment | Logged n | Frame range | Mean Mask Hit Ratio | Sample P95 (ms) | Sample P99 (ms) |
| --- | ---: | --- | ---: | ---: | ---: |
| 01_static | 64 | 10–640 | 0% | 2.4709 | 3.06450 |
| 02_static_A | 63 | 10–630 | 0% | 2.3726 | 2.60112 |
| 03_arc_A | 177 | 10–1770 | 1.6412% | 2.2572 | 2.90344 |
| 04_loop_A | 174 | 10–1740 | 1.7059% | 1.8316 | 1.97847 |
| 05_static_B | 71 | 10–710 | 0% | 2.3875 | 3.07660 |
| 06_arc_B | 177 | 10–1770 | 3.1832% | 2.1064 | 2.52424 |
| 07_loop_B | 119 | 10–1190 | 3.4896% | 1.5341 | 1.92050 |

上述 P95/P99 仅针对每 10 帧输出一次的**日志样本**，不是完整帧级延迟分布，也不能证明实时性。表中 n 是日志观测数，不能当作独立试验次数。完整精度、均值、P50、最大值见 `tables/callback_latency_summary.csv`。

静态组只观察到 1–2 个姿态分箱，Mask 和命中数为零。运动组首次正 Mask 的**日志帧**依次为 170、140、170、50；它们不能确定未记录帧中的精确激活时刻。四组运动数据最终均达到当前源码的 60-bin 上限。最大日志耗时为 `03_arc_A` Frame 1500 的 9.304 ms，未删除或裁切。

## 字段语义与研究限制

| Field | Type/unit | Meaning verified from current source |
| --- | --- | --- |
| frame | Nullable Int64 count | Received LiDAR callback count; original frame IDs preserved |
| raw | Nullable Int64 points | All incoming `msg->points`, including invalid and non-near-field points |
| candidate_hits | Nullable Int64 points | Finite near-field points hitting the active snapshot |
| mask_voxels | Nullable Int64 voxels | Mask snapshot cardinality read at callback start |
| callback_ms | Nullable Float64, ms | Timed callback processing up to enqueue; excludes subsequent statistics emission and asynchronous learner completion |
| learning_frames | Nullable Int64 batches | Learner-processed observation batch count |
| orientation_bins | Nullable Int64 bins | Global stored relative-IMU orientation prototypes; source cap 60 |
| candidate_voxels | Nullable Int64 voxels | Current learner candidate-map size, including unconfirmed entries |
| dropped_learning_batches | Nullable Int64 batches | Cumulative learner queue overflow / failed submission count |

定义证据来自根目录 README、`gasf_filter_node.cpp`、`core.hpp` 和 `online.yaml`。详细函数/行号与默认参数见 [设计及语义审计](reports/design_plan.md)。当前代码不等于历史运行配置的证明：日志未携带构建哈希、完整参数快照或运行清单。

- **Mask Hit Ratio = candidate_hits / raw**。CSV 使用 0–1 小数，图使用百分比。缺失、非法计数和零分母不补零。`hits > raw` 不截断，而是报错并停止正式制图。默认均值是逐日志记录比例的算术平均；额外的 `pooled_logged_points_ratio` 是日志点计数加权比例，两者均不代表未记录帧。
- Mask Hit Ratio 不是 Precision、Recall、Accuracy 或 F1；没有 Ground Truth，不能据此评价真实自体识别准确率，比例高也不一定更好。
- `callback_ms` 仅为稀疏日志样本；P50/P95/P99 使用 NumPy `method='linear'`，标准差使用 `ddof=1`。分位数插值仅作用于排序后的观测值，不生成时间序列帧。样本最大值也不是运行全过程最大值。
- Mask 使用回调开始的快照；学习指标来自独立的后台原子变量。字段不是一个同步的学习器状态快照。`frame-learning_frames` 为 0 或 1 的记录均被保留，不能把相差 1 当作丢帧。
- 当前默认准入依据是每体素 hits >=8、每体素方向位数 >=3、最近观测未过期；日志中的全局 `orientation_bins` 不能替代每体素条件。60-bin 平台反映实现容量限制，不能证明方向覆盖完整。
- `01_static` 无外笼体；A/B 是两种笼体条件。`04_loop_A` 被仓库标注存在轻微 LiDAR/笼体相对位移，所有图均用星号提示。各组长度不同，无已确认的匹配重复试验，不合并为静态/动态总体做显著性检验。
- Spearman 使用平均秩处理并列值，记录有效配对数；常数序列返回 NA，不返回 0。自相关、共同时间趋势、异步状态和上限效应限制解释，因此无 p 值、置信区间或因果结论。
- 没有体素身份序列，仅数量趋稳不能证明算法或 Mask 成员收敛。`dropped_learning_batches=0` 也不能证明 LiDAR/ROS 传输无丢失。

## 图表与文件

正式图使用同一套 Matplotlib 图对象依次导出 `.png`、`.svg`、`.pdf`，英文标注，DejaVu Sans 字体，统一实验颜色/点形、零起点坐标轴；无平滑、无双纵轴、无异常值删除。箱线图为 Q1/中位数/Q3 与 1.5-IQR 须，不能解读为置信区间。点的轻微纵向抖动仅用于分类分布图，不改变指标值，并使用固定随机种子。

| File stem | Design |
| --- | --- |
| `01_online_mask_convergence` | 七组同尺度分面；Mask 实线与候选体素虚线；标记首次正值日志帧 |
| `02_mask_hit_ratio_comparison` | 箱线 + 全部日志点 + 均值；补充真实 Frame 趋势 |
| `03_runtime_latency_distribution` | 全范围箱线/散点 + ECDF；保留 9.304 ms 最大观测 |
| `04_static_vs_dynamic_learning` | 五指标 × 静态/动态分面；每个实验独立保留 |
| `05_orientation_diversity_vs_mask_activation` | A/B 分列、Mask/候选体素分行；标记 bin cap；无笼体参考在两列重复展示 |

图注见 [figures/captions.md](figures/captions.md)。Figure 4 建议作为论文全页图或汇报中的大图，避免缩成窄单栏。PNG 宽度均为 2460 px（300 DPI），各图高为 2610、2160、2220、3180、2040 px。PNG 元数据可能读取为 299.9994 DPI，这是 PNG 用整数 pixels-per-metre 表达 300 DPI 的正常舍入。

```text
visualization/
├── README.md
├── requirements.txt
├── requirements-validated.txt
├── run.py
├── validate_outputs.py
├── src/
│   ├── __init__.py
│   ├── log_parser.py
│   ├── data_audit.py
│   ├── statistics.py
│   ├── exploration.py
│   ├── style.py
│   ├── plot_results.py
│   └── reporting.py
├── tests/test_analysis.py
├── figures/                 # Five stems × PNG/SVG/PDF, captions and manifest
├── tables/                  # Twelve CSVs and table definitions
└── reports/                 # Audit, design, Skill comparisons, QA and integrity evidence
```

12 个 CSV 为 `parsed_records`、`file_inventory`、`data_quality`、`parse_diagnostics`、`field_ranges`、`frame_intervals`、`cross_group_identity`、`mask_hit_ratio_summary`、`callback_latency_summary`、`static_dynamic_summary`、`mask_activation_summary`、`orientation_association`。字段、样本数及统计限制见 [tables/README.md](tables/README.md)。空的 `parse_diagnostics.csv` 保留表头，代表本批数据无解析异常。

## Skill 的实际应用

完整阅读 `plot-is-all-you-need` 兼容入口、plot/SKILL.md 和 Resonance/Rendition/Appraisal 细则。依据用户“不必再次确认”的要求采用快速路径：阅读图库索引，查看三张候选原图和鉴赏卡，选择观测点/箱线、ECDF、双面板关系图的结构；先生成真实日志的六视图探索图，再确定正式方案。三张参考的 `code` 字段为空，因此自行实现 Matplotlib 绘图。配色根据色觉可辨识要求调整为 Okabe-Ito 加中性灰，未照搬参考图数据。

参考样板：`reports/style_references.png`；探索：`reports/exploratory_overview.png`；参考/成品并排检查：`reports/style_appraisal.png`。完成了五张正式图目视检查，并修复 Figure 1 初版的图例/说明重叠。参考图来源及授权记录在 [reference_attribution.md](reports/reference_attribution.md)。没有修改图库、Skill 或用户品味文件，没有向图库收录结果。

## 验证与可复现性

- 18 项 unittest 已通过。测试临时合成记录只存在于测试临时目录，不进入研究统计或图表。
- 独立逐 token 读取原日志，核对 845 × 9 = 7,605 个核心字段值。
- 输出验证重新计算比例、有效样本数、均值、最大值，以及独立实现的线性分位数，与 CSV 核对。
- PNG 实际打开并检查尺寸/DPI；SVG XML、矢量路径和无嵌入栅格检查；PDF 文件结构验证。绘图导出前检查文字是否超出画布，随后人工目视检查遮挡。
- 本次还使用已有 Poppler 渲染全部 PDF、pypdf 严格读取页与文本，用已有 sharp/librsvg 渲染全部 SVG，均成功。这些是交付验收的补充工具，不是日常 Python 分析依赖。
- `protected_files_before.json` 是开始工作时的日志及 `src/` 共 17 个文件基线；`run_integrity.json` 比较每次运行前后哈希。验收时再次对照初始基线，原始日志和 ROS 2 源码未修改。

如果系统已有 Poppler 且命令位于 PATH，可复现 PDF 渲染检查：

```powershell
python visualization/validate_outputs.py --render-pdfs
```

未安装 Poppler 时，常规生成与基础验证仍可运行；基础验证报告会明确只完成 PDF 结构检查，不能将其当作渲染检查。完整验收记录见 [reports/verification_report.md](reports/verification_report.md)、`validation.json`、`pdf_structure_validation.json` 和 `svg_render_validation.json`。

## 后续实验

需要匹配时长/订阅负载的重复冷启动试验、完整逐帧与端到端时间轨迹、历史构建/参数清单、Mask 成员快照及明确收敛判据。若要评价真实识别性能，需要独立标注的自体/环境点 Ground Truth 和适当的留出试验；若要研究方向覆盖，需要 IMU/姿态轨迹与每体素方向证据。本工程没有用现有日志替代这些证据。
