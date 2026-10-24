# r.avaflow Rev7 resourcefix1

本发布只修复 Segment 资源收尾；原官方源码、原镜像、v1交接及历史产物保留。`runtime_resourcefix_handoff.json`是本次机器交接，`resourcefix1_addon_manifest.json`固定全部24个addon文件。已发布目录 `release_addon/` 不再重编覆盖。

## 可用版本

- 派生镜像：`sha256:3d8d8b4a31a520f64c52c2e8d3e23684181222c40ffd246f2d9e25d5cd511bce`
- 本地tag：`mathorcup-r3-solvers:r3-resourcefix1-20261024`，未推送远端。
- 原base：`sha256:a725b54f17797c8d4ffd2ac94a02b4a613115832c0633eb26135b309d5336f29`
- 生产二进制SHA256：`45ace2befd657d31232a73e1f5eabc174dd68c5962f6353385594fc70499bc1c`。
- 只读addon：`/Users/maxchen/Documents/MathorCup/research_cache/round3/runtime/diagnostics/q4_native_asan/derived/release_addon`。

镜像内 `/opt/grass-addons/bin/r.avaflow.main` 已核对上述SHA；派生源码、精确patch及资源所有权证据位于 `/opt/ravaflow-resourcefix1`。外部交接包括后续有效csurface=0回归，内容比镜像内早期说明更完整。

## 根因、精确修复与构建

GRASS的 `Segment_open` 在全内存分支设置 `cache` 并令 `scb=NULL`；r.avaflow却用低层 `Segment_release` 清理，后者直接读取scb。原版ASAN明确报告 `main.c:12483 → Segment_release → NULL read`，独立最小API探针也复现release失败、close成功。配对API `Segment_close`先判断全内存分支，磁盘分支则正确释放缓存、关闭并删除临时后端。原始API证据保存在上一层 `reference_sources/`，来源为[open.c](https://raw.githubusercontent.com/OSGeo/grass/7.8.7/lib/segment/open.c)、[release.c](https://raw.githubusercontent.com/OSGeo/grass/7.8.7/lib/segment/release.c)、[close.c](https://raw.githubusercontent.com/OSGeo/grass/7.8.7/lib/segment/close.c)。

`segment_close.patch`仅将最终清理段45个 `Segment_release` 改为 `Segment_close`。45个handle和初始化条件一一对应；没有后续引用、额外手工close/free或双释放。`resource_ownership_check.json`、`source_package_diff.json`与`change_manifest.json`记录检查。逆向替换可逐字恢复原始源码；所有物理方程、状态推进、参数读取与Python wrapper保持原字节。

- 原main.c SHA：`cdb1168d7cf154e3504d199f7bef8d095cbafe74298cb9087874e1d700a1127a`
- 派生main.c SHA：`5cd245c8aadc8f1869cb091a0eefc49e3f3241cec4a8266bd117a432d0f1b975`

原base依赖环境为Ubuntu22.04 / GRASS7.8.7 / GCC11.4.0。通过未修改的官方GRASS Makefile、`g.extension`完成生产构建（不带ASAN），日志 `build_release.log`。原构建命令如下；复建须使用新的输出目录，不能写已发布addon：

```sh
grass --tmp-location XY --exec g.extension extension=r.avaflow.40G \
  url=/diagnostics/derived/source_package/r.avaflow.40G \
  prefix=/diagnostics/derived/release_addon
```

## 有效回归与限制

`valid_cs0_regression.json`使用同一bowl DEM/release和**单相csurface=0**：

| 比较 | 共同ASCII逐字相同 | 退出状态 |
|---|---:|---|
| 原版两次重复 | 77/77 | 均在最终Segment清理SIGSEGV |
| 修复版两次重复 | 70/70 | 均0 |
| 原版→修复版 | 70/70 | SIGSEGV→0 |
| 修复addon→派生镜像 | 70/70 | 均0 |
| 修复addon→只读挂载addon | 70/70 | 均0 |

各次原生 `tsum` 均为 `[0,27.3,40.8,70.3,85.7,115.3]` 秒，按实际模型时刻比较。原版多出的7个basechange零场是wrapper未能继续清理；原版summary/volumes的未刷新缓冲为空，修复后正常关闭写入。另有ASAN flatrest single/multi均正常，single34/34共同ASCII逐字一致；生产flatrest single34/34、multi102/102一致。

旧单相csurface=2的bowl配置涉及不适用状态索引，其输出保留为不合格配置，不用来评价补丁动态一致性。四组合短时运行成功也不能证明该配置有效。这项资源回归不替代物理、守恒、边界、时间步与网格验证，不增加灾害验证事件数。

原固定源码16×16块、16个缓存块，`ceil(rows/16)*ceil(cols/16) <= 16`进入全内存分支：30×40小网格6块触发；CopDEM120m的77×150为50块、60m的154×300为190块，不触发。已有大域结果不因本收尾修复自动要求科学重算，仍按各自版本和Q4数值验收保留。

## 运行方式

使用派生镜像执行已有case脚本；case的输入和命令仍由Q4配置：

```sh
docker run --rm --cpus=1 --memory=1536m \
  --mount type=bind,src=/absolute/case,dst=/case \
  sha256:3d8d8b4a31a520f64c52c2e8d3e23684181222c40ffd246f2d9e25d5cd511bce \
  grass --tmp-location /case/dem.tif --exec bash /case/run_grass.sh
```

也可在原base上固定只读addon；`GRASS_ADDON_BASE=/resourcefix`已实际运行验证，70/70输出一致：

```sh
docker run --rm --cpus=1 --memory=1536m \
  -e GRASS_ADDON_BASE=/resourcefix \
  --mount type=bind,src=/Users/maxchen/Documents/MathorCup/research_cache/round3/runtime/diagnostics/q4_native_asan/derived/release_addon,dst=/resourcefix,readonly \
  --mount type=bind,src=/absolute/case,dst=/case \
  sha256:a725b54f17797c8d4ffd2ac94a02b4a613115832c0633eb26135b309d5336f29 \
  grass --tmp-location /case/dem.tif --exec bash /case/run_grass.sh
```

新运行登记 `solver_build=ravaflow4r7-resourcefix1`、`resource_fix=segment_open_close_v1`及镜像ID/二进制SHA。必须同时审核进程退出、success、原生summary/volumes实际时刻和物理场；不能把success=1或帧号×20当完整通过。该源码的日志tlength显示100×dt，tsum才是模型秒；求解器可能跨越预设输出/终止时刻。
