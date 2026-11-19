'use strict';

const byId = (id) => document.getElementById(id);
const form = byId('ask-form');
const question = byId('question');
const result = byId('result');
let busy = false;
let serviceMode = 'demo';
let lastQuestion = '';

const statusLabels = {
  ok: 'Informação encontrada',
  not_found: 'Não consta',
  clarification: 'Precisamos de um detalhe',
  unavailable: 'Consulta indisponível'
};

function announce(message) {
  byId('announcer').textContent = message;
}

function safeUrl(value) {
  if (value === '/base/POLITICA-DO-PRODUTO.md') return value;
  try {
    const url = new URL(value);
    return url.protocol === 'https:' ? url.href : null;
  } catch {
    return null;
  }
}

function clearFields() {
  byId('line-code').value = '';
  byId('stop-code').value = '';
  byId('direction').value = '';
}

function populateExample(button) {
  if (busy) return;
  clearFields();
  if (button.dataset.demo) {
    question.value = 'Qual a previsão de chegada da linha 8000 neste ponto?';
    byId('line-code').value = '1273';
    byId('stop-code').value = '4200153';
    byId('direction').value = '1';
    byId('details-fields').open = true;
  } else {
    question.value = button.dataset.example || '';
  }
  question.focus();
  announce('Exemplo preenchido. Confira a pergunta e selecione Consultar.');
}

document.querySelectorAll('[data-example], [data-demo]').forEach((button) => {
  button.addEventListener('click', () => populateExample(button));
});

function setBusy(value) {
  busy = value;
  form.setAttribute('aria-busy', String(value));
  byId('submit-button').disabled = value;
  byId('submit-text').textContent = value ? 'Consultando…' : 'Consultar';
  byId('submit-spinner').hidden = !value;
  document.querySelectorAll('[data-example], [data-demo]').forEach((button) => { button.disabled = value; });
  if (value) announce('Consulta em andamento. A resposta pode levar alguns instantes.');
}

function renderSources(sources) {
  const list = byId('sources');
  list.replaceChildren();
  for (const source of Array.isArray(sources) ? sources : []) {
    if (!source || typeof source !== 'object') continue;
    const item = document.createElement('li');
    const url = safeUrl(source.url);
    const label = typeof source.title === 'string' ? source.title : 'Fonte consultada';
    if (url) {
      const link = document.createElement('a');
      link.href = url;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      link.textContent = label;
      link.setAttribute('aria-label', label + ' (abre em nova aba)');
      item.append(link);
    } else {
      item.textContent = label;
    }
    list.append(item);
  }
  byId('sources-box').hidden = list.children.length === 0;
}

function renderOptions(options) {
  const container = byId('options');
  container.replaceChildren();
  for (const option of Array.isArray(options) ? options : []) {
    if (typeof option === 'string') {
      const text = document.createElement('p');
      text.textContent = option;
      container.append(text);
      continue;
    }
    if (!option || typeof option !== 'object') continue;
    const label = option.label || option.title || option.name;
    if (typeof label !== 'string') continue;
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = label;
    button.addEventListener('click', () => {
      if (busy) return;
      if (Number.isSafeInteger(option.line_code) && option.line_code > 0) byId('line-code').value = String(option.line_code);
      if (Number.isSafeInteger(option.stop_code) && option.stop_code > 0) byId('stop-code').value = String(option.stop_code);
      if ([1, 2].includes(option.direction)) byId('direction').value = String(option.direction);
      byId('details-fields').open = true;
      question.value = lastQuestion;
      question.focus();
      announce('Detalhe selecionado. Selecione Consultar para atualizar a resposta.');
    });
    container.append(button);
  }
  container.hidden = container.children.length === 0;
}

