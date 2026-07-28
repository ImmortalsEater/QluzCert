// ==================== STATE ====================
const DB = {
  get(k){try{return JSON.parse(localStorage.getItem('crt_'+k)||'null')}catch{return null}},
  set(k,v){localStorage.setItem('crt_'+k,JSON.stringify(v))},
};
const storedClientes = DB.get('clientes');
let clientes = (Array.isArray(storedClientes) && storedClientes.length)
  ? storedClientes
  : ((typeof window !== 'undefined' && Array.isArray(window.INITIAL_CLIENTES) && window.INITIAL_CLIENTES.length>0)
      ? window.INITIAL_CLIENTES.slice()
      : []);
let parceiros = (typeof window !== 'undefined' && Array.isArray(window.INITIAL_PARCEIROS)) ? window.INITIAL_PARCEIROS.slice() : [];
let precos = (typeof window !== 'undefined' && Array.isArray(window.INITIAL_PRECOS)) ? window.INITIAL_PRECOS.slice() : [];
let leads = (typeof window !== 'undefined' && Array.isArray(window.INITIAL_LEADS)) ? window.INITIAL_LEADS.slice() : [];
let notificacoesRecentes = (typeof window !== 'undefined' && Array.isArray(window.INITIAL_NOTIFICACOES)) ? window.INITIAL_NOTIFICACOES.slice() : [];
let editingId = null;
let backendAlertData = (typeof window !== 'undefined' && window.INITIAL_ALERTS) ? window.INITIAL_ALERTS : null;

const ROWS_PER_PAGE = 50;
let planilhaPage = 1;
let clientesPage = 1;

const STATUS_LIST = ['Novo Lead','Documentação Pendente','Aguardando Pagamento','Agendado para Vídeo','Emitido'];
const STATUS_CLASSES = ['badge-novo','badge-doc','badge-pag','badge-video','badge-emitido'];
const STATUS_COLORS = ['info','warn','purple','teal','success'];
const KANBAN_COLORS = ['var(--info)','var(--warn)','var(--purple)','var(--teal)','var(--success)'];

function save(){DB.set('clientes',clientes);DB.set('parceiros',parceiros);DB.set('precos',precos);updateBadges()}

function saveLocalOnly(){DB.set('clientes',clientes);DB.set('parceiros',parceiros);DB.set('precos',precos);updateBadges();setStatus('Salvo localmente'); showToast('Salvo localmente','success')}

function setStatus(message){
  const status = document.getElementById('save-status');
  if(status){ status.textContent = message; }
}

// Toast visual
function _ensureToastContainer(){
  let c = document.querySelector('.toast-container');
  if(!c){ c = document.createElement('div'); c.className='toast-container'; document.body.appendChild(c); }
  return c;
}
const TOAST_ICONS = {success:'ti-circle-check', error:'ti-alert-circle', warning:'ti-alert-triangle', info:'ti-info-circle'};
function showToast(message, type='info', timeout=3500){
  try{
    const container = _ensureToastContainer();
    const t = document.createElement('div');
    t.className = 'toast '+(type||'info');
    const icon = document.createElement('i');
    icon.className = 'toast-icon ti '+(TOAST_ICONS[type]||TOAST_ICONS.info);
    const text = document.createElement('span');
    text.className = 'toast-text';
    text.textContent = message;
    t.appendChild(icon);
    t.appendChild(text);
    container.appendChild(t);
    requestAnimationFrame(()=>requestAnimationFrame(()=>t.classList.add('toast-visible')));
    setTimeout(()=>{t.classList.remove('toast-visible');}, timeout-200);
    setTimeout(()=>{try{container.removeChild(t)}catch(e){}}, timeout);
  }catch(e){console.warn('Toast failed',e)}
}

