"""Run mod checks without permitting missing dependencies to masquerade as a pass."""
import keystone, unicorn, pefile, capstone
import json
import hashlib
from collections import Counter
from pathlib import Path
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


def compare_player_snapshots(public_before, reference_before, committed_after, generation):
    """Validate managed capture contents, not ownership or capture-time ordering.

    The producer must preserve both before buffers before its single Start.
    The release verifier must additionally bind them to the owned session,
    final package, source manifests, map loads and durable battle records.
    """
    if generation <= 0 or len(public_before) < 1172 or len(committed_after) != 3024:
        raise ValueError('Incomplete player snapshot or invalid attack generation')
    public_version, attack, placement, rendered, _ = struct.unpack_from('<5I', public_before)
    if public_version != 1 or attack != generation:
        raise ValueError('Public prediction belongs to another attack')
    model_count = struct.unpack_from('<I', public_before, 776)[0]
    # Match native Start admission: stale/unavailable rendering freezes an
    # empty ordinary forecast, independently of an available full reference.
    forecast_count = model_count if rendered == placement and 0 < model_count <= 7 else 0
    capture_version, capture_generation, armed, positions, quantities, failures, overflow, sequence = struct.unpack_from(
        '<8I', committed_after)
    if (capture_version != 2 or capture_generation != generation or armed or positions or quantities or
            failures or overflow or sequence & 1):
        raise ValueError('Committed capture is stale, partial or uses developer result observers')
    header = struct.unpack_from('<8I', committed_after, 1616)
    version, frozen_generation, frozen, frozen_count, width, height, committed, capture_failures = header
    if (version != 1 or frozen_generation != generation or frozen != 1 or frozen_count != forecast_count or
            committed != 1 or capture_failures or not 8 <= width <= 32 or not 4 <= height <= 32):
        raise ValueError('Player forecast/facts lifetime or native dimensions are invalid')
    world, own_army, enemy_army, own_count, enemy_count, failures, overflow = struct.unpack_from(
        '<7I', committed_after, 1816)
    if (not world or not own_army or not enemy_army or own_army == enemy_army or
            not 1 <= own_count <= 7 or not 1 <= enemy_count <= 7 or failures or overflow):
        raise ValueError('Initial armies are incomplete or not distinct')
    if any(struct.unpack_from('<3I', committed_after, 2180)):
        raise ValueError('Script result observers must not supply ordinary capture data')
    if any(struct.unpack_from('<4I', committed_after, 1600)):
        raise ValueError('Developer roster observers must not supply ordinary capture data')

    def read_stack(offset, require_actor, require_quantity):
        actor, creature, quantity, footprint, x, y = struct.unpack_from('<4I2i', committed_after, offset)
        if (not 1 <= creature <= 1024 or quantity > 0x7fffffff or
                (require_actor and not actor) or (require_quantity and not quantity) or
                footprint not in (1, 2) or not footprint + 1 <= x <= width - 3 or
                not footprint <= y <= height - 2):
            raise ValueError('Invalid stack or footprint outside the playable field')
        return {'actor': actor, 'type': creature, 'quantity': quantity, 'footprint': footprint, 'cell': [x, y]}

    forecast = [read_stack(1648 + index * 24, False, False) for index in range(forecast_count)]
    for index, stack in enumerate(forecast):
        creature = struct.unpack_from('<I', public_before, 920 + index * 4)[0]
        quantity = struct.unpack_from('<I', public_before, 1144 + index * 4)[0]
        cell = list(struct.unpack_from('<2i', public_before, 96 + index * 8))
        if (stack['type'], stack['quantity'], stack['cell']) != (creature, quantity, cell):
            raise ValueError('Frozen forecast differs from the public data saved before Start')
    own = [read_stack(1844 + index * 24, True, True) for index in range(own_count)]
    actual = [read_stack(2012 + index * 24, True, True) for index in range(enemy_count)]
    if len({stack['actor'] for stack in own + actual}) != own_count + enemy_count:
        raise ValueError('An actor appears more than once in the committed armies')
    if len(reference_before) != 20 + enemy_count * 52:
        raise ValueError('Full reference does not contain every defender')
    reference_attack, reference_version, reference_placement, reference_count, reference_complete = struct.unpack_from(
        '<5I', reference_before)
    if ((reference_attack, reference_version, reference_count, reference_complete) != (generation, 1, enemy_count, 1) or
            not reference_placement or (forecast_count and reference_placement != placement)):
        raise ValueError('Full reference is incomplete or belongs to another placement')
    if committed_after[2192:2192 + len(reference_before)] != reference_before:
        raise ValueError('Full reference changed after Start')
    decisions = [struct.unpack_from('<6I4i3I', reference_before, 20 + index * 52)
                 for index in range(enemy_count)]
    if ([row[3] for row in decisions] != list(range(1, enemy_count + 1)) or
            any(row[4] > 7 or row[5] > 1 or not 1 <= row[10] <= 6 or row[11] > 1 or row[12] > 1
                for row in decisions)):
        raise ValueError('Full reference lacks a valid placement order or explanation rule')
    reference_units = Counter((row[0], row[1], row[2], row[6], row[7]) for row in decisions)
    actual_units = Counter((stack['type'], stack['quantity'], stack['footprint'], *stack['cell']) for stack in actual)
    if reference_units != actual_units:
        raise ValueError('Full reference disagrees with the actual initial army')

    def occupied_cells(stacks):
        return Counter((stack['cell'][0] - horizontal, stack['cell'][1] - vertical)
                       for stack in stacks for horizontal in range(stack['footprint'])
                       for vertical in range(stack['footprint']))

    predicted_cells, actual_cells = occupied_cells(forecast), occupied_cells(actual)
    if any(count != 1 for count in occupied_cells(own + actual).values()):
        raise ValueError('Initial army footprints overlap')
    predicted_positions = Counter((*stack['cell'], stack['footprint']) for stack in forecast)
    actual_positions = Counter((*stack['cell'], stack['footprint']) for stack in actual)
    return {'prediction': forecast, 'observed': actual, 'own': own,
            'position_full_match': (forecast_count == enemy_count and predicted_cells == actual_cells and
                                    predicted_positions == actual_positions),
            'reference_full_match': True, 'reference_decisions': [list(row) for row in decisions],
            'predicted_only': sorted((predicted_cells - actual_cells).elements()),
            'actual_only': sorted((actual_cells - predicted_cells).elements())}

