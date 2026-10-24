# Q4 第三轮复跑说明

状态：**原生区域31完成＝30必跑＋1诊断，7个材料不适用代理明确未运行，reduced34项区域计算已闭合；原生持续写入进程已结束。论文主展示建议单相120m sf0，孔压／复合相作结构挑战；全部科学接受标记false，科学采用待队员审视**。本文件根据脚本、固定环境和真实执行记录整理，分别记录原完整研究、两项安全wrapper科学复跑、只读完整性检查及launcher帮助检查。最终采用的run ID、原生配置、实际终时和输出哈希，以最终`HANDOFF.md`、运行表、bundle和manifest为准。

## 1. 执行位置、输入保护和检查

唯一当前工作树为 `/Users/maxchen/Documents/MathorCup/worktrees/track-b-q4`，分支 `codex/track-b-q4-r3`。所有命令从该目录执行；聊天关联的父目录不是执行根。共同基线 `904d7257b899b9f71d1ac9e0eab7479e459eab52`；preparation `de790034cf302de58e69329dbe288aad269a359c`。冻结清单含725文件，SHA256为 `fd755fab38df285a67c986026859be5f635a314aa3f79f2d247a2626246c3a53`。

```sh
cd /Users/maxchen/Documents/MathorCup/worktrees/track-b-q4
git branch --show-current
track_b/.venv/bin/python -V
track_b/.venv/bin/python track_b/scripts/stage4_workspace.py verify \
  --round round3 --question q4 \
  --expected-root /Users/maxchen/Documents/MathorCup/worktrees/track-b-q4 \
  --expected-base 904d7257b899b9f71d1ac9e0eab7479e459eab52
```

原 `track_b/.venv` 为44包锁定环境，对照 `track_b/requirements-lock.txt`；本轮不得向该环境安装新包。上述标准验证检查隔离目录、Git基线、冻结输入、依赖和标准通路，并只更新本问运行记录。启动时已经执行过 `--pristine` 并通过，原启动记录保存在 `sources/startup_workspace_verification.json`；已有成果后不要再把 `--pristine` 当收尾命令。历史轮完整性按对应历史Git ref核验，不用本轮合法升级的共享helper倒查旧轮。

`exports/geometry_bundle.json`、`exports/geometry_v1/` 以及 `inputs/q2/`、`inputs/q3/` 是版本化交接输入。先核对各 bundle 的逐文件 path/bytes/sha256，再引用。消费者复制件和上游原字节保留；不能直接读取他问活动目录代替已分发输入。以下只读核对示例支持 repo-relative 和绝对缓存路径，不包含清单自项：

```sh
track_b/.venv/bin/python - <<'PY'
from pathlib import Path
import hashlib, json
root = Path.cwd()
r = root/'track_b/research/q4/round3'
bundles = [r/'exports/geometry_bundle.json'] + sorted((r/'inputs').glob('**/bundle.json'))
for bundle in bundles:
    packet = json.loads(bundle.read_text())
    for rec in packet.get('files', []):
        p = Path(rec['path'])
        if not p.is_absolute(): p = root/p
        assert p.stat().st_size == rec['bytes'], (bundle, p, 'bytes')
        assert hashlib.sha256(p.read_bytes()).hexdigest() == rec['sha256'], (bundle, p, 'sha256')
    print('verified', bundle.relative_to(root))
PY
```

所有Git新成果只写本问 `round3/`；大型下载、局部环境和过程场只写 `/Users/maxchen/Documents/MathorCup/research_cache/round3/q4/` 的所属子目录。共享 `/Users/maxchen/Documents/MathorCup/research_cache/round3/runtime/` 只读，不重复编译、改方程或全局安装。仅本地计算，不使用远程服务器。

**覆盖规则**：下列生成／计算命令是本轮实际使用的入口，部分脚本具有固定输出目录，重复执行会重写case、日志、结果或索引。已有冻结交付不在原位置重跑；须先由主参谋建立新版本输出／隔离副本并固定输入与脚本哈希。没有 `--output-root` 的脚本不能假称已支持该选项。单纯核查既有结果优先校验哈希并读取字段。