function showDjangoMessages(){
  const items = Array.isArray(window.DJANGO_MESSAGES) ? window.DJANGO_MESSAGES : [];
  const TAG_TO_TYPE = {success:'success', error:'error', warning:'warning', info:'info', debug:'info'};
  const TAG_TO_TIMEOUT = {success:4200, error:6500, warning:5500, info:4200};
  items.forEach(function(item, i){
    const type = TAG_TO_TYPE[item.tags] || 'info';
    setTimeout(()=>showToast(item.text, type, TAG_TO_TIMEOUT[type]), i*250);
  });
}

// Inicializa o menu de salvar (botão único com opções)
function initSaveMenu(){
  const mainBtn = document.getElementById('save-main-btn');
  const menu = document.getElementById('save-menu');
  const btnLocal = document.getElementById('save-local-btn');
  if(!mainBtn || !menu) return;
  mainBtn.addEventListener('click', function(e){ e.stopPropagation(); menu.style.display = (menu.style.display==='block'?'none':'block'); });
  // fechar ao clicar fora
  document.addEventListener('click', function(){ if(menu) menu.style.display='none' });
  if(btnLocal) btnLocal.addEventListener('click', function(e){ e.stopPropagation(); menu.style.display='none'; saveLocalOnly(); });
  const btnExport = document.getElementById('export-btn');
  if(btnExport) btnExport.addEventListener('click', function(e){ e.stopPropagation(); menu.style.display='none'; exportState(); });
}

async function atualizarPlanilha(){
  const btn = document.getElementById('atualizar-planilha-btn');
  if(btn) btn.disabled = true;
  try{
    const response = await fetch('/atualizar-planilha/', {
      method: 'POST',
      headers: {'X-CSRFToken': getCsrfToken(), 'X-Requested-With': 'XMLHttpRequest'},
    });
    if(!response.ok) throw new Error('Falha ao atualizar');
    showToast('Planilha atualizada, recarregando...', 'success');
    setTimeout(()=>{ location.hash = 'clientes'; location.reload(); }, 500);
  }catch(err){
    console.error(err);
    showToast('Erro ao atualizar planilha', 'error');
    if(btn) btn.disabled = false;
  }
}

async function exportState(){
  // baixa um xlsx gerado a partir dos dados atuais da planilha do Google Sheets
  try{
    const resp = await fetch('/app_state_download/');
    // show overlay while generating
    showExportOverlay();
    if(!resp.ok){
      const txt = await resp.text();
      showToast('Erro ao exportar: '+txt,'error');
      return;
    }
    const blob = await resp.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'clientes_parceiros_precos.xlsx';
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
    showToast('Arquivo preparado para download','success');
  }catch(err){
    console.error(err);
    showToast('Erro ao exportar','error');
  }
  finally{
    hideExportOverlay();
  }
}

function showExportOverlay(){
  const ov = document.getElementById('export-overlay');
  if(ov) ov.style.display='flex';
}
function hideExportOverlay(){
  const ov = document.getElementById('export-overlay');
  if(ov) ov.style.display='none';
}

