const $=s=>document.querySelector(s);
const fileInput=$('#fileInput');
const toast=$('#toast');
const DEFAULT_API_URL='https://skygrid-backend.onrender.com';
let toastTimer, keepAliveTimer, wakeInProgress=false;
function notify(msg){toast.textContent=msg;toast.classList.add('show');clearTimeout(toastTimer);toastTimer=setTimeout(()=>toast.classList.remove('show'),3200)}
function apiBase(){return (window.SKYGRID_API_URL||localStorage.getItem('skygrid_api_url')||DEFAULT_API_URL).trim().replace(/\/$/,'')}
function setStatus(state,label){const status=$('#status'),top=$('#apiStatusTop');status.className='status '+state;status.innerHTML='<i></i> '+label;top.className='api-status '+state;top.innerHTML='<i></i> '+label; }
function setMessage(message){$('#connectText').textContent=message}
function chooseFiles(){if(!$('#connectBtn').dataset.ready){notify('Connect to your cloud before uploading.');return}fileInput.click()}
$('#uploadTop').addEventListener('click',chooseFiles);$('#uploadHero').addEventListener('click',chooseFiles);$('#emptyUpload').addEventListener('click',chooseFiles);
fileInput.addEventListener('change',()=>{if(fileInput.files.length)notify(fileInput.files.length+' file(s) selected. Storage upload will be enabled after backend integration.');fileInput.value=''});
document.querySelectorAll('.nav-item').forEach(b=>b.addEventListener('click',()=>{document.querySelectorAll('.nav-item').forEach(n=>n.classList.remove('active'));b.classList.add('active');const labels={all:'All files',photos:'Photos',videos:'Videos',shared:'Shared with me',groups:'Shared spaces'};$('#crumbTitle').textContent=labels[b.dataset.view];$('#sectionTitle').textContent=b.dataset.view==='all'?'Recent files':labels[b.dataset.view];notify(labels[b.dataset.view]+' view selected.')}));
$('#search').addEventListener('input',e=>{if(e.target.value.trim())notify('Search will work when file metadata is connected.')});
async function pingHealth(timeout=5000){const response=await fetch(apiBase()+'/health',{method:'GET',cache:'no-store',signal:AbortSignal.timeout(timeout)});if(!response.ok)throw new Error('api_unavailable');return response}
function setConnected(){const btn=$('#connectBtn'),wake=$('#wakeBtn');btn.dataset.ready='1';btn.textContent='Connected';btn.disabled=false;wake.textContent='⚡ Wake Up';wake.hidden=true;setStatus('ready','API Online');setMessage('Backend is responding. Note: real file uploads still need storage integration.')}
function setOffline(message='Backend is unreachable. Try waking it up again.'){setStatus('','Offline');setMessage(message);const btn=$('#connectBtn'),wake=$('#wakeBtn');btn.dataset.ready='';btn.textContent='Retry connection';btn.disabled=false;wake.textContent='⚡ Wake Up';wake.hidden=false}
async function wakeApi(){if(wakeInProgress)return;wakeInProgress=true;const btn=$('#connectBtn'),wake=$('#wakeBtn');btn.disabled=true;wake.disabled=true;wake.hidden=false;wake.textContent='Waking up…';setStatus('waiting','Waking up');setMessage('Contacting the backend. A sleeping service may take a little while to start.');
 try{for(let i=0;i<18;i++){try{await pingHealth(5000);setConnected();notify('SKYGRID API is online.');return}catch(e){}if(i<17)await new Promise(r=>setTimeout(r,4000))}setOffline('The API did not respond within about 90 seconds. Tap Wake Up to retry.');notify('Backend did not respond within 90 seconds.')}
 finally{wakeInProgress=false;btn.disabled=false;wake.disabled=false;if(!btn.dataset.ready){wake.hidden=false;wake.textContent='⚡ Wake Up'}}
}
$('#connectBtn').addEventListener('click',wakeApi);$('#wakeBtn').addEventListener('click',wakeApi);
function startKeepAlive(){clearInterval(keepAliveTimer);const keepAlive=async()=>{try{await pingHealth(8000);if(!wakeInProgress)setConnected()}catch(e){if(!wakeInProgress)setOffline('Backend fetch failed. Tap Wake Up to retry.')}};keepAlive();keepAliveTimer=setInterval(keepAlive,10*60*1000)}
document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='visible'&&!wakeInProgress){pingHealth(5000).then(()=>setConnected()).catch(()=>setOffline('Backend fetch failed. Tap Wake Up to retry.'))}});
startKeepAlive();
/* SKYGRID Telegram OTP authentication. */
(function setupAuth(){
 const gate=$('#authGate'),form=$('#authForm');
 if(!gate||!form)return;
 const phone=$('#authPhone'),code=$('#authCode'),password=$('#authTelegramPassword');
 const codeWrap=$('#codeWrap'),passwordWrap=$('#passwordWrap');
 const error=$('#authError'),submit=$('#authSubmit'),title=$('#authTitle'),subtitle=$('#authSubtitle'),switchText=$('#authSwitch');
 const tokenKey='skygrid_access_token';
 let phase='phone',challengeId='',busy=false;
 function showError(message){error.textContent=message||''}
 function setPhase(next){
  phase=next;showError('');
  codeWrap.hidden=phase==='phone'||phase==='password';
  passwordWrap.hidden=phase!=='password';
  phone.disabled=phase!=='phone';
  code.required=phase==='code';
  password.required=phase==='password';
  title.innerHTML=phase==='phone'?'Welcome to <span>SKYGRID</span>':phase==='code'?'Verify your <span>Telegram</span> code':'Telegram <span>2-step verification</span>';
  subtitle.textContent=phase==='phone'?'Sign in securely using your Telegram account.':phase==='code'?'Enter the code Telegram sent you.':'Enter your Telegram 2-step verification password.';
  submit.textContent=phase==='phone'?'Send Telegram code':phase==='code'?'Verify and sign in':'Verify password';
  switchText.textContent=phase==='phone'?'Your code is sent by Telegram. Never share it with anyone.':'If the request expires, reload the page and start again.';
 }
 function enter(user){
  gate.hidden=true;
  const displayName=user?.display_name||user?.email?.split('@')[0]||'User';
  document.querySelectorAll('.profile b').forEach(el=>el.textContent=displayName);
  document.querySelectorAll('.avatar').forEach(el=>{if(el.textContent.trim()==='A')el.textContent=displayName.slice(0,1).toUpperCase()});
  notify('Signed in successfully.');
 }
 async function request(path,options={}){
  const response=await fetch(apiBase()+path,{...options,headers:{'Content-Type':'application/json',...(options.headers||{})},signal:AbortSignal.timeout(15000)});
  let data={};try{data=await response.json()}catch{}
  if(!response.ok)throw new Error(data.detail||'Request failed ('+response.status+').');
  return data;
 }
 async function restore(){
  const token=localStorage.getItem(tokenKey);
  if(!token){gate.hidden=false;return}
  try{const user=await request('/auth/me',{headers:{Authorization:'Bearer '+token}});enter(user)}
  catch(e){localStorage.removeItem(tokenKey);gate.hidden=false;showError('Session expired. Please sign in again.')}
 }
 form.addEventListener('submit',async e=>{
  e.preventDefault();if(busy)return;busy=true;submit.disabled=true;showError('');
  try{
   if(phase==='phone'){
    const result=await request('/auth/telegram/send-code',{method:'POST',body:JSON.stringify({phone:phone.value.trim()})});
    challengeId=result.challenge_id;setPhase('code');code.focus();notify('Telegram verification code requested.');
   }else{
    const body={challenge_id:challengeId};
    if(phase==='code')body.code=code.value.trim();
    if(phase==='password')body.password=password.value;
    const result=await request('/auth/telegram/verify-code',{method:'POST',body:JSON.stringify(body)});
    if(result.requires_password){setPhase('password');password.focus();return}
    if(!result.access_token)throw new Error('API ne access token return nahi kiya.');
    localStorage.setItem(tokenKey,result.access_token);
    const user=await request('/auth/me',{headers:{Authorization:'Bearer '+result.access_token}});
    enter(user);
   }
  }catch(err){
   const message=err.name==='TimeoutError'||err.name==='AbortError'?'Backend timeout. Wake Up karke dobara try karo.':err.message;
   showError(message==='Failed to fetch'?'Backend tak fetch nahi pahucha. API/CORS status check karo.':message);
  }finally{busy=false;submit.disabled=false}
 });
 setPhase('phone');restore();
})();