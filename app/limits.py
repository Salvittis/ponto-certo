"""Bound resource use before JSON parsing or inference. No IP or user tracking."""
import asyncio
from starlette.responses import JSONResponse, Response

class QueryLimits:
    def __init__(self, app, max_bytes=8192, capacity=2):
        self.app=app
        self.max_bytes=max_bytes
        self.capacity=capacity
        self.inflight=0

    async def __call__(self, scope, receive, send):
        if scope['type']!='http' or scope.get('path')!='/api/ask' or scope.get('method')!='POST':
            return await self.app(scope,receive,send)
        # This counter runs on the single ASGI event loop; no await between check and increment.
        if self.inflight>=self.capacity:
            return await JSONResponse({'detail':'Assistente ocupado. Tente novamente em instantes.'},status_code=429,headers={'Retry-After':'3'})(scope,receive,send)
        self.inflight+=1
        try:
            body=bytearray()
            try:
                async with asyncio.timeout(10):
                    while True:
                        message=await receive()
                        if message['type']=='http.disconnect':
                            # Complete the middleware response contract even when the
                            # peer left; otherwise outer BaseHTTPMiddleware reports 500.
                            return await Response(status_code=499)(scope,receive,send)
                        body.extend(message.get('body',b''))
                        if len(body)>self.max_bytes:
                            return await JSONResponse({'detail':'Corpo da consulta excede 8 KiB.'},status_code=413)(scope,receive,send)
                        if not message.get('more_body',False):break
            except TimeoutError:
                return await JSONResponse({'detail':'Tempo de envio da consulta excedido.'},status_code=408)(scope,receive,send)
            delivered=False
            async def bounded_receive():
                nonlocal delivered
                if not delivered:
                    delivered=True
                    return {'type':'http.request','body':bytes(body),'more_body':False}
                return await receive()
            return await self.app(scope,bounded_receive,send)
        finally:
            self.inflight-=1