function renderTo(id, html){const el=document.getElementById(id); if(el) el.innerHTML=html}
function debounce(fn, delay=200){
  let t;
  return function(...args){
    clearTimeout(t);
    t=setTimeout(()=>fn.apply(this,args), delay);
  };
}
function normalizeQuery(v){return (v||'').trim().toLowerCase()}
function updateResultCount(elId, shown, total){
  const el=document.getElementById(elId);
  if(!el) return;
  el.textContent = total===0 ? '' : (shown===total ? `${total} resultado${total===1?'':'s'}` : `${shown} de ${total} resultado${total===1?'':'s'}`);
}
function renderPaginationControls(containerId, page, totalPages, onGotoFnName){
  const el=document.getElementById(containerId);
  if(!el) return;
  if(totalPages<=1){ el.innerHTML=''; return; }
  el.innerHTML = `
    <button type="button" class="btn btn-sm" ${page<=1?'disabled':''} onclick="${onGotoFnName}(${page-1})"><i class="ti ti-chevron-left"></i></button>
    <span class="pagination-info">Página ${page} de ${totalPages}</span>
    <button type="button" class="btn btn-sm" ${page>=totalPages?'disabled':''} onclick="${onGotoFnName}(${page+1})"><i class="ti ti-chevron-right"></i></button>
  `;
}
function statusIndex(status){return STATUS_LIST.indexOf(status)>=0?STATUS_LIST.indexOf(status):0}
function statusBadge(status){const i=statusIndex(status); return `<span class="badge ${STATUS_CLASSES[i]}">${escapeHtml(status||'Novo Lead')}</span>`}
function parceiroBadge(id){const p=parceiros.find(x=>x.id===id); return p?`<span class="parceiro-tag">${escapeHtml(p.nome)}</span>`:'—'}
function formatVencimento(c){const d=c.dataVencimento?daysUntil(c.dataVencimento):null; return d!==null&&d<=60?`<span class="badge ${d<0?'badge-vencido':'badge-vencendo'}">${d<0?'Vencido':d+' dias'}</span>`:(c.dataVencimento?`<span style="font-size:12px;color:var(--muted)">${fmtDate(c.dataVencimento)}</span>`:'—')}
function tableRows(rows){return rows.join('')}
function uid(){return Date.now()+Math.random().toString(36).slice(2)}
// Escapa texto vindo da planilha (nomes, status, contatos etc.) antes de
// interpolar em innerHTML -- sem isso, um valor como <img src=x onerror=...>
// gravado por alguém com acesso de edição na planilha executaria no
// navegador de quem visse o dashboard/kanban/tabela.
function escapeHtml(value){
  return String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
}
// Datas "YYYY-MM-DD" puras (sem hora) são interpretadas pelo construtor
// Date como UTC meia-noite -- em fusos negativos (Brasil, UTC-3) isso exibe
// o dia anterior. Anexar "T00:00:00" força o parse como horário local.
function fmtDate(d){
  if(!d) return '—';
  const dt = /^\d{4}-\d{2}-\d{2}$/.test(d) ? new Date(d+'T00:00:00') : new Date(d);
  return dt.toLocaleDateString('pt-BR');
}
function fmtDateTime(d){
  if(!d) return '—';
  const dt = new Date(d);
  if(Number.isNaN(dt.getTime())) return String(d);
  return dt.toLocaleDateString('pt-BR') + ' ' + dt.toLocaleTimeString('pt-BR', {hour:'2-digit', minute:'2-digit'});
}
function fmtMoney(v){return'R$ '+Number(v).toFixed(2).replace('.',',').replace(/\B(?=(\d{3})+(?!\d))/g,'.')}
function fmtPercent(v){return Number(v).toFixed(2).replace(/\.?0+$/,'').replace('.',',')+'%'}
function daysUntil(d){if(!d)return 9999;return Math.ceil((new Date(d)-new Date())/(1000*86400))}
function addDays(d,n){const dt=new Date(d);dt.setDate(dt.getDate()+n);return dt.toISOString().split('T')[0]}

// Converte a string livre de "Validade" cadastrada em Preços (ex.: "1 ano",
// "3 anos", "6 meses") em número de dias. Retorna null se não reconhecer o
// formato -- o chamador decide o fallback (ex.: 365 dias).
function parseValidadeToDays(validade){
  if(!validade) return null;
  const match = String(validade).trim().toLowerCase().match(/(\d+)\s*(ano|anos|mes|mês|meses)/);
  if(!match) return null;
  const qty = parseInt(match[1], 10);
  if(Number.isNaN(qty)) return null;
  return match[2].startsWith('ano') ? qty * 365 : qty * 30;
}

