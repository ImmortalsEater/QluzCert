// ==================== STATE ====================
const DB = {
  get(k){try{return JSON.parse(localStorage.getItem('crt_'+k)||'null')}catch{return null}},
  set(k,v){localStorage.setItem('crt_'+k,JSON.stringify(v))},
};
const storedClientes = DB.get('clientes');
const storedParceiros = DB.get('parceiros');
let clientes = (Array.isArray(storedClientes) && storedClientes.length)
  ? storedClientes
  : ((typeof window !== 'undefined' && Array.isArray(window.INITIAL_CLIENTES) && window.INITIAL_CLIENTES.length>0)
      ? window.INITIAL_CLIENTES.slice()
      : []);
let parceiros = ((typeof window !== 'undefined' && Array.isArray(window.INITIAL_PARCEIROS) && window.INITIAL_PARCEIROS.length>0)
      ? window.INITIAL_PARCEIROS.slice()
      : (Array.isArray(storedParceiros) ? storedParceiros : []));
let precos = DB.get('precos')||[
  {id:1,tipo:'e-CPF A1',validade:'1 ano',preco:150},
  {id:2,tipo:'e-CPF A3',validade:'3 anos',preco:280},
  {id:3,tipo:'e-CNPJ A1',validade:'1 ano',preco:200},
  {id:4,tipo:'e-CNPJ A3',validade:'3 anos',preco:350},
  {id:5,tipo:'NF-e',validade:'1 ano',preco:120},
];
let editingId = null;
let backendAlertData = (typeof window !== 'undefined' && window.INITIAL_ALERTS) ? window.INITIAL_ALERTS : null;

const STATUS_LIST = ['Novo Lead','Documentação Pendente','Aguardando Pagamento','Agendado para Vídeo','Emitido'];
const STATUS_CLASSES = ['badge-novo','badge-doc','badge-pag','badge-video','badge-emitido'];
const STATUS_COLORS = ['info','warn','purple','teal','success'];
const KANBAN_COLORS = ['var(--info)','var(--warn)','var(--purple)','var(--teal)','var(--success)'];

function save(){DB.set('clientes',clientes);DB.set('parceiros',parceiros);DB.set('precos',precos);updateBadges()}

function saveLocalOnly(){DB.set('clientes',clientes);DB.set('parceiros',parceiros);DB.set('precos',precos);updateBadges();setStatus('Salvo localmente'); showToast('Salvo localmente','success')}

async function saveServerState(){
  saveLocalOnly();
  try {
    const response = await fetch('/app_state/', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({clientes, parceiros, precos})
    });
    if (!response.ok) throw new Error('Falha ao salvar no servidor');
    const data = await response.json();
    if (data.saved) { setStatus('Salvo no servidor'); showToast('Salvo no servidor','success'); }
    else { setStatus('Falha ao salvar no servidor'); showToast('Falha ao salvar no servidor','error'); }
  } catch (err) {
    console.error(err);
    setStatus('Erro ao salvar no servidor');
    showToast('Erro ao salvar no servidor','error');
  }
}

async function saveCloudState(){
  saveLocalOnly();
  try {
    const response = await fetch('/app_state_drive/', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({clientes, parceiros, precos})
    });
    if (!response.ok) throw new Error('Falha ao salvar na nuvem');
    const data = await response.json();
    if (data.saved && data.drive) { setStatus('Salvo na nuvem'); showToast('Salvo na nuvem','success'); }
    else if (data.saved) { setStatus('Salvo no servidor, falha na nuvem'); showToast('Salvo no servidor, falha na nuvem','info'); }
    else { setStatus('Falha ao salvar na nuvem'); showToast('Falha ao salvar na nuvem','error'); }
  } catch (err) {
    console.error(err);
    setStatus('Erro ao salvar na nuvem');
    showToast('Erro ao salvar na nuvem','error');
  }
}

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
  const btnCloud = document.getElementById('save-cloud-btn');
  if(!mainBtn || !menu) return;
  mainBtn.addEventListener('click', function(e){ e.stopPropagation(); menu.style.display = (menu.style.display==='block'?'none':'block'); });
  // fechar ao clicar fora
  document.addEventListener('click', function(){ if(menu) menu.style.display='none' });
  if(btnLocal) btnLocal.addEventListener('click', function(e){ e.stopPropagation(); menu.style.display='none'; saveLocalOnly(); });
  if(btnCloud) btnCloud.addEventListener('click', function(e){ e.stopPropagation(); menu.style.display='none'; saveCloudState(); });
  const btnExport = document.getElementById('export-btn');
  if(btnExport) btnExport.addEventListener('click', function(e){ e.stopPropagation(); menu.style.display='none'; exportState(); });
  // data source bindings
  const srcSelect = document.getElementById('data-source-select');
  const syncBtn = document.getElementById('sync-server-btn');
  if(srcSelect){ srcSelect.value = getDataSource(); srcSelect.addEventListener('change', function(){ setDataSource(this.value); }); }
  if(syncBtn){ syncBtn.addEventListener('click', function(){ syncBtn.disabled=true; fetchServerState(true).finally(()=>{ syncBtn.disabled=false; }); }); }
  renderDataSourceIndicator();
}

