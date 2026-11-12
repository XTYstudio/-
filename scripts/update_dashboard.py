#!/usr/bin/env python3
"""Extract candidate skill tags from added postings and rebuild dashboard files.
Rule matching is a transparent first pass, not a web crawler or autonomous Agent.
"""
from pathlib import Path
import csv, json, re, html

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data'
POSTINGS=DATA/'postings.csv'
SKILLS=DATA/'skills.csv'
INBOX=DATA/'new_postings.csv'
OUT=ROOT/'index.html'
POST_FIELDS=['job_id','title','company','location','date_posted','page_updated_or_first_seen','job_type','experience_requirement','source_type','source_url','status_note','analysis_excerpt','review_status']
SKILL_FIELDS=['job_id','title','skill_raw','skill_normalized','skill_category','requirement_level','evidence_quote','source_url','confidence','review_note']

# Terms are intentionally explicit. The audit log explains known limitations and corrections.
RULES=[
 (r'Python\s*(?:or|/|或)\s*R|R\s*(?:or|/|或)\s*Python','Python/R','编程语言'),
 (r'\bSQL\b','SQL','技术技能'),
 (r'\bPython\b','Python','技术技能'),
 (r'\bR\b(?=\s*(?:,|/|、|and|or|语言|等))','R','技术技能'),
 (r'\bExcel\b|VBA','Excel / VBA','工具平台'),
 (r'Tableau|Grafana|Power\s*BI|Quick\s*BI|BI\b','BI与数据可视化','工具平台'),
 (r'dashboard|看板|数据可视化','数据看板与可视化','方法能力'),
 (r'A\s*/\s*B\s*(?:tests?|实验)|A/B实验|实验分析|controlled experiments?','实验设计','方法能力'),
 (r'causal inference|因果推断','因果推断','方法能力'),
 (r'data mining|数据挖掘','数据挖掘','方法能力'),
 (r'machine learning|机器学习','机器学习','技术方法'),
 (r'customer segmentation|user segmentation|用户分群|用户画像','用户分群与画像','方法能力'),
 (r'KPI|metrics|指标体系|核心指标','指标设计与监控','方法能力'),
 (r'forecast(ing)?|预测','预测分析','方法能力'),
 (r'agent evaluation|Agent evaluation|AI Agent|\bAgent\b|智能体','Agent与AI应用','AI应用'),
 (r'AI product|AI数据产品|AI产品','AI产品规划','AI产品能力'),
 (r'evaluation framework|evaluation criteria|评测框架|评估标准','模型评测框架','评估方法'),
 (r'data governance|数据治理','数据治理','数据管理'),
 (r'anomaly detection|异常检测','异常检测','分析方法'),
 (r'big data|大数据','大数据技术','技术工具'),
 (r'data exploration|data validation|数据探查|数据校验|数据验证','数据探查与校验','数据质量'),
 (r'LLM|large language model|大模型','大语言模型应用','AI应用'),
 (r'AI tools?|AI-assisted|AI工具|AI取数|AI数据体系','AI工具使用','AI应用'),
 (r'data cleaning|cleaning data|数据清洗','数据清洗','数据处理'),
 (r'data analysis|analytics|数据分析|商业分析|分析能力','数据分析','分析方法'),
 (r'Excel|VBA','Excel / VBA','工具平台'),
 (r'forecast(ing)?|预测','预测分析','方法能力'),
 (r'causal inference|因果推断','因果推断','方法能力'),
 (r'data model(ing)?|数据建模','数据建模','数据能力'),
 (r'data collection|数据收集','数据收集','数据处理'),
 (r'data extract(ion)?|数据提取|取数','数据提取','数据处理'),
 (r'data cleaning|数据清洗','数据清洗','数据处理'),
 (r'customer journey|客户旅程','客户旅程分析','分析方法'),
 (r'market intelligence|市场情报|竞品分析','市场情报与竞品分析','分析方法'),
 (r'financial acumen|financial analysis|财务分析|预算|forecasting','财务分析','分析方法'),
 (r'project management|项目管理','项目管理','项目能力'),
 (r'cross-functional|cross functional|跨团队|跨职能','沟通与跨团队协作','软技能'),
 (r'data storytelling|business stories|数据故事|洞察表达','数据洞察表达','沟通能力'),
 (r'Agent evaluation|Agent评测|评测体系','Agent评测','评估方法'),
 (r'automated evaluation|automated testing|自动化评测|自动化测试','自动化评测','技术方法'),
 (r'Python\s*/\s*Go\s*/\s*Java\s*/\s*TypeScript','Python/Go/Java/TypeScript','编程语言'),
 (r'Python\s*(?:or|/|或)\s*R|R\s*(?:or|/|或)\s*Python','Python/R','编程语言'),
 (r'CI/CD|Git|containerization|容器化','软件研发流程','工程能力'),
 (r'API integration|API集成|MCP','API与MCP集成','技术工具'),
 (r'KPI|metrics|指标体系|核心指标','指标设计与监控','方法能力'),
 (r'eCPM|ROI|CTR|LTV|广告效果指标','广告效果指标','方法能力'),
 (r'Salesforce','Salesforce','工具平台'),
 (r'BI dashboard|BI报表','BI报表','工具平台'),
 (r'product requirements|PRD|需求PRD','需求分析与PRD','产品能力'),
 (r'knowledge base|知识库','数据知识库构建','数据能力'),
 (r'communication|沟通|stakeholder|协作','沟通与跨团队协作','软技能'),
 (r'Spark|Flink|Hive|Kafka','大数据技术','技术工具'),
]

