// ==================== TABELA PREÇOS ====================
function renderTabela(){
  document.getElementById('tabela-tbody').innerHTML=precos.map(p=>`<tr>
    <td><strong>${escapeHtml(p.tipo)}</strong></td><td>${escapeHtml(p.validade)}</td><td style="font-weight:700;color:var(--success)">${fmtMoney(p.preco)}</td>
    <td><button class="btn btn-sm" onclick="editPreco('${p.id}')"><i class="ti ti-edit"></i></button> <button class="btn btn-sm btn-danger" onclick="deletePreco('${p.id}')"><i class="ti ti-trash"></i></button></td>
  </tr>`).join('');
}
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
