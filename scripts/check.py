"""Run mod checks without permitting missing dependencies to masquerade as a pass."""
import keystone, unicorn, pefile, capstone
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]

def verify_policy_decisions(report):
    """Compare original decisions by source army and observed evaluation lifetime."""
    if (report['generation'] != report['strategy_generation'] or report['failures'] or report['overflow']
            or report['strategy_mask'] != 3):
        raise ValueError('Strategy comparison requires complete matching-generation observations')
    armies = report['army_identities']
    strategies = report['strategies']
    if len(armies) != 2 or not all(armies) or armies[0] == armies[1] or len(strategies) != 2:
        raise ValueError('Expected two distinct captured army identities and strategies')
    if any(value not in (0, 1) for value in strategies):
        raise ValueError('Invalid captured strategy value')
    events = report['events']
    decisions = []
    block_start = 0
    for index, event in enumerate(events):
        if event['kind'] != 'decision':
            continue
        block = events[block_start:index]
        sources = [item for item in block if item['kind'] == 'capability_input']
        returns = [item for item in block if item['kind'] == 'capability_result']
        if (len(sources) != 1 or len(returns) != 1 or sources[0]['army_identity'] not in armies
                or block.index(sources[0]) >= block.index(returns[0])
                or not event['evaluation_identity'] or returns[0]['evaluation_identity'] != event['evaluation_identity']
                or event['defensive'] not in (0, 1)):
            raise ValueError('Original decision has no unique captured source army')
        army_index = armies.index(sources[0]['army_identity'])
        decisions.append({'event_index': index, 'evaluation_identity': event['evaluation_identity'],
                          'army_index': army_index, 'native': event['defensive'], 'own': strategies[army_index],
                          'matches': event['defensive'] == strategies[army_index]})
        block_start = index + 1
    if not decisions:
        raise ValueError('No original strategy decisions captured')
    policies = []
    for policy in report['policies']:
        fence = policy['events_seen']
        if not isinstance(fence, int) or not 0 <= fence <= len(events):
            raise ValueError('Policy observation has an invalid event boundary')
        candidates = [decision for decision in decisions if decision['event_index'] < fence
                      and decision['evaluation_identity'] == policy['evaluation_identity']]
        if len(candidates) != 1 or candidates[0]['native'] != policy['defensive']:
            raise ValueError('Policy observation is not aligned with one original decision')
        policies.append({'policy_label': policy['side'], 'army_index': candidates[0]['army_index'],
                         'native': policy['defensive'], 'matches': candidates[0]['matches']})
    if not policies:
        raise ValueError('No policy observations aligned')
    return {'ok': all(decision['matches'] for decision in decisions), 'decisions': decisions,
            'policies': policies, 'scope': 'decision flags with verified source/lifetime alignment',
            'goal_complete': False}

