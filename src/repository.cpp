#include "airflow/repository.hpp"

#include <cmath>

namespace airflow {
namespace {

bool nearlyEqual(double a, double b, double tolerance = 1e-9) {
    return std::abs(a - b) <= tolerance;
}

CenterlineParameterSet row(
    const std::string& id,
    GeometryType type,
    double width,
    double height,
    double inletVelocity,
    double logZoneEnd,
    double coreZoneEnd,
    double a,
    double b,
    double coreRatio) {
    return {id, type, width, height, inletVelocity, logZoneEnd, coreZoneEnd, a, b, coreRatio};
}

} // namespace

ModelRepository::ModelRepository() {
    const auto rect = GeometryType::Rectangle;
    const auto semi = GeometryType::SemicircleArch;

    parameterSets_ = {
        row("RECT_4x3_V0.8", rect, 4.0, 3.0, 0.8, 1.25, 1.50, 1.1839, 0.1633, 1.2250),
        row("RECT_4x3_V2",   rect, 4.0, 3.0, 2.0, 1.25, 1.50, 1.1573, 0.1391, 1.2100),
        row("RECT_4x3_V4",   rect, 4.0, 3.0, 4.0, 1.25, 1.50, 1.1406, 0.1267, 1.1850),
        row("RECT_4x3_V6",   rect, 4.0, 3.0, 6.0, 1.25, 1.50, 1.1332, 0.1189, 1.1750),
        row("RECT_4x3_V8",   rect, 4.0, 3.0, 8.0, 1.25, 1.50, 1.1273, 0.1146, 1.1663),

        row("RECT_5x3.5_V0.8", rect, 5.0, 3.5, 0.8, 1.50, 1.75, 1.1605, 0.1686, 1.2250),
        row("RECT_5x3.5_V2",   rect, 5.0, 3.5, 2.0, 1.50, 1.75, 1.1179, 0.1221, 1.1750),
        row("RECT_5x3.5_V4",   rect, 5.0, 3.5, 4.0, 1.50, 1.75, 1.1065, 0.1113, 1.1575),
        row("RECT_5x3.5_V6",   rect, 5.0, 3.5, 6.0, 1.50, 1.75, 1.0999, 0.1050, 1.1470),
        row("RECT_5x3.5_V8",   rect, 5.0, 3.5, 8.0, 1.50, 1.75, 1.0924, 0.0968, 1.1338),

        row("RECT_6x4_V0.8", rect, 6.0, 4.0, 0.8, 1.70, 2.00, 1.1171, 0.1430, 1.1875),
        row("RECT_6x4_V2",   rect, 6.0, 4.0, 2.0, 1.70, 2.00, 1.0899, 0.1084, 1.1550),
        row("RECT_6x4_V4",   rect, 6.0, 4.0, 4.0, 1.70, 2.00, 1.0796, 0.0964, 1.1350),
        row("RECT_6x4_V6",   rect, 6.0, 4.0, 6.0, 1.70, 2.00, 1.0596, 0.0723, 1.0970),
        row("RECT_6x4_V8",   rect, 6.0, 4.0, 8.0, 1.70, 2.00, 1.0718, 0.0866, 1.1200),

        row("SEMI_4x3_V0.8", semi, 4.0, 3.0, 0.8, 1.25, 1.50, 1.1730, 0.1530, 1.2125),
        row("SEMI_4x3_V2",   semi, 4.0, 3.0, 2.0, 1.25, 1.50, 1.1157, 0.1075, 1.1450),
        row("SEMI_4x3_V4",   semi, 4.0, 3.0, 4.0, 1.25, 1.50, 1.1055, 0.0975, 1.1275),
        row("SEMI_4x3_V6",   semi, 4.0, 3.0, 6.0, 1.25, 1.50, 1.0985, 0.0920, 1.1180),
        row("SEMI_4x3_V8",   semi, 4.0, 3.0, 8.0, 1.25, 1.50, 1.0941, 0.0881, 1.1113),

        row("SEMI_4.5x3.3_V0.8", semi, 4.5, 3.3, 0.8, 1.60, 1.65, 1.1476, 0.1473, 1.2000),
        row("SEMI_4.5x3.3_V2",   semi, 4.5, 3.3, 2.0, 1.60, 1.65, 1.1020, 0.1038, 1.1350),
        row("SEMI_4.5x3.3_V4",   semi, 4.5, 3.3, 4.0, 1.60, 1.65, 1.0894, 0.0908, 1.1175),
        row("SEMI_4.5x3.3_V6",   semi, 4.5, 3.3, 6.0, 1.60, 1.65, 1.0827, 0.0840, 1.1070),
        row("SEMI_4.5x3.3_V8",   semi, 4.5, 3.3, 8.0, 1.60, 1.65, 1.0793, 0.0806, 1.1012)
    };
}

std::optional<CenterlineParameterSet> ModelRepository::findExact(
    GeometryType geometryType,
    double width,
    double height,
    double inletVelocity) const {
    for (const auto& item : parameterSets_) {
        if (item.geometryType == geometryType &&
            nearlyEqual(item.width, width) &&
            nearlyEqual(item.height, height) &&
            nearlyEqual(item.inletVelocity, inletVelocity)) {
            return item;
        }
    }
    return std::nullopt;
}

const std::vector<CenterlineParameterSet>& ModelRepository::all() const {
    return parameterSets_;
}

} // namespace airflow

