import unittest,datetime,tempfile,pathlib,json
from unittest.mock import patch
import cleanup as cleanup
from cleanup import cutoff_months,select_reason
class SelectionTests(unittest.TestCase):
 def test_calendar_month_clamps_day(self):
  self.assertEqual(cutoff_months(datetime.datetime(2026,5,31,tzinfo=datetime.timezone.utc)).date(),datetime.date(2026,2,28))
 def test_subscribed_actor_protected(self):
  item={'Name':'ABF-188','DateCreated':'2025-01-01T00:00:00Z','People':[{'Name':'枫可怜','Type':'Actor'}]}
  self.assertIsNone(select_reason(item,{'枫可怜'},set(),datetime.datetime(2026,8,8,tzinfo=datetime.timezone.utc)))
 def test_missing_actor_retained(self):
  self.assertIsNone(select_reason({'Name':'ABF-188','DateCreated':'2025-01-01T00:00:00Z'},set(),set(),datetime.datetime(2026,8,8,tzinfo=datetime.timezone.utc)))
 def test_vr_removed_even_when_actor_protected(self):
  self.assertEqual(select_reason({'Name':'KAVR-495 【VR】','People':[{'Name':'伊藤舞雪','Type':'Actor'}]}, {'伊藤舞雪'},set(),datetime.datetime(2026,8,8,tzinfo=datetime.timezone.utc)),'vr')
 def test_number_protects_when_actor_metadata_differs(self):
  self.assertIsNone(select_reason({'Name':'ABF-188','DateCreated':'2025-01-01T00:00:00Z','People':[{'Name':'different','Type':'Actor'}]},set(),{'ABF-188'},datetime.datetime(2026,8,8,tzinfo=datetime.timezone.utc)))
 def test_exact_cutoff_not_deleted(self):
  self.assertIsNone(select_reason({'Name':'ABF-188','DateCreated':'2026-08-08T00:00:00Z','People':[{'Name':'other','Type':'Actor'}]},set(),set(),datetime.datetime(2026,8,8,tzinfo=datetime.timezone.utc)))
 def test_emby_failure_preserves_cloud_files(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=pathlib.Path(tmp);local=root/'local';cloud=root/'cloud';local.mkdir();cloud.mkdir();(local/'film').mkdir();(cloud/'film').mkdir()
   video=cloud/'film'/'film.mp4';video.write_bytes(b'video')
   entry={'folder':'film','items':[{'id':'123'}],'cloud_files':[{'name':'film.mp4','size':5}],'local_files':[]}
   def fail(*args,**kwargs):raise RuntimeError('Emby unavailable')
   with patch.object(cleanup,'LOCAL',local),patch.object(cleanup,'CLOUD',cloud):cleanup.execute(fail,{'candidates':[entry]},root/'audit.json')
   self.assertTrue(video.exists())
 def test_changed_file_prevents_any_emby_delete(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=pathlib.Path(tmp);local=root/'local';cloud=root/'cloud';local.mkdir();cloud.mkdir();(local/'film').mkdir();(cloud/'film').mkdir();(cloud/'film'/'film.mp4').write_bytes(b'changed')
   entry={'folder':'film','items':[{'id':'123'}],'cloud_files':[{'name':'film.mp4','size':5}],'local_files':[]};calls=[]
   with patch.object(cleanup,'LOCAL',local),patch.object(cleanup,'CLOUD',cloud):cleanup.execute(lambda *a,**k:calls.append(a),{'candidates':[entry]},root/'audit.json')
   self.assertEqual(calls,[])
if __name__=='__main__':unittest.main()
