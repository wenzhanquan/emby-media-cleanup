import unittest,datetime
from scheduler import next_run
from docker_bridge import demux
class ContainerTests(unittest.TestCase):
 def test_sunday_after_due_uses_next_week(self):
  now=datetime.datetime(2026,11,8,11,0,tzinfo=datetime.timezone(datetime.timedelta(hours=8)))
  self.assertEqual(next_run(now).isoformat(),'2026-11-15T04:30:00+08:00')
 def test_before_due_uses_today(self):
  now=datetime.datetime(2026,11,8,4,0,tzinfo=datetime.timezone(datetime.timedelta(hours=8)))
  self.assertEqual(next_run(now).isoformat(),'2026-11-08T04:30:00+08:00')
 def test_docker_demux_keeps_stderr_separate(self):
  def frame(stream,data):return bytes([stream,0,0,0])+len(data).to_bytes(4,'big')+data
  self.assertEqual(demux(frame(1,b'{"ok":true}')+frame(2,b'warning')),(b'{"ok":true}',b'warning'))
 def test_truncated_docker_output_is_rejected(self):
  with self.assertRaises(ValueError):demux(b'\x01\x00\x00\x00\x00\x00\x00\x05hi')
if __name__=='__main__':unittest.main()
