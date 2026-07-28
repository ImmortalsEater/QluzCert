function renderPagamentoModal(box, cid) {
  let c = resolveClienteById(cid || editingId);
  if (!c) {
      const alertData = getAlertData();
      const allAlerts = [...alertData.renovacoes.urgentes, ...alertData.renovacoes.normais, ...alertData.pagamentos.urgentes, ...alertData.pagamentos.normais];
      const alertItem = allAlerts.find(x => String(x.id) === String(cid));
      if (alertItem) {
          c = {
              id: cid,
              nome: alertItem.nome,
              tipoCert: alertItem.tipoCert,
              valorCobrado: alertItem.valorCobrado || 0,
              dataVencimento: alertItem.dataVencimento || '',
              pago: alertItem.pago || false,
              formaPag: 'Pix',
              historico: [],
              notificacoes: []
          };
      } else {
          box.innerHTML = `<div class="modal-head"><h2>Pagamento</h2><button class="btn btn-sm" onclick="closeModal(true)"><i class="ti ti-x"></i></button></div><div class="modal-body"><p style="font-size:13px;color:var(--muted)">Selecione um cliente válido antes de registrar um pagamento.</p></div>`;
          return;
      }
  }

  const histHTML = (c.historico || []).slice().reverse().map(h => `
    <div style="padding: 14px; border-bottom: 1px solid var(--border); font-size: 13px;">
        <div style="display:flex; justify-content:space-between; margin-bottom:6px;">
            <strong><i class="ti ti-calendar"></i> ${fmtDate(h.data)} — ${h.canal || 'Pagamento'}</strong>
            <span class="badge ${c.pago ? 'badge-emitido' : 'badge-pag'}">${h.obs ? h.obs.split('·')[0] : 'Atualizado'}</span>
        </div>
        <div style="background: var(--bg); padding: 10px; border-radius: 6px;">${h.obs || 'Nenhuma observação informada.'}</div>
    </div>`).join('') || '<div class="empty-state"><i class="ti ti-receipt-off"></i><p>Nenhum histórico de pagamento registrado.</p></div>';

  box.innerHTML = `
  <div class="modal-head">
    <h2><i class="ti ti-cash"></i> Gestão de Pagamento — ${escapeHtml(c.nome) || 'Cliente'}</h2>
    <button class="btn btn-sm" onclick="closeModal(true)"><i class="ti ti-x"></i></button>
  </div>
  <div class="modal-body" style="padding: 0;">

    <!-- Abas -->
    <div class="tabs" style="padding: 14px 20px 0 20px; background: var(--surface-alt); border-bottom: 1px solid var(--border); margin-bottom:0;">
      <div class="tab active" onclick="switchTab(this,'tab-reg-pagamento')">Registrar Pagamento</div>
      <div class="tab" onclick="switchTab(this,'tab-hist-pagamento')">Visualizar Histórico</div>
    </div>

    <!-- Aba de Formulário -->
    <div id="tab-reg-pagamento" class="tab-pane" style="padding: 20px;">
        <div style="background: var(--bg); padding: 12px; border-radius: 8px; margin-bottom: 20px; font-size: 13px; display:flex; justify-content:space-between; align-items:center;">
            <div><strong>Cliente:</strong> <br><span style="color:var(--accent)">${escapeHtml(c.nome) || '—'}</span></div>
            <div><strong>Status Atual:</strong> <br><span style="color:${c.pago ? 'var(--success)' : 'var(--danger)'}">${c.pago ? '✓ Confirmado' : '⚠ Pendente'}</span></div>
        </div>

        <div class="form-grid">
          <div class="field"><label>Valor (R$)</label><input id="pg-valor" type="number" step="0.01" value="${c.valorCobrado || ''}" placeholder="0,00"></div>
          <div class="field"><label>Status do Pagamento</label><select id="pg-status"><option value="Pendente"${!c.pago?' selected':''}>Pendente</option><option value="Pago"${c.pago?' selected':''}>Pago / Confirmado</option></select></div>
          <div class="field"><label>Forma de Pagamento</label><select id="pg-forma"><option${(c.formaPag||'Pix')==='Pix'?' selected':''}>Pix</option><option${(c.formaPag||'Boleto')==='Boleto'?' selected':''}>Boleto</option><option${(c.formaPag||'Cartão')==='Cartão'?' selected':''}>Cartão</option><option${(c.formaPag||'Dinheiro')==='Dinheiro'?' selected':''}>Dinheiro</option></select></div>
          <div class="field"><label>Data da Transação</label><input id="pg-data" type="date" value="${c.dataPagamento || new Date().toISOString().split('T')[0]}"></div>

          <div class="field form-full"><label>Observação / Detalhes</label><textarea id="pg-obs" placeholder="Ex: Pagamento confirmado via PIX no valor integral.">${c.obs || ''}</textarea></div>

          <div class="field form-full" style="background: var(--bg); padding: 12px; border-radius: 8px;">
            <label style="display:flex; align-items:center; gap:8px; cursor:pointer;"><input id="pg-notificar" type="checkbox" checked> Enviar notificação de pagamento ao cliente</label>
            <div style="margin-top: 8px;"><input id="pg-notificacao" class="field" style="width:100%" placeholder="Mensagem: Seu pagamento foi confirmado, obrigado." value="Pagamento registrado com sucesso."></div>
          </div>
        </div>
    </div>

    <!-- Aba de Histórico -->
    <div id="tab-hist-pagamento" class="tab-pane" style="display: none; max-height: 450px; overflow-y: auto;">
        ${histHTML}
    </div>
  </div>

  <div class="modal-foot">
    <button class="btn" onclick="closeModal(true)">Cancelar</button>
    <button class="btn btn-primary" onclick="savePagamento('${c.id}')"><i class="ti ti-device-floppy"></i> Salvar Pagamento</button>
  </div>`;
}

