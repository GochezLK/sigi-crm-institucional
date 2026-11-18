from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
from pathlib import Path
import hashlib, json, secrets, sqlite3, urllib.request, base64, os
from datetime import datetime, timedelta

ROOT = Path(__file__).parent
DB = ROOT / "sigi.db"
NTFY = "http://127.0.0.1:2586"
NTFY_USER = os.getenv('SIGI_NTFY_USER','sigi-crm')
NTFY_PASSWORD = os.getenv('SIGI_NTFY_PASSWORD','sigi-crm-dev-2026')
SESSION_HOURS = 8
SESSIONS = {}

def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    return c

def seed():
    c = db()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, password TEXT NOT NULL, role TEXT NOT NULL, active INTEGER DEFAULT 1);
    CREATE TABLE IF NOT EXISTS projects(id INTEGER PRIMARY KEY, code TEXT UNIQUE, name TEXT NOT NULL, organization TEXT, owner TEXT, status TEXT, priority TEXT, progress INTEGER DEFAULT 0, due TEXT, budget TEXT DEFAULT '', hours INTEGER DEFAULT 0, risks TEXT DEFAULT '', deliverables TEXT DEFAULT '');
    CREATE TABLE IF NOT EXISTS project_comments(id INTEGER PRIMARY KEY, project_id INTEGER, user_id INTEGER, body TEXT NOT NULL, created TEXT DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(project_id) REFERENCES projects(id));
    CREATE TABLE IF NOT EXISTS phases(id INTEGER PRIMARY KEY, project_id INTEGER, name TEXT NOT NULL, status TEXT DEFAULT 'Pendiente', progress INTEGER DEFAULT 0, FOREIGN KEY(project_id) REFERENCES projects(id));
    CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY, project_id INTEGER, phase_id INTEGER, title TEXT NOT NULL, assignee TEXT, status TEXT DEFAULT 'Por hacer', due TEXT, FOREIGN KEY(project_id) REFERENCES projects(id));
    CREATE TABLE IF NOT EXISTS requests(id INTEGER PRIMARY KEY, code TEXT UNIQUE, subject TEXT NOT NULL, organization TEXT, requester TEXT, priority TEXT, status TEXT, created TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS notifications(id INTEGER PRIMARY KEY, user_id INTEGER, title TEXT, body TEXT, read INTEGER DEFAULT 0, created TEXT DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(user_id) REFERENCES users(id));
    CREATE TABLE IF NOT EXISTS activities(id INTEGER PRIMARY KEY, title TEXT NOT NULL, responsible TEXT, project TEXT, status TEXT, due TEXT);
    CREATE TABLE IF NOT EXISTS calendar_events(id INTEGER PRIMARY KEY, title TEXT NOT NULL, event_date TEXT, responsible TEXT, project TEXT, type TEXT);
    CREATE TABLE IF NOT EXISTS tickets(id INTEGER PRIMARY KEY, title TEXT NOT NULL, requester TEXT, project TEXT, priority TEXT, status TEXT, created TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS audit_log(id INTEGER PRIMARY KEY, user_id INTEGER, action TEXT NOT NULL, entity TEXT NOT NULL, entity_id INTEGER, detail TEXT, created TEXT DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(user_id) REFERENCES users(id));
    CREATE TABLE IF NOT EXISTS permissions(id INTEGER PRIMARY KEY, role TEXT NOT NULL, module TEXT NOT NULL, can_view INTEGER DEFAULT 0, can_create INTEGER DEFAULT 0, can_edit INTEGER DEFAULT 0, can_delete INTEGER DEFAULT 0, UNIQUE(role,module));
    CREATE TABLE IF NOT EXISTS documents(id INTEGER PRIMARY KEY, project_id INTEGER, name TEXT NOT NULL, mime TEXT, data TEXT NOT NULL, created TEXT DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(project_id) REFERENCES projects(id));
    """)
    for col, definition in [('budget',"TEXT DEFAULT ''"),('hours','INTEGER DEFAULT 0'),('risks',"TEXT DEFAULT ''"),('deliverables',"TEXT DEFAULT ''")]:
        try: c.execute(f"ALTER TABLE projects ADD COLUMN {col} {definition}")
        except sqlite3.OperationalError: pass
    if not c.execute("SELECT 1 FROM users LIMIT 1").fetchone():
        pw = hashlib.sha256(b"admin123").hexdigest()
        c.execute("INSERT INTO users(name,email,password,role) VALUES(?,?,?,?)", ("Mtra. Laura Méndez", "admin@sigi.local", pw, "admin"))
        c.execute("INSERT INTO users(name,email,password,role) VALUES(?,?,?,?)", ("Ing. Ricardo Salas", "ricardo@sigi.local", hashlib.sha256(b"demo123").hexdigest(), "manager"))
    if not c.execute("SELECT 1 FROM permissions LIMIT 1").fetchone():
        modules=['home','organizations','people','requests','projects','activity','calendar','support','reports','admin']
        for role in ('admin','manager','user'):
            for module in modules:
                values=(1,1,1,1) if role=='admin' else ((1,1,1,0) if role=='manager' and module in ('projects','requests','activity','calendar','support') else (1,0,0,0) if role!='admin' else (1,1,1,1))
                c.execute("INSERT INTO permissions(role,module,can_view,can_create,can_edit,can_delete) VALUES(?,?,?,?,?,?)",(role,module,*values))
    if not c.execute("SELECT 1 FROM projects LIMIT 1").fetchone():
        rows=[("PRY-2026-014","Plataforma de Trámites Digitales","Dir. de Gobierno Digital","Ing. Ricardo Salas","En desarrollo","Alta",68,"15/12/2026"),("PRY-2026-011","Portal de Transparencia v2","Unidad de Transparencia","Mtra. Laura Méndez","En revisión","Alta",82,"05/12/2026"),("PRY-2026-009","Sistema de Control de Inventarios","Dir. de Recursos Materiales","Lic. Andrea Torres","En desarrollo","Media",45,"30/01/2027"),("PRY-2026-006","Sistema de Becas Escolares","Sría. de Educación","Ing. Marian Ruiz","En pruebas","Alta",90,"10/11/2026")]
        c.executemany("INSERT INTO projects(code,name,organization,owner,status,priority,progress,due) VALUES(?,?,?,?,?,?,?,?)", rows)
    if not c.execute("SELECT 1 FROM requests LIMIT 1").fetchone():
        rows=[("SOL-2026-118","Integración API Registro Civil","Dir. de Catastro","Mtra. Laura Méndez","Alta","En evaluación"),("SOL-2026-124","Portal de citas del Registro Civil","Registro Civil","Mtra. Laura Méndez","Media","Aprobada"),("SOL-2026-109","Módulo de reportes ciudadanos","Atención Ciudadana","Ing. Ricardo Salas","Alta","En revisión")]
        c.executemany("INSERT INTO requests(code,subject,organization,requester,priority,status) VALUES(?,?,?,?,?,?)", rows)
    if not c.execute("SELECT 1 FROM activities LIMIT 1").fetchone():
        c.executemany("INSERT INTO activities(title,responsible,project,status,due) VALUES(?,?,?,?,?)",[("Revisión de entregables","Mtra. Laura Méndez","Portal de Transparencia v2","En seguimiento","19/11/2026"),("Mesa de trabajo","Ing. Ricardo Salas","Plataforma de Trámites Digitales","Programada","21/11/2026")])
    if not c.execute("SELECT 1 FROM calendar_events LIMIT 1").fetchone():
        c.executemany("INSERT INTO calendar_events(title,event_date,responsible,project,type) VALUES(?,?,?,?,?)",[("Reunión de seguimiento","20/11/2026","Ing. Ricardo Salas","Plataforma de Trámites Digitales","Reunión"),("Entrega de versión","05/12/2026","Mtra. Laura Méndez","Portal de Transparencia v2","Hito")])
    if not c.execute("SELECT 1 FROM tickets LIMIT 1").fetchone():
        c.executemany("INSERT INTO tickets(title,requester,project,priority,status) VALUES(?,?,?,?,?)",[("Error de acceso al portal","Unidad de Transparencia","Portal de Transparencia v2","Alta","Abierto"),("Actualización de catálogo","Dir. de Gobierno Digital","Plataforma de Trámites Digitales","Media","En atención")])
    if not c.execute("SELECT 1 FROM phases LIMIT 1").fetchone():
        p=c.execute("SELECT id FROM projects ORDER BY id LIMIT 1").fetchone()[0]
        c.executemany("INSERT INTO phases(project_id,name,status,progress) VALUES(?,?,?,?)",[(p,'Análisis y diseño','Completada',100),(p,'Desarrollo','En curso',60),(p,'Pruebas y entrega','Pendiente',0)])
        phase=c.execute("SELECT id FROM phases WHERE project_id=? AND name='Desarrollo'",(p,)).fetchone()[0]
        c.execute("INSERT INTO tasks(project_id,phase_id,title,assignee,status,due) VALUES(?,?,?,?,?,?)",(p,phase,'Construir módulo de solicitudes','Ing. Ricardo Salas','En progreso','25/11/2026'))
    c.commit(); c.close()

def notify(user_id, title, body):
    c=db(); c.execute("INSERT INTO notifications(user_id,title,body) VALUES(?,?,?)",(user_id,title,body)); c.commit(); c.close()
    try:
        data=body.encode(); auth=base64.b64encode(f"{NTFY_USER}:{NTFY_PASSWORD}".encode()).decode(); req=urllib.request.Request(f"{NTFY}/sigi",data=data,method="POST",headers={"Title":title,"Priority":"default","Authorization":f"Basic {auth}"}); urllib.request.urlopen(req,timeout=2).close()
    except Exception: pass

def audit(c, user_id, action, entity, entity_id, detail=''):
    c.execute("INSERT INTO audit_log(user_id,action,entity,entity_id,detail) VALUES(?,?,?,?,?)",(user_id,action,entity,entity_id,detail))

def allowed(user, module, action='view'):
    if user['role']=='admin': return True
    key={'view':'can_view','create':'can_create','edit':'can_edit','delete':'can_delete'}[action]
    c=db(); row=c.execute(f"SELECT {key} AS ok FROM permissions WHERE role=? AND module=?",(user['role'],module)).fetchone(); c.close(); return bool(row and row['ok'])

def automatic_alerts(user_id):
    c=db(); today=datetime.now(); limit=today+timedelta(days=3)
    items=[]
    for table,title_field,date_field,label in [('tasks','title','due','Tarea'),('projects','name','due','Proyecto')]:
        for x in c.execute(f"SELECT id,{title_field} AS title,{date_field} AS due FROM {table} WHERE {date_field}<>''").fetchall():
            try: due=datetime.strptime(x['due'],'%d/%m/%Y')
            except ValueError: continue
            if due<=limit:
                state='vencido' if due<today else 'vence pronto'; items.append((f"alert:{table}:{x['id']}:{state}",f"{label} {state}",f"{x['title']} {state}: {x['due']}"))
    for x in c.execute("SELECT id,title FROM tickets WHERE status NOT IN ('Cerrado','Resuelto')").fetchall(): items.append((f"alert:ticket:{x['id']}",'Soporte pendiente',x['title']))
    for marker,title,body in items:
        if not c.execute("SELECT 1 FROM notifications WHERE user_id=? AND body=? AND created>=datetime('now','-1 day')",(user_id,body)).fetchone():
            c.execute("INSERT INTO notifications(user_id,title,body) VALUES(?,?,?)",(user_id,title,body)); c.commit()
            try:
                data=body.encode(); auth=base64.b64encode(f"{NTFY_USER}:{NTFY_PASSWORD}".encode()).decode(); req=urllib.request.Request(f"{NTFY}/sigi",data=data,method="POST",headers={"Title":title,"Authorization":f"Basic {auth}"}); urllib.request.urlopen(req,timeout=2).close()
            except Exception: pass
    c.close()

def rows(query, args=()):
    c=db(); out=[dict(x) for x in c.execute(query,args).fetchall()]; c.close(); return out

def sync_progress(c, project_id):
    row=c.execute("SELECT AVG(progress) AS progress FROM phases WHERE project_id=?",(project_id,)).fetchone()
    c.execute("UPDATE projects SET progress=? WHERE id=?",(round(row['progress']) if row and row['progress'] is not None else 0,project_id))

def sync_phase_progress(c, phase_id):
    phase=c.execute("SELECT project_id FROM phases WHERE id=?",(phase_id,)).fetchone()
    if not phase: return
    values={'Por hacer':0,'Bloqueada':0,'En progreso':50,'Completada':100}
    tasks=c.execute("SELECT status FROM tasks WHERE phase_id=?",(phase_id,)).fetchall()
    if tasks: c.execute("UPDATE phases SET progress=? WHERE id=?",(round(sum(values.get(x['status'],0) for x in tasks)/len(tasks)),phase_id))
    sync_progress(c,phase['project_id'])

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_): pass
    def send(self, code, obj, headers=None):
        raw=json.dumps(obj, ensure_ascii=False).encode(); self.send_response(code); self.send_header("Content-Type","application/json; charset=utf-8"); self.send_header("Content-Length",str(len(raw))); self.send_header("Access-Control-Allow-Origin","*");
        for k,v in (headers or {}).items(): self.send_header(k,v)
        self.end_headers(); self.wfile.write(raw)
    def body(self):
        n=int(self.headers.get("Content-Length",0)); return json.loads(self.rfile.read(n) or b"{}")
    def user(self):
        token=self.headers.get("Authorization","").replace("Bearer ",""); session=SESSIONS.get(token)
        if not session: return None
        if session['expires'] < datetime.now(): SESSIONS.pop(token,None); return None
        return session['user']
    def do_OPTIONS(self): self.send(204,{})
    def do_GET(self):
        p=urlparse(self.path).path; u=self.user()
        if p.startswith("/api/") and not u: return self.send(401,{"error":"Sesión requerida"})
        if p=="/api/me": return self.send(200,u)
        if p=="/api/dashboard":
            automatic_alerts(u['id']); ps=rows("SELECT * FROM projects"); rs=rows("SELECT * FROM requests"); ts=rows("SELECT * FROM tasks"); ns=rows("SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT 20",(u['id'],)); return self.send(200,{"projects":ps,"requests":rs,"tasks":ts,"notifications":ns,"metrics":{"active":sum(x['status'] not in ('Completado','Cerrado') for x in ps),"pending":sum(x['status'] not in ('Aprobada','Completada') for x in rs),"average":round(sum(x['progress'] for x in ps)/len(ps)) if ps else 0}})
        if p=="/api/projects": return self.send(200,rows("SELECT * FROM projects ORDER BY id DESC"))
        if p.startswith("/api/projects/"):
            try: project_id=int(p.rsplit('/',1)[1])
            except ValueError: return self.send(400,{"error":"Proyecto inválido"})
            project=rows("SELECT * FROM projects WHERE id=?",(project_id,))
            if not project: return self.send(404,{"error":"Proyecto no encontrado"})
            return self.send(200,{"project":project[0],"phases":rows("SELECT * FROM phases WHERE project_id=? ORDER BY id",(project_id,)),"tasks":rows("SELECT * FROM tasks WHERE project_id=? ORDER BY id",(project_id,)),"documents":rows("SELECT id,project_id,name,mime,created FROM documents WHERE project_id=? ORDER BY id DESC",(project_id,)),"comments":rows("SELECT c.*,u.name AS user_name FROM project_comments c LEFT JOIN users u ON u.id=c.user_id WHERE project_id=? ORDER BY c.id DESC",(project_id,))})
        if p=="/api/requests": return self.send(200,rows("SELECT * FROM requests ORDER BY id DESC"))
        if p=="/api/notifications": return self.send(200,rows("SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC",(u['id'],)))
        if p.startswith("/api/organizations"): return self.send(200,[{"name":"Dirección de Gobierno Digital","type":"Dirección","projects":4},{"name":"Secretaría de Educación","type":"Secretaría","projects":3},{"name":"Unidad de Transparencia","type":"Unidad","projects":2}])
        if p.startswith("/api/people"): return self.send(200,[{"name":"Mtra. Laura Méndez","area":"Coordinación de Desarrollo de Software","email":"laura.mendez@institucion.gob.mx","status":"Activo"},{"name":"Ing. Ricardo Salas","area":"Gobierno Digital","email":"ricardo.salas@institucion.gob.mx","status":"Activo"}])
        if p=="/api/users": return self.send(200,rows("SELECT id,name,email,role,active FROM users"))
        if p=="/api/audit":
            if u['role']!='admin': return self.send(403,{"error":"Solo administración puede consultar auditoría"})
            return self.send(200,rows("SELECT a.*,u.name AS user_name FROM audit_log a LEFT JOIN users u ON u.id=a.user_id ORDER BY a.id DESC LIMIT 100"))
        if p=="/api/permissions":
            if u['role']!='admin': return self.send(403,{"error":"Solo administración puede consultar permisos"})
            return self.send(200,rows("SELECT * FROM permissions ORDER BY role,module"))
        if p.startswith("/api/documents/"):
            try: doc_id=int(p.rsplit('/',1)[1])
            except ValueError: return self.send(400,{"error":"Documento inválido"})
            doc=rows("SELECT id,project_id,name,mime,data FROM documents WHERE id=?",(doc_id,))
            return self.send(200,doc[0]) if doc else self.send(404,{"error":"Documento no encontrado"})
        if p=="/api/documents":
            project_id=self.headers.get('X-Project-Id')
            return self.send(200,rows("SELECT id,project_id,name,mime,created FROM documents WHERE project_id=? ORDER BY id DESC",(project_id,)) if project_id else rows("SELECT id,project_id,name,mime,created FROM documents ORDER BY id DESC"))
        if p=="/api/activities": return self.send(200,rows("SELECT * FROM activities ORDER BY id DESC"))
        if p=="/api/calendar": return self.send(200,rows("SELECT * FROM calendar_events ORDER BY id"))
        if p=="/api/support": return self.send(200,rows("SELECT * FROM tickets ORDER BY id DESC"))
        if p.startswith("/api/"): return self.send(404,{"error":"Ruta no encontrada"})
        file=ROOT/("index.html" if p=="/" else p.lstrip("/"));
        if file.exists() and file.is_file():
            data=file.read_bytes(); self.send_response(200); self.send_header("Content-Type", "text/html" if file.suffix=='.html' else "text/css" if file.suffix=='.css' else "application/javascript"); self.send_header("Content-Length",str(len(data))); self.end_headers(); self.wfile.write(data); return
        self.send(404,{"error":"No encontrado"})
    def do_PUT(self):
        p=urlparse(self.path).path; u=self.user()
        if not u: return self.send(401,{"error":"Sesión requerida"})
        b=self.body(); c=db()
        if p.startswith('/api/phases/'):
            try: item_id=int(p.rsplit('/',1)[1])
            except ValueError: return self.send(400,{"error":"Fase inválida"})
            if not b.get('name'): return self.send(400,{"error":"El nombre es obligatorio"})
            phase=c.execute("SELECT project_id FROM phases WHERE id=?",(item_id,)).fetchone()
            if not phase: return self.send(404,{"error":"Fase no encontrada"})
            c.execute("UPDATE phases SET name=?,status=?,progress=? WHERE id=?",(b['name'],b.get('status','Pendiente'),int(b.get('progress',0)),item_id)); sync_progress(c,phase['project_id']); audit(c,u['id'],'Editar','phase',item_id)
        elif p.startswith('/api/tasks/'):
            try: item_id=int(p.rsplit('/',1)[1])
            except ValueError: return self.send(400,{"error":"Tarea inválida"})
            if not b.get('title'): return self.send(400,{"error":"El título es obligatorio"})
            old=c.execute("SELECT phase_id,status,title,project_id FROM tasks WHERE id=?",(item_id,)).fetchone()
            if not old: return self.send(404,{"error":"Tarea no encontrada"})
            new_status=b.get('status','Por hacer'); c.execute("UPDATE tasks SET title=?,phase_id=?,assignee=?,status=?,due=? WHERE id=?",(b['title'],b.get('phase_id') or None,b.get('assignee',''),new_status,b.get('due',''),item_id)); sync_phase_progress(c,b.get('phase_id') or 0); sync_phase_progress(c,old['phase_id'] or 0)
            if old['status'] != new_status: notify(u['id'],'Tarea actualizada',f"{b['title']} cambió a {new_status}")
            audit(c,u['id'],'Editar','task',item_id)
        elif p.startswith('/api/activities/') or p.startswith('/api/calendar/') or p.startswith('/api/support/'):
            kind=p.split('/')[2]; table={'activities':'activities','calendar':'calendar_events','support':'tickets'}[kind]
            try: item_id=int(p.rsplit('/',1)[1])
            except ValueError: return self.send(400,{"error":"Registro inválido"})
            fields={'activities':['title','responsible','project','status','due'],'calendar':['title','event_date','responsible','project','type'],'support':['title','requester','project','priority','status']}[kind]
            if not b.get('title'): return self.send(400,{"error":"El título es obligatorio"})
            c.execute(f"UPDATE {table} SET {','.join(x+'=?' for x in fields)} WHERE id=?",tuple(b.get(x,'') for x in fields)+(item_id,)); audit(c,u['id'],'Editar',kind,item_id)
        elif p.startswith('/api/requests/'):
            try: item_id=int(p.rsplit('/',1)[1])
            except ValueError: return self.send(400,{"error":"Solicitud inválida"})
            if not b.get('subject'): return self.send(400,{"error":"El asunto es obligatorio"})
            c.execute("UPDATE requests SET subject=?,organization=?,priority=?,status=? WHERE id=?",(b['subject'],b.get('organization',''),b.get('priority','Media'),b.get('status','En evaluación'),item_id)); audit(c,u['id'],'Editar','request',item_id)
        elif p.startswith('/api/projects/'):
            try: item_id=int(p.rsplit('/',1)[1])
            except ValueError: return self.send(400,{"error":"Proyecto inválido"})
            if not b.get('name'): return self.send(400,{"error":"El nombre es obligatorio"})
            c.execute("UPDATE projects SET name=?,organization=?,status=?,priority=?,due=?,budget=?,hours=?,risks=?,deliverables=? WHERE id=?",(b['name'],b.get('organization',''),b.get('status','En análisis'),b.get('priority','Media'),b.get('due',''),b.get('budget',''),int(b.get('hours',0) or 0),b.get('risks',''),b.get('deliverables',''),item_id)); audit(c,u['id'],'Editar','project',item_id)
        else: return self.send(404,{"error":"Ruta no encontrada"})
        c.commit(); return self.send(200,{"ok":True})
    def do_DELETE(self):
        p=urlparse(self.path).path; u=self.user()
        if not u: return self.send(401,{"error":"Sesión requerida"})
        c=db()
        if p.startswith('/api/phases/'):
            table='phases'
        elif p.startswith('/api/documents/'):
            try: item_id=int(p.rsplit('/',1)[1])
            except ValueError: return self.send(400,{"error":"Documento inválido"})
            c.execute("DELETE FROM documents WHERE id=?",(item_id,)); audit(c,u['id'],'Eliminar','document',item_id); c.commit(); return self.send(200,{"ok":True})
        elif p.startswith('/api/tasks/'):
            table='tasks'
        elif p.startswith('/api/activities/'):
            table='activities'
        elif p.startswith('/api/calendar/'):
            table='calendar_events'
        elif p.startswith('/api/support/'):
            table='tickets'
        elif p.startswith('/api/requests/'):
            table='requests'
        elif p.startswith('/api/projects/'):
            table='projects'
        else: return self.send(404,{"error":"Ruta no encontrada"})
        try: item_id=int(p.rsplit('/',1)[1])
        except ValueError: return self.send(400,{"error":"Registro inválido"})
        project_id=None; phase_id=None
        if table in ('activities','calendar_events','tickets'):
            c.execute(f"DELETE FROM {table} WHERE id=?",(item_id,)); audit(c,u['id'],'Eliminar',table,item_id); c.commit(); return self.send(200,{"ok":True})
        if table=='requests':
            c.execute("DELETE FROM requests WHERE id=?",(item_id,)); audit(c,u['id'],'Eliminar','request',item_id); c.commit(); return self.send(200,{"ok":True})
        if table=='projects':
            for child in ('tasks','phases','documents','project_comments'): c.execute(f"DELETE FROM {child} WHERE project_id=?",(item_id,))
            c.execute("DELETE FROM projects WHERE id=?",(item_id,)); audit(c,u['id'],'Eliminar','project',item_id); c.commit(); return self.send(200,{"ok":True})
        if table=='phases':
            phase=c.execute("SELECT project_id FROM phases WHERE id=?",(item_id,)).fetchone()
            if not phase: return self.send(404,{"error":"Fase no encontrada"})
            project_id=phase['project_id']
        else:
            task=c.execute("SELECT phase_id,project_id FROM tasks WHERE id=?",(item_id,)).fetchone()
            if not task: return self.send(404,{"error":"Tarea no encontrada"})
            phase_id=task['phase_id']; project_id=task['project_id']
        c.execute(f"DELETE FROM {table} WHERE id=?",(item_id,)); audit(c,u['id'],'Eliminar',table.rstrip('s'),item_id)
        if phase_id: sync_phase_progress(c,phase_id)
        if project_id: sync_progress(c,project_id)
        c.commit(); return self.send(200,{"ok":True})
    def do_POST(self):
        p=urlparse(self.path).path
        if p=="/api/login":
            b=self.body(); u=rows("SELECT id,name,email,role FROM users WHERE email=? AND password=? AND active=1",(b.get('email',''),hashlib.sha256(b.get('password','').encode()).hexdigest()))
            if not u: return self.send(401,{"error":"Correo o contraseña incorrectos"})
            token=secrets.token_urlsafe(32); SESSIONS[token]={'user':u[0],'expires':datetime.now()+timedelta(hours=SESSION_HOURS)}; return self.send(200,{"user":u[0],"token":token,"expires_in":SESSION_HOURS*3600})
        u=self.user()
        if not u: return self.send(401,{"error":"Sesión requerida"})
        b=self.body(); c=db()
        if p=="/api/logout": return self.send(200,{"ok":True})
        if p=="/api/password":
            if not b.get('current') or not b.get('new') or len(b['new'])<8: return self.send(400,{"error":"Contraseña actual y nueva de mínimo 8 caracteres son obligatorias"})
            old=hashlib.sha256(b['current'].encode()).hexdigest(); new=hashlib.sha256(b['new'].encode()).hexdigest()
            if not c.execute("SELECT 1 FROM users WHERE id=? AND password=?",(u['id'],old)).fetchone(): return self.send(401,{"error":"La contraseña actual no coincide"})
            c.execute("UPDATE users SET password=? WHERE id=?",(new,u['id'])); audit(c,u['id'],'Cambiar','password',u['id']); c.commit(); return self.send(200,{"ok":True})
        if p=="/api/phases":
            if not b.get('project_id') or not b.get('name'): return self.send(400,{"error":"Proyecto y nombre son obligatorios"})
            cur=c.execute("INSERT INTO phases(project_id,name,status,progress) VALUES(?,?,?,?)",(b['project_id'],b['name'],b.get('status','Pendiente'),int(b.get('progress',0)))); sync_progress(c,b['project_id']); audit(c,u['id'],'Crear','phase',cur.lastrowid); c.commit(); return self.send(201,{"ok":True})
        if p=="/api/tasks":
            if not b.get('project_id') or not b.get('title'): return self.send(400,{"error":"Proyecto y título son obligatorios"})
            status=b.get('status','Por hacer'); cur=c.execute("INSERT INTO tasks(project_id,phase_id,title,assignee,status,due) VALUES(?,?,?,?,?,?)",(b['project_id'],b.get('phase_id') or None,b['title'],b.get('assignee',''),status,b.get('due',''))); sync_phase_progress(c,b.get('phase_id') or 0); audit(c,u['id'],'Crear','task',cur.lastrowid); c.commit(); notify(u['id'],'Nueva tarea',f"Se creó: {b['title']}"); return self.send(201,{"ok":True})
        if p=="/api/documents":
            if not b.get('project_id') or not b.get('name') or not b.get('data'): return self.send(400,{"error":"Proyecto, nombre y archivo son obligatorios"})
            cur=c.execute("INSERT INTO documents(project_id,name,mime,data) VALUES(?,?,?,?)",(b['project_id'],b['name'],b.get('mime','application/octet-stream'),b['data'])); audit(c,u['id'],'Crear','document',cur.lastrowid); c.commit(); return self.send(201,{"ok":True,"id":cur.lastrowid})
        if p=="/api/project-comments":
            if not b.get('project_id') or not b.get('body'): return self.send(400,{"error":"Proyecto y comentario son obligatorios"})
            cur=c.execute("INSERT INTO project_comments(project_id,user_id,body) VALUES(?,?,?)",(b['project_id'],u['id'],b['body'])); audit(c,u['id'],'Crear','comment',cur.lastrowid); c.commit(); return self.send(201,{"ok":True})
        if p=="/api/activities":
            if not b.get('title'): return self.send(400,{"error":"El título es obligatorio"})
            cur=c.execute("INSERT INTO activities(title,responsible,project,status,due) VALUES(?,?,?,?,?)",(b['title'],b.get('responsible',''),b.get('project',''),b.get('status','Pendiente'),b.get('due',''))); audit(c,u['id'],'Crear','activity',cur.lastrowid); c.commit(); return self.send(201,{"ok":True})
        if p=="/api/calendar":
            if not b.get('title'): return self.send(400,{"error":"El título es obligatorio"})
            cur=c.execute("INSERT INTO calendar_events(title,event_date,responsible,project,type) VALUES(?,?,?,?,?)",(b['title'],b.get('event_date',''),b.get('responsible',''),b.get('project',''),b.get('type','Reunión'))); audit(c,u['id'],'Crear','calendar',cur.lastrowid); c.commit(); return self.send(201,{"ok":True})
        if p=="/api/support":
            if not b.get('title'): return self.send(400,{"error":"El título es obligatorio"})
            cur=c.execute("INSERT INTO tickets(title,requester,project,priority,status) VALUES(?,?,?,?,?)",(b['title'],b.get('requester',''),b.get('project',''),b.get('priority','Media'),b.get('status','Abierto'))); audit(c,u['id'],'Crear','support',cur.lastrowid); c.commit(); return self.send(201,{"ok":True})
        if p=="/api/projects":
            code=f"PRY-{2026}-{c.execute('SELECT COUNT(*) FROM projects').fetchone()[0]+20:03d}"; cur=c.execute("INSERT INTO projects(code,name,organization,owner,status,priority,progress,due) VALUES(?,?,?,?,?,?,?,?)",(code,b['name'],b.get('organization',''),u['name'],b.get('status','En análisis'),b.get('priority','Media'),0,b.get('due',''))); audit(c,u['id'],'Crear','project',cur.lastrowid); c.commit(); notify(u['id'],'Nuevo proyecto',f"Se creó {code}: {b['name']}"); return self.send(201,{"ok":True,"code":code})
        if p=="/api/requests":
            code=f"SOL-{2026}-{c.execute('SELECT COUNT(*) FROM requests').fetchone()[0]+120:03d}"; cur=c.execute("INSERT INTO requests(code,subject,organization,requester,priority,status) VALUES(?,?,?,?,?,?)",(code,b['subject'],b.get('organization',''),u['name'],b.get('priority','Media'),'En evaluación')); audit(c,u['id'],'Crear','request',cur.lastrowid); c.commit(); notify(u['id'],'Nueva solicitud',f"Se registró {code}: {b['subject']}"); return self.send(201,{"ok":True,"code":code})
        if p.startswith('/api/requests/') and p.endswith('/action'):
            try: request_id=int(p.split('/')[-2])
            except ValueError: return self.send(400,{"error":"Solicitud inválida"})
            req=c.execute("SELECT * FROM requests WHERE id=?",(request_id,)).fetchone()
            if not req: return self.send(404,{"error":"Solicitud no encontrada"})
            action=b.get('action')
            if action in ('approve','reject'):
                status='Aprobada' if action=='approve' else 'Rechazada'; c.execute("UPDATE requests SET status=? WHERE id=?",(status,request_id)); audit(c,u['id'],status,'request',request_id); c.commit(); notify(u['id'],'Solicitud actualizada',f"{req['code']} quedó {status}"); return self.send(200,{"ok":True,"status":status})
            if action=='convert':
                if req['status']!='Aprobada': return self.send(400,{"error":"Solo se pueden convertir solicitudes aprobadas"})
                cur=c.execute("INSERT INTO projects(code,name,organization,owner,status,priority,progress,due) VALUES(?,?,?,?,?,?,?,?)",(f"PRY-{2026}-{c.execute('SELECT COUNT(*) FROM projects').fetchone()[0]+20:03d}",req['subject'],req['organization'],u['name'],'En análisis',req['priority'],0,'')); c.execute("UPDATE requests SET status='Convertida' WHERE id=?",(request_id,)); audit(c,u['id'],'Convertir','request',request_id); c.commit(); notify(u['id'],'Solicitud convertida',f"{req['code']} se convirtió en proyecto"); return self.send(201,{"ok":True,"project_id":cur.lastrowid})
            return self.send(400,{"error":"Acción no válida"})
        if p=="/api/users":
            if u['role']!='admin': return self.send(403,{"error":"Solo administración puede crear usuarios"})
            if not b.get('email') or not b.get('password') or not b.get('name'): return self.send(400,{"error":"Nombre, correo y contraseña son obligatorios"})
            try: cur=c.execute("INSERT INTO users(name,email,password,role) VALUES(?,?,?,?)",(b['name'],b['email'],hashlib.sha256(b['password'].encode()).hexdigest(),b.get('role','user'))); audit(c,u['id'],'Crear','user',cur.lastrowid); c.commit()
            except sqlite3.IntegrityError: return self.send(409,{"error":"El correo ya está registrado"})
            return self.send(201,{"ok":True})
        if p=="/api/permissions":
            if u['role']!='admin': return self.send(403,{"error":"Solo administración puede modificar permisos"})
            if not b.get('role') or not b.get('module'): return self.send(400,{"error":"Rol y módulo son obligatorios"})
            c.execute("INSERT INTO permissions(role,module,can_view,can_create,can_edit,can_delete) VALUES(?,?,?,?,?,?) ON CONFLICT(role,module) DO UPDATE SET can_view=excluded.can_view,can_create=excluded.can_create,can_edit=excluded.can_edit,can_delete=excluded.can_delete",(b['role'],b['module'],int(bool(b.get('can_view'))),int(bool(b.get('can_create'))),int(bool(b.get('can_edit'))),int(bool(b.get('can_delete'))))); audit(c,u['id'],'Editar','permission',0,f"{b['role']}:{b['module']}"); c.commit(); return self.send(200,{"ok":True})
        if p=="/api/notifications/read":
            if b.get('id'): c.execute("UPDATE notifications SET read=1 WHERE id=? AND user_id=?",(b['id'],u['id']))
            else: c.execute("UPDATE notifications SET read=1 WHERE user_id=?",(u['id'],))
            c.commit(); return self.send(200,{"ok":True})
        return self.send(404,{"error":"Ruta no encontrada"})

seed()
ThreadingHTTPServer(("127.0.0.1",4173),Handler).serve_forever()
