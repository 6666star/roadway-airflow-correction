#include "airflow/service.hpp"
#include "airflow/radial.hpp"

#include <cmath>

namespace airflow {

std::string toString(GeometryType type) {
    switch (type) {
    case GeometryType::Circle: return "CIRCLE";
    case GeometryType::Rectangle: return "RECTANGLE";
    case GeometryType::SemicircleArch: return "SEMICIRCLE_ARCH";
    case GeometryType::Trapezoid: return "TRAPEZOID";
    case GeometryType::ThreeCenterArch: return "THREE_CENTER_ARCH";
    }
    return "UNKNOWN";
}

std::string toString(ModelCapability capability) {
    switch (capability) {
    case ModelCapability::FullField: return "FULL_FIELD";
    case ModelCapability::DirectCorrection: return "DIRECT_CORRECTION";
    case ModelCapability::NotImplemented: return "NOT_IMPLEMENTED";
    }
    return "UNKNOWN";
}

std::string toString(ErrorCode code) {
    switch (code) {
    case ErrorCode::InvalidArgument: return "INVALID_ARGUMENT";
    case ErrorCode::InvalidGeometry: return "INVALID_GEOMETRY";
    case ErrorCode::SensorOutsideSection: return "SENSOR_OUTSIDE_SECTION";
    case ErrorCode::SensorTooCloseToWall: return "SENSOR_TOO_CLOSE_TO_WALL";
    case ErrorCode::SensorNotOnRequiredLine: return "SENSOR_NOT_ON_REQUIRED_LINE";
    case ErrorCode::ModelNotFound: return "MODEL_NOT_FOUND";
    case ErrorCode::ModelNotApplicable: return "MODEL_NOT_APPLICABLE";
    case ErrorCode::FieldNotSupported: return "FIELD_NOT_SUPPORTED";
    case ErrorCode::ParameterInterpolationRequired: return "PARAMETER_INTERPOLATION_REQUIRED";
    case ErrorCode::NumericalIntegrationFailed: return "NUMERICAL_INTEGRATION_FAILED";
    }
    return "UNKNOWN";
}

ModelRegistry::ModelRegistry(std::shared_ptr<const ModelRepository> repository) {
    for (auto type : {GeometryType::Rectangle, GeometryType::SemicircleArch, GeometryType::Trapezoid, GeometryType::ThreeCenterArch}) {
        auto radial = std::make_shared<RadialWeiModel>(type);
        models_.emplace(radial->metadata().id, radial);
    }
    auto circle = std::make_shared<CircularPowerLawModel>();
    auto rectanglePoint = std::make_shared<RectangularWei2019PointModel>();
    auto rectangle = std::make_shared<CenterlineCorrectionModel>(
        GeometryType::Rectangle, repository);
    auto semicircle = std::make_shared<CenterlineCorrectionModel>(
        GeometryType::SemicircleArch, std::move(repository));

    models_.emplace(circle->metadata().id, circle);
    models_.emplace(rectanglePoint->metadata().id, rectanglePoint);
    models_.emplace(rectangle->metadata().id, rectangle);
    models_.emplace(semicircle->metadata().id, semicircle);
}

std::shared_ptr<const AirflowModel> ModelRegistry::findById(const std::string& id) const {
    const auto found = models_.find(id);
    if (found == models_.end()) {
        throw AirflowError(ErrorCode::ModelNotFound, "Unknown model id: " + id);
    }
    return found->second;
}

std::shared_ptr<const AirflowModel> ModelRegistry::selectAutomatically(GeometryType type) const {
    switch (type) {
    case GeometryType::Circle:
        return findById("CIRCLE_POWER_1_7");
    case GeometryType::Rectangle:
        return findById("RECT_ZHANG2022_CENTERLINE");
    case GeometryType::SemicircleArch:
        return findById("SEMICIRCLE_ZHANG2022_CENTERLINE");
    case GeometryType::Trapezoid:
    case GeometryType::ThreeCenterArch:
        return findById(toString(type)+"_WEI_RADIAL");
    }
    throw AirflowError(ErrorCode::ModelNotApplicable, "Unsupported geometry type");
}

std::vector<ModelMetadata> ModelRegistry::list() const {
    std::vector<ModelMetadata> result;
    result.reserve(models_.size());
    for (const auto& [id, model] : models_) {
        (void)id;
        result.push_back(model->metadata());
    }
    return result;
}

AirflowCorrectionService::AirflowCorrectionService(ModelRegistry registry)
    : registry_(std::move(registry)) {}

CorrectionResult AirflowCorrectionService::calculate(const CorrectionCommand& command) const {
    if (!command.geometry) {
        throw AirflowError(ErrorCode::InvalidArgument, "Geometry is required");
    }
    if (!command.geometry->isValid()) {
        throw AirflowError(ErrorCode::InvalidGeometry, "Geometry is invalid");
    }
    if (!std::isfinite(command.sensor.velocity) || command.sensor.velocity <= 0.0) {
        throw AirflowError(ErrorCode::InvalidArgument, "Measured velocity must be positive");
    }
    if (!command.geometry->contains(command.sensor.position)) {
        throw AirflowError(ErrorCode::SensorOutsideSection, "Sensor is outside the section");
    }

    const auto model = command.modelId == "AUTO"
        ? registry_.selectAutomatically(command.geometry->type())
        : registry_.findById(command.modelId);

    return model->calculate(
        *command.geometry,
        command.sensor,
        command.inletVelocity,
        command.options);
}

} // namespace airflow