async function savePagamento(cid){
  let c = resolveClienteById(cid || editingId);
  let isNewToLocal = false;

  if(!c) {
      const alertData = getAlertData();
      const allAlerts = [...alertData.renovacoes.urgentes, ...alertData.renovacoes.normais, ...alertData.pagamentos.urgentes, ...alertData.pagamentos.normais];
      const alertItem = allAlerts.find(x => String(x.id) === String(cid));

      if (alertItem) {
          c = {
              id: cid,
              nome: alertItem.nome,
              tipoCert: alertItem.tipoCert,
              criadoEm: new Date().toISOString().split('T')[0],
              status: 'Aguardando Pagamento',
              historico: [],
              notificacoes: []
          };
          isNewToLocal = true;
      } else {
          showToast('Erro ao salvar pagamento: Cliente não encontrado.', 'error');
          return;
      }
  }

  const valor = parseFloat(document.getElementById('pg-valor').value) || 0;
  const status = document.getElementById('pg-status').value;
  const forma = document.getElementById('pg-forma').value;
  const data = document.getElementById('pg-data').value || new Date().toISOString().split('T')[0];
  const obs = document.getElementById('pg-obs').value.trim();

  c.valorCobrado = valor;
  c.formaPag = forma;
  c.pago = (status === 'Pago');
  c.dataPagamento = data;
  if(obs){ c.obs = [c.obs, obs].filter(Boolean).join('\n'); }

  if(c.pago && c.status === 'Aguardando Pagamento'){
      c.status = 'Emitido';
  }

  if(!c.historico) c.historico = [];
  c.historico.push({
      data,
      canal: 'Pagamento',
      obs: `${status} · ${forma}${valor ? ` · ${fmtMoney(valor)}` : ''}${obs ? ` - ${obs}` : ''}`,
      dt: new Date().toISOString()
  });

  const notify = document.getElementById('pg-notificar')?.checked;
  if(notify){
    const planilhaPk = getPlanilhaPkFromClientId(c.id);
    const texto = document.getElementById('pg-notificacao').value.trim() || `Pagamento ${status.toLowerCase()} para ${c.nome || 'o cliente'}.`;
    if(planilhaPk){
      try{
        const body = new URLSearchParams({
          tipo: 'notificacao', data, titulo: 'Pagamento registrado', texto,
          status: c.pago ? 'enviado' : 'pendente',
        });
        const resp = await fetch(`/planilha/${planilhaPk}/contatos/`, {
          method: 'POST',
          headers: {'Content-Type': 'application/x-www-form-urlencoded', 'X-CSRFToken': getCsrfToken(), 'X-Requested-With': 'XMLHttpRequest'},
          body: body.toString(),
        });
        const respData = await resp.json().catch(()=>({}));
        if(!resp.ok) throw new Error(respData.error || 'Falha ao registrar notificação');
      }catch(err){
        console.error(err);
        showToast(err.message || 'Pagamento salvo, mas a notificação não pôde ser registrada', 'error');
      }
    }else{
      showToast('Cliente não sincronizado com a planilha — notificação não registrada', 'info');
    }
  }

  if(isNewToLocal){
      clientes.unshift(c);
  }

  save();
  closeModal(true);

  renderClientes();
  renderDashboard();
  renderKanban();
  renderRenovacoes();
  renderInadimplencia();

  showToast('Pagamento salvo com sucesso!', 'success');
}
// ==================== NOVO MODAL DE CRM (CONTATOS) ====================
async function renderContatoModal(box, cid) {
  const pk = getPlanilhaPkFromClientId(cid);
  if(!pk){
    box.innerHTML = `<div class="modal-head"><h2>Registrar Contato</h2><button class="btn btn-sm" onclick="closeModal(true)"><i class="ti ti-x"></i></button></div><div class="modal-body"><p style="font-size:13px;color:var(--muted)">Cliente sincronizado da planilha é necessário para registrar contato.</p></div>`;
    return;
  }

  box.innerHTML = `<div class="modal-head"><h2>Registrar Contato</h2><button class="btn btn-sm" onclick="closeModal(true)"><i class="ti ti-x"></i></button></div><div class="modal-body"><p style="font-size:13px;color:var(--muted)">Carregando...</p></div>`;

  let cliente = {};
  let historico = [];
  try{
    const resp = await fetch(`/planilha/${pk}/contatos/`);
    if(resp.ok){
      const data = await resp.json();
      cliente = data.cliente || {};
      historico = (data.contatos || []).filter(c => c.tipo !== 'notificacao');
    }
  }catch(err){
    console.error(err);
  }

  const histHTML = historico.map(h => `
    <div style="padding: 14px; border-bottom: 1px solid var(--border); font-size: 13px;">
        <div style="display:flex; justify-content:space-between; margin-bottom:6px;">
            <strong><i class="ti ti-calendar"></i> ${fmtDate(h.data)} — ${escapeHtml(h.canal)||'—'}</strong>
            <span class="badge badge-novo">${escapeHtml(h.resultado) || 'Contato Feito'}</span>
        </div>
        <div style="color: var(--muted); margin-bottom: 6px;">
            <strong>Agendado para:</strong> ${h.agendamento ? new Date(h.agendamento).toLocaleString('pt-BR') : 'Não agendado'}
            ${h.produto ? `| <strong>Produto Ofertado:</strong> ${escapeHtml(h.produto)}` : ''}
        </div>
        <div style="background: var(--bg); padding: 10px; border-radius: 6px;">${escapeHtml(h.texto) || 'Nenhuma observação detalhada.'}</div>
    </div>`).join('') || '<div class="empty-state"><i class="ti ti-message-off"></i><p>Nenhum histórico de contato registrado.</p></div>';

  box.innerHTML = `
  <div class="modal-head">
    <h2><i class="ti ti-headset"></i> Gestão de Contato — ${escapeHtml(cliente.nome) || 'Cliente'}</h2>
    <button class="btn btn-sm" onclick="closeModal(true)"><i class="ti ti-x"></i></button>
  </div>
  <div class="modal-body" style="padding: 0;">

    <!-- Abas -->
    <div class="tabs" style="padding: 14px 20px 0 20px; background: var(--surface-alt); border-bottom: 1px solid var(--border); margin-bottom:0;">
      <div class="tab active" onclick="switchTab(this,'tab-reg-contato')">Registrar Contato</div>
      <div class="tab" onclick="switchTab(this,'tab-hist-contato')">Visualizar Histórico</div>
    </div>

    <!-- Aba de Formulário -->
    <div id="tab-reg-contato" class="tab-pane" style="padding: 20px;">
        <div style="background: var(--bg); padding: 12px; border-radius: 8px; margin-bottom: 20px; font-size: 13px; display:flex; gap:20px;">
            <div><strong>Cliente:</strong> <br><span style="color:var(--accent)">${escapeHtml(cliente.nome) || '—'}</span></div>
            <div><strong>Produto Atual:</strong> <br><span style="color:var(--accent)">${escapeHtml(cliente.tipoCert) || 'Não identificado'}</span></div>
        </div>

        <div class="form-grid cols3">
          <div class="field"><label>Data do Contato</label><input id="ct-data" type="date" value="${new Date().toISOString().split('T')[0]}"></div>
          <div class="field"><label>Canal</label><select id="ct-canal"><option>WhatsApp</option><option>Ligação</option><option>E-mail</option><option>Presencial</option></select></div>
          <div class="field"><label>Resultado da Conversa</label><select id="ct-resultado"><option>Em Negociação</option><option>Agendado para Renovação</option><option>Sem Interesse</option><option>Caixa Postal / Não Atende</option><option>Pagamento Confirmado</option></select></div>

          <div class="field"><label>Produto Ofertado</label><select id="ct-produto"><option value="">Manter atual</option>${precos.map(p=>`<option>${p.tipo}</option>`).join('')}</select></div>
          <div class="field"><label>Agendar Retorno Para</label><input id="ct-agendamento" type="datetime-local"></div>
          <div class="field"><label>Alterar Status no Funil</label><select id="ct-status"><option value="">Manter atual</option>${STATUS_LIST.map(s=>`<option>${s}</option>`).join('')}</select></div>

          <div class="field form-full">
            <label>Observação (Até 600 caracteres recomendados)</label>
            <textarea id="ct-obs" placeholder="Descreva como foi o atendimento..." style="min-height: 100px; resize: vertical;"></textarea>
          </div>
        </div>
    </div>

    <!-- Aba de Histórico -->
    <div id="tab-hist-contato" class="tab-pane" style="display: none; max-height: 450px; overflow-y: auto;">
        ${histHTML}
    </div>
  </div>

  <div class="modal-foot">
    <button class="btn" onclick="closeModal(true)">Cancelar</button>
    <button class="btn btn-primary" onclick="saveContato('${pk}')"><i class="ti ti-device-floppy"></i> Salvar Registro</button>
  </div>`;
}

