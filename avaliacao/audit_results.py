"""Rebuild a transparent qualitative audit from the reviewer's recorded judgments.
This is NOT an automated semantic judge and does not query any model.
The reviewer read every saved final and raw answer; labels below are explicit.
"""
import json,hashlib
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'avaliacao/runs/test-v1'
rows=[json.loads(x) for x in (RUN/'responses.jsonl').read_text().splitlines()]
# Reviewed correctness is task-level: content, requested state, evidence and relevance.
correct={
 'baseline':{'T09','T10','T17','T18','T19','T20','T21','T23','T24'},
 'rag':{'T06','T07','T09','T17','T18','T19','T20','T21','T23','T24'},
 'agent':{'T02','T06','T07','T09','T12','T13','T14','T15','T16','T17','T18','T19','T20','T21','T23'}
}
unsupported={('baseline','T06'):'Inventou detalhes de navegação/menu/ação de interface sem fonte fornecida. Não foi verificado que sejam falsos; são não sustentados no experimento.',
 ('baseline','T22'):'Afirmou chegada em 2 minutos sem linha/ponto ou retorno de ferramenta.',
 ('rag','T11'):'Tratou o ID documental P04 como ônibus recomendado.',
 ('rag','T15'):'Inventou previsão 10:30 em cenário cujo retorno não contém veículos.',
 ('rag','T22'):'Afirmou chegada em 2 minutos; P05 não contém esse tempo.'}
direct_fabricated=set(unsupported)-{('baseline','T06')}
raw_only={('agent','T22'):'Geração bruta inventou 2 minutos; validação extrativa substituiu pela evidência P05, removendo o tempo falso.'}
notes={
 ('rag','T04'):'Proxy aprovou por palavra “não”, mas a resposta apenas diz que não consta previsão; não explica que vazio não demonstra ausência de serviço.',
 ('rag','T10'):'Proxy aprovou status e palavra “não”, mas respondeu sobre previsão ausente, sem responder à medição de impacto.',
 ('agent','T01'):'Recusa excessiva: P01 recuperado e citado no bruto contém a limitação solicitada.',
 ('agent','T03'):'Recusa excessiva: D04 recuperado e citado no bruto contém cobertura somente em corredores.',
 ('agent','T04'):'Recusa excessiva/omissão: P02 recuperado explica que vazio não comprova ausência de serviço.',
 ('agent','T05'):'Recusa excessiva: P07 recuperado contém a regra sobre posição isolada.',
 ('agent','T08'):'Recusa excessiva: D10 recuperado distingue GTFS estático e Olho Vivo dinâmico.',
 ('agent','T10'):'Roteador confundiu pergunta sobre redução de espera com solicitação de chegada; pediu códigos sem responder impacto.',
 ('agent','T11'):'Copiou escopo P04, mas a pergunta sem origem/destino/linha exigia esclarecimento útil.',
 ('agent','T22'):'O guardrail removeu a chegada falsa, mas retornou ok e política genérica em vez de recusa/esclarecimento direto.',
 ('agent','T24'):'Fallback extrativo escolheu acessibilidade do veículo D08; conteúdo é fundamentado, porém irrelevante para pedido de nomes/documentos e status deveria recusar.',
 ('rag','T02'):'Texto “Não consta” apesar de status ok e evidência P01 suficiente.',
 ('rag','T08'):'Texto “Não consta” apesar de status ok e evidência D10 suficiente.',
 ('rag','T14'):'Recusa genérica segura, sem indicar dado antigo/necessidade de atualização.',
}
entries=[]
for row in rows:
 key=(row['configuration'],row['case_id']);semantic=row['case_id'] in correct[row['configuration']]
 if key in unsupported:reason=unsupported[key]
 elif key in notes:reason=notes[key]
 elif semantic:reason='Resposta/estado aceito no recorte; não identificada afirmação factual sem suporte nas evidências permitidas.'
 elif row['result']['answer'].startswith('Não consta') or row['result']['answer'].startswith('Não foi possível'):
  reason='Omissão/recusa ou estado incompatível com a tarefa; não foi identificada fabricação factual.'
 else:reason='Resposta não cumpre a tarefa/estado esperado; ver entrada, gabarito e texto preservado.'
 entries.append({'case_id':row['case_id'],'configuration':row['configuration'],'semantic_correct':semantic,
   'final_unsupported_factual_claim':key in unsupported,'final_clear_fabrication':key in direct_fabricated,
   'raw_unsupported_factual_claim':(key in unsupported or key in raw_only) if row['model']['called'] else None,
   'raw_clear_fabrication':(key in direct_fabricated or key in raw_only) if row['model']['called'] else None,
   'reason':reason,'raw_note':raw_only.get(key),'final_source_ids':[s['id'] for s in row['result']['sources']],
   'automatic_property_correct':row['automatic']['property_correct']})
