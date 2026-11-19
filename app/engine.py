"""Tool-using agent with a bounded state machine and extractive grounding validator.
The model is never allowed to create tool URLs or credentials, or to invent a bus ETA.
"""
import re
import unicodedata
import uuid
from datetime import datetime, timedelta
from .settings import Settings
from .retrieval import Retriever
from .llm import LocalModel, ModelUnavailable
from .transit import Transit, TransitUnavailable, DOC, observed_time

def norm(s):
    return ''.join(c for c in unicodedata.normalize('NFD',s.lower()) if unicodedata.category(c)!='Mn')

def source(c):
    url=c.get('source_url',c.get('url',DOC))
    if url.startswith('base/'):url='/'+url
    return {'id':c['id'],'title':c.get('source_title',c.get('title',c['id'])),'url':url}

class Engine:
    def __init__(self, settings=None, model=None, transit=None):
        self.settings=settings or Settings()
        self.model=model or LocalModel(self.settings)
        self.transit=transit or Transit(self.settings)
        self.retriever=Retriever(threshold=self.settings.threshold)
    async def answer(self, question, configuration='agent',line_code=None,stop_code=None,direction=None,scenario='normal',evaluation=False):
        if configuration not in ('baseline','rag','agent'):raise ValueError('Configuração inválida')
        result={'status':'not_found','answer':'Não consta informação suficiente na base para responder.','sources':[],'updated_at':None,'data_mode':'documental','model':self.settings.model,'request_id':str(uuid.uuid4()),'warnings':[],'options':[]}
        meta={'model_called':False,'model_raw':None,'model_json_valid':None,'configuration':configuration,'guardrail':None,'tool':None}
        def finish():
            if evaluation:result['metadata']=meta
            return result
        evidence=[]
        q=norm(question)
        query_input=question
        if line_code or stop_code or direction:
            query_input+='\nParâmetros confirmados: '+str({'line_code':line_code,'stop_code':stop_code,'direction':direction})
        if configuration in ('rag','agent'):
            evidence=self.retriever.search(question,k=3)
        if configuration=='agent':
            # Rules are part of the specialization, not trained weights. Small bounded action space.
            if re.search(r'\b(receita|bitcoin|futebol|senha|token|segredo|hackear|medicamento)\b',q):
                result['answer']='Não consta: atendo informações de ônibus municipais de São Paulo. Não forneço segredos ou dados pessoais.'
                return finish()
            if re.search(r'\b(baldea|conex|trajeto completo|rota completa|mais rapido|mais rapida)',q):
                result['answer']='Não consta planejamento completo de viagens ou baldeações neste recorte. Consulte o planejador oficial da SPTrans.'
                result['sources']=[{'id':'SPTRANS','title':'Planeje sua viagem — SPTrans','url':'https://www.sptrans.com.br/'}]
                return finish()
            action=None
            if stop_code or re.search(r'quando.*(chega|passa)|quanto.*(tempo|esper)|proximo onibus|previsao.*agora|chega.*agora',q):action='arrivals'
            elif re.search(r'(pontos|paradas).*(linha)|linha.*(pontos|paradas)',q) and (line_code or re.search(r'\d{4}',q)):action='stops'
            elif re.search(r'(busc|consult|quais|sentido|linha).*\b[0-9][0-9A-Z]{3}',question,re.I):action='lines'
            if action:
                meta['tool']=action
                result['data_mode']=self.settings.mode
                if self.settings.mode=='demo':result['warnings'].append('DEMONSTRAÇÃO: dados sintéticos fixos de 19/11/2026 às 10h, não são uma consulta ao vivo.')
                if action=='arrivals' and (not line_code or not stop_code):
                    result.update(status='clarification',answer='Informe o código da linha por sentido e o código do ponto para consultar a previsão. O número no letreiro pode ter mais de um sentido.')
                    return finish()
                if action=='stops' and not line_code:
                    result.update(status='clarification',answer='Informe o código da linha por sentido para consultar as paradas disponíveis.')
                    return finish()
                match=re.search(r'\b([0-9][0-9a-z]{3})(?:[-/]\d{2})?\b',q)
                term=match.group(1).upper() if match else ''
                try:
                    tool=await self.transit.call(action,query=term,line_code=line_code,stop_code=stop_code,direction=direction,scenario=scenario)
                    meta['tool_result']=tool
                    result['updated_at']=tool['observed_at']
                    data=tool['data'];text=''
                    if action=='lines':
                        if not data:
                            result['answer']='Não consta linha correspondente no retorno consultado. Isso não comprova ausência de serviço.'
                            return finish()
                        result['options']=[{'line_code':x['cl'],'direction':x['sl'],'label':f"{x['lt']}-{x['tl']} · sentido {x['sl']} · {x['tp']} / {x['ts']}"} for x in data[:20]]
                        text='Linhas retornadas: '+'; '.join(f"{x['lt']}-{x['tl']}, código {x['cl']}, sentido {x['sl']}, letreiros {x['tp']} / {x['ts']}" for x in data[:10])+'.'
                        if len(data)>1:
                            result['status']='clarification';text+=' Escolha a linha e o sentido antes de consultar a chegada.'
                    elif action=='stops':
                        if not data:
                            result['answer']='Não constam paradas no retorno. A cobertura da categoria é limitada a corredores; ausência de retorno não prova ausência de ponto ou serviço.'
                            return finish()
                        result['options']=[{'stop_code':x['cp'],'label':x['np']} for x in data[:30]]
                        text='Paradas retornadas: '+'; '.join(f"{x['np']} (código {x['cp']})" for x in data[:30])+'. A categoria não cobre necessariamente todos os pontos da cidade.'
                    else:
                        lines=(data.get('p') or {}).get('l') or []
                        lines=[x for x in lines if x.get('cl')==line_code and (not direction or x.get('sl')==direction)]
                        arrivals=[]
                        for line in lines:
                            for vehicle in line.get('vs',[]):
                                if not re.fullmatch(r'\d{2}:\d{2}',str(vehicle.get('t',''))):continue
                                predicted=observed_time(vehicle['t'],datetime.fromisoformat(tool['queried_at']))
                                delta=round((predicted-datetime.fromisoformat(tool['queried_at'])).total_seconds()/60)
                                if delta<0:continue
                                arrivals.append(f"{line['c']} sentido {line['sl']}: previsão {vehicle['t']} (aproximadamente {delta} minutos no relógio {'da simulação' if tool['synthetic'] else 'da consulta'})")
                        if not arrivals:
                            result['answer']='Não consta previsão de chegada nesse retorno. Isso não significa ausência de ônibus ou de serviço. Tente novamente ou consulte a SPTrans.'
                            result['sources']=[{'id':'SPTRANS_QUERY','title':'Retorno da consulta SPTrans (simulado)' if tool['synthetic'] else 'Consulta SPTrans Olho Vivo','url':DOC}]
                            return finish()
                        text='; '.join(arrivals[:6])+'. Previsão não é garantia de chegada; trânsito e operação podem mudar.'
                    if tool['synthetic']:text='DEMONSTRAÇÃO com dados sintéticos, não ao vivo. '+text
                    evidence=[{'id':'SPTRANS_QUERY','text':text,'title':'Consulta SPTrans (cenário sintético)' if tool['synthetic'] else 'Consulta SPTrans Olho Vivo','source_url':DOC}]
                except (TransitUnavailable,KeyError,TypeError,ValueError) as exc:
                    result.update(status='unavailable',answer=str(exc) if isinstance(exc,TransitUnavailable) else 'A fonte retornou dados incompletos. Tente novamente.')
                    return finish()
            if not evidence:
                return finish()
        try:
            instruction=''
            if configuration=='agent':instruction='Selecione a evidência que responde à pergunta. Copie seu texto fielmente em answer, sem acrescentar fatos. Cite seu id em source_ids. Se nenhuma responder, retorne not_found. Dados sintéticos nunca são atuais.'
            compact=[{'id':x['id'],'text':x['text']} for x in evidence]
            parsed,modelmeta=await self.model.generate(query_input,compact,instruction)
            meta.update(modelmeta)
            if not meta['model_json_valid']:
                result.update(status='unavailable',answer='O modelo local retornou uma resposta inválida. Tente novamente.');return finish()
            valid_ids={x['id']:x for x in evidence}
            ids=[s for s in parsed['source_ids'] if s in valid_ids]
            if configuration=='agent':
                if parsed['status']=='not_found' and not meta['tool']:
                    result.update(status='not_found',answer='Não consta informação suficiente na base para responder.');return finish()
                chosen=valid_ids[ids[0]] if ids else evidence[0]
                # A precise, auditable grounding boundary: free-form unsupported claims never reach the citizen.
                if norm(parsed['answer']).strip()!=norm(chosen['text']).strip():
                    meta['guardrail']='extractive_fallback'
                    answer=chosen['text']
                else:answer=parsed['answer']
                result.update(answer=answer,sources=[source(chosen)])
                if result['status']!='clarification':result['status']='ok'
            else:
                # Raw baseline / simple RAG output is intentionally NOT polished by the specialized validator.
                result.update(status=parsed['status'],answer=parsed['answer'],sources=[source(valid_ids[i]) for i in ids])
                meta['invalid_source_ids']=[s for s in parsed['source_ids'] if s not in valid_ids]
        except ModelUnavailable:
            result.update(status='unavailable',answer='O modelo local está indisponível. Tente novamente. Você também pode consultar diretamente a SPTrans.')
        return finish()
