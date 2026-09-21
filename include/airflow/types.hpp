#pragma once

#include <stdexcept>
#include <string>

namespace airflow {

enum class GeometryType {
    Circle,
    Rectangle,
    SemicircleArch,
    Trapezoid,
    ThreeCenterArch
};

enum class ModelCapability {
    FullField,
    DirectCorrection,
    NotImplemented
};

enum class ErrorCode {
    InvalidArgument,
    InvalidGeometry,
    SensorOutsideSection,
    SensorTooCloseToWall,
    SensorNotOnRequiredLine,
    ModelNotFound,
    ModelNotApplicable,
    FieldNotSupported,
    ParameterInterpolationRequired,
    NumericalIntegrationFailed
};

struct Point {
    double x{};
    double y{};
};

struct Bounds {
    double minX{};
    double minY{};
    double maxX{};
    double maxY{};
};

struct SensorMeasurement {
    Point position;
    double velocity{};
};

struct CalculationOptions {
    bool useMappingCenter{false};
    Point mappingCenter{};
    int meshResolution{300};
    double centerlineTolerance{0.02};
    double absoluteRoughness{0.0055};
    bool returnVelocityField{false};
    bool allowInterpolation{false};
};

struct ModelMetadata {
    std::string id;
    std::string name;
    std::string version;
    GeometryType geometryType{};
    ModelCapability capability{};
    std::string source;
};

struct ApplicabilityResult {
    bool applicable{};
    ErrorCode errorCode{ErrorCode::ModelNotApplicable};
    std::string message;
    std::string confidenceLevel;
    bool interpolationUsed{};
};

struct CorrectionResult {
    double radialEta{}, equivalentRadius{}, equivalentWallDistance{}, trueWallDistance{};
    bool success{};
    double sectionArea{};
    double measuredVelocity{};
    double correctionFactor{};
    double meanVelocity{};
    double airVolume{};
    double maximumVelocity{};
    double integrationRelativeError{};
    bool integrationConverged{};
    bool interpolationUsed{};
    std::string confidenceLevel;
    std::string parameterSetId;
    ModelMetadata model;
    std::string warning;
};

class AirflowError : public std::runtime_error {
public:
    AirflowError(ErrorCode code, const std::string& message)
        : std::runtime_error(message), code_(code) {}

    [[nodiscard]] ErrorCode code() const noexcept { return code_; }

private:
    ErrorCode code_;
};

std::string toString(GeometryType type);
std::string toString(ModelCapability capability);
std::string toString(ErrorCode code);

} // namespace airflow
