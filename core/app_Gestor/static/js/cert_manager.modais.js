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
// A visão de detalhe local (renderizada a partir do array `clientes`/
// localStorage) foi substituída pela página real de edição (editar_google_row),
// que já mostra e edita todos os campos vindos da planilha. Esta função existe
// apenas como fallback caso algum ponto futuro volte a chamar openDetail(id)
// diretamente.
function openDetail(id){
  const pk = getPlanilhaPkFromClientId(id);
  if(!pk){
    showToast('Detalhes disponíveis apenas para clientes sincronizados da planilha','info');
    return;
  }
  location.href = `/planilha/editar/${pk}/`;
}
function closeDetail(e){if(e===true||e.target===document.getElementById('detail-overlay')){document.getElementById('detail-overlay').classList.remove('open')}}
