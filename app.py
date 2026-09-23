"""Career Quest local demo. Python standard library only."""
import argparse
import json
import secrets
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from data_loader import Store

ROOT = Path(__file__).resolve().parent
PAGE = '''<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Career Quest</title><style>body{font:16px system-ui;max-width:1100px;margin:32px auto;padding:20px;background:#f1f5f9;color:#172033}h1{color:#164e63}section,article{background:white;padding:20px;margin:16px 0;border-radius:12px}button,input,select{padding:10px;margin:5px}button{background:#155e75;color:white;border:0;border-radius:6px;cursor:pointer}table{border-collapse:collapse;width:100%}td,th{padding:8px;border-bottom:1px solid #ddd;text-align:left}progress{width:100%}.muted{color:#526477}</style>
<h1>Career Quest · трек 03 «Управление»</h1><p class="muted">Синтетическая локальная демонстрация · объяснимый рекомендательный baseline</p>
<section id="login"><h2>Демо-вход</h2><p>Employee: E001–E200 / employee-demo. HR: HR / hr-demo.</p>
<form id="form"><input id="user" value="E001" aria-label="Логин"><input id="password" type="password" value="employee-demo" aria-label="Пароль"><button>Войти</button></form></section>
<button id="logout" hidden>Выйти</button><p id="message" role="status"></p><main id="content"></main>
<script>
let csrf=''; const $=id=>document.getElementById(id);
const esc=x=>String(x).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function api(path,body){let r=await fetch(path,{method:body?'POST':'GET',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:body?JSON.stringify(body):undefined});let v=await r.json();if(!r.ok)throw Error(v.error);return v;}
function table(headers,rows){return '<table><tr>'+headers.map(x=>'<th>'+esc(x)+'</th>').join('')+'</tr>'+rows.map(row=>'<tr>'+row.map(x=>'<td>'+esc(x)+'</td>').join('')+'</tr>').join('')+'</table>';}
async function render(){const me=await api('/api/me');csrf=me.csrf;$('login').hidden=true;$('logout').hidden=false;
if(me.role==='HR'){let d=await api('/api/hr');$('content').innerHTML='<section><h2>HR · обзор карьерного развития</h2><p>Агрегаты по синтетическим профилям. Решения о повышении принимает человек.</p>'+table(['Сотрудник','Траектория','Грейд','Цель','Готовность %'],d.employees.map(x=>[x.id,x.track,x.grade,x.target_grade,x.progress]))+'</section>';return;}
let p=await api('/api/profile'),e=p.employee,a=p.assessment;
$('content').innerHTML='<section><h2>'+esc(e.name)+' · '+esc(e.id)+'</h2><p>'+esc(e.track)+' · '+esc(e.grade)+' → '+esc(a.target_grade)+(a.at_top_grade?' (верхний грейд: развитие навыков)':'')+'</p><progress max="100" value="'+a.progress+'"></progress><p>Покрытие требований: '+a.progress+'%</p>'+table(['Навык','Текущий уровень','Требование','Gap'],Object.entries(a.requirements).map(([s,v])=>[s,e.skills[s]||0,v,a.gaps[s]]))+'</section><section><h2>Следующие шаги</h2><p>Оценки ожидаемые: демо-завершение начисляет баллы, не подтверждает реальную квалификацию.</p>'+ (p.recommendations.length?p.recommendations.map(r=>'<article><h3>'+esc(r.event.title)+'</h3><p>Рейтинг '+r.score+' · '+r.event.hours+' ч</p><ul>'+r.explanations.map(t=>'<li>'+esc(t)+'</li>').join('')+'</ul><button data-event="'+esc(r.event.id)+'">Выполнить активность (демо)</button></article>').join(''):'<p>Нет подходящих шагов. Требования закрыты либо каталог не покрывает оставшийся gap; обсудите план с HR.</p>')+'</section><section><h2>История активности</h2>'+table(['Дата','Событие','Статус','Формат'],p.history.map(h=>[h.date,h.event_id,h.status,h.format]))+'</section>';
document.querySelectorAll('[data-event]').forEach(b=>b.onclick=async()=>{b.disabled=true;try{await api('/api/complete',{event_id:b.dataset.event});await render();$('message').textContent='Прогресс обновлён и сохранён.';}catch(e){$('message').textContent=e.message;b.disabled=false;}});}
$('form').onsubmit=async e=>{e.preventDefault();try{await api('/api/login',{user:$('user').value,password:$('password').value});$('message').textContent='';await render();}catch(e){$('message').textContent=e.message;}};
$('logout').onclick=async()=>{await api('/api/logout',{});location.reload();};
render().catch(()=>{});
</script></html>'''


