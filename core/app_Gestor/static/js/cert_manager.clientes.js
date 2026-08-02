// ==================== CLIENTES ====================
// A tabela "Clientes Cadastrados" (client-side, array local `clientes`) foi
// removida -- hoje existem duas views vindas do Sheets: a Planilha
// (#planilha-tbody, todas as colunas, ver filterPlanilhaImportada) e a
// Clientes (#clientes-simples-tbody, colunas essenciais, ver
// renderClientesSimples). renderClientes() é mantida como no-op porque o
// fluxo antigo do modal rico (saveCliente, registrarContato etc., fora do
// escopo desta migração) ainda a chama após salvar.
function renderClientes(){}

// Decora a célula de status (texto cru vindo do Django) com o badge colorido
// já usado no Kanban -- feito client-side para não precisar marcar a célula
// como |safe no template (as outras colunas são texto livre digitado por
// humanos, então o template evita HTML cru nas células por segurança).
function decoratePlanilhaStatusBadges(){
  document.querySelectorAll('#planilha-tbody td.col-status').forEach(td=>{
    const raw=td.textContent.trim();
    if(td.dataset.decorated===raw) return;
    td.dataset.decorated=raw;
    td.innerHTML=statusBadge(raw==='—'?'':raw);
  });
}

function filterPlanilhaImportada(){
  const statusFilterVal=document.getElementById('filter-status')?.value||'';
  const tbody=document.getElementById('planilha-tbody');
  const table=document.getElementById('planilha-table');
  const noMatch=document.getElementById('planilha-no-match');
  const msg=document.getElementById('planilha-empty-msg');
  if(!tbody||!table) return;
  decoratePlanilhaStatusBadges();
  const dataRows=Array.from(tbody.querySelectorAll('tr'));

  if(!dataRows.length){
    table.style.display='none';
    if(noMatch){ noMatch.style.display=''; }
    if(msg) msg.textContent='Nenhum cliente cadastrado na planilha ainda.';
    updateResultCount('planilha-count', 0, 0);
    renderPaginationControls('planilha-pagination', 1, 1, 'goToPlanilhaPage');
    return;
  }

  const matches=dataRows.filter(row=>{
    const statusCell=row.querySelector('td.col-status');
    return !statusFilterVal||(statusCell?.dataset.decorated===statusFilterVal);
  });

  const totalPages=Math.max(1,Math.ceil(matches.length/ROWS_PER_PAGE));
  if(planilhaPage>totalPages) planilhaPage=totalPages;
  if(planilhaPage<1) planilhaPage=1;
  const pageStart=(planilhaPage-1)*ROWS_PER_PAGE;
  const visiblePage=new Set(matches.slice(pageStart,pageStart+ROWS_PER_PAGE));

  dataRows.forEach(row=>{ row.style.display=visiblePage.has(row)?'':'none'; });

  updateResultCount('planilha-count', matches.length, dataRows.length);
  table.style.display='';
  if(noMatch){
    if(statusFilterVal&&!matches.length){
      noMatch.style.display='';
      if(msg) msg.textContent='Nenhum cliente encontrado para esse filtro.';
    } else {
      noMatch.style.display='none';
    }
  }
  renderPaginationControls('planilha-pagination', planilhaPage, totalPages, 'goToPlanilhaPage');
}
function goToPlanilhaPage(n){planilhaPage=n;filterPlanilhaImportada()}

// ==================== CLIENTES (visão enxuta) ====================
// Diferente da Planilha (server-rendered com todas as colunas), esta tabela
// é montada no cliente a partir de `leads` (mesmos dados do Kanban), só com
// os campos mais usados no dia a dia.

// Filtro de status como chips (mesma cor por etapa que o Kanban usa) --
// o chip ativo assume a própria cor em vez de um azul genérico.
let clientesFiltroStatus='';
function setClientesStatusFiltro(status){
  clientesFiltroStatus=(clientesFiltroStatus===status)?'':status;
  clientesPage=1;
  renderClientesSimples();
  // Escolher (ou limpar) um filtro fecha o painel "Filtrar" -- não faz
  // sentido deixá-lo aberto depois que a pessoa já decidiu o que queria.
  const panel=document.getElementById('filtrar-clientes-panel');
  if(panel) panel.classList.remove('open');
  document.getElementById('filtrar-clientes-toggle')?.setAttribute('aria-expanded','false');
}
function renderFiltroStatusClientes(){
  const badge=document.getElementById('filtrar-clientes-badge');
  if(badge) badge.hidden=!clientesFiltroStatus;
  const el=document.getElementById('filter-status-clientes-chips');
  if(!el) return;
  const bgTokens=['var(--info-bg)','var(--warn-bg)','var(--purple-bg)','var(--teal-bg)','var(--success-bg)'];
  const chip=(status,label,color,bg)=>{
    const active=clientesFiltroStatus===status;
    const style=active?` style="background:${bg};border-color:${bg};color:${color};font-weight:600"`:'';
    const dot=color?`<span class="status-filter-dot" style="background:${color}"></span>`:'';
    return `<button type="button" class="status-filter-chip"${style} onclick="setClientesStatusFiltro('${status.replace(/'/g,"\\'")}')">${dot}${escapeHtml(label)}</button>`;
  };
  el.innerHTML=[
    chip('','Todos',null,null),
    ...STATUS_LIST.map((s,i)=>chip(s,s,KANBAN_COLORS[i],bgTokens[i])),
  ].join('');
}

