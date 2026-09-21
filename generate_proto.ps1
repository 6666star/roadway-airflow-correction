$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$generated = Join-Path $projectRoot "generated"
New-Item -ItemType Directory -Force -Path $generated | Out-Null

python -m grpc_tools.protoc `
  -I (Join-Path $projectRoot "proto") `
  --python_out=$generated `
  --grpc_python_out=$generated `
  (Join-Path $projectRoot "proto\airflow_correction.proto")

Write-Host "Generated Python gRPC files in $generated"

