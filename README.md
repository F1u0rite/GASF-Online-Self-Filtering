# GASF — 在线自体点云滤波（V1）

**GASF（Geometry-Agnostic Self-Filtering）** 是面向笼式无人机的 LiDAR 自体回波过滤原型，服务于隧道等 GPS 拒止环境下的 SLAM 与自主导航研究。

目标是在**不预先提供笼体 CAD 模型**的情况下，在线学习 LiDAR 周围的固定自体结构，减少笼体杆件、连接件及平台安装结构等回波对后续建图的干扰。

> 当前版本是基于 ROS 2 Humble 的 **V1 实验基线**：已实现近场体素时序学习、IMU 姿态多样性门控及异步 Mask 更新；**尚未实现完整的世界坐标系运动一致性判别，也没有真实自体/环境点标签来评估准确率。**

## 1. 算法思路

1. **近场体素化**：从 Livox Mid-360 的 `CustomMsg` 中提取近场点，在 LiDAR 坐标系下离散为体素。当前默认体素边长 **0.06 m**，学习范围 **0.12–0.45 m**。
2. **时间重复性**：累计每个体素在不同帧中的出现次数，并记录最近一次观测；长期不出现的候选体素会被清除。
3. **姿态多样性门控**：使用 IMU 陀螺仪积分得到的相对姿态，对观测划分姿态区间。体素必须同时达到最少观测次数和最少姿态区间数，才进入正式 Mask。
4. **异步模型学习**：LiDAR 回调把候选体素送入学习队列，后台线程定期构建 Mask 快照；实时过滤直接读取最新快照，不需要等待学习完成。
5. **实时过滤与可视化**：命中 Mask 的点被划入删除集合，其余点保留；同时输出原始、保留、删除和模型点云。

当前核心参数见 [`src/gasf_filter/config/online.yaml`](src/gasf_filter/config/online.yaml)：

| 参数 | 默认值 | 用途 |
| --- | ---: | --- |
| `voxel_size` | 0.06 m | 体素分辨率 |
| `min_range` / `max_range` | 0.12 / 0.45 m | 近场学习及过滤范围 |
| `min_hits` | 8 | 最少观测帧数 |
| `min_orientations` | 3 | 最少姿态区间数 |
| `orientation_step_deg` | 6° | 姿态分箱角度阈值 |
| `stale_frames` | 250 | 体素过期帧数 |
| `snapshot_every_frames` | 5 | Mask 快照更新间隔 |

**注意**：V1 实际学到的是 LiDAR 坐标系中的“稳定近场候选结构”，并非对笼体进行语义识别。与雷达刚性连接的实验板车前缘也可能被学习；反之，近距离静止环境仍可能造成误学习。

## 2. 环境与 ROS 2 话题

- 平台：Jetson Orin Nano、Ubuntu 22.04、ROS 2 Humble
- 传感器：Livox Mid-360 + IMU
- 输入：`/livox/lidar` (`livox_ros_driver2/msg/CustomMsg`)、`/livox/imu` (`sensor_msgs/msg/Imu`)

| 输出话题 | 内容 |
| --- | --- |
| `/gasf/raw_points` | 原始点云（PointCloud2） |
| `/gasf/filtered_points` | 保留点云（PointCloud2） |
| `/gasf/removed_points` | Mask 命中点（PointCloud2） |
| `/gasf/model_points` | Mask 体素中心点（PointCloud2） |
| `/gasf/stats` | 帧数、候选命中数、模型体素数量、处理耗时等 |
| `/gasf/filtered_custom` | 可选 Livox CustomMsg 输出；默认关闭 |

可视化 PointCloud2 按需发布；启用 CustomMsg 输出时保留原始时间戳及每个点的 `offset_time`。

## 3. 编译与运行

```bash
source /opt/ros/humble/setup.bash
source ~/livox_ros2_ws/install/setup.bash
cd ~/cage_filter_ws
colcon build --symlink-install --packages-select gasf_filter
source install/local_setup.bash
ros2 launch gasf_filter online.launch.py
```

在另一终端回放测试数据（原始 bag 不在本仓库中）：

```bash
source /opt/ros/humble/setup.bash
source ~/livox_ros2_ws/install/setup.bash
ros2 bag play ~/cage_bags/06_arc_B --clock
```

使用保存的 RViz2 配置：

```bash
source /opt/ros/humble/setup.bash
rviz2 -d ~/cage_filter_ws/rviz/gasf_v1.rviz --ros-args -p use_sim_time:=true
```

RViz2 的 `Fixed Frame` 必须与点云消息中的 `header.frame_id` 一致。每组**在线冷启动**实验应重新启动 GASF 节点，清空上一组学习的模型。

## 4. 目前的实验

七组实验日志位于 [`analysis/results/online_controls/`](analysis/results/online_controls/)：

- 无外笼体静止：`01_static`
- 笼体 A：`02_static_A`、`03_arc_A`、`04_loop_A`
- 笼体 B：`05_static_B`、`06_arc_B`、`07_loop_B`

初步结果：三组静止实验积累了候选体素，但未满足多姿态门控，因此没有启动正式过滤；四组运动实验均成功在线建立 Mask，并持续产生 Mask 命中。约 10 Hz LiDAR 输入下，记录的回调耗时通常为毫秒级，学习队列无丢弃报告。

这些结果验证了**在线候选模型生成及实时过滤流程**，但 `candidate_hits / raw` 仅表示 Mask 命中比例，**不是自体识别准确率、Precision 或 Recall**。`04_loop_A` 中曾出现 LiDAR 与笼体之间的轻微相对位移，不能直接作为严格刚性安装条件的测试。

## 5. 目录与后续计划

```text
src/gasf_filter/                ROS 2 C++ 节点、参数与启动文件
analysis/                       离线分析脚本、模型与实验结果
rviz/gasf_v1.rviz               已保存的可视化配置
visualization/                  后续论文绘图脚本与输出
```

后续重点：加入 **Body–World Motion Consistency**（自体/世界运动一致性）、环境负证据、冷启动策略和误删率定量评估，再与 FAST-LIVO2 集成验证。

**状态：GASF V1 在线演示基线已建立，尚非最终论文算法。**
