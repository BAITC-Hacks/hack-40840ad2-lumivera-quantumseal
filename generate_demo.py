"""Explicit deterministic synthetic dataset generation; never called on startup."""
import csv
import json
from pathlib import Path


def generate(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    tracks = ['Management', 'Product', 'Engineering']
    formats = ['workshop', 'course', 'mentoring']
    names = ['Планирование', 'Обратная связь', 'Делегирование', 'Управление рисками', 'Коммуникация']
    skills = [{'id': f'S{i+1:03}', 'name': f'{names[i%5]} {i//5+1}', 'track': tracks[i//20],
               'requirements': {'Junior': 1, 'Middle': 3, 'Senior': 5}} for i in range(60)]
    employees = [{'id': f'E{i+1:03}', 'name': f'Demo {i+1:03}', 'track': tracks[i%3],
                  'grade': ['Junior', 'Middle', 'Senior'][i//3%3], 'preferred_format': formats[i%3],
                  'weekly_hours': 2+i%5,
                  'skills': {s['id']: 1+(i+j)%3 for j, s in enumerate(skills) if s['track'] == tracks[i%3]}}
                 for i in range(200)]
    events = [{'id': f'EV{i+1:03}', 'title': f'Практика {i+1:02}: {tracks[i%3]}',
               'format': formats[i//3%3], 'hours': 2+i%4, 'active': True, 'prerequisites': {},
               'gains': {s['id']: 1 for j, s in enumerate(skills) if s['track'] == tracks[i%3] and j%4 == i//3%4}}
              for i in range(40)]
    for name, value in [('employees', employees), ('events', events), ('skills', skills)]:
        (directory/f'{name}.json').write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    with (directory/'activity_history.csv').open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['employee_id', 'event_id', 'date', 'status', 'format'])
        writer.writeheader()
        for i, employee in enumerate(employees):
            for month in range(24):
                event = events[(i+month)%40]
                absolute = 2024*12+8+month
                writer.writerow({'employee_id': employee['id'], 'event_id': event['id'],
                                 'date': f'{absolute//12:04}-{absolute%12+1:02}-15',
                                 'status': 'completed' if month%3 == 0 else 'skipped', 'format': event['format']})


if __name__ == '__main__':
    generate(Path(__file__).parent/'data')
