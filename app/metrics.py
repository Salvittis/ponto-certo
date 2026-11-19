from prometheus_client import Counter, Gauge, Histogram
REQUESTS = Counter('ponto_certo_http_requests_total', 'HTTP requests', ['route','method','status'])
LATENCY = Histogram('ponto_certo_http_request_duration_seconds','HTTP duration',['route'],buckets=(.1,.5,1,2,5,10,30,60,120))
ACTIVE = Gauge('ponto_certo_http_inflight','Active HTTP requests')
MODEL_ACTIVE = Gauge('ponto_certo_llm_inflight','Active LLM generations')
MODEL_CALLS = Counter('ponto_certo_llm_requests_total','LLM calls',['outcome'])
MODEL_LATENCY = Histogram('ponto_certo_llm_duration_seconds','LLM duration',buckets=(.5,1,2,5,10,30,60,120))
ASK_STATUS = Counter('ponto_certo_answers_total','Assistant responses',['status'])

MODEL_CAPACITY = Gauge('ponto_certo_llm_capacity','LLM concurrency slots')
MODEL_CAPACITY.set(1)
MODEL_READY = Gauge('ponto_certo_model_ready','LLM ready at last probe')
