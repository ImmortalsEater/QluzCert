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

// Ordem local (por navegador) de cards dentro de cada coluna do Kanban --
// não persiste na planilha nem é compartilhada entre usuários/dispositivos.
function getOrdemColuna(status){ return DB.get('kanban_ordem_' + status) || []; }
function setOrdemColuna(status, ids){ DB.set('kanban_ordem_' + status, ids); }

// ==================== KANBAN ====================
function renderKanban(){
  const board=document.getElementById('kanban-board');
  board.innerHTML=STATUS_LIST.map((s,i)=>{
    let cards=leads.filter(l=>l.status===s);
    const ordemSalva = getOrdemColuna(s);
    if(ordemSalva.length){
      const idxMap = new Map(ordemSalva.map((id, idx) => [String(id), idx]));
      cards = cards.slice().sort((a,b) => {
        const ia = idxMap.has(String(a.id)) ? idxMap.get(String(a.id)) : Infinity;
        const ib = idxMap.has(String(b.id)) ? idxMap.get(String(b.id)) : Infinity;
        return ia - ib;
      });
    }
    return`<div class="kanban-col" ondragover="handleKanbanDragOver(event)" ondragleave="handleKanbanDragLeave(event)" ondrop="handleKanbanDrop(event,'${s}')">
      <div class="kanban-col-head" style="color:${KANBAN_COLORS[i]}">${s} <span style="background:${KANBAN_COLORS[i]}22;color:${KANBAN_COLORS[i]};padding:1px 7px;border-radius:10px;font-size:11px">${cards.length}</span></div>
      ${cards.map(l=>`<div class="kanban-card" draggable="true" data-lead-id="${l.id}" onclick="openDetail('${l.id}')" ondragstart="handleKanbanDragStart(event,'${l.id}')" ondragend="handleKanbanDragEnd(event)" ondragover="handleCardDragOver(event)">
        <div class="kanban-card-name">${escapeHtml(l.nome)}</div>
        <div class="kanban-card-sub">${escapeHtml(l.tipoCert)||'Tipo não definido'}</div>
        <div class="kanban-card-footer">
          ${!l.pago&&l.dataVencimento&&daysUntil(l.dataVencimento)<=30?`<span class="parceiro-tag" style="font-size:10px;background:${daysUntil(l.dataVencimento)<0?'var(--danger)':'var(--warn)'}22;color:${daysUntil(l.dataVencimento)<0?'var(--danger)':'var(--warn)'}">${daysUntil(l.dataVencimento)<0?`Pagamento vencido há ${Math.abs(daysUntil(l.dataVencimento))} dias`:'Pagamento pendente'}</span>`:''}
          ${l.parceiro?`<span class="parceiro-tag" style="font-size:10px">${escapeHtml(l.parceiro)}</span>`:''}
        </div>
        <select class="kanban-status-select" onclick="event.stopPropagation()" onchange="mudarStatusLead('${l.id}', this.value)">
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
  document.querySelectorAll('.kanban-card.drag-over-top,.kanban-card.drag-over-bottom').forEach(el=>{
    el.classList.remove('drag-over-top','drag-over-bottom');
  });
}

function handleKanbanDragOver(event){
  event.preventDefault();
  event.dataTransfer.dropEffect = 'move';
  event.currentTarget.classList.add('drag-over');
}

function handleKanbanDragLeave(event){
  event.currentTarget.classList.remove('drag-over');
}

// Ao arrastar sobre outro card (não a coluna), marca visualmente se o card
// arrastado vai ser inserido antes ou depois dependendo da metade sobre a
// qual o cursor está.
function handleCardDragOver(event){
  event.preventDefault();
  event.stopPropagation();
  const card = event.currentTarget;
  const rect = card.getBoundingClientRect();
  const isAfter = (event.clientY - rect.top) > (rect.height / 2);
  card.classList.toggle('drag-over-top', !isAfter);
  card.classList.toggle('drag-over-bottom', isAfter);
}

function handleKanbanDrop(event, novoStatus){
  event.preventDefault();
  event.currentTarget.classList.remove('drag-over');
  const id = event.dataTransfer.getData('text/plain');
  const lead = leads.find(l=>l.id===id);
  if(!lead) return;

  if(lead.status === novoStatus){
    const targetCard = event.target.closest('.kanban-card');
    const cardsNaColuna = leads.filter(l => l.status === novoStatus).map(l => l.id);
    let ordemAtual = getOrdemColuna(novoStatus);
    if(!ordemAtual.length) ordemAtual = cardsNaColuna.slice();
    ordemAtual = ordemAtual.filter(cid => cardsNaColuna.includes(cid));
    cardsNaColuna.forEach(cid => { if(!ordemAtual.includes(cid)) ordemAtual.push(cid); });
    ordemAtual = ordemAtual.filter(cid => cid !== id);
    if(targetCard){
      const targetId = targetCard.dataset.leadId;
      const isAfter = targetCard.classList.contains('drag-over-bottom');
      const targetIdx = ordemAtual.indexOf(targetId);
      ordemAtual.splice(isAfter ? targetIdx + 1 : targetIdx, 0, id);
    } else {
      ordemAtual.push(id);
    }
    setOrdemColuna(novoStatus, ordemAtual);
    renderKanban();
    return;
  }

  mudarStatusLead(id, novoStatus);
}
