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
async function pingHealth(timeout=5000){const base=apiBase();const response=await fetch(base+'/health',{method:'GET',cache:'no-store',signal:AbortSignal.timeout(timeout)});if(!response.ok)throw new Error('api_unavailable');return response}
function setConnected(){const btn=$('#connectBtn');btn.dataset.ready='1';btn.textContent='Connected';btn.disabled=false;$('#wakeBtn').textContent='API Online';setStatus('ready','API Online');setMessage('Backend is responding. Note: real file uploads still need storage integration.')}
function setOffline(message='Backend is unreachable. Try waking it up again.'){setStatus('','Offline');setMessage(message);const btn=$('#connectBtn');btn.dataset.ready='';btn.textContent='Retry connection';btn.disabled=false;$('#wakeBtn').textContent='⚡ Wake Up'}
async function wakeApi(){if(wakeInProgress)return;wakeInProgress=true;const btn=$('#connectBtn'),wake=$('#wakeBtn');btn.disabled=true;wake.disabled=true;wake.textContent='Waking up…';setStatus('waiting','Waking up');setMessage('Contacting the backend. A sleeping service may take a little while to start.');
 try{for(let i=0;i<18;i++){try{await pingHealth(5000);setConnected();notify('SKYGRID API is online.');return}catch(e){}if(i<17)await new Promise(r=>setTimeout(r,4000))}setOffline('The API did not respond within about 90 seconds. You can retry.');notify('Backend did not respond within 90 seconds.')}
 finally{wakeInProgress=false;btn.disabled=false;wake.disabled=false;if(!btn.dataset.ready)wake.textContent='⚡ Wake Up'}
}
$('#connectBtn').addEventListener('click',wakeApi);$('#wakeBtn').addEventListener('click',wakeApi);
function startKeepAlive(){clearInterval(keepAliveTimer);const keepAlive=async()=>{try{await pingHealth(8000);if(!wakeInProgress)setConnected()}catch(e){if(!wakeInProgress)setOffline('Automatic health check could not reach the backend. Use Wake Up to retry.')}};keepAlive();keepAliveTimer=setInterval(keepAlive,10*60*1000)}
document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='visible'&&!wakeInProgress){pingHealth(5000).then(()=>setConnected()).catch(()=>setOffline())}});
startKeepAlive();