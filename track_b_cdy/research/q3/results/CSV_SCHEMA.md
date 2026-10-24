# Q3 机器审计表说明

CSV为UTF-8、首行列名、LF换行；嵌套值是JSON字符串。未知值用字面`null`，布尔为`true/false`，不能当作0或已核验。所有时间字符串须带时区；NASA原始epoch换算列仅作目录编码展示，未核实发生时区的`time_utc`保持null。

- `label_review.csv`：63条证据/候选记录；`record_kind`区分9条同一案例证据和54条历史候选。候选ID不等于独立事件组；审核及重复理由为显式字段。
- `availability_review.csv`：6个实际GRIB字段的时间、单位、累计区间及可用性审核。资料检索时刻与历史`available_time`分别保存。
- `replay_gate.csv`：3个固定技术发布时刻×11个输入/引用=33行。时间门禁不会批准特征质量或源区代表性。
- `replay_delay_scenarios.csv`：3发布时刻×4个未核实延迟假设×6字段=72行。`data_role=scenario`，不能作为真实可用性或验证样本。

规范字段遵循共同`stage4_contract.json`。`input_version`绑定共同起点和清单SHA-256；原始/加工来源的路径与SHA另列。`results/input_manifest.json`保存本轮直接读取的稳定输入；运行时就绪/派单信息复制为独立快照，避免后续验证更新造成伪输入漂移。
