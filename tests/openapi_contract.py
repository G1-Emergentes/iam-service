"""Keep the checked-in OpenAPI contract aligned with the actual HTTP routes."""
import json
from pathlib import Path
import re

root = Path(__file__).resolve().parents[1]
spec = json.loads((root / 'docs/openapi.json').read_text(encoding='utf-8'))
expected = {('/health', 'get')}
for filename in ['AuthController.h', 'profile/interfaces/ProfileController.h']:
    source = (root / filename).read_text()
    for path, method in re.findall(
        r'ADD_METHOD_TO\([^,]+,\s*"([^"]+)",\s*(?:drogon::)?(Get|Post|Put)\)', source
    ):
        expected.add((path.replace('{1}', '{userId}'), method.lower()))
actual = {(path, method) for path, operations in spec['paths'].items() for method in operations}
assert actual == expected, (actual - expected, expected - actual)
ids = [operation['operationId'] for operations in spec['paths'].values() for operation in operations.values()]
assert len(set(ids)) == len(ids)
assert spec['servers'] == [{'url': '/', 'description': 'Este servidor'}]
assert spec['components']['securitySchemes']['BearerAuth']['scheme'] == 'bearer'


def check_references(value):
    if isinstance(value, dict):
        if '$ref' in value:
            target = spec
            assert value['$ref'].startswith('#/')
            for part in value['$ref'][2:].split('/'):
                target = target[part.replace('~1', '/').replace('~0', '~')]
        for child in value.values():
            check_references(child)
    elif isinstance(value, list):
        for child in value:
            check_references(child)


check_references(spec)
print(f'PASS: OpenAPI documents all {len(expected)} operations, unique IDs and valid local references')
