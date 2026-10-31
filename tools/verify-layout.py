from pathlib import Path
root = Path(__file__).resolve().parents[1]
for name in ['src/app.js','test/gateway.test.js','docs/architecture.md','docs/contracts.md','docs/local-development.md','docs/openapi.json','docs/service-overview.md','scripts/prepare-local.ps1','scripts/start-local.ps1','scripts/test.ps1','scripts/smoke-local.ps1','tools/service.json','compose.yml','compose.integration.yml','Dockerfile','.env.example','README.md','LICENSE']:
    assert (root/name).is_file(), name
print('smartgn-api-gateway: Node runtime and shared repository layout valid')
