#pragma once

#include "airflow/geometry.hpp"
#include "airflow/repository.hpp"
#include "airflow/types.hpp"

#include <memory>
#include <string>

namespace airflow {

class AirflowModel {
public:
    virtual ~AirflowModel() = default;

    [[nodiscard]] virtual ModelMetadata metadata() const = 0;

    [[nodiscard]] virtual ApplicabilityResult checkApplicability(
        const Geometry& geometry,
        const SensorMeasurement& sensor,
        double inletVelocity,
        const CalculationOptions& options) const = 0;

    [[nodiscard]] virtual CorrectionResult calculate(
        const Geometry& geometry,
        const SensorMeasurement& sensor,
        double inletVelocity,
        const CalculationOptions& options) const = 0;
};

class CircularPowerLawModel final : public AirflowModel {
public:
    [[nodiscard]] ModelMetadata metadata() const override;
    [[nodiscard]] ApplicabilityResult checkApplicability(
        const Geometry& geometry,
        const SensorMeasurement& sensor,
        double inletVelocity,
        const CalculationOptions& options) const override;
    [[nodiscard]] CorrectionResult calculate(
        const Geometry& geometry,
        const SensorMeasurement& sensor,
        double inletVelocity,
        const CalculationOptions& options) const override;
};

// Wei et al. (2019) rectangular point-wind model. The paper maps a point in a
// rectangle to an equivalent circular-pipe wall distance and applies a rough
// pipe logarithmic law. Coordinates use the project's lower-left origin.
class RectangularWei2019PointModel final : public AirflowModel {
public:
    [[nodiscard]] ModelMetadata metadata() const override;
    [[nodiscard]] ApplicabilityResult checkApplicability(
        const Geometry& geometry,
        const SensorMeasurement& sensor,
        double inletVelocity,
        const CalculationOptions& options) const override;
    [[nodiscard]] CorrectionResult calculate(
        const Geometry& geometry,
        const SensorMeasurement& sensor,
        double inletVelocity,
        const CalculationOptions& options) const override;
};

class CenterlineCorrectionModel final : public AirflowModel {
public:
    CenterlineCorrectionModel(
        GeometryType geometryType,
        std::shared_ptr<const ModelRepository> repository);

    [[nodiscard]] ModelMetadata metadata() const override;
    [[nodiscard]] ApplicabilityResult checkApplicability(
        const Geometry& geometry,
        const SensorMeasurement& sensor,
        double inletVelocity,
        const CalculationOptions& options) const override;
    [[nodiscard]] CorrectionResult calculate(
        const Geometry& geometry,
        const SensorMeasurement& sensor,
        double inletVelocity,
        const CalculationOptions& options) const override;

private:
    GeometryType geometryType_;
    std::shared_ptr<const ModelRepository> repository_;
};

} // namespace airflow