// Máscaras "ingênuas" (reescrevem o value inteiro a cada tecla): aceitável
// para digitação sequencial do início; ao editar no meio já digitado o
// cursor pode pular pro fim, trade-off assumido pela simplicidade.
function maskCpfCnpj(value){
  const digits = String(value||'').replace(/\D/g,'').slice(0,14);
  if(digits.length <= 11){
    return digits.replace(/(\d{3})(\d)/,'$1.$2').replace(/(\d{3})(\d)/,'$1.$2').replace(/(\d{3})(\d{1,2})$/,'$1-$2');
  }
  return digits.replace(/(\d{2})(\d)/,'$1.$2').replace(/(\d{3})(\d)/,'$1.$2').replace(/(\d{3})(\d)/,'$1/$2').replace(/(\d{4})(\d{1,2})$/,'$1-$2');
}
function maskTelefone(value){
  const digits = String(value||'').replace(/\D/g,'').slice(0,11);
  if(digits.length <= 10){
    return digits.replace(/(\d{2})(\d)/,'($1) $2').replace(/(\d{4})(\d{1,4})$/,'$1-$2');
  }
  return digits.replace(/(\d{2})(\d)/,'($1) $2').replace(/(\d{5})(\d{1,4})$/,'$1-$2');
}

function normalizeAlertItem(item, categoria){
  if(!item || typeof item !== 'object') return null;
  const dias = Number(item.dias ?? item.days ?? 9999);
  const dataVencimento = item.dataVencimento || item.data_vencimento || '';
  const nome = item.nome || item.cliente || 'Sem nome';
  const tipoCert = item.tipoCert || item.tipo_certificado || '';
  const tipoPagamento = item.tipoPagamento || item.tipo_pagamento || '';
  const statusLabel = item.statusLabel || (dias < 0 ? `Vencido há ${Math.abs(dias)} dias` : `Vence em ${dias} dias`);
  return {
    ...item,
    id: item.id || `alert-${uid()}`,
    categoria: item.categoria || categoria,
    nome,
    dataVencimento,
    tipoCert,
    tipoPagamento,
    dias,
    statusLabel,
  };
}

function normalizeAlertGroup(group, categoria){
  const source = group && typeof group === 'object' ? group : {};
  return {
    urgentes: Array.isArray(source.urgentes) ? source.urgentes.map(item=>normalizeAlertItem(item, categoria)).filter(Boolean) : [],
    normais: Array.isArray(source.normais) ? source.normais.map(item=>normalizeAlertItem(item, categoria)).filter(Boolean) : [],
  };
}

function normalizeAlertData(data){
  const source = data && typeof data === 'object' ? data : {};
  const counts = source.counts && typeof source.counts === 'object' ? source.counts : {};
  const renovacoes = normalizeAlertGroup(source.renovacoes, 'renovacao');
  const pagamentos = normalizeAlertGroup(source.pagamentos, 'pagamento');
  return {
    counts:{
      total_registros:Number(counts.total_registros || 0),
      emitidos:Number(counts.emitidos || 0),
      vencendo_60_dias:Number(counts.vencendo_60_dias || 0),
      renovacoes_urgentes:Number(counts.renovacoes_urgentes || renovacoes.urgentes.length),
      renovacoes_normais:Number(counts.renovacoes_normais || renovacoes.normais.length),
      pagamentos_urgentes:Number(counts.pagamentos_urgentes || pagamentos.urgentes.length),
      pagamentos_normais:Number(counts.pagamentos_normais || pagamentos.normais.length),
      alertas_totais:Number(counts.alertas_totais || 0),
      faturamento_recebido:Number(counts.faturamento_recebido || 0),
    },
    renovacoes,
    pagamentos,
  };
}

