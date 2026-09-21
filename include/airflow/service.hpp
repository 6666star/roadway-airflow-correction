#pragma once

#include "airflow/model.hpp"

#include <memory>
#include <string>
#include <unordered_map>
#include <vector>

namespace airflow {

struct CorrectionCommand {
    std::shared_ptr<const Geometry> geometry;
    SensorMeasurement sensor;
    double inletVelocity{};
    std::string modelId{"AUTO"};
    CalculationOptions options;
};

class ModelRegistry {
public:
    explicit ModelRegistry(std::shared_ptr<const ModelRepository> repository);

    [[nodiscard]] std::shared_ptr<const AirflowModel> findById(
        const std::string& id) const;

    [[nodiscard]] std::shared_ptr<const AirflowModel> selectAutomatically(
        GeometryType type) const;

    [[nodiscard]] std::vector<ModelMetadata> list() const;

private:
    std::unordered_map<std::string, std::shared_ptr<const AirflowModel>> models_;
};

class AirflowCorrectionService {
public:
    explicit AirflowCorrectionService(ModelRegistry registry);

    [[nodiscard]] CorrectionResult calculate(const CorrectionCommand& command) const;

private:
    ModelRegistry registry_;
};

} // namespace airflow