## 2. 空间取得、标准化和补证顺序

实际脚本与依赖顺序如下；下载和源索引在 `q4/spatial/` 与 `sources/spatial_*.json`，公共几何初始版本不被后续影像／OSM分析覆盖。

| 顺序 | 脚本 | 作用及输出边界 |
|---|---|---|
| 1 | `spatial_acquire.py` | Copernicus原tile、S2目录及Overpass请求；保存成功和失败响应记录 |
| 2 | `spatial_build.py` | UTM45N 60／120m共同格网、二值源、P1—P3及terrain bundle；v1已冻结 |
| 3 | `spatial_compare.py` | 新产品与原供应DEM同格网比较；不将差异解读为时序高程变化 |
| 4 | `spatial_optical_osm.py`、`spatial_auxiliary_acquire.py` | 三景TCI/SCL、合法OSM直接接口及同产品C1辅助资料；认证失败入口关闭，原失败保留 |
| 5 | `spatial_optical_read.py`、`spatial_osm_read.py`、`spatial_edge_review.py` | 实际像元质量、独立机器几何和局部接河候选；不把目录足迹等同已读像元 |
| 6 | `spatial_radiometry.py` → `spatial_spectral.py` | 同product URI辐射转换检查后再做有效像元光谱筛选；保留被拒绝的重复offset计算 |
| 7 | `spatial_validate.py` | 冻结v1、格网／几何／像元分母／已查看图及缓存哈希检查 |

上述脚本的实际历史调用均为 `track_b/.venv/bin/python track_b/research/q4/round3/scripts/<script>.py`。多数会写本轮空间结果和来源索引，不能无版本隔离地再次执行。公共源tile可按已有哈希复用；HTTP范围读取只绑定实际派生窗口，完整远端对象bytes/hash未知时继续保留null。

当前 `spatial_build.py` 已增加一个真正可用的安全复跑入口：冻结v1存在时，默认拒绝覆盖。以下仅在指定目录尚不存在时生成独立副本，不发布／替换原几何包：

```sh
track_b/.venv/bin/python track_b/research/q4/round3/scripts/spatial_build.py \
  --output-root /Users/maxchen/Documents/MathorCup/research_cache/round3/q4/spatial/replay_geometry_run01
```

新资料或几何改变须另登记版本和哈希，由主参谋分发。光谱筛选、OSM和文献路线的协议版本、观测时间及历史可用时间分别保存；OSM修改时间不是地物观测时间。

## 3. 独立一维／二维基线与局部Numba环境

登记在 `config/reduced_protocol.json` 和 amendment01；共同条件、数值缺陷与34个区域情景见 `REDUCED_MODELS.md`。该包已冻结，入口 `results/reduced_delivery_index.json`，SHA256 `cd82c52cc772ed7702a6f4452f4bfbbe5c9a092bbbeeed46d356d09709a4a7dc`。不要通过再次运行报告或验证脚本覆盖其冻结时间戳／哈希。

本机实际成功运行的独立解释器是：

`/Users/maxchen/Documents/MathorCup/research_cache/round3/q4/reduced/venv/bin/python`

Python3.12.14，Numba0.62.1、llvmlite0.45.1、NumPy2.3.5；其余科学依赖通过 `.pth` 在**局部site-packages之后**引用原44包环境。`config/reduced_environment.lock` 是实际freeze，`reduced_environment.json`记录路径与版本。曾尝试Numba0.68.0，但llvmlite源码构建缺LLVM而失败；没有为此安装工具链，该失败不算执行结果。

本轮实际安装命令固定Numba0.62.1和NumPy2.3.5，解析得到llvmlite0.45.1；以下复建命令将该解析结果也显式固定。既有环境已可直接使用；独立重建选择新的 `q4/reduced/rebuild_env01`（若已存在则换新名字），按实际lock核对。`PIP_CACHE_DIR`指向本问缓存，原venv不执行pip install：

