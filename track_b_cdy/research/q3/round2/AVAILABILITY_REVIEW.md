# Q3 第二轮历史可用性：固定 GFS 18UTC f009

状态：有界补证完成；首次历史公开可用时间仍未知。AI 辅助：OpenAI Codex，2026-10-24。

**已补齐当前对象修改时间及版本关联证据；`available_time` 仍为 null，灾前发布门禁仍为 `unknown_not_eligible`。这些证据尚不能认证历史实时回放。**

## 唯一审核对象与已有语义

- 起报：2026-08-25T18:00:00Z。
- 文件：`gfs.t18z.pgrb2.0p25.f009`；有效时刻：2026-08-26T03:00:00Z。
- 精确对象：[NOAA GFS S3 key](https://noaa-gfs-bdp-pds.s3.amazonaws.com/gfs.20260825/18/atmos/gfs.t18z.pgrb2.0p25.f009)。仅 HEAD，未 GET GRIB 正文。
- 复用冻结首轮六条 Range HTTP 记录、原索引及已处理 summary；不重解码 GRIB，不扩大起报或时次。有效时刻晚于目录代理时刻本身不等于泄漏，关键仍是该信息是否在预测发布前实际可得。

## 实际证据及最强解释

| 证据 | 实际结果 | 可以支持什么 |
|---|---|---|
| 精确对象 HEAD | 200；Length=544,955,433；Last-Modified=2026-08-25T21:38:07Z | 当前服务器报告该对象修改时间；不是首次业务发布证明 |
| 对象 ETag | `854b49133eff0621b43f59c19b3e1c66`，同冻结六条 Range 记录一致 | 加强本次元数据与既有读取对象的关联；不证明8月完整历史版本与访问权限 |
| VersionId 响应 | 未返回 | 本次响应无值；不能据此宣布存储桶禁用版本管理 |
| 对应索引 HEAD／GET | 40,473字节；Last-Modified=21:38:34Z；正文 SHA-256 同冻结索引一致 | 当前索引与首轮索引逐字节一致；索引可读不证明8月GRIB首次公开时间 |
| 首轮最早已存成功 Range 接收 | 2026-10-24T03:35:01.714773Z | 至少到这次10月接收时已有公开字节访问；没有提供灾前历史上界 |
| [GDEX 指定日期目录](https://gdex.ucar.edu/datasets/d084001/filelist/20260825/)的唯一目标条目 | `gfs.0p25.2026082518.f009.grib2`，显示519.71 MB、Date Archived=2026-08-27 | 该归档渠道报告的日期；未核准时区／时分秒，也未核对完整二进制同一性 |
| [NCEP 当前生产状态](https://www.nco.ncep.noaa.gov/pmb/nwprod/prodstat/) | 当前状态与滚动平均计划 | 不能替代2026-08-25这一实际运行的完成／发布日志 |

对象 HEAD 请求开始为2026-10-24T06:01:06.770729Z，接收结束06:01:08.396003Z；其他请求 UTC、版本元数据、URL、阅读范围和 SHA-256 均见 [source_register.json](results/source_register.json)。GDEX 页面虽包含其他文件，本轮仅解析指定 f009 条目，没有跟随其他条目或下载数据。

[AWS HeadObject 官方定义](https://docs.aws.amazon.com/AmazonS3/latest/API/API_HeadObject.html)说明 HEAD 返回对象元数据而无正文；Last-Modified 是对象修改属性，ETag 是不透明标识。其响应没有提供该对象何时首次对公众开放的历史记录。本轮实际读取相应官方 Markdown 快照中的 HEAD、Last-Modified、ETag、VersionId 定义；没有假定 ETag 必为文件 MD5。

## 历史边界与门禁

本轮没有建立灾前首次公开可用的有效上下界。21:38:07Z 不能直接写成 `issue_time`／`available_time`，也不能据起报时刻相减宣布实际发布延迟3小时38分。GDEX 的8月27日归档日期不能替代 NOAA 业务渠道的首次可用时间，也不证明此前不可用。10月成功读取只给出10月观察上界。

机器证据链 [gfs_f009_availability_chain.json](results/gfs_f009_availability_chain.json)保留：

- `forecast_reference_time` 和 `valid_time` 为已知；本轮没有设定新的模拟 `issue_time`。
- `available_time=null`、`available_time_verified=false`。
- `historical_first_public_access_lower_bound=null`、`historical_first_public_access_upper_bound_before_event=null`。
- 灾前门禁 `unknown_not_eligible`；`real_coverage=null`。

本轮可以采用对象修改元数据、ETag关联和索引一致性，首次历史可用仍为 unknown。若后续授权继续补证，只需寻求这个精确 key 的历史分发／对象创建记录、对应版本证据及当时公开访问证明，并核对时间语义；不需再下全球GRIB或扩扫时次。若记录无法取得，可以维持未知并限制为方法示范／情景回放，不升级为已验证业务预报。

首轮72条延迟情景及20项机械检查保持原样；本轮未重跑，它们也不能替代真实历史可用证据。
