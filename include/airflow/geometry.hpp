#pragma once

#include "airflow/types.hpp"

#include <memory>

namespace airflow {

class Geometry {
public:
    virtual ~Geometry() = default;

    [[nodiscard]] virtual GeometryType type() const = 0;
    [[nodiscard]] virtual bool isValid() const = 0;
    [[nodiscard]] virtual double area() const = 0;
    [[nodiscard]] virtual bool contains(Point point) const = 0;
    [[nodiscard]] virtual double distanceToBoundary(Point point) const = 0;
    [[nodiscard]] virtual Bounds bounds() const = 0;
    [[nodiscard]] virtual double width() const = 0;
    [[nodiscard]] virtual double height() const = 0;
};

class CircleGeometry final : public Geometry {
public:
    CircleGeometry(double radius, Point center = {0.0, 0.0});

    [[nodiscard]] GeometryType type() const override;
    [[nodiscard]] bool isValid() const override;
    [[nodiscard]] double area() const override;
    [[nodiscard]] bool contains(Point point) const override;
    [[nodiscard]] double distanceToBoundary(Point point) const override;
    [[nodiscard]] Bounds bounds() const override;
    [[nodiscard]] double width() const override;
    [[nodiscard]] double height() const override;
    [[nodiscard]] double radius() const;
    [[nodiscard]] Point center() const;

private:
    double radius_;
    Point center_;
};

class RectangleGeometry final : public Geometry {
public:
    RectangleGeometry(double width, double height);

    [[nodiscard]] GeometryType type() const override;
    [[nodiscard]] bool isValid() const override;
    [[nodiscard]] double area() const override;
    [[nodiscard]] bool contains(Point point) const override;
    [[nodiscard]] double distanceToBoundary(Point point) const override;
    [[nodiscard]] Bounds bounds() const override;
    [[nodiscard]] double width() const override;
    [[nodiscard]] double height() const override;

private:
    double width_;
    double height_;
};

// 坐标原点位于左下角。断面由直墙矩形和顶部半圆组成。
// 圆弧半径 R=W/2，直墙高度 wallHeight=H-R。
class SemicircleArchGeometry final : public Geometry {
public:
    SemicircleArchGeometry(double width, double totalHeight);

    [[nodiscard]] GeometryType type() const override;
    [[nodiscard]] bool isValid() const override;
    [[nodiscard]] double area() const override;
    [[nodiscard]] bool contains(Point point) const override;
    [[nodiscard]] double distanceToBoundary(Point point) const override;
    [[nodiscard]] Bounds bounds() const override;
    [[nodiscard]] double width() const override;
    [[nodiscard]] double height() const override;
    [[nodiscard]] double radius() const;
    [[nodiscard]] double wallHeight() const;

private:
    double width_;
    double totalHeight_;
};

} // namespace airflow