async function exportState(){
  // envia estado atual para o servidor e força download do arquivo gerado
  const payload = {clientes, parceiros, precos};
  try{
    const resp = await fetch('/app_state_download/', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify(payload)
    });
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
    a.download = 'estado_clientes_parceiros.xlsx';
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
function statusIndex(status){return STATUS_LIST.indexOf(status)>=0?STATUS_LIST.indexOf(status):0}
function statusBadge(status){const i=statusIndex(status); return `<span class="badge ${STATUS_CLASSES[i]}">${status||'Novo Lead'}</span>`}
function parceiroBadge(id){const p=parceiros.find(x=>x.id===id); return p?`<span class="parceiro-tag">${p.nome}</span>`:'—'}
function formatVencimento(c){const d=c.dataVencimento?daysUntil(c.dataVencimento):null; return d!==null&&d<=60?`<span class="badge ${d<0?'badge-vencido':'badge-vencendo'}">${d<0?'Vencido':d+' dias'}</span>`:(c.dataVencimento?`<span style="font-size:12px;color:var(--muted)">${fmtDate(c.dataVencimento)}</span>`:'—')}
function tableRows(rows){return rows.join('')}
function uid(){return Date.now()+Math.random().toString(36).slice(2)}
function fmtDate(d){if(!d)return'—';const dt=new Date(d);return dt.toLocaleDateString('pt-BR')}
function fmtMoney(v){return'R$ '+Number(v).toFixed(2).replace('.',',').replace(/\B(?=(\d{3})+(?!\d))/g,'.')}
function fmtPercent(v){return Number(v).toFixed(2).replace(/\.?0+$/,'').replace('.',',')+'%'}
function daysUntil(d){if(!d)return 9999;return Math.ceil((new Date(d)-new Date())/(1000*86400))}
function addDays(d,n){const dt=new Date(d);dt.setDate(dt.getDate()+n);return dt.toISOString().split('T')[0]}

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
      renovacoes_urgentes:Number(counts.renovacoes_urgentes || renovacoes.urgentes.length),
      renovacoes_normais:Number(counts.renovacoes_normais || renovacoes.normais.length),
      pagamentos_urgentes:Number(counts.pagamentos_urgentes || pagamentos.urgentes.length),
      pagamentos_normais:Number(counts.pagamentos_normais || pagamentos.normais.length),
      alertas_totais:Number(counts.alertas_totais || 0),
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
  const counts = {
    total_registros: clientes.length,
    renovacoes_urgentes: renovacoes.urgentes.length,
    renovacoes_normais: renovacoes.normais.length,
    pagamentos_urgentes: pagamentos.urgentes.length,
    pagamentos_normais: pagamentos.normais.length,
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
    ? `${item.statusLabel} · ${item.tipoPagamento || 'Pagamento'}${item.tipoCert ? ` · ${item.tipoCert}` : ''}`
    : `${item.statusLabel} · ${item.tipoCert || '—'}${item.telefone ? ` · ${item.telefone}` : ''}`;
  return `<div class="alert-item ${accentClass}" style="cursor:pointer" onclick="openDetail('${item.id}')">
    <div class="alert-icon ${accentClass}"><i class="${iconClass}"></i></div>
    <div class="alert-info">
      <div class="alert-name">${item.nome}</div>
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

const PAGE_CONFIG = {
  dashboard:{title:'Dashboard', render:renderDashboard},
  clientes:{title:'Clientes', render:renderClientes},
  funil:{title:'Funil de Atendimento', render:renderKanban},
  renovacoes:{title:'Alertas de Renovação', render:renderRenovacoes},
  pagamentos:{title:'Alertas de Pagamento', render:renderInadimplencia},
  parceiros:{title:'Parceiros Comerciais', render:renderParceiros},
  tabela:{title:'Tabela de Preços', render:renderTabela},
}

// ==================== NAVIGATION ====================
function nav(page){
  document.querySelectorAll('.nav-item').forEach(el=>{
    el.classList.toggle('active', el.getAttribute('onclick')===`nav('${page}')`);
  });
  document.querySelectorAll('.view').forEach(v=>v.classList.remove('active'));
  document.getElementById('view-'+page).classList.add('active');
  const config=PAGE_CONFIG[page]||{title:page,render:()=>{}};
  document.getElementById('page-title').textContent=config.title;
  renderTo('topbar-actions','');
  config.render();
  // renderiza os controles de salvar novamente e re-bind dos eventos
  try{ renderSaveActions(); initSaveMenu(); }catch(e){}
}

function renderSaveActions(){
  const html = `
    <div style="display:flex;align-items:center;gap:10px">
      <div style="display:flex;align-items:center;gap:8px">
        <label style="font-size:12px;color:var(--muted)">Fonte:</label>
        <select id="data-source-select" style="padding:6px;border-radius:6px;border:1px solid var(--border);background:var(--surface)">
          <option value="server">Servidor</option>
          <option value="local">Local</option>
        </select>
        <button class="btn" id="sync-server-btn" style="padding:6px 10px">Sincronizar</button>
        <span id="data-source-indicator" style="font-size:12px;color:var(--muted)"></span>
      </div>
      <div class="save-dropdown" style="position:relative;display:inline-block">
        <button class="btn btn-sm" id="save-main-btn"><i class="ti ti-device-floppy"></i> Salvar <i class="ti ti-chevron-down" style="margin-left:6px;font-size:12px"></i></button>
        <div id="save-menu" style="position:absolute;right:0;top:36px;background:var(--surface);border:1px solid var(--border);border-radius:6px;box-shadow:0 6px 18px rgba(0,0,0,0.06);display:none;min-width:180px;padding:8px;z-index:60">
          <button class="btn" style="display:block;width:100%;text-align:left;padding:8px;border-radius:6px" id="save-local-btn">Salvar localmente</button>
          <button class="btn" style="display:block;width:100%;text-align:left;padding:8px;border-radius:6px;margin-top:6px" id="save-cloud-btn">Salvar na nuvem</button>
          <button class="btn" style="display:block;width:100%;text-align:left;padding:8px;border-radius:6px;margin-top:6px" id="export-btn">Exportar (.xlsx)</button>
        </div>
      </div>
    </div>
    <span id="save-status" style="margin-left:12px;font-size:13px;color:var(--muted)"></span>
  `;
  const ta = document.getElementById('topbar-actions');
  if(ta) ta.innerHTML = html;
}

function getDataSource(){
  const cached = DB.get('data_source');
  if(cached) return cached;
  if(typeof window !== 'undefined' && Array.isArray(window.INITIAL_CLIENTES) && window.INITIAL_CLIENTES.length>0) return 'server';
  return 'local';
}

function setDataSource(src){
  DB.set('data_source', src);
  renderDataSourceIndicator();
  if(src==='server') fetchServerState(true);
}

function renderDataSourceIndicator(){
  const el = document.getElementById('data-source-indicator');
  if(!el) return;
  const src = getDataSource();
  el.textContent = src==='server' ? 'Usando: servidor' : 'Usando: local';
}

async function fetchServerState(apply){
  try{
    const r = await fetch('/app_state/');
    if(!r.ok) throw new Error('Falha ao obter estado do servidor');
    const data = await r.json();
    if(apply){
      if (Array.isArray(data.clientes) && data.clientes.length) {
        clientes = data.clientes;
      }
      if (Array.isArray(data.parceiros) && data.parceiros.length) {
        parceiros = data.parceiros;
      }
      if (Array.isArray(data.precos) && data.precos.length) {
        precos = data.precos;
      }
      save();
      renderClientes(); renderParceiros(); renderTabela(); renderDashboard();
      syncBackendAlertCounts();
      showToast('Estado do servidor aplicado','success');
    }
    return data;
  }catch(e){ showToast('Erro ao obter estado do servidor','error'); console.error(e); return null }
}

function updateBadges(){
  const alertData = getAlertData();
  const counts = alertData.counts || {};
  const totalAlerts = Number(counts.alertas_totais || 0);
  const renovacoesTotal = Number(counts.renovacoes_urgentes || 0) + Number(counts.renovacoes_normais || 0);
  const pagamentosTotal = Number(counts.pagamentos_urgentes || 0) + Number(counts.pagamentos_normais || 0);
  const b=document.getElementById('alert-badge');
  if(b){b.style.display=totalAlerts?'':'none';b.textContent=totalAlerts}
  const rb=document.getElementById('ren-badge');
  if(rb){rb.style.display=renovacoesTotal?'':'none';rb.textContent=renovacoesTotal}
  const pb=document.getElementById('pag-badge');
  if(pb){pb.style.display=pagamentosTotal?'':'none';pb.textContent=pagamentosTotal}
  const totalCount=document.getElementById('total-count');
  if(totalCount) totalCount.textContent=Number(counts.total_registros || clientes.length);
}

// ==================== DASHBOARD ====================
function renderDashboard(){
  const total=clientes.length;
  const emitidos=clientes.filter(c=>c.status==='Emitido').length;
  const leads=clientes.filter(c=>c.status==='Novo Lead').length;
  const vencendo=clientes.filter(c=>c.dataVencimento&&daysUntil(c.dataVencimento)<=60).length;
 // Lê o valor processado pelo Django na tabela. Se não existir, faz a soma local.
  const faturamento = (typeof window !== 'undefined' && window.INITIAL_FATURAMENTO !== undefined)
    ? Number(window.INITIAL_FATURAMENTO)
    : clientes.filter(c=>c.pago).reduce((s,c)=>s+(parseFloat(c.valorCobrado)||0),0);

  document.getElementById('dashboard-metrics').innerHTML=`
    <div class="metric-card accent"><div class="metric-label">Total de Clientes</div><div class="metric-val">${total}</div><div class="metric-sub">${leads} novos leads</div></div>
    <div class="metric-card success"><div class="metric-label">Emitidos</div><div class="metric-val">${emitidos}</div><div class="metric-sub">${Math.round(total?emitidos/total*100:0)}% do total</div></div>
    <div class="metric-card warn"><div class="metric-label">Renovações ≤60 dias</div><div class="metric-val">${vencendo}</div><div class="metric-sub">requerem contato</div></div>
    <div class="metric-card"><div class="metric-label">Faturamento Recebido</div><div class="metric-val" style="font-size:18px">${fmtMoney(faturamento)}</div><div class="metric-sub">pagamentos confirmados</div></div>
  `;
  const alertData = getAlertData();
  const urgentes=[...alertData.renovacoes.urgentes,...alertData.pagamentos.urgentes,...alertData.renovacoes.normais,...alertData.pagamentos.normais]
    .sort((a,b)=>(a.dias??9999)-(b.dias??9999))
    .slice(0,5);
  const al=document.getElementById('dashboard-alerts');
  if(!urgentes.length){al.innerHTML='<p style="font-size:13px;color:var(--muted);text-align:center;padding:20px">Nenhum alerta no momento ✓</p>';}
  else { al.innerHTML=urgentes.map(c=>{
    const kind = c.categoria === 'pagamento' ? 'pagamento' : 'renovacao';
    return renderAlertCard(c, kind);
  }).join(''); }
  const recent=clientes.slice().sort((a,b)=>new Date(b.criadoEm||0)-new Date(a.criadoEm||0)).slice(0,6);
  document.getElementById('dashboard-recent').innerHTML=`<table style="width:100%;border-collapse:collapse">${recent.map(c=>`
    <tr onclick="openDetail('${c.id}')" style="cursor:pointer;border-bottom:1px solid var(--border)">
      <td style="padding:10px 16px;font-size:13px">${c.nome}</td>
      <td style="padding:10px 16px"><span class="badge ${STATUS_CLASSES[STATUS_LIST.indexOf(c.status)]||'badge-novo'}">${c.status||'Novo Lead'}</span></td>
      <td style="padding:10px 16px;color:var(--muted);font-size:12px">${fmtDate(c.criadoEm)}</td>
    </tr>`).join('')}</table>`;
  const notificados=clientes.filter(c=>Array.isArray(c.notificacoes)&&c.notificacoes.length).sort((a,b)=>(b.notificacoes?.length||0)-(a.notificacoes?.length||0)).slice(0,6);
  const panel=document.getElementById('dashboard-notificados');
  if(panel){
    panel.innerHTML = notificados.length ? `<table style="width:100%;border-collapse:collapse">${notificados.map(c=>`
      <tr onclick="openDetail('${c.id}')" style="cursor:pointer;border-bottom:1px solid var(--border)">
        <td style="padding:10px 16px;font-size:13px"><strong>${c.nome}</strong></td>
        <td style="padding:10px 16px;color:var(--muted);font-size:12px">${(c.notificacoes||[]).length} aviso(s)</td>
        <td style="padding:10px 16px;color:var(--muted);font-size:12px">${fmtDate((c.notificacoes||[])[0]?.data||c.criadoEm)}</td>
      </tr>`).join('')}</table>` : '<p style="font-size:13px;color:var(--muted);text-align:center;padding:20px">Nenhum cliente notificado ainda.</p>';
  }
}

// ==================== CLIENTES ====================
function renderClientes(){
  const q=normalizeQuery(document.getElementById('search-cliente')?.value);
  const sf=document.getElementById('filter-status')?.value||'';
  let list=clientes.filter(c=>{
    const match=!q||[c.nome,c.cpfCnpj,c.email,c.telefone].some(v=>(v||'').toLowerCase().includes(q));
    const sm=!sf||c.status===sf;
    return match&&sm;
  });
  const tbody=document.getElementById('clientes-tbody');
  const empty=document.getElementById('clientes-empty');
  updateResultCount('clientes-count', list.length, clientes.length);
  if(!list.length){tbody.innerHTML='';empty.style.display='';return}
  empty.style.display='none';
  const rows=list.map(c=>{
    const vBadge=formatVencimento(c);
    return`<tr>
      <td><strong style="cursor:pointer;color:var(--accent)" onclick="openDetail('${c.id}')">${c.nome}</strong></td>
      <td style="font-family:monospace;font-size:12px">${c.cpfCnpj||'—'}</td>
      <td><span class="tipo-cert">${c.tipoCert||'—'}</span></td>
      <td>${statusBadge(c.status)}</td>
      <td>${parceiroBadge(c.parceiroId)}</td>
      <td>${vBadge}</td>
      <td><button class="btn btn-sm" onclick="openDetail('${c.id}')"><i class="ti ti-eye"></i></button> <button class="btn btn-sm" onclick="editCliente('${c.id}')"><i class="ti ti-edit"></i></button> <button class="btn btn-sm" onclick="deleteCliente('${c.id}')" style="color:var(--danger)"><i class="ti ti-trash"></i></button></td>
    </tr>`;
  });
  tbody.innerHTML=tableRows(rows);
}

// Colunas de identificação da tabela "Planilha Importada" são localizadas pelo texto do
// cabeçalho (não pela classe CSS): a classe de cada coluna é derivada do cabeçalho real da
// planilha em tempo de sincronização (ver normalize_header em core/app/services.py) e pode
// variar a cada sync (ex: "CPF/CNPJ" vira col-cpfcnpj, não col-cpf-cnpj).
const PLANILHA_SEARCH_KEYWORDS = ['cliente','nome','cpf','cnpj','email','e-mail','telefone','celular','whatsapp'];
let _planilhaSearchColIndexes = null;
function getPlanilhaSearchColIndexes(){
  if(_planilhaSearchColIndexes) return _planilhaSearchColIndexes;
  const ths = Array.from(document.querySelectorAll('#planilha-table thead th'));
  _planilhaSearchColIndexes = ths.reduce((acc, th, i)=>{
    const text = th.textContent.toLowerCase();
    if(PLANILHA_SEARCH_KEYWORDS.some(k=>text.includes(k))) acc.push(i);
    return acc;
  }, []);
  return _planilhaSearchColIndexes;
}

function filterPlanilhaImportada(){
  const q=normalizeQuery(document.getElementById('search-cliente')?.value);
  const tbody=document.getElementById('planilha-tbody');
  const table=document.getElementById('planilha-table');
  const noMatch=document.getElementById('planilha-no-match');
  const msg=document.getElementById('planilha-empty-msg');
  if(!tbody||!table) return;
  const dataRows=Array.from(tbody.querySelectorAll('tr'));

  if(!dataRows.length){
    table.style.display='none';
    if(noMatch){ noMatch.style.display=''; }
    if(msg) msg.textContent='Nenhuma planilha importada ainda. Use "Sincronizar com o Google Drive".';
    updateResultCount('planilha-count', 0, 0);
    return;
  }

  const cols=getPlanilhaSearchColIndexes();
  let visibleCount=0;
  dataRows.forEach(row=>{
    const cells=row.querySelectorAll('td');
    const text=cols.map(i=>cells[i]?.textContent||'').join(' ').toLowerCase();
    const match=!q||text.includes(q);
    row.style.display=match?'':'none';
    if(match) visibleCount++;
  });
  updateResultCount('planilha-count', visibleCount, dataRows.length);
  table.style.display='';
  if(noMatch){
    if(q&&!visibleCount){
      noMatch.style.display='';
      if(msg) msg.textContent='Nenhum cliente encontrado para essa busca.';
    } else {
      noMatch.style.display='none';
    }
  }
}

function editCliente(id){editingId=id;openModal('cliente')}
function deleteCliente(id){if(confirm('Remover este cliente?')){clientes=clientes.filter(c=>c.id!==id);save();renderClientes();renderDashboard()}}

// ==================== KANBAN ====================
function renderKanban(){
  const board=document.getElementById('kanban-board');
  board.innerHTML=STATUS_LIST.map((s,i)=>{
    const cards=clientes.filter(c=>c.status===s);
    return`<div class="kanban-col">
      <div class="kanban-col-head" style="color:${KANBAN_COLORS[i]}">${s} <span style="background:${KANBAN_COLORS[i]}22;color:${KANBAN_COLORS[i]};padding:1px 7px;border-radius:10px;font-size:11px">${cards.length}</span></div>
      ${cards.map(c=>`<div class="kanban-card" onclick="openDetail('${c.id}')">
        <div class="kanban-card-name">${c.nome}</div>
        <div class="kanban-card-sub">${c.tipoCert||'Tipo não definido'}</div>
        <div class="kanban-card-footer">
          <span style="font-size:11px;color:var(--muted)">${fmtDate(c.criadoEm)}</span>
          ${!c.pago&&c.dataVencimento&&daysUntil(c.dataVencimento)<=30?`<span class="parceiro-tag" style="font-size:10px;background:${daysUntil(c.dataVencimento)<0?'var(--danger)':'var(--warn)'}22;color:${daysUntil(c.dataVencimento)<0?'var(--danger)':'var(--warn)'}">${daysUntil(c.dataVencimento)<0?`Pagamento vencido há ${Math.abs(daysUntil(c.dataVencimento))} dias`:'Pagamento pendente'}</span>`:''}
          ${c.parceiroId?`<span class="parceiro-tag" style="font-size:10px">${(parceiros.find(p=>p.id===c.parceiroId)||{}).nome||''}</span>`:''}
        </div>
      </div>`).join('')}
    </div>`;
  }).join('');
}

// ==================== RENOVAÇÕES ====================
function renderRenovacoes(){
  const alertData = getAlertData();
  const urgentes=alertData.renovacoes.urgentes.sort((a,b)=>(a.dias??9999)-(b.dias??9999));
  const normais=alertData.renovacoes.normais.sort((a,b)=>(a.dias??9999)-(b.dias??9999));
  document.getElementById('ren-urgente').innerHTML=urgentes.length?urgentes.map(c=>renderAlertCard(c,'renovacao')).join(''):'<p style="font-size:13px;color:var(--muted)">Nenhum vencimento urgente ✓</p>';
  document.getElementById('ren-normal').innerHTML=normais.length?normais.map(c=>renderAlertCard(c,'renovacao')).join(''):'<p style="font-size:13px;color:var(--muted)">Nenhum no período ✓</p>';
}

function renderInadimplencia(){
  const alertData = getAlertData();
  const urgentes=alertData.pagamentos.urgentes.sort((a,b)=>(a.dias??9999)-(b.dias??9999));
  const normais=alertData.pagamentos.normais.sort((a,b)=>(a.dias??9999)-(b.dias??9999));
  document.getElementById('pag-urgente').innerHTML=urgentes.length?urgentes.map(c=>renderAlertCard(c,'pagamento')).join(''):'<p style="font-size:13px;color:var(--muted)">Nenhum pagamento vencido ✓</p>';
  document.getElementById('pag-normal').innerHTML=normais.length?normais.map(c=>renderAlertCard(c,'pagamento')).join(''):'<p style="font-size:13px;color:var(--muted)">Nenhum pagamento a vencer ✓</p>';
}

function getPlanilhaPkFromClientId(clientId){
  if(clientId === null || clientId === undefined || clientId === '') return null;
  const raw = String(clientId).trim();
  if(!raw) return null;
  const match = raw.match(/^(?:planilha[-_]?|)(\d+)$/i);
  if(match) return parseInt(match[1], 10);
  if(raw.startsWith('planilha-')){
    const fallback = raw.split('-', 2)[1];
    const pk = parseInt(fallback, 10);
    return Number.isFinite(pk) ? pk : null;
  }
  return null;
}

function resolveClienteById(clientId){
  const raw = String(clientId || '').trim();
  if(!raw) return null;
  const direct = clientes.find(c => String(c.id) === raw || String(c.id) === raw.replace(/^planilha[-_]?/i, ''));
  if(direct) return direct;
  const planilhaPk = getPlanilhaPkFromClientId(raw);
  if(planilhaPk !== null){
    const byPlanilha = clientes.find(c => Number(getPlanilhaPkFromClientId(c.id)) === planilhaPk || Number(c.planilhaPk) === planilhaPk || Number(c.planilha_id) === planilhaPk || Number(c.planilhaId) === planilhaPk);
    if(byPlanilha) return byPlanilha;
  }
  const simplified = raw.replace(/^planilha[-_]?/i, '');
  if(simplified !== raw){
    const bySimplified = clientes.find(c => String(c.id) === simplified || String(c.planilhaPk) === simplified || String(c.planilha_id) === simplified || String(c.planilhaId) === simplified);
    if(bySimplified) return bySimplified;
  }
  return null;
}

function openDocumentosCliente(clientId){
  const pk = getPlanilhaPkFromClientId(clientId);
  if(!pk){
    showToast('Documentos disponíveis apenas para clientes sincronizados da planilha','info');
    return;
  }
  openModal('cliente', clientId);
  setTimeout(()=>switchTabById('tab-documentos'), 0);
}

function switchTabById(tabId){
  const tab = document.querySelector(`.tab[onclick*="'${tabId}'"]`);
  if(tab){
    switchTab(tab, tabId);
  }
}

function getCsrfToken(){
  const match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : '';
}

function bytesToHuman(bytes){
  const value = Number(bytes || 0);
  if(!Number.isFinite(value) || value <= 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  let current = value;
  let unitIndex = 0;
  while(current >= 1024 && unitIndex < units.length - 1){
    current /= 1024;
    unitIndex += 1;
  }
  return `${current.toFixed(current >= 10 || unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
}

async function loadDocumentosCliente(clientId){
  const pk = getPlanilhaPkFromClientId(clientId);
  const container = document.getElementById('documentos-list');
  const meta = document.getElementById('documentos-meta');
  const uploadForm = document.getElementById('documentos-form');
  if(!pk || !container) return;
  container.innerHTML = '<p style="font-size:13px;color:var(--muted)">Carregando documentos...</p>';
  if(meta) meta.textContent = 'Carregando...';
  try{
    const response = await fetch(`/planilha/${pk}/documentos/?format=json`);
    if(!response.ok) throw new Error('Falha ao carregar documentos');
    const data = await response.json();
    const docs = Array.isArray(data.documentos) ? data.documentos : [];
    if(meta){
      const cliente = data.registro?.cliente || 'cliente';
      meta.textContent = `Documentos de ${cliente} · ${docs.length} item(ns)`;
    }
    if(!docs.length){
      container.innerHTML = '<p style="font-size:13px;color:var(--muted)">Nenhum documento enviado para este cliente ainda.</p>';
      return;
    }
    container.innerHTML = docs.map(doc => `
      <div class="document-card" style="display:flex;justify-content:space-between;gap:12px;align-items:center;padding:10px 12px;border:1px solid var(--border);border-radius:10px;background:var(--surface);margin-bottom:8px">
        <div style="min-width:0">
          <div style="font-weight:700;font-size:13px;word-break:break-word">${doc.nome_original}</div>
          <div style="font-size:12px;color:var(--muted);margin-top:2px">${doc.tipo_documento_display} · ${fmtDate(doc.data_envio)} · ${bytesToHuman(doc.tamanho_bytes)}</div>
        </div>
        <div style="display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end">
          <a class="btn btn-sm" href="${doc.download_url}" target="_blank" rel="noopener"><i class="ti ti-download"></i> Baixar</a>
          <button class="btn btn-sm" onclick="deleteDocumentoCliente('${clientId}', ${doc.id})" style="color:var(--danger)"><i class="ti ti-trash"></i></button>
        </div>
      </div>
    `).join('');
  }catch(err){
    console.error(err);
    if(meta) meta.textContent = 'Erro ao carregar documentos';
    container.innerHTML = '<p style="font-size:13px;color:var(--danger)">Não foi possível carregar os documentos.</p>';
  }
}

async function uploadDocumentoCliente(event, clientId){
  event.preventDefault();
  const pk = getPlanilhaPkFromClientId(clientId);
  if(!pk){
    showToast('Cliente sincronizado da planilha é necessário para upload de documentos','error');
    return false;
  }
  const form = event.target;
  const formData = new FormData(form);
  const file = formData.get('arquivo');
  if(!file || !file.name){
    showToast('Selecione um arquivo antes de enviar','error');
    return false;
  }
  try{
    const response = await fetch(`/planilha/${pk}/documentos/`, {
      method: 'POST',
      headers: {'X-CSRFToken': getCsrfToken()},
      body: formData,
    });
    if(!response.ok){
      const text = await response.text();
      throw new Error(text || 'Falha ao enviar documento');
    }
    form.reset();
    showToast('Documento enviado com sucesso','success');
    await loadDocumentosCliente(clientId);
  }catch(err){
    console.error(err);
    showToast('Erro ao enviar documento','error');
  }
  return false;
}

async function deleteDocumentoCliente(clientId, docId){
  if(!confirm('Remover este documento?')) return;
  try{
    const response = await fetch(`/documentos/${docId}/excluir/`, {
      method: 'POST',
      headers: {'X-CSRFToken': getCsrfToken()},
    });
    if(!response.ok) throw new Error('Falha ao excluir documento');
    showToast('Documento removido','success');
    await loadDocumentosCliente(clientId);
  }catch(err){
    console.error(err);
    showToast('Erro ao remover documento','error');
  }
}

// ==================== PARCEIROS ====================
function renderParceiros(){
  const tbody=document.getElementById('parceiros-tbody');
  const empty=document.getElementById('parceiros-empty');
  if(!parceiros.length){tbody.innerHTML='';empty.style.display='';return}
  empty.style.display='none';
  tbody.innerHTML=parceiros.map(p=>{
    const count=clientes.filter(c=>c.parceiroId===p.id).length;
    return`<tr><td><strong>${p.nome}</strong></td><td>${p.tipo||'—'}</td><td>${p.comissao!=null?fmtPercent(p.comissao):'—'}</td><td>${p.contato||'—'}</td><td><span style="font-size:13px;font-weight:700;color:var(--accent)">${count}</span></td>
    <td><button class="btn btn-sm" onclick="editParceiro('${p.id}')"><i class="ti ti-edit"></i></button> <button class="btn btn-sm" onclick="deleteParceiro('${p.id}')" style="color:var(--danger)"><i class="ti ti-trash"></i></button></td></tr>`;
  }).join('');
}
function editParceiro(id){editingId=id;openModal('parceiro')}
function deleteParceiro(id){if(confirm('Remover parceiro?')){parceiros=parceiros.filter(p=>p.id!==id);save();renderParceiros()}}

// ==================== TABELA PREÇOS ====================
function renderTabela(){
  document.getElementById('tabela-tbody').innerHTML=precos.map(p=>`<tr>
    <td><strong>${p.tipo}</strong></td><td>${p.validade}</td><td style="font-weight:700;color:var(--success)">${fmtMoney(p.preco)}</td>
    <td><button class="btn btn-sm" onclick="editPreco('${p.id}')"><i class="ti ti-edit"></i></button> <button class="btn btn-sm" onclick="deletePreco('${p.id}')" style="color:var(--danger)"><i class="ti ti-trash"></i></button></td>
  </tr>`).join('');
}
function editPreco(id){editingId=id;openModal('preco')}
function deletePreco(id){if(confirm('Remover?')){precos=precos.filter(p=>p.id!==id);save();renderTabela()}}

// ==================== MODAIS ====================
let modalTriggerEl=null;
function openModal(type, extraId, triggerEl){
  const matched = resolveClienteById(extraId || editingId);
  editingId = matched ? matched.id : (extraId || editingId || null);
  modalTriggerEl=triggerEl||document.activeElement;
  const overlay=document.getElementById('modal-overlay');
  const box=document.getElementById('modal-box');
  overlay.classList.add('open');
  if(type==='cliente')renderClienteModal(box);
  if(type==='novoCliente')renderNovoClienteModal(box);
  if(type==='parceiro')renderParceiroModal(box);
  if(type==='preco')renderPrecoModal(box);
  if(type==='contato')renderContatoModal(box,extraId||editingId);
  if(type==='pagamento')renderPagamentoModal(box,extraId||editingId);
  const firstField=box.querySelector('input,select,textarea')||box.querySelector('button');
  if(firstField)firstField.focus();
}
function closeModal(e){
  if(e.target===document.getElementById('modal-overlay')||e===true){
    document.getElementById('modal-overlay').classList.remove('open');
    editingId=null;
    if(modalTriggerEl&&typeof modalTriggerEl.focus==='function')modalTriggerEl.focus();
    modalTriggerEl=null;
  }
}
function handleModalKeydown(e){
  const overlay=document.getElementById('modal-overlay');
  if(!overlay||!overlay.classList.contains('open'))return;
  if(e.key==='Escape'){closeModal(true);return}
  if(e.key==='Tab'){
    const box=document.getElementById('modal-box');
    const focusables=Array.prototype.slice.call(box.querySelectorAll('input,select,textarea,button,a[href]')).filter(function(el){return !el.disabled&&el.offsetParent!==null});
    if(!focusables.length)return;
    const first=focusables[0],last=focusables[focusables.length-1];
    if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus()}
    else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus()}
  }
}
document.addEventListener('keydown',handleModalKeydown);

function renderClienteModal(box){
  const c=resolveClienteById(editingId) || {};
  const pOpts=parceiros.map(p=>`<option value="${p.id}"${c.parceiroId===p.id?' selected':''}>${p.nome}</option>`).join('');
  const tOpts=precos.map(p=>`<option value="${p.tipo}"${c.tipoCert===p.tipo?' selected':''}>${p.tipo} — ${fmtMoney(p.preco)}</option>`).join('');
  const hasPlanilhaId = !!String(c.id || editingId || '').startsWith('planilha-');
  box.innerHTML=`
  <div class="modal-head">
    <div>
      <h2 id="modal-dialog-title">${editingId?'Editar Cliente':'Novo Cliente'}</h2>
      <div style="font-size:12px;color:var(--muted);margin-top:3px">Cadastro, triagem, documentos e pagamento no mesmo fluxo</div>
    </div>
    <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
      ${hasPlanilhaId?`<button class="btn btn-sm" onclick="openDocumentosCliente('${c.id || editingId}')"><i class="ti ti-folder"></i> Documentos</button>`:''}
      ${editingId?`<button class="btn btn-sm" onclick="openModal('pagamento','${c.id || editingId}')"><i class="ti ti-qrcode"></i> Pagamento</button>`:''}
      <button class="btn btn-sm" onclick="closeModal(true)" aria-label="Fechar"><i class="ti ti-x" aria-hidden="true"></i></button>
    </div>
  </div>
  <div class="modal-body">
    <div class="tabs">
      <div class="tab active" onclick="switchTab(this,'tab-dados')">Dados Pessoais</div>
      <div class="tab" onclick="switchTab(this,'tab-cert')">Certificado & Pagamento</div>
      ${hasPlanilhaId?`<div class="tab" onclick="switchTab(this,'tab-documentos')">Documentos</div>`:''}
      <div class="tab" onclick="switchTab(this,'tab-soluti')">Kit Soluti</div>
    </div>
    <div id="tab-dados" class="tab-pane">
      <div class="form-grid">
        <div class="field form-full"><label>Nome Completo *</label><input id="f-nome" value="${c.nome||''}" placeholder="Nome do cliente"></div>
        <div class="field"><label>CPF / CNPJ</label><input id="f-cpfcnpj" value="${c.cpfCnpj||''}" placeholder="000.000.000-00"></div>
        <div class="field"><label>Data de Nascimento</label><input id="f-nasc" type="date" value="${c.dataNasc||''}"></div>
        <div class="field"><label>Telefone / WhatsApp</label><input id="f-tel" value="${c.telefone||''}" placeholder="(00) 00000-0000"></div>
        <div class="field"><label>E-mail</label><input id="f-email" value="${c.email||''}" placeholder="email@exemplo.com"></div>
        <div class="field form-full"><label>Parceiro / Indicação</label><select id="f-parceiro"><option value="">Nenhum (direto)</option>${pOpts}</select></div>
        <div class="field"><label>Origem do Lead</label><select id="f-origem"><option${c.origem==='Indicação'?' selected':''}>Indicação</option><option${c.origem==='Google Ads'?' selected':''}>Google Ads</option><option${c.origem==='Instagram'?' selected':''}>Instagram</option><option${c.origem==='Site'?' selected':''}>Site</option><option${c.origem==='Direto'?' selected':''}>Direto</option></select></div>
        <div class="field"><label>Status do Atendimento</label><select id="f-status">${STATUS_LIST.map(s=>`<option${c.status===s?' selected':''}>${s}</option>`).join('')}</select></div>
        <div class="field form-full"><label>Observações</label><textarea id="f-obs">${c.obs||''}</textarea></div>
      </div>
    </div>
    <div id="tab-cert" class="tab-pane" style="display:none">
      <div class="form-grid">
        <div class="field"><label>Tipo de Certificado</label><select id="f-tipo">${tOpts}</select></div>
        <div class="field"><label>Data de Emissão</label><input id="f-emissao" type="date" value="${c.dataEmissao||''}"></div>
        <div class="field"><label>Data de Vencimento</label><input id="f-venc" type="date" value="${c.dataVencimento||''}"></div>
        <div class="field"><label>Valor Cobrado (R$)</label><input id="f-valor" type="number" step="0.01" value="${c.valorCobrado||''}" placeholder="0,00"></div>
        <div class="field"><label>Forma de Pagamento</label><select id="f-pagform"><option${c.formaPag==='Pix'?' selected':''}>Pix</option><option${c.formaPag==='Boleto'?' selected':''}>Boleto</option><option${c.formaPag==='Cartão'?' selected':''}>Cartão</option><option${c.formaPag==='Dinheiro'?' selected':''}>Dinheiro</option></select></div>
        <div class="field"><label>Pagamento Confirmado?</label><select id="f-pago"><option value="false"${!c.pago?' selected':''}>Não confirmado</option><option value="true"${c.pago?' selected':''}>✓ Pago / Confirmado</option></select></div>
        <div class="field"><label>Tipo de Validação</label><select id="f-valid"><option${c.tipoValidacao==='Videoconferência'?' selected':''}>Videoconferência</option><option${c.tipoValidacao==='Presencial'?' selected':''}>Presencial</option></select></div>
        <div class="field"><label>Data da Videoconferência</label><input id="f-videodata" type="datetime-local" value="${c.dataVideo||''}"></div>
      </div>
    </div>
    ${hasPlanilhaId?`
    <div id="tab-documentos" class="tab-pane" style="display:none">
      <div style="display:flex;justify-content:space-between;gap:10px;align-items:center;margin-bottom:12px">
        <div>
          <div id="documentos-meta" style="font-size:13px;font-weight:700">Documentos do cliente</div>
          <div style="font-size:12px;color:var(--muted)">Envie, baixe e remova arquivos sem sair do CRM.</div>
        </div>
        <button class="btn btn-sm" type="button" onclick="loadDocumentosCliente('${c.id || editingId}')"><i class="ti ti-refresh"></i> Atualizar</button>
      </div>
      <form id="documentos-form" onsubmit="return uploadDocumentoCliente(event, '${c.id || editingId}')" style="display:grid;gap:12px;padding:14px;border:1px solid var(--border);border-radius:12px;background:var(--surface);margin-bottom:14px">
        <div class="field form-full"><label>Tipo de documento</label><select name="tipo_documento"><option value="rg_cnh">RG/CNH</option><option value="contrato_social">Contrato Social</option><option value="comprovante_residencia">Comprovante de Residência</option><option value="foto_selfie">Foto/Selfie</option><option value="outro" selected>Outro</option></select></div>
        <div class="field form-full"><label>Arquivo</label><input name="arquivo" type="file" accept=".pdf,.jpg,.jpeg,.png" required></div>
        <div class="field form-full"><button class="btn btn-primary" type="submit"><i class="ti ti-upload"></i> Enviar documento</button></div>
      </form>
      <div id="documentos-list"></div>
    </div>
    `:''}
    <div id="tab-soluti" class="tab-pane" style="display:none">
      <p style="font-size:12px;color:var(--muted);margin-bottom:14px">Dados gerados após a videoconferência no Portal Soluti.</p>
      <div class="form-grid">
        <div class="field form-full"><label>Link de Instalação Soluti</label><input id="f-link" value="${c.solutiLink||''}" placeholder="https://..."></div>
        <div class="field form-full"><label>Chave de Acesso</label><input id="f-chave" value="${c.solutiChave||''}" placeholder="XXXX-XXXX-XXXX-XXXX"></div>
        <div class="field form-full"><label>Destinatário do Kit (contador, cliente, etc.)</label><input id="f-dest" value="${c.kitDestinatario||''}" placeholder="Nome ou e-mail do destinatário"></div>
        <div class="field form-full"><label>Kit Enviado?</label><select id="f-kitenviado"><option value="false"${!c.kitEnviado?' selected':''}>Não enviado</option><option value="true"${c.kitEnviado?' selected':''}>✓ Enviado</option></select></div>
      </div>
    </div>
  </div>
  <div class="modal-foot">
    ${hasPlanilhaId?`<button class="btn" onclick="switchTabById('tab-documentos')"><i class="ti ti-folder"></i> Documentos</button>`:''}
    ${editingId?`<button class="btn" onclick="openModal('pagamento','${c.id || editingId}')"><i class="ti ti-qrcode"></i> Abrir Pagamento</button>`:''}
    <button class="btn" onclick="closeModal(true)">Cancelar</button>
    <button class="btn btn-primary" onclick="saveCliente()"><i class="ti ti-device-floppy"></i> Salvar Cliente</button>
  </div>`;
  // Auto-fill vencimento ao escolher emissao
  document.getElementById('f-emissao').addEventListener('change',function(){
    if(this.value){document.getElementById('f-venc').value=addDays(this.value,365)}
  });
  if(hasPlanilhaId){
    loadDocumentosCliente(c.id || editingId);
  }
}

// ==================== NOVO CLIENTE (Planilha real) ====================
function renderNovoClienteModal(box){
  box.innerHTML=`
  <div class="modal-head">
    <div>
      <h2 id="modal-dialog-title">Novo Cliente</h2>
      <div style="font-size:12px;color:var(--muted);margin-top:3px">Grava direto na planilha do Google Drive, junto com os demais registros</div>
    </div>
    <button class="btn btn-sm" onclick="closeModal(true)" aria-label="Fechar"><i class="ti ti-x" aria-hidden="true"></i></button>
  </div>
  <div class="modal-body">
    <form id="novo-cliente-form" onsubmit="saveNovoCliente(event);return false">
      <fieldset class="modal-fieldset">
        <legend>Dados do Cliente</legend>
        <div class="form-grid">
          <div class="field form-full"><label for="ng-nome">Nome do Cliente <span aria-hidden="true" style="color:var(--danger)">*</span></label><input id="ng-nome" name="cliente" placeholder="Nome completo" autocomplete="name" required aria-required="true"></div>
          <div class="field"><label for="ng-cpfcnpj">CPF / CNPJ</label><input id="ng-cpfcnpj" name="cpf_cnpj" placeholder="000.000.000-00" inputmode="numeric" autocomplete="off"></div>
          <div class="field"><label for="ng-email">E-mail</label><input id="ng-email" name="email" type="email" placeholder="email@exemplo.com" autocomplete="email"></div>
          <div class="field"><label for="ng-tel1">Telefone</label><input id="ng-tel1" name="telefone1" type="tel" placeholder="(00) 00000-0000" inputmode="tel" autocomplete="tel"></div>
          <div class="field"><label for="ng-tel2">Telefone 2</label><input id="ng-tel2" name="telefone2" type="tel" placeholder="(00) 00000-0000" inputmode="tel" autocomplete="tel"></div>
          <div class="field"><label for="ng-parceiro">Contador/Parceiro</label><input id="ng-parceiro" name="contador_parceiro" autocomplete="off"></div>
          <div class="field"><label for="ng-contabilidade">Contador/Contabilidade</label><input id="ng-contabilidade" name="contador_contabilidade" autocomplete="off"></div>
        </div>
      </fieldset>
      <fieldset class="modal-fieldset">
        <legend>Certificado &amp; Venda</legend>
        <div class="form-grid">
          <div class="field"><label for="ng-tipo">Tipo de Certificado</label><input id="ng-tipo" name="tipo_certificado" placeholder="Ex: e-CPF A1" autocomplete="off"></div>
          <div class="field"><label for="ng-datavenda">Data da Venda</label><input id="ng-datavenda" name="data_venda" type="date"></div>
          <div class="field"><label for="ng-datavenc">Data de Vencimento</label><input id="ng-datavenc" name="data_vencimento" type="date"></div>
          <div class="field"><label for="ng-valorvenda">Valor da Venda (R$)</label><input id="ng-valorvenda" name="valor_venda" type="number" step="0.01" min="0" inputmode="decimal" placeholder="0,00"></div>
          <div class="field"><label for="ng-percentual">Percentual de Comissão (%)</label><input id="ng-percentual" name="percentual_comissao" type="number" step="0.01" min="0" inputmode="decimal" placeholder="0,00"></div>
          <div class="field"><label for="ng-valorcomissao">Valor da Comissão (R$)</label><input id="ng-valorcomissao" name="valor_comissao" type="number" step="0.01" min="0" inputmode="decimal" placeholder="0,00"></div>
        </div>
      </fieldset>
      <fieldset class="modal-fieldset">
        <legend>Pagamento</legend>
        <div class="form-grid">
          <div class="field"><label for="ng-formapag">Forma de Pagamento</label><input id="ng-formapag" name="forma_pagamento" placeholder="Pix, Boleto, Cartão..." autocomplete="off"></div>
          <div class="field"><label for="ng-banco">Banco</label><input id="ng-banco" name="banco" autocomplete="off"></div>
          <div class="field"><label for="ng-pix">Chave PIX</label><input id="ng-pix" name="chave_pix" autocomplete="off"></div>
          <div class="field"><label for="ng-pagovenda">Pago (Venda)</label><select id="ng-pagovenda" name="pago_venda"><option value="Não" selected>Não</option><option value="Sim">Sim</option></select></div>
          <div class="field"><label for="ng-pagocomissao">Pago (Comissão)</label><select id="ng-pagocomissao" name="pago_comissao"><option value="Não" selected>Não</option><option value="Sim">Sim</option></select></div>
        </div>
      </fieldset>
    </form>
  </div>
  <div class="modal-foot">
    <button class="btn" onclick="closeModal(true)">Cancelar</button>
    <button class="btn btn-primary" id="ng-save-btn" onclick="document.getElementById('novo-cliente-form').requestSubmit()"><i class="ti ti-device-floppy" aria-hidden="true"></i> Salvar Cliente</button>
  </div>`;
}

async function saveNovoCliente(event){
  if(event)event.preventDefault();
  const form=document.getElementById('novo-cliente-form');
  if(!form.reportValidity())return;
  const btn=document.getElementById('ng-save-btn');
  const payload=new URLSearchParams(new FormData(form));
  const originalBtnContent=btn?btn.innerHTML:'';
  if(btn){
    btn.disabled=true;
    btn.innerHTML='<i class="ti ti-loader-2" aria-hidden="true" style="animation:spin 1s linear infinite"></i> Salvando...';
  }
  try{
    const response=await fetch('/planilha/criar/',{
      method:'POST',
      headers:{'Content-Type':'application/x-www-form-urlencoded','X-CSRFToken':getCsrfToken(),'X-Requested-With':'XMLHttpRequest'},
      body:payload.toString(),
    });
    const data=await response.json().catch(()=>({}));
    if(!response.ok)throw new Error(data.error||'Falha ao criar cliente');
    showToast(data.drive_updated?'Cliente criado e planilha do Drive atualizada':'Cliente criado localmente (falha ao atualizar Drive)', data.drive_updated?'success':'info');
    closeModal(true);
    setTimeout(()=>{ location.hash='clientes'; location.reload(); },900);
  }catch(err){
    console.error(err);
    showToast(err.message||'Erro ao criar cliente','error');
    if(btn){btn.disabled=false;btn.innerHTML=originalBtnContent;}
  }
}

function switchTab(el,tabId){
  el.closest('.tabs').querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  el.classList.add('active');
  document.querySelectorAll('.tab-pane').forEach(p=>p.style.display='none');
  document.getElementById(tabId).style.display='';
}
// Adicione isto no cert_manager.js caso as funções não existam mais

function saveCliente(){
  const nome=document.getElementById('f-nome').value.trim();
  if(!nome){alert('Nome obrigatório');return}
  const c=resolveClienteById(editingId) || {id:(editingId || uid()),criadoEm:new Date().toISOString().split('T')[0],historico:[],notificacoes:[]};
  c.nome=nome;
  c.cpfCnpj=document.getElementById('f-cpfcnpj').value;
  c.dataNasc=document.getElementById('f-nasc').value;
  c.telefone=document.getElementById('f-tel').value;
  c.email=document.getElementById('f-email').value;
  c.parceiroId=document.getElementById('f-parceiro').value||null;
  c.origem=document.getElementById('f-origem').value;
  c.status=document.getElementById('f-status').value;
  c.obs=document.getElementById('f-obs').value;
  c.tipoCert=document.getElementById('f-tipo').value;
  c.dataEmissao=document.getElementById('f-emissao').value;
  c.dataVencimento=document.getElementById('f-venc').value;
  c.valorCobrado=parseFloat(document.getElementById('f-valor').value)||0;
  c.formaPag=document.getElementById('f-pagform').value;
  c.pago=document.getElementById('f-pago').value==='true';
  c.tipoValidacao=document.getElementById('f-valid').value;
  c.dataVideo=document.getElementById('f-videodata').value;
  c.solutiLink=document.getElementById('f-link').value;
  c.solutiChave=document.getElementById('f-chave').value;
  c.kitDestinatario=document.getElementById('f-dest').value;
  c.kitEnviado=document.getElementById('f-kitenviado').value==='true';
  c.triagem={
    temCnh:Number(document.getElementById('triagem-temCnh')?.value ?? 0),
    jaTeveCertificado:Number(document.getElementById('triagem-jaTeveCertificado')?.value ?? 0),
    temBiometria:Number(document.getElementById('triagem-temBiometria')?.value ?? 0),
  };
  c.triagem.resumo=getTriagemSummary(c.triagem);
  if(!editingId)clientes.unshift(c);
  save();closeModal(true);renderClientes();renderDashboard();renderKanban();
  editingId=null;
}

function renderParceiroModal(box){
  const p=editingId?parceiros.find(x=>x.id===editingId):{};
  box.innerHTML=`
  <div class="modal-head"><h2 id="modal-dialog-title">${editingId?'Editar Parceiro':'Novo Parceiro'}</h2><button class="btn btn-sm" onclick="closeModal(true)" aria-label="Fechar"><i class="ti ti-x" aria-hidden="true"></i></button></div>
  <div class="modal-body">
    <div class="form-grid">
      <div class="field form-full"><label>Nome / Escritório *</label><input id="p-nome" value="${p.nome||''}" placeholder="Ex: Escritório Contábil Silva"></div>
      <div class="field"><label>Tipo</label><select id="p-tipo"><option${p.tipo==='Contador'?' selected':''}>Contador</option><option${p.tipo==='Advogado'?' selected':''}>Advogado</option><option${p.tipo==='Escritório'?' selected':''}>Escritório</option><option${p.tipo==='Correspondente'?' selected':''}>Correspondente</option><option${p.tipo==='Outro'?' selected':''}>Outro</option></select></div>
      <div class="field"><label>Telefone</label><input id="p-tel" value="${p.telefone||''}" placeholder="(00) 00000-0000"></div>
      <div class="field"><label>E-mail</label><input id="p-email" value="${p.email||''}" placeholder="contato@escritorio.com"></div>
      <div class="field form-full"><label>Comissão (%)</label><input id="p-comissao" type="number" step="0.01" min="0" value="${p.comissao!=null?p.comissao:''}" placeholder="10"></div>
      <div class="field form-full"><label>Contato Principal</label><input id="p-contato" value="${p.contato||''}" placeholder="Nome do responsável"></div>
    </div>
  </div>
  <div class="modal-foot">
    <button class="btn" onclick="closeModal(true)">Cancelar</button>
    <button class="btn btn-primary" onclick="saveParceiro()"><i class="ti ti-device-floppy"></i> Salvar</button>
  </div>`;
}
// Inicializa comportamentos ao carregar o DOM
document.addEventListener('DOMContentLoaded', function(){
  try{ renderSaveActions(); initSaveMenu();
    // se a fonte padrão for servidor e não há clientes locais, aplica estado do servidor
    if(getDataSource()==='server' && (!clientes || clientes.length===0)){
      fetchServerState(true);
    }
  }catch(e){}
});

function saveParceiro(){
  const nome=document.getElementById('p-nome').value.trim();
  if(!nome){alert('Nome obrigatório');return}
  const p=editingId?parceiros.find(x=>x.id===editingId):{id:uid()};
  p.nome=nome;p.tipo=document.getElementById('p-tipo').value;
  p.telefone=document.getElementById('p-tel').value;p.email=document.getElementById('p-email').value;
  const comissao=parseFloat(document.getElementById('p-comissao').value);
  p.comissao=Number.isFinite(comissao)?comissao:null;
  p.contato=document.getElementById('p-contato').value;
  if(!editingId)parceiros.push(p);
  save();closeModal(true);renderParceiros();editingId=null;
}

function renderPrecoModal(box){
  const p=editingId?precos.find(x=>x.id==editingId):{};
  box.innerHTML=`
  <div class="modal-head"><h2 id="modal-dialog-title">${editingId?'Editar Preço':'Novo Tipo de Certificado'}</h2><button class="btn btn-sm" onclick="closeModal(true)" aria-label="Fechar"><i class="ti ti-x" aria-hidden="true"></i></button></div>
  <div class="modal-body">
    <div class="form-grid">
      <div class="field form-full"><label>Tipo de Certificado *</label><input id="pr-tipo" value="${p.tipo||''}" placeholder="Ex: e-CPF A1"></div>
      <div class="field"><label>Validade</label><input id="pr-valid" value="${p.validade||'1 ano'}" placeholder="1 ano, 3 anos..."></div>
      <div class="field"><label>Preço (R$) *</label><input id="pr-preco" type="number" step="0.01" value="${p.preco||''}" placeholder="0,00"></div>
    </div>
  </div>
  <div class="modal-foot">
    <button class="btn" onclick="closeModal(true)">Cancelar</button>
    <button class="btn btn-primary" onclick="savePreco()"><i class="ti ti-device-floppy"></i> Salvar</button>
  </div>`;
}

function savePreco(){
  const tipo=document.getElementById('pr-tipo').value.trim();
  if(!tipo){alert('Tipo obrigatório');return}
  const p=editingId?precos.find(x=>x.id==editingId):{id:uid()};
  p.tipo=tipo;p.validade=document.getElementById('pr-valid').value;
  p.preco=parseFloat(document.getElementById('pr-preco').value)||0;
  if(!editingId)precos.push(p);
  save();closeModal(true);renderTabela();editingId=null;
}

function renderContatoModal(box,cid){
  const c=clientes.find(x=>x.id===cid);
  if(!c)return;
  box.innerHTML=`
  <div class="modal-head"><h2 id="modal-dialog-title">Registrar Contato — ${c.nome}</h2><button class="btn btn-sm" onclick="closeModal(true)" aria-label="Fechar"><i class="ti ti-x" aria-hidden="true"></i></button></div>
  <div class="modal-body">
    <div class="form-grid">
      <div class="field"><label>Data</label><input id="ct-data" type="date" value="${new Date().toISOString().split('T')[0]}"></div>
      <div class="field"><label>Canal</label><select id="ct-canal"><option>WhatsApp</option><option>Telefone</option><option>E-mail</option><option>Presencial</option></select></div>
      <div class="field form-full"><label>Resultado / Observação</label><textarea id="ct-obs" placeholder="Ex: Cliente confirmou interesse, aguardando documentos..."></textarea></div>
      <div class="field"><label>Novo Status</label><select id="ct-status">${STATUS_LIST.map(s=>`<option${c.status===s?' selected':''}>${s}</option>`).join('')}</select></div>
    </div>
  </div>
  <div class="modal-foot">
    <button class="btn" onclick="closeModal(true)">Cancelar</button>
    <button class="btn btn-primary" onclick="saveContato('${cid}')">Registrar</button>
  </div>`;
}

function saveContato(cid){
  const c=clientes.find(x=>x.id===cid);
  if(!c)return;
  if(!c.historico)c.historico=[];
  c.historico.push({data:document.getElementById('ct-data').value,canal:document.getElementById('ct-canal').value,obs:document.getElementById('ct-obs').value,dt:new Date().toISOString()});
  c.status=document.getElementById('ct-status').value;
  save();closeModal(true);renderClientes();renderRenovacoes();renderKanban();
}

function renderPagamentoModal(box, cid) {
  let c = resolveClienteById(cid || editingId);
  if (!c) {
      const alertData = getAlertData();
      const allAlerts = [...alertData.renovacoes.urgentes, ...alertData.renovacoes.normais, ...alertData.pagamentos.urgentes, ...alertData.pagamentos.normais];
      const alertItem = allAlerts.find(x => String(x.id) === String(cid));
      if (alertItem) {
          c = { 
              id: cid, 
              nome: alertItem.nome, 
              tipoCert: alertItem.tipoCert, 
              valorCobrado: alertItem.valorCobrado || 0,
              dataVencimento: alertItem.dataVencimento || '',
              pago: alertItem.pago || false,
              formaPag: 'Pix',
              historico: [],
              notificacoes: []
          };
      } else {
          box.innerHTML = `<div class="modal-head"><h2>Pagamento</h2><button class="btn btn-sm" onclick="closeModal(true)"><i class="ti ti-x"></i></button></div><div class="modal-body"><p style="font-size:13px;color:var(--muted)">Selecione um cliente válido antes de registrar um pagamento.</p></div>`;
          return;
      }
  }

  const histHTML = (c.historico || []).slice().reverse().map(h => `
    <div style="padding: 14px; border-bottom: 1px solid var(--border); font-size: 13px;">
        <div style="display:flex; justify-content:space-between; margin-bottom:6px;">
            <strong><i class="ti ti-calendar"></i> ${fmtDate(h.data)} — ${h.canal || 'Pagamento'}</strong>
            <span class="badge ${c.pago ? 'badge-emitido' : 'badge-pag'}">${h.obs ? h.obs.split('·')[0] : 'Atualizado'}</span>
        </div>
        <div style="background: var(--bg); padding: 10px; border-radius: 6px;">${h.obs || 'Nenhuma observação informada.'}</div>
    </div>`).join('') || '<div class="empty-state"><i class="ti ti-receipt-off"></i><p>Nenhum histórico de pagamento registrado.</p></div>';

  box.innerHTML = `
  <div class="modal-head">
    <h2><i class="ti ti-cash"></i> Gestão de Pagamento — ${c.nome || 'Cliente'}</h2>
    <button class="btn btn-sm" onclick="closeModal(true)"><i class="ti ti-x"></i></button>
  </div>
  <div class="modal-body" style="padding: 0;">
    
    <!-- Abas -->
    <div class="tabs" style="padding: 14px 20px 0 20px; background: #fafaf8; border-bottom: 1px solid var(--border); margin-bottom:0;">
      <div class="tab active" onclick="switchTab(this,'tab-reg-pagamento')">Registrar Pagamento</div>
      <div class="tab" onclick="switchTab(this,'tab-hist-pagamento')">Visualizar Histórico</div>
    </div>

    <!-- Aba de Formulário -->
    <div id="tab-reg-pagamento" class="tab-pane" style="padding: 20px;">
        <div style="background: var(--bg); padding: 12px; border-radius: 8px; margin-bottom: 20px; font-size: 13px; display:flex; justify-content:space-between; align-items:center;">
            <div><strong>Cliente:</strong> <br><span style="color:var(--accent)">${c.nome || '—'}</span></div>
            <div><strong>Status Atual:</strong> <br><span style="color:${c.pago ? 'var(--success)' : 'var(--danger)'}">${c.pago ? '✓ Confirmado' : '⚠ Pendente'}</span></div>
        </div>

        <div class="form-grid">
          <div class="field"><label>Valor (R$)</label><input id="pg-valor" type="number" step="0.01" value="${c.valorCobrado || ''}" placeholder="0,00"></div>
          <div class="field"><label>Status do Pagamento</label><select id="pg-status"><option value="Pendente"${!c.pago?' selected':''}>Pendente</option><option value="Pago"${c.pago?' selected':''}>Pago / Confirmado</option></select></div>
          <div class="field"><label>Forma de Pagamento</label><select id="pg-forma"><option${(c.formaPag||'Pix')==='Pix'?' selected':''}>Pix</option><option${(c.formaPag||'Boleto')==='Boleto'?' selected':''}>Boleto</option><option${(c.formaPag||'Cartão')==='Cartão'?' selected':''}>Cartão</option><option${(c.formaPag||'Dinheiro')==='Dinheiro'?' selected':''}>Dinheiro</option></select></div>
          <div class="field"><label>Data da Transação</label><input id="pg-data" type="date" value="${c.dataPagamento || new Date().toISOString().split('T')[0]}"></div>
          
          <div class="field form-full"><label>Observação / Detalhes</label><textarea id="pg-obs" placeholder="Ex: Pagamento confirmado via PIX no valor integral.">${c.obs || ''}</textarea></div>
          
          <div class="field form-full" style="background: var(--bg); padding: 12px; border-radius: 8px;">
            <label style="display:flex; align-items:center; gap:8px; cursor:pointer;"><input id="pg-notificar" type="checkbox" checked> Enviar notificação de pagamento ao cliente</label>
            <div style="margin-top: 8px;"><input id="pg-notificacao" class="field" style="width:100%" placeholder="Mensagem: Seu pagamento foi confirmado, obrigado." value="Pagamento registrado com sucesso."></div>
          </div>
        </div>
    </div>

    <!-- Aba de Histórico -->
    <div id="tab-hist-pagamento" class="tab-pane" style="display: none; max-height: 450px; overflow-y: auto;">
        ${histHTML}
    </div>
  </div>
  
  <div class="modal-foot">
    <button class="btn" onclick="closeModal(true)">Cancelar</button>
    <button class="btn btn-primary" onclick="savePagamento('${c.id}')"><i class="ti ti-device-floppy"></i> Salvar Pagamento</button>
  </div>`;
}

function savePagamento(cid){
  let c = resolveClienteById(cid || editingId);
  let isNewToLocal = false;

  if(!c) {
      const alertData = getAlertData();
      const allAlerts = [...alertData.renovacoes.urgentes, ...alertData.renovacoes.normais, ...alertData.pagamentos.urgentes, ...alertData.pagamentos.normais];
      const alertItem = allAlerts.find(x => String(x.id) === String(cid));
      
      if (alertItem) {
          c = { 
              id: cid, 
              nome: alertItem.nome, 
              tipoCert: alertItem.tipoCert, 
              criadoEm: new Date().toISOString().split('T')[0], 
              status: 'Aguardando Pagamento', 
              historico: [],
              notificacoes: []
          };
          isNewToLocal = true;
      } else {
          showToast('Erro ao salvar pagamento: Cliente não encontrado.', 'error');
          return;
      }
  }

  const valor = parseFloat(document.getElementById('pg-valor').value) || 0;
  const status = document.getElementById('pg-status').value;
  const forma = document.getElementById('pg-forma').value;
  const data = document.getElementById('pg-data').value || new Date().toISOString().split('T')[0];
  const obs = document.getElementById('pg-obs').value.trim();

  c.valorCobrado = valor;
  c.formaPag = forma;
  c.pago = (status === 'Pago');
  c.dataPagamento = data;
  if(obs){ c.obs = [c.obs, obs].filter(Boolean).join('\n'); }

  if(c.pago && c.status === 'Aguardando Pagamento'){
      c.status = 'Emitido';
  }

  if(!c.historico) c.historico = [];
  c.historico.push({
      data, 
      canal: 'Pagamento', 
      obs: `${status} · ${forma}${valor ? ` · ${fmtMoney(valor)}` : ''}${obs ? ` - ${obs}` : ''}`, 
      dt: new Date().toISOString()
  });

  const notify = document.getElementById('pg-notificar')?.checked;
  if(notify){
    if(!Array.isArray(c.notificacoes)) c.notificacoes = [];
    c.notificacoes.unshift({
      id: uid(),
      data,
      tipo: 'pagamento',
      titulo: 'Pagamento registrado',
      texto: document.getElementById('pg-notificacao').value.trim() || `Pagamento ${status.toLowerCase()} para ${c.nome || 'o cliente'}.`,
      status: c.pago ? 'enviado' : 'pendente',
      origem: 'pagamento',
    });
  }

  if(isNewToLocal){
      clientes.unshift(c);
  }

  save();
  closeModal(true);
  
  renderClientes();
  renderDashboard();
  renderKanban();
  renderRenovacoes();
  renderInadimplencia();
  
  showToast('Pagamento salvo com sucesso!', 'success');
}
// ==================== NOVO MODAL DE CRM (CONTATOS) ====================
function renderContatoModal(box, cid) {
  // 1. Busca o cliente localmente, ou extrai os dados do card de alerta (se vier da planilha)
  let c = clientes.find(x => String(x.id) === String(cid));
  if (!c) {
      const alertData = getAlertData();
      const allAlerts = [...alertData.renovacoes.urgentes, ...alertData.renovacoes.normais, ...alertData.pagamentos.urgentes, ...alertData.pagamentos.normais];
      const alertItem = allAlerts.find(x => String(x.id) === String(cid));
      if (alertItem) {
          c = { id: cid, nome: alertItem.nome, tipoCert: alertItem.tipoCert, historico: [] };
      } else {
          showToast('Erro: Cliente não encontrado.', 'error');
          return;
      }
  }

  // 2. Monta a lista visual de contatos anteriores
  const histHTML = (c.historico || []).slice().reverse().map(h => `
    <div style="padding: 14px; border-bottom: 1px solid var(--border); font-size: 13px;">
        <div style="display:flex; justify-content:space-between; margin-bottom:6px;">
            <strong><i class="ti ti-calendar"></i> ${fmtDate(h.data)} — ${h.canal}</strong>
            <span class="badge badge-novo">${h.resultado || 'Contato Feito'}</span>
        </div>
        <div style="color: var(--muted); margin-bottom: 6px;">
            <strong>Agendado para:</strong> ${h.agendamento ? new Date(h.agendamento).toLocaleString('pt-BR') : 'Não agendado'} 
            ${h.produto ? `| <strong>Produto Ofertado:</strong> ${h.produto}` : ''}
        </div>
        <div style="background: var(--bg); padding: 10px; border-radius: 6px;">${h.obs || 'Nenhuma observação detalhada.'}</div>
    </div>`).join('') || '<div class="empty-state"><i class="ti ti-message-off"></i><p>Nenhum histórico de contato registrado.</p></div>';

  // 3. Renderiza a estrutura do Modal com Abas
  box.innerHTML = `
  <div class="modal-head">
    <h2><i class="ti ti-headset"></i> Gestão de Contato — ${c.nome}</h2>
    <button class="btn btn-sm" onclick="closeModal(true)"><i class="ti ti-x"></i></button>
  </div>
  <div class="modal-body" style="padding: 0;">
    
    <!-- Abas -->
    <div class="tabs" style="padding: 14px 20px 0 20px; background: #fafaf8; border-bottom: 1px solid var(--border); margin-bottom:0;">
      <div class="tab active" onclick="switchTab(this,'tab-reg-contato')">Registrar Contato</div>
      <div class="tab" onclick="switchTab(this,'tab-hist-contato')">Visualizar Histórico</div>
    </div>
    
    <!-- Aba de Formulário -->
    <div id="tab-reg-contato" class="tab-pane" style="padding: 20px;">
        <div style="background: var(--bg); padding: 12px; border-radius: 8px; margin-bottom: 20px; font-size: 13px; display:flex; gap:20px;">
            <div><strong>Cliente:</strong> <br><span style="color:var(--accent)">${c.nome}</span></div>
            <div><strong>Produto Atual:</strong> <br><span style="color:var(--accent)">${c.tipoCert || 'Não identificado'}</span></div>
        </div>
        
        <div class="form-grid cols3">
          <div class="field"><label>Data do Contato</label><input id="ct-data" type="date" value="${new Date().toISOString().split('T')[0]}"></div>
          <div class="field"><label>Canal</label><select id="ct-canal"><option>WhatsApp</option><option>Ligação</option><option>E-mail</option><option>Presencial</option></select></div>
          <div class="field"><label>Resultado da Conversa</label><select id="ct-resultado"><option>Em Negociação</option><option>Agendado para Renovação</option><option>Sem Interesse</option><option>Caixa Postal / Não Atende</option><option>Pagamento Confirmado</option></select></div>
          
          <div class="field"><label>Produto Ofertado</label><select id="ct-produto"><option value="">Manter atual</option>${precos.map(p=>`<option>${p.tipo}</option>`).join('')}</select></div>
          <div class="field"><label>Agendar Retorno Para</label><input id="ct-agendamento" type="datetime-local"></div>
          <div class="field"><label>Alterar Status no Funil</label><select id="ct-status">${STATUS_LIST.map(s=>`<option${c.status===s?' selected':''}>${s}</option>`).join('')}</select></div>
          
          <div class="field form-full">
            <label>Observação (Até 600 caracteres recomendados)</label>
            <textarea id="ct-obs" placeholder="Descreva como foi o atendimento..." style="min-height: 100px; resize: vertical;"></textarea>
          </div>
        </div>
    </div>

    <!-- Aba de Histórico -->
    <div id="tab-hist-contato" class="tab-pane" style="display: none; max-height: 450px; overflow-y: auto;">
        ${histHTML}
    </div>
  </div>
  
  <div class="modal-foot">
    <button class="btn" onclick="closeModal(true)">Cancelar</button>
    <button class="btn btn-primary" onclick="saveContato('${c.id}')"><i class="ti ti-device-floppy"></i> Salvar Registro</button>
  </div>`;
}

function saveContato(cid) {
  let c = clientes.find(x => String(x.id) === String(cid));
  let isNewToLocal = false;

  // Se o cliente só existe na planilha/backend, cria uma base local para ele receber o histórico
  if (!c) {
      const alertData = getAlertData();
      const allAlerts = [...alertData.renovacoes.urgentes, ...alertData.renovacoes.normais, ...alertData.pagamentos.urgentes, ...alertData.pagamentos.normais];
      const alertItem = allAlerts.find(x => String(x.id) === String(cid));
      
      if (alertItem) {
          c = { 
              id: cid, 
              nome: alertItem.nome, 
              tipoCert: alertItem.tipoCert, 
              criadoEm: new Date().toISOString().split('T')[0], 
              status: 'Novo Lead', 
              historico: [] 
          };
          isNewToLocal = true;
      } else {
          showToast('Erro ao salvar: Cliente não encontrado.', 'error');
          return;
      }
  }

  if (!c.historico) c.historico = [];
  
  // Salva os dados enriquecidos do novo formulário
  c.historico.push({
      data: document.getElementById('ct-data').value,
      canal: document.getElementById('ct-canal').value,
      resultado: document.getElementById('ct-resultado').value,
      produto: document.getElementById('ct-produto').value,
      agendamento: document.getElementById('ct-agendamento').value,
      obs: document.getElementById('ct-obs').value,
      dt: new Date().toISOString()
  });

  // Atualiza o status do Kanban de acordo com a seleção
  c.status = document.getElementById('ct-status').value;
  
  if (isNewToLocal) {
      clientes.unshift(c);
  }

  save();
  closeModal(true);
  
  // Recarrega as telas para refletir a mudança de status
  renderClientes();
  renderRenovacoes();
  renderInadimplencia();
  renderKanban();
  
  showToast('Contato registrado com sucesso!', 'success');
}

// ==================== DETAIL ====================
function openDetail(id){
  const c=resolveClienteById(id);
  if(!c)return;
  const parc=parceiros.find(p=>p.id===c.parceiroId);
  const si=STATUS_LIST.indexOf(c.status);
  const steps=STATUS_LIST.map((s,i)=>`<div class="step${i<si?' done':i===si?' current':''}">${s}</div>`).join('');
  const hist=(c.historico||[]).slice().reverse().map(h=>`<div class="contact-entry"><span class="dt">${fmtDate(h.data)}<br><small>${h.canal}</small></span><span>${h.obs||'—'}</span></div>`).join('')||'<p style="font-size:12px;color:var(--muted)">Nenhum contato registrado</p>';
  const notificacoes=(c.notificacoes||[]).slice().reverse().map(n=>`<div class="contact-entry"><span class="dt">${fmtDate(n.data)}<br><small>${n.titulo||'Notificação'}</small></span><span>${n.texto||'—'}</span></div>`).join('')||'<p style="font-size:12px;color:var(--muted)">Nenhuma notificação registrada</p>';
  const kit=c.solutiLink||c.solutiChave?`<div class="kit-box"><div class="kit-label"><i class="ti ti-key"></i> Kit de Instalação Soluti</div><div class="kit-row"><strong>Link:</strong> <a href="${c.solutiLink}" style="color:var(--accent)" target="_blank">${c.solutiLink}</a></div><div class="kit-row"><strong>Chave:</strong> <code>${c.solutiChave}</code></div><div class="kit-row"><strong>Destinatário:</strong> ${c.kitDestinatario||'—'} <span style="color:${c.kitEnviado?'var(--success)':'var(--danger)'}">${c.kitEnviado?'✓ Enviado':'Não enviado'}</span></div></div>`:'<p style="font-size:12px;color:var(--muted)">Kit Soluti ainda não registrado</p>';
  document.getElementById('detail-box').innerHTML=`
  <div class="modal-head">
    <div>
      <h2>${c.nome}</h2>
      <div style="font-size:12px;color:var(--muted);margin-top:2px">${c.cpfCnpj||'CPF/CNPJ não informado'} · Cadastrado em ${fmtDate(c.criadoEm)}</div>
    </div>
    <div style="display:flex;gap:8px">
      <button class="btn btn-sm" onclick="openDocumentosCliente('${c.id}')"><i class="ti ti-folder"></i> Documentos</button>
      <button class="btn btn-sm" onclick="openModal('pagamento','${c.id}');closeDetail(true)"><i class="ti ti-qrcode"></i> Pagamento</button>
      <button class="btn btn-sm" onclick="editCliente('${c.id}');closeDetail(true)"><i class="ti ti-edit"></i> Editar</button>
      <button class="btn btn-sm" onclick="closeDetail(true)"><i class="ti ti-x"></i></button>
    </div>
  </div>
  <div class="modal-body">
    <div class="progress-steps" style="margin-bottom:18px">${steps}</div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px">
      <div>
        <div class="detail-section">
          <h4>Dados Pessoais</h4>
          <div class="detail-row"><span class="lbl">Telefone</span><span class="val">${c.telefone||'—'}</span></div>
          <div class="detail-row"><span class="lbl">E-mail</span><span class="val" style="word-break:break-all">${c.email||'—'}</span></div>
          <div class="detail-row"><span class="lbl">Nascimento</span><span class="val">${fmtDate(c.dataNasc)}</span></div>
          <div class="detail-row"><span class="lbl">Origem</span><span class="val">${c.origem||'—'}</span></div>
          <div class="detail-row"><span class="lbl">Parceiro</span><span class="val">${parc?`<span class="parceiro-tag">${parc.nome}</span>`:'Sem parceiro'}</span></div>
        </div>
        <div class="detail-section">
          <h4>Certificado</h4>
          <div class="detail-row"><span class="lbl">Tipo</span><span class="val">${c.tipoCert||'—'}</span></div>
          <div class="detail-row"><span class="lbl">Emissão</span><span class="val">${fmtDate(c.dataEmissao)}</span></div>
          <div class="detail-row"><span class="lbl">Vencimento</span><span class="val">${c.dataVencimento?`<span class="badge ${daysUntil(c.dataVencimento)<0?'badge-vencido':daysUntil(c.dataVencimento)<60?'badge-vencendo':'badge-emitido'}">${fmtDate(c.dataVencimento)}</span>`:'—'}</span></div>
          <div class="detail-row"><span class="lbl">Validação</span><span class="val">${c.tipoValidacao||'—'}</span></div>
          <div class="detail-row"><span class="lbl">Videoconferência</span><span class="val">${c.dataVideo?fmtDate(c.dataVideo):'—'}</span></div>
        </div>
        <div class="detail-section">
          <h4>Pagamento</h4>
          <div class="detail-row"><span class="lbl">Valor</span><span class="val" style="font-weight:700;color:var(--success)">${c.valorCobrado?fmtMoney(c.valorCobrado):'—'}</span></div>
          <div class="detail-row"><span class="lbl">Forma</span><span class="val">${c.formaPag||'—'}</span></div>
          <div class="detail-row"><span class="lbl">Status pagto</span><span class="val"><span style="color:${c.pago?'var(--success)':'var(--danger)'}">${c.pago?'✓ Confirmado':'Pendente'}</span></span></div>
        </div>
      </div>
      <div>
        <div class="detail-section">
          <h4>Kit Soluti</h4>
          ${kit}
        </div>
        <div class="detail-section">
          <h4>Histórico de Contatos</h4>
          <button class="btn btn-sm" style="margin-bottom:8px" onclick="openModal('contato','${c.id}');closeDetail(true)"><i class="ti ti-plus"></i> Registrar Contato</button>
          <div class="contact-log">${hist}</div>
        </div>
        <div class="detail-section">
          <h4>Notificações</h4>
          <div class="contact-log">${notificacoes}</div>
        </div>
        ${c.obs?`<div class="detail-section"><h4>Observações</h4><p style="font-size:13px;color:var(--muted)">${c.obs}</p></div>`:''}
      </div>
    </div>
  </div>`;
  document.getElementById('detail-overlay').classList.add('open');
}
function closeDetail(e){if(e===true||e.target===document.getElementById('detail-overlay')){document.getElementById('detail-overlay').classList.remove('open')}}

// ==================== INIT ====================
async function loadAppState(){
  try {
    const response = await fetch('/app_state/');
    if (response.ok){
      const data = await response.json();
      if (Array.isArray(data.clientes) && data.clientes.length) {
        clientes = data.clientes;
      }
      if (Array.isArray(data.parceiros) && data.parceiros.length) {
        parceiros = data.parceiros;
      } else if (!parceiros.length && typeof window !== 'undefined' && Array.isArray(window.INITIAL_PARCEIROS) && window.INITIAL_PARCEIROS.length>0) {
        parceiros = window.INITIAL_PARCEIROS.slice();
      }
      if (Array.isArray(data.precos) && data.precos.length) {
        precos = data.precos;
      }
      save();
    }
  } catch (err){
    console.warn('Não foi possível carregar estado do servidor', err);
  }
  renderDashboard();
  renderClientes();
  filterPlanilhaImportada();
  renderParceiros();
  renderTabela();
  updateBadges();
  syncBackendAlertCounts();
}

loadAppState();