function buildLocalAlertData(){
  const renovacoes={urgentes:[],normais:[]};
  const pagamentos={urgentes:[],normais:[]};
  const now = new Date();
  clientes.forEach(c=>{
    if(!c || !c.dataVencimento) return;
    const vencimento = new Date(c.dataVencimento);
    if(Number.isNaN(vencimento.getTime())) return;
    const dias = Math.ceil((vencimento - now)/(1000*86400));
    const base = {
      id: c.id,
      nome: c.nome || 'Sem nome',
      tipoCert: c.tipoCert || '',
      dataVencimento: c.dataVencimento,
      dias,
      statusLabel: dias < 0 ? `Vencido há ${Math.abs(dias)} dias` : `Vence em ${dias} dias`,
      telefone: c.telefone || '',
      email: c.email || '',
      valorCobrado: Number(c.valorCobrado || 0),
      pago: !!c.pago,
    };
    if(dias <= 30){
      renovacoes.urgentes.push({...base, categoria:'renovacao'});
    }else if(dias <= 90){
      renovacoes.normais.push({...base, categoria:'renovacao'});
    }
    if(!c.pago){
      const pagamentoBase = {...base, categoria:'pagamento', tipoPagamento:'Venda'};
      if(dias <= 0){
        pagamentos.urgentes.push(pagamentoBase);
      }else if(dias <= 30){
        pagamentos.normais.push(pagamentoBase);
      }
    }
  });
  const vencendo60 = [...renovacoes.urgentes, ...renovacoes.normais].filter(r=>r.dias<=60).length;
  const counts = {
    total_registros: clientes.length,
    emitidos: clientes.filter(c=>c.status==='Emitido').length,
    vencendo_60_dias: vencendo60,
    renovacoes_urgentes: renovacoes.urgentes.length,
    renovacoes_normais: renovacoes.normais.length,
    pagamentos_urgentes: pagamentos.urgentes.length,
    pagamentos_normais: pagamentos.normais.length,
    faturamento_recebido: clientes.filter(c=>c.pago).reduce((s,c)=>s+(parseFloat(c.valorCobrado)||0),0),
  };
  counts.alertas_totais = counts.renovacoes_urgentes + counts.renovacoes_normais + counts.pagamentos_urgentes + counts.pagamentos_normais;
  return {counts, renovacoes, pagamentos};
}

function getAlertData() {
  // 1. Obtém os dados de alerta vindos do backend ou gerados localmente
  let baseData = normalizeAlertData(backendAlertData || buildLocalAlertData());

  // 2. Filtro Inteligente para Pagamentos
  const filterPagamentos = (alertArray) => alertArray.filter(alerta => {
      const clienteLocal = clientes.find(c => String(c.id) === String(alerta.id));
      if (clienteLocal) {
          // Se o cliente foi marcado como pago localmente na interface, esconde o alerta
          return !clienteLocal.pago;
      }
      return true; // Se o cliente não constar localmente, mantém a informação original
  });

  // 3. Filtro Inteligente para Renovações (Vencimentos)
  const filterRenovacoes = (alertArray) => alertArray.filter(alerta => {
      const clienteLocal = clientes.find(c => String(c.id) === String(alerta.id));
      if (clienteLocal) {
          // Se o status local for alterado para "Emitido" (problema resolvido), esconde o alerta
          return clienteLocal.status !== 'Emitido';
      }
      return true;
  });

  // 4. Aplica a limpeza nas listas em tempo real
  baseData.pagamentos.urgentes = filterPagamentos(baseData.pagamentos.urgentes);
  baseData.pagamentos.normais = filterPagamentos(baseData.pagamentos.normais);

  baseData.renovacoes.urgentes = filterRenovacoes(baseData.renovacoes.urgentes);
  baseData.renovacoes.normais = filterRenovacoes(baseData.renovacoes.normais);

  // 5. Recalcula os números dos crachás (badges) no menu lateral
  baseData.counts.pagamentos_urgentes = baseData.pagamentos.urgentes.length;
  baseData.counts.pagamentos_normais = baseData.pagamentos.normais.length;
  baseData.counts.renovacoes_urgentes = baseData.renovacoes.urgentes.length;
  baseData.counts.renovacoes_normais = baseData.renovacoes.normais.length;

  baseData.counts.alertas_totais =
      baseData.counts.pagamentos_urgentes +
      baseData.counts.pagamentos_normais +
      baseData.counts.renovacoes_urgentes +
      baseData.counts.renovacoes_normais;

  return baseData;
}

