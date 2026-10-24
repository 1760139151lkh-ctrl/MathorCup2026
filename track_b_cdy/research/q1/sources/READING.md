# Q1 新增来源与实际读取范围

日期：2026-10-24（America/New_York）。本轮只做有界证据核查，下载文件均在本问 sources，未替换任何公共输入。获取时间不等于资料在灾前可得时间。逐项URL、HTTP结果、大小与SHA-256见 access_log.json。

| 对象 | 实际访问与阅读范围 | 能支持与不能支持 |
|---|---|---|
| TPDC数据详情 UUID 5b09afd1-d11b-4150-a291-50f0484dddf1 | web工具直接详情/DOI访问失败；HTTP实际取得1927字节前端HTML壳；官方搜索索引可见同名摘要 | 可定位原发布入口，不能声称已阅读官方详情全文或下载认证原版 |
| WaterNet同名元数据 | web正文抽取中阅读数据摘要、站点/时区/QC说明、引用与下载链接；保存HTML原响应231361字节 | 数据发布镜像声明区域站位置、UTC+8及适用限制；未证明本地24文件全版本一致，也未说明小时积分边界和FLUX完整处理 |
| WaterNet FLUX 2026 单文件 | 按元数据给定URL取得完整CSV2228464字节；表头有四个候选QC字段；后续逐时逐列对比结果见 results/remote_flux_comparison.json | 可提供该子文件匹配和QC来源审核线索；不能替代QC语义核验、其余变量QC或实际历史可用性 |
| 既有本地来源汇编 | 本轮读取相关条目和已存的变量字典、政策、时序报告；未重新访问汇编内所有论文链接全文 | 可恢复既有研究边界；不把二手条目读取登记为新全文核验 |

WaterNet 元数据原始字段有 DOI 拼写差异：标题区域为10.1888，引用段为10.11888；本轮保存原响应，不自动修订公共引用。继续以原TPDC/DOI解析核实为后续动作。

- TPDC入口：https://data.tpdc.ac.cn/zh-hans/data/5b09afd1-d11b-4150-a291-50f0484dddf1
- DOI候选：https://doi.org/10.11888/Atmos.tpdc.303600
- WaterNet元数据：https://gwfnet.net/Metadata/Index/T-2026-08-28-p1f3e5qIqTEyibfPAp3smBeA
- 有界下载：https://waternet.ca/fileserver/T-2026-08-28-p1f3e5qIqTEyibfPAp3smBeA/QC_FLUX_JILO_2026_hourly.csv
