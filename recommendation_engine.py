"""Deterministic, explainable content-based recommendation baseline."""
GRADES = ['Junior', 'Middle', 'Senior']


def assess(employee, skills):
    index = GRADES.index(employee['grade'])
    target = GRADES[min(index + 1, len(GRADES) - 1)]
    requirements = {s['id']: s['requirements'][target] for s in skills
                    if s['track'] == employee['track']}
    gaps = {sid: max(0, level - employee['skills'].get(sid, 0))
            for sid, level in requirements.items()}
    total = sum(requirements.values())
    return {'target_grade': target, 'at_top_grade': index == len(GRADES) - 1,
            'requirements': requirements, 'gaps': gaps,
            'progress': round(100 * (total - sum(gaps.values())) / total, 1)}


def recommend(employee, events, skills, history):
    assessment = assess(employee, skills)
    completed = {h['event_id'] for h in history if h['status'] == 'completed'}
    results = []
    for event in events:
        if event['id'] in completed or not event['active']:
            continue
        if any(employee['skills'].get(s, 0) < v for s, v in event['prerequisites'].items()):
            continue
        gain = sum(min(assessment['gaps'].get(s, 0), v) for s, v in event['gains'].items())
        if not gain:
            continue
        fit = float(event['format'] == employee['preferred_format'])
        time = min(1, employee['weekly_hours'] / event['hours'])
        similar = sum(h['status'] == 'completed' and h['format'] == event['format'] for h in history)
        novelty = 1 / (1 + similar)
        components = {'gap': round(0.55 * gain / sum(assessment['gaps'].values()), 4),
                      'format': round(0.20 * fit, 4), 'time': round(0.15 * time, 4),
                      'history': round(0.10 * novelty, 4)}
        results.append({'event': event, 'score': round(sum(components.values()), 4),
                        'components': components, 'expected_gain': gain,
                        'explanations': [
                            f'Навыки: закрывает {gain} балл(а) gap к {assessment["target_grade"]}.',
                            f'Формат: {event["format"]}; предпочтение сотрудника: {employee["preferred_format"]}.',
                            f'Нагрузка: {event["hours"]} ч; доступно {employee["weekly_hours"]} ч/неделю.',
                            f'История: завершено {similar} активностей этого формата; это событие ещё не завершено.']})
    return sorted(results, key=lambda r: (-r['score'], r['event']['id']))[:3]