function getCurrentViewId(){
  return document.querySelector('.view.active')?.id || '';
}

function renderAlertCard(item, kind){
  const isPayment = kind === 'pagamento';
  const iconClass = isPayment ? 'ti ti-receipt-2' : 'ti ti-certificate';
  const accentClass = item.dias < 0 ? 'red' : 'yellow';
  const actionLabel = isPayment ? 'Abrir Pagamento' : 'Registrar Contato';
  const actionFn = isPayment ? `openModal('pagamento','${item.id}')` : `openModal('contato','${item.id}')`;
  const detail = isPayment
    ? `${escapeHtml(item.statusLabel)} · ${item.tipoPagamento || 'Pagamento'}${item.tipoCert ? ` · ${escapeHtml(item.tipoCert)}` : ''}`
    : `${escapeHtml(item.statusLabel)} · ${escapeHtml(item.tipoCert)||'—'}${item.telefone ? ` · ${escapeHtml(item.telefone)}` : ''}`;
  return `<div class="alert-item ${accentClass}" style="cursor:pointer" onclick="navigateIfExists('${item.planilha_pk}', '/planilha/editar/${item.planilha_pk}/')">
    <div class="alert-icon ${accentClass}"><i class="${iconClass}"></i></div>
    <div class="alert-info">
      <div class="alert-name">${escapeHtml(item.nome)}</div>
      <div class="alert-detail">${detail}</div>
    </div>
    <button class="btn btn-sm btn-primary" onclick="event.stopPropagation();${actionFn}">${actionLabel}</button>
  </div>`;
}

async function syncBackendAlertCounts(){
  try{
    const response = await fetch('/alertas/', {cache:'no-store'});
    if(!response.ok) throw new Error('Falha ao obter alertas do backend');
    backendAlertData = normalizeAlertData(await response.json());
    updateBadges();
    const viewId = getCurrentViewId();
    if(viewId === 'view-dashboard') renderDashboard();
    if(viewId === 'view-renovacoes') renderRenovacoes();
    if(viewId === 'view-pagamentos') renderInadimplencia();
  }catch(err){
    console.warn('Não foi possível sincronizar alertas do backend', err);
  }
}

// Retorna o id real da linha na planilha (ex: "CLI-a1b2c3d4") a partir de um id
// de cliente, removendo o prefixo "planilha-" usado pelos cards de alerta
// (ex: "planilha-CLI-a1b2c3d4"). Ids da planilha nunca são numéricos -- são
// gerados por sheets_repository._new_id como "<PREFIXO>-<hex>".
function getPlanilhaPkFromClientId(clientId){
  if(clientId === null || clientId === undefined) return null;
  const raw = String(clientId).trim();
  if(!raw) return null;
  const stripped = raw.replace(/^planilha[-_]?/i, '');
  return /^CLI-/i.test(stripped) ? stripped : null;
}

function resolveClienteById(clientId){
  const raw = String(clientId || '').trim();
  if(!raw) return null;
  const simplified = raw.replace(/^planilha[-_]?/i, '');
  return clientes.find(c => String(c.id) === raw || String(c.id) === simplified) || null;
}

// Checa se o registro ainda existe na planilha antes de navegar para uma
// página full-page (edição, documentos) -- evita cair na tela de erro 404
// do Django quando o registro foi excluído por outra pessoa nesse meio-tempo.
async function navigateIfExists(pk, url){
  try{
    const resp = await fetch(`/planilha/${pk}/existe/`, {cache:'no-store'});
    const data = await resp.json().catch(()=>({existe:false}));
    if(!data.existe){
      showToast('Registro não encontrado. Pode ter sido excluído por outra pessoa.', 'error');
      return;
    }
    location.href = url;
  }catch(err){
    showToast('Não foi possível verificar o registro. Tente novamente.', 'error');
  }
}

function getCsrfToken(){
  const match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : '';
}