```sh
track_b/.venv/bin/python -m venv /Users/maxchen/Documents/MathorCup/research_cache/round3/q4/reduced/rebuild_env01
PIP_CACHE_DIR=/Users/maxchen/Documents/MathorCup/research_cache/round3/q4/reduced/pip_cache \
  /Users/maxchen/Documents/MathorCup/research_cache/round3/q4/reduced/rebuild_env01/bin/python -m pip install \
  --only-binary=:all: numba==0.62.1 llvmlite==0.45.1 numpy==2.3.5
/Users/maxchen/Documents/MathorCup/research_cache/round3/q4/reduced/rebuild_env01/bin/python - <<'PY'
from pathlib import Path
import sysconfig
bridge = Path(sysconfig.get_paths()['purelib'])/'original_scientific_stack.pth'
bridge.write_text('/Users/maxchen/Documents/MathorCup/worktrees/track-b-q4/track_b/.venv/lib/python3.12/site-packages\n')
PY
```

**当前建议用安全隔离wrapper复跑** `scripts/replay_reduced.py`：原四个科学源码不改，导入后仅在内存重定向结果R／过程场C；输出必须是本round3内不存在的新目录，cache-name必须是新单段名称，缓存落在 `q4/replays/`。它复制并核验共同格网、路径和精确历史目标表 `spatial_targets_v2_initial.csv`（SHA256 `96202126426c50fdebe5d72ddf74bd443f531a77c77db094d0c8fe739dc86b98`），避免后加entity_id的表结构改变冻结后处理的输入字节；当前脚本也复制环境lock/json。

```sh
# 只做安全准备／输入哈希检查，不启动任何求解；这将占用这两个新目录名。
/Users/maxchen/Documents/MathorCup/research_cache/round3/q4/reduced/venv/bin/python \
  track_b/research/q4/round3/scripts/replay_reduced.py \
  --output results/replay_PREP_NEW --cache-name PREP_NEW --mode all --prepare-only
# 真正区域复跑须用另一个NEW名字；all表示全部1D+2D区域情景，不包含数值基准。
/Users/maxchen/Documents/MathorCup/research_cache/round3/q4/reduced/venv/bin/python \
  track_b/research/q4/round3/scripts/replay_reduced.py \
  --output results/replay_REGION_NEW --cache-name REGION_NEW --mode all
# 基准单独生成新包；--select可在区域模式选择如2d_ref_120m，不能混称整包完成。
/Users/maxchen/Documents/MathorCup/research_cache/round3/q4/reduced/venv/bin/python \
  track_b/research/q4/round3/scripts/replay_reduced.py \
  --output results/replay_BENCH_NEW --cache-name BENCH_NEW --mode benchmarks
```

本窗先实际做过wrapper的 `--prepare-only`；随后又实际复跑两个既有参考配置，命令如下。9项复制输入校验、两个配置的全部物理summary（wall time除外）及全部数值场数组与原交付逐项完全相等；原93+60项包／缓存哈希仍通过。证据为`results/replay_execution_comparison.json`与新目录的`replay_record.json`；1幅派生检查图也已真实打开。它验证安全wrapper真正能执行科学计算，**不是再次跑完34项或13种基准，也不改变原路线区域精度不合格的判断**。

```sh
/Users/maxchen/Documents/MathorCup/research_cache/round3/q4/reduced/venv/bin/python \
  track_b/research/q4/round3/scripts/replay_reduced.py \
  --output results/replay_execution_check --cache-name execution_check_v1 \
  --mode all --select 1d_P1_ref,2d_ref_120m
```

上面目录已经占用，重放须换新名字。新增复制项以最新`replay_record.json/copied_inputs`为准，不沿用最初准备检查的计数。wrapper写新包，不运行原`reduced_validate.py`改旧冻结索引；其继承报告内的历史固定路径命令不是新复跑目录入口，以本节wrapper命令为准。

本轮实际求解顺序和命令如下。**它们含固定R/C输出路径，只在新输出版本完成隔离后复跑；此处保留真实历史入口，不代表可直接覆盖冻结包。** `reduced_region.py` 支持 `--mode 1d|2d|all`、`--select` 精确run列表，没有输出根选项。

