"""Run isolated HTTP tests and capture reproducible evidence."""
import io
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT/'tests'))
from test_mvp import MVPTest


if __name__ == '__main__':
    evidence = ROOT/'evidence'
    evidence.mkdir(exist_ok=True)
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(MVPTest))
    (evidence/'tests.txt').write_text(stream.getvalue(), encoding='utf-8')
    print(stream.getvalue())
    if not result.wasSuccessful():
        raise SystemExit(1)
    test = MVPTest()
    test.setUp()
    try:
        report = {'status': 'PASS', 'transport': 'real localhost HTTP', 'profiles': []}
        for employee_id in ('E001', 'E002', 'E003'):
            test.login(employee_id)
            report['profiles'].append(test.call('/api/profile')[1])
        test.login('E001')
        before = test.call('/api/profile')[1]
        event = before['recommendations'][0]['event']['id']
        response = test.call('/api/complete', {'event_id': event})
        after = test.call('/api/profile')[1]
        report['completion'] = {'event_id': event, 'response': response,
                                'before': before['assessment']['progress'], 'after': after['assessment']['progress'],
                                'repeat': test.call('/api/complete', {'event_id': event})}
        (evidence/'demo_results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(report['completion']))
    finally:
        test.tearDown()