function switchTab(el,tabId){
  el.closest('.tabs').querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  el.classList.add('active');
  document.querySelectorAll('.tab-pane').forEach(p=>p.style.display='none');
  document.getElementById(tabId).style.display='';
}

// Helper central de fetch: injeta o header CSRF (exceto em GET), tenta
// parsear a resposta como JSON e lança um Error com a mensagem do backend
// quando response.ok é falso -- cada chamador só precisa decidir a UI de
// erro (toast, alert, etc.), sem repetir esse boilerplate em cada função.
async function apiFetch(url, {method='GET', body, headers={}, errorMessage='Falha na requisição'} = {}){
  const finalHeaders = {...headers};
  if(method !== 'GET'){
    finalHeaders['X-CSRFToken'] = getCsrfToken();
    finalHeaders['X-Requested-With'] = 'XMLHttpRequest';
  }
  const response = await fetch(url, {method, body, headers: finalHeaders});
  const data = await response.json().catch(()=>({}));
  if(!response.ok) throw new Error(data.error || errorMessage);
  return data;
}

// Modal de confirmação customizado (substitui window.confirm nativo, que
// aparece com estilo do navegador em vez do resto da UI do app).
let _confirmResolve = null;
function askConfirm(message, {title='Confirmar ação', confirmLabel='Confirmar', cancelLabel='Cancelar', danger=true} = {}){
  return new Promise((resolve) => {
    _confirmResolve = resolve;
    const box = document.getElementById('confirm-box');
    box.innerHTML = `
      <div class="modal-head"><h2>${escapeHtml(title)}</h2></div>
      <div class="modal-body"><p style="font-size:13px;color:var(--text)">${escapeHtml(message)}</p></div>
      <div class="modal-foot">
        <button class="btn" onclick="_resolveConfirm(false)">${escapeHtml(cancelLabel)}</button>
        <button class="btn ${danger?'btn-danger':'btn-primary'}" onclick="_resolveConfirm(true)">${escapeHtml(confirmLabel)}</button>
      </div>`;
    document.getElementById('confirm-overlay').classList.add('open');
  });
}
function _resolveConfirm(result){
  document.getElementById('confirm-overlay').classList.remove('open');
  if(_confirmResolve) _confirmResolve(result);
  _confirmResolve = null;
}
function _confirmBackdropClick(e){
  if(e.target === document.getElementById('confirm-overlay')) _resolveConfirm(false);
}

// CRUD genérico para excluir um registro simples (parceiro, preço, etc.):
// confirma com o usuário, chama a API e, em caso de sucesso, deixa o
// chamador atualizar o array local e re-renderizar via onSuccess.
async function crudDelete({url, confirmMsg, successMsg, errorMsg, onSuccess}){
  const ok = await askConfirm(confirmMsg, {title:'Remover registro', confirmLabel:'Remover', danger:true});
  if(!ok) return;
  try{
    await apiFetch(url, {method:'POST', errorMessage: errorMsg});
    if(onSuccess) onSuccess();
    showToast(successMsg, 'success');
  }catch(err){
    console.error(err);
    showToast(err.message || errorMsg, 'error');
  }
}

// CRUD genérico para criar/editar um registro simples (parceiro, preço) via
// formulário: monta o payload urlencoded, decide criar vs editar pelo id, e
// trata sucesso/erro de forma padronizada.
async function crudSave({editingId, createUrl, editUrlFn, payload, successMsg, errorMsg, onSuccess}){
  const url = editingId ? editUrlFn(editingId) : createUrl;
  try{
    await apiFetch(url, {
      method: 'POST',
      headers: {'Content-Type': 'application/x-www-form-urlencoded'},
      body: payload.toString(),
      errorMessage: errorMsg,
    });
    showToast(successMsg, 'success');
    if(onSuccess) onSuccess();
  }catch(err){
    console.error(err);
    showToast(err.message || errorMsg, 'error');
  }
}
