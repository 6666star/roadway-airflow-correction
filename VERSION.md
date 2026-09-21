# V2 版本分离记录

- 原版：`C:/Users/staro/Desktop/Cluade/Project_1`
- 新版：`C:/Users/staro/Desktop/Cluade/Project_1_v2`
- 版本：2.0.0
- 分离日期：2026-09-08

V2 包含半圆拱、三心拱、等腰梯形及矩形的 Wei 径向映射后端、CLI、gRPC 扩展与测试。原版恢复到本轮算法扩展之前，保留原有 Wei 矩形、Zhang 中心线模型及此前的方案文档。

两个目录使用各自的 `.venv` 与 `build-codex`，V2 不依赖原版路径运行。

## 运行与测试

在本目录执行：

```powershell
.\.venv\Scripts\python.exe run_backend.py
.\build-codex\airflow_cli.exe semicircle-wei-radial 4 3 1 2 2 0.0055
ctest --test-dir build-codex --output-on-failure
```

算法及参数说明见 [V2 后端文档](docs/wei_radial_backend_v2.md)。

## 分离后的验证

- 原版重新生成协议并重新编译，CTest 2/2 通过。
- V2 独立创建虚拟环境并从新路径编译，CTest 4/4 通过。
- 原版中本轮新增的径向源码、测试和 V2 说明已移至 V2；完整内容保留在本目录。
