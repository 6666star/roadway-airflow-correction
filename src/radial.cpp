#include "airflow/radial.hpp"
#include <algorithm>
#include <cmath>
#include <limits>
#include <numbers>

namespace airflow {
namespace {
constexpr double pi=std::numbers::pi;
Point sub(Point a,Point b) { return {a.x-b.x,a.y-b.y}; }
double dot(Point a,Point b) { return a.x*b.x+a.y*b.y; }
double cross(Point a,Point b) { return a.x*b.y-a.y*b.x; }
double norm(Point a) { return std::hypot(a.x,a.y); }
bool finite(Point p) { return std::isfinite(p.x)&&std::isfinite(p.y); }
void require(bool ok) { if(!ok) throw AirflowError(ErrorCode::InvalidGeometry,"Invalid dimensions or three-center arc tangency"); }
bool positive(double v) { return std::isfinite(v)&&v>0; }
bool onArc(const BoundaryPiece& p,Point x) {
    double a=std::atan2(x.y-p.center.y,x.x-p.center.x);
    if(a < -1e-12) a+=2*pi;
    return a>=p.start-1e-10 && a<=p.end+1e-10;
}
}
void RadialGeometry::line(Point a,Point b) {
    pieces_.push_back({a,b,{},0,0,0});
    area_+=cross(a,b)/2; perimeter_+=norm(sub(b,a));
}
void RadialGeometry::arc(Point c,double r,double a,double b) {
    pieces_.push_back({{},{},c,r,a,b});
    area_+=(r*c.x*(std::sin(b)-std::sin(a))+r*c.y*(std::cos(a)-std::cos(b))+r*r*(b-a))/2;
    perimeter_+=r*(b-a);
}
RadialGeometry RadialGeometry::rectangle(double w,double h) {
    require(positive(w)&&positive(h)); RadialGeometry g;
    g.type_=GeometryType::Rectangle; g.width_=w; g.height_=h;
    g.line({0,0},{w,0}); g.line({w,0},{w,h}); g.line({w,h},{0,h}); g.line({0,h},{0,0}); return g;
}
RadialGeometry RadialGeometry::trapezoid(double b,double t,double h) {
    require(positive(b)&&positive(t)&&positive(h)); RadialGeometry g;
    g.type_=GeometryType::Trapezoid; g.width_=b; g.top_=t; g.height_=h;
    g.line({0,0},{b,0}); g.line({b,0},{(b+t)/2,h}); g.line({(b+t)/2,h},{(b-t)/2,h}); g.line({(b-t)/2,h},{0,0}); return g;
}
RadialGeometry RadialGeometry::semicircle(double w,double h) {
    require(positive(w)&&positive(h)&&h>=w/2); RadialGeometry g;
    g.type_=GeometryType::SemicircleArch; g.width_=w; g.height_=h; g.wall_=h-w/2;
    g.line({0,0},{w,0});
    if(g.wall_>0) g.line({w,0},{w,g.wall_});
    g.arc({w/2,g.wall_},w/2,0,pi);
    if(g.wall_>0) g.line({0,g.wall_},{0,0});
    return g;
}
RadialGeometry RadialGeometry::threeCenter(double w,double h,double f,double R,double r) {
    require(positive(w)&&std::isfinite(h)&&h>=0&&positive(f)&&positive(R)&&positive(r)&&R>r&&r<w/2&&R>f);
    const double dx=w/2-r,dy=R-f,d=std::hypot(dx,dy);
    require(std::abs(d-(R-r))<=1e-8*std::max({w,R,r}));
    RadialGeometry g; g.type_=GeometryType::ThreeCenterArch;
    g.width_=w; g.height_=h+f; g.wall_=h; g.rise_=f; g.crown_=R; g.side_=r;
    g.joinX_=R*dx/d;
    const double a=std::atan2(dy,dx);
    g.line({0,0},{w,0});
    if(h>0) g.line({w,0},{w,h});
    g.arc({w-r,h},r,0,a); g.arc({w/2,h+f-R},R,a,pi-a);
    g.arc({r,h},r,pi-a,pi);
    if(h>0) g.line({0,h},{0,0});
    return g;
}
bool RadialGeometry::isValid() const { return positive(area_)&&positive(perimeter_)&&positive(height_); }
Bounds RadialGeometry::bounds() const {
    double extra=type_==GeometryType::Trapezoid?std::max(0.0,(top_-width_)/2):0;
    return {-extra,0,width_+extra,height_};
}
bool RadialGeometry::contains(Point p) const {
    if(!finite(p)||p.y<0||p.y>height_) return false;
    const double x=std::abs(p.x-width_/2);
    if(type_==GeometryType::Trapezoid) return x<=(width_+(top_-width_)*p.y/height_)/2;
    if(x>width_/2) return false;
    if(type_==GeometryType::Rectangle||p.y<=wall_) return true;
    if(type_==GeometryType::SemicircleArch) return std::hypot(x,p.y-wall_)<=width_/2;
    if(x<=joinX_) return p.y<=wall_+rise_-crown_+std::sqrt(std::max(0.0,crown_*crown_-x*x));
    const double dx=x-(width_/2-side_);
    return p.y<=wall_+std::sqrt(std::max(0.0,side_*side_-dx*dx));
}
double RadialGeometry::distanceToBoundary(Point x) const {
    double best=std::numeric_limits<double>::infinity();
    for(const auto& p:pieces_) {
        if(p.radius==0) {
            Point s=sub(p.b,p.a); double u=std::clamp(dot(sub(x,p.a),s)/dot(s,s),0.0,1.0);
            best=std::min(best,norm(sub(x,{p.a.x+u*s.x,p.a.y+u*s.y})));
        } else {
            if(onArc(p,x)) best=std::min(best,std::abs(norm(sub(x,p.center))-p.radius));
            for(double a:{p.start,p.end}) best=std::min(best,norm(sub(x,{p.center.x+p.radius*std::cos(a),p.center.y+p.radius*std::sin(a)})));
        }
    }
    return best;
}
double RadialGeometry::rayDistance(Point c,Point e) const {
    if(!contains(c)||distanceToBoundary(c)<=1e-12||!finite(e)||std::abs(norm(e)-1)>1e-8)
        throw AirflowError(ErrorCode::InvalidArgument,"Ray requires interior center and unit direction");
    double best=std::numeric_limits<double>::infinity();
    for(const auto& p:pieces_) {
        if(p.radius==0) {
            const Point s=sub(p.b,p.a),q=sub(p.a,c); const double den=cross(e,s);
            if(std::abs(den)<1e-14*norm(s)) continue;
            const double t=cross(q,s)/den,u=cross(q,e)/den;
            if(t>0&&u>=-1e-10&&u<=1+1e-10) best=std::min(best,t);
        } else {
            Point q=sub(c,p.center); double b=dot(q,e),disc=b*b-dot(q,q)+p.radius*p.radius;
            if(disc<0) continue;
            for(double t:{-b-std::sqrt(disc),-b+std::sqrt(disc)})
                if(t>0&&onArc(p,{c.x+t*e.x,c.y+t*e.y})) best=std::min(best,t);
        }
    }
    if(!std::isfinite(best)) throw AirflowError(ErrorCode::InvalidGeometry,"No ray boundary intersection");
    return best;
}
RadialMapping mapRadial(const RadialGeometry& g,Point p,Point c) {
    if(!g.contains(p)) throw AirflowError(ErrorCode::SensorOutsideSection,"Sensor outside section");
    if(!g.contains(c)||g.distanceToBoundary(c)<=1e-12) throw AirflowError(ErrorCode::InvalidArgument,"Mapping center must be strictly interior");
    Point q=sub(p,c); const double rho=norm(q),r0=2*g.area()/g.perimeter();
    const double eta=rho==0?0:rho/g.rayDistance(c,{q.x/rho,q.y/rho});
    return {eta,r0,r0*(1-eta),g.distanceToBoundary(p)};
}
ModelMetadata RadialWeiModel::metadata() const {
    return {toString(type_)+"_WEI_RADIAL","Wei rough-pipe law with radial section mapping","2.0.0",type_,ModelCapability::DirectCorrection,"Wei 2019 Eq.(5); new radial geometry extension"};
}
ApplicabilityResult RadialWeiModel::checkApplicability(const Geometry& g,const SensorMeasurement& s,double,const CalculationOptions& o) const {
    try { (void)calculate(g,s,0,o); }
    catch(const AirflowError& e) { return {false,e.code(),e.what(),"",false}; }
    return {true,ErrorCode::ModelNotApplicable,"","EXPERIMENTAL",false};
}
CorrectionResult RadialWeiModel::calculate(const Geometry& geometry,const SensorMeasurement& s,double,const CalculationOptions& o) const {
    const auto* g=dynamic_cast<const RadialGeometry*>(&geometry);
    if(!g||g->type()!=type_) throw AirflowError(ErrorCode::ModelNotApplicable,"Model requires matching radial geometry");
    if(o.returnVelocityField) throw AirflowError(ErrorCode::FieldNotSupported,"Sample interior points; logarithmic field is not defined on boundaries");
    if(!positive(s.velocity)) throw AirflowError(ErrorCode::InvalidArgument,"Velocity must be positive and finite");
    auto m=mapRadial(*g,s.position,o.useMappingCenter?o.mappingCenter:g->mappingCenter());
    if(m.trueWallDistance<=1e-9||m.equivalentWallDistance<=0) throw AirflowError(ErrorCode::SensorTooCloseToWall,"Sensor on or too close to wall");
    if(!positive(o.absoluteRoughness)||o.absoluteRoughness>=m.equivalentRadius) throw AirflowError(ErrorCode::InvalidArgument,"Roughness must be positive and less than equivalent radius");
    const double slope=1/(std::log(m.equivalentRadius/o.absoluteRoughness)+1.9);
    const double phi=1+slope*(std::log1p(-m.eta)+1.5);
    if(!positive(phi)) throw AirflowError(ErrorCode::ModelNotApplicable,"Non-positive log-law ratio; sensor outside model domain");
    CorrectionResult r; r.success=true; r.sectionArea=g->area(); r.measuredVelocity=s.velocity;
    r.correctionFactor=1/phi; r.meanVelocity=s.velocity/phi; r.airVolume=g->area()*r.meanVelocity;
    r.maximumVelocity=r.meanVelocity*(1+1.5*slope); r.integrationConverged=true;
    r.confidenceLevel="EXPERIMENTAL"; r.model=metadata(); r.parameterSetId="WEI_RADIAL_ROUGHNESS";
    r.warning="Radial extension of Wei; independent multi-section accuracy validation pending. Log law excludes wall layer.";
    r.radialEta=m.eta; r.equivalentRadius=m.equivalentRadius; r.equivalentWallDistance=m.equivalentWallDistance; r.trueWallDistance=m.trueWallDistance;
    return r;
}
}
