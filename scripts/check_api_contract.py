"""Compare a service's registered HTTP API with the committed OpenAPI contract.

Run with that service's dependencies installed. No DB/broker connection is made.
--write updates only that service and refuses to silently delete documented routes.
Health/readiness are container probes, not gateway API operations.
"""
from __future__ import annotations

import argparse
from copy import copy, deepcopy
from pathlib import Path
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
SERVICES = ('auth', 'room', 'tenant', 'metering', 'billing', 'notification')
METHODS = {'get', 'post', 'put', 'patch', 'delete', 'head', 'options'}
ERROR = {
    'type': 'object', 'required': ['code', 'message', 'correlation_id'],
    'properties': {name: {'type': 'string'} for name in ('code', 'message', 'correlation_id')},
}


def registered_routes(app):
    """Support both flattened and lazy FastAPI routers without changing the app."""
    from fastapi import routing
    contexts = (routing.iter_route_contexts(app.routes)
                if hasattr(routing, 'iter_route_contexts') else app.routes)
    for context in contexts:
        source = getattr(context, 'original_route', context)
        if not isinstance(source, routing.APIRoute):
            continue
        if context.path in ('/health', '/ready'):
            continue
        route = copy(source)
        route.path = context.path
        route.path_format = context.path_format
        route.include_in_schema = True  # Inventory also includes private/compatibility routes.
        yield route


def namespace_refs(value, service):
    if isinstance(value, dict):
        return {key: (item.replace('#/components/schemas/', f'#/components/schemas/{service}__', 1)
                      if key == '$ref' and item.startswith('#/components/schemas/')
                      else namespace_refs(item, service)) for key, item in value.items()}
    if isinstance(value, list):
        return [namespace_refs(item, service) for item in value]
    return value


def export_service(service):
    from fastapi.openapi.utils import get_openapi
    path = ROOT / ('backend/auth' if service == 'auth' else f'backend/services/{service}')
    sys.path.insert(0, str(path))
    from app.main import app
    routes = list(registered_routes(app))
    schema = get_openapi(title=service, version='1', routes=routes)
    schema = namespace_refs(schema, service)
    schema['components']['schemas'] = {
        f'{service}__{key}': value for key, value in schema.get('components', {}).get('schemas', {}).items()
    }
    for path, operations in schema['paths'].items():
        for method, operation in operations.items():
            operation['x-service'] = service
            operation['operationId'] = service + '_' + operation['operationId']
            operation['tags'] = [service.title()]
            if path.startswith('/internal/'):
                operation['servers'] = [{'url': f'http://{service}:8000',
                                          'description': 'Docker network only; blocked by Nginx'}]
                operation['security'] = [{'ServiceToken': []}]
                if path == '/internal/v1/auth/verify':
                    operation['security'] = [{'ServiceToken': [], 'BearerAuth': []}]
            elif path.startswith('/api/') and path != '/api/v1/auth/login':
                operation['security'] = [{'BearerAuth': []}]
            else:
                operation['security'] = []
            # These credentials are expressed by securitySchemes, not editable duplicate headers.
            parameters = operation.get('parameters', [])
            injected = [p for p in parameters if p['in'] == 'header' and
                        p['name'].lower() == 'x-auth-user-id' and path.startswith('/api/')]
            if injected:
                operation['x-gateway-injected-headers'] = ['X-Auth-User-Id']
            parameters = [p for p in parameters if p not in injected and not (
                p['in'] == 'header' and p['name'].lower() in ('authorization', 'x-service-token'))]
            if parameters:
                operation['parameters'] = parameters
            else:
                operation.pop('parameters', None)
            if service in ('auth', 'room', 'tenant', 'billing') and '422' in operation['responses']:
                operation['responses']['422'] = {
                    'description': 'Request validation failed',
                    'content': {'application/json': {'schema': deepcopy(ERROR)}}}
            operation['responses']['default'] = {
                'description': 'Domain, authentication or dependency error; inspect HTTP status and response body.',
                'content': {'application/json': {'schema': deepcopy(ERROR) if service in (
                    'auth', 'room', 'tenant', 'billing') else {'type': 'object'}}},
            }
            if path.endswith('/revise'):
                operation['deprecated'] = True
                operation['description'] = 'Compatibility alias. Use the /corrections endpoint.'
    return schema


