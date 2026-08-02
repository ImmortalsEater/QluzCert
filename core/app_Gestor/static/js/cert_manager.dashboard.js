const PAGE_CONFIG = {
  dashboard:{title:'Dashboard', render:renderDashboard},
  clientes:{title:'Clientes', render:renderClientesSimples},
  planilha:{title:'Planilha', render:filterPlanilhaImportada},
  funil:{title:'Funil de Atendimento', render:renderKanban},
  renovacoes:{title:'Alertas de Renovação', render:renderRenovacoes},
  pagamentos:{title:'Alertas de Pagamento', render:renderInadimplencia},
  parceiros:{title:'Parceiros Comerciais', render:renderParceiros},
  tabela:{title:'Tabela de Preços', render:renderTabela},
}

// ==================== PLANILHA: PRESETS DE COLUNAS ====================
const PLANILHA_COLUMN_PRESETS = {
  essencial: ['col-cliente','col-telefone1','col-status','col-data-vencimento'],
  financeiro: ['col-cliente','col-telefone1','col-status','col-data-vencimento',
    'col-valor-venda','col-percentual','col-valor-comissao','col-pago-venda','col-pago-comissao'],
};
function aplicarPresetColunas(nome){
  const alvo = PLANILHA_COLUMN_PRESETS[nome] || null; // null = 'tudo', mostra todas
  document.querySelectorAll('.column-toggle').forEach(toggle=>{
    const show = alvo ? alvo.includes(toggle.dataset.col) : true;
    if(toggle.checked !== show){
      toggle.checked = show;
      toggle.dispatchEvent(new Event('change'));
    }
  });
  document.querySelectorAll('.column-preset-chip').forEach(chip=>{
    chip.classList.toggle('active', chip.dataset.preset === nome);
  });
  DB.set('planilha_preset', nome);
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

function toggleNavSection(header){
  const key = header.dataset.group;
  const group = document.getElementById('nav-group-'+key);
  if(!group) return;
  const collapsed = group.classList.toggle('collapsed');
  header.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
  const state = DB.get('nav_collapsed') || {};
  if(collapsed) state[key]=true; else delete state[key];
  DB.set('nav_collapsed', state);
}

function restoreNavSectionState(){
  const state = DB.get('nav_collapsed') || {};
  Object.keys(state).forEach(key=>{
    const group = document.getElementById('nav-group-'+key);
    const header = document.querySelector(`.nav-section[data-group="${key}"]`);
    if(group && header){
      group.classList.add('collapsed');
      header.setAttribute('aria-expanded','false');
    }
  });
}

function renderSaveActions(){
  const html = `
    <div class="btn-segmented">
      <button class="btn-segment btn-segment-start" id="atualizar-planilha-btn" onclick="atualizarPlanilha()"><i class="ti ti-refresh"></i>Atualizar agora</button>
      <div class="save-dropdown btn-segment-end-wrap" style="position:relative">
        <button class="btn-segment btn-segment-end btn-segment-primary" id="save-main-btn"><i class="ti ti-device-floppy"></i>Salvar<i class="ti ti-chevron-down" style="margin-left:2px;font-size:12px"></i></button>
        <div id="save-menu" class="column-selector-panel">
          <button type="button" class="action-menu-item" id="save-local-btn"><i class="ti ti-device-floppy"></i>Salvar localmente</button>
          <button type="button" class="action-menu-item" id="export-btn"><i class="ti ti-download"></i>Exportar (.xlsx)</button>
        </div>
      </div>
    </div>
    <span id="save-status" style="margin-left:12px;font-size:13px;color:var(--muted)"></span>
  `;
  const ta = document.getElementById('topbar-actions');
  if(ta) ta.innerHTML = html;
}

function updateBadges(){
  const alertData = getAlertData();
  const counts = alertData.counts || {};
  // Badge de Renovações só conta o que já venceu ou vence em até 7 dias --
  // o "urgentes" do backend (<=30 dias) avisava cedo demais e deixava o
  // badge sempre vermelho, o que fazia a cor deixar de significar algo.
  const renovacoesProximas = [...alertData.renovacoes.urgentes, ...alertData.renovacoes.normais]
    .filter(item => Number(item.dias) <= 7).length;
  // Pagamentos já tem um limiar rigoroso pronto no backend (dias_restantes<=0,
  // ou seja, vencido de verdade) -- usa ele em vez de somar com "normais".
  const pagamentosVencidos = Number(counts.pagamentos_urgentes || 0);
  const rb=document.getElementById('ren-badge');
  if(rb){rb.style.display=renovacoesProximas?'':'none';rb.textContent=renovacoesProximas}
  const pb=document.getElementById('pag-badge');
  if(pb){pb.style.display=pagamentosVencidos?'':'none';pb.textContent=pagamentosVencidos}
  const totalCount=document.getElementById('total-count');
  if(totalCount) totalCount.textContent=Number(counts.total_registros || clientes.length);
}

// ==================== DASHBOARD ====================
// Soma o valorCobrado dos pagamentos de venda ainda não pagos (mesma lista
// que já alimenta os badges de Pagamentos no sidebar) -- não é um dado novo,
// só a metade que faltava mostrar ao lado do que já foi recebido.
function faturamentoPendenteInfo(alertData){
  const itens = [...alertData.pagamentos.urgentes, ...alertData.pagamentos.normais]
    .filter(p => p.tipoPagamento === 'Venda');
  const total = itens.reduce((s,p) => s + (Number(p.valorCobrado) || 0), 0);
  return { total, count: itens.length };
}

function renderFaturamentoCard(faturamento, alertData){
  const pendente = faturamentoPendenteInfo(alertData);
  const totalEsperado = faturamento + pendente.total;
  const pctRecebido = totalEsperado ? Math.round(faturamento / totalEsperado * 100) : 0;
  const pctPendente = totalEsperado ? 100 - pctRecebido : 0;
  return `
    <div class="metric-card">
      <div class="metric-label">Faturamento Recebido</div>
      <div class="metric-val">${fmtMoney(faturamento)}</div>
      <div class="metric-spacer"></div>
      <div class="fat-legend">
        <div class="fat-leg-item fat-leg-rec"><span class="dot"></span>Recebido<div class="fat-tip">${fmtMoney(faturamento)} · ${pctRecebido}%</div></div>
        <div class="fat-leg-item fat-leg-pend"><span class="dot"></span>Pendente<div class="fat-tip">${fmtMoney(pendente.total)}${pendente.count ? ` · ${pendente.count} cliente${pendente.count>1?'s':''}` : ''}</div></div>
      </div>
      <div class="fat-bar"><div class="fat-bar-rec" style="width:${pctRecebido}%"></div><div class="fat-bar-pend" style="width:${pctPendente}%"></div></div>
    </div>
  `;
}

function renderDashboard(){
  // Total/Emitidos/Renovações vêm da planilha real (Clientes), não do funil de leads local
  const alertData = getAlertData();
  const counts = alertData.counts || {};
  const total = Number(counts.total_registros || 0);
  const emitidos = Number(counts.emitidos || 0);
  const vencendo = Number(counts.vencendo_60_dias || 0);
  const aguardandoEmissao = Math.max(total - emitidos, 0);
  // Mesma fonte dos demais cards (counts, vinda do backend via /alertas/ ou
  // do INITIAL_ALERTS embutido no carregamento inicial) -- assim o card
  // atualiza junto com os outros a cada syncBackendAlertCounts(), em vez de
  // depender de um valor injetado uma única vez no carregamento da página.
  const faturamento = Number(counts.faturamento_recebido || 0);
  // O valor já vem zerado do backend quando sem permissão -- o cadeado aqui
  // é só a forma de comunicar isso na tela, não a proteção em si.
  const podeVerFaturamento = window.IS_ADMIN || window.PERMS.pagamentos;
  const faturamentoCard = podeVerFaturamento
    ? renderFaturamentoCard(faturamento, alertData)
    : `<div class="metric-card locked-feature"><div class="metric-label">Faturamento Recebido</div><div class="metric-val">R$ ••••</div><div class="metric-sub">pagamentos confirmados</div><div class="lock-note"><i class="ti ti-lock"></i>Requer permissão de administrador</div></div>`;

  const pctEmitidos = total ? Math.round(emitidos/total*100) : 0;
  const pctVencendo = total ? Math.round(vencendo/total*100) : 0;
  document.getElementById('dashboard-metrics').innerHTML=`
    <div class="metric-card accent"><div class="metric-label">Total de Clientes</div><div class="metric-val">${total}</div><div class="metric-sub">${aguardandoEmissao} aguardando emissão</div><div class="metric-ratio"><div class="metric-ratio-fill" style="width:${pctEmitidos}%"></div></div></div>
    <div class="metric-card success"><div class="metric-label">Emitidos</div><div class="metric-val">${emitidos}</div><div class="metric-sub">${pctEmitidos}% do total</div><div class="metric-ratio"><div class="metric-ratio-fill" style="width:${pctEmitidos}%"></div></div></div>
    <div class="metric-card warn"><div class="metric-label">Renovações ≤60 dias</div><div class="metric-val">${vencendo}</div><div class="metric-sub">requerem contato</div><div class="metric-ratio"><div class="metric-ratio-fill" style="width:${pctVencendo}%"></div></div></div>
    ${faturamentoCard}
  `;
  const urgentes=[...alertData.renovacoes.urgentes,...alertData.pagamentos.urgentes,...alertData.renovacoes.normais,...alertData.pagamentos.normais]
    .sort((a,b)=>(a.dias??9999)-(b.dias??9999))
    .slice(0,5);
  const al=document.getElementById('dashboard-alerts');
  if(!urgentes.length){al.innerHTML='<p style="font-size:13px;color:var(--muted);text-align:center;padding:20px">Nenhum alerta no momento ✓</p>';}
  else { al.innerHTML=urgentes.map(c=>{
    const kind = c.categoria === 'pagamento' ? 'pagamento' : 'renovacao';
    return renderAlertCard(c, kind);
  }).join(''); }
  const recent=leads.slice().sort((a,b)=>new Date(b.atualizadoEm||0)-new Date(a.atualizadoEm||0)).slice(0,6);
  document.getElementById('dashboard-recent').innerHTML=`<table style="width:100%;border-collapse:collapse">${recent.map(l=>`
    <tr style="border-bottom:1px solid var(--border)">
      <td style="padding:10px 16px;font-size:13px">${escapeHtml(l.nome)}</td>
      <td style="padding:10px 16px">${statusBadge(l.status)}</td>
      <td style="padding:10px 16px;color:var(--muted);font-size:12px">${fmtDateTime(l.atualizadoEm)}</td>
    </tr>`).join('')}</table>`;
  const panel=document.getElementById('dashboard-notificados');
  if(panel){
    panel.innerHTML = notificacoesRecentes.length ? `<table style="width:100%;border-collapse:collapse">${notificacoesRecentes.map(n=>`
      <tr onclick="navigateIfExists('${n.clienteId}', '/planilha/editar/${n.clienteId}/')" style="cursor:pointer;border-bottom:1px solid var(--border)">
        <td style="padding:10px 16px;font-size:13px"><strong>${escapeHtml(n.nome)}</strong></td>
        <td style="padding:10px 16px;color:var(--muted);font-size:12px">${escapeHtml(n.titulo)}${n.texto?` — ${escapeHtml(n.texto)}`:''}</td>
        <td style="padding:10px 16px;color:var(--muted);font-size:12px">${fmtDate(n.data)}</td>
      </tr>`).join('')}</table>` : '<p style="font-size:13px;color:var(--muted);text-align:center;padding:20px">Nenhum cliente notificado ainda.</p>';
  }
}
