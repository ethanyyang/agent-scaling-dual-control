# Qwen3.5 4B S1 results export

本包从本机实测原始结果逐字节导出，保持 tau2 Results 格式，不合并不同域或不同配置。不新增实验记录、不补造对话、分数、token、时间戳或模型来源。

|目录|尝试/计划|有效|基础设施错误|有效 episode 平均 reward|
|---|---:|---:|---:|---:|
|airline|150/150|144|6|0.3958333333|
|retail|150/150|142|8|0.3591549296|
|telecom|22/150|22|0|0.5909090909|
|airline-october-partial|10/150|8|2|0.875|

每个目录含原始 results.json 和来源 manifest.json。顶层 manifest.json 汇总来源路径、SHA-256、运行配置、完整性与排除数量。失败记录保留在 results.json 中；上表仅排除基础设施错误和没有 reward 的记录，agent_error 等正常计为实验失败。这里的平均值是 episode mean，不是按任务加权的 pass^1。

前三个目录为原始 ollama_chat/qwen3.5:4b、32k 上下文、temperature=0 实验。十月 Airline 为独立 OpenAI-compatible 接口实验；不能混入早期 150 条记录，也不能直接证明满足 M1 配对的服务栈/build 来源要求。manifest 的 registered_stack_match 只表示接口和配置类别，不表示主分析资格通过。

Telecom 旧 summary.json 记录的是更早的全基础设施失败批次；本次直接读取当前原始 results.json，实际为 22 条未完成实验。注册配置下 Telecom 150 条、94.7% 的原始结果本机仍缺失，不由该汇总分数生成替代数据。

校验：四个文件均通过当前项目 tau2.data_model.simulation.Results.model_validate；task/trial 无重复，simulation ID 无重复，task ID 属于任务列表，导出 SHA-256 与原文件完全一致。Airline 和 Retail 哈希也与原校准 summary.json 一致。

下游注意：calibrate_budget.py 对所有 simulations 计算分位数，不自动排除基础设施错误。不要将含基础设施失败的本包直接用于重建或覆盖冻结预算；应依项目排除规则处理，并保留原始来源与已有百分位算法口径。此次未修改 budgets.json、注册 manifest 或主分析表，未启动新实验。
