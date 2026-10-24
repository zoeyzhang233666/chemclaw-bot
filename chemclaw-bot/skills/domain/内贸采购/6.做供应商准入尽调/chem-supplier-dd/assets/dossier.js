(function(){
  const body=document.body;
  // filter
  document.querySelectorAll('.fbtn').forEach(b=>{
    b.addEventListener('click',()=>{
      document.querySelectorAll('.fbtn').forEach(x=>x.classList.remove('on'));
      b.classList.add('on');
      const f=b.dataset.f;
      document.querySelectorAll('[data-s]').forEach(el=>{
        const s=(el.dataset.s||'').split(',');
        el.classList.toggle('dim', !(f==='all'||s.includes(f)));
      });
    });
  });
  // nav active
  const links=[...document.querySelectorAll('.rail nav a')];
  const secs=links.map(a=>document.querySelector(a.getAttribute('href'))).filter(Boolean);
  const io=new IntersectionObserver(es=>{
    es.forEach(e=>{
      if(e.isIntersecting){
        links.forEach(a=>a.classList.toggle('on',a.getAttribute('href')==='#'+e.target.id));
      }
    });
  },{rootMargin:'-15% 0px -70% 0px'});
  secs.forEach(s=>io.observe(s));
  // checklist progress
  function prog(box){
    const all=box.querySelectorAll('.ci input');
    const done=box.querySelectorAll('.ci input:checked');
    const pct=all.length?Math.round(done.length/all.length*100):0;
    box.querySelector('.prog .bar i').style.width=pct+'%';
    box.querySelector('.prog .num').textContent=done.length+' / '+all.length;
  }
  document.querySelectorAll('.chkbox').forEach(box=>{
    box.querySelectorAll('.ci input').forEach(i=>{
      i.addEventListener('change',()=>{
        i.closest('.ci').classList.toggle('done',i.checked);
        prog(box);
      });
    });
    prog(box);
  });
  // select all
  function syncPickAll(){
    const ps=[...document.querySelectorAll('.pick input')];
    const btn=document.getElementById('pickall');
    if(btn) btn.textContent=ps.every(p=>p.checked)?'全不选':'全选';
  }
  document.querySelectorAll('.pick input').forEach(i=>{
    i.addEventListener('change',()=>{
      i.closest('section').classList.toggle('picked',i.checked);
      syncPickAll();
    });
  });
  document.querySelectorAll('.pick input').forEach(i=>{
    i.closest('section').classList.toggle('picked',i.checked);
  });
  syncPickAll();
  document.getElementById('pickall')?.addEventListener('click',()=>{
    const ps=document.querySelectorAll('.pick input');
    const allOn=[...ps].every(p=>p.checked);
    ps.forEach(p=>{p.checked=!allOn;p.dispatchEvent(new Event('change'));});
  });
  function chosen(){return [...document.querySelectorAll('.pick input:checked')].map(p=>p.closest('section'));}
  // export html
  document.getElementById('dl')?.addEventListener('click',()=>{
    const list=chosen();
    if(!list.length){alert('请先勾选需要导出的模块（每个模块标题右侧的复选框）。');return;}
    const css=document.getElementById('css').textContent;
    const head=document.querySelector('.exporthead').outerHTML.replace('display:none','display:block');
    const inner=list.map(s=>{s.classList.add('picked');return s.outerHTML;}).join('\n');
    const doc='<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'+
      '<meta name="viewport" content="width=device-width,initial-scale=1">'+
      '<title>'+document.title+'（摘录）</title><style>'+css+
      '.exporthead{display:block!important}</style></head><body class="export">'+
      '<div class="wrap">'+head+inner+'</div></body></html>';
    const blob=new Blob([doc],{type:'text/html;charset=utf-8'});
    const a=document.createElement('a');
    a.href=URL.createObjectURL(blob);
    a.download='供应商准入尽调底稿_山东海化_纯碱_摘录.html';
    a.click();
    setTimeout(()=>URL.revokeObjectURL(a.href),4000);
  });
  // print
  document.getElementById('prt')?.addEventListener('click',()=>{
    const list=chosen();
    if(!list.length){alert('请先勾选需要导出的模块。');return;}
    body.classList.add('export');
    setTimeout(()=>{window.print();body.classList.remove('export');},120);
  });
})();