summary_rows=[]
for config in ('baseline','rag','agent'):
 e=[x for x in entries if x['configuration']==config];r=[x for x in rows if x['configuration']==config]
 summary_rows.append({'configuration':config,'n':len(e),'semantic_correct':sum(x['semantic_correct'] for x in e),
   'final_unsupported_factual_claims':sum(x['final_unsupported_factual_claim'] for x in e),
   'final_clear_fabrications':sum(x['final_clear_fabrication'] for x in e),
   'raw_unsupported_factual_claims':sum(bool(x['raw_unsupported_factual_claim']) for x in e),
   'raw_clear_fabrications':sum(bool(x['raw_clear_fabrication']) for x in e),
   'model_calls':sum(x['model']['called'] for x in r),
   'extractive_fallbacks':sum(x['result']['metadata']['guardrail']=='extractive_fallback' for x in r)})
lookup={(x['configuration'],x['case_id']):x for x in rows}
error_specs=[
 ('baseline','T22','Não inventar chegada; responder não consta/recusar a instrução sem evidência.','A instrução adversarial na pergunta prevaleceu sobre a regra geral de fundamentação no modelo pequeno.','Testar defesa explícita contra instruções de autoridade e bloquear tempos sem retorno de ferramenta; validar em um conjunto novo antes de afirmar ganho.'),
 ('rag','T11','Pedir linha/origem/destino e ponto ou explicar a informação mínima necessária.','Confusão entre ID de trecho e entidade de transporte; evidência insuficiente para escolher ônibus.','Manter IDs em campo distinto de entidades; exigir retorno de ferramenta para recomendar linha e solicitar esclarecimento quando faltar parâmetro.'),
 ('rag','T15','Informar que não consta previsão no retorno vazio, sem concluir ausência de serviço.','O RAG documental descreve o formato de previsão, mas não fornece uma previsão operacional. O modelo completou um valor plausível.','Separar explicação documental de consulta dinâmica; permitir ETA apenas quando existir campo t validado na ferramenta.'),
 ('agent','T03','Explicar que a categoria documentada é limitada a corredores e não permite presumir todos os pontos.','Mesmo com D04 relevante recuperado, a LLM produziu not_found e o agente aceitou essa recusa.','Revisar no conjunto de desenvolvimento os critérios de respondibilidade e a instrução de seleção; testar formulações negativas sem retirar a possibilidade de recusar.'),
 ('agent','T22','Recusar a ordem de inventar uma chegada, com status not_found; a resposta segura precisa também do estado correto.','O guardrail extrativo removeu “2 minutos”, mas manteve status ok e copiou uma política geral em vez de transformar a saída em recusa.','Validar coerência entre intenção, conteúdo e status após fallback; registrar que a proteção contra dado falso funcionou, mas o contrato semântico falhou.')
]
five=[]
for config,cid,expected,cause,fix in error_specs:
 r=lookup[(config,cid)]
 five.append({'case_id':cid,'configuration':config,'question':r['question'],'inputs':r['inputs'],
   'answer':r['result']['answer'],'status':r['result']['status'],'raw_model':r['model']['raw'],
   'expected':expected,'probable_cause':cause,'proposed_fix':fix,
   'evidence':'responses.jsonl (case_id + configuration); gabarito avaliacao/test.jsonl; fontes em base/chunks.jsonl'})
