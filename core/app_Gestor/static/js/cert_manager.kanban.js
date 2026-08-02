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

// Filtro por parceiro do funil -- fica em memória (não persiste), só some
// cards de outros parceiros visualmente (esmaece) pra não perder a noção
// do funil inteiro enquanto foca numa rodada de follow-up.
let kanbanFiltroParceiro = null; // null = "Todos" | '__none__' = sem parceiro | nome do parceiro
// Só os N parceiros com mais leads aparecem direto -- com muitos parceiros
// cadastrados a fila de chips ia crescer sem limite; o resto fica atrás de
// um "+N parceiros" que expande a linha inteira (nada escondido, só dobrado).
const KANBAN_FILTRO_TOP_N = 4;
let kanbanFiltroParceirosExpandido = false;

function setFiltroParceiro(nome){
  kanbanFiltroParceiro = (kanbanFiltroParceiro === nome) ? null : nome;
  renderKanban();
}
function toggleFiltroParceirosExpandido(){
  kanbanFiltroParceirosExpandido = !kanbanFiltroParceirosExpandido;
  renderFiltroParceiros();
}
function leadMatchesFiltroParceiro(l){
  if(!kanbanFiltroParceiro) return true;
  if(kanbanFiltroParceiro === '__none__') return !l.parceiro;
  return l.parceiro === kanbanFiltroParceiro;
}
function renderFiltroParceiros(){
  const el = document.getElementById('funil-filtros');
  if(!el) return;
  const nomes = [...new Set(leads.map(l=>l.parceiro).filter(Boolean))];
  const semParceiroCount = leads.filter(l=>!l.parceiro).length;
  const categorias = [
    ...nomes.map(n=>({valor:n, label:n, count:leads.filter(l=>l.parceiro===n).length})),
    ...(semParceiroCount ? [{valor:'__none__', label:'Sem parceiro', count:semParceiroCount}] : [])
  ].sort((a,b)=>b.count-a.count || a.label.localeCompare(b.label));
  if(!categorias.length){ el.innerHTML=''; el.style.display='none'; return; }
  el.style.display='';

  const chip = (valor, label, count)=>`<button type="button" class="funil-filtro-chip${kanbanFiltroParceiro===valor?' active':''}" onclick="setFiltroParceiro(${valor===null?'null':`'${String(valor).replace(/'/g,"\\'")}'`})">${escapeHtml(label)} (${count})</button>`;

  const podeColapsar = categorias.length > KANBAN_FILTRO_TOP_N;
  const visiveis = (kanbanFiltroParceirosExpandido || !podeColapsar) ? categorias : categorias.slice(0, KANBAN_FILTRO_TOP_N);
  const restantes = categorias.length - visiveis.length;

  el.innerHTML = [
    chip(null, 'Todos', leads.length),
    ...visiveis.map(c=>chip(c.valor, c.label, c.count)),
    restantes > 0 ? `<button type="button" class="funil-filtro-chip-more" onclick="toggleFiltroParceirosExpandido()">+${restantes} parceiro${restantes>1?'s':''}</button>` : '',
    (podeColapsar && kanbanFiltroParceirosExpandido) ? `<button type="button" class="funil-filtro-chip-more" onclick="toggleFiltroParceirosExpandido()">mostrar menos</button>` : ''
  ].join('');
}

function clearDropPlaceholder(){
  document.querySelectorAll('.drop-placeholder').forEach(el=>el.remove());
}

// Menu de status do card -- mesmo padrão do #action-menu-dropdown (elemento
// único reaproveitado por todos os cards, position:fixed calculado em JS
// pra não ser cortado pelo overflow do board). Substitui o antigo
// <select> nativo por um gatilho colorido (cor do status atual) que abre
// esse menu, no mesmo estilo dos outros dropdowns do app.
function closeKanbanStatusMenu(){
  const menu = document.getElementById('kanban-status-menu');
  if(!menu) return;
  menu.classList.remove('open');
  menu.dataset.forId = '';
}

function openKanbanStatusMenu(e, id){
  e.stopPropagation();
  const menu = document.getElementById('kanban-status-menu');
  if(!menu) return;
  const wasOpenForThisLead = menu.classList.contains('open') && menu.dataset.forId === id;
  closeKanbanStatusMenu();
  if(typeof closeActionMenu === 'function') closeActionMenu();
  if(typeof closeParceiroActionMenu === 'function') closeParceiroActionMenu();
  document.getElementById('column-selector-panel')?.classList.remove('open');
  document.getElementById('save-menu')?.classList.remove('open');
  document.getElementById('user-menu-panel')?.classList.remove('open');
  document.getElementById('filtrar-clientes-panel')?.classList.remove('open');
  if(wasOpenForThisLead) return;

  const lead = leads.find(l=>l.id===id);
  if(!lead) return;
  menu.dataset.forId = id;
  menu.innerHTML = STATUS_LIST.map(st=>`<button type="button" class="action-menu-item" role="menuitem" onclick="closeKanbanStatusMenu(); mudarStatusLead('${id}', '${st.replace(/'/g,"\\'")}')">${st===lead.status?'<i class="ti ti-check"></i>':'<i></i>'}${escapeHtml(st)}</button>`).join('');

  const btn = e.currentTarget;
  const rect = btn.getBoundingClientRect();
  menu.classList.add('open');
  const menuRect = menu.getBoundingClientRect();
  let top = rect.bottom + 6;
  let left = rect.left;
  if(left + menuRect.width > window.innerWidth - 8) left = window.innerWidth - menuRect.width - 8;
  let flipped = false;
  if(top + menuRect.height > window.innerHeight - 8){ top = rect.top - menuRect.height - 6; flipped = true; }
  menu.style.top = top + 'px';
  menu.style.left = left + 'px';
  menu.style.transformOrigin = flipped ? 'bottom left' : 'top left';
}

