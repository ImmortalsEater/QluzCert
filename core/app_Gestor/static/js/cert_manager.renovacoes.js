// ==================== RENOVAÇÕES ====================
function renderRenovacoes(){
  const alertData = getAlertData();
  const urgentes=alertData.renovacoes.urgentes.sort((a,b)=>(a.dias??9999)-(b.dias??9999));
  const normais=alertData.renovacoes.normais.sort((a,b)=>(a.dias??9999)-(b.dias??9999));
  document.getElementById('ren-urgente').innerHTML=urgentes.length?urgentes.map(c=>renderAlertCard(c,'renovacao')).join(''):'<p style="font-size:13px;color:var(--muted)">Nenhum vencimento urgente ✓</p>';
  document.getElementById('ren-normal').innerHTML=normais.length?normais.map(c=>renderAlertCard(c,'renovacao')).join(''):'<p style="font-size:13px;color:var(--muted)">Nenhum no período ✓</p>';
}

function renderInadimplencia(){
  const alertData = getAlertData();
  const urgentes=alertData.pagamentos.urgentes.sort((a,b)=>(a.dias??9999)-(b.dias??9999));
  const normais=alertData.pagamentos.normais.sort((a,b)=>(a.dias??9999)-(b.dias??9999));
  document.getElementById('pag-urgente').innerHTML=urgentes.length?urgentes.map(c=>renderAlertCard(c,'pagamento')).join(''):'<p style="font-size:13px;color:var(--muted)">Nenhum pagamento vencido ✓</p>';
  document.getElementById('pag-normal').innerHTML=normais.length?normais.map(c=>renderAlertCard(c,'pagamento')).join(''):'<p style="font-size:13px;color:var(--muted)">Nenhum pagamento a vencer ✓</p>';
}
