"""End-to-end gRPC checks of the new radial geometry models."""
import argparse, math, sys
from pathlib import Path
import grpc
root=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(root),str(root/"generated")]
from grpc_adapter.server import create_server
import airflow_correction_pb2 as pb
import airflow_correction_pb2_grpc as rpc
p=argparse.ArgumentParser()
p.add_argument("--exe",required=True)
server=create_server(Path(p.parse_args().exe).resolve())
port=server.add_insecure_port("127.0.0.1:0")
server.start()
try:
 with grpc.insecure_channel(f"127.0.0.1:{port}") as channel:
  stub=rpc.AirflowCorrectionServiceStub(channel)
  cases=[
   (pb.GEOMETRY_TYPE_RECTANGLE,"RECTANGLE_WEI_RADIAL",dict(width=4,height=3)),
   (pb.GEOMETRY_TYPE_SEMICIRCLE_ARCH,"SEMICIRCLE_ARCH_WEI_RADIAL",dict(width=4,height=3)),
   (pb.GEOMETRY_TYPE_TRAPEZOID,"TRAPEZOID_WEI_RADIAL",dict(bottom_width=5,top_width=3,height=3)),
   (pb.GEOMETRY_TYPE_THREE_CENTER_ARCH,"THREE_CENTER_ARCH_WEI_RADIAL",dict(width=4,wall_height=1.5,arch_rise=1,crown_radius=3,side_radius=.5))]
  for typ,model,dims in cases:
   geometry=pb.GeometryRequest(type=typ,dimensions_m=dims)
   v=stub.ValidateGeometry(geometry)
   assert v.valid,v
   models=stub.ListApplicableModels(pb.ModelQueryRequest(geometry=geometry))
   assert model in [m.model_id for m in models.models]
   req=pb.CorrectionRequest(geometry=geometry,model_id=model,
    sensor=pb.SensorMeasurement(x_m=1,y_m=2,measured_velocity_mps=2),absolute_roughness_m=.0055)
   r=stub.CalculateCorrection(req)
   assert r.success,r
   assert math.isclose(r.section_area_m2,v.area_m2,rel_tol=1e-10)
   expected=(math.log(r.equivalent_wall_distance_m/.0055)+3.4)/(math.log(r.equivalent_radius_m/.0055)+1.9)
   assert math.isclose(r.mean_velocity_mps,2/expected,rel_tol=1e-12)
   req.sensor.x_m=dims.get("width",dims.get("bottom_width"))-1
   mirror=stub.CalculateCorrection(req)
   assert mirror.success and math.isclose(mirror.mean_velocity_mps,r.mean_velocity_mps,rel_tol=1e-12)
   req.mapping_center_x_m=2
   assert not stub.CalculateCorrection(req).success
   req.ClearField("mapping_center_x_m")
   req.absolute_roughness_m=0
   assert not stub.CalculateCorrection(req).success
  print("PASS: four radial models over gRPC; geometry, formula, symmetry, invalid inputs")
finally:
 server.stop(0).wait()
