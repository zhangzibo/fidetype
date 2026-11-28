// Site script for every generated page: colour theme button, copy buttons, reveal on scroll.
// It makes no network request. Loaded in <head>, so the stored theme applies before the first paint.
(function(){
  var root=document.documentElement;
  root.classList.remove('no-js');
  // Theme: auto -> dark -> light -> auto. Stored per viewer only (localStorage, may be blocked).
  var KEY='fidetype-theme';
  function get(){try{return localStorage.getItem(KEY)}catch(e){return null}}
  function set(v){try{v?localStorage.setItem(KEY,v):localStorage.removeItem(KEY)}catch(e){}}
  function label(v){var b=document.getElementById('theme-btn');if(b)b.setAttribute('aria-label','Colour theme: '+(v||'auto')+'. Select to change.')}
  function apply(v){if(v)root.setAttribute('data-theme',v);else root.removeAttribute('data-theme');label(v)}
  apply(get());
  function fallback(t){var a=document.createElement('textarea');a.value=t;a.style.position='fixed';a.style.opacity='0';document.body.appendChild(a);a.select();try{document.execCommand('copy')}catch(e){}a.remove()}
  document.addEventListener('click',function(e){
    var b=e.target.closest('#theme-btn');
    if(b){var cur=get();var nx=cur==null?'dark':cur==='dark'?'light':null;set(nx);apply(nx)}
    var c=e.target.closest('.copy');
    if(c){var pre=document.getElementById(c.getAttribute('data-for'));var t=pre?pre.getAttribute('data-copy')||pre.innerText:'';
      var done=function(){var o=c.textContent;c.textContent='Copied';setTimeout(function(){c.textContent=o},1400)};
      if(navigator.clipboard&&navigator.clipboard.writeText)navigator.clipboard.writeText(t).then(done,function(){fallback(t);done()});else{fallback(t);done()}}
  });
  document.addEventListener('DOMContentLoaded',function(){
    label(get());
    var els=document.querySelectorAll('.reveal');
    if('IntersectionObserver' in window){var io=new IntersectionObserver(function(es){es.forEach(function(x){if(x.isIntersecting){x.target.classList.add('in');io.unobserve(x.target)}})},{rootMargin:'0px 0px -8% 0px'});
      els.forEach(function(el){io.observe(el)})}else els.forEach(function(el){el.classList.add('in')});
  });
})();