async function saveContato(cid) {
  const planilhaPk = getPlanilhaPkFromClientId(cid);
  if(!planilhaPk){
    showToast('Cliente sincronizado da planilha é necessário para registrar contato', 'error');
    return;
  }

  const body = new URLSearchParams({
    tipo: 'contato',
    data: document.getElementById('ct-data').value,
    canal: document.getElementById('ct-canal').value,
    resultado: document.getElementById('ct-resultado').value,
    produto: document.getElementById('ct-produto').value,
    agendamento: document.getElementById('ct-agendamento').value,
    texto: document.getElementById('ct-obs').value,
    novo_status_funil: document.getElementById('ct-status').value,
  });

  try{
    const resp = await fetch(`/planilha/${planilhaPk}/contatos/`, {
      method: 'POST',
      headers: {'Content-Type': 'application/x-www-form-urlencoded', 'X-CSRFToken': getCsrfToken(), 'X-Requested-With': 'XMLHttpRequest'},
      body: body.toString(),
    });
    const data = await resp.json().catch(()=>({}));
    if(!resp.ok) throw new Error(data.error || 'Falha ao registrar contato');
    showToast('Contato registrado com sucesso!', 'success');
    closeModal(true);
    location.reload();
  }catch(err){
    console.error(err);
    showToast(err.message || 'Erro ao registrar contato', 'error');
  }
}

