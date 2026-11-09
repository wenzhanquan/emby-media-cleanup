import datetime,json,pathlib,sys
p=pathlib.Path('/state/scheduler-status.json')
if not p.exists():raise SystemExit(1)
d=json.loads(p.read_text());age=(datetime.datetime.now(datetime.timezone.utc)-datetime.datetime.fromisoformat(d['heartbeat'])).total_seconds()
raise SystemExit(0 if d.get('last_result')=='running' or (age<180 and d.get('last_result')!='failed') else 1)