```sh
NUMBA_CACHE_DIR=/Users/maxchen/Documents/MathorCup/research_cache/round3/q4/reduced/numba_cache \
  /Users/maxchen/Documents/MathorCup/research_cache/round3/q4/reduced/venv/bin/python \
  track_b/research/q4/round3/scripts/reduced_benchmarks.py
NUMBA_CACHE_DIR=/Users/maxchen/Documents/MathorCup/research_cache/round3/q4/reduced/numba_cache \
  /Users/maxchen/Documents/MathorCup/research_cache/round3/q4/reduced/venv/bin/python \
  track_b/research/q4/round3/scripts/reduced_region.py --mode all
/Users/maxchen/Documents/MathorCup/research_cache/round3/q4/reduced/venv/bin/python \
  track_b/research/q4/round3/scripts/reduced_report.py
# 实际打开五幅图、记录其最终哈希后，再做交付检查与局部索引。
/Users/maxchen/Documents/MathorCup/research_cache/round3/q4/reduced/venv/bin/python \
  track_b/research/q4/round3/scripts/reduced_validate.py
```

实际JIT证据在 `results/reduced_numerical_validation.json/jit_evidence`，包含 `advance`、`timestep` 的真实编译签名；不是仅以Numba可导入代替JIT。原环境没有Numba，直接用原解释器跑区域循环会退回Python，不能作为正常复跑性能。

34个区域配置均实际算至1800s，过程场在 `q4/reduced/<run_id>/`，源字节与派生速度向量文件均由交付索引绑定。1D使用路径速度，末态另投影到UTM45N东／北；二维为水平图坐标。两路线薄层陡坡精度未合格，`include_in_arrival_envelope=false`；数值基准不算事件验证。

## 4. 官方固定镜像、目录映射和执行入口

平台为本机Docker中的 **linux/amd64**，固定镜像ID：

`sha256:a725b54f17797c8d4ffd2ac94a02b4a613115832c0633eb26135b309d5336f29`

唯一标签为 `mathorcup-r3-solvers:r3-rev7-dclaw1-20261024`；不要使用曾被失败恢复路线复用的旧 `:20261024` 标签。r.avaflow4.0 Rev7 / 20250902、D-Claw1.0.0 commit `7d48663bbed916372ba18732627c52043afb109f`、Clawpack5.11.0源码与二进制哈希见 `sources/runtime_ready_snapshot.json`、`official_source_identity.json` 和共享runtime的 `source_versions.json`。镜像检查不等同科学验证。

当前推荐 launcher 的参数已在文档编写时实际用 `--help` 核对：

```sh
track_b/.venv/bin/python track_b/research/q4/round3/scripts/official_launch.py --help
track_b/.venv/bin/python track_b/research/q4/round3/scripts/official_launch_container.py --help
docker image inspect sha256:a725b54f17797c8d4ffd2ac94a02b4a613115832c0633eb26135b309d5336f29
```

`official_launch.py` 用 `docker run --rm` 按ID执行已编译求解器，实际映射为：

| 主机 | 容器内 | 权限 |
|---|---|---|
| `research_cache/round3/q4/official/` | `/work` | 本问case/过程场可写 |
| 当前Q4 worktree根 | `/repo` | 只读源码及提交输入 |
| `research_cache/round3/runtime/` | `/runtime` | 只读固定来源／基准 |

案例工作目录为 `/work/runs/<run_id>`。launcher设置CLAW、PYTHONPATH、GRASS_ADDON_BASE和OMP线程数，不重新编译 `/opt`。`official_launch_container.py --container ... --cases ... [--only ...] [--retry]` 是已使用的容器兼容路线：用docker cp复制到 `/work/q4/official`，记录container ID并核对固定源码／二进制，不能把早期 `image_id=null` 记录伪装成已按最终镜像ID执行。

输入准备的历史入口：

