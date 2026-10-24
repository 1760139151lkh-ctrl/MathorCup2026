# 第三轮本地 Linux 求解器运行时

本目录仅为项目外的运行缓存；未修改主仓库或四个工作树。运行位置为本机 Docker Desktop，未使用远程服务器。

## 已固定源码

- r.avaflow 4.0 Revision 7，20250902：官方源码包 SHA256 `8301b4804f45e228633aa823caba4a3387a47f8bd143cf5569fdc5a9f95ad3a7`。源码头声明 GPL >=v2，随包 LICENSE 为 GPLv3 文本。目录 `sources/r.avaflow.40G/`。
- D-Claw 发布标签是 `1.0.0`（没有 v 前缀），提交 `7d48663bbed916372ba18732627c52043afb109f`，BSD 3-Clause。目录 `sources/dclaw-1.0.0/`。
- Clawpack `v5.11.0`，提交 `285b7de9837702276213b7deb040495adc60c4cc`，所用五个子模块固定在 `source_versions.json`。已编译 D-Claw，无需用主分支替换。
- 官方 Cascadia 原始训练包 `sources/Cascadia_r.avaflow40G.zip`，SHA256 `564a9920c3036431915eaa5136f57c5bb720e7b980bc7a2de32998e855d78a9e`，4845673 字节，解压到 `benchmarks/`。该训练包HTTP修改日期是2024，源码是2025；参数以固定源码的接口和实际验证为准。

## 镜像和环境

冻结镜像名为 `mathorcup-r3-solvers:r3-rev7-dclaw1-20261024`，镜像已生成并从新实例实际运行两个模型，ID为 `sha256:a725b54f17797c8d4ffd2ac94a02b4a613115832c0633eb26135b309d5336f29`。优先按ID或上述唯一标签运行。

容器内：Ubuntu22.04，GRASS GIS7.8.7，GDAL3.4.1，gfortran11，Python3.10.12，NumPy1.21.5，SciPy1.8.0，Matplotlib3.5.1，Clawpack5.11.0；R及terra/raster/ROCR可导入。完整包版本在 `dpkg_packages.txt`。

安装源码 `/opt/sources/r.avaflow.40G`；GRASS插件 `/opt/grass-addons`；Clawpack `/opt/clawpack`，其中 D-Claw `/opt/clawpack/dclaw`。已编译可执行文件 `/opt/clawpack/dclaw/examples/gully/xdclaw`。

正式研究建议每次运行挂载本问 round3 到 `/work`，公共输入另挂为只读。以下路径仅为示例，请用实际本问工作树和本轮目录：

```bash
/usr/local/bin/docker run --rm --cpus=3 --memory=5g \
  -v /Users/maxchen/Documents/MathorCup/worktrees/track-b-q4/track_b/research/q4/round3:/work \
  -v /Users/maxchen/Documents/MathorCup/worktrees/track-b-q4/track_b/data:/inputs:ro \
  -w /work mathorcup-r3-solvers:r3-rev7-dclaw1-20261024 \
  grass --tmp-location EPSG:32645 --exec bash /work/scripts/run_case.sh
```

EPSG只是展示调用格式，实际模型位置、坐标和基准必须由Q4决定；本次Cascadia环境检查使用XY无投影的官方通用地形。不同模型串行运行可避免争用Docker约8GB内存；本轮未改Docker全局资源设置，未改用户其他容器。

D-Claw运行时须保留 `CLAW=/opt/clawpack`、`PYTHONPATH=/opt/clawpack`、`CLAW_PYTHON=python3`、`FC=gfortran`。make前用 `bash -lc 'cd ... && make ...'`，确保实际cwd/PWD正确。输入及输出在自己的case目录，求解器在固定的opt路径。

## 已观察的兼容问题

- GRASS的 `g.extension` 即使本地安装也需要svn；已经补齐，安装日志保留。
- Rev7在线说明与实际Python接口存在差异：**单相必须使用 `hrelease=`**；`hrelease1=`用于多相组分，单相仅传该参数会被拒绝。以固定源码与接口XML为准。
- 包装脚本遇到参数错误或数值失败仍可能退出码0。必须同时读取 `*_files/*_nout1.txt` 第二行success，并检查结果有限性、非负性和预期时间覆盖，正式研究另做守恒和收敛。
- D-Claw官方gully的 `make input` 绘图阶段因 `from pylab import *` 覆盖 `colormaps` 名称，报 `ColormapRegistry has no attribute white_red`。原始拓扑生成函数 `setinput.maketopo()`可直接调用，避免绘图入口；没有修改求解器物理源码。
- Docker Hub元数据连接超时，BuildKit拉取路线未用来完成构建。使用本机已有且有digest记录的Ubuntu22.04镜像，官方apt包通过HTTPS缓存校验，再由apt安装。Docker原生commit/export客户端长时间无结果后被取消；原commit随后实际生成了含Ubuntu基础层的可运行镜像（见history与RootFS记录）。备份路线保留容器静态rootfs tar/gzip，已取消多余导入客户端。原20261024标签曾被这些尝试使用，正式实验固定ID或唯一r3-rev7-dclaw1-20261024标签。未发布远端。完整rootfs归档与校验为 runtime_static_rootfs.tar / rootfs_validation.json。

## 检查范围

`runtime_checks.json`记录系统、工具、接口XML、二进制与依赖导入检查；`numerical_environment_checks.json`记录实际模型执行。r.avaflow使用Cascadia20米格网5秒的环境算例，成功标记1，6帧流深有限非负。

这些检查用于证明安装和I/O可用，不能充当事件重建、参数标定、独立验证或完整模型竞争结果。Q4须完成本轮的标准算例、真实地形实验、守恒和收敛比较。

## 文件证据

`source_versions.json`、`sources_manifest.json`、`benchmarks_manifest.json`保留来源、实际审读范围、版本与哈希；`apt_download_manifest.json`为并行获取部分，其余包由apt原始下载并安装。`install_packages*.log`、`install_subversion.log`、`build_ravaflow*.log`、`build_dclaw*.log`和`selfcheck_*.log`保留成功与失败尝试。
