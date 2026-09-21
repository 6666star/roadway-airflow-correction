# 扩展文献验证：数值结果（2026-09-10）

后端未改、未拟合。位置误差不等于均速误差。详细适用条件见 expanded_validation_20260910_report.md。

| 数据组 | 评价数 | 距壁位置 MAPE | 条件均速 MAPE，ε=5.5mm | 条件均速最大误差 |
|---|---:|---:|---:|---:|
| Song2022_LDA_contour | 10 | 28.992% | 6.092% | 13.344% |
| Song2022_LDA_fitted_profile | 40 | 不适用 | 5.261% | 13.387% |
| Zhang2022_CFD_rectangle | 10 | 1.736% | 0.218% | 0.322% |
| Zhang2022_CFD_semiarch | 10 | 1.853% | 0.240% | 0.477% |
| Zhang2022_Sima_field_proxy | 4 | 3.038% | 0.397% | 0.524% |

## 粗糙度敏感性：条件均速误差

| 组 | 假设 ε/m | MAPE | 最大绝对误差 | ≤10%数量 |
|---|---:|---:|---:|---:|
| Song2022_LDA_contour | 0.0055 | 6.092% | 13.344% | 9/10 |
| Song2022_LDA_contour | 0.0001 | 3.335% | 6.856% | 10/10 |
| Song2022_LDA_contour | 1e-05 | 2.647% | 5.359% | 10/10 |
| Song2022_LDA_contour | 1e-06 | 2.195% | 4.399% | 10/10 |
| Song2022_LDA_fitted_profile | 0.0055 | 5.261% | 13.387% | 36/40 |
| Song2022_LDA_fitted_profile | 0.0001 | 7.227% | 18.766% | 28/40 |
| Song2022_LDA_fitted_profile | 1e-05 | 8.398% | 20.419% | 26/40 |
| Song2022_LDA_fitted_profile | 1e-06 | 9.245% | 21.495% | 23/40 |
| Zhang2022_CFD_rectangle | 0.0055 | 0.218% | 0.322% | 10/10 |
| Zhang2022_CFD_rectangle | 0.0001 | 0.145% | 0.213% | 10/10 |
| Zhang2022_CFD_rectangle | 1e-05 | 0.121% | 0.178% | 10/10 |
| Zhang2022_CFD_rectangle | 1e-06 | 0.104% | 0.153% | 10/10 |
| Zhang2022_CFD_semiarch | 0.0055 | 0.240% | 0.477% | 10/10 |
| Zhang2022_CFD_semiarch | 0.0001 | 0.157% | 0.312% | 10/10 |
| Zhang2022_CFD_semiarch | 1e-05 | 0.131% | 0.260% | 10/10 |
| Zhang2022_CFD_semiarch | 1e-06 | 0.113% | 0.223% | 10/10 |
| Zhang2022_Sima_field_proxy | 0.0055 | 0.397% | 0.524% | 4/4 |
| Zhang2022_Sima_field_proxy | 0.0001 | 0.262% | 0.346% | 4/4 |
| Zhang2022_Sima_field_proxy | 1e-05 | 0.219% | 0.290% | 4/4 |
| Zhang2022_Sima_field_proxy | 1e-06 | 0.188% | 0.249% | 4/4 |

## 位置逐项结果

| 组/工况 | 参考距壁/m | 预测/m | 位置误差 |
|---|---:|---:|---:|
| Song2022_LDA_contour/Re23000_floor | 0.033300 | 0.022313 | -32.994% |
| Song2022_LDA_contour/Re23000_roof | 0.033780 | 0.022313 | -33.946% |
| Song2022_LDA_contour/Re35000_floor | 0.030700 | 0.022313 | -27.319% |
| Song2022_LDA_contour/Re35000_roof | 0.030800 | 0.022313 | -27.555% |
| Song2022_LDA_contour/Re46000_floor | 0.029340 | 0.022313 | -23.950% |
| Song2022_LDA_contour/Re46000_roof | 0.029680 | 0.022313 | -24.821% |
| Song2022_LDA_contour/Re57000_floor | 0.022920 | 0.022313 | -2.648% |
| Song2022_LDA_contour/Re57000_roof | 0.021120 | 0.022313 | +5.649% |
| Song2022_LDA_contour/Re65000_floor | 0.016520 | 0.022313 | +35.067% |
| Song2022_LDA_contour/Re65000_roof | 0.012680 | 0.022313 | +75.970% |
| Zhang2022_CFD_rectangle/W5_H3.5_U0.8 | 0.386000 | 0.390478 | +1.160% |
| Zhang2022_CFD_rectangle/W5_H3.5_U2 | 0.380800 | 0.390478 | +2.541% |
| Zhang2022_CFD_rectangle/W5_H3.5_U4 | 0.384100 | 0.390478 | +1.660% |
| Zhang2022_CFD_rectangle/W5_H3.5_U6 | 0.386200 | 0.390478 | +1.108% |
| Zhang2022_CFD_rectangle/W5_H3.5_U8 | 0.384900 | 0.390478 | +1.449% |
| Zhang2022_CFD_rectangle/W6_H4_U0.8 | 0.440900 | 0.446260 | +1.216% |
| Zhang2022_CFD_rectangle/W6_H4_U2 | 0.436300 | 0.446260 | +2.283% |
| Zhang2022_CFD_rectangle/W6_H4_U4 | 0.437900 | 0.446260 | +1.909% |
| Zhang2022_CFD_rectangle/W6_H4_U6 | 0.438500 | 0.446260 | +1.770% |
| Zhang2022_CFD_rectangle/W6_H4_U8 | 0.436400 | 0.446260 | +2.259% |
| Zhang2022_CFD_semiarch/W4_H3_U0.8 | 0.322800 | 0.334695 | +3.685% |
| Zhang2022_CFD_semiarch/W4_H3_U2 | 0.328600 | 0.334695 | +1.855% |
| Zhang2022_CFD_semiarch/W4_H3_U4 | 0.330500 | 0.334695 | +1.269% |
| Zhang2022_CFD_semiarch/W4_H3_U6 | 0.326600 | 0.334695 | +2.479% |
| Zhang2022_CFD_semiarch/W4_H3_U8 | 0.325700 | 0.334695 | +2.762% |
| Zhang2022_CFD_semiarch/W4.5_H3.3_U0.8 | 0.367100 | 0.368165 | +0.290% |
| Zhang2022_CFD_semiarch/W4.5_H3.3_U2 | 0.362100 | 0.368165 | +1.675% |
| Zhang2022_CFD_semiarch/W4.5_H3.3_U4 | 0.362800 | 0.368165 | +1.479% |
| Zhang2022_CFD_semiarch/W4.5_H3.3_U6 | 0.362800 | 0.368165 | +1.479% |
| Zhang2022_CFD_semiarch/W4.5_H3.3_U8 | 0.362500 | 0.368165 | +1.563% |
| Zhang2022_Sima_field_proxy/Sima_1 | 0.394600 | 0.379321 | -3.872% |
| Zhang2022_Sima_field_proxy/Sima_2 | 0.395200 | 0.379321 | -4.018% |
| Zhang2022_Sima_field_proxy/Sima_3 | 0.343700 | 0.334695 | -2.620% |
| Zhang2022_Sima_field_proxy/Sima_4 | 0.317600 | 0.312382 | -1.643% |
