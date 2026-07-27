// ==================== PARCEIROS ====================
function renderParceiros(){
  const tbody=document.getElementById('parceiros-tbody');
  const empty=document.getElementById('parceiros-empty');
  if(!parceiros.length){tbody.innerHTML='';empty.style.display='';return}
  empty.style.display='none';
  tbody.innerHTML=parceiros.map(p=>{
    const count=clientes.filter(c=>c.parceiroId===p.id).length;
    return`<tr><td><strong>${escapeHtml(p.nome)}</strong></td><td>${escapeHtml(p.tipo)||'—'}</td><td>${p.comissao!=null?fmtPercent(p.comissao):'—'}</td><td>${escapeHtml(p.contato)||'—'}</td><td><span style="font-size:13px;font-weight:700;color:var(--accent)">${count}</span></td>
    <td><button class="btn btn-sm" onclick="editParceiro('${p.id}')"><i class="ti ti-edit"></i></button> <button class="btn btn-sm btn-danger" onclick="deleteParceiro('${p.id}')"><i class="ti ti-trash"></i></button></td></tr>`;
  }).join('');
}
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
      setTimeout(()=>{ location.reload(); },600);
    },
  });
}