def make_server(store, port=8000):
    sessions = {}

    class Handler(BaseHTTPRequestHandler):
        def respond(self, status, value, cookie=None):
            raw = value.encode() if isinstance(value, str) else json.dumps(value, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'text/html; charset=utf-8' if isinstance(value, str) else 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('X-Frame-Options', 'DENY')
            if cookie:
                self.send_header('Set-Cookie', cookie)
            self.end_headers()
            self.wfile.write(raw)

        def session(self):
            cookie = SimpleCookie(self.headers.get('Cookie', ''))
            token = cookie.get('session')
            return sessions.get(token.value) if token else None

        def do_GET(self):
            if self.path == '/':
                return self.respond(200, PAGE)
            session = self.session()
            if not session:
                return self.respond(401, {'error': 'Войдите в демо-аккаунт'})
            if self.path == '/api/me':
                return self.respond(200, session)
            if self.path == '/api/profile' and session['role'] == 'employee':
                return self.respond(200, store.profile(session['user']))
            if self.path == '/api/hr' and session['role'] == 'HR':
                rows = []
                for employee in store.data['employees']:
                    p = store.profile(employee['id'])
                    rows.append({k: employee[k] for k in ('id', 'track', 'grade')} | {k: p['assessment'][k] for k in ('target_grade', 'progress')})
                return self.respond(200, {'employees': rows})
            return self.respond(403, {'error': 'Доступ запрещён'})

        def do_POST(self):
            try:
                length = int(self.headers.get('Content-Length', 0))
                if not 0 < length <= 4096:
                    raise ValueError('Invalid body size')
                body = json.loads(self.rfile.read(length))
                if not isinstance(body, dict):
                    raise ValueError('Expected JSON object')
                if self.path == '/api/login':
                    user = body.get('user')
                    role = 'HR' if user == 'HR' else 'employee'
                    valid = user == 'HR' or user in {e['id'] for e in store.data['employees']}
                    if not valid or body.get('password') != ('hr-demo' if role == 'HR' else 'employee-demo'):
                        return self.respond(401, {'error': 'Неверный демо-логин или пароль'})
                    token = secrets.token_urlsafe(32)
                    sessions[token] = {'role': role, 'user': user, 'csrf': secrets.token_urlsafe(32)}
                    return self.respond(200, {'ok': True}, f'session={token}; HttpOnly; SameSite=Strict; Path=/')
                session = self.session()
                if not session:
                    return self.respond(401, {'error': 'Authentication required'})
                if self.headers.get('X-CSRF-Token') != session['csrf']:
                    return self.respond(403, {'error': 'Invalid CSRF token'})
                if self.path == '/api/logout':
                    cookie = SimpleCookie(self.headers['Cookie'])
                    sessions.pop(cookie['session'].value, None)
                    return self.respond(200, {'ok': True}, 'session=; Max-Age=0; Path=/; HttpOnly; SameSite=Strict')
                if self.path != '/api/complete' or session['role'] != 'employee':
                    return self.respond(403, {'error': 'Доступ запрещён'})
                if set(body) != {'event_id'} or not isinstance(body['event_id'], str):
                    raise ValueError('Expected event_id only; employee comes from session')
                return self.respond(200, {'updated': store.complete(session['user'], body['event_id'])})
            except (ValueError, KeyError, TypeError) as exc:
                self.respond(400, {'error': str(exc)})

    return ThreadingHTTPServer(('127.0.0.1', port), Handler)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--data-dir', type=Path, default=ROOT/'data')
    parser.add_argument('--db', type=Path, default=ROOT/'runtime'/'progress.sqlite3')
    args = parser.parse_args()
    server = make_server(Store(args.data_dir, args.db), args.port)
    print(f'Career Quest: http://127.0.0.1:{server.server_port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
