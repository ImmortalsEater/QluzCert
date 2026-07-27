// Inicializa comportamentos ao carregar o DOM
document.addEventListener('DOMContentLoaded', function(){
  try{ renderSaveActions(); initSaveMenu(); }catch(e){}
});

// ==================== INIT ====================
function initApp(){
  renderDashboard();
  renderClientes();
  filterPlanilhaImportada();
  renderParceiros();
  renderTabela();
  updateBadges();
  syncBackendAlertCounts();
}

initApp();
