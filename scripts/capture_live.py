#!/usr/bin/env python3
"""Capture a real, sanitized query only when SPTRANS_TOKEN is configured.
Run python -m scripts.capture_live --line 1273 --stop 4200153; codes must be
independently verified. Output labels capture time, never a permanent live claim.
"""
import argparse,asyncio,json
from datetime import datetime,timezone
from pathlib import Path
from app.settings import Settings
from app.transit import Transit
async def main():
 p=argparse.ArgumentParser();p.add_argument('--line',type=int,required=True);p.add_argument('--stop',type=int,required=True);a=p.parse_args()
 settings=Settings(mode='live')
 if not settings.token:raise SystemExit('SPTRANS_TOKEN não configurado; nenhuma captura realizada.')
 result=await Transit(settings).call('arrivals',line_code=a.line,stop_code=a.stop)
 # Exclude vehicle identifiers and precise coordinates; retain arrival and line facts only.
 data=result['data'];st=data.get('p') or {}
 result['data']={'hr':data.get('hr'),'p':{'cp':st.get('cp'),'np':st.get('np'),'l':[{'c':l.get('c'),'cl':l.get('cl'),'sl':l.get('sl'),'vs':[{'t':v.get('t'),'ta':v.get('ta')} for v in l.get('vs',[])]} for l in st.get('l',[])]}}
 result['notice']='Captura externa histórica, não consulta atual. Coordenadas e identificadores de veículos removidos.'
 out=Path('evidencias')/('sptrans-live-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.json')
 out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(out)
if __name__=='__main__':asyncio.run(main())
