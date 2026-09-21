#include "airflow/radial.hpp"
#include <cmath>
#include <iostream>
#include <numbers>
#include <stdexcept>
using namespace airflow;
void check(bool b) { if(!b) throw std::runtime_error("Check failed"); }
void near(double a,double b,double tol=1e-8) { check(std::abs(a-b)<=tol); }
int main() {
 try {
 const double pi=std::numbers::pi;
 auto rect=RadialGeometry::rectangle(4,3),semi=RadialGeometry::semicircle(4,3);
 auto pure=RadialGeometry::semicircle(4,2),trap=RadialGeometry::trapezoid(5,3,3);
 auto wide=RadialGeometry::trapezoid(3,5,3),three=RadialGeometry::threeCenter(4,1.5,1,3,.5);
 near(rect.area(),12); near(rect.perimeter(),14);
 near(semi.area(),4+2*pi); near(semi.perimeter(),6+2*pi); near(pure.area(),2*pi);
 near(trap.area(),12); near(wide.area(),12); near(trap.perimeter(),8+2*std::sqrt(10.0));
 near(three.rayDistance(three.mappingCenter(),{0,1}),1.25);
 near(semi.rayDistance(semi.mappingCenter(),{1,0}),std::sqrt(3.75));
 for(const auto& g:{rect,semi,pure,trap,wide,three}) {
   check(g.isValid()); auto c=g.mappingCenter(); near(mapRadial(g,c,c).eta,0);
   double areaPolar=0;
   for(int i=0;i<1440;++i) {
     double a=2*pi*(i+.5)/1440; Point e{std::cos(a),std::sin(a)};
     double t=g.rayDistance(c,e);
     near(g.distanceToBoundary({c.x+t*e.x,c.y+t*e.y}),0);
     check(!g.contains({c.x+t*1.00001*e.x,c.y+t*1.00001*e.y}));
     Point p{c.x+.61*t*e.x,c.y+.61*t*e.y}; auto m=mapRadial(g,p,c);
     near(m.eta,.61); near(mapRadial(g,{g.width()-p.x,p.y},c).eta,.61);
     areaPolar+=t*t*pi/1440;
   }
   near(areaPolar,g.area(),g.area()*2e-5);
   auto b=g.bounds(); double area=0,integral=0; int n=500;
   double dx=(b.maxX-b.minX)/n,dy=(b.maxY-b.minY)/n;
   for(int iy=0;iy<n;++iy) for(int ix=0;ix<n;++ix) {
     Point p{b.minX+(ix+.5)*dx,b.minY+(iy+.5)*dy};
     if(!g.contains(p)||g.distanceToBoundary(p)<1e-10) continue;
     auto m=mapRadial(g,p,c);
     integral+=(1+(std::log1p(-m.eta)+1.5)/(std::log(m.equivalentRadius/.0055)+1.9))*dx*dy;
     area+=dx*dy;
   }
   near(area,g.area(),g.area()*.004); near(integral/g.area(),1,.004);
   auto result=RadialWeiModel(g.type()).calculate(g,{c,2},0,{});
   near(result.airVolume,result.meanVelocity*g.area()); check(result.meanVelocity>0);
 }
 bool rejected=false;
 try { (void)RadialGeometry::threeCenter(4,1.5,1,2,.5); } catch(const AirflowError&) { rejected=true; }
 check(rejected); rejected=false;
 try { (void)mapRadial(semi,{1,2},{0,0}); } catch(const AirflowError&) { rejected=true; }
 check(rejected);
 std::cout<<"PASS: 8640 rays, six sections, independent Cartesian normalization, invalid geometry\n";
 return 0;
 } catch(const std::exception& e) { std::cerr<<e.what()<<"\n"; return 1; }
}
