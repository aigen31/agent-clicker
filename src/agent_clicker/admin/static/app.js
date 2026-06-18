function fmtTs(s){ if(!s) return ''; return s.replace('T',' ').slice(0,19); }

function tasksPage(){
  return {
    tasks:[], total:0, page:1, page_size:25,
    filters:{ status:'', ad_id:null },
    newTask:{ ad_id:1, link:'https://example.com', description:'Test task', cookies:'', proxy_host:'', proxy_port:null, proxy_login:'', proxy_password:'' },
    async load(){
      const params=new URLSearchParams();
      if(this.filters.status) params.set('status', this.filters.status);
      if(this.filters.ad_id) params.set('ad_id', this.filters.ad_id);
      params.set('page', this.page); params.set('page_size', this.page_size);
      const r=await fetch('/api/tasks?'+params); const j=await r.json();
      this.tasks=j.items; this.total=j.total;
    },
    next(){ this.page++; this.load(); },
    prev(){ if(this.page>1){ this.page--; this.load(); } },
    fmtTs,
    async create(){
      const payload={ ad_id:this.newTask.ad_id, link:this.newTask.link, description:this.newTask.description };
      if(this.newTask.cookies && this.newTask.cookies.trim()) payload.cookies=this.newTask.cookies.trim();
      if(this.newTask.proxy_host) payload.proxy_host=this.newTask.proxy_host;
      if(this.newTask.proxy_port) payload.proxy_port=this.newTask.proxy_port;
      if(this.newTask.proxy_login) payload.proxy_login=this.newTask.proxy_login;
      if(this.newTask.proxy_password) payload.proxy_password=this.newTask.proxy_password;
      const r=await fetch('/api/tasks',{ method:'POST', headers:{'content-type':'application/json'}, body: JSON.stringify(payload) });
      if(r.ok){ this.newTask.cookies=''; this.load(); } else { alert('error: '+await r.text()); }
    },
    async retry(id){ await fetch('/api/tasks/'+id+'/retry',{method:'POST'}); this.load(); },
    async del(id){ if(!confirm('delete '+id+'?')) return; await fetch('/api/tasks/'+id,{method:'DELETE'}); this.load(); },
  };
}

function adProxyPage(){
  return {
    configs:[], status_msg:'',
    form:{ ad_id:0, proxy_host:'dc.oxylabs.io', proxy_port:8000, proxy_login:'', proxy_password:'' },
    async load(){
      const r=await fetch('/api/ad-proxy'); this.configs=await r.json();
    },
    edit(c){
      this.form.ad_id=c.ad_id; this.form.proxy_host=c.proxy_host; this.form.proxy_port=c.proxy_port;
      this.form.proxy_login=c.proxy_login||''; this.form.proxy_password=c.proxy_password||'';
    },
    async save(){
      const body={ ad_id:this.form.ad_id, proxy_host:this.form.proxy_host, proxy_port:this.form.proxy_port, proxy_login:this.form.proxy_login||null, proxy_password:this.form.proxy_password||null };
      const r=await fetch('/api/ad-proxy/'+this.form.ad_id,{ method:'PUT', headers:{'content-type':'application/json'}, body:JSON.stringify(body) });
      if(r.ok){ this.status_msg='saved'; this.load(); this.form={ ad_id:0, proxy_host:'dc.oxylabs.io', proxy_port:8000, proxy_login:'', proxy_password:'' }; }
      else { this.status_msg='error: '+await r.text(); }
      setTimeout(()=>{this.status_msg='';},2000);
    },
    async del(ad_id){ if(!confirm('delete proxy for ad '+ad_id+'?')) return; await fetch('/api/ad-proxy/'+ad_id,{method:'DELETE'}); this.load(); },
  };
}

function settingsPage(){
  return {
    json:{ agent:'', browser:'', worker:'' },
    status:{ agent:'', browser:'', worker:'' },
    async load(){
      for(const s of ['agent','browser','worker']){
        const r=await fetch('/api/settings/'+s); const j=await r.json();
        this.json[s]=JSON.stringify(j,null,2);
      }
    },
    async save(s){
      try{
        const body=JSON.parse(this.json[s]);
        const r=await fetch('/api/settings/'+s,{method:'PUT',headers:{'content-type':'application/json'},body:JSON.stringify(body)});
        this.status[s]=r.ok?'saved':('error: '+await r.text());
        setTimeout(()=>{this.status[s]='';},2000);
      }catch(e){ this.status[s]='bad json: '+e.message; }
    },
  };
}

function logsPage(){
  return {
    lines:[], ws:null, level:'INFO', task_id:'', worker_id:'',
    connect(){
      const params=new URLSearchParams();
      if(this.level) params.set('level', this.level);
      if(this.task_id) params.set('task_id', this.task_id);
      if(this.worker_id) params.set('worker_id', this.worker_id);
      const proto = location.protocol==='https:'?'wss:':'ws:';
      this.ws = new WebSocket(proto+'//'+location.host+'/ws/logs?'+params);
      this.ws.onmessage=(e)=>{
        try{ const r=JSON.parse(e.data); this.lines.push(r); if(this.lines.length>500) this.lines.splice(0,this.lines.length-500); }catch(_e){}
      };
    },
    reconnect(){ if(this.ws) this.ws.close(); this.connect(); },
  };
}