def verify_player_campaign_data(report, fixtures, read_evidence):
    """Verify complete managed rounds; file/package provenance belongs to caller."""
    if (report.get('schema') != 2 or report.get('transport') != 'managed_owned_session' or
            report.get('mode') != 'normal_public_prediction' or report.get('error') or
            report.get('requested_rounds') != 10 or set(fixtures) != {'polygon', 'rmg_a', 'rmg_b'}):
        raise ValueError('Expected a completed normal managed ten-load campaign')
    if (fixtures['polygon'].get('kind') != 'authored_polygon' or
            any(fixtures[family].get('kind') != 'tagged_universe_rmg' for family in ('rmg_a', 'rmg_b')) or
            len({fixture['name'].casefold() for fixture in fixtures.values()}) != 3 or
            len({fixture['map_sha256'] for fixture in fixtures.values()}) != 3 or
            len({fixtures[family]['source_name'].casefold() for family in ('rmg_a', 'rmg_b')}) != 2 or
            len({fixtures[family]['source_sha256'] for family in ('rmg_a', 'rmg_b')}) != 2):
        raise ValueError('Campaign requires one authored map and two distinct RMG maps and sources')
    owner = report.get('owner', {})
    if set(owner) != {'pid', 'created'} or any(type(value) is not int or value <= 0 for value in owner.values()):
        raise ValueError('Campaign lacks a valid owned process identity')
    runs = report.get('runs', [])
    if len(runs) != 10:
        raise ValueError('Campaign lacks ten fresh map loads')
    schedule = ('polygon', 'rmg_a', 'rmg_b')
    tokens, identities, generations = set(), set(), set()
    previous_generation, previous_return = 0, 0
    total = full = mixed_total = mixed_full = reference_full = 0
    for index, run in enumerate(runs):
        family = schedule[index % 3]
        fixture = fixtures[family]
        load = run.get('load', {})
        token = load.get('token')
        if (run.get('round') != index + 1 or run.get('family') != family or
                run.get('map') != fixture['name'] or load.get('owner') != owner or
                not isinstance(token, str) or not token or token in tokens or
                load.get('status') != 'ready' or load.get('phase') != 'adventure' or
                not 0 < load.get('submitted_ns', 0) < load.get('ready_ns', 0) or
                load['submitted_ns'] <= previous_return or
                load.get('map_sha256') != fixture['map_sha256']):
            raise ValueError('Map load is missing, reused, out of order or not confirmed')
        tokens.add(token)
        packs = fixture['packs']
        if not packs or len({pack['name'] for pack in packs}) != len(packs):
            raise ValueError('Fixture packs are empty or duplicated')
        records = [json.loads(read_evidence(reference)) for reference in run.get('battles', [])]
        if [battle.get('pack') for battle in records] != [pack['name'] for pack in packs]:
            raise ValueError('Map load does not contain every selected pack in order')
        last_return = load['ready_ns']
        for pack, battle in zip(packs, records):
            generation, identity = battle.get('generation', 0), battle.get('id')
            before, start, after = [battle.get(key, 0) for key in ('before_start_ns', 'start_ns', 'after_start_ns')]
            returned = battle.get('return', {})
            if (battle.get('owner') != owner or not isinstance(identity, str) or not identity or
                    type(generation) is not int or identity in identities or generation in generations or generation <= previous_generation or
                    not last_return < before < start < after or battle.get('clock') != 'perf_counter_ns' or
                    returned.get('phase') != 'adventure' or returned.get('owner') != owner or
                    returned.get('generation') != generation or returned.get('time_ns', 0) <= after):
                raise ValueError('Battle provenance, timing or adventure return is invalid')
            reference_before = read_evidence(battle['reference_before'])
            comparison = compare_player_snapshots(read_evidence(battle['public_before']),
                reference_before, read_evidence(battle['committed_after']), generation)
            explanation = battle.get('explanation', {})
            if (explanation.get('status') != 'verified_actual_placement' or
                    explanation.get('scope') != 'actual_placement' or
                    explanation.get('reference_sha256') != hashlib.sha256(reference_before).hexdigest() or
                    explanation.get('orders') != [row[3] for row in comparison['reference_decisions']] or
                    not isinstance(explanation.get('reason'), str) or not explanation['reason'].strip()):
                raise ValueError('Battle lacks a verified full-reference explanation of actual placement')
            identities.add(identity)
            generations.add(generation)
            previous_generation = generation
            last_return = returned['time_ns']
            matched = comparison['position_full_match']
            full += matched
            reference_full += comparison['reference_full_match']
            total += 1
            if not isinstance(pack.get('public_count'), int) or not 1 <= pack['public_count'] <= 7:
                raise ValueError('Fixture has no valid public stack classification')
            if pack['public_count'] > 1:
                mixed_total += 1
                mixed_full += matched
        completion = run.get('completion', {})
        if (completion.get('owner') != owner or completion.get('phase') != 'adventure' or
                completion.get('generation') != previous_generation or completion.get('time_ns', 0) < last_return):
            raise ValueError('Map round did not complete in the same owned session')
        previous_return = completion['time_ns']
    accepted = mixed_total > 0 and mixed_full * 10 >= mixed_total * 7 and reference_full == total
    summary = {'battles': total, 'full_matches': full, 'mixed_battles': mixed_total,
               'mixed_full_matches': mixed_full, 'reference_full_matches': reference_full,
               'solo_battles': total - mixed_total, 'solo_full_matches': full - mixed_full, 'passed': accepted}
    if report.get('acceptance') != summary:
        raise ValueError('Stored campaign totals differ from independently decoded battles')
    if not accepted:
        raise ValueError(f'Mixed-pack accuracy failed: {mixed_full}/{mixed_total}; require at least70%')
    return summary


def source_fingerprints():
    """Use xkit's build input graph, including the adapter and shared runtime."""
    import importlib.util
    import tempfile
    sdk = ROOT / 'devkit'
    sys.path.insert(0, str(sdk / 'scripts'))
    from plugin_core import core_source_snapshot
    specification = importlib.util.spec_from_file_location('accuracy_source_watch', sdk / 'scripts/plugin-watch.py')
    watcher_module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(watcher_module)
    with tempfile.TemporaryDirectory(prefix='h5-source-check-') as output:
        watcher = watcher_module.PluginWatch(ROOT, Path(output), None, {}, None)
        return {'source_hashes': watcher.snapshot(), 'core_source_hashes': core_source_snapshot(sdk / 'native')}


def verify_source_fingerprints(report):
    for name, expected in source_fingerprints().items():
        if report.get(name) != expected:
            raise ValueError('Historical or stale evidence cannot certify current sources: ' + name)


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
    report = json.loads(path.read_text(encoding='utf-8'))
    verify_source_fingerprints(report)
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
