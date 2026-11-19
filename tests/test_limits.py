import asyncio
import pytest
from app.limits import QueryLimits

@pytest.mark.asyncio
async def test_streaming_body_limit_never_calls_app():
    called=[];sent=[]
    async def app(*args):called.append(True)
    chunks=iter([{'type':'http.request','body':b'x'*5000,'more_body':True},{'type':'http.request','body':b'x'*4000,'more_body':False}])
    async def receive():return next(chunks)
    async def send(m):sent.append(m)
    middleware=QueryLimits(app)
    await middleware({'type':'http','method':'POST','path':'/api/ask'},receive,send)
    assert not called and sent[0]['status']==413 and middleware.inflight==0

@pytest.mark.asyncio
async def test_capacity_and_release_after_exception():
    entered=asyncio.Event();release=asyncio.Event();sent=[]
    async def app(scope,receive,send):
        entered.set();await release.wait();raise RuntimeError('test')
    async def receive():return {'type':'http.request','body':b'{}','more_body':False}
    async def send(m):sent.append(m)
    middleware=QueryLimits(app,capacity=1);scope={'type':'http','method':'POST','path':'/api/ask'}
    first=asyncio.create_task(middleware(scope,receive,send));await entered.wait()
    await middleware(scope,receive,send)
    assert sent[0]['status']==429 and middleware.inflight==1
    release.set()
    with pytest.raises(RuntimeError):await first
    assert middleware.inflight==0

@pytest.mark.asyncio
async def test_disconnect_during_body_through_real_app_does_not_raise_500(monkeypatch):
    from app.main import app, engine

    async def unexpected_inference(*args, **kwargs):
        pytest.fail('A disconnected upload must not invoke the assistant')
    monkeypatch.setattr(engine, 'answer', unexpected_inference)
    scope={
        'type':'http', 'asgi':{'version':'3.0','spec_version':'2.4'},
        'method':'POST', 'path':'/api/ask', 'raw_path':b'/api/ask',
        'query_string':b'', 'root_path':'', 'scheme':'http',
        'http_version':'1.1', 'headers':[],
        'client':('127.0.0.1',12345), 'server':('test',80),
    }
    messages=iter([
        {'type':'http.request','body':b'{"question":','more_body':True},
        {'type':'http.disconnect'},
    ])
    async def receive():
        return next(messages, {'type':'http.disconnect'})
    sent=[]
    async def send(message):
        sent.append(message)

    await app(scope,receive,send)
    assert [m['status'] for m in sent if m['type']=='http.response.start']==[499]
    assert b''.join(m.get('body',b'') for m in sent if m['type']=='http.response.body')==b''
    middleware=app.middleware_stack
    while not isinstance(middleware,QueryLimits):
        middleware=middleware.app
    assert middleware.inflight==0
