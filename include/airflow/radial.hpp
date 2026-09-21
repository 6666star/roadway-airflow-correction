#pragma once
#include "airflow/model.hpp"
#include <vector>
namespace airflow {
struct BoundaryPiece { Point a,b,center; double radius{},start{},end{}; };
class RadialGeometry final : public Geometry {
public:
    static RadialGeometry rectangle(double w,double h);
    static RadialGeometry semicircle(double w,double h);
    static RadialGeometry trapezoid(double bottom,double top,double h);
    static RadialGeometry threeCenter(double w,double wall,double rise,double R,double r);
    GeometryType type() const override { return type_; }
    bool isValid() const override;
    double area() const override { return area_; }
    bool contains(Point p) const override;
    double distanceToBoundary(Point p) const override;
    Bounds bounds() const override;
    double width() const override { return width_; }
    double height() const override { return height_; }
    double perimeter() const { return perimeter_; }
    Point mappingCenter() const { return {width_/2,height_/2}; }
    double rayDistance(Point center,Point unitDirection) const;
private:
    GeometryType type_{};
    double width_{},height_{},top_{},wall_{},rise_{},crown_{},side_{},joinX_{};
    double area_{},perimeter_{};
    std::vector<BoundaryPiece> pieces_;
    void line(Point a,Point b);
    void arc(Point center,double radius,double start,double end);
};
struct RadialMapping { double eta{},equivalentRadius{},equivalentWallDistance{},trueWallDistance{}; };
RadialMapping mapRadial(const RadialGeometry&,Point,Point center);
class RadialWeiModel final : public AirflowModel {
public:
    explicit RadialWeiModel(GeometryType type):type_(type) {}
    ModelMetadata metadata() const override;
    ApplicabilityResult checkApplicability(const Geometry&,const SensorMeasurement&,double,const CalculationOptions&) const override;
    CorrectionResult calculate(const Geometry&,const SensorMeasurement&,double,const CalculationOptions&) const override;
private:
    GeometryType type_;
};
}
