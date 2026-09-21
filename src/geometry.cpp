#include "airflow/geometry.hpp"

#include <algorithm>
#include <cmath>
#include <numbers>

namespace airflow {
namespace {

double distance(Point a, Point b) {
    return std::hypot(a.x - b.x, a.y - b.y);
}

double distanceToSegment(Point p, Point a, Point b) {
    const double dx = b.x - a.x;
    const double dy = b.y - a.y;
    const double lengthSquared = dx * dx + dy * dy;
    if (lengthSquared == 0.0) {
        return distance(p, a);
    }
    const double t = std::clamp(
        ((p.x - a.x) * dx + (p.y - a.y) * dy) / lengthSquared,
        0.0,
        1.0);
    return distance(p, {a.x + t * dx, a.y + t * dy});
}

} // namespace

CircleGeometry::CircleGeometry(double radius, Point center)
    : radius_(radius), center_(center) {}

GeometryType CircleGeometry::type() const { return GeometryType::Circle; }
bool CircleGeometry::isValid() const { return std::isfinite(radius_) && radius_ > 0.0; }
double CircleGeometry::area() const { return std::numbers::pi * radius_ * radius_; }
bool CircleGeometry::contains(Point point) const {
    return distance(point, center_) <= radius_ + 1e-12;
}
double CircleGeometry::distanceToBoundary(Point point) const {
    return std::max(0.0, radius_ - distance(point, center_));
}
Bounds CircleGeometry::bounds() const {
    return {center_.x - radius_, center_.y - radius_, center_.x + radius_, center_.y + radius_};
}
double CircleGeometry::width() const { return 2.0 * radius_; }
double CircleGeometry::height() const { return 2.0 * radius_; }
double CircleGeometry::radius() const { return radius_; }
Point CircleGeometry::center() const { return center_; }

RectangleGeometry::RectangleGeometry(double width, double height)
    : width_(width), height_(height) {}

GeometryType RectangleGeometry::type() const { return GeometryType::Rectangle; }
bool RectangleGeometry::isValid() const {
    return std::isfinite(width_) && std::isfinite(height_) && width_ > 0.0 && height_ > 0.0;
}
double RectangleGeometry::area() const { return width_ * height_; }
bool RectangleGeometry::contains(Point point) const {
    return point.x >= 0.0 && point.x <= width_ && point.y >= 0.0 && point.y <= height_;
}
double RectangleGeometry::distanceToBoundary(Point point) const {
    if (!contains(point)) {
        return 0.0;
    }
    return std::min({point.x, width_ - point.x, point.y, height_ - point.y});
}
Bounds RectangleGeometry::bounds() const { return {0.0, 0.0, width_, height_}; }
double RectangleGeometry::width() const { return width_; }
double RectangleGeometry::height() const { return height_; }

SemicircleArchGeometry::SemicircleArchGeometry(double width, double totalHeight)
    : width_(width), totalHeight_(totalHeight) {}

GeometryType SemicircleArchGeometry::type() const { return GeometryType::SemicircleArch; }
bool SemicircleArchGeometry::isValid() const {
    return std::isfinite(width_) && std::isfinite(totalHeight_) &&
           width_ > 0.0 && totalHeight_ >= width_ / 2.0;
}
double SemicircleArchGeometry::area() const {
    const double r = radius();
    return width_ * wallHeight() + 0.5 * std::numbers::pi * r * r;
}
bool SemicircleArchGeometry::contains(Point point) const {
    if (point.x < 0.0 || point.x > width_ || point.y < 0.0 || point.y > totalHeight_) {
        return false;
    }
    if (point.y <= wallHeight()) {
        return true;
    }
    const double dx = point.x - width_ / 2.0;
    const double dy = point.y - wallHeight();
    return dx * dx + dy * dy <= radius() * radius() + 1e-12;
}
double SemicircleArchGeometry::distanceToBoundary(Point point) const {
    if (!contains(point)) {
        return 0.0;
    }

    const double r = radius();
    const double h = wallHeight();
    const Point leftBottom{0.0, 0.0};
    const Point rightBottom{width_, 0.0};
    const Point leftSpring{0.0, h};
    const Point rightSpring{width_, h};

    const double bottom = distanceToSegment(point, leftBottom, rightBottom);
    const double leftWall = distanceToSegment(point, leftBottom, leftSpring);
    const double rightWall = distanceToSegment(point, rightBottom, rightSpring);

    const double radial = std::hypot(point.x - width_ / 2.0, point.y - h);
    double arch = std::abs(r - radial);
    if (point.y < h) {
        arch = std::min(distance(point, leftSpring), distance(point, rightSpring));
    }
    return std::min({bottom, leftWall, rightWall, arch});
}
Bounds SemicircleArchGeometry::bounds() const { return {0.0, 0.0, width_, totalHeight_}; }
double SemicircleArchGeometry::width() const { return width_; }
double SemicircleArchGeometry::height() const { return totalHeight_; }
double SemicircleArchGeometry::radius() const { return width_ / 2.0; }
double SemicircleArchGeometry::wallHeight() const { return totalHeight_ - radius(); }

} // namespace airflow

