"""Allowlisted SPTrans tools. Credentials never leave this server or reach error messages."""
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import httpx
from .settings import Settings
TZ=ZoneInfo('America/Sao_Paulo')
API='https://api.olhovivo.sptrans.com.br/v2.1'
DOC='https://www.sptrans.com.br/desenvolvedores/api-do-olho-vivo-guia-de-referencia/documentacao-api'
class TransitUnavailable(Exception): pass

def current_time():
    return datetime.now(TZ)

def live_arrival_lines(data, stop_code):
    """Validate the returned point before any forecast can reach the model."""
    if not isinstance(data,dict) or 'p' not in data:
        raise TransitUnavailable('A fonte retornou dados incompletos para o ponto consultado. Tente novamente.')
    point=data['p']
    if point is None:return []
    if not isinstance(point,dict) or type(point.get('cp')) is not int or point['cp']!=stop_code:
        raise TransitUnavailable('A fonte retornou um ponto diferente do consultado; não é seguro informar essa previsão.')
    lines=point.get('l')
    if not isinstance(lines,list) or not all(isinstance(line,dict) for line in lines):
        raise TransitUnavailable('A fonte retornou dados incompletos para o ponto consultado. Tente novamente.')
    return lines

def timestamp_age(stamp, now):
    """Measure a timezone-aware source timestamp against the current clock."""
    try:
        if not isinstance(stamp,str) or not 1<=len(stamp)<=40:raise ValueError()
        observed=datetime.fromisoformat(stamp.replace('Z','+00:00'))
        if observed.utcoffset() is None or now.utcoffset() is None:raise ValueError()
        return round((now-observed).total_seconds(),3)
    except (AttributeError,TypeError,ValueError):
        raise TransitUnavailable('Não foi possível confirmar a atualização da previsão recebida. Tente novamente ou consulte a SPTrans.') from None

def require_fresh_observation(stamp, now, max_age):
    age=timestamp_age(stamp,now)
    if not -60<=age<=max_age:
        raise TransitUnavailable('A informação está desatualizada; não é seguro informar uma chegada atual')

def require_fresh_vehicle(vehicle, now, max_age):
    """A fresh API clock does not make an old/missing vehicle observation fresh."""
    age=timestamp_age(vehicle.get('ta'),now)
    if not -60<=age<=max_age:
        raise TransitUnavailable('A telemetria da previsão está fora da janela de atualização; não é seguro informar uma chegada atual.')

def observed_time(hr, now):
    if not isinstance(hr,str) or not re.fullmatch(r'\d{2}:\d{2}',hr):
        raise TransitUnavailable('Horário da fonte ausente')
    try:
        hour,minute=map(int,hr.split(':'))
        candidate=now.replace(hour=hour,minute=minute,second=0,microsecond=0)
    except ValueError:
        raise TransitUnavailable('Horário da fonte inválido') from None
    return min((candidate-timedelta(days=1),candidate,candidate+timedelta(days=1)),key=lambda x:abs((now-x).total_seconds()))

class Transit:
    def __init__(self, settings=None, clock=None):
        self.settings=settings or Settings()
        self.clock=clock or current_time
        self.fixture=json.loads((Path(__file__).resolve().parents[1]/'dados/fixtures/sptrans-demo.json').read_text())
    async def call(self, action, query='',line_code=None,stop_code=None,direction=None,scenario='normal'):
        if self.settings.mode=='demo':
            if scenario=='unavailable':raise TransitUnavailable('Serviço indisponível no cenário de teste')
            now=datetime.fromisoformat(self.fixture['reference_time'])
            if scenario=='stale':now+=timedelta(minutes=10)
            if action=='lines':
                data=[x for x in self.fixture['lines'] if (not direction or x['sl']==direction) and (not query or query.casefold() in json.dumps(x).casefold())]
            elif action=='stops':
                data=self.fixture['stops'] if line_code in (1273,34041) else []
            else:
                data=json.loads(json.dumps(self.fixture['predictions']))
                if line_code!=1273 or stop_code!=4200153 or scenario=='empty':data['p']['l']=[]
        else:
            if not self.settings.token:raise TransitUnavailable('Credencial da fonte não configurada')
            now=self.clock()
            if now.utcoffset() is None:raise TransitUnavailable('Relógio da consulta indisponível')
            now=now.astimezone(TZ)
            try:
                async with httpx.AsyncClient(timeout=12,follow_redirects=False) as c:
                    auth=await c.post(API+'/Login/Autenticar',params={'token':self.settings.token})
                    if auth.status_code!=200 or auth.json() is not True:raise TransitUnavailable('Autenticação da fonte indisponível')
                    routes={'lines':('/Linha/Buscar',{'termosBusca':query}), 'stops':('/Parada/BuscarParadasPorLinha',{'codigoLinha':line_code}), 'arrivals':('/Previsao',{'codigoLinha':line_code,'codigoParada':stop_code})}
                    path,params=routes[action]
                    r=await c.get(API+path,params=params);r.raise_for_status();data=r.json()
                    received=self.clock()
                    if received.utcoffset() is None:raise TransitUnavailable('Relógio da consulta indisponível')
                    received=received.astimezone(TZ)
                    if action=='lines' and direction:data=[x for x in data if x.get('sl')==direction]
            except (httpx.HTTPError,ValueError,TypeError):raise TransitUnavailable('Não foi possível consultar a fonte') from None
        observed=now
        if action=='arrivals':
            if not isinstance(data,dict):raise TransitUnavailable('Formato da fonte inválido')
            checked_at=now if self.settings.mode=='demo' else received
            observed=observed_time(data.get('hr'),checked_at)
            require_fresh_observation(observed.isoformat(),checked_at,self.settings.max_age)
        elif not isinstance(data,list):raise TransitUnavailable('Formato da fonte inválido')
        result={'data':data,'observed_at':observed.isoformat(),'queried_at':now.isoformat(),'mode':self.settings.mode,'synthetic':self.settings.mode=='demo','source':DOC,'action':action}
        if self.settings.mode=='live':result['received_at']=received.isoformat()
        return result
