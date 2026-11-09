"""Visible weekly scheduler; restarting the container never triggers an extra cleanup."""
import datetime,json,os,pathlib,subprocess,time,traceback
from zoneinfo import ZoneInfo
def next_run(now,weekday=6,hour=4,minute=30):
 due=now.replace(hour=hour,minute=minute,second=0,microsecond=0)+datetime.timedelta(days=(weekday-now.weekday())%7)
 if due<=now:due+=datetime.timedelta(days=7)
 return due
def save(path,data):
 temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(data,ensure_ascii=False,indent=2));temporary.replace(path)
def main():
 ZONE=ZoneInfo('Asia/Shanghai')
 state=pathlib.Path(os.environ.get('CLEANUP_STATE','/state'));state.mkdir(exist_ok=True,parents=True)
 status_path=state/'scheduler-status.json';schedule_path=state/'scheduler-schedule.json'
 weekday=int(os.environ.get('CLEANUP_WEEKDAY','6'));hour=int(os.environ.get('CLEANUP_HOUR','4'));minute=int(os.environ.get('CLEANUP_MINUTE','30'))
 if not 0<=weekday<=6 or not 0<=hour<24 or not 0<=minute<60:raise ValueError('Invalid weekly schedule')
 schedule={'weekday':weekday,'hour':hour,'minute':minute}
 stored=json.loads(schedule_path.read_text()) if schedule_path.exists() else {}
 now=datetime.datetime.now(ZONE)
 due=datetime.datetime.fromisoformat(stored['next_run']) if stored.get('schedule')==schedule and stored.get('next_run') else next_run(now,weekday,hour,minute)
 last={'last_result':'not_run'}
 if status_path.exists():last.update(json.loads(status_path.read_text()))
 if last.get('last_result')=='running':last['last_result']='interrupted'
 print('Emby 媒体清理容器已启动；时区 Asia/Shanghai',flush=True)
 print('清理规则：排除 VR；非订阅演员影片入库超过三个自然月才清理；未知演员保留。',flush=True)
 print('下次执行时间：'+due.isoformat(),flush=True)
 while True:
  now=datetime.datetime.now(ZONE)
  if now>=due:
   scheduled=due;due=next_run(now,weekday,hour,minute)
   save(schedule_path,{'schedule':schedule,'next_run':due.isoformat()})
   last.update(last_started=now.isoformat(),last_result='running',scheduled_for=scheduled.isoformat());save(status_path,last)
   print('开始每周清理：'+now.isoformat(),flush=True)
   result=subprocess.run(['python','-u','/opt/media-cleanup/cleanup.py','--apply'],timeout=10800)
   last.update(last_finished=datetime.datetime.now(ZONE).isoformat(),last_result='success' if result.returncode==0 else 'failed',last_exit_code=result.returncode)
   print('本轮执行结果：'+last['last_result']+'；下次执行：'+due.isoformat(),flush=True)
  last.update(heartbeat=now.isoformat(),next_run=due.isoformat(),schedule=schedule)
  save(status_path,last);save(schedule_path,{'schedule':schedule,'next_run':due.isoformat()})
  time.sleep(30)
if __name__=='__main__':main()
