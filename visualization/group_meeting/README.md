# GASF 组会版图表：修改与验收报告

本目录是原有论文版图表的独立、16:9 组会适配版本。原始日志、ROS 2 源码、现有解析/统计/绘图脚本、原版图片和 CSV 均未覆盖。

## 实际交付

`figures/` 中包含五个主题、六页图，每页均有 **4800 × 2700、300 DPI PNG** 以及 SVG/PDF 矢量版本，共 18 个图文件。建议一页图占一张 16:9 幻灯片；不要把六页总览当成正式汇报页。

| 输出文件名（另有同名 SVG/PDF） | 修改及原因 |
| --- | --- |
| `01_online_mask_state_evolution.png` | 标题去掉 Convergence；七个独立实验面板按静态三组/动态四组排列，第八格用于紧凑的指标图例。静态零 Mask 用简短标签与零线表达，保留全部候选序列；首次正 Mask 日志帧仍为 170/140/170/50。共同纵轴，静态横轴 0–750、动态 0–1800，范围在行标题中明确。 |
| `02_mask_hit_ratio_comparison.png` | 原上下布局改为左右“分布 + 时间序列”。静态三组列在上方，分别注明全部 64/63/71 个样本均为零，消除重叠点/均值符号。动态箱线保留全部点；抖动仅在分类纵轴，比例值不变。右侧保留七组完整原始 Frame 序列，并显示静态曲线终点。 |
| `03_runtime_latency_distribution.png` | 左侧保留 0–10 ms 完整范围及全部样本，右侧放大 0–3.2 ms 的 ECDF。843/845 个日志样本位于放大范围内，2 个范围外值在左图保留；9.304 ms 单独标出。ECDF 分母仍为各组全部样本数，未对可视范围重新归一化、未拟合。 |
| `04_static_vs_dynamic_learning.png` | 拆分页 1：只讲 Active Mask 与 Candidate-map，保留 Static / Dynamic 两列和真实曲线。每列横轴根据时长设置，纵轴同指标保持一致，避免静态列被大量空白压缩。 |
| `04b_learning_progress_and_queue.png` | 拆分页 2：显示 learning_frames 与 orientation_bins 两项时间序列；七组 dropped_learning_batches 在 845 个观测上全部为零，用一条明确的总说明代替多个相同零值面板。五个指标在两页间完整保留。原五行完整图仍在上级 `figures/`。 |
| `05_orientation_diversity_vs_mask_activation.png` | 保留 Cage A/B 分列、Mask/Candidate 分行及两列重复展示的无笼体静态参考。点、轴、标题增大，图例集中排列。60-bin 虚线保留，注释移到页脚以避免盖住真实点；上限处所有重叠观测仍逐点绘制，无抖动或删除。 |

统一白底、轻网格、28 pt 主标题、17–20 pt 子标题/主要轴标签、14 pt 刻度/图例/简注。七组实验的颜色和点形直接导入原 `src/style.py`，没有重新指定颜色语义。时间序列仍包含每一个日志观测顶点，只将符号标记改为每 7 个记录显示一次；未抽稀曲线数据、未平滑或补帧。

## 复现

在仓库根目录运行，复用上级 requirements 中已有依赖，无新增依赖：

```powershell
python visualization/group_meeting/plot_meeting.py
python visualization/group_meeting/verify_meeting.py
```

如果已创建上级虚拟环境，可将 `python` 换为 `./visualization/.venv/Scripts/python.exe`。组会版本仅支持已经核实的这批实验；输入固定为 `analysis/results/online_controls/`。脚本会先验证原版数据与统计，而不是静默接受变更后的实验。可以用 `--output visualization/group_meeting/another_render` 指定本目录内的其他绘图输出位置；默认验证和对照图脚本针对 `figures/`。

已有 Poppler 且位于 PATH 时，可附加执行 PDF 渲染验收：

```powershell
python visualization/group_meeting/verify_meeting.py --render-pdfs
```

