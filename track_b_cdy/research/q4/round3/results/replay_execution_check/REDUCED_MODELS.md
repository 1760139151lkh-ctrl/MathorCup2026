# 独立一维与二维基线：实际计算与适用域

这两条路线已经运行真实区域地形上的条件释放；它们是自写浅层流有限体积实现，均不是 r.avaflow、RAMMS 或 D-Claw。共同输入由空间组提供，候选源区／路径／口岸点未因此成为事件真值。

## 方程、数值方法和共同条件

求解 `∂t h+div(h u)=0`、`∂t(h u)+div(h u⊗u+g h² I/2)=−g h grad(z)−h a_f`，`a_f=[mu*g*cos(theta)+g*|u|²/(xi*h)] u/|u|`。这里 h 是 Cartesian 图地形上的垂直厚度、速度为水平投影；不包含曲率、主动／被动土压力、冰融化、相间交换、孔压、底床侵蚀或河水夹带。陡坡不是此实现已经验证的适用域。

一阶 Rusanov 通量配合 Audusse 水静力重构及两侧压力修正。运输显式，CFL=.35；摩阻用速度标量隐式二次根收缩，不改变体积。干层只令动量归零，体积保留；任何负深截断的增加体积单列，低于−1e−8m即失败。开边界为零梯度透射，出流和可能的入流逐面计量。没有动能提前停止，均算至1800s。

2D 60m源区257格、925200m²，15m体积13,878,000m³；120m源区67格、964800m²，厚度乘925200/964800保持体积。初速UTM45N东／北均0。5／15／30m及mu=.08/.15/.25、xi=500/1000/2000按OFAT比较；136m挑战来自外部作者重建，实际格网体积125,827,200m³，未强迫等于论文体积或拟合约8分钟。密度2000kg/m³仅为显式均质情景记账，不影响本方程的体积动力学。

1D在P1/P2/P3真实候选折线上插值DEM高程，保留上坡障碍，不强制单调。站距为UTM水平折线长度；首个连续源区段均匀厚度释放，等效恒宽=925200m²/该段长度，使体积与2D完全相同。恒宽不是实测谷宽；1D不能描述横向分流、汇流展宽或脱离指定路径。

## 计算结果

实际执行 2 个区域情景：1 个2D、1 个1D。区域质量账相对残差最大 `2.684313516689663e-16`。每个情景的完整记录、首达括号、体积账和缓存哈希分别见 `results/reduced_<run_id>.json`。

| Run | V0 (Mm³) | hmax (m) | u_max any wet (m/s) | Target delay (s) | Status |
|---|---:|---:|---:|---:|---|
| 1d_P1_ref | 13.878 | 18.61 | 3.53 | null | not_reached_within_horizon |
| 2d_ref_120m | 13.878 | 53.10 | 4.31 | null | not_reached_within_horizon |

最大速度表格按任何h>1e−9m湿格统计，薄前缘可能影响该值；不将其当实测峰速。图中的hmax是全时最大流深；h_final只是1800s残余材料，只有另报速度<.1m/s体积才可称近静止残余。footprint为hmax>=.1m，并非泥石流真实影响范围。

到达定义为代表口岸点100m内格心或1D路径格心第一次h>=.1m的求解器步；保留前后步括号，保存的过程图另以30s间隔。未达为1800s内未达，不能解释为永久不到达；数值失败、目标缺失、出域也保留。时间从条件成规模释放起算，`initiation_to_release_delay_seconds=null`；任何传播时延均不能替代源区首次机械启动时刻。

## 数值反证及采用建议

两格网和减半CFL的实算差异见`reduced_comparisons.json`；两格网不构成渐近收敛证明。若官方复杂模型传播更远，须先区分其数值处理与物理新增项；不能把这个自写方法的缺陷直接算作多相／孔压收益。没有本地区域独立传播真值，校准数和独立事件验证数均为0；合成基准不计作事件。所有区域结果属于conditional_scenario，不产生概率、95%区间或覆盖率。

## 文件与复跑

`config/reduced_protocol.json`及amendment01在区域求解前登记；`config/reduced_environment.lock/json`固定局部Numba运行时，原44包venv未改。大型过程场在专有cache，run JSON逐文件bytes/hash绑定。源码为五个reduced_*.py（含交付检查与清单生成）。先建立并锁定局部环境、以pth桥接原科学包（原环境路径见环境JSON），随后从本worktree执行：

```sh
NUMBA_CACHE_DIR=/Users/maxchen/Documents/MathorCup/research_cache/round3/q4/reduced/numba_cache /Users/maxchen/Documents/MathorCup/research_cache/round3/q4/reduced/venv/bin/python track_b/research/q4/round3/scripts/reduced_benchmarks.py
NUMBA_CACHE_DIR=/Users/maxchen/Documents/MathorCup/research_cache/round3/q4/reduced/numba_cache /Users/maxchen/Documents/MathorCup/research_cache/round3/q4/reduced/venv/bin/python track_b/research/q4/round3/scripts/reduced_region.py --mode all
/Users/maxchen/Documents/MathorCup/research_cache/round3/q4/reduced/venv/bin/python track_b/research/q4/round3/scripts/reduced_report.py
```

数值方法来源：[Audusse et al. 2004](https://epubs.siam.org/doi/abs/10.1137/S1064827503431090)、[水静力重构限制原文](https://arxiv.org/abs/1206.4986)；摩阻项参考[RAMMS官方方程说明](https://ramms.ch/ramms-avalanche/friction-parameters/)。参数范围由共同协议指定，未从RAMMS校准表迁移为本地区域真值。实际下载元数据／源字节哈希在reduced_protocol的sources登记；可读范围以该记录为准。

新增OSM五个候选对象按预登记protocol_v2全量后处理，不挑选最快点：`results/reduced_osm_target_arrivals_v2.csv`保留每个模型×五个对象。使用已存30s场，不重算；首次达阈值与前一个未达输出构成括号，不能标成求解器步精度。原paper_port_symbol主目标和结果完全保留，设施／旧桥／临时桥对象身份不合并。

新增对象共10行，状态计数{'missing': 5, 'not_reached_within_horizon': 5}。1D路径有限终点及格心与新对象100m圈可能不相交，missing表示空间支持缺失；不能改写为未到达、外推或取最近格替代。
