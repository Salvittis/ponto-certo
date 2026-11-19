import logging
import secrets
import time
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ConfigDict, field_validator
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from .settings import Settings
from .limits import QueryLimits
from .engine import Engine
from .metrics import REQUESTS,LATENCY,ACTIVE,ASK_STATUS,MODEL_READY
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)
settings=Settings()
engine=Engine(settings)
ROOT=Path(__file__).resolve().parents[1]
app=FastAPI(title='Ponto Certo',version=settings.version)
app.add_middleware(QueryLimits,max_bytes=8192,capacity=2)
class AskRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    question:str=Field(min_length=1,max_length=1000)
    line_code:int|None=Field(default=None,gt=0,le=2_147_483_647)
    stop_code:int|None=Field(default=None,gt=0,le=2_147_483_647)
    direction:int|None=Field(default=None,ge=1,le=2)
    @field_validator('question')
    @classmethod
    def trim_question(cls,value):
        if not value.strip():raise ValueError('Informe uma pergunta')
        return value.strip()
class Source(BaseModel):
    id:str
    title:str
    url:str
class AskResponse(BaseModel):
    status:str
    answer:str
    sources:list[Source]
    updated_at:str|None
    data_mode:str
    model:str
    request_id:str
    warnings:list[str]
    options:list[dict]
@app.exception_handler(RequestValidationError)
async def invalid_request(request,exc):
    # FastAPI's default validation response echoes input; omit it for privacy.
    return JSONResponse(status_code=422,content={'detail':'Entrada inválida. Informe uma pergunta de até 1000 caracteres e códigos positivos.'})
@app.middleware('http')
async def telemetry(request:Request,call_next):
    started=time.perf_counter();ACTIVE.inc();code=500
    try:
        response=await call_next(request);code=response.status_code
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='no-referrer'
        response.headers['Content-Security-Policy']="default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'"
        response.headers['Cache-Control']='no-store' if request.url.path.startswith('/api/') else 'no-cache'
        return response
    finally:
        route=getattr(request.scope.get('route'),'path','unmatched')
        REQUESTS.labels(route,request.method,str(code)).inc();LATENCY.labels(route).observe(time.perf_counter()-started);ACTIVE.dec()
@app.get('/healthz')
async def health():return {'status':'ok','version':settings.version,'revision':settings.revision}
@app.get('/readyz')
async def ready():
    model_ready=await engine.model.ready();MODEL_READY.set(int(model_ready))
    data_ready=settings.mode=='demo' or bool(settings.token)
    return JSONResponse(status_code=200 if model_ready and data_ready else 503,content={'status':'ready' if model_ready and data_ready else 'not_ready','model_ready':model_ready,'data_ready':data_ready,'data_mode':settings.mode,'sptrans_live_verified':False,'version':settings.version,'revision':settings.revision})
@app.get('/api/config')
async def config():return {'mode':settings.mode,'model':settings.model,'version':settings.version,'revision':settings.revision,'scope':'Ônibus municipais de São Paulo. Demonstração sintética: 8000-10, sentidos 1/2, ponto 4200153. Cobertura ao vivo depende do retorno da SPTrans.'}
@app.get('/metrics')
async def metrics(request:Request):
    if not settings.metrics_token:raise HTTPException(503,'Métricas não configuradas')
    if not secrets.compare_digest(request.headers.get('authorization',''),'Bearer '+settings.metrics_token):raise HTTPException(401,'Não autorizado')
    return Response(content=generate_latest(),media_type=CONTENT_TYPE_LATEST)
@app.post('/api/ask',response_model=AskResponse)
async def ask(body:AskRequest,response:Response):
    result=await engine.answer(**body.model_dump())
    ASK_STATUS.labels(result['status']).inc()
    if result['status']=='unavailable':response.status_code=503
    return result
@app.get('/')
async def index():return FileResponse(ROOT/'app/static/index.html')
@app.get('/base/POLITICA-DO-PRODUTO.md')
async def policy():return FileResponse(ROOT/'base/POLITICA-DO-PRODUTO.md',media_type='text/plain')
app.mount('/static',StaticFiles(directory=ROOT/'app/static'),name='static')