function renderClientesSimples(){
  renderFiltroStatusClientes();
  const q=normalizeQuery(document.getElementById('search-cliente')?.value);
  const statusFilterVal=clientesFiltroStatus;
  const tbody=document.getElementById('clientes-simples-tbody');
  const table=document.getElementById('clientes-simples-table');
  const noMatch=document.getElementById('clientes-simples-no-match');
  const msg=document.getElementById('clientes-simples-empty-msg');
  if(!tbody||!table) return;

  if(!leads.length){
    table.style.display='none';
    if(noMatch){ noMatch.style.display=''; }
    if(msg) msg.textContent='Nenhum cliente cadastrado na planilha ainda.';
    updateResultCount('clientes-simples-count', 0, 0);
    renderPaginationControls('clientes-simples-pagination', 1, 1, 'goToClientesPage');
    return;
  }

  const matches=leads.filter(l=>{
    const haystack=`${l.nome||''} ${l.telefone||''} ${l.email||''} ${l.cpfCnpj||''}`.toLowerCase();
    const searchOk=!q||haystack.includes(q);
    const statusOk=!statusFilterVal||l.status===statusFilterVal;
    return searchOk&&statusOk;
  });

  const totalPages=Math.max(1,Math.ceil(matches.length/ROWS_PER_PAGE));
  if(clientesPage>totalPages) clientesPage=totalPages;
  if(clientesPage<1) clientesPage=1;
  const pageStart=(clientesPage-1)*ROWS_PER_PAGE;
  const pageItems=matches.slice(pageStart,pageStart+ROWS_PER_PAGE);

  tbody.innerHTML=pageItems.map(l=>`<tr>
    <td>${escapeHtml(l.nome)}</td>
    <td>${escapeHtml(l.telefone)||'—'}</td>
    <td>${statusBadge(l.status)}</td>
    <td>${escapeHtml(l.tipoCert)||'—'}</td>
    <td>${l.dataVencimento?fmtDate(l.dataVencimento):'—'}</td>
    <td>${l.parceiro?escapeHtml(l.parceiro):'—'}</td>
    <td>
      <div class="row-actions">
        <a class="btn btn-sm btn-edit" href="/planilha/editar/${l.id}/" onclick="event.preventDefault(); navigateIfExists('${l.id}', this.href);" title="Editar" aria-label="Editar"><i class="ti ti-pencil"></i></a>
        <button type="button" class="btn btn-sm action-menu-trigger" onclick="openRowActionMenu(event, '${l.id}')" aria-haspopup="true" aria-label="Mais ações"><i class="ti ti-dots-vertical"></i></button>
      </div>
    </td>
  </tr>`).join('');

  updateResultCount('clientes-simples-count', matches.length, leads.length);
  table.style.display='';
  if(noMatch){
    if((q||statusFilterVal)&&!matches.length){
      noMatch.style.display='';
      if(msg) msg.textContent='Nenhum cliente encontrado para essa busca.';
    } else {
      noMatch.style.display='none';
    }
  }
  renderPaginationControls('clientes-simples-pagination', clientesPage, totalPages, 'goToClientesPage');
}
function goToClientesPage(n){clientesPage=n;renderClientesSimples()}

async function deletePlanilhaCliente(id){
  await crudDelete({
    url: `/planilha/${id}/excluir/`,
    confirmMsg: 'Remover este cliente da planilha? Essa ação não pode ser desfeita.',
    successMsg: 'Cliente removido da planilha',
    errorMsg: 'Erro ao remover cliente',
    onSuccess: () => {
      // Volta pra mesma aba de onde a exclusão partiu (Clientes ou Planilha).
      location.hash=(getCurrentViewId()||'view-clientes').replace('view-','');
      location.reload();
    },
  });
}

// O modal local (renderClienteModal) só grava em localStorage, nunca na
// planilha -- a edição real é a página servida por editar_google_row. Esta
// função existe apenas como fallback caso algum ponto futuro volte a chamar
// editCliente(id) diretamente.
function editCliente(id){
  const pk = getPlanilhaPkFromClientId(id);
  if(!pk){
    showToast('Edição disponível apenas para clientes sincronizados da planilha','info');
    return;
  }
  navigateIfExists(pk, `/planilha/editar/${pk}/`);
}
async function deleteCliente(id){
  const ok = await askConfirm('Remover este cliente?', {title:'Remover cliente', confirmLabel:'Remover'});
  if(!ok) return;
  clientes=clientes.filter(c=>c.id!==id); save(); renderClientes(); renderDashboard();
}