```sh
track_b/.venv/bin/python track_b/research/q4/round3/scripts/official_prepare.py \
  --dem /Users/maxchen/Documents/MathorCup/research_cache/round3/q4/spatial/q4-r3-spatial-copdem-v1_dem_60m.tif \
  --geometry track_b/research/q4/round3/results/computational_geometries.geojson \
  --terrain-id copdem --resolutions 120,60
```

实际主输入取 `spatial_inputs_60m.npz` / `120m.npz`；`--dem`参数不代表另行覆盖共同数组。该准备脚本会生成固定case及config；已有case不重新覆盖。60m二值源面积925200m²，120m按925200/964800缩放厚度保同V，初速东／北0。

当前修订配置登记在 `official_protocol_v2.json`、`official_surface_correction_v2.json`。`official_corrected_cases.py` 在原case之外生成 `__sf0`；单相 `csurface=2` 已隔离，旧队列 `official_sweep.py` 与不带v2的原生r.avaflow主套件**不是推荐复跑队列**。多相sf2仅作为单列挑战保留。原始sf2状态索引风险、GRASS mapcalc适配失败、−11及重试日志都要保留，不通过重命名抹去。

当前已登记的正式入口示例（须先隔离新的run/output版本；`--only`为run ID子串筛选）：

```sh
track_b/.venv/bin/python track_b/research/q4/round3/scripts/official_launch.py \
  --image sha256:a725b54f17797c8d4ffd2ac94a02b4a613115832c0633eb26135b309d5336f29 \
  --cases track_b/research/q4/round3/config/official_cases_copdem_v2.json
track_b/.venv/bin/python track_b/research/q4/round3/scripts/official_launch.py \
  --image sha256:a725b54f17797c8d4ffd2ac94a02b4a613115832c0633eb26135b309d5336f29 \
  --cases track_b/research/q4/round3/config/official_cases_physics_v2.json
```

`official_sweep_v2.py` 是当前已登记队列入口，无argparse／`--help`；它会启动真实求解，并等待已有D-Claw60m参考，不能拿它做只读检查。单独launcher以退出码0决定跳过缓存，不等同科学质量已通过；先查execution的命令、case哈希、日志和实际末帧。不要同时启动重复run ID。

固定原生控制的安全重放入口为`official_replay_native.py`，读取`official_native_control_index.json`并核查case／execution／log、原始控制及输入哈希，输出目录必须是`q4/official/replays/`下尚不存在的新目录。默认只打印计划，既不创建输出目录也不启动求解；实际加`--execute`才复制控制并在独立可写目录执行，原证据以只读挂载提供。早期Python adapter未起点保存的缺失继续保留，不用当前adapter反造历史身份。D-Claw、r.avaflow、夹带和resourcefix四类的哈希／计划shell检查已实际完成，**未把计划检查称完整native复跑验证，也未因此增加执行案例数**。

```sh
# 只读描述；示例NEW目录若以后实际执行占用，则换新名称。
track_b/.venv/bin/python track_b/research/q4/round3/scripts/official_replay_native.py \
  --run-id copdem_120_single_ref__sf0 \
  --output-dir /Users/maxchen/Documents/MathorCup/research_cache/round3/q4/official/replays/REPLAY_NATIVE_NEW
```

原生 `-a` 附加输出／`-e` 对照独立登记在 `official_output_flag_protocol.json`、`official_cases_output_flag.json`，为同输入诊断，不自动替换主套件或消除失败。官方Cascadia和gully基准的launcher `--benchmarks` 及 `official_benchmarks_container.py` 是历史真实入口；gully默认绘图兼容错误有记录，不能把中途失败报为基准通过。最终保留的成功／失败分母由运行表确认。

`model_applicability_decision_03.json`与后续`official_entrainment_protocol.json`另列历史登记38／材料适用required30／代理诊断1／材料排除未运行7；不能直接用最初整套copdem配置重启所有代理。未来launcher使用per-run进程锁，避免调度重叠重写同run；已启动时的实际adapter副本及其SHA留在本case。合法数学代理未运行不等于数值失败，旧sf2取消也不覆盖其历史失败／重试记录。

