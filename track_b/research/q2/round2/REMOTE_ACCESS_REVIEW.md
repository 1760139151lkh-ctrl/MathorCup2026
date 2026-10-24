# 第二轮指定同轨 VV 对：匿名访问结论

日期：2026-10-24。仅尝试任务书指定的 S1D descending/relative orbit 121、2026-08-19与08-31两景，VV优先；未扩选日期／轨道／极化，未下载完整场景。

## 已实际执行

从冻结的官方场景清单提取两条 VV COG HTTPS 资产入口，各发一次匿名 GET，Range为bytes=0-16383。关闭环境认证继承、自动重定向和重试。请求前启用持久化总账，失败／元数据／头部及像元响应正文均在同一计数中。

| 景 | UTC观测时刻 | 库存VV对象大小 | 实际响应 | 正文实读 | 可采用内容 |
|---|---|---:|---|---:|---|
| 8/19，004187_007ABD_B38C | 00:10:36.889384Z | 671,193,558字节 | 401，application/json | 96字节 | 认证失败链；没有TIFF／像元 |
| 8/31，004362_0080EC_65B9 | 00:10:37.647071Z | 671,749,872字节 | 401，application/json | 96字节 | 认证失败链；没有TIFF／像元 |

两时相累计正文 **192字节／134,217,728字节**。精确URL、Range、UTC、状态、Content-Type、响应文件与SHA-256见`network_budget.json`和`results/pair_access.json`。计数是客户端显式消费的响应正文，不包含HTTP头、TLS开销或操作系统缓冲；没有把库存对象大小当实读字节。

## 采用、排除与未知

- **可采用：** 固定两景元数据身份、匿名请求的实际认证失败和预算账。结果仅针对这两个已声明入口。
- **排除：** 在当前匿名条件下用本轮结果作VV像元支持、配准、地形可见性或变化解释。JSON错误正文不是遥感像元。
- **仍未知：** 认证之后的Range能力、TIFF目录、真实像元CRS／分辨率／有效比例及AOI可见性。401不是“不支持Range”的证明。
- **空间输入：** 已接收主参谋分发的`q4-r2-fig1-search-v1`，并核对GeoJSON、原证据及独立advisor记录哈希。AOI约175.36km²；两景都相交但均未完整包含AOI，三个图上候选符号锚点均在两景目录足迹内。仅作离线拓扑核对，没有新增网络请求；不缩小AOI或重试下载。见`results/aoi_pixel_support.csv`和`aoi_support_check.json`。

采用角色始终为search_only。生产者JSON的pending原字节保留，独立advisor记录仅说明有限角色采用；原图精度、原始投影／基准、纬度独立留出仍未知，2km余量不作为位置误差界或置信区间。足迹支持不是精确地面覆盖、真实释放范围或像元清晰／配准通过。

## 守卫与离线重现

`scripts/check_network_guards.py`的7个离线HTTP夹具检查通过：Range被答200即不读正文、超请求范围拒读、有界206只认头部、两景失败正文累计／持久化、错误正文64KiB界限、预算不足时不发请求、重定向不跟随／不读正文。夹具不证明提供方Range能力或真实像元可用。

离线复跑：

    track_b/.venv/bin/python track_b/research/q2/round2/scripts/check_network_guards.py
    track_b/.venv/bin/python track_b/research/q2/round2/scripts/probe_pair.py --offline

`--online`是首次实测命令；同一总账中已有尝试的场景不会自动重复请求，计数不按景重置。测试只在本问临时子目录模拟，不改真实192字节总账。没有注册、凭据使用、付费、联系作者或更改系统设置。
