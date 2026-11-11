"""Tenant API entrypoint. External /api/v1 paths MUST be behind Nginx JWT."""
from uuid import UUID,uuid4
from fastapi import FastAPI,HTTPException,Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from app.api import router as public_router
from app.api_internal import router as internal_router
from app.db import get_engine
from app.service import TenantError

app=FastAPI(title='tenant',version='1.0.0')
app.include_router(public_router)
app.include_router(internal_router)

def error_response(request,status,code,message):
    try: trace=str(UUID(request.headers.get('x-correlation-id','')))
    except (TypeError,ValueError): trace=str(uuid4())
    return JSONResponse(status_code=status,
        content={'code':code,'message':message,'correlation_id':trace},
        headers={'Cache-Control':'no-store'})

@app.exception_handler(TenantError)
async def tenant_error(request:Request,exc:TenantError):
    return error_response(request,exc.status,exc.code,exc.message)

@app.exception_handler(RequestValidationError)
async def invalid_body(request:Request,exc:RequestValidationError):
    return error_response(request,422,'VALIDATION_ERROR','Request validation failed')

@app.exception_handler(HTTPException)
async def generic_http(request:Request,exc:HTTPException):
    code={403:'FORBIDDEN',404:'NOT_FOUND',503:'DEPENDENCY_UNAVAILABLE'}.get(exc.status_code,'HTTP_ERROR')
    response=error_response(request,exc.status_code,code,str(exc.detail))
    if exc.headers: response.headers.update(exc.headers)
    return response

@app.get('/health',include_in_schema=False)
async def health(): return {'status':'ok'}

@app.get('/ready',include_in_schema=False)
def ready():
    try:
        with get_engine().connect() as db:
            if not db.execute(text('SELECT version_num FROM alembic_version LIMIT 1')).scalar_one_or_none():
                raise HTTPException(status_code=503,detail='database_not_migrated')
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503,detail='database_not_ready') from exc
    return {'status':'ready'}
