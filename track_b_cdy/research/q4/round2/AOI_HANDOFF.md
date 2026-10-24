# Q4 → 主参谋：搜索 AOI 早交件

日期：2026-10-24（America/New_York）。版本`q4-r2-fig1-search-v1`；状态：已生成，待主参谋审核后分发Q2；没有声称Q2已接收或公共已采用。

- AOI：`results/search_aoi.geojson`，SHA-256 `14db392ea6d318c2df34152af950b227653fd1f938aed1f4aa9eedf92c29579f`。
- 证据：`results/search_aoi_evidence.json`，SHA-256 `78ff69266903ee77626679b0bba542ec36f1e73e3d39581909543d63ba262d14`。
- 配准约束与审查：`results/georeference_controls.csv`、`results/georeference_review.json`。
- 离线复跑：在本问唯一执行根运行`track_b/.venv/bin/python track_b/research/q4/round2/scripts/build_search_aoi.py`；300dpi裁切图和配置已保存，不需联网。

已实际打开原PDF第6页/完整图注、Fig.1c和经度刻度裁切。用85°24′/28′/32′E的三个经度轴约束，以及28°20′/16′N两个纬度轴约束，拟合轴分离线性关系。刻度只约束一个轴，不冒充完整二维地面控制点；无独立证据检验旋转、剪切或原地图投影。

仅用两端经度刻度预测中间刻度，等效留出误差为20.85 m；纬度只有两个刻度，不能做独立留出，也不能把零拟合残差当精度。±5个渲染像素的敏感性另列。原地图定位精度、基准偏移和地物识别误差仍未知，渲染分辨率不是原图空间分辨率。

假设印刷经纬刻度可暂按WGS84/CRS84解释，仅用于检索；原基准/投影未核实。根据图中的源区符号中心、Chhochen/Lende交汇和Gyirong Port符号中心，取UTM45N包络并向各边扩展2 km作为检索余量。此2 km是研究者选择的搜索范围，不是置信半径或已证实的误差上界。

AOI外包经纬范围约为W85.35717、S28.26106、E85.54598、N28.34920；UTM面积约175.36 km²。它是`search_only`，不能用于释放范围、失稳面积、体积、真实传播距离或独立验证。所有几何为事后文献图重建候选，不能进入灾前信息集。

本轮共同基线`76ee1532cb2acf36fb82c5f4749a4288507dfcc8`，冻结清单SHA-256`c10cb6a30ea728ffbbd3a64d5f10fe00981bdf1d4b966ec37506dcef02e5d29d`。源PDF、裁切、配置、脚本哈希均在证据JSON中绑定。后续源区描边、口岸对象与河道候选另行交付，不需阻止Q2的有限场景搜索。