def read_csv(p):
 if not p.exists(): return []
 with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def write_csv(p,rows,fields):
 with p.open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)

def classify_level(text,start):
 before=text[:start].lower()
 preferred=max(before.rfind('preferred:'),before.rfind('preferred qualifications'),before.rfind('优先'))
 required=max(before.rfind('minimum:'),before.rfind('minimum qualifications'),before.rfind('required:'),before.rfind('必需'))
 if preferred>required:return '优先'
 if required>=0:return '必需'
 return '描述不清（需回原文确认）'

def extract(job):
 text=job.get('analysis_excerpt','') or job.get('description','')
 found=[];occupied=[];norms=set()
 for pattern,norm,category in RULES:
  for m in re.finditer(pattern,text,re.I):
   if any(m.start()<b and m.end()>a for a,b in occupied):continue
   if norm in norms:continue
   # Avoid obvious negated mentions; user must still inspect context for nuanced cases.
   pre=text[max(0,m.start()-32):m.start()].lower()
   if re.search(r'(?:not|required|without|no)\s+(?:\w+\s+){0,2}$',pre) or re.search(r'(?:不要求|无需|不需要)\s*$',pre):continue
   norms.add(norm);occupied.append((m.start(),m.end()))
   found.append({'job_id':job['job_id'],'title':job['title'],'skill_raw':m.group(0),'skill_normalized':norm,'skill_category':category,'requirement_level':classify_level(text,m.start()),'evidence_quote':m.group(0),'source_url':job['source_url'],'confidence':'中（规则初筛）','review_note':'自动关键词匹配；必须回原文确认语境、技能类别和必需/优先属性'})
 return found

