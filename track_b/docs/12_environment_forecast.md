# 阶段3：独立环境与历史预报最小样本

日期：2026-10-23。环境与GFS样本处理均已实际执行；其余包的整体交接见阶段3综合报告。

## 1. 环境的真实状态

项目独立环境为`track_b/.venv/`，Python 3.12.14，使用Codex提供的Python创建标准venv。本轮没有修改系统Python或已有Anaconda环境。`.venv/`沿用仓库忽略规则，不是研究数据或提交附件。

依赖意图：[requirements.in](../requirements.in)；实际安装的精确版本锁：[requirements-lock.txt](../requirements-lock.txt)。锁包含全部传递依赖及pip；只在本机macOS x86_64 / Python 3.12上验证，不声称跨平台二进制相同。

真实导入成功：numpy、pandas、pyarrow、openpyxl、xarray、h5netcdf/h5py、rasterio、pyproj、shapely、geopandas/pyogrio、cfgrib/ecCodes、matplotlib等。`pip check`无依赖冲突；具体原生GDAL/PROJ/GEOS/ecCodes版本见[环境记录](../audit/stage3/environment.json)。没有安装尚未选定的全部建模或仿真软件。

## 2. 重建与运行

首次创建本机环境：

```bash
/Users/maxchen/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m venv track_b/.venv
track_b/.venv/bin/python -m pip --isolated install --index-url https://pypi.org/simple --only-binary=:all: -r track_b/requirements-lock.txt
track_b/.venv/bin/python -m pip check
```

换机器时先提供Python3.12，再用该解释器创建同名venv；上面的绝对路径只是当前机器事实。若平台缺少某个锁定wheel，应记录差异并重新验证，不能悄悄改锁后仍称同环境。

```bash
track_b/.venv/bin/python track_b/scripts/capture_stage3_environment.py
track_b/.venv/bin/python track_b/scripts/prepare_forecast_sample.py
```

环境记录脚本检查当前运行在隔离venv内、`pip check`为0、`freeze --all`与锁完全相同；导入成功之外，真实格式读写由各数据管线和集成检查另行验证。

## 3. GFS实际取到了什么

- 来源：[NOAA官方登记的公开S3](https://registry.opendata.aws/noaa-gfs-bdp-pds/)。产品命名与时效规则依据[NCEP官方目录](https://www.nco.ncep.noaa.gov/pmb/products/gfs/)。
- 起报时刻：`2026-08-25T18:00:00Z`，提前9小时的有效时刻为`2026-08-26T03:00:00Z`。
- 下载方式：从公开`.idx`定位，HTTP Range读取6条完整GRIB2消息，而不是下载544,955,433字节的整个预报文件。每条保存响应状态、字节范围、ETag、抓取时刻、文件SHA-256；核验GRIB长度与首尾标记。
- 6条完整消息合计 **3,943,234字节**，是少量全球字段，随后在本地裁剪AOI；网络获取并非服务端区域裁剪。
- 测试AOI：85—86E、28—29N。保留原0.25°网格中心，得到每变量5×5格；没有插值或降尺度。
- 原始字段及单位：2m温度K、2m相对湿度%、10m风分量m/s、两种累计降水kg/m²。不把表面气象场当高海拔源区的直接观测。

| 字段 | ecCodes核验的时效 | 处理 |
|---|---|---|
| 2m温度、相对湿度、10m风u/v | 起报后第9小时的瞬时场 | 保留源单位和层次属性 |
| APCP 6—9h | 起报后6至9小时累计，UTC 8月26日00:00—03:00 | 与0—9h分别命名，不相加、不当作瞬时雨强 |
| APCP 0—9h | 起报至第9小时累计，UTC 8月25日18:00—26日03:00 | 保留累计起止时刻 |

每条消息用ecCodes检查参考/有效时间、层次、单位、startStep/endStep及小时单位，再用xarray的cfgrib后端真实解码。裁剪结果写入NetCDF4/h5netcdf并回读，所有数值逐项相同。结构化证据见[summary.json](../data/processed/forecast_sample/summary.json)。

## 4. 不能由通路通过推出的内容

起报早于事件，但**当时实际业务发布时间尚无证据**。f009有效时刻稍晚于USGS目录参考时刻；这不妨碍它作为预报目标时刻，但能否用作某个预警发布时刻的输入，仍取决于当时的数据可得时间。

当前下载时刻和S3对象修改时刻不能代替原业务发布时间；后来的归档、修订也应与实时版本分开。此样本尚未检验历史档案完整性、模型在本地的误差、发生概率或区间覆盖率。

0.25°网格无法解析约4km的冰川小网格或狭窄沟谷；25个AOI格是环境背景样本，不能被插值成25个独立灾害样本，更不能直接支持分钟级现场预警。

## 5. 软件依据与AI辅助

采用的接口依据：[xarray I/O后端文档](https://docs.xarray.dev/en/stable/user-guide/io.html)、[ECMWF cfgrib](https://github.com/ecmwf/cfgrib)、[ECMWF ecCodes Python](https://github.com/ecmwf/eccodes-python)、[Rasterio安装与wheel说明](https://rasterio.readthedocs.io/en/stable/installation.html)。本轮记录实际版本，后续变更须重新验证受影响的管线。

本脚本、环境配置和报告由OpenAI Codex辅助生成与验证，精确模型标识待队员补齐；不替代队员核心建模和人工采用记录，见[AI_USAGE](../AI_USAGE.md)。