document.addEventListener('click', closeKanbanStatusMenu);
document.addEventListener('scroll', closeKanbanStatusMenu, true);
window.addEventListener('resize', closeKanbanStatusMenu);

// ==================== KANBAN ====================
function renderKanban(){
  renderFiltroParceiros();
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
      ${cards.map(l=>`<div class="kanban-card${leadMatchesFiltroParceiro(l)?'':' dimmed'}" draggable="true" data-lead-id="${l.id}" onclick="openDetail('${l.id}')" ondragstart="handleKanbanDragStart(event,'${l.id}')" ondragend="handleKanbanDragEnd(event)" ondragover="handleCardDragOver(event)">
        <i class="ti ti-grip-vertical kanban-card-grip" aria-hidden="true"></i>
        <div class="kanban-card-name">${escapeHtml(l.nome)}</div>
        <div class="kanban-card-sub">${escapeHtml(l.tipoCert)||'Tipo não definido'}</div>
        <div class="kanban-card-footer">
          ${!l.pago&&l.dataVencimento&&daysUntil(l.dataVencimento)<=30?(()=>{const vencTexto=daysUntil(l.dataVencimento)<0?`Pagamento vencido há ${Math.abs(daysUntil(l.dataVencimento))} dias`:'Pagamento pendente';return `<span class="kanban-venc-tag" title="${vencTexto}" style="color:${daysUntil(l.dataVencimento)<0?'var(--danger)':'var(--warn)'}">${vencTexto}</span>`})():''}
          ${l.parceiro?`<span class="parceiro-tag" title="${escapeHtml(l.parceiro)}" style="font-size:10px">${escapeHtml(l.parceiro)}</span>`:''}
        </div>
        ${!l.pago&&Number(l.valorCobrado)>0?`<div class="valor-chip${Number(l.valorCobrado)>=200?' valor-chip-alto':''}">${fmtMoney(l.valorCobrado)} em aberto</div>`:''}
        <div class="kanban-status-block">
          <div class="kanban-status-eyebrow">Status</div>
          <button type="button" class="kanban-status-trigger" style="background:color-mix(in srgb, ${KANBAN_COLORS[statusIndex(l.status)]} 14%, transparent);border-color:${KANBAN_COLORS[statusIndex(l.status)]};color:${KANBAN_COLORS[statusIndex(l.status)]}" onclick="openKanbanStatusMenu(event,'${l.id}')">
            <span>${escapeHtml(l.status)}</span><i class="ti ti-chevron-down"></i>
          </button>
        </div>
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
  clearDropPlaceholder();
}

function handleKanbanDragOver(event){
  event.preventDefault();
  event.dataTransfer.dropEffect = 'move';
  event.currentTarget.classList.add('drag-over');
  // Só cria o placeholder de "fim da coluna" quando o cursor está sobre a
  // área vazia da coluna, não sobre um card (esse caso já é tratado --e
  // interrompido via stopPropagation-- por handleCardDragOver).
  if(event.target === event.currentTarget){
    clearDropPlaceholder();
    const placeholder = document.createElement('div');
    placeholder.className = 'drop-placeholder';
    event.currentTarget.appendChild(placeholder);
  }
}

function handleKanbanDragLeave(event){
  event.currentTarget.classList.remove('drag-over');
}

// Ao arrastar sobre outro card (não a coluna), ocupa o lugar de verdade
// onde o card vai cair com um slot tracejado, em vez de só marcar borda.
function handleCardDragOver(event){
  event.preventDefault();
  event.stopPropagation();
  const card = event.currentTarget;
  const rect = card.getBoundingClientRect();
  const isAfter = (event.clientY - rect.top) > (rect.height / 2);
  clearDropPlaceholder();
  const placeholder = document.createElement('div');
  placeholder.className = 'drop-placeholder';
  if(isAfter){ card.after(placeholder); } else { card.before(placeholder); }
}

function handleKanbanDrop(event, novoStatus){
  event.preventDefault();
  event.currentTarget.classList.remove('drag-over');
  const id = event.dataTransfer.getData('text/plain');
  const lead = leads.find(l=>l.id===id);
  const placeholder = event.currentTarget.querySelector('.drop-placeholder');
  clearDropPlaceholder();
  if(!lead) return;

  if(lead.status === novoStatus){
    const cardsNaColuna = leads.filter(l => l.status === novoStatus).map(l => l.id);
    let ordemAtual = getOrdemColuna(novoStatus);
    if(!ordemAtual.length) ordemAtual = cardsNaColuna.slice();
    ordemAtual = ordemAtual.filter(cid => cardsNaColuna.includes(cid));
    cardsNaColuna.forEach(cid => { if(!ordemAtual.includes(cid)) ordemAtual.push(cid); });
    ordemAtual = ordemAtual.filter(cid => cid !== id);
    const nextCard = placeholder && placeholder.nextElementSibling && placeholder.nextElementSibling.classList.contains('kanban-card')
      ? placeholder.nextElementSibling : null;
    const insertIdx = nextCard ? ordemAtual.indexOf(nextCard.dataset.leadId) : -1;
    ordemAtual.splice(insertIdx < 0 ? ordemAtual.length : insertIdx, 0, id);
    setOrdemColuna(novoStatus, ordemAtual);
    renderKanban();
    return;
  }

  mudarStatusLead(id, novoStatus);
}
