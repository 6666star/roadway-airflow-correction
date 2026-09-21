#include "airflow/geometry.hpp"
#include "airflow/repository.hpp"
#include "airflow/service.hpp"
#include "airflow/radial.hpp"

#include <cmath>
#include <iomanip>
#include <iostream>
#include <memory>
#include <sstream>
#include <string>

namespace {

double parseDouble(const char* text, const std::string& name) {
    try {
        std::size_t consumed = 0;
        const std::string value(text);
        const double result = std::stod(value, &consumed);
        if (consumed != value.size() || !std::isfinite(result)) {
            throw std::invalid_argument("not finite");
        }
        return result;
    } catch (...) {
        throw airflow::AirflowError(
            airflow::ErrorCode::InvalidArgument,
            "Invalid numeric argument: " + name);
    }
}

int parseInt(const char* text, const std::string& name) {
    try {
        std::size_t consumed = 0;
        const std::string value(text);
        const int result = std::stoi(value, &consumed);
        if (consumed != value.size()) {
            throw std::invalid_argument("trailing input");
        }
        return result;
    } catch (...) {
        throw airflow::AirflowError(
            airflow::ErrorCode::InvalidArgument,
            "Invalid integer argument: " + name);
    }
}

std::string escapeJson(const std::string& value) {
    std::ostringstream out;
    for (const char c : value) {
        switch (c) {
        case '\\': out << "\\\\"; break;
        case '"': out << "\\\""; break;
        case '\n': out << "\\n"; break;
        case '\r': out << "\\r"; break;
        case '\t': out << "\\t"; break;
        default: out << c; break;
        }
    }
    return out.str();
}

void printResult(const airflow::CorrectionResult& result) {
    std::cout << std::setprecision(15)
              << "{\n"
              << "  \"success\": true,\n"
              << "  \"section_area_m2\": " << result.sectionArea << ",\n"
              << "  \"radial_eta\": " << result.radialEta << ",\n"
              << "  \"equivalent_radius_m\": " << result.equivalentRadius << ",\n"
              << "  \"equivalent_wall_distance_m\": " << result.equivalentWallDistance << ",\n"
              << "  \"true_wall_distance_m\": " << result.trueWallDistance << ",\n"
              << "  \"measured_velocity_mps\": " << result.measuredVelocity << ",\n"
              << "  \"correction_factor\": " << result.correctionFactor << ",\n"
              << "  \"mean_velocity_mps\": " << result.meanVelocity << ",\n"
              << "  \"air_volume_m3ps\": " << result.airVolume << ",\n"
              << "  \"integration_relative_error\": " << result.integrationRelativeError << ",\n"
              << "  \"integration_converged\": " << (result.integrationConverged ? "true" : "false") << ",\n"
              << "  \"confidence_level\": \"" << escapeJson(result.confidenceLevel) << "\",\n"
              << "  \"model_id\": \"" << escapeJson(result.model.id) << "\",\n"
              << "  \"model_capability\": \"" << airflow::toString(result.model.capability) << "\",\n"
              << "  \"parameter_set_id\": \"" << escapeJson(result.parameterSetId) << "\",\n"
              << "  \"warning\": \"" << escapeJson(result.warning) << "\"\n"
              << "}\n";
}

void printUsage() {
    std::cerr
        << "Usage:\n"
        << "  airflow_cli rectangle-wei-radial W H x y velocity roughness [center_x center_y]\n"
        << "  airflow_cli semicircle-wei-radial W H x y velocity roughness [center_x center_y]\n"
        << "  airflow_cli trapezoid-wei-radial bottom top H x y velocity roughness [center_x center_y]\n"
        << "  airflow_cli three-center-wei-radial W wall rise R r x y velocity roughness [center_x center_y]\n"
        << "  airflow_cli circle R sensor_x sensor_y measured_velocity [mesh_resolution]\n"
        << "  airflow_cli rectangle-wei2019 W H sensor_x sensor_y measured_velocity [roughness_m]\n"
        << "  airflow_cli rectangle W H sensor_x sensor_y measured_velocity inlet_velocity\n"
        << "  airflow_cli semicircle W H sensor_x sensor_y measured_velocity inlet_velocity\n";
}

} // namespace