function renderResponse(data, asked) {
  const status = Object.hasOwn(statusLabels, data.status) ? data.status : 'unavailable';
  byId('result-title').textContent = status === 'clarification' ? 'Vamos esclarecer sua consulta' : 'Resposta à sua pergunta';
  byId('result-badge').textContent = statusLabels[status];
  byId('result-badge').className = 'badge' + (status === 'unavailable' ? ' badge-error' : status === 'clarification' ? ' badge-clarification' : '');
  byId('asked-question').textContent = asked;
  byId('answer').textContent = typeof data.answer === 'string' ? data.answer : 'Não foi possível obter uma resposta agora.';
  const warnings = Array.isArray(data.warnings) ? data.warnings.filter((value) => typeof value === 'string') : [];
  if (data.data_mode === 'demo') warnings.unshift('DEMONSTRAÇÃO: os dados desta consulta são de teste. Eles não representam a chegada real de um ônibus.');
  const warningList = byId('warnings');
  warningList.replaceChildren();
  for (const warning of [...new Set(warnings)]) {
    const item = document.createElement('li');
    item.textContent = warning;
    warningList.append(item);
  }
  byId('warnings-box').hidden = warnings.length === 0;
  byId('data-mode').textContent = ({demo: 'Dados de teste · demonstração', live: 'Consulta à SPTrans', documental: 'Informação documental'})[data.data_mode] || '';
  const time = byId('updated-at');
  const timestamp = typeof data.updated_at === 'string' ? new Date(data.updated_at) : null;
  if (timestamp && !Number.isNaN(timestamp.getTime())) {
    time.dateTime = timestamp.toISOString();
    time.textContent = 'Atualização informada: ' + new Intl.DateTimeFormat('pt-BR', {dateStyle: 'short', timeStyle: 'short', timeZone: 'America/Sao_Paulo'}).format(timestamp) + ' (São Paulo)';
  } else {
    time.removeAttribute('datetime');
    time.textContent = '';
  }
  renderSources(data.sources);
  renderOptions(data.options);
  byId('error-fallback').hidden = status !== 'unavailable';
  result.hidden = false;
  announce(statusLabels[status] + '. Resposta disponível abaixo do formulário.');
  result.focus({preventScroll: true});
  result.scrollIntoView({behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start'});
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (busy || !form.reportValidity()) return;
  const asked = question.value.trim();
  if (!asked) {
    question.setCustomValidity('Digite uma pergunta para continuar.');
    question.reportValidity();
    return;
  }
  lastQuestion = asked;
  const payload = {question: asked};
  for (const [field, id] of [['line_code', 'line-code'], ['stop_code', 'stop-code'], ['direction', 'direction']]) {
    const value = byId(id).value;
    if (value) payload[field] = Number(value);
  }
  setBusy(true);
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 180000);
  try {
    const response = await fetch('/api/ask', {
      method: 'POST',
      headers: {'Content-Type': 'application/json', 'Accept': 'application/json'},
      body: JSON.stringify(payload),
      signal: controller.signal
    });
    const data = await response.json();
    if (!data || typeof data !== 'object' || typeof data.answer !== 'string') throw new Error('Invalid response');
    renderResponse(data, asked);
  } catch (error) {
    renderResponse({
      status: 'unavailable',
      answer: error.name === 'AbortError' ? 'A consulta demorou mais que o esperado. Não temos uma resposta confirmada agora.' : 'Não foi possível concluir a consulta. Verifique sua conexão e tente novamente.',
      sources: [], warnings: [], options: []
    }, asked);
  } finally {
    window.clearTimeout(timeout);
    setBusy(false);
  }
});

question.addEventListener('input', () => question.setCustomValidity(''));

async function loadServiceState() {
  try {
    const response = await fetch('/api/config', {headers: {'Accept': 'application/json'}});
    if (!response.ok) throw new Error('Config unavailable');
    const config = await response.json();
    serviceMode = config.mode === 'live' ? 'live' : 'demo';
    byId('mode-badge').textContent = serviceMode === 'live' ? 'CONSULTA SPTRANS' : 'DEMONSTRAÇÃO';
    byId('mode-badge').className = 'badge' + (serviceMode === 'live' ? '' : ' badge-demo');
    byId('mode-description').textContent = serviceMode === 'live' ? 'As informações disponíveis dependem da cobertura da SPTrans. Confira a atualização em cada resposta.' : 'Consultas de chegada usam dados de teste. Não use esses horários para planejar uma viagem real.';
    byId('demo-example').hidden = serviceMode === 'live';
  } catch {
    byId('mode-description').textContent = 'Não foi possível confirmar o modo de consulta. Não há informação de chegada ao vivo confirmada.';
    byId('demo-example').hidden = true;
  }
  try {
    const ready = await fetch('/readyz', {headers: {'Accept': 'application/json'}});
    byId('service-status').textContent = ready.ok ? 'Assistente disponível para consultas.' : 'Assistente temporariamente indisponível. Você pode tentar uma consulta ou acessar a SPTrans.';
  } catch {
    byId('service-status').textContent = 'Sem conexão com o assistente no momento.';
  }
}

loadServiceState();
