"""Audited adult-library cleanup, using current Immortal subscriptions."""
import calendar,datetime,json,pathlib,re,subprocess,urllib.request,urllib.error,xml.etree.ElementTree as ET,os,sys
from zoneinfo import ZoneInfo
LOCAL=pathlib.Path(os.environ.get('LOCAL_MEDIA_ROOT','/nas-data/strm/小姐姐'))
CLOUD=pathlib.Path(os.environ.get('CLOUD_MEDIA_ROOT','/nas-data/115open/strm/小姐姐'))
STATE=pathlib.Path(os.environ.get('AUDIT_ROOT','/audit'))
EMBY_ROOT=os.environ.get('EMBY_LIBRARY_PATH','/media/strm/小姐姐').rstrip('/')+'/'
def cutoff_months(now):
 month=now.month-3;year=now.year
 if month<=0:year-=1;month+=12
 return now.replace(year=year,month=month,day=min(now.day,calendar.monthrange(year,month)[1]))
def number_of(item):
 m=re.search(r'(?i)(?:FC2[-_ ]?(?:PPV[-_ ]?)?\d+|[A-Z]{2,10}[-_]\d{2,7})',item.get('Name','')+' '+pathlib.PurePosixPath(item.get('Path','')).name)
 return m.group().upper().replace('_','-') if m else None
def select_reason(item,aliases,protected_numbers,cutoff):
 text=' '.join([item.get('Name',''),item.get('Path','')]+item.get('Genres',[])+item.get('Tags',[]))
 if re.search(r'(?i)(?<![a-z])VR(?![a-z])|[A-Z]*VR[-_ ]?\d|仮想現実|虚拟现实',text):return 'vr'
 names={p['Name'] for p in item.get('People',[]) if p.get('Type')=='Actor'}
 if not names or names&aliases or number_of(item) in protected_numbers:return None
 try:added=datetime.datetime.fromisoformat(item['DateCreated'].replace('Z','+00:00'))
 except (KeyError,ValueError):return None
 if added.tzinfo is None:return None
 return 'older_than_three_months' if added<cutoff else None
SNAPSHOT=r'''
import json
from app.core.database import session_scope
from app.models.config import Config
from app.models.movie import Movie
from sqlalchemy import text
with session_scope() as db:
 rows=db.execute(text('select c.id,c.name,c.cn_name,c.former_name from cast_subscribe cs join "cast" c on c.id=cs.cast_id')).fetchall()
 if not rows:raise RuntimeError('No actor subscriptions; refusing cleanup')
 ids={str(r[0]) for r in rows};aliases=set()
 for r in rows:aliases.update(x for x in [r[1],r[2]]+list(r[3] or []) if x)
 protected=[]
 for n,casts,names in db.query(Movie.number,Movie.casts,Movie.cast_names).all():
  if ids.intersection(str(x) for x in (casts or [])) or aliases.intersection(names or []):protected.append(n.upper())
 config=json.loads(db.query(Config).filter(Config.key=='MediaServer.emby').first().content)
 print(json.dumps({'config':config,'aliases':sorted(aliases),'protected_numbers':protected},ensure_ascii=False))
'''
def snapshot():
 from docker_bridge import exec_python
 data=json.loads(exec_python(os.environ.get('IMMORTAL_CONTAINER','immortal'),SNAPSHOT));aliases=set(data['aliases'])
 groups=[]
 for node in ET.parse(os.environ.get('ACTOR_MAPPING','/config/mapping_actor.xml')).getroot():
  groups.append(set(filter(None,[node.get('zh_cn'),node.get('zh_tw'),node.get('jp')]+node.get('keyword','').split(','))))
 for _ in range(3):
  for group in groups:
   if aliases&group:aliases.update(group)
 return data,aliases
def api_client(cfg):
 base=cfg['url'].rstrip('/');op=urllib.request.build_opener(urllib.request.ProxyHandler({}))
 def call(path,method='GET'):
  req=urllib.request.Request(base+path,headers={'X-Emby-Token':cfg['api_key']},method=method)
  with op.open(req,timeout=45) as r:
   b=r.read();return json.loads(b) if b else None
 return call
