# Q2—Q4 条件几何耦合 v2

使用主参谋批准分发的 `q4-r3-spatial-copdem-v1-frozen-export`，入口 SHA256 `8eb6cbc1b85e60fe8a82906f4f025ec22b3bcf96d5c59bd0535ffbe0ccf8a0c5`。所有8个顶层成员已逐文件核验；只读取本树副本和明确列出的只读地形缓存，不读取Q4活动工作树。保留v1发布文件原字节；本文件与独立`exports/release_bundle_v2.json`组成新增版本。

## 实际计算

- 60 m源mask：257格，水平面积925200 m²；120 m：67格，面积964800 m²，相差4.2802%。这是同一候选几何栅格化差异。
- 两网格地形像元与交付NPZ逐值相等。完整DSM先计算`atan(norm(gradient(z)))`，再选mask；60/120 m源区地表坡度中位数分别为41.2263°/41.8135°，P05–P95分别15.1698–60.8892°/15.2297–56.8030°。地表坡度不是结构面倾角，没有替换或重新拟合父机制theta。
- 父接口8个预定参数×4机制=32个情景，扩展为64行。共同体积`V=A60*h_mechanism/cos(theta_mechanism)`，两个网格的垂直厚度分别`V/Agrid`。体积范围16476616.480308–51755728.592650 m³；总体质量范围24930853979.760117–92354489432.754044 kg。
- 全64行实际构造厚度数组并积分。最大体积相对误差1.44e-16；组分质量和相对误差2.5e-16。32对网格体积与质量一致。前2个预定参数`q2r3-p0000`、`q2r3-p0036`保存4张float64厚度GeoTIFF；各机制共享同参数初值栅格，其余情景明确给出mask路径、数组名和常数垂直厚度，可原样重建。
- 组分沿用父接口的体积分数，和为1；岩/冰相密度2700/917 kg m⁻³，体积加权总体密度与父参数一致。自由水相比例为父情景的0，**没有把H储水状态推算为释放自由水量**。全部初速度为EPSG:32645坐标下的零向量，方向无意义。

## 接口解释与限制

`base_scenario_id`精确指回父32条记录；新`scenario_id`添加`__geomv2_60m/120m`，`geometry_version=q4-r3-spatial-copdem-v1`。`mechanism_thickness_normal_m`与`mechanism_plane_theta_deg`保留父模型定义；`release_thickness_vertical_m`是用于栅格积分的厚度，`release_thickness_normal_equivalent_m`只表示按该假设倾角换算的等效量。120 m保持体积的厚度缩放不重新计算父单位面积稳定裕度。CSV中的`source_polygon_or_release_raster`为带mask和可选TIFF的JSON规格；未保存TIFF的情景仍有完整常数厚度定义。

mask是Q4按题图重建的条件源区候选，不能称为实测失稳面或反演体积。COPDEM是2011–2015主要获取、2021编辑发布的背景地形，垂直基准EGM2008，不能声称2026事件地形。此实验只证明几何、厚度、体积和组分质量的接口一致性，没有验证真实源区、体积、结构面、材料或启动时刻；不增加独立事件数，也不赋参数网格概率。保留父`onset_status`；从未越阈情景若用于传播，只表示外加假设释放，并不代表模型预测启动。

实际复跑命令（离线；输出版本已存在时只允许字节相同）：

```sh
track_b/.venv/bin/python track_b/research/q2/round3/scripts/integrate_geometry.py
```

逐情景误差、输入哈希见`results/geometry_integration_summary.json`；坡度分布见`results/geometry_integration_terrain.csv`。最终科学采用待队员联合审视。
