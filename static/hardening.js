(function(){
  try {
    var noop = function(){};
    var c = window.console = window.console || {};
    var methods = [
      'log','info','debug','warn','error','trace','table','dir','dirxml',
      'group','groupCollapsed','groupEnd','time','timeEnd','timeLog',
      'profile','profileEnd','assert','clear','count','countReset'
    ];
    for (var i=0;i<methods.length;i++){
      var m = methods[i];
      try { c[m] = noop; } catch(_) { /* ignore */ }
    }
  } catch (_) {}
})();

