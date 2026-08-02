// ==================== PARCEIROS ====================
const PARCEIRO_TIPO_COLOR={
  'Contador':'var(--accent)',
  'Advogado':'var(--secondary)',
  'Escritório':'var(--tertiary)',
  'Correspondente':'var(--quaternary)',
};
function parceiroTipoColor(tipo){return PARCEIRO_TIPO_COLOR[tipo]||'var(--muted-strong)'}
function parceiroIniciais(nome){
  const palavras=(nome||'').trim().split(/\s+/).filter(Boolean);
  if(!palavras.length) return '?';
  if(palavras.length===1) return palavras[0].slice(0,2).toUpperCase();
  return (palavras[0][0]+palavras[1][0]).toUpperCase();
}
function renderParceiros(){
  const grid=document.getElementById('parceiros-grid');
  const empty=document.getElementById('parceiros-empty');
  if(!parceiros.length){grid.innerHTML='';empty.style.display='';return}
  empty.style.display='none';
  grid.innerHTML=parceiros.map(p=>{
    // Clientes vinculam parceiro pelo nome (contador_parceiro, vindo da
    // planilha) em `leads`, não por um parceiroId no array local legado
    // `clientes` (que não é mais populado desde a migração para o Sheets).
    const indicados=leads.filter(l=>l.parceiro===p.nome);
    const count=indicados.length;
    const cor=parceiroTipoColor(p.tipo);
    const porStatus=STATUS_LIST.map((s,i)=>({
      status:s, cor:KANBAN_COLORS[i],
      n:indicados.filter(l=>l.status===s).length,
    })).filter(x=>x.n>0);
    const emitidoPct=count?Math.round((indicados.filter(l=>l.status==='Emitido').length/count)*100):0;

    const barra = count ? `
      <div class="parceiro-bar-label"><span>${count} indicaç${count===1?'ão':'ões'}</span><span class="val">${emitidoPct}% emitido</span></div>
      <div class="parceiro-compbar">${porStatus.map(x=>`<span style="width:${(x.n/count*100)}%;background:${x.cor}"></span>`).join('')}</div>
      <div class="parceiro-legend">${porStatus.map(x=>`<span class="parceiro-legend-item"><span class="dot" style="background:${x.cor}"></span>${escapeHtml(x.status)} <b>${x.n}</b></span>`).join('')}</div>
    ` : `<p class="parceiro-sem-indicacao">Nenhuma indicação ainda</p>`;

    return`<div class="parceiro-card">
      <div class="parceiro-card-head">
        <span class="parceiro-eyebrow">Parceiro</span>
        ${p.contato?`<span class="parceiro-contato-pill">Contato: ${escapeHtml(p.contato)}</span>`:''}
      </div>
      <div class="parceiro-card-body">
        <div class="parceiro-card-top">
          <span class="parceiro-avatar" style="background:${cor}">${parceiroIniciais(p.nome)}</span>
          <div>
            <div class="parceiro-nome">${escapeHtml(p.nome)}</div>
            <div class="parceiro-tipo">${escapeHtml(p.tipo)||'—'}${p.comissao!=null?` · ${fmtPercent(p.comissao)} comissão`:''}</div>
          </div>
        </div>
        ${barra}
      </div>
      <div class="parceiro-card-foot">
        <span class="parceiro-meta">Atualizado em ${fmtDate(p.atualizadoEm)}</span>
        <button type="button" class="btn btn-sm action-menu-trigger" onclick="openParceiroActionMenu(event, '${p.id}')" aria-haspopup="true" aria-label="Mais ações"><i class="ti ti-dots-vertical" aria-hidden="true"></i></button>
      </div>
    </div>`;
  }).join('');
}

// Menu "⋮" do card de Parceiro (Editar/Excluir) -- mesmo padrão do
// #action-menu-dropdown de Clientes e do #kanban-status-menu: elemento
// único reaproveitado por todos os cards, position:fixed calculado em JS.
function closeParceiroActionMenu(){
  const menu = document.getElementById('parceiro-action-menu');
  if(!menu) return;
  menu.classList.remove('open');
  menu.dataset.forId = '';
}

function openParceiroActionMenu(e, id){
  e.stopPropagation();
  const menu = document.getElementById('parceiro-action-menu');
  if(!menu) return;
  const wasOpenForThisCard = menu.classList.contains('open') && menu.dataset.forId === id;
  closeParceiroActionMenu();
  if(typeof closeActionMenu === 'function') closeActionMenu();
  if(typeof closeKanbanStatusMenu === 'function') closeKanbanStatusMenu();
  document.getElementById('column-selector-panel')?.classList.remove('open');
  document.getElementById('save-menu')?.classList.remove('open');
  document.getElementById('user-menu-panel')?.classList.remove('open');
  document.getElementById('filtrar-clientes-panel')?.classList.remove('open');
  if(wasOpenForThisCard) return;

  menu.dataset.forId = id;
  menu.innerHTML = `
    <button type="button" class="action-menu-item" role="menuitem" onclick="closeParceiroActionMenu(); editParceiro('${id}')"><i class="ti ti-edit"></i>Editar</button>
    <div class="action-menu-divider"></div>
    <button type="button" class="action-menu-item action-menu-item-danger" role="menuitem" onclick="closeParceiroActionMenu(); deleteParceiro('${id}')"><i class="ti ti-trash"></i>Excluir</button>
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

document.addEventListener('click', closeParceiroActionMenu);
document.addEventListener('scroll', closeParceiroActionMenu, true);
window.addEventListener('resize', closeParceiroActionMenu);

function editParceiro(id){editingId=id;openModal('parceiro')}
async function deleteParceiro(id){
  await crudDelete({
    url: `/parceiro/excluir/${id}/`,
    confirmMsg: 'Remover parceiro?',
    successMsg: 'Parceiro removido',
    errorMsg: 'Erro ao remover parceiro',
    onSuccess: () => { parceiros = parceiros.filter(p=>p.id!==id); renderParceiros(); },
  });
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

async function saveParceiro(){
  const nome=document.getElementById('p-nome').value.trim();
  if(!nome){alert('Nome obrigatório');return}
  const atual=editingId?parceiros.find(p=>p.id===editingId):null;
  const payload=new URLSearchParams({
    nome,
    tipo:document.getElementById('p-tipo').value,
    telefone:document.getElementById('p-tel').value,
    email:document.getElementById('p-email').value,
    comissao:document.getElementById('p-comissao').value,
    contato:document.getElementById('p-contato').value,
    expected_atualizado_em: atual?.atualizadoEm || '',
  });
  await crudSave({
    editingId,
    createUrl: '/parceiro/criar/',
    editUrlFn: id => `/parceiro/editar/${id}/`,
    payload,
    successMsg: 'Parceiro salvo com sucesso',
    errorMsg: 'Erro ao salvar parceiro',
    onSuccess: () => {
      closeModal(true);
      editingId=null;
      location.hash='parceiros';
      setTimeout(()=>{ location.reload(); },600);
    },
  });
}