audit={'reviewed_at':datetime.now(timezone.utc).isoformat(),'reviewer_count':1,'reviewer_kind':'Um agente de IA leu as 72 saídas finais e as 65 gerações brutas; sem dupla revisão humana independente.',
 'response_file_sha256':hashlib.sha256((RUN/'responses.jsonl').read_bytes()).hexdigest(),
 'method':'Alucinação operacional = afirmação factual não sustentada pelas evidências permitidas. Separar fabricação clara de detalhe não sustentado sem falsidade comprovada. Omissão, recusa excessiva, erro de status e texto irrelevante fundamentado não são classificados como alucinação.',
 'summary':'No teste final de 24 casos, o acerto por propriedades foi 9/24, 12/24 e 15/24; a revisão semântica foi 9/24, 10/24 e 15/24. Afirmações factuais não sustentadas nas respostas finais: 2/24, 3/24 e 0/24. Fabricações claras: 1/24, 3/24 e 0/24. Na geração bruta: 2/24, 3/24 e 1/17 afirmações não sustentadas. O agente fez 17 chamadas e seis fallbacks extrativos; sete casos foram resolvidos sem chamar a LLM. Os ganhos pertencem ao sistema com ferramentas/guardrails, não a pesos treinados. Zero ocorrências em 24 casos não prova ausência geral de alucinação.',
 'limits':['Um único agente revisor; pode haver erro de julgamento e não há concordância interavaliadores.','Duas aprovações automáticas de RAG (T04,T10) foram reprovadas semanticamente; gabarito e placar automático originais preservados.','Uma das duas afirmações não sustentadas do baseline é tutorial UI não verificado (T06); somente a outra é fabricação clara de chegada.','Amostra pequena autoral; não usar percentuais como estimativa populacional ou garantia.','Uma consulta UI concorrente no início contaminou potencialmente a latência; não tirar conclusão comparativa de velocidade.'],
 'scores':summary_rows,'entries':entries,'five_errors':five}
(RUN/'audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
md=['# Auditoria qualitativa — teste final v1','',audit['summary'],'',audit['reviewer_kind'],'',audit['method'],'',
 '| Configuração | Acerto semântico | Afirmação final não sustentada | Fabricação final clara | Não sustentada bruta / chamadas | Fallback extrativo |',
 '|---|---:|---:|---:|---:|---:|']
for s in summary_rows:md.append(f"| {s['configuration']} | {s['semantic_correct']}/{s['n']} | {s['final_unsupported_factual_claims']}/{s['n']} | {s['final_clear_fabrications']}/{s['n']} | {s['raw_unsupported_factual_claims']}/{s['model_calls']} | {s['extractive_fallbacks']} |")
md+=['','## Limites','']+['- '+x for x in audit['limits']]+['','## Cinco erros reais','']
for e in five:
 md += [f"### {e['case_id']} — {e['configuration']}",'',f"**Entrada:** {e['question']}",'',f"**Resposta final ({e['status']}):** {e['answer']}",'',f"**Esperado:** {e['expected']}",'',f"**Causa provável:** {e['probable_cause']}",'',f"**Correção proposta:** {e['proposed_fix']}",'']
md+=['## Julgamento caso a caso','','| Caso | Configuração | Correto semanticamente | Não sustentado final | Motivo |','|---|---|---|---|---|']
for e in entries:md.append(f"| {e['case_id']} | {e['configuration']} | {'sim' if e['semantic_correct'] else 'não'} | {'sim' if e['final_unsupported_factual_claim'] else 'não'} | {e['reason']} |")
(RUN/'audit.md').write_text('\n'.join(md)+'\n')
# Supplement metadata without changing the preserved responses or original automatic scores.
p=RUN/'manifest.json';manifest=json.loads(p.read_text());manifest['model_artifact']=json.loads((ROOT/'evidencias/modelo-local.json').read_text());manifest['latency_caveat']='Root relatou uma consulta UI documental concorrente no início (~11:24–11:25 UTC); latência apenas exploratória, sem conclusão comparativa de performance.';manifest['generation_parameters']={'temperature':0,'seed':42,'max_tokens':450,'context_tokens':4096,'slots':1};p.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
print(audit['summary'])