def service_slice(document, service):
    paths = {}
    for path, operations in document.get('paths', {}).items():
        selected = {method: operation for method, operation in operations.items()
                    if method in METHODS and operation.get('x-service') == service}
        if selected:
            paths[path] = selected
    schemas = {name: value for name, value in document.get('components', {}).get('schemas', {}).items()
               if name.startswith(service + '__')}
    return {'paths': paths, 'schemas': schemas}


def reconcile(document, generated, service):
    expected = {'paths': generated['paths'], 'schemas': generated['components']['schemas']}
    current = service_slice(document, service)
    missing = {(p, m) for p, ops in current['paths'].items() for m in ops} - {
        (p, m) for p, ops in expected['paths'].items() for m in ops}
    if missing:
        raise ValueError(f'Documented routes removed from {service}: {sorted(missing)}. Review explicitly; do not auto-delete.')
    for path, operations in expected['paths'].items():
        document.setdefault('paths', {}).setdefault(path, {}).update(operations)
    schemas = document.setdefault('components', {}).setdefault('schemas', {})
    for name in list(schemas):
        if name.startswith(service + '__'):
            del schemas[name]
    schemas.update(expected['schemas'])
    return current == expected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--service', required=True, choices=SERVICES)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    target = ROOT / 'contracts/openapi.yaml'
    document = yaml.safe_load(target.read_text(encoding='utf-8'))
    generated = export_service(args.service)
    original_slice = service_slice(document, args.service)
    equal = reconcile(document, generated, args.service)
    count = sum(len(ops) for ops in generated['paths'].values())
    if args.write:
        target.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False, width=110), encoding='utf-8')
        print(f'Updated {args.service}: {count} operations')
    elif not equal:
        # Show an actionable bounded diff without relaxing contract enforcement.
        from difflib import unified_diff
        expected = {'paths': generated['paths'], 'schemas': generated['components']['schemas']}
        # Compare by key so unrelated path ordering never obscures the actual drift.
        differences = []
        for path in sorted(set(original_slice['paths']) | set(expected['paths'])):
            committed_ops = original_slice['paths'].get(path, {})
            generated_ops = expected['paths'].get(path, {})
            for method in sorted(set(committed_ops) | set(generated_ops)):
                before, after = committed_ops.get(method), generated_ops.get(method)
                if before != after:
                    differences.append((f'{method.upper()} {path}', before, after))
        for name in sorted(set(original_slice['schemas']) | set(expected['schemas'])):
            before, after = original_slice['schemas'].get(name), expected['schemas'].get(name)
            if before != after:
                differences.append((f'SCHEMA {name}', before, after))
        for label, before, after in differences[:10]:
            print(f'CONTRACT DRIFT: {label}')
            a = yaml.safe_dump(before, allow_unicode=True, sort_keys=True).splitlines()
            b = yaml.safe_dump(after, allow_unicode=True, sort_keys=True).splitlines()
            for index, line in enumerate(unified_diff(a, b, fromfile='committed', tofile='generated', lineterm='')):
                if index >= 80:
                    print('... individual diff truncated')
                    break
                print(line)
        if len(differences) > 10:
            print(f'... {len(differences) - 10} additional differing API entries')
        raise SystemExit(f'OpenAPI differs from {args.service}: run python scripts/check_api_contract.py --service {args.service} --write and review the diff.')
    else:
        print(f'API CONTRACT OK: {args.service}, {count} operations')


if __name__ == '__main__':
    main()
