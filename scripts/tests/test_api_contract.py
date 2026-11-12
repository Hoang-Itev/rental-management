"""Regression tests for contract drift detection, independent of backend imports."""
from copy import deepcopy
import importlib.util
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('api_contract_checker', ROOT / 'scripts/check_api_contract.py')
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


def generated():
    return {'paths': {'/api/v1/example': {'get': {'x-service': 'room', 'responses': {'200': {}}}}},
            'components': {'schemas': {'room__Item': {'type': 'object'}}}}


def test_checker_detects_new_route_input_and_schema_drift():
    doc = {'paths': {}, 'components': {'schemas': {}}}
    expected = generated()
    assert not checker.reconcile(doc, expected, 'room')
    assert checker.reconcile(doc, expected, 'room')
    modified = deepcopy(expected)
    modified['paths']['/api/v1/example']['get']['parameters'] = [{'name': 'page', 'in': 'query'}]
    assert not checker.reconcile(doc, modified, 'room')
    modified = deepcopy(modified)
    modified['components']['schemas']['room__Item']['required'] = ['id']
    assert not checker.reconcile(doc, modified, 'room')


def test_checker_refuses_silent_route_deletion():
    doc = {'paths': {}, 'components': {'schemas': {}}}
    checker.reconcile(doc, generated(), 'room')
    with pytest.raises(ValueError, match='Documented routes removed'):
        checker.reconcile(doc, {'paths': {}, 'components': {'schemas': {}}}, 'room')


def test_service_schema_names_do_not_collide():
    value = {'items': [{'$ref': '#/components/schemas/Page'}], 'description': 'Page'}
    assert checker.namespace_refs(value, 'room')['items'][0]['$ref'] == '#/components/schemas/room__Page'
    assert checker.namespace_refs(value, 'tenant')['items'][0]['$ref'] == '#/components/schemas/tenant__Page'
    assert value['items'][0]['$ref'] == '#/components/schemas/Page'


def test_committed_contract_references_security_and_inventory():
    document = yaml.safe_load((ROOT / 'contracts/openapi.yaml').read_text())
    identifiers = set()
    counts = {service: 0 for service in checker.SERVICES}
    for path, operations in document['paths'].items():
        for method, operation in operations.items():
            if method not in checker.METHODS:
                continue
            assert operation['operationId'] not in identifiers
            identifiers.add(operation['operationId'])
            if path in ('/health', '/ready'):
                assert len(operation['servers']) == 6
                continue
            counts[operation['x-service']] += 1
            if path.startswith('/internal/'):
                assert operation['servers'][0]['url'] != 'http://localhost:8080'
                assert 'ServiceToken' in operation['security'][0]
            elif path.startswith('/api/') and path != '/api/v1/auth/login':
                assert operation['security'] == [{'BearerAuth': []}]
            for status, response in operation['responses'].items():
                if status.startswith('2') and 'application/json' in response.get('content', {}):
                    assert response['content']['application/json']['schema'], (path, 'Missing output schema')
    assert all(counts.values())

    def walk(value):
        if isinstance(value, dict):
            if '$ref' in value:
                ref = value['$ref']
                assert ref.startswith('#/'), ref
                resolved = document
                for key in ref[2:].split('/'):
                    resolved = resolved[key.replace('~1', '/').replace('~0', '~')]
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
    walk(document)
