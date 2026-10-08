/* HumanVoiced Studio — phone-first. Real waveform + dBFS + sound check, persistent audio before OAuth. */
(() => {
  'use strict';
  const API = 'https://api.humanvoiced.com';
  const DEMO = new URLSearchParams(location.search).has('demo') || location.protocol === 'file:';
  const $ = x => document.getElementById(x);
  const msg = (text, cls='') => { const e=$('record-hint'); e.textContent=text; e.className='note '+cls; };
  const dbOpen = () => new Promise((resolve,reject) => {
    const r=indexedDB.open('humanvoiced-studio-v1',1);
    r.onupgradeneeded=()=>{const d=r.result;if(!d.objectStoreNames.contains('recordings'))d.createObjectStore('recordings');};
    r.onsuccess=()=>resolve(r.result); r.onerror=()=>reject(r.error);
  });
  const saveLocal = async (key,value) => {const db=await dbOpen();await new Promise((resolve,reject)=>{const t=db.transaction('recordings','readwrite');t.objectStore('recordings').put(value,key);t.oncomplete=resolve;t.onerror=()=>reject(t.error);});db.close();};
  const getLocal = async key => {const db=await dbOpen();const value=await new Promise((resolve,reject)=>{const t=db.transaction('recordings');const r=t.objectStore('recordings').get(key);r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error);});db.close();return value;};
  let wavBlob=null, wavUrl='', stream=null, ctx=null, analyser=null, frameId=0, recorder=null, timer=null, started=0, sampleSha='', signedIn=false, draftReady=false;
  const step = (name,ok) => {$(name).textContent=ok?'✓':name.slice(-1);$(name).style.background=ok?'#e1f5e7':'';};
  const dbfsOf = rms => rms<=0.00001 ? -96 : Math.max(-96, Math.round(20*Math.log10(rms)*10)/10);

  /* ---- real-time scrolling waveform + dBFS + optional spectrogram ---- */
  const waveHist = new Array(240).fill(0);
  let lastDbUi = 0;
  function drawLive(){
    if(!analyser) return;
    const td = new Float32Array(analyser.fftSize);
    analyser.getFloatTimeDomainData(td);
    let e=0, peak=0;
    for(const v of td){ e+=v*v; const a=Math.abs(v); if(a>peak) peak=a; }
    const rms = Math.sqrt(e/td.length);
    waveHist.push(Math.min(1, peak)); waveHist.shift();
    const cv = $('wave');
    if(cv){
      const g = cv.getContext('2d'), W=cv.width, H=cv.height;
      g.fillStyle='#10160f'; g.fillRect(0,0,W,H);
      g.strokeStyle='#4c9a6d'; g.lineWidth=1.5; g.beginPath();
      waveHist.forEach((p,i)=>{ const x=i/(waveHist.length-1)*W, y=H/2-p*(H/2-3); i?g.lineTo(x,y):g.moveTo(x,y); });
      g.stroke();
      g.strokeStyle='rgba(255,255,255,.25)'; g.beginPath(); g.moveTo(0,H/2); g.lineTo(W,H/2); g.stroke();
    }
    const now = performance.now();
    if(now-lastDbUi>250){ lastDbUi=now; const d=$('dbfs-live'); if(d) d.textContent=dbfsOf(rms)+' dBFS'; }
    if($('spec') && !$('spec').classList.contains('hidden')){
      const f = new Uint8Array(analyser.frequencyBinCount);
      analyser.getByteFrequencyData(f);
      const sg=$('spec'), g2=sg.getContext('2d');
      const img=g2.getImageData(1,0,sg.width-1,sg.height);
      g2.putImageData(img,-1,0);
      const bins=Math.min(f.length, sg.height);
      for(let y=0;y<bins;y++){
        const v=f[Math.floor(y/bins*f.length)]/255;
        g2.fillStyle=`rgb(${Math.floor(v*220)},${Math.floor(60+v*80)},${Math.floor(90+v*60)})`;
        g2.fillRect(sg.width-1, sg.height-1-y, 1, 1);
      }
    }
    if(peak>=0.985) msg('The microphone is clipping. Move slightly further away.','warn');
    frameId=requestAnimationFrame(drawLive);
  }
  function trackStream(on){
    $('record-dot').classList.toggle('good',on);
    const pill=$('rec-live'); if(pill) pill.classList.toggle('on',on);
  }
  if($('spec-toggle')) $('spec-toggle').onclick=()=>{ const s=$('spec'); s.classList.toggle('hidden'); $('spec-toggle').textContent=s.classList.contains('hidden')?'Show spectrogram':'Hide spectrogram'; };

  function wavEncode(buf){const n=buf.length,sr=buf.sampleRate,ch=buf.numberOfChannels;const bytes=new ArrayBuffer(44+n*2),dv=new DataView(bytes);const str=(at,s)=>{for(let i=0;i<s.length;i++)dv.setUint8(at+i,s.charCodeAt(i));};str(0,'RIFF');dv.setUint32(4,36+n*2,true);str(8,'WAVE');str(12,'fmt ');dv.setUint32(16,16,true);dv.setUint16(20,1,true);dv.setUint16(22,1,true);dv.setUint32(24,sr,true);dv.setUint32(28,sr*2,true);dv.setUint16(32,2,true);dv.setUint16(34,16,true);str(36,'data');dv.setUint32(40,n*2,true);let channels=Array.from({length:ch},(_,i)=>buf.getChannelData(i));for(let i=0;i<n;i++){let v=0;for(const c of channels)v+=c[i];v=Math.max(-1,Math.min(1,v/ch));dv.setInt16(44+i*2,v<0?v*32768:v*32767,true);}return new Blob([bytes],{type:'audio/wav'});}
  async function drawSaved(blob){
    const cv=$('wave-saved'); if(!cv||!blob) return;
    try{
      const tmp=new(window.AudioContext||window.webkitAudioContext)();
      const dec=await tmp.decodeAudioData(await blob.arrayBuffer());
      await tmp.close();
      const ch0=dec.getChannelData(0), g=cv.getContext('2d'), W=cv.width, H=cv.height, stepN=Math.max(1,Math.floor(ch0.length/W));
      g.fillStyle='#10160f'; g.fillRect(0,0,W,H); g.strokeStyle='#4c9a6d'; g.lineWidth=1; g.beginPath();
      for(let x=0;x<W;x++){ let p=0; for(let i=x*stepN;i<(x+1)*stepN&&i<ch0.length;i+=7){const a=Math.abs(ch0[i]); if(a>p)p=a;} const y=H/2-p*(H/2-2); x?g.lineTo(x,y):g.moveTo(x,y); }
      g.stroke();
      cv.classList.remove('hidden');
    }catch{ /* decorative only; upload still stands */ }
  }
  function setAudio(blob){wavBlob=blob;if(wavUrl)URL.revokeObjectURL(wavUrl);wavUrl=URL.createObjectURL(blob);$('playback').src=wavUrl;$('playback').classList.remove('hidden');$('retake').classList.remove('hidden');step('check-record',true);drawSaved(blob);}
  function resetMic(){if(recorder&&recorder.state!=='inactive')recorder.stop();if(stream)stream.getTracks().forEach(t=>t.stop());stream=null;analyser=null;if(frameId)cancelAnimationFrame(frameId);frameId=0;if(ctx)ctx.close().catch(()=>{});ctx=null;clearInterval(timer);trackStream(false);$('stop').disabled=true;$('rec').disabled=false;}
  $('rec').onclick=async()=>{try{stream=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:false,noiseSuppression:false,autoGainControl:false}});ctx=new(window.AudioContext||window.webkitAudioContext)();analyser=ctx.createAnalyser();analyser.fftSize=2048;ctx.createMediaStreamSource(stream).connect(analyser);const mime=['audio/webm;codecs=opus','audio/mp4','audio/webm'].find(x=>MediaRecorder.isTypeSupported(x));recorder=new MediaRecorder(stream,mime?{mimeType:mime}:undefined);const chunks=[];recorder.ondataavailable=e=>{if(e.data.size)chunks.push(e.data);};recorder.onstop=async()=>{try{const blob=new Blob(chunks,{type:recorder.mimeType});const tmp=new(window.AudioContext||window.webkitAudioContext)();const decoded=await tmp.decodeAudioData(await blob.arrayBuffer());const wav=wavEncode(decoded);await tmp.close();setAudio(wav);await saveLocal('pending-onboarding',wav);$('record-clock').textContent='Recording saved on this device';msg('Saved locally. You can sign in, refresh or return later without losing this recording.');}catch(e){msg('Could not process the recording: '+e.message,'error');}};recorder.start();started=Date.now();$('stop').disabled=false;$('rec').disabled=true;trackStream(true);drawLive();timer=setInterval(()=>{$('record-clock').textContent=`● RECORDING · ${Math.floor((Date.now()-started)/1000)}s`;},250);msg('Recording… read normally and stop when finished.');}catch(e){msg('Microphone access failed: '+e.message,'error');}};
  $('stop').onclick=()=>{const mr=recorder;resetMic();if(mr&&mr.state!=='inactive')mr.stop();};
  $('retake').onclick=()=>{$('playback').classList.add('hidden');msg('Ready for another take. Your previous clip remains saved until you finish the next one.');$('rec').click();};

  /* ---- upload an existing recording (Voice Memos etc): decode → WAV ---- */
  if($('upload-existing')) $('upload-existing').addEventListener('change', async ev=>{
    const f=ev.target.files&&ev.target.files[0]; if(!f) return;
    if(f.size>25*1024*1024){ $('upload-hint').textContent='That file is over 25 MB — trim it first.'; return; }
    $('upload-hint').textContent='Converting…';
    try{
      const tmp=new(window.AudioContext||window.webkitAudioContext)();
      const dec=await tmp.decodeAudioData(await f.arrayBuffer());
      await tmp.close();
      const wav=wavEncode(dec);
      setAudio(wav); await saveLocal('pending-onboarding',wav);
      $('record-clock').textContent='Existing recording ready';
      msg('Your file is converted and saved on this device. Listen above, then continue.');
      $('upload-hint').textContent='Done — it behaves exactly like a fresh recording.';
    }catch(e){ $('upload-hint').textContent='Could not read that file: '+e.message; }
    ev.target.value='';
  });

  /* ---- 5-second sound check: 2s room tone + 3s speech, advisory only ---- */
  let checking=false;
  async function soundCheck(){
    if(checking) return; checking=true;
    const hint=$('check-hint'), out=$('check-results');
    $('checkroom').disabled=true; out.classList.add('hidden'); $('check-keep').classList.add('hidden');
    let s=null, ac=null, an=null;
    const stop=()=>{ try{s.getTracks().forEach(t=>t.stop());}catch{} try{ac.close();}catch{} };
    try{
      s=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:false,noiseSuppression:false,autoGainControl:false}});
      ac=new(window.AudioContext||window.webkitAudioContext)();
      an=ac.createAnalyser(); an.fftSize=2048; ac.createMediaStreamSource(s).connect(an);
      const td=new Float32Array(an.fftSize);
      const rmsNow=()=>{ an.getFloatTimeDomainData(td); let e=0; for(const v of td)e+=v*v; return Math.sqrt(e/td.length); };
      hint.textContent='Stay silent… measuring your room (2s).';
      let nz=0, nn=0; const t0=performance.now();
      await new Promise(res=>{ const iv=setInterval(()=>{ nz+=rmsNow(); nn++; if(performance.now()-t0>2000){clearInterval(iv);res();} },100); });
      const noise=nz/Math.max(1,nn), noiseDb=dbfsOf(noise);
      hint.textContent='Now read the script out loud (3s).';
      const chunks=[]; let mr=null;
      try{ const m2=['audio/webm;codecs=opus','audio/mp4','audio/webm'].find(x=>MediaRecorder.isTypeSupported(x)); mr=new MediaRecorder(s,m2?{mimeType:m2}:undefined); mr.ondataavailable=e=>{if(e.data.size)chunks.push(e.data);}; mr.start(); }catch{}
      let sz=0, sn=0, pk=0; const t1=performance.now();
      await new Promise(res=>{ const iv=setInterval(()=>{ const r=rmsNow(); sz+=r; sn++; const p=Math.max(...td.map(Math.abs)); if(p>pk)pk=p; const left=Math.ceil((3000-(performance.now()-t1))/1000); hint.textContent=`Speaking… ${left>0?left:1}s — keep reading.`; if(performance.now()-t1>3000){clearInterval(iv);res();} },100); });
      if(mr&&mr.state!=='inactive') await new Promise(res=>{ mr.onstop=res; mr.stop(); });
      const speech=sz/Math.max(1,sn), speechDb=dbfsOf(speech), snr=Math.round((speechDb-noiseDb)*10)/10;
      const tips=[];
      if(noiseDb>-40) tips.push('The room is quite noisy — a quieter, furnished room (bedroom with door closed) will help more than any microphone.');
      if(pk>=0.985) tips.push('Clipping heard — hold the phone a little further away.');
      else if(speechDb<-30) tips.push('Your voice is quiet — hold the phone closer (15–20 cm).');
      if(snr<10) tips.push('Your voice is barely above the room noise — move closer or quieter.');
      else if(snr<20) tips.push('Usable. A quieter spot would make it cleaner.');
      else tips.push('Sounds good — you are ready to record your audition.');
      out.innerHTML='';
      const line=(k,v)=>{ const d=document.createElement('div'); d.className='checkrow'; const a=document.createElement('span'); a.textContent=k; const b=document.createElement('b'); b.textContent=v; d.append(a,b); out.append(d); };
      line('Room noise', noiseDb+' dBFS'); line('Your voice', speechDb+' dBFS'); line('Voice above room', snr+' dB');
      const adv=document.createElement('div'); adv.className='note'; adv.textContent='Advice (not a verdict): '+tips.join(' '); out.append(adv);
      out.classList.remove('hidden');
      if(chunks.length){
        try{
          const blob=new Blob(chunks,{type:mr.mimeType});
          const t2=new(window.AudioContext||window.webkitAudioContext)();
          const dec=await t2.decodeAudioData(await blob.arrayBuffer());
          await t2.close();
          const wav=wavEncode(dec);
          $('check-playback').src=URL.createObjectURL(wav);
          $('check-playback').classList.remove('hidden');
          $('check-keep').classList.remove('hidden');
          $('check-keep').onclick=async()=>{ setAudio(wav); await saveLocal('pending-onboarding',wav); $('record-clock').textContent='Sound-check take kept as your audition'; msg('Kept. It is saved on this device — continue below when ready.'); };
        }catch{}
      }
      hint.textContent='Check complete. Nothing is uploaded; this stays on your phone.';
    }catch(e){ hint.textContent='Microphone unavailable: '+e.message; }
    stop(); $('checkroom').disabled=false; checking=false;
  }
  if($('checkroom')) $('checkroom').onclick=soundCheck;

  function markSigned(name){signedIn=true;$('user-label').textContent=name||'Signed in with Google';$('account-title').textContent='Account connected';$('account-copy').textContent='You can now save and publish your recording.';$('google-signin').textContent='Connected ✓';$('auth-button').textContent='Account connected';step('check-account',true);}
  $('google-signin').onclick=$('auth-button').onclick=async()=>{if(DEMO){markSigned('Preview account');localStorage.setItem('hv-demo-signedin','1');return;}if(wavBlob)await saveLocal('pending-onboarding',wavBlob);location.assign(API+'/api/auth/google/start');};
  async function request(path,opts={}){const r=await fetch(API+path,{...opts,credentials:'include'});if(!r.ok){let info;try{info=await r.json();}catch{info=await r.text();}throw new Error(typeof info==='string'?info:JSON.stringify(info));}return r.json();}
  async function analyze(){if(!wavBlob){msg('Record or restore a sample before generating your profile.','warn');return;}if(!signedIn){msg('Connect your Google account first, then we can upload and analyse your recording.','warn');return;}$('analyze').disabled=true;$('analyze').textContent='Analysing your recording…';try{let draft,meta;if(DEMO){await new Promise(r=>setTimeout(r,500));sampleSha='demo-voice-sample';draft={display_name:'',languages:['en'],accent_description:{text:'',source:'declared'},bio:'A natural, conversational voice. Add your own description before publishing.',suggested_categories:['Storytelling','YouTube narration']};meta='Preview draft · not actual AI analysis';}else{const data=await request('/v1/narrators/me/sample?language=en&kind=natural',{method:'POST',headers:{'Content-Type':'audio/wav'},body:wavBlob});sampleSha=data.sample;const answer=await request('/v1/narrators/me/profile',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({draft_from_sample:true})});draft=answer.draft||{};meta=data.transcript_provider==='none'?'Transcription unavailable · edit manually':`Analysis source: ${data.transcript_provider||'unknown'}`;}
  $('name').value=draft.display_name||'';$('lang').value=(draft.languages||['en']).join(', ');$('accent').value=draft.accent_description?.text||'';$('bio').value=draft.bio||'';$('categories').value=(draft.suggested_categories||['Storytelling','YouTube narration']).join(', ');$('analysis-label').textContent=meta;$('profile-editor').classList.remove('hidden');draftReady=true;step('check-profile',true);updatePublish();$('profile-editor').scrollIntoView({behavior:'smooth',block:'center'});}catch(e){msg('Analysis failed: '+e.message,'error');}finally{$('analyze').disabled=false;$('analyze').textContent='Regenerate profile draft';}}
  $('analyze').onclick=analyze;
  function updatePublish(){const valid=/^[A-Za-z0-9_.-]{2,30}$/.test($('handle').value.trim())&&$('name').value.trim()&&$('consent').checked&&draftReady&&signedIn; $('publish').disabled=!valid; $('publish-note').textContent=valid?'Ready to publish your public portfolio.':'Enter a display name and unique handle, then explicitly approve the sample.';}
  for(const id of ['name','handle','consent'])$(id).addEventListener('input',updatePublish);
  $('publish').onclick=async()=>{if($('publish').disabled)return;$('publish').disabled=true;const name=$('name').value.trim(),handle=$('handle').value.trim();const langs=$('lang').value.split(',').map(x=>x.trim()).filter(Boolean);const categories=$('categories').value.split(',').map(x=>x.trim()).filter(Boolean);const profile={display_name:name,bio:$('bio').value.trim(),accent_description:{text:$('accent').value.trim(),source:'self_declared'},languages:langs,categories,published:true};try{if(DEMO){localStorage.setItem('hv-demo-profile',JSON.stringify({...profile,handle,samples:[{sha256:sampleSha,language:langs[0]||'English',kind:'natural',consented_public:true}]}));}else{await request('/v1/narrators/me/profile',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({handle,languages:langs.map(x=>x.toLowerCase().slice(0,2)),prefs:{categories}})});await request('/v1/narrators/me/profile',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({publish:true,profile,consent_samples:[sampleSha]})});}const url='portfolio.html?h='+encodeURIComponent(handle)+(DEMO?'&demo=1':'');$('success').classList.remove('hidden');$('success').replaceChildren(document.createTextNode('Portfolio published '+(DEMO?'locally in preview mode':'to HumanVoiced')+'. '));const a=document.createElement('a');a.href=url;a.textContent='View your portfolio →';a.style.color='#166d4b';a.style.fontWeight='700';$('success').append(a);step('check-publish',true);$('success').scrollIntoView({behavior:'smooth',block:'center'});}catch(e){msg('Could not publish: '+e.message,'error');}finally{updatePublish();}};
  async function boot(){try{const saved=await getLocal('pending-onboarding');if(saved){setAudio(saved);msg('Your previous recording was restored from this device.');$('record-clock').textContent='Saved recording restored';}}catch(e){msg('Local recording storage unavailable: '+e.message,'warn');}
  if(DEMO){$('user-label').textContent='Interactive preview';$('account-copy').textContent='Preview mode: everything stays on this device.';if(localStorage.getItem('hv-demo-signedin')==='1')markSigned('Preview account');}
  else if(new URLSearchParams(location.search).get('login')==='ok'){markSigned('Google sign-in returned');$('account-copy').textContent='Google returned successfully. Server verifies your session when you upload.';}
  else{try{const r=await request('/api/auth/me');if(r.authenticated)markSigned(r.name||r.email||'Signed in');}catch{ /* Optional GET /api/auth/me for reliable status; server upload still enforces auth. */}}
  }
  boot();
})();
