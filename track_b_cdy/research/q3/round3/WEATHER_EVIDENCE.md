# Q3 第三轮天气输入证据与接口

AI辅助：OpenAI Codex，2026-10-24；科学采用待队员审查。登记实验协议先于解析和计算；本包只负责天气获取、原生字段解析和质量诊断，逐发布时刻的模型回放由 Q3 主任务另行计算。

本轮实际获取 NOAA GFS 三个起报（2026-08-23、24、25 的18:00 UTC），每个起报保留 f000–f096 的原生逐小时2米温度及 f001–f096 的地面全程累计总降水。保留原始 0.25° 网格，裁取85–86°E、28–29°N的25个格点。没有把三小时产品插值为小时产品，也没有下载整份多变量全球文件：按索引仅下载所需完整 GRIB2 字段，再本地裁切。原始缓存属于 Q3，位置为 `/Users/maxchen/Documents/MathorCup/research_cache/round3/q3/weather/`。

[NOAA产品目录](https://www.nco.ncep.noaa.gov/pmb/products/gfs/nomads/)列明0.25°文件命名、00/06/12/18 UTC起报和小时产品；[NOAA字段目录](https://www.nco.ncep.noaa.gov/pmb/products/gfs/gfs.t00z.pgrb2.0p25.f003.shtml)用于核对TMP、APCP与层次/单位。这些当前文档不证明2026年8月的准确软件语义版本或首发时刻。运行版本以实际GRIB元数据、精确S3 key、ETag和SHA-256绑定，不从[公开数据登记页](https://registry.opendata.aws/noaa-gfs-bdp-pds/)中较早的软件升级说明推定当前运行版本。三个文档的本地快照和实际阅读范围见 `inputs/weather/docs/sources.json`。

## CSV接口与时间口径

- `inputs/weather/gfs_hourly_source_grid.csv`：3×97×25=7,275行；`forecast_reference_time`、`valid_time`、`lead_hours`、原始经纬度、2m温度K、降水原始累计及小时差分。原生GRIB为总降水水当量，kg m^-2按1:1换为mm水当量；不自动区分降雨与降雪。
- `inputs/weather/gfs_hourly_summary.csv`：3×97×2=582行；`space_object=aoi_unweighted_mean`是25格的等权均值；`proxy_nearest_grid_28.25N_85.5E`是原USGS目录中心28.271°N、85.515°E的最近格点。中心来源为冻结的 `track_b/data/external/event_remote/runs/20261024T034202Z/raw/usgs_event.json`。该格点并非已核验的首次机械启动源区坐标。
- f000不对应一个先前的预测降水时段，小时降水为空。该行全程累计0仅为空区间的数学边界。
- f001及以后，每小时增量为同一起报的全程累计之差：P(0,h)−P(0,h−1)。起止边界明确为(reference+h−1, reference+h]。不将0–h与桶累计叠加。f024/f048/f072/f096在索引中可能用day表示，读取时兼容，并以GRIB实际startStep=0、endStep=h、stepUnits=hour复核。
- 各时次独立打包的累计量可能有小负差。`precipitation_increment_raw_mm`保留负值；用于模型的`precipitation_increment_mm`在这些格点为空，并带`negative_difference_missing`标记；没有静默截零。AOI均值遇到该情况按非缺测格点计算，所以使用者应同时检查格点QC，不能将缺测格点均值冒充25格完整均值。
- CSV中`issue_time`为空，因为原始天气集合尚未指定模拟发布；Q3回放生成时另赋值。全部`available_time`为空。`source_product_version`是精确产品key，ETag/字节范围/哈希及获取UTC在`results/weather_sources.json`。

## 可用性和三轨实验边界

第二轮固定f009审核未能建立历史首次公开可用，本轮也没有得到8月首发/访问日志。当前206响应、ETag、Last-Modified和成功下载只支持当前对象及版本关联。因此 `historically_available`已认证记录仍为0，不能以本包宣称灾前业务预报成功。

实际天气值可以用于`assumed_latency`的0/3/6/9小时起报后可用假设。主回放按每次发布选择不晚于信息截止且假定已可用的最新起报；实际历史首发未知必须始终保留。f096扩展用于减少延迟及滚动发布的72小时尾端缺口；最新起报仍可能在切换前出现尾端不足，保持缺失，不能外推补造。`ideal_weather`使用未来实测时还须明确其预见性及原观测口径；实际GFS是模式预报，不能改称未来实测。

## 本地区域站的理想输入

`inputs/weather/local_weather_case.csv`从冻结公共小时表截取2026-08-22至29 UTC的192个小时标签。温度保留原严格QC=0视图；降水只保留有限且非9999.9的原值。192小时中二者各121个有值，连续有效温度止于2026-08-27T00:00Z，后续缺测没有插补。

该站为区域背景站，非源坡面传感器。UTC由原处理中UTC+8假设换算；来源为同名外部元数据，下载文件同一性尚未哈希核准。原时间标签是瞬时/起始/终止/中心尚未证实；降水没有QC列，累计时段未知。本文件保留`precipitation_header_mm_raw`，并令累计边界为空，不能直接把该字段当成已验证一小时水量。局部未来温度可作标明时间与代表性假设的`ideal_weather`输入；不把不足72小时的窗口补成完整窗口，也不把理想天气实验当作实证预报性能。

## 校验与复跑

脚本保留原44包环境，未安装新包。下载命中缓存时核对URL、字节范围、缓存路径、字节数、HTTP状态、Content-Range和SHA-256；每个T/APCP配对核对同一对象ETag。解码核对变量、层次、起报、有效时刻、累计边界、单位和25格空间范围。

联网补齐缓存并复跑：

```bash
cd /Users/maxchen/Documents/MathorCup/worktrees/track-b-q3
track_b/.venv/bin/python track_b/research/q3/round3/scripts/acquire_weather.py --collect --workers 8
```

缓存完整后的离线重建：

```bash
cd /Users/maxchen/Documents/MathorCup/worktrees/track-b-q3
track_b/.venv/bin/python track_b/research/q3/round3/scripts/acquire_weather.py
```

数值摘要见`results/weather/summary.json`，逐消息元数据见`decoded_metadata.json`，负差诊断见`precipitation_difference_qc.json`。25个空间格点、291个起报/有效时刻组合、各滚动发布都不构成独立灾害事件。本包没有局地天气误差校准，也没有对首次机械启动真值进行采用。

本次实际负累计差为0。三个起报在AOI等权均值上的96小时累计分别为40.7175、30.2、31.155 mm水当量；相应全程温度范围约6.08–12.81、6.36–12.68、6.49–11.82°C。这些为模式区域平均的描述值，不是源坡面观测或局地临界温度。已有8月25日18Z f009的2m温度与0–9h累计原消息同本轮逐字节一致（SHA-256分别`36c0bab95887d7c0395bd2d2e5cf59ff5323e7bbaa1fa9b5b8e6f86bf104bba2`、`342d34c3d44c28df5cf08ac60874029b37bda6c58d08ed9cb864c98381589991`），该一致性仍不能证明历史首次可用。