def verify_admin_data(report, expected_packs):
    from collections import Counter
    from datetime import datetime
    import hashlib
    if report.get('mode') != 'superadmin_source_research' or report.get('error'):
        raise ValueError('Expected an error-free Superadmin campaign')
    runs = report.get('runs', [])
    if report.get('requested_rounds') != 10 or len(runs) != 10:
        raise ValueError('Ten completed fresh loads are required')
    schedule = ('polygon', 'rmg_a', 'rmg_b')
    total = mixed = solo = 0
    for index, run in enumerate(runs):
        family = schedule[index % 3]
        fixture = report['fixtures'][family]
        if run.get('round') != index + 1 or run['map'] != fixture['name']:
            raise ValueError('Map rotation differs from the required schedule')
        if run.get('close', {}).get('status') != 'game_closed' or run.get('background_requested'):
            raise ValueError('Every owned visible game must close normally')
        if [battle['pack'] for battle in run['battles']] != expected_packs[family]:
            raise ValueError('A load omits or reorders required packs')
        for battle in run['battles']:
            predicted = battle['prediction']
            observed = battle['observed']
            if not battle.get('prediction_complete') or not battle.get('full_match'):
                raise ValueError('Incomplete or mismatching prediction: ' + battle['pack'])
            digest = hashlib.sha256(json.dumps(predicted, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
            if digest != battle['prediction_sha256']:
                raise ValueError('Frozen prediction hash differs')
            if datetime.fromisoformat(battle['prediction_frozen_at_utc']) >= datetime.fromisoformat(battle['observation_captured_at_utc']):
                raise ValueError('Prediction must precede observation')
            if 'observed_after_start_before_cleanup' not in battle:
                raise ValueError('Actual-before-cleanup evidence missing')
            for unit in predicted + observed:
                if not isinstance(unit.get('quantity'), int) or unit['quantity'] <= 0:
                    raise ValueError('Every exact quantity must be present')
            expected = Counter((unit['type'], unit['quantity'], *unit['cell']) for unit in predicted)
            actual = Counter((unit['type'], unit['quantity'], *unit['cell']) for unit in observed)
            early_actual = Counter((unit['type'], unit['quantity'], *unit['cell'])
                                   for unit in battle['observed_after_start_before_cleanup']['units'])
            if actual != early_actual:
                raise ValueError('Actual evidence changed during cleanup')
            if not expected or expected != actual:
                raise ValueError('Exact creature/quantity/cell mismatch: ' + battle['pack'])
            if not battle['comparison'].get('full_composition_match') or not battle['comparison'].get('quantities_checked'):
                raise ValueError('Stored strict comparison is missing')
            total += 1
            mixed += battle['fixture']['public_count'] > 1
            solo += battle['fixture']['public_count'] == 1
    summary = report.get('acceptance', {})
    if (summary.get('full_matches'), summary.get('battles'), summary.get('mixed_full_matches'),
        summary.get('mixed_battles'), summary.get('solo_full_matches'), summary.get('solo_battles')) != (total, total, mixed, mixed, solo, solo):
        raise ValueError('Stored totals differ from independently verified battles')
    return {'ok': True, 'scope': 'ten_rotated_superadmin_loads', 'goal_complete': False,
            'battles': total, 'mixed_battles': mixed, 'solo_battles': solo}


def verify_admin_report(path):
    import hashlib
    import importlib.util
    import os
    from zipfile import ZipFile
    import xml.etree.ElementTree as ET
    workspace = ROOT.parents[1] if (ROOT.parents[1] / 'scripts/sync-subrepos.ps1').is_file() else ROOT
    os.environ.setdefault('H5_WORKSPACE', str(workspace))
    os.environ.setdefault('H5_PREVIEW_BUILD', str(ROOT / '.local/player-build/Release'))
    specification = importlib.util.spec_from_file_location('verification_context', ROOT / 'scripts/native-preview-check.py')
    context = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(context)
    report = json.loads(path.read_text(encoding='utf-8'))
    files = {'source_sha256': ROOT / 'src/preview_plugin.cpp', 'driver_sha256': ROOT / 'scripts/accuracy-campaign.py',
             'native_check_sha256': Path(context.__file__),
             'plugin_sha256': context.ROOT / '.local/test-game/bin/Heroes5Mods/WorkshopDeploymentPreview.dll',
             'loader_sha256': context.BUILD / 'workshop_preview_loader.exe',
             'game_exe_sha256': context.ROOT / '.local/test-game/bin/H5_Game.exe',
             'devkit_probe_sha256': context.PROBE, 'devkit_control_sha256': context.CONTROL,
             'devkit_ui_sha256': context.GAME_UI}
    for name, filename in files.items():
        if report.get(name) != hashlib.sha256(filename.read_bytes()).hexdigest():
            raise ValueError('Stale or changed evidence: ' + name)
    if report['plugin_sha256'] != hashlib.sha256((context.BUILD / 'WorkshopDeploymentPreview.dll').read_bytes()).hexdigest():
        raise ValueError('Build and sandbox DLL differ')
    manifest = json.loads((context.ROOT / '.local/test-state/test-map.json').read_text(encoding='utf-8'))
    if len(manifest['packs']) != 36:
        raise ValueError('All36 authored compositions are required')
    expected = {'polygon': ['pack_' + str(index) for index in range(36)]}
    for family, fixture in report['fixtures'].items():
        map_file = context.ROOT / '.local/test-game/Maps' / (fixture['name'] + '.h5m')
        if fixture['map_sha256'] != hashlib.sha256(map_file.read_bytes()).hexdigest():
            raise ValueError('Test map hash changed: ' + family)
        if family == 'polygon':
            if fixture['map_sha256'] != manifest['sha256']:
                raise ValueError('Polygon differs from its authored manifest')
            continue
        source = context.ROOT / '.local/test-game/Maps' / fixture['source_name']
        if fixture['source_sha256'] != hashlib.sha256(source.read_bytes()).hexdigest():
            raise ValueError('RMG source hash changed')
        with ZipFile(map_file) as archive:
            document = ET.fromstring(archive.read(next(name for name in archive.namelist() if name.endswith('/map.xdb'))))
        monsters = [element for element in document.iter() if element.tag == 'AdvMapMonster']
        towns = [(int(element.findtext('Pos/x')), int(element.findtext('Pos/y'))) for element in document.iter() if element.tag == 'AdvMapTown']
        selected = []
        for count in range(1, 5):
            candidates = [(min(abs(int(monster.findtext('Pos/x')) - x) + abs(int(monster.findtext('Pos/y')) - y) for x, y in towns), index)
                          for index, monster in enumerate(monsters) if 1 + len(monster.findall('AdditionalStacks/Item')) == count]
            selected.extend(index for _, index in sorted(candidates)[:6])
        expected[family] = [monsters[index].findtext('Name') for index in sorted(selected)]
    return verify_admin_data(report, expected)


def main():
    if len(sys.argv) == 3 and sys.argv[1] == '--verify-superadmin':
        try:
            print(json.dumps(verify_admin_report(Path(sys.argv[2])), ensure_ascii=True))
            return 0
        except (ValueError, KeyError, OSError, StopIteration) as error:
            print(json.dumps({'ok': False, 'error': str(error)}, ensure_ascii=True))
            return 1

    suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests'))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    allowed_reasons = {'Pinned game EXE is needed for the native movement oracle',
                       'Pinned game EXE is needed for the native placement comparator oracle'}
    unexpected = [(str(test), reason) for test, reason in result.skipped if reason not in allowed_reasons]
    passed = result.wasSuccessful() and not unexpected and result.testsRun > 0
    print(json.dumps({'ok': passed, 'tests_run': result.testsRun, 'failures': len(result.failures),
                      'errors': len(result.errors), 'skipped': [(str(test), reason) for test, reason in result.skipped],
                      'unexpected_skips': unexpected}, ensure_ascii=True))
    return 0 if passed else 1

if __name__ == '__main__':
    raise SystemExit(main())
