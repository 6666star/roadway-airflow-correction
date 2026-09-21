# 巷道风速校正 · V2

基于径向映射，将局部时间平均风速转换为断面平均风速和风量估计。支持矩形、半圆拱、相切三心拱及等腰梯形。网页保留当前精简界面，所有计算由原C++核心完成。

## 一条命令启动网页

需要Python 3.12、CMake 3.20以上和支持C++20的编译器。

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

首次启动自动编译C++程序，并在进程内启动仅监听本机的gRPC服务。后续页面交互与多个访问会话复用该服务；不需要手动启动另一台计算服务器。源代码变更后使用新的构建目录。

## 部署到Streamlit Community Cloud

1. 将本仓库上传至GitHub私有仓库。
2. 登录 https://share.streamlit.io ，连接有本仓库访问权限的GitHub账号，并授予私有仓库访问权限。
3. Create app → 从已有GitHub仓库部署。
4. Repository：`6666star/roadway-airflow-correction`；Branch：`main`；Main file path：`streamlit_app.py`。
5. Advanced settings选择Python 3.12，然后部署。
6. 部署完成后打开网页，依次测试四个示例。首次启动包含C++编译，需要等待。

Python包由requirements.txt安装，Linux编译工具由packages.txt安装，无需上传Windows可执行文件。应用不需要密钥。不要将GitHub令牌写入源代码或secrets.toml后提交。

GitHub私有仓库与网页访问权限是两个设置。初次保持网页私有，在Streamlit应用设置中按需邀请查看者；不要仅因仓库私有就假定网页没有公开。

官方说明：[部署入口](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy)、[依赖管理](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies)。

## 验证

```bash
python tests/test_cloud_app.py
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j 2
ctest --test-dir build --output-on-failure
```

GitHub Actions在Linux上执行C++测试、RPC集成测试和云入口四断面测试。云部署时仍需检查实际启动日志和网页结果。

## 目录

- `streamlit_app.py`：云端/本地一体启动入口。
- `cloud_runtime.py`：编译与缓存计算服务。
- `frontend/app.py`：Streamlit页面；直接运行此文件仍可手动连接后端。
- `src/`、`include/`：C++模型与计算核心。
- `grpc_adapter/`、`proto/`、`generated/`：RPC适配层、协议及生成代码。
- `docs/项目介绍.md`、`docs/算例验证及局限.md`：项目介绍与验证汇总。
- `docs/validation/`：历史结果、数据清单和验证脚本。来源PDF、DNS大体积二进制不在本仓库；部分历史复测脚本需要恢复原始数据和调整本机路径后运行。

## 模型说明

默认采用径向映射；旧算法实现仅作为兼容与回归对照保留，网页不提供旧工作区或旧矩形方法选择。粗糙度为长度参数，不能直接用矿井摩擦阻力系数代替。几何示意不代表实测风场，模型适用范围和已知误差见验证文档。

部署副本来自Project_1_v2。原本机项目未被覆盖。文献PDF、虚拟环境、Windows构建产物、账号凭据均未纳入上传目录。
