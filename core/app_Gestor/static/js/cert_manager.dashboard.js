const PAGE_CONFIG = {
  dashboard:{title:'Dashboard', render:renderDashboard},
  clientes:{title:'Clientes', render:filterPlanilhaImportada},
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
      <button class="btn btn-quaternary" id="atualizar-planilha-btn" onclick="atualizarPlanilha()"><i class="ti ti-refresh"></i>Atualizar agora</button>
      <div class="save-dropdown" style="position:relative;display:inline-block">
        <button class="btn btn-sm btn-quaternary-soft" id="save-main-btn"><i class="ti ti-device-floppy"></i> Salvar <i class="ti ti-chevron-down" style="margin-left:6px;font-size:12px"></i></button>
        <div id="save-menu" style="position:absolute;right:0;top:36px;background:var(--surface);border:1px solid var(--border);border-radius:6px;box-shadow:0 6px 18px rgba(0,0,0,0.06);display:none;min-width:180px;padding:8px;z-index:60">
          <button class="btn" style="display:block;width:100%;text-align:left;padding:8px;border-radius:6px" id="save-local-btn">Salvar localmente</button>
          <button class="btn" style="display:block;width:100%;text-align:left;padding:8px;border-radius:6px;margin-top:6px" id="export-btn">Exportar (.xlsx)</button>
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
  // Total/Emitidos/Renovações vêm da planilha real (Clientes), não do funil de leads local
  const alertData = getAlertData();
  const counts = alertData.counts || {};
  const total = Number(counts.total_registros || 0);
  const emitidos = Number(counts.emitidos || 0);
  const vencendo = Number(counts.vencendo_60_dias || 0);
  const aguardandoEmissao = Math.max(total - emitidos, 0);
 // Lê o valor processado pelo Django na tabela. Se não existir, faz a soma local.
  const faturamento = (typeof window !== 'undefined' && window.INITIAL_FATURAMENTO !== undefined)
    ? Number(window.INITIAL_FATURAMENTO)
    : clientes.filter(c=>c.pago).reduce((s,c)=>s+(parseFloat(c.valorCobrado)||0),0);

  document.getElementById('dashboard-metrics').innerHTML=`
    <div class="metric-card accent"><div class="metric-label">Total de Clientes</div><div class="metric-val">${total}</div><div class="metric-sub">${aguardandoEmissao} aguardando emissão</div></div>
    <div class="metric-card success"><div class="metric-label">Emitidos</div><div class="metric-val">${emitidos}</div><div class="metric-sub">${Math.round(total?emitidos/total*100:0)}% do total</div></div>
    <div class="metric-card warn"><div class="metric-label">Renovações ≤60 dias</div><div class="metric-val">${vencendo}</div><div class="metric-sub">requerem contato</div></div>
    <div class="metric-card"><div class="metric-label">Faturamento Recebido</div><div class="metric-val" style="font-size:18px">${fmtMoney(faturamento)}</div><div class="metric-sub">pagamentos confirmados</div></div>
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
      <td style="padding:10px 16px;color:var(--muted);font-size:12px">${fmtDate(l.atualizadoEm)}</td>
    </tr>`).join('')}</table>`;
  const panel=document.getElementById('dashboard-notificados');
  if(panel){
    panel.innerHTML = notificacoesRecentes.length ? `<table style="width:100%;border-collapse:collapse">${notificacoesRecentes.map(n=>`
      <tr onclick="location.href='/planilha/editar/${n.clienteId}/'" style="cursor:pointer;border-bottom:1px solid var(--border)">
        <td style="padding:10px 16px;font-size:13px"><strong>${escapeHtml(n.nome)}</strong></td>
        <td style="padding:10px 16px;color:var(--muted);font-size:12px">${escapeHtml(n.titulo)}${n.texto?` — ${escapeHtml(n.texto)}`:''}</td>
        <td style="padding:10px 16px;color:var(--muted);font-size:12px">${fmtDate(n.data)}</td>
      </tr>`).join('')}</table>` : '<p style="font-size:13px;color:var(--muted);text-align:center;padding:20px">Nenhum cliente notificado ainda.</p>';
  }
}
