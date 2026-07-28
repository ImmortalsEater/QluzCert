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
  markModalFieldsPristine(box);
  const firstField=box.querySelector('input,select,textarea')||box.querySelector('button');
  if(firstField)firstField.focus();
}

// Grava o valor/estado inicial de cada campo do modal em data-attributes,
// para que isFormDirty() consiga detectar alterações reais do usuário em
// vez de comparar contra string vazia (o que marcaria qualquer edição
// pré-preenchida como "suja" assim que o modal abre).
function markModalFieldsPristine(container){
  container.querySelectorAll('input, select, textarea').forEach(el=>{
    if(el.type === 'checkbox' || el.type === 'radio'){ el.dataset.initialChecked = String(el.checked); }
    else { el.dataset.initialValue = el.value || ''; }
  });
}
function isFormDirty(containerSelector){
  const box = document.querySelector(containerSelector);
  if(!box) return false;
  const fields = box.querySelectorAll('input, select, textarea');
  for(const el of fields){
    if(el.type === 'checkbox' || el.type === 'radio'){
      if(el.dataset.initialChecked !== undefined && el.checked !== (el.dataset.initialChecked === 'true')) return true;
      continue;
    }
    if((el.value || '').trim() !== (el.dataset.initialValue || '').trim()) return true;
  }
  return false;
}

