"""Canonical starter-kit boundary and transactional progress storage."""
import csv
import hashlib
import json
import sqlite3
from copy import deepcopy
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from recommendation_engine import GRADES, assess, recommend


def load_data(directory):
    directory = Path(directory)
    data = {name: json.loads((directory / f'{name}.json').read_text(encoding='utf-8-sig'))
            for name in ('employees', 'events', 'skills')}
    with (directory / 'activity_history.csv').open(encoding='utf-8-sig', newline='') as f:
        data['history'] = list(csv.DictReader(f))
    # Add official schema mappings here when its actual contract is available.
    for name in ('employees', 'events', 'skills'):
        ids = [item['id'] for item in data[name]]
        if not ids or len(ids) != len(set(ids)):
            raise ValueError(f'{name}: empty dataset or duplicate IDs')
    skill_ids = {s['id'] for s in data['skills']}
    event_ids = {e['id'] for e in data['events']}
    employee_ids = {e['id'] for e in data['employees']}
    def levels(values):
        return all(k in skill_ids and type(v) is int and 0 <= v <= 5 for k, v in values.items())
    for s in data['skills']:
        if set(s['requirements']) != set(GRADES) or any(type(v) is not int or not 1 <= v <= 5 for v in s['requirements'].values()):
            raise ValueError('Invalid grade requirements')
    for e in data['employees']:
        if e['grade'] not in GRADES or not levels(e['skills']) or e['weekly_hours'] <= 0 or not any(s['track'] == e['track'] for s in data['skills']):
            raise ValueError('Invalid employee')
    for e in data['events']:
        if not levels(e['gains']) or not levels(e['prerequisites']) or e['hours'] <= 0 or type(e['active']) is not bool:
            raise ValueError('Invalid event')
    for h in data['history']:
        if h['employee_id'] not in employee_ids or h['event_id'] not in event_ids or h['status'] not in ('completed', 'skipped'):
            raise ValueError('Invalid history reference/status')
        datetime.fromisoformat(h['date'])
    return data


class Store:
    def __init__(self, data_dir, db_path):
        self.data = load_data(data_dir)
        self.db_path = str(db_path)
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        fingerprint = hashlib.sha256(json.dumps(self.data, sort_keys=True).encode()).hexdigest()
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS metadata (fingerprint TEXT)')
            row = db.execute('SELECT fingerprint FROM metadata').fetchone()
            if row and row[0] != fingerprint:
                raise ValueError('Dataset changed: use a new --db path to isolate progress')
            if not row:
                db.execute('INSERT INTO metadata VALUES (?)', (fingerprint,))
            db.execute('CREATE TABLE IF NOT EXISTS completions (employee_id TEXT, event_id TEXT, date TEXT, PRIMARY KEY(employee_id,event_id))')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.db_path)
        try:
            with db:
                yield db
        finally:
            db.close()

    def profile(self, employee_id, db=None):
        employee = next((deepcopy(e) for e in self.data['employees'] if e['id'] == employee_id), None)
        if employee is None:
            raise KeyError(employee_id)
        history = [dict(h) for h in self.data['history'] if h['employee_id'] == employee_id]
        if db is None:
            with self.connect() as connection:
                rows = connection.execute('SELECT event_id,date FROM completions WHERE employee_id=?', (employee_id,)).fetchall()
        else:
            rows = db.execute('SELECT event_id,date FROM completions WHERE employee_id=?', (employee_id,)).fetchall()
        events = {e['id']: e for e in self.data['events']}
        for event_id, date in rows:
            event = events[event_id]
            for sid, gain in event['gains'].items():
                employee['skills'][sid] = min(5, employee['skills'].get(sid, 0) + gain)
            history.append({'employee_id': employee_id, 'event_id': event_id, 'date': date,
                            'status': 'completed', 'format': event['format']})
        return {'employee': employee, 'assessment': assess(employee, self.data['skills']),
                'history': sorted(history, key=lambda h: h['date'], reverse=True),
                'recommendations': recommend(employee, self.data['events'], self.data['skills'], history)}

    def complete(self, employee_id, event_id):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            profile = self.profile(employee_id, db)
            if any(h['event_id'] == event_id and h['status'] == 'completed' for h in profile['history']):
                return False
            if event_id not in {r['event']['id'] for r in profile['recommendations']}:
                raise ValueError('Only a currently recommended activity can be completed')
            db.execute('INSERT INTO completions VALUES (?,?,?)',
                       (employee_id, event_id, datetime.now(timezone.utc).isoformat()))
        return True