## 如何确认数据没有变化

1. 开始工作时对 89 个原有文件建立 SHA-256 基线，涵盖七组日志、`src/`、已有可视化代码、图表、CSV 和说明文档；排除解释器/字体缓存。生成前后以及最终验收均确认 **89/89 文件未变化**。
2. 复用 `parse_logs`、`with_derived` 和 `compute_statistics`，重新从只读原日志取得 **845 条记录、7,605 个核心字段值**。无解析诊断。未新增解析逻辑。
3. 新版使用的 parsed_records 和五张统计表，重新序列化后与原 CSV **逐字节一致**，包括有效样本量、比例、分位数、激活帧和相关分析结果。
4. 绘制时执行 **93 项数据到图元检查**：时序的全部 x/y 顶点对应原始 Frame 与指标值；分布散点 x 值等于真实比值/延迟；ECDF 保留全部排序样本及完整样本量；方向散点的每个 x/y 对与原日志相同。每页都覆盖七组实验。常数零值用标签表达时记录其全部样本数。
5. 6 张 PNG 均实际打开检查尺寸/DPI；6 张 SVG 的 XML/矢量路径检查通过；6 张 PDF 均用 Poppler 打开并渲染。导出前进行文字边界检查，导出后逐页目视检查。首轮发现的重复标题和标签相邻问题已修复，最终版本未发现文字裁切或图例遮挡。

验证证据：`reports/protected_before.json`、`reports/validation.json`、`reports/format_validation.json`。`reports/comparison_01.png` 至 `comparison_05.png` 按相同 16:9 显示区域对比前后布局；`reports/overview.png` 是六页导航总览。

## Skill 的实际应用

再次完整阅读安装的 `plot-is-all-you-need` 入口、plot/SKILL.md 及 Resonance/Rendition/Appraisal，审计现有代码/文档并查看五张实际旧图。按用户直接执行要求走快速路径。

- `oa-tech-pone-0258309-f04`：沿用箱线和实际观测点；为投屏调整尺寸、布局和零值表达。
- `oa-geo-hess-30-629-2026-f12`：采用成对分布视图和 ECDF 结构；不采用零值数据不适合的密度平滑。
- `plos-cc0-trajectories`：参考从论文到报告的直接标注与局部聚焦。其卡片明确提醒报告版省略部分轨迹，因此本任务只借用聚焦/放大布局，**不采用省略数据的做法**；全部延迟仍展示于完整范围。

保留已有代码，通过新脚本导入原来的 `trace`、`export`、`subset`、颜色/点形及统计模块，对绘图函数做专门的展示适配。没有重写解析器，也没有安装新包或改动图库。参考方向图在 `reports/style_directions.png`；与旧图并排比较完成了 Appraisal。

参考出处：前三类既有参考图的署名见上级 `reports/reference_attribution.md`。新增 `plos-cc0-trajectories` 为 Rougier NP, Droettboom M, Bourne PE (2014), *Ten Simple Rules for Better Figures*, Figure 3，[论文](https://doi.org/10.1371/journal.pcbi.1003833)，[CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/)，依据安装图库的 THIRD_PARTY_NOTICES.md。

## 汇报边界

详细口头说明见 [speaker_notes_zh.md](speaker_notes_zh.md)。关键限制仍是：日志每 10 帧取样；无 Ground Truth 和明确匹配的重复试验；A/B 为笼体条件；04_loop_A 存在相对位移；global bins 上限 60；模型字段为异步观测。图中“更高命中比例”“更多体素”“计数变平”分别不能直接解释为更高准确率、更好性能或算法收敛。

已检查数字图像和渲染效果，实际会议室投影亮度/距离仍可能影响浅蓝及粉色辨识。建议全屏展示，并保留彩色点形；不要进一步缩小或裁掉边界/采样提示。Figure 1 七面板是信息最密集的一页，可以先讲静态行，再讲动态行；Figure 4 已拆成两页以保持可读性。
