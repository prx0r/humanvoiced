/* hv i18n: ?lang= or saved choice, data-i18n binding, en fallback. */
(() => {
'use strict';
const LOCALES = {en: 'English', es: 'Español'};
const cache = {};
async function strings(lang){
  if(cache[lang]) return cache[lang];
  try{
    const r = await fetch('i18n/' + lang + '.json', {credentials: 'omit'});
    if(!r.ok) throw 0;
    cache[lang] = await r.json();
    return cache[lang];
  }catch{ return null; }
}
function get(obj, key){
  return key.split('.').reduce((o, k) => (o && o[k] !== undefined) ? o[k] : null, obj);
}
async function apply(lang){
  const dict = await strings(lang) || await strings('en') || {};
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const v = get(dict, el.dataset.i18n);
    if(v) el.textContent = v;
  });
  document.querySelectorAll('[data-i18n-ph]').forEach(el => {
    const v = get(dict, el.dataset.i18nPh);
    if(v) el.placeholder = v;
  });
  document.querySelectorAll('[data-i18n-html]').forEach(el => {
    const v = get(dict, el.dataset.i18nHtml);
    if(v) el.innerHTML = v;
  });
  document.documentElement.lang = lang;
  try{ localStorage.setItem('hv-lang', lang); }catch{}
  const sel = document.getElementById('lang-switch');
  if(sel) sel.value = lang;
}
function current(){
  const q = new URLSearchParams(location.search).get('lang');
  if(q && LOCALES[q]) return q;
  try{
    const s = localStorage.getItem('hv-lang');
    if(s && LOCALES[s]) return s;
  }catch{}
  const nav = (navigator.language || 'en').slice(0, 2).toLowerCase();
  return LOCALES[nav] ? nav : 'en';
}
function mountSwitcher(){
  const host = document.getElementById('lang-switch-host');
  if(!host || document.getElementById('lang-switch')) return;
  const sel = document.createElement('select');
  sel.id = 'lang-switch';
  sel.setAttribute('aria-label', 'Language');
  for(const [code, label] of Object.entries(LOCALES)){
    const o = document.createElement('option');
    o.value = code; o.textContent = label;
    sel.append(o);
  }
  sel.onchange = () => {
    const u = new URL(location.href);
    u.searchParams.set('lang', sel.value);
    location.href = u.toString();
  };
  host.append(sel);
}
window.hvI18n = {apply, current, mountSwitcher, LOCALES};
document.addEventListener('DOMContentLoaded', () => {
  mountSwitcher();
  apply(current());
});
})();