async function closeModal(e){
  const overlay = document.getElementById('modal-overlay');
  const isBackdropClick = e && e.target === overlay;
  if(e !== true && !isBackdropClick) return;
  if(isBackdropClick && isFormDirty('#modal-box')){
    const ok = await askConfirm('Existem alterações não salvas neste formulário. Deseja descartá-las?', {title:'Descartar alterações?', confirmLabel:'Descartar', danger:true});
    if(!ok) return;
  }
  overlay.classList.remove('open');
  editingId=null;
  if(modalTriggerEl&&typeof modalTriggerEl.focus==='function')modalTriggerEl.focus();
  modalTriggerEl=null;
}
function handleModalKeydown(e){
  const confirmOverlay=document.getElementById('confirm-overlay');
  if(confirmOverlay&&confirmOverlay.classList.contains('open')){
    if(e.key==='Escape'){_resolveConfirm(false)}
    return;
  }
  const detailOverlay=document.getElementById('detail-overlay');
  if(detailOverlay&&detailOverlay.classList.contains('open')){
    if(e.key==='Escape'){closeDetail(true)}
    return;
  }
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
  const hasPlanilhaId = !!getPlanilhaPkFromClientId(c.id || editingId);
  box.innerHTML=`
  <div class="modal-head">
    <div>
      <h2 id="modal-dialog-title">${editingId?'Editar Cliente':'Novo Cliente'}</h2>
      <div style="font-size:12px;color:var(--muted);margin-top:3px">Cadastro, documentos e pagamento no mesmo fluxo</div>
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
    </div>
    <div id="tab-dados" class="tab-pane">
      <div class="form-grid">
        <div class="field form-full"><label>Nome Completo *</label><input id="f-nome" value="${c.nome||''}" placeholder="Nome do cliente"></div>
        <div class="field"><label>CPF / CNPJ</label><input id="f-cpfcnpj" value="${c.cpfCnpj||''}" placeholder="000.000.000-00"></div>
        <div class="field"><label>Data de Nascimento</label><input id="f-nasc" type="date" value="${c.dataNasc||''}"></div>
        <div class="field"><label>Telefone / WhatsApp</label><input id="f-tel" value="${c.telefone||''}" placeholder="(00) 00000-0000"></div>
        <div class="field"><label>E-mail</label><input id="f-email" value="${c.email||''}" placeholder="email@exemplo.com"></div>
        <div class="field form-full"><label>Parceiro / Indicação</label><select id="f-parceiro"><option value="">Nenhum (direto)</option>${pOpts}</select></div>
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
          <div class="field"><label for="ng-parceiro">Contador/Parceiro</label>
            <select id="ng-parceiro" name="contador_parceiro">
              <option value="">Nenhum / Direto</option>
              ${parceiros.map(p=>`<option value="${escapeHtml(p.nome)}">${escapeHtml(p.nome)}</option>`).join('')}
            </select>
          </div>
          <div class="field"><label for="ng-contabilidade">Contador/Contabilidade</label><input id="ng-contabilidade" name="contador_contabilidade" autocomplete="off"></div>
        </div>
      </fieldset>
      <fieldset class="modal-fieldset">
        <legend>Certificado &amp; Venda</legend>
        <div class="form-grid">
          <div class="field"><label for="ng-tipo">Tipo de Certificado</label>
            <select id="ng-tipo" name="tipo_certificado">
              <option value="">Selecione...</option>
              ${precos.map(p=>`<option value="${escapeHtml(p.tipo)}" data-validade="${escapeHtml(p.validade||'')}">${escapeHtml(p.tipo)} — ${p.preco!=null?fmtMoney(p.preco):'—'}</option>`).join('')}
            </select>
          </div>
          <div class="field"><label for="ng-datavenda">Data da Venda</label><input id="ng-datavenda" name="data_venda" type="date"></div>
          <div class="field"><label for="ng-datavenc">Data de Vencimento</label><input id="ng-datavenc" name="data_vencimento" type="date" readonly></div>
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
  document.getElementById('ng-cpfcnpj').addEventListener('input', function(){ this.value = maskCpfCnpj(this.value); });
  document.getElementById('ng-tel1').addEventListener('input', function(){ this.value = maskTelefone(this.value); });
  document.getElementById('ng-tel2').addEventListener('input', function(){ this.value = maskTelefone(this.value); });
  function _recalcularVencimentoNovoCliente(){
    const tipoSel = document.getElementById('ng-tipo');
    const dataVenda = document.getElementById('ng-datavenda').value;
    const vencInput = document.getElementById('ng-datavenc');
    if(!dataVenda){ vencInput.value=''; return; }
    const opt = tipoSel.options[tipoSel.selectedIndex];
    const dias = parseValidadeToDays(opt && opt.dataset.validade) ?? 365;
    vencInput.value = addDays(dataVenda, dias);
  }
  document.getElementById('ng-tipo').addEventListener('change', _recalcularVencimentoNovoCliente);
  document.getElementById('ng-datavenda').addEventListener('change', _recalcularVencimentoNovoCliente);
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
  c.status=document.getElementById('f-status').value;
  c.obs=document.getElementById('f-obs').value;
  c.tipoCert=document.getElementById('f-tipo').value;
  c.dataEmissao=document.getElementById('f-emissao').value;
  c.dataVencimento=document.getElementById('f-venc').value;
  c.valorCobrado=parseFloat(document.getElementById('f-valor').value)||0;
  c.formaPag=document.getElementById('f-pagform').value;
  c.pago=document.getElementById('f-pago').value==='true';
  if(!editingId)clientes.unshift(c);
  save();closeModal(true);renderClientes();renderDashboard();renderKanban();
  editingId=null;
}

// ==================== DETAIL ====================
// Modal de detalhe do card do Kanban, com edição inline. Opera sobre `leads`
// (dados ao vivo do Sheets), não sobre o antigo array `clientes` local -- os
// campos disponíveis são só os que _build_clientes_leads_from_sheets expõe;
// dados financeiros/documentos completos ficam no link "Ver cadastro completo".
let detailEditMode = false;

function openDetail(id){
  const lead = leads.find(l => String(l.id) === String(id));
  if(!lead){ showToast('Registro não encontrado', 'error'); return; }
  detailEditMode = false;
  renderDetailView(lead);
  document.getElementById('detail-overlay').classList.add('open');
}

function renderDetailView(lead){
  const box = document.getElementById('detail-box');
  const si = STATUS_LIST.indexOf(lead.status);
  const steps = STATUS_LIST.map((s,i)=>`<div class="step${i<si?' done':i===si?' current':''}">${escapeHtml(s)}</div>`).join('');
  box.innerHTML = `
  <div class="modal-head">
    <div>
      <h2 id="modal-dialog-title">${escapeHtml(lead.nome)}</h2>
      <div style="font-size:12px;color:var(--muted);margin-top:2px">Atualizado em ${fmtDateTime(lead.atualizadoEm)}</div>
    </div>
    <div style="display:flex;gap:8px">
      <button class="btn btn-sm" onclick="enterDetailEditMode('${lead.id}')"><i class="ti ti-edit"></i> Editar</button>
      <button class="btn btn-sm" onclick="closeDetail(true)" aria-label="Fechar"><i class="ti ti-x" aria-hidden="true"></i></button>
    </div>
  </div>
  <div class="modal-body">
    <div class="progress-steps">${steps}</div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px">
      <div class="detail-section">
        <h4>Dados Pessoais</h4>
        <div class="detail-row"><span class="lbl">Telefone</span><span class="val">${escapeHtml(lead.telefone)||'—'}</span></div>
        <div class="detail-row"><span class="lbl">E-mail</span><span class="val">${escapeHtml(lead.email)||'—'}</span></div>
        <div class="detail-row"><span class="lbl">Parceiro</span><span class="val">${lead.parceiro?escapeHtml(lead.parceiro):'Sem parceiro'}</span></div>
      </div>
      <div class="detail-section">
        <h4>Certificado</h4>
        <div class="detail-row"><span class="lbl">Tipo</span><span class="val">${escapeHtml(lead.tipoCert)||'—'}</span></div>
        <div class="detail-row"><span class="lbl">Vencimento</span><span class="val">${lead.dataVencimento?fmtDate(lead.dataVencimento):'—'}</span></div>
        <div class="detail-row"><span class="lbl">Pagamento</span><span class="val" style="color:${lead.pago?'var(--success)':'var(--danger)'}">${lead.pago?'Confirmado':'Pendente'}</span></div>
      </div>
    </div>
  </div>
  <div class="modal-foot">
    <button class="btn" onclick="closeDetail(true)">Fechar</button>
    <a class="btn" href="/planilha/editar/${lead.id}/" onclick="event.preventDefault(); navigateIfExists('${lead.id}', this.href);">Ver cadastro completo</a>
  </div>`;
  markModalFieldsPristine(box);
}

function enterDetailEditMode(id){
  const lead = leads.find(l => String(l.id) === String(id));
  if(!lead) return;
  detailEditMode = true;
  const box = document.getElementById('detail-box');
  box.innerHTML = `
  <div class="modal-head">
    <h2 id="modal-dialog-title">Editar: ${escapeHtml(lead.nome)}</h2>
    <button class="btn btn-sm" onclick="closeDetail(true)" aria-label="Fechar"><i class="ti ti-x" aria-hidden="true"></i></button>
  </div>
  <div class="modal-body">
    <div class="form-grid">
      <div class="field form-full"><label for="de-nome">Nome</label><input id="de-nome" value="${escapeHtml(lead.nome)}"></div>
      <div class="field"><label for="de-telefone">Telefone</label><input id="de-telefone" value="${escapeHtml(lead.telefone)}"></div>
      <div class="field"><label for="de-email">E-mail</label><input id="de-email" value="${escapeHtml(lead.email)}"></div>
      <div class="field"><label for="de-parceiro">Parceiro</label>
        <select id="de-parceiro"><option value="">Nenhum</option>
          ${parceiros.map(p=>`<option value="${escapeHtml(p.nome)}"${lead.parceiro===p.nome?' selected':''}>${escapeHtml(p.nome)}</option>`).join('')}
        </select>
      </div>
      <div class="field"><label for="de-tipo">Tipo de Certificado</label>
        <select id="de-tipo"><option value="">Selecione...</option>
          ${precos.map(p=>`<option value="${escapeHtml(p.tipo)}"${lead.tipoCert===p.tipo?' selected':''}>${escapeHtml(p.tipo)}</option>`).join('')}
        </select>
      </div>
      <div class="field"><label for="de-venc">Data de Vencimento</label><input id="de-venc" type="date" value="${lead.dataVencimento||''}"></div>
    </div>
  </div>
  <div class="modal-foot">
    <button class="btn" onclick="renderDetailView(leads.find(l=>String(l.id)==='${lead.id}'))">Cancelar</button>
    <button class="btn btn-primary" id="de-save-btn" onclick="saveDetailInline('${lead.id}')"><i class="ti ti-device-floppy"></i> Salvar</button>
  </div>`;
  markModalFieldsPristine(box);
}

async function saveDetailInline(id){
  const lead = leads.find(l => String(l.id) === String(id));
  const btn = document.getElementById('de-save-btn');
  const payload = new URLSearchParams({
    cliente: document.getElementById('de-nome').value.trim(),
    telefone1: document.getElementById('de-telefone').value,
    email: document.getElementById('de-email').value,
    contador_parceiro: document.getElementById('de-parceiro').value,
    tipo_certificado: document.getElementById('de-tipo').value,
    data_vencimento: document.getElementById('de-venc').value,
    expected_atualizado_em: lead?.atualizadoEm || '',
  });
  if(btn) btn.disabled = true;
  try{
    const data = await apiFetch(`/planilha/${id}/detalhe/`, {
      method: 'POST',
      headers: {'Content-Type': 'application/x-www-form-urlencoded'},
      body: payload.toString(),
      errorMessage: 'Falha ao salvar alterações',
    });
    Object.assign(lead, {
      nome: payload.get('cliente'), telefone: payload.get('telefone1'), email: payload.get('email'),
      parceiro: payload.get('contador_parceiro'), tipoCert: payload.get('tipo_certificado'),
      dataVencimento: payload.get('data_vencimento'), atualizadoEm: data.atualizado_em,
    });
    showToast('Cliente atualizado', 'success');
    detailEditMode = false;
    renderDetailView(lead);
    renderKanban();
  }catch(err){
    showToast(err.message || 'Erro ao salvar', 'error');
  }finally{
    if(btn) btn.disabled = false;
  }
}

async function closeDetail(e){
  const overlay = document.getElementById('detail-overlay');
  const isBackdropClick = e && e.target === overlay;
  if(e !== true && !isBackdropClick) return;
  if(isBackdropClick && detailEditMode && isFormDirty('#detail-box')){
    const ok = await askConfirm('Existem alterações não salvas. Deseja descartá-las?', {title:'Descartar alterações?', confirmLabel:'Descartar', danger:true});
    if(!ok) return;
  }
  overlay.classList.remove('open');
  detailEditMode = false;
}
