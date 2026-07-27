// ==================== CLIENTES ====================
// A tabela "Clientes Cadastrados" (client-side, array local `clientes`) foi
// removida -- a view Clientes agora tem só a tabela vinda do Sheets
// (#planilha-tbody, ver filterPlanilhaImportada). renderClientes() é mantida
// como no-op porque o fluxo antigo do modal rico (saveCliente, registrarContato
// etc., fora do escopo desta migração) ainda a chama após salvar.
function renderClientes(){}

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
  const q=normalizeQuery(document.getElementById('search-cliente')?.value);
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

  const cols=getPlanilhaSearchColIndexes();
  const matches=dataRows.filter(row=>{
    const cells=row.querySelectorAll('td');
    const text=cols.map(i=>cells[i]?.textContent||'').join(' ').toLowerCase();
    const searchOk=!q||text.includes(q);
    const statusCell=row.querySelector('td.col-status');
    const statusOk=!statusFilterVal||(statusCell?.dataset.decorated===statusFilterVal);
    return searchOk&&statusOk;
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
    if(q&&!matches.length){
      noMatch.style.display='';
      if(msg) msg.textContent='Nenhum cliente encontrado para essa busca.';
    } else {
      noMatch.style.display='none';
    }
  }
  renderPaginationControls('planilha-pagination', planilhaPage, totalPages, 'goToPlanilhaPage');
}
function goToPlanilhaPage(n){planilhaPage=n;filterPlanilhaImportada()}

async function deletePlanilhaCliente(id){
  await crudDelete({
    url: `/planilha/${id}/excluir/`,
    confirmMsg: 'Remover este cliente da planilha? Essa ação não pode ser desfeita.',
    successMsg: 'Cliente removido da planilha',
    errorMsg: 'Erro ao remover cliente',
    onSuccess: () => { location.hash='clientes'; location.reload(); },
  });
}

function editCliente(id){editingId=id;openModal('cliente')}
function deleteCliente(id){if(confirm('Remover este cliente?')){clientes=clientes.filter(c=>c.id!==id);save();renderClientes();renderDashboard()}}
