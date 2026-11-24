(async function boot() {
  loadSavedTheme();
  refreshFavUi();
  loadCategories();
  loadMarket(true);
  await refreshMe();
  updateDrawerProfile();
  // Незарегистрированному пользователю сразу предлагаем указать @username (можно отложить и просто смотреть маркет).
  if (me.loaded && !me.is_registered) showRegModal();
  checkShopStatus();
})();