尾部调度按主参谋指令由4提高至6并发，见`official_scheduling_amendment_06.json`；两个剩余fullmask优先启动，无新增case或重启原生run。实际原生环境OMP为3，并非声称每例只有一个线程；2026-10-24 UTC10:39仅对精确6个本问solver容器将CPU quota由3降至1，给8vCPU VM留2vCPU配额余量，独立回执`official_scheduling_cpu_receipt_07.json`保留原/新NanoCpus和完整ID。没有修改运行中case／旧execution／线程环境，后续launcher也按1CPU限额。wall time跨不同并发、配额与I/O阶段，属于实际运行代价记录，不能当受控性能基准。

**可比性限制**：D-Claw写入的是节点tt3，原生cell积分会改变局部厚度及有效离散地形，虽总体积接近保持，仍不等同逐格初态／地形一致。原生 `bed_normal=0`、r.avaflow `ctopo=0` 的高度方向及其标量速度地形修正分别记录。官方采样峰值、原生累计峰值、reduced步级峰值与湿深阈值不能混用。原生成功字段、实际时长、输出／清理失败、场值有效性和质量账分别判定。任务规模可能很大，60m、多相及扩域案例可长时间运行；持续看实际日志，不把暂时无输出当已完成或数值失败。

### 原版与资源清理修复版

原版固定镜像保持不变。小网格（`ceil(rows/16)*ceil(cols/16)<=16`）触发GRASS Segment全内存分支，原版最终`Segment_release`可在物理输出完成后空指针崩溃。主参谋发布的资源修复版只将45处最终清理调用换为`Segment_close`，不改物理方程、参数或Python wrapper。它是明确的派生构建，不能统称未改官方二进制。

- 派生镜像：`mathorcup-r3-solvers:r3-resourcefix1-20261024`，固定ID `sha256:3d8d8b4a31a520f64c52c2e8d3e23684181222c40ffd246f2d9e25d5cd511bce`。
- 派生原生二进制SHA256：`45ace2befd657d31232a73e1f5eabc174dd68c5962f6353385594fc70499bc1c`。
- 本问不可变交接快照：`sources/runtime_resourcefix_snapshot.json`，SHA256 `41b816bdb13d5abf9bd65998b3fae7e738556e731cbf86711bf184f7546c92b7`；说明见`runtime_resourcefix_guide_snapshot.md`。
- 有效`csurface=0`回归中共同70个ASCII输出逐字一致，原生时间数组相同；修复版正常退出。该检查验证资源修复不改变这些输出，不构成区域物理验证。

本问受影响小基准另登记`solver_build=explicit_resourcefix_build`，实际使用原镜像加只读`/resourcefix` addon，GRASS会话内核对`command -v`和二进制哈希。此执行方式不能误写为已在新镜像执行。重放可使用同一实际挂载方式或新固定镜像，并保留各自运行身份。77×150／154×300的大区域格网不触发该分支，已有正式区域运行继续使用原版，不为这个清理修复重算。`csurface=2`单相另属不适用状态索引配置，仍隔离；资源修复不能使其合格。

以下是固定新镜像的只读检查入口；它没有启动区域求解：

```sh
docker image inspect sha256:3d8d8b4a31a520f64c52c2e8d3e23684181222c40ffd246f2d9e25d5cd511bce
```

## 5. Q2两种物源映射与扩域敏感性

这些是有独立登记的不同几何／体积假设，后者不覆盖前者；Q2 `never_crossed` 也保留条件“若释放后传播”，不能转成源区启动预测。只消费本问 `inputs/q2/` 分发副本。

小面积v1的实际依赖顺序：

```sh
track_b/.venv/bin/python track_b/research/q4/round3/scripts/map_q2_releases.py
track_b/.venv/bin/python track_b/research/q4/round3/scripts/official_q2_cases.py
```

四个预选S／S_T／S_H／S_T_H代表按Q2原plan area取候选源区交集，逐格精确面积分数形成厚度，不用整块925200m²替代。协议与源哈希见 `q2_release_mapping_protocol.json`；缓存 `q4/integrated_inputs/q4-r3-q2-mapped-release-v1/`。