def dashboard(jobs,skills):
 byskill={}
 for s in skills:byskill.setdefault(s['skill_normalized'],set()).add(s['job_id'])
 bars=sorted([{'skill':k,'count':len(v),'pct':round(100*len(v)/max(len(jobs),1))} for k,v in byskill.items()],key=lambda x:(-x['count'],x['skill']))
 data={'jobs':jobs,'skills':skills,'bars':bars,'n':len(jobs),'companies':len(set(j['company'] for j in jobs))}
 payload=json.dumps(data,ensure_ascii=False).replace('</','<\\/')
 template='''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>中国大陆数据与AI岗位技能观察</title><style>
:root{--ink:#19243a;--muted:#69758a;--line:#e5e9f0;--blue:#365ff5;--bg:#f4f6fa}*{box-sizing:border-box}body{margin:0;background:var(--bg);font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:var(--ink)}main{max-width:1200px;margin:34px auto;padding:0 22px}.top{display:flex;justify-content:space-between;align-items:end;margin-bottom:22px;gap:20px}.eyebrow{font-size:12px;color:var(--blue);font-weight:700;letter-spacing:.08em}h1{font-size:30px;margin:6px 0}.muted{color:var(--muted)}.card{background:#fff;border:1px solid var(--line);border-radius:14px;padding:18px;box-shadow:0 3px 15px #2538580d}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:13px}.metric{font-size:28px;font-weight:750;margin:4px 0}.layout{display:grid;grid-template-columns:.9fr 1.1fr;gap:14px;margin-top:14px}.title{font-size:17px;margin:0 0 12px}.bar{display:grid;grid-template-columns:145px 1fr 52px;align-items:center;gap:9px;margin:10px 0;font-size:13px}.track{height:10px;border-radius:99px;background:#edf0f6;overflow:hidden}.fill{height:100%;border-radius:99px;background:linear-gradient(90deg,#426aff,#90a5ff)}select{padding:9px 11px;border:1px solid var(--line);border-radius:8px;background:#fff;color:var(--ink);margin:0 6px 10px 0}.tablewrap{overflow:auto}table{width:100%;border-collapse:collapse;min-width:920px;font-size:13px}td,th{text-align:left;padding:10px;border-bottom:1px solid var(--line);vertical-align:top}th{color:var(--muted);font-weight:650}td a{color:var(--blue);text-decoration:none}.small{font-size:12px;color:var(--muted)}.pill{display:inline-block;background:#eef2ff;color:#3556cb;border-radius:99px;padding:3px 8px;font-size:11px}.warn{background:#fff8e9;border-color:#efdfb7;margin-top:14px}.jobs{margin-top:14px}.job{border-top:1px solid var(--line);padding:12px 0}.job:first-of-type{border-top:0}.job a{color:var(--blue);font-weight:700;text-decoration:none}.foot{font-size:12px;color:var(--muted);margin:16px 2px 42px}@media(max-width:800px){.grid{grid-template-columns:repeat(2,1fr)}.layout{grid-template-columns:1fr}.top{display:block}h1{font-size:24px}.bar{grid-template-columns:120px 1fr 46px}}
</style></head><body><main><div class="top"><div><div class="eyebrow">PURPOSIVE SAMPLE · MAINLAND CHINA</div><h1>数据分析与 AI 数据工作岗位观察</h1><div class="muted">公开岗位要求整理 · 可筛选 · 技能证据可回到来源页</div></div><div class="small">样本快照：2026-11-12</div></div><div id="metrics" class="grid"></div>
<div class="layout"><section class="card"><h2 class="title">技能覆盖岗位数</h2><div class="small">分母为筛选后的岗位数；每个岗位同一技能只计一次</div><div id="bars"></div></section><section class="card"><h2 class="title">岗位样本</h2><select id="company"><option value="all">所有公司</option></select><select id="city"><option value="all">所有城市</option></select><select id="type"><option value="all">所有岗位类型</option></select><div id="jobs" class="small"></div></section></div>
<section class="card" style="margin-top:14px"><h2 class="title">逐岗位技能证据</h2><div class="tablewrap"><table><thead><tr><th>岗位 / 公司</th><th>技能标签</th><th>分类</th><th>要求级别</th><th>原文短摘</th><th>来源</th></tr></thead><tbody id="evidence"></tbody></table></div></section>
<section class="card warn"><h2 class="title">样本与解释边界</h2><div>这是目的性样本：按“数据分析、商业分析、数据产品或 AI 数据工作流相关”筛选公开岗位，不是随机抽样。它跨公司、地区、招聘类型和经验级别，不能代表整个中国岗位市场或应届岗位市场。发布日期未标注时保留为未标注，页面更新时间单独记录。第三方聚合来源与雇主官方页面分开标记；当前申请状态需要回原页核实。</div><div style="margin-top:8px">技能比例 = 至少提到该技能的不同岗位数 ÷ 当前筛选后的岗位数。脚本按关键词初筛，人工抽查与修正规则记录在 README 和 audit_log.csv。</div></section>
<div class="foot">新增岗位：填写 data/new_postings.csv 中的字段后运行 scripts/update_dashboard.py。该脚本按明示关键词生成候选标签并刷新看板，不会自动联网抓取，也不是自主 Agent。</div></main><script>
const D=__DATA__,esc=s=>String(s||'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const co=document.querySelector('#company'),ci=document.querySelector('#city'),ty=document.querySelector('#type');for(const v of [...new Set(D.jobs.map(x=>x.company))].sort())co.insertAdjacentHTML('beforeend',`<option>${esc(v)}</option>`);for(const v of [...new Set(D.jobs.flatMap(x=>x.location.split(/[、,，]/)))].sort())ci.insertAdjacentHTML('beforeend',`<option>${esc(v)}</option>`);for(const v of [...new Set(D.jobs.map(x=>x.job_type))].sort())ty.insertAdjacentHTML('beforeend',`<option>${esc(v)}</option>`);
function filtered(){return D.jobs.filter(j=>(co.value==='all'||j.company===co.value)&&(ci.value==='all'||j.location.split(/[、,，]/).includes(ci.value))&&(ty.value==='all'||j.job_type===ty.value))}function render(){let J=filtered(),ids=new Set(J.map(j=>j.job_id)),S=D.skills.filter(s=>ids.has(s.job_id)),cnt={};for(const s of S){cnt[s.skill_normalized]??=new Set();cnt[s.skill_normalized].add(s.job_id)}let B=Object.entries(cnt).map(([skill,ids])=>({skill,count:ids.size,pct:Math.round(ids.size/Math.max(J.length,1)*100)})).sort((a,b)=>b.count-a.count||a.skill.localeCompare(b.skill));document.querySelector('#metrics').innerHTML=[["岗位样本",J.length,"筛选后记录数"],["公司",new Set(J.map(j=>j.company)).size,"不同雇主"],["技能标签",new Set(S.map(s=>s.skill_normalized)).size,"初筛/复核标签"],["来源",new Set(J.map(j=>j.source_type)).size,"官方与第三方类型"]].map(x=>`<div class="card"><div class="muted">${x[0]}</div><div class="metric">${x[1]}</div><div class="small">${x[2]}</div></div>`).join('');let max=Math.max(...B.map(x=>x.count),1);document.querySelector('#bars').innerHTML=B.slice(0,16).map(x=>`<div class="bar"><div>${esc(x.skill)}</div><div class="track"><div class="fill" style="width:${100*x.count/max}%"></div></div><div>${x.count}/${J.length} · ${x.pct}%</div></div>`).join('');document.querySelector('#jobs').innerHTML=J.map(j=>`<div class="job"><a href="${esc(j.source_url)}" target="_blank" rel="noreferrer">${esc(j.title)}</a> <span class="pill">${esc(j.company)}</span><div class="small">${esc(j.location)} · ${esc(j.job_type)} · 发布日期：${esc(j.date_posted)} · 经验：${esc(j.experience_requirement)}</div><div class="small">来源类型：${esc(j.source_type)} · ${esc(j.status_note)}</div></div>`).join('');document.querySelector('#evidence').innerHTML=S.map(s=>{let j=D.jobs.find(x=>x.job_id===s.job_id);return `<tr><td>${esc(s.title)}<br><span class="small">${esc(j.company)}</span></td><td>${esc(s.skill_normalized)}</td><td>${esc(s.skill_category)}</td><td>${esc(s.requirement_level)}</td><td>${esc(s.evidence_quote)}</td><td><a href="${esc(s.source_url)}" target="_blank" rel="noreferrer">查看原页面</a></td></tr>`}).join('')}[co,ci,ty].forEach(x=>x.addEventListener('change',render));render();
</script></body></html>'''
 OUT.write_text(template.replace('__DATA__',payload),encoding='utf-8')

def main():
 jobs=read_csv(POSTINGS);known={j['job_id'] for j in jobs};skills=read_csv(SKILLS);done={s['job_id'] for s in skills};added=[]
 for row in read_csv(INBOX):
  jid=row.get('job_id','').strip()
  if not jid or jid in known:continue
  base={k:row.get(k,'') for k in POST_FIELDS};jobs.append(base);known.add(jid);added.append(base)
 # Process only postings that do not yet have candidate tags; stable ID prevents double counts on re-run.
 for job in jobs:
  if job['job_id'] not in done:
   skills.extend(extract(job));done.add(job['job_id'])
 write_csv(POSTINGS,jobs,POST_FIELDS);write_csv(SKILLS,skills,SKILL_FIELDS)
 write_csv(DATA/'evidence.csv',skills,SKILL_FIELDS)
 dashboard(jobs,skills)
 print(f'新增岗位 {len(added)}；岗位总数 {len(jobs)}；技能证据行 {len(skills)}；看板已刷新：{OUT}')

if __name__=='__main__':main()
