"""Read the current Immortal configuration over Docker's local Unix socket."""
import http.client,json,socket,urllib.parse
class DockerConnection(http.client.HTTPConnection):
 def __init__(self):super().__init__('localhost',timeout=90)
 def connect(self):
  self.sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);self.sock.settimeout(self.timeout);self.sock.connect('/var/run/docker.sock')
def request(path,payload=None,method='GET'):
 c=DockerConnection()
 try:
  body=json.dumps(payload).encode() if payload is not None else None
  c.request(method,path,body,{'Content-Type':'application/json'});r=c.getresponse();raw=r.read()
  if r.status not in (200,201):raise RuntimeError('Docker API returned HTTP '+str(r.status))
  return raw
 finally:c.close()
def demux(raw):
 out=[];err=[];offset=0
 while offset<len(raw):
  if len(raw)-offset<8:raise ValueError('Incomplete Docker stream header')
  stream=raw[offset];size=int.from_bytes(raw[offset+4:offset+8],'big');offset+=8
  if len(raw)-offset<size:raise ValueError('Incomplete Docker stream data')
  if stream not in (1,2):raise ValueError('Unexpected Docker stream')
  (out if stream==1 else err).append(raw[offset:offset+size]);offset+=size
 return b''.join(out),b''.join(err)
def exec_python(container,script):
 path='/containers/'+urllib.parse.quote(container,safe='')+'/exec'
 exec_id=json.loads(request(path,{'AttachStdout':True,'AttachStderr':True,'Tty':False,'Cmd':['python','-c',script]},'POST'))['Id']
 stdout,stderr=demux(request('/exec/'+exec_id+'/start',{'Detach':False,'Tty':False},'POST'))
 status=json.loads(request('/exec/'+exec_id+'/json'))
 if status['Running'] or status['ExitCode']!=0:raise RuntimeError('Immortal read-only snapshot failed')
 return stdout.decode('utf-8')