Q2几何v2已提供共同全mask释放栅格，本问登记三个固定网格／情景组合后原样校验复制，实际入口：

```sh
track_b/.venv/bin/python track_b/research/q4/round3/scripts/official_q2_v2_cases.py
# 在已有基础/Q2 case准备后统一生成sf0新配置；该脚本会写config，不能覆盖冻结case。
track_b/.venv/bin/python track_b/research/q4/round3/scripts/official_corrected_cases.py
```

随后 `official_launch.py --image <固定ID> --cases config/official_cases_q2mapped_v2.json` 与 `official_cases_q2fullmask_v2.json`（均补完整 `track_b/research/q4/round3/` 前缀）是各自的原生求解入口；当前 `official_sweep_v2.py` 也引用这两套。区分small-area v1、fullmask geomv2、上游base_scenario_id、正常／垂直厚度、体积、密度及被动组分，不能按传播最快重新挑输入。

扩大域用于检查D-Claw原域边界先于目标到达受影响。实际准备链为：

```sh
track_b/.venv/bin/python track_b/research/q4/round3/scripts/extend_computational_domain.py
track_b/.venv/bin/python track_b/research/q4/round3/scripts/official_extended_case.py
track_b/.venv/bin/python track_b/research/q4/round3/scripts/official_launch.py \
  --image sha256:a725b54f17797c8d4ffd2ac94a02b4a613115832c0633eb26135b309d5336f29 \
  --cases track_b/research/q4/round3/config/official_cases_extended.json
```

`domain_extension_protocol.json`预登记120m每边加84格／10080m，保留同源Copernicus、原核心DEM值和参考释放体积；新增缓存 `q4/integrated_inputs/domain_extension_v1/`，原域结果仍保留。脚本会写既定扩域版本，后续再扩必须新版本。扩大一次仅是敏感性，不证明无限域收敛；首次触边、到达前边界作用、输出时间括号和近似净质量通量分别报告。

## 6. 后处理、图审、manifest与收尾顺序

在每个case执行结束且文件完整后再分析。当前已有实际后处理入口：

```sh
track_b/.venv/bin/python track_b/research/q4/round3/scripts/official_analyse.py
track_b/.venv/bin/python track_b/research/q4/round3/scripts/official_targets.py
track_b/.venv/bin/python track_b/research/q4/round3/scripts/compare_optical_agreement.py
track_b/.venv/bin/python track_b/research/q4/round3/scripts/compare_native_sensitivity.py --require-complete
track_b/.venv/bin/python track_b/research/q4/round3/scripts/plot_regional_comparison.py
track_b/.venv/bin/python track_b/research/q4/round3/scripts/plot_composite_phases.py
track_b/.venv/bin/python track_b/research/q4/round3/scripts/plot_entrainment_residual.py
track_b/.venv/bin/python track_b/research/q4/round3/scripts/plot_stationary_residuals.py
```

分别写官方run／metrics／arrival／validation／场索引、全部OSM代表目标后处理、光谱候选与模型足迹的探索性一致性，以及已登记单相敏感性、共同轴参考图、复合各相过程和有界夹带末态。后三种根图脚本要求输入NPZ与case绑定哈希，未闭合对照会拒绝或显式只输出已完成子集；`--require-complete`要求10个单相登记全部闭合。`plot_domain_sensitivity.py`固定读冻结v1域对照；`audit_dclaw_mass.py`只读原生raw、不启动新的native计算。脚本会重写各自派生报告／图，最终manifest后不要在原包执行；另建新版本才可重算。光谱足迹一致性不是独立事件验证，也不能自动给参数校准或95%覆盖结论。

`scientific_acceptance_decision_05.json`的accepted名单当前为空，新rolling／最终v3+全部区域`include_in_arrival_envelope=false`。执行、实际时间、字段、适用材料、触边gate独立于科学接受，原始命中／未达不删；`conditional_diagnostic_range_eligible`若true也只表示有限执行诊断。该决定不以结果临时设预算容忍百分比。旧v1的12条true仅表示当时明示的执行／边界gate；v2两例全部排除，两包不可追改。

