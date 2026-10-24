# 独立地理来源有限核查

2026-10-24 UTC。完成3次定向搜索、4次官方URL HTTP尝试（其中尼泊尔官网两次TLS证书链失败）；仅保存元数据，没有下载河网、DEM或影像。完整请求时间、HTTP状态、响应字节数和SHA-256见 [independent_geography_review.json](independent_geography_review.json)。

可采用 [HydroRIVERS官方产品页](https://www.hydrosheds.org/products/hydrorivers) 作为独立河网产品的说明：它从15角秒基础栅格提取线网络；该分辨率不能当成本地定位精度。本轮读取了产品页和 [HydroSHEDS FAQ](https://www.hydrosheds.org/faq)，未取得或匹配AOI内河段。FAQ的局地适用性/命名限制也不能替代本地核查。产品说明不等于已取得真实河道。

中国海关单次定向搜索未得到可采用官方定位页面；这不证明资料不存在。[尼泊尔Rasuwagadhi移民办公室官网](https://rasuwagadhi.immigration.gov.np/) 仅取得搜索索引的地名线索，直接读取失败，没有原始响应字节可哈希，也没有验证坐标。不能将办公室、口岸设施和桥位自动视为同一保护对象。

因此，五个对象的独立坐标/几何、相应CRS、精度和观测时间仍为 **unknown / not obtained**。现有五对象继续保留为同一JMS图的事后重建候选；同图内部一致性不构成独立定位。没有修改候选几何或搜索AOI。
