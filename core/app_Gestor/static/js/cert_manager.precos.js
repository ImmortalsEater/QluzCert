// ==================== TABELA PREÇOS ====================
function renderTabela(){
  const grid=document.getElementById('precos-grid');
  const empty=document.getElementById('precos-empty');
  if(!precos.length){grid.innerHTML='';empty.style.display='';return}
  empty.style.display='none';
  grid.innerHTML=precos.map(p=>`<div class="preco-card">
    <div class="preco-tipo">${escapeHtml(p.tipo)}</div>
    <div>
      <div class="preco-price-label">Preço</div>
      <span class="preco-price-wrap"><span class="preco-price">${fmtMoney(p.preco)}</span><span class="preco-underline"></span></span>
    </div>
    <span class="preco-validade"><i class="ti ti-calendar" aria-hidden="true"></i>Validade <b>${escapeHtml(p.validade)}</b></span>
    <div class="preco-card-foot">
      <span class="preco-meta">Atualizado em ${fmtDate(p.atualizadoEm)}</span>
      <button type="button" class="btn btn-sm action-menu-trigger" onclick="openPrecoActionMenu(event, '${p.id}')" aria-haspopup="true" aria-label="Mais ações"><i class="ti ti-dots-vertical" aria-hidden="true"></i></button>
    </div>
  </div>`).join('');
}

// Menu "⋮" do card de Preço -- mesmo padrão do #parceiro-action-menu.
function closePrecoActionMenu(){
  const menu = document.getElementById('preco-action-menu');
  if(!menu) return;
  menu.classList.remove('open');
  menu.dataset.forId = '';
}

function openPrecoActionMenu(e, id){
  e.stopPropagation();
  const menu = document.getElementById('preco-action-menu');
  if(!menu) return;
  const wasOpenForThisCard = menu.classList.contains('open') && menu.dataset.forId === id;
  closePrecoActionMenu();
  if(typeof closeActionMenu === 'function') closeActionMenu();
  if(typeof closeKanbanStatusMenu === 'function') closeKanbanStatusMenu();
  if(typeof closeParceiroActionMenu === 'function') closeParceiroActionMenu();
  document.getElementById('column-selector-panel')?.classList.remove('open');
  document.getElementById('save-menu')?.classList.remove('open');
  document.getElementById('user-menu-panel')?.classList.remove('open');
  document.getElementById('filtrar-clientes-panel')?.classList.remove('open');
  document.getElementById('filtrar-planilha-panel')?.classList.remove('open');
  if(wasOpenForThisCard) return;

  menu.dataset.forId = id;
  menu.innerHTML = `
    <button type="button" class="action-menu-item" role="menuitem" onclick="closePrecoActionMenu(); editPreco('${id}')"><i class="ti ti-edit"></i>Editar</button>
    <div class="action-menu-divider"></div>
    <button type="button" class="action-menu-item action-menu-item-danger" role="menuitem" onclick="closePrecoActionMenu(); deletePreco('${id}')"><i class="ti ti-trash"></i>Excluir</button>
  `;

  const btn = e.currentTarget;
  const rect = btn.getBoundingClientRect();
  menu.classList.add('open');
  const menuRect = menu.getBoundingClientRect();
  let top = rect.bottom + 6;
  let left = rect.right - menuRect.width;
  if(left < 8) left = 8;
  if(top + menuRect.height > window.innerHeight - 8){ top = rect.top - menuRect.height - 6; }
  menu.style.top = top + 'px';
  menu.style.left = left + 'px';
}

document.addEventListener('click', closePrecoActionMenu);
document.addEventListener('scroll', closePrecoActionMenu, true);
window.addEventListener('resize', closePrecoActionMenu);

function editPreco(id){editingId=id;openModal('preco')}
async function deletePreco(id){
  await crudDelete({
    url: `/preco/excluir/${id}/`,
    confirmMsg: 'Remover?',
    successMsg: 'Preço removido',
    errorMsg: 'Erro ao remover preço',
    onSuccess: () => { precos = precos.filter(p=>p.id!==id); renderTabela(); },
  });
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

async function savePreco(){
  const tipo=document.getElementById('pr-tipo').value.trim();
  if(!tipo){alert('Tipo obrigatório');return}
  const atual=editingId?precos.find(p=>p.id===editingId):null;
  const payload=new URLSearchParams({
    tipo,
    validade:document.getElementById('pr-valid').value,
    preco:document.getElementById('pr-preco').value,
    expected_atualizado_em: atual?.atualizadoEm || '',
  });
  await crudSave({
    editingId,
    createUrl: '/preco/criar/',
    editUrlFn: id => `/preco/editar/${id}/`,
    payload,
    successMsg: 'Preço salvo com sucesso',
    errorMsg: 'Erro ao salvar preço',
    onSuccess: () => {
      closeModal(true);
      editingId=null;
      location.hash='tabela';
      setTimeout(()=>{ location.reload(); },600);
    },
  });
}
