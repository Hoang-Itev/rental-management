"""Idempotently extend CURRENT contracts/openapi.yaml for P02 Room additions.

No global YAML reserialization; preserves existing unrelated API contracts.
Usage: python scripts/room/sync_openapi.py [--check] contracts/openapi.yaml
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re

UPDATES = {
    '/api/v1/properties/{property_id}': ('delete', 'room_delete_property', 'Vô hiệu hóa khu trọ; không xóa dữ liệu lịch sử'),
    '/api/v1/buildings/{building_id}': ('delete', 'room_delete_building', 'Vô hiệu hóa dãy nhà; không xóa dữ liệu lịch sử'),
    '/api/v1/floors/{floor_id}': ('delete', 'room_delete_floor', 'Vô hiệu hóa tầng; không xóa dữ liệu lịch sử'),
    '/api/v1/rooms/{room_id}': ('delete', 'room_delete_room', 'Vô hiệu hóa phòng; giữ lịch sử và hợp đồng'),
}

NEW_PATHS = {
    '/api/v1/buildings/{building_id}': ('get','room_get_building','Chi tiết dãy nhà','building_id','Building'),
    '/api/v1/floors/{floor_id}': ('get','room_get_floor','Chi tiết tầng','floor_id','Floor'),
    '/api/v1/floors/{floor_id}/rooms': ('post','room_post_single_room','Tạo một phòng','floor_id','Room'),
}


def path_method_exists(document: str, path: str, method: str) -> bool:
    match = re.search(r'^  ' + re.escape(path) + r':\s*$', document, re.M)
    if not match:
        return False
    block_end = re.search(r'(?m)^(?:  /[^\n]+:|[a-zA-Z][a-zA-Z0-9_-]*:)', document[match.end():])
    section = document[match.end():match.end()+block_end.start() if block_end else len(document)]
    return re.search(r'^    ' + re.escape(method) + r':\s*$', section, re.M) is not None


def insert_method(document: str, path: str, snippet: str) -> str:
    match = re.search(r'^  ' + re.escape(path) + r':\s*$', document, re.M)
    if not match:
        raise ValueError('Missing expected canonical API path: '+path)
    suffix = document[match.end():]
    end = re.search(r'(?m)^(?:  /[^\n]+:|[a-zA-Z][a-zA-Z0-9_-]*:)', suffix)
    offset = match.end() + (end.start() if end else len(suffix))
    return document[:offset] + snippet + document[offset:]


def delete_method(ident: str, summary: str) -> str:
    return (f'    delete:\n'
            f'      tags: [Room]\n'
            f'      operationId: {ident}\n'
            f'      summary: {summary}\n'
            f'      description: 204 khi vô hiệu hóa hoặc đã vô hiệu hóa; 409 khi còn phần tử active/hợp đồng.\n'
            f'      responses:\n'
            f"        '204':\n          description: Đã vô hiệu hóa (soft-delete)\n"
            f"        '404':\n          description: Không tìm thấy\n"
            f"        '409':\n          description: Không thể vô hiệu hóa khi còn phụ thuộc\n")


def new_path_snippet(path: str, method: str, ident: str, summary: str, parameter: str, schema: str) -> str:
    body = ''
    if method == 'post':
        body = ("      requestBody:\n"
                "        required: true\n"
                "        content:\n"
                "          application/json:\n"
                "            schema:\n"
                "              $ref: '#/components/schemas/RoomCreateItem'\n")
    return (f'  {path}:\n'
            f'    {method}:\n'
            f'      tags: [Room]\n'
            f'      operationId: {ident}\n'
            f'      summary: {summary}\n'
            f'      parameters:\n'
            f'      - name: {parameter}\n'
            f'        in: path\n'
            f'        required: true\n'
            f'        schema: {{type: string, format: uuid}}\n'
            f'{body}'
            f'      responses:\n'
            f"        '{'201' if method == 'post' else '200'}':\n"
            f'          description: Thành công\n'
            f'          content:\n'
            f'            application/json:\n'
            f'              schema:\n'
            f"                $ref: '#/components/schemas/{schema}'\n"
            f"        '404':\n          description: Không tìm thấy\n"
            f"        '409':\n          description: Xung đột nghiệp vụ\n")


def updated(document: str) -> str:
    # Add only missing methods. Existing spec remains untouched.
    for path, (method, ident, summary) in UPDATES.items():
        if not path_method_exists(document, path, method):
            document = insert_method(document, path, delete_method(ident, summary))
    for path, (method, ident, summary, param, schema) in NEW_PATHS.items():
        if path_method_exists(document, path, method):
            continue
        if re.search(r'^  '+re.escape(path)+r':\s*$', document, re.M):
            document = insert_method(document,path,new_path_snippet(path,method,ident,summary,param,schema).split('\n',1)[1])
        else:
            component_start = re.search(r'^components:\s*$', document, re.M)
            if not component_start:
                raise ValueError('Cannot find root components: marker in OpenAPI')
            document = document[:component_start.start()] + new_path_snippet(path,method,ident,summary,param,schema) + document[component_start.start():]
    # Optional client-provided property assertion on RoomCreateItem.
    # The server always derives the authoritative property from the floor.
    room_schema = re.search(r'^    RoomCreateItem:\s*$', document, re.M)
    if not room_schema:
        raise ValueError('RoomCreateItem schema missing')
    suffix = document[room_schema.end():]
    next_schema = re.search(r'^    [A-Za-z][A-Za-z0-9_]*:\s*$', suffix, re.M)
    section_end = room_schema.end() + (next_schema.start() if next_schema else len(suffix))
    section = document[room_schema.end():section_end]
    if not re.search(r'^        property_id:\s*$', section, re.M):
        required = re.search(r'^      required:\s*$', section, re.M)
        if not required:
            raise ValueError('RoomCreateItem required marker missing')
        offset = room_schema.end()+required.start()
        extension = '        property_id:\n          type: string\n          format: uuid\n          description: Optional property assertion; server derives authoritative property from floor.\n'
        document = document[:offset]+extension+document[offset:]
    return document


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--check',action='store_true')
    parser.add_argument('file',type=Path)
    args=parser.parse_args()
    original=args.file.read_text(encoding='utf-8')
    expected=updated(original)
    if args.check:
        if expected != original:
            raise SystemExit('P02 OpenAPI routes not synced: run apply_p02.ps1 -Apply')
        print('P02 OpenAPI route additions present')
        return
    if expected != original:
        args.file.write_text(expected,encoding='utf-8',newline='\n')
        print('Updated P02 Room operations in current contract')
    else:
        print('P02 Room operations already present')


if __name__=='__main__':
    main()
