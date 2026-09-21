#pragma once

#include "airflow/types.hpp"

#include <optional>
#include <vector>

namespace airflow {

struct CenterlineParameterSet {
    std::string id;
    GeometryType geometryType{};
    double width{};
    double height{};
    double inletVelocity{};
    double logZoneEnd{};
    double coreZoneEnd{};
    double coefficientA{};
    double coefficientB{};
    double coreRatio{};
};

class ModelRepository {
public:
    ModelRepository();

    [[nodiscard]] std::optional<CenterlineParameterSet> findExact(
        GeometryType geometryType,
        double width,
        double height,
        double inletVelocity) const;

    [[nodiscard]] const std::vector<CenterlineParameterSet>& all() const;

private:
    std::vector<CenterlineParameterSet> parameterSets_;
};

} // namespace airflow