int main(int argc, char** argv) {
    try {
        if (argc < 2) {
            printUsage();
            return 2;
        }

        const std::string geometryType(argv[1]);
        airflow::CorrectionCommand command;

        if (geometryType.ends_with("-wei-radial")) {
            const int dims = geometryType == "three-center-wei-radial" ? 5 :
                             geometryType == "trapezoid-wei-radial" ? 3 : 2;
            if (argc != dims+6 && argc != dims+8)
                throw airflow::AirflowError(airflow::ErrorCode::InvalidArgument,"Radial command requires geometry, x y velocity roughness, optional center_x center_y");
            auto d = [&](int i) { return parseDouble(argv[2+i],"geometry dimension"); };
            using G = airflow::RadialGeometry;
            if (geometryType=="rectangle-wei-radial")
                command.geometry=std::make_shared<G>(G::rectangle(d(0),d(1)));
            else if (geometryType=="semicircle-wei-radial")
                command.geometry=std::make_shared<G>(G::semicircle(d(0),d(1)));
            else if (geometryType=="trapezoid-wei-radial")
                command.geometry=std::make_shared<G>(G::trapezoid(d(0),d(1),d(2)));
            else if (geometryType=="three-center-wei-radial")
                command.geometry=std::make_shared<G>(G::threeCenter(d(0),d(1),d(2),d(3),d(4)));
            else throw airflow::AirflowError(airflow::ErrorCode::InvalidArgument,"Unknown radial shape");
            command.sensor.position={parseDouble(argv[2+dims],"x"),parseDouble(argv[3+dims],"y")};
            command.sensor.velocity=parseDouble(argv[4+dims],"velocity");
            command.options.absoluteRoughness=parseDouble(argv[5+dims],"roughness");
            if(argc==dims+8) {
                command.options.useMappingCenter=true;
                command.options.mappingCenter={parseDouble(argv[6+dims],"center_x"),parseDouble(argv[7+dims],"center_y")};
            }
            command.modelId=airflow::toString(command.geometry->type())+"_WEI_RADIAL";
        } else if (geometryType == "circle") {
            if (argc != 7 && argc != 8) {
                printUsage();
                return 2;
            }
            const double radius = parseDouble(argv[2], "R");
            command.geometry = std::make_shared<airflow::CircleGeometry>(radius);
            command.sensor.position = {
                parseDouble(argv[3], "sensor_x"),
                parseDouble(argv[4], "sensor_y")
            };
            command.sensor.velocity = parseDouble(argv[5], "measured_velocity");
            command.inletVelocity = 0.0;
            command.options.meshResolution = parseInt(argv[6], "mesh_resolution");
            if (argc == 8) {
                throw airflow::AirflowError(
                    airflow::ErrorCode::InvalidArgument,
                    "Unexpected extra circle argument");
            }
        } else if (geometryType == "rectangle-wei2019") {
            if (argc != 7 && argc != 8) {
                printUsage();
                return 2;
            }
            command.geometry = std::make_shared<airflow::RectangleGeometry>(
                parseDouble(argv[2], "W"),
                parseDouble(argv[3], "H"));
            command.sensor.position = {
                parseDouble(argv[4], "sensor_x"),
                parseDouble(argv[5], "sensor_y")
            };
            command.sensor.velocity = parseDouble(argv[6], "measured_velocity");
            command.inletVelocity = 0.0;
            command.modelId = "RECT_WEI2019_POINT";
            if (argc == 8) {
                command.options.absoluteRoughness = parseDouble(argv[7], "roughness_m");
            }
        } else if (geometryType == "rectangle" || geometryType == "semicircle") {
            if (argc != 8) {
                printUsage();
                return 2;
            }
            const double width = parseDouble(argv[2], "W");
            const double height = parseDouble(argv[3], "H");
            if (geometryType == "rectangle") {
                command.geometry = std::make_shared<airflow::RectangleGeometry>(width, height);
            } else {
                command.geometry = std::make_shared<airflow::SemicircleArchGeometry>(width, height);
            }
            command.sensor.position = {
                parseDouble(argv[4], "sensor_x"),
                parseDouble(argv[5], "sensor_y")
            };
            command.sensor.velocity = parseDouble(argv[6], "measured_velocity");
            command.inletVelocity = parseDouble(argv[7], "inlet_velocity");
        } else {
            throw airflow::AirflowError(
                airflow::ErrorCode::InvalidArgument,
                "Unknown geometry command: " + geometryType);
        }

        auto repository = std::make_shared<airflow::ModelRepository>();
        airflow::ModelRegistry registry(repository);
        airflow::AirflowCorrectionService service(std::move(registry));
        printResult(service.calculate(command));
        return 0;
    } catch (const airflow::AirflowError& error) {
        std::cout << "{\n"
                  << "  \"success\": false,\n"
                  << "  \"error_code\": \"" << airflow::toString(error.code()) << "\",\n"
                  << "  \"message\": \"" << escapeJson(error.what()) << "\"\n"
                  << "}\n";
        return 1;
    } catch (const std::exception& error) {
        std::cout << "{\n"
                  << "  \"success\": false,\n"
                  << "  \"error_code\": \"INTERNAL_ERROR\",\n"
                  << "  \"message\": \"" << escapeJson(error.what()) << "\"\n"
                  << "}\n";
        return 1;
    }
}
