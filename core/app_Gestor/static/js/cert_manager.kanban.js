async function mudarStatusLead(id, novoStatus){
  const lead = leads.find(l=>l.id===id);
  const anterior = lead ? lead.status : null;
  if(lead) lead.status = novoStatus;
  renderKanban();
  try{
    const body = new URLSearchParams({status: novoStatus, expected_atualizado_em: lead?.atualizadoEm || ''});
    const resp = await fetch(`/planilha/${id}/status/`, {
      method: 'POST',
      headers: {'Content-Type': 'application/x-www-form-urlencoded', 'X-CSRFToken': getCsrfToken(), 'X-Requested-With': 'XMLHttpRequest'},
      body: body.toString(),
    });
    const data = await resp.json().catch(()=>({}));
    if(!resp.ok) throw new Error(data.error || 'Falha ao atualizar status');
    if(lead) lead.atualizadoEm = data.atualizado_em;
    showToast('Status atualizado', 'success');
  }catch(err){
    if(lead) lead.status = anterior;
    renderKanban();
    showToast(err.message || 'Erro ao atualizar status', 'error');
  }
}

// ==================== KANBAN ====================
function renderKanban(){
  const board=document.getElementById('kanban-board');
  board.innerHTML=STATUS_LIST.map((s,i)=>{
    const cards=leads.filter(l=>l.status===s);
    return`<div class="kanban-col" ondragover="handleKanbanDragOver(event)" ondragleave="handleKanbanDragLeave(event)" ondrop="handleKanbanDrop(event,'${s}')">
      <div class="kanban-col-head" style="color:${KANBAN_COLORS[i]}">${s} <span style="background:${KANBAN_COLORS[i]}22;color:${KANBAN_COLORS[i]};padding:1px 7px;border-radius:10px;font-size:11px">${cards.length}</span></div>
      ${cards.map(l=>`<div class="kanban-card" draggable="true" ondragstart="handleKanbanDragStart(event,'${l.id}')" ondragend="handleKanbanDragEnd(event)">
        <div class="kanban-card-name">${escapeHtml(l.nome)}</div>
        <div class="kanban-card-sub">${escapeHtml(l.tipoCert)||'Tipo não definido'}</div>
        <div class="kanban-card-footer">
          ${!l.pago&&l.dataVencimento&&daysUntil(l.dataVencimento)<=30?`<span class="parceiro-tag" style="font-size:10px;background:${daysUntil(l.dataVencimento)<0?'var(--danger)':'var(--warn)'}22;color:${daysUntil(l.dataVencimento)<0?'var(--danger)':'var(--warn)'}">${daysUntil(l.dataVencimento)<0?`Pagamento vencido há ${Math.abs(daysUntil(l.dataVencimento))} dias`:'Pagamento pendente'}</span>`:''}
          ${l.parceiro?`<span class="parceiro-tag" style="font-size:10px">${escapeHtml(l.parceiro)}</span>`:''}
        </div>
        <select class="kanban-status-select" onchange="mudarStatusLead('${l.id}', this.value)">
          ${STATUS_LIST.map(st=>`<option${l.status===st?' selected':''}>${st}</option>`).join('')}
        </select>
      </div>`).join('')}
    </div>`;
  }).join('');
}

function handleKanbanDragStart(event, id){
  event.dataTransfer.setData('text/plain', id);
  event.dataTransfer.effectAllowed = 'move';
  event.currentTarget.classList.add('dragging');
}

function handleKanbanDragEnd(event){
  event.currentTarget.classList.remove('dragging');
}

function handleKanbanDragOver(event){
  event.preventDefault();
  event.dataTransfer.dropEffect = 'move';
  event.currentTarget.classList.add('drag-over');
}

function handleKanbanDragLeave(event){
  event.currentTarget.classList.remove('drag-over');
}

function handleKanbanDrop(event, novoStatus){
  event.preventDefault();
  event.currentTarget.classList.remove('drag-over');
  const id = event.dataTransfer.getData('text/plain');
  const lead = leads.find(l=>l.id===id);
  if(!lead || lead.status===novoStatus) return;
  mudarStatusLead(id, novoStatus);
}
