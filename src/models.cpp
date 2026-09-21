#include "airflow/model.hpp"

#include <algorithm>
#include <cmath>
#include <functional>
#include <limits>

namespace airflow {
namespace {

double integrateMean(
    const Geometry& geometry,
    const std::function<double(Point)>& function,
    int resolution) {
    if (resolution < 20) {
        throw AirflowError(ErrorCode::InvalidArgument, "meshResolution must be at least 20");
    }

    const auto b = geometry.bounds();
    const double dx = (b.maxX - b.minX) / static_cast<double>(resolution);
    const double dy = (b.maxY - b.minY) / static_cast<double>(resolution);
    double integral = 0.0;

    for (int iy = 0; iy < resolution; ++iy) {
        const double y = b.minY + (static_cast<double>(iy) + 0.5) * dy;
        for (int ix = 0; ix < resolution; ++ix) {
            const double x = b.minX + (static_cast<double>(ix) + 0.5) * dx;
            const Point point{x, y};
            if (geometry.contains(point)) {
                integral += function(point) * dx * dy;
            }
        }
    }
    return integral / geometry.area();
}

std::string directModelId(GeometryType type) {
    return type == GeometryType::Rectangle
        ? "RECT_ZHANG2022_CENTERLINE"
        : "SEMICIRCLE_ZHANG2022_CENTERLINE";
}

std::string directModelName(GeometryType type) {
    return type == GeometryType::Rectangle
        ? "Zhang 2022 rectangle centerline correction"
        : "Zhang 2022 semicircle-arch centerline correction";
}

struct Wei2019PointEvaluation {
    double equivalentRadius{};
    double equivalentWallDistance{};
    double shapeFactor{};
};

Wei2019PointEvaluation evaluateWei2019Point(
    const RectangleGeometry& rectangle,
    Point point,
    double absoluteRoughness) {
    const double width = rectangle.width();
    const double height = rectangle.height();
    const double equivalentRadius = width * height / (width + height);

    // Wei et al. define a and b as distances from the two centre lines. Their
    // Table 1 lists positions from the adjacent walls, so those tabulated
    // coordinates must first be converted to centre-line distances.
    const double a = std::abs(point.x - width / 2.0);
    const double b = std::abs(point.y - height / 2.0);
    const double harmonicCentreDistance = a + b <= 1e-15
        ? 0.0
        : 2.0 * a * b / (a + b);
    const double equivalentWallDistance = equivalentRadius - harmonicCentreDistance;

    if (!(equivalentWallDistance > 0.0) || !std::isfinite(equivalentWallDistance)) {
        throw AirflowError(
            ErrorCode::SensorTooCloseToWall,
            "Wei 2019 equivalent wall distance is zero or invalid");
    }

    const double numerator = std::log(equivalentWallDistance) -
                             std::log(absoluteRoughness) + 3.4;
    const double denominator = std::log(equivalentRadius) -
                               std::log(absoluteRoughness) + 1.9;
    const double shapeFactor = numerator / denominator;
    if (!(shapeFactor > 0.0) || !std::isfinite(shapeFactor)) {
        throw AirflowError(
            ErrorCode::ModelNotApplicable,
            "Wei 2019 point-to-mean velocity ratio is not positive and finite");
    }

    return {equivalentRadius, equivalentWallDistance, shapeFactor};
}

} // namespace

ModelMetadata CircularPowerLawModel::metadata() const {
    return {
        "CIRCLE_POWER_1_7",
        "Circular 1/7 power-law full field",
        "1.0.0",
        GeometryType::Circle,
        ModelCapability::FullField,
        "Classical fully-developed turbulent pipe engineering model"
    };
}

ApplicabilityResult CircularPowerLawModel::checkApplicability(
    const Geometry& geometry,
    const SensorMeasurement& sensor,
    double,
    const CalculationOptions&) const {
    if (geometry.type() != GeometryType::Circle) {
        return {false, ErrorCode::ModelNotApplicable, "Model requires circle geometry", "", false};
    }
    if (!geometry.isValid()) {
        return {false, ErrorCode::InvalidGeometry, "Circle geometry is invalid", "", false};
    }
    if (!geometry.contains(sensor.position)) {
        return {false, ErrorCode::SensorOutsideSection, "Sensor is outside the circle", "", false};
    }
    if (!(sensor.velocity > 0.0) || !std::isfinite(sensor.velocity)) {
        return {false, ErrorCode::InvalidArgument, "Measured velocity must be positive", "", false};
    }
    const auto& circle = dynamic_cast<const CircleGeometry&>(geometry);
    const double radial = std::hypot(
        sensor.position.x - circle.center().x,
        sensor.position.y - circle.center().y);
    if (radial >= circle.radius() * (1.0 - 1e-8)) {
        return {false, ErrorCode::SensorTooCloseToWall, "Sensor is on or too close to the wall", "", false};
    }
    return {true, ErrorCode::ModelNotApplicable, "", "C", false};
}

CorrectionResult CircularPowerLawModel::calculate(
    const Geometry& geometry,
    const SensorMeasurement& sensor,
    double inletVelocity,
    const CalculationOptions& options) const {
    const auto applicability = checkApplicability(geometry, sensor, inletVelocity, options);
    if (!applicability.applicable) {
        throw AirflowError(applicability.errorCode, applicability.message);
    }

    const auto& circle = dynamic_cast<const CircleGeometry&>(geometry);
    const auto shape = [&circle](Point point) {
        const double r = std::hypot(
            point.x - circle.center().x,
            point.y - circle.center().y);
        const double normalized = std::clamp(1.0 - r / circle.radius(), 0.0, 1.0);
        return std::pow(normalized, 1.0 / 7.0);
    };

    const double sensorShape = shape(sensor.position);
    if (sensorShape <= 1e-8) {
        throw AirflowError(ErrorCode::SensorTooCloseToWall, "Sensor shape value is too small");
    }

    const int coarseResolution = std::max(20, options.meshResolution);
    const int fineResolution = coarseResolution * 2;
    const double coarseMeanShape = integrateMean(geometry, shape, coarseResolution);
    const double fineMeanShape = integrateMean(geometry, shape, fineResolution);
    const double relativeError = std::abs(fineMeanShape - coarseMeanShape) /
                                 std::max(std::abs(fineMeanShape), 1e-12);
    const bool converged = relativeError <= 0.005;
    if (!converged) {
        throw AirflowError(
            ErrorCode::NumericalIntegrationFailed,
            "Circle field integration did not meet the 0.5% convergence criterion");
    }

    CorrectionResult result;
    result.success = true;
    result.sectionArea = geometry.area();
    result.measuredVelocity = sensor.velocity;
    result.correctionFactor = fineMeanShape / sensorShape;
    result.meanVelocity = sensor.velocity * result.correctionFactor;
    result.airVolume = result.sectionArea * result.meanVelocity;
    result.maximumVelocity = sensor.velocity / sensorShape;
    result.integrationRelativeError = relativeError;
    result.integrationConverged = converged;
    result.confidenceLevel = "C";
    result.model = metadata();
    result.warning = "Engineering 1/7 power-law model; roughness and supports are not represented";
    return result;
}

ModelMetadata RectangularWei2019PointModel::metadata() const {
    return {
        "RECT_WEI2019_POINT",
        "Wei 2019 rectangular equivalent-distance point model",
        "1.0.0",
        GeometryType::Rectangle,
        ModelCapability::FullField,
        "Wei et al., Thermal Science 23(3A) (2019), 1513-1519, equations (5)-(6)"
    };
}

ApplicabilityResult RectangularWei2019PointModel::checkApplicability(
    const Geometry& geometry,
    const SensorMeasurement& sensor,
    double,
    const CalculationOptions& options) const {
    if (geometry.type() != GeometryType::Rectangle) {
        return {false, ErrorCode::ModelNotApplicable, "Model requires rectangle geometry", "", false};
    }
    if (!geometry.isValid()) {
        return {false, ErrorCode::InvalidGeometry, "Rectangle geometry is invalid", "", false};
    }
    if (!geometry.contains(sensor.position)) {
        return {false, ErrorCode::SensorOutsideSection, "Sensor is outside the rectangle", "", false};
    }
    if (!(sensor.velocity > 0.0) || !std::isfinite(sensor.velocity)) {
        return {false, ErrorCode::InvalidArgument, "Measured velocity must be positive", "", false};
    }
    if (!(options.absoluteRoughness > 0.0) || !std::isfinite(options.absoluteRoughness)) {
        return {false, ErrorCode::InvalidArgument, "Absolute roughness must be positive", "", false};
    }

    const auto& rectangle = dynamic_cast<const RectangleGeometry&>(geometry);
    const double equivalentRadius = rectangle.width() * rectangle.height() /
                                    (rectangle.width() + rectangle.height());
    if (options.absoluteRoughness >= equivalentRadius) {
        return {
            false,
            ErrorCode::InvalidArgument,
            "Absolute roughness must be smaller than the equivalent pipe radius",
            "",
            false
        };
    }
    if (rectangle.distanceToBoundary(sensor.position) <= 1e-9) {
        return {
            false,
            ErrorCode::SensorTooCloseToWall,
            "Wei 2019 logarithmic point model cannot be evaluated on a wall",
            "",
            false
        };
    }

    try {
        (void)evaluateWei2019Point(rectangle, sensor.position, options.absoluteRoughness);
    } catch (const AirflowError& error) {
        return {false, error.code(), error.what(), "", false};
    }

    const bool paperGeometry = std::abs(rectangle.width() - 4.94) <= 1e-9 &&
                               std::abs(rectangle.height() - 3.43) <= 1e-9;
    const bool paperRoughnessRange = options.absoluteRoughness >= 0.001 &&
                                     options.absoluteRoughness <= 0.009;
    return {
        true,
        ErrorCode::ModelNotApplicable,
        "",
        paperGeometry && paperRoughnessRange ? "B" : "C",
        false
    };
}

CorrectionResult RectangularWei2019PointModel::calculate(
    const Geometry& geometry,
    const SensorMeasurement& sensor,
    double inletVelocity,
    const CalculationOptions& options) const {
    const auto applicability = checkApplicability(
        geometry, sensor, inletVelocity, options);
    if (!applicability.applicable) {
        throw AirflowError(applicability.errorCode, applicability.message);
    }

    const auto& rectangle = dynamic_cast<const RectangleGeometry&>(geometry);
    const auto sensorEvaluation = evaluateWei2019Point(
        rectangle, sensor.position, options.absoluteRoughness);

    const double meanVelocity = sensor.velocity / sensorEvaluation.shapeFactor;
    const double maximumShape =
        (std::log(sensorEvaluation.equivalentRadius) -
         std::log(options.absoluteRoughness) + 3.4) /
        (std::log(sensorEvaluation.equivalentRadius) -
         std::log(options.absoluteRoughness) + 1.9);

    CorrectionResult result;
    result.success = true;
    result.sectionArea = geometry.area();
    result.measuredVelocity = sensor.velocity;
    result.correctionFactor = 1.0 / sensorEvaluation.shapeFactor;
    result.meanVelocity = meanVelocity;
    result.airVolume = result.sectionArea * result.meanVelocity;
    result.maximumVelocity = meanVelocity * maximumShape;
    result.integrationRelativeError = 0.0;
    result.integrationConverged = true;
    result.interpolationUsed = false;
    result.confidenceLevel = applicability.confidenceLevel;
    result.parameterSetId = std::abs(options.absoluteRoughness - 0.0055) <= 1e-12
        ? "WEI2019_EQ5_EPS_0.0055_REFERENCE"
        : "WEI2019_EQ5_CUSTOM_ROUGHNESS";
    result.model = metadata();

    result.warning =
        "Point model validation: one 4.94 m x 3.43 m roadway, 24 quarter-section points, "
        "mean absolute error about 3.1% and published maximum 8.36%; the formula is not a "
        "validated no-slip near-wall field.";
    if (rectangle.distanceToBoundary(sensor.position) < 0.4) {
        result.warning += " Sensor is closer to a wall than the nearest published test points (0.4 m).";
    }
    if (applicability.confidenceLevel == "C") {
        result.warning += " Geometry or roughness is outside the paper's directly tested configuration.";
    }
    return result;
}

CenterlineCorrectionModel::CenterlineCorrectionModel(
    GeometryType geometryType,
    std::shared_ptr<const ModelRepository> repository)
    : geometryType_(geometryType), repository_(std::move(repository)) {
    if (geometryType_ != GeometryType::Rectangle &&
        geometryType_ != GeometryType::SemicircleArch) {
        throw AirflowError(
            ErrorCode::InvalidArgument,
            "CenterlineCorrectionModel supports only rectangle and semicircle arch");
    }
}

ModelMetadata CenterlineCorrectionModel::metadata() const {
    return {
        directModelId(geometryType_),
        directModelName(geometryType_),
        "1.0.0",
        geometryType_,
        ModelCapability::DirectCorrection,
        "Zhang, Luo & Zou, Energy Science & Engineering 10 (2022), 4150-4175"
    };
}

ApplicabilityResult CenterlineCorrectionModel::checkApplicability(
    const Geometry& geometry,
    const SensorMeasurement& sensor,
    double inletVelocity,
    const CalculationOptions& options) const {
    if (geometry.type() != geometryType_) {
        return {false, ErrorCode::ModelNotApplicable, "Geometry type does not match the model", "", false};
    }
    if (!geometry.isValid()) {
        return {false, ErrorCode::InvalidGeometry, "Geometry is invalid", "", false};
    }
    if (!geometry.contains(sensor.position)) {
        return {false, ErrorCode::SensorOutsideSection, "Sensor is outside the section", "", false};
    }
    if (!(sensor.velocity > 0.0) || !std::isfinite(sensor.velocity)) {
        return {false, ErrorCode::InvalidArgument, "Measured velocity must be positive", "", false};
    }
    if (std::abs(sensor.position.x - geometry.width() / 2.0) > options.centerlineTolerance) {
        return {
            false,
            ErrorCode::SensorNotOnRequiredLine,
            "Zhang 2022 model requires the sensor on the central vertical line",
            "",
            false
        };
    }
    const auto parameters = repository_->findExact(
        geometryType_, geometry.width(), geometry.height(), inletVelocity);
    if (!parameters) {
        return {
            false,
            ErrorCode::ModelNotApplicable,
            "No exact Zhang 2022 parameter set for this width, height and inlet velocity",
            "",
            false
        };
    }
    const double distanceFromRoof = geometry.height() - sensor.position.y;
    if (!(distanceFromRoof > 0.0) || distanceFromRoof > parameters->coreZoneEnd + 1e-9) {
        return {
            false,
            ErrorCode::ModelNotApplicable,
            "Sensor is outside the published roof-to-core fitting interval",
            "",
            false
        };
    }
    return {true, ErrorCode::ModelNotApplicable, "", "A", false};
}

CorrectionResult CenterlineCorrectionModel::calculate(
    const Geometry& geometry,
    const SensorMeasurement& sensor,
    double inletVelocity,
    const CalculationOptions& options) const {
    if (options.returnVelocityField) {
        throw AirflowError(
            ErrorCode::FieldNotSupported,
            "Centerline correction model cannot generate a two-dimensional field");
    }

    const auto applicability = checkApplicability(geometry, sensor, inletVelocity, options);
    if (!applicability.applicable) {
        throw AirflowError(applicability.errorCode, applicability.message);
    }

    const auto parameters = repository_->findExact(
        geometryType_, geometry.width(), geometry.height(), inletVelocity);
    if (!parameters) {
        throw AirflowError(ErrorCode::ModelNotApplicable, "Parameter set disappeared during calculation");
    }

    const double distanceFromRoof = geometry.height() - sensor.position.y;
    double measuredToMeanRatio = 0.0;
    if (distanceFromRoof <= parameters->logZoneEnd) {
        measuredToMeanRatio = parameters->coefficientA +
                              parameters->coefficientB * std::log(distanceFromRoof);
    } else {
        measuredToMeanRatio = parameters->coreRatio;
    }
    if (!(measuredToMeanRatio > 0.0) || !std::isfinite(measuredToMeanRatio)) {
        throw AirflowError(ErrorCode::ModelNotApplicable, "Calculated u/mean ratio is invalid");
    }

    CorrectionResult result;
    result.success = true;
    result.sectionArea = geometry.area();
    result.measuredVelocity = sensor.velocity;
    result.correctionFactor = 1.0 / measuredToMeanRatio;
    result.meanVelocity = sensor.velocity * result.correctionFactor;
    result.airVolume = result.sectionArea * result.meanVelocity;
    result.maximumVelocity = std::numeric_limits<double>::quiet_NaN();
    result.integrationRelativeError = 0.0;
    result.integrationConverged = true;
    result.interpolationUsed = false;
    result.confidenceLevel = applicability.confidenceLevel;
    result.parameterSetId = parameters->id;
    result.model = metadata();
    return result;
}

} // namespace airflow