def plan(call,aliases,protected):
 from urllib.parse import urlencode
 libraries=call('/Library/VirtualFolders');lib=next(x for x in libraries if x['Locations']==[EMBY_ROOT.rstrip('/')])
 items=[];start=0
 while True:
  data=call('/Items?'+urlencode({'ParentId':lib['ItemId'],'Recursive':'true','IncludeItemTypes':'Movie','Fields':'Path,DateCreated,People,Genres,Tags,MediaSources','Limit':500,'StartIndex':start}))
  items+=data['Items'];start+=len(data['Items'])
  if start>=data['TotalRecordCount']:break
  if not data['Items']:raise RuntimeError('Incomplete Emby paging')
 cutoff=cutoff_months(datetime.datetime.now(ZoneInfo('Asia/Shanghai')));folders={};skips=[]
 for item in items:
  p=item.get('Path','')
  if not p.startswith(EMBY_ROOT):continue
  rel=pathlib.PurePosixPath(p).relative_to(EMBY_ROOT)
  if len(rel.parts)!=2:continue
  folders.setdefault(rel.parts[0],[]).append(item)
 candidates=[]
 for name,group in folders.items():
  reasons=[select_reason(i,aliases,protected,cutoff) for i in group]
  if not all(reasons):continue
  local=LOCAL/name;cloud=CLOUD/name
  try:
   if local.is_symlink() or cloud.is_symlink():raise ValueError('Symlink folder')
   if local.resolve().parent!=LOCAL.resolve() or cloud.resolve().parent!=CLOUD.resolve():raise ValueError('Path outside roots')
   if not local.is_dir() or not cloud.is_dir():raise ValueError('Missing corresponding cloud folder')
   lf=list(local.iterdir());cf=list(cloud.iterdir())
   if any(not p.is_file() or p.is_symlink() for p in lf+cf):raise ValueError('Nested directory or symlink')
   strms={p.stem for p in lf if p.suffix.lower()=='.strm'}
   videos=[p for p in cf if p.suffix.lower() in ['.mp4','.mkv','.avi','.wmv','.mov','.m4v','.ts']]
   if not videos or any(p.stem not in strms for p in videos):raise ValueError('Video/STRM names do not match')
   if any(p.suffix.lower() not in ['.mp4','.mkv','.avi','.wmv','.mov','.m4v','.ts','.strm','.nfo','.jpg','.jpeg','.png','.webp','.srt','.ass','.ssa','.sub','.idx','.txt'] and not p.name.endswith('-mediainfo.json') for p in lf+cf):raise ValueError('Unexpected file extension')
   candidates.append({'folder':name,'reasons':sorted(set(reasons)),'items':[{'id':i['Id'],'name':i['Name'],'created':i.get('DateCreated'),'path':i['Path']} for i in group],'cloud_files':[{'name':p.name,'size':p.stat().st_size} for p in cf],'local_files':[p.name for p in lf]})
  except (ValueError,OSError) as e:skips.append({'folder':name,'reason':str(e)})
 return {'cutoff':cutoff.isoformat(),'total_items':len(items),'protected_alias_count':len(aliases),'candidates':candidates,'skipped':skips}
def execute(call,manifest,out):
 ledger=out.with_suffix('.jsonl')
 def log(row):
  with ledger.open('a') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n');f.flush();os.fsync(f.fileno())
 for entry in manifest['candidates']:
  name=entry['folder'];local=LOCAL/name;cloud=CLOUD/name
  try:
   # Recheck all preflighted paths before the first mutation.
   if cloud.resolve().parent!=CLOUD.resolve() or local.resolve().parent!=LOCAL.resolve():raise ValueError('Root mismatch')
   if {p.name for p in cloud.iterdir()}!={p['name'] for p in entry['cloud_files']}:raise ValueError('Cloud folder changed')
   for spec in entry['cloud_files']:
    p=cloud/spec['name']
    if not p.is_file() or p.is_symlink() or p.stat().st_size!=spec['size']:raise ValueError('Cloud file changed')
   log({'folder':name,'stage':'started'})
   for item in entry['items']:
    try:call('/Items/'+item['id'],method='DELETE')
    except urllib.error.HTTPError as e:
     if e.code!=404:raise
    try:call('/Items/'+item['id'])
    except urllib.error.HTTPError as e:
     if e.code!=404:raise
    else:raise RuntimeError('Emby item still exists after delete')
   log({'folder':name,'stage':'emby_removed'})
   for spec in entry['cloud_files']:(cloud/spec['name']).unlink()
   cloud.rmdir()
   if local.exists():
    for filename in entry['local_files']:
     p=local/filename
     if p.is_file() and not p.is_symlink():p.unlink()
    if not any(local.iterdir()):local.rmdir()
   log({'folder':name,'stage':'completed','cloud_bytes':sum(p['size'] for p in entry['cloud_files'])})
   print('Deleted',name,flush=True)
  except Exception as e:
   log({'folder':name,'stage':'error','error':type(e).__name__+': '+str(e)[:200]});print('Failed',name,type(e).__name__,flush=True)
def main():
 import fcntl
 STATE.mkdir(parents=True,exist_ok=True);lock=(STATE/'cleanup.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 data,aliases=snapshot();call=api_client(data['config']);manifest=plan(call,aliases,set(data['protected_numbers']))
 out=STATE/(datetime.datetime.now().strftime('%Y%m%d-%H%M%S')+'.json');out.write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
 print('Manifest',str(out),'candidates',len(manifest['candidates']),'skipped',len(manifest['skipped']),flush=True)
 if '--apply' in sys.argv:execute(call,manifest,out)
if __name__=='__main__':main()
