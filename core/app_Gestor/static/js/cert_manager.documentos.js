function openDocumentosCliente(clientId){
  const pk = getPlanilhaPkFromClientId(clientId);
  if(!pk){
    showToast('Documentos disponíveis apenas para clientes sincronizados da planilha','info');
    return;
  }
  openModal('cliente', clientId);
  setTimeout(()=>switchTabById('tab-documentos'), 0);
}

function switchTabById(tabId){
  const tab = document.querySelector(`.tab[onclick*="'${tabId}'"]`);
  if(tab){
    switchTab(tab, tabId);
  }
}

function bytesToHuman(bytes){
  const value = Number(bytes || 0);
  if(!Number.isFinite(value) || value <= 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  let current = value;
  let unitIndex = 0;
  while(current >= 1024 && unitIndex < units.length - 1){
    current /= 1024;
    unitIndex += 1;
  }
  return `${current.toFixed(current >= 10 || unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
}

async function loadDocumentosCliente(clientId){
  const pk = getPlanilhaPkFromClientId(clientId);
  const container = document.getElementById('documentos-list');
  const meta = document.getElementById('documentos-meta');
  const uploadForm = document.getElementById('documentos-form');
  if(!pk || !container) return;
  container.innerHTML = '<p style="font-size:13px;color:var(--muted)">Carregando documentos...</p>';
  if(meta) meta.textContent = 'Carregando...';
  try{
    const response = await fetch(`/planilha/${pk}/documentos/?format=json`);
    if(!response.ok) throw new Error('Falha ao carregar documentos');
    const data = await response.json();
    const docs = Array.isArray(data.documentos) ? data.documentos : [];
    if(meta){
      const cliente = data.registro?.cliente || 'cliente';
      meta.textContent = `Documentos de ${cliente} · ${docs.length} item(ns)`;
    }
    if(!docs.length){
      container.innerHTML = data.documentos_erro
        ? '<p style="font-size:13px;color:var(--warn)">Não foi possível carregar os documentos agora (planilha/Drive indisponível). Você ainda pode enviar um novo arquivo.</p>'
        : '<p style="font-size:13px;color:var(--muted)">Nenhum documento enviado para este cliente ainda.</p>';
      return;
    }
    container.innerHTML = docs.map(doc => `
      <div class="document-card" style="display:flex;justify-content:space-between;gap:12px;align-items:center;padding:10px 12px;border:1px solid var(--border);border-radius:10px;background:var(--surface);margin-bottom:8px">
        <div style="min-width:0">
          <div style="font-weight:700;font-size:13px;word-break:break-word">${escapeHtml(doc.nome_original)}</div>
          <div style="font-size:12px;color:var(--muted);margin-top:2px">${escapeHtml(doc.tipo_documento_display)} · ${fmtDate(doc.data_envio)} · ${bytesToHuman(doc.tamanho_bytes)}</div>
          ${doc.armazenamento === 'local_pendente' ? '<div style="font-size:11px;color:var(--warn);margin-top:2px;font-weight:600">Pendente de sincronização com o Drive</div>' : ''}
        </div>
        <div style="display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end">
          <a class="btn btn-sm" href="${doc.download_url}" target="_blank" rel="noopener"><i class="ti ti-download"></i> Baixar</a>
          ${(window.IS_ADMIN || window.PERMS.excluir_documento) ? `<button class="btn btn-sm btn-danger" onclick="deleteDocumentoCliente('${clientId}', '${doc.delete_url}')" aria-label="Excluir documento"><i class="ti ti-trash" aria-hidden="true"></i></button>` : ''}
        </div>
      </div>
    `).join('');
  }catch(err){
    console.error(err);
    if(meta) meta.textContent = 'Erro ao carregar documentos';
    container.innerHTML = '<p style="font-size:13px;color:var(--danger)">Não foi possível carregar os documentos.</p>';
  }
}

async function uploadDocumentoCliente(event, clientId){
  event.preventDefault();
  const pk = getPlanilhaPkFromClientId(clientId);
  if(!pk){
    showToast('Cliente sincronizado da planilha é necessário para upload de documentos','error');
    return false;
  }
  const form = event.target;
  const formData = new FormData(form);
  const file = formData.get('arquivo');
  if(!file || !file.name){
    showToast('Selecione um arquivo antes de enviar','error');
    return false;
  }
  try{
    const response = await fetch(`/planilha/${pk}/documentos/`, {
      method: 'POST',
      headers: {'X-CSRFToken': getCsrfToken()},
      body: formData,
    });
    if(!response.ok){
      const text = await response.text();
      throw new Error(text || 'Falha ao enviar documento');
    }
    form.reset();
    showToast('Documento enviado com sucesso','success');
    await loadDocumentosCliente(clientId);
  }catch(err){
    console.error(err);
    showToast('Erro ao enviar documento','error');
  }
  return false;
}

async function deleteDocumentoCliente(clientId, deleteUrl){
  if(!confirm('Remover este documento?')) return;
  try{
    const response = await fetch(deleteUrl, {
      method: 'POST',
      headers: {'X-CSRFToken': getCsrfToken()},
    });
    if(!response.ok) throw new Error('Falha ao excluir documento');
    showToast('Documento removido','success');
    await loadDocumentosCliente(clientId);
  }catch(err){
    console.error(err);
    showToast('Erro ao remover documento','error');
  }
}