根汇总入口为`scripts/integrate_comparison.py`，完整性与接口检查为`scripts/validate_round3.py`，最终流式冻结为`scripts/freeze_round3.py`。滚动运行不带freeze；最终已实际使用`--freeze --version propagation_v4`冻结777成员，SHA256 `d3b87e86ceacd0709b6f9278aee7096e6671964b8baec0c4055eac1355d529e4`；该目录不可覆盖。今后重算须用更高未占用版本。v3已冻结三个Q2 fullmask的独立partial早交，另有legacy体积metadata adapter与SH／STH compact_delta_v1，最后全模型另版且不得覆盖已分发v3。脚本拒绝变化输入／未完成required／未结实际尝试，并冻结为`frozen_for_joint_review`，不是预测精度接受。`--early-freeze --version propagation_v1`是历史真实早交命令，不可重用已占用v1目录。

复核须在稳定输入上按以下顺序执行；实际检查结果见workspace_verification.json、validation.json与最终只读manifest核验：

1. 停止重复队列，确认每个计划run的完成、失败、取消、隔离或未运行状态；保留全部尝试目录、case、UTC、日志及命令。
2. 解析全部原生实际时间和字段；保留失败前命中及其资格标记，未到达按实际censor时间，不把提前结束说成1800s内未达。
3. 根跨模型汇总、Q2两版物源、扩域差异与光谱一致性；按指标定义和有效性门槛分组，不能把不合格reduced路线纳入到达包络。
4. 实际打开最终图，检查单位／目标／时间／标签，记录图像哈希；重画图后相应重审。
5. 写 `MODEL_COMPARISON.md`、`EVIDENCE_REVIEW.md`、`PAPER_OUTLINE.md`、`HANDOFF.md`；明确条件情景、外部迁移、数值基准及本地观测各自证据边界。
6. 冻结最终 `exports/propagation_bundle.json` 及文件索引，逐文件path/bytes/sha256/role；输入／输出manifest不自包含，运行环境与可变日志排除项须说明。
7. 用原44包环境再次执行第1节标准五组验证，执行`validate_round3.py`写最终`validation.json`；随后`freeze_round3.py`绑定包括该验证在内的字节，最后`validate_round3.py --check-manifests`只读校验而不改包。最终验证要求包状态`frozen_for_joint_review`、版本至少v4及三张CSV与根最终表逐字一致；freeze拒绝rolling、pending、未结attempt或validation后根表变化，并调用`validate_round3.py --read-only-final`重查全部实际绑定字节、确认缓存／非manifest包文件在整个扫描期间未改变。只读清单验证还检查完整路径集合，不能让新增未登记文件漏过。仅本问round3本地提交、不push，确认工作树干净后交主参谋联合审查。

`validate_round3.py --provisional`初次实际128项、后续扩充154项完整性／接口检查通过，最终项目数以validation.json为准；它不要求队列结束，也不证明区域精度。最终无此选项的检查还要求全部当前登记运行和实际尝试有明确终态、冻结传播包及最终图审。`freeze_round3.py`不能在缓存持续写入时使用。原生小基准的数值反证、区域薄流精度不足和独立事件数0由数值记录另存，不因artifact检查通过而改写。

保留故障入口至少包括：局部Numba0.68/LLVM失败、最初mapcalc适配失败、gully绘图错误、被隔离sf2、−11、输出flag诊断，以及任何后续数值失败和未达。失败日志不是可执行推荐队列，也不能因新版本成功而删除。

尾部CPU配额续回执见`official_scheduling_cpu_tail_receipts_08.json`：全部待启任务确实启动后，按剩余活跃数每例min(3,6/n)CPU复用最多6vCPU；原OMP=3、输入、物理与原进程未改。最终50个native重放计划已做hash／shell检查，额外完整native重放仍为0；安全reduced实际科学复现为2个既有案例。完整raw清单、实际控制及最终交付身份见`official_final_delivery.json`。