async function openHistoricoCliente(pk){
  const box=document.getElementById('detail-box');
  const overlay=document.getElementById('detail-overlay');
  box.innerHTML='<div class="modal-head"><h2>Histórico do Cliente</h2><button class="btn btn-sm" onclick="closeDetail(true)"><i class="ti ti-x"></i></button></div><div class="modal-body"><p style="font-size:13px;color:var(--muted)">Carregando...</p></div>';
  overlay.classList.add('open');
  try{
    const resp=await fetch(`/planilha/${pk}/contatos/`);
    if(!resp.ok) throw new Error('Falha ao carregar histórico');
    const data=await resp.json();
    const cliente=data.cliente||{};
    const contatos=(data.contatos||[]).filter(c=>c.tipo!=='notificacao');
    const notificacoes=(data.contatos||[]).filter(c=>c.tipo==='notificacao');
    const histHTML=contatos.length?contatos.map(h=>`<div class="contact-entry"><span class="dt">${fmtDate(h.data)}<br><small>${escapeHtml(h.canal)||'—'}${h.resultado?` · ${escapeHtml(h.resultado)}`:''}</small></span><span>${escapeHtml(h.texto)||'—'}</span></div>`).join(''):'<p style="font-size:12px;color:var(--muted)">Nenhum contato registrado</p>';
    const notifHTML=notificacoes.length?notificacoes.map(n=>`<div class="contact-entry"><span class="dt">${fmtDate(n.data)}<br><small>${escapeHtml(n.titulo)||'Notificação'}</small></span><span>${escapeHtml(n.texto)||'—'}</span></div>`).join(''):'<p style="font-size:12px;color:var(--muted)">Nenhuma notificação registrada</p>';
    box.innerHTML=`
    <div class="modal-head">
      <div>
        <h2>${escapeHtml(cliente.nome)||'Cliente'}</h2>
        <div style="font-size:12px;color:var(--muted);margin-top:2px">${escapeHtml(cliente.telefone)||'Telefone não informado'}${cliente.email?` · ${escapeHtml(cliente.email)}`:''}</div>
      </div>
      <div style="display:flex;gap:8px">
        <button class="btn btn-sm" onclick="openModal('contato','${pk}');closeDetail(true)"><i class="ti ti-plus"></i> Registrar Contato</button>
        <button class="btn btn-sm" onclick="closeDetail(true)"><i class="ti ti-x"></i></button>
      </div>
    </div>
    <div class="modal-body">
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px">
        <div class="detail-section">
          <h4>Histórico de Contatos</h4>
          <div class="contact-log">${histHTML}</div>
        </div>
        <div class="detail-section">
          <h4>Notificações</h4>
          <div class="contact-log">${notifHTML}</div>
        </div>
      </div>
    </div>`;
  }catch(err){
    console.error(err);
    box.innerHTML='<div class="modal-head"><h2>Histórico do Cliente</h2><button class="btn btn-sm" onclick="closeDetail(true)"><i class="ti ti-x"></i></button></div><div class="modal-body"><p style="font-size:13px;color:var(--danger)">Não foi possível carregar o histórico deste cliente.</p></div>';
  }
}
