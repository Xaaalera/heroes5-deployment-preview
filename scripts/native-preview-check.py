"""End-to-end WorkshopPolygon check for the compiled deployment-preview DLL."""
import json
import os
import argparse
from collections import Counter
import ctypes
from ctypes import wintypes
import importlib.util
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time


MOD_ROOT = Path(__file__).resolve().parents[1]
DEVKIT = MOD_ROOT / 'devkit'
if not (DEVKIT / 'scripts/native-probe.py').is_file():
    raise RuntimeError('Initialize devkit: git submodule update --init --recursive')
ROOT = Path(os.environ.get('H5_WORKSPACE') or MOD_ROOT).expanduser().resolve()
os.environ.setdefault('H5_WORKSPACE', str(ROOT))
BUILD = Path(os.environ.get('H5_PREVIEW_BUILD') or MOD_ROOT / '.local/build/deployment-preview-native').resolve()
PYTHON = sys.executable
LOADER = ROOT / '.local/dist/deployment-preview-native/workshop_preview_loader.exe'
PLUGIN = ROOT / '.local/dist/deployment-preview-native/WorkshopDeploymentPreview.dll'
CONTROL = DEVKIT / 'scripts/game_control.py'
PROBE = DEVKIT / 'scripts/native-probe.py'
GAME_UI = DEVKIT / 'scripts/game-ui.ps1'
DIAGNOSTIC = re.compile(
    r'public portraits=(\d+), model outputs=(\d+), hovered creature=(\d+), cursor cell=(\d+),(\d+), output alignment=(\d+)')


def command(*arguments, allowed=(0,)):
    completed = subprocess.run(arguments, cwd=ROOT, text=True, encoding='utf-8', capture_output=True)
    if completed.returncode not in allowed:
        raise RuntimeError((completed.stdout + completed.stderr).strip())
    return completed.stdout + completed.stderr


def control(*arguments):
    output = command(PYTHON, '-X', 'utf8', str(CONTROL), *arguments)
    return json.loads(output)


def capture(process_id, label):
    screen = json.loads(command('powershell', '-ExecutionPolicy', 'Bypass', '-File', str(GAME_UI),
                                'capture', '-OcrTiles', '-GameProcessId', str(process_id)))
    image = ROOT / '.local/test-state' / f'native-preview-{process_id}-{label}.png'
    shutil.copyfile(screen['Image'], image)
    screen['Image'] = str(image)
    image.with_suffix('.json').write_text(json.dumps(screen, ensure_ascii=False, indent=2), encoding='utf-8')
    return screen


def diagnostics(process_id):
    output = command(str(LOADER), '--pid', str(process_id), '--dll', str(PLUGIN), allowed=(1,))
    match = DIAGNOSTIC.search(output)
    if match is None:
        raise RuntimeError('Expected native preview diagnostics: ' + output.strip())
    public, models, hovered, x, y, alignment = (int(value) for value in match.groups())
    return {'public': public, 'models': models, 'hovered': hovered, 'cell': [x, y], 'alignment': alignment}


def wait_for_models(process_id, public_count):
    deadline = time.monotonic() + 10
    latest = None
    while time.monotonic() < deadline:
        latest = diagnostics(process_id)
        if latest['public'] == public_count and latest['models'] == public_count:
            trace = json.loads(command(str(LOADER), '--pid', str(process_id), '--dll', str(PLUGIN), '--projection-trace'))
            if trace['public'] != public_count or trace['models'] != public_count or len(trace['slots']) != public_count:
                raise RuntimeError('Incomplete projection snapshot: ' + json.dumps(trace))
            occupied = set()
            width, height = trace['grid']
            for slot in trace['slots']:
                x, y = slot['cell']
                size = slot['size']
                if size not in (1, 2) or not (size <= x < width - 1 and size <= y < height - 1):
                    raise RuntimeError('Invalid or out-of-bounds footprint: ' + json.dumps(trace))
                cells = {(column, row) for column in range(x - size + 1, x + 1)
                         for row in range(y - size + 1, y + 1)}
                if occupied & cells:
                    raise RuntimeError('Projection cells overlap: ' + str(sorted(occupied & cells)))
                occupied.update(cells)
            latest['footprints'] = trace['slots']
            latest['generation'] = trace['generation']
            return latest
        time.sleep(0.5)
    raise RuntimeError('Projection readiness timed out: ' + json.dumps(latest))


def find_projection(process_id, creature_type, candidates, mouse_options):
    for screen_x, screen_y in dict.fromkeys(candidates):
        command('powershell', '-ExecutionPolicy', 'Bypass', '-File', str(GAME_UI), 'move', *mouse_options,
                '-GameProcessId', str(process_id), '-X', str(screen_x), '-Y', str(screen_y))
        time.sleep(0.15)
        hovered = diagnostics(process_id)
        if hovered['models'] == 0:
            raise RuntimeError('Deployment ended during projection search')
        if hovered['hovered'] == creature_type:
            return screen_x, screen_y, hovered
    raise RuntimeError(f'Could not hover public type {creature_type}: ' + json.dumps(hovered))


def complete_battle(process_id, projection, observe=True):
    armed = control('deployment-observation', '--arm') if observe else None
    control('confirm')
    time.sleep(0.6)
    released = diagnostics(process_id)
    if released['models'] != 0 or released['hovered'] != 0:
        raise RuntimeError('Projection survived deployment confirmation: ' + json.dumps(released))
    if projection.get('card_open_before_start'):
        after_start = capture(process_id, 'after-start')
        after_text = ' '.join(line['Text'] for line in after_start['Lines']).lower()
        released['card_cleanup_image'] = after_start['Image']
        if any(word in after_text for word in ('умения', 'защита', 'падение')):
            raise RuntimeError('Open projection card survived Start: ' + after_text)
    observed = control('deployment-observation') if observe else None
    if observe and (observed['sequence'] != armed['sequence'] or not observed['units']):
        raise RuntimeError('No complete after-start observation for this battle: ' + json.dumps(observed))
    control('finish', '--winner', '0')
    time.sleep(0.25)
    control('results')
    time.sleep(0.35)
    result = {'release': released, 'hero': control('hero', 'Brem')}
    if observe:
        # Resolve public Lua constants only after returning to adventure mode.
        # Actual combat units never feed back into DLL prediction.
        expression = "''.." + "..','..".join(unit['creature'] for unit in observed['units'])
        types = [int(value) for value in control('eval', expression)['result'].split(',')]
        if len(types) != len(observed['units']):
            raise RuntimeError('Observed creature constants did not resolve completely')
        for unit, creature in zip(observed['units'], types):
            unit['type'] = creature
        predicted_cells = Counter((slot['type'], *slot['cell']) for slot in projection['footprints'])
        actual_cells = Counter((unit['type'], *unit['cell']) for unit in observed['units'])
        result['observation'] = observed
        result['comparison'] = {
            'exact_matches': sum((predicted_cells & actual_cells).values()),
            'predicted': sum(predicted_cells.values()), 'actual': sum(actual_cells.values()),
            'same_type_counts': Counter(slot['type'] for slot in projection['footprints']) == Counter(types),
        }
    return result


def main():
    global LOADER, PLUGIN
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--late-install", action="store_true", help="Check diagnostic attach and conflicting-hook refusal instead of packaged startup.")
    parser.add_argument('--system-input', action='store_true',
                        help='Opt in to foreground/shared-cursor input. Requires an exclusive mouse test interval.')
    parser.add_argument('--offscreen', action='store_true',
                        help='Explicit isolated automation only; never use for a visible user demo.')
    options = parser.parse_args()
    mouse_options = ['-SystemInput'] if options.system_input else []
    if options.late_install:
        LOADER = BUILD / 'workshop_preview_loader.exe'
        PLUGIN = BUILD / 'WorkshopDeploymentPreview.dll'
    if not LOADER.is_file() or not PLUGIN.is_file():
        raise RuntimeError('Build the native plugin before running this check')
    user_interface = ctypes.WinDLL('user32', use_last_error=True)
    user_interface.GetForegroundWindow.restype = wintypes.HWND
    previous_foreground = user_interface.GetForegroundWindow() or 0
    launch = json.loads(command(PYTHON, '-X', 'utf8', str(PROBE), 'launch', '--map', 'WorkshopPolygon', '--control',
                                *([] if options.late_install else ['--native-loader'])))
    process_id = launch['pid']
    result = {'pid': process_id, 'native_loader': launch['native_loader'], 'battles': [],
              'input_transport': 'system_mouse' if options.system_input else 'postmessage'}
    try:
        if options.offscreen and not options.system_input:
            result['background_window'] = json.loads(command('powershell', '-ExecutionPolicy', 'Bypass', '-File', str(GAME_UI),
                                                             'background', '-GameProcessId', str(process_id),
                                                             '-ReturnFocusWindow', str(previous_foreground)))
        if options.late_install:
            # Refuse a conflicting final hook before touching any earlier hook,
            # then restore our owned sandbox and retry in the same process.
            specification = importlib.util.spec_from_file_location('preview_install_probe', PROBE)
            probe = importlib.util.module_from_spec(specification)
            specification.loader.exec_module(probe)
            kernel = probe.api()
            process = probe.checked(kernel.OpenProcess(0x1038, False, process_id))
            entries = ((0x433440, 5), (0x577e70, 6), (0x579370, 9), (0x541fa0, 5),
                       (0x577010, 6), (0x5767a0, 6), (0x546f40, 6), (0xa4eb10, 6), (0x578986, 6))
            originals = {entry: probe.read(kernel, process, entry, size) for entry, size in entries}
            old, ignored = wintypes.DWORD(), wintypes.DWORD()
            changed = False
            try:
                probe.checked(kernel.VirtualProtectEx(process, 0x578986, 6, 0x40, ctypes.byref(old)))
                changed = True
                probe.write(kernel, process, 0x578986, b'\x90' + originals[0x578986][1:])
                probe.checked(kernel.FlushInstructionCache(process, None, 0))
                refused = command(str(LOADER), '--pid', str(process_id), '--dll', str(PLUGIN), allowed=(1,))
                if 'Plugin refused to install' not in refused:
                    raise RuntimeError('Expected incompatible-hook refusal: ' + refused)
                for entry, size in entries[:-1]:
                    if probe.read(kernel, process, entry, size) != originals[entry]:
                        raise RuntimeError(f'Failed install modified an earlier hook: {entry:x}')
                result['conflicting_hook_refused_without_partial_install'] = True
            finally:
                if changed:
                    probe.write(kernel, process, 0x578986, originals[0x578986])
                    probe.checked(kernel.FlushInstructionCache(process, None, 0))
                    probe.checked(kernel.VirtualProtectEx(process, 0x578986, 6, old.value, ctypes.byref(ignored)))
                kernel.CloseHandle(process)
            command(str(LOADER), '--pid', str(process_id), '--dll', str(PLUGIN))
        control('interact', 'Brem', 'pack_8')
        first = wait_for_models(process_id, 3)
        result['card_check'] = first
        viewport = capture(process_id, 'deployment')
        width, height = viewport['Width'], viewport['Height']
        first['viewport'] = [width, height]
        # Obstacles vary between arenas. Locate the public genie projection;
        # never change an expected grid cell just to match one screenshot.
        reference_points = [(1000, 430)] + [(x, y) for y in (430, 375) for x in range(525, 1301, 75)]
        candidates = [(round(x * width / 1744), round(y * height / 1358)) for x, y in reference_points]
        # Camera rotation can put defenders elsewhere on screen. Check the
        # battlefield area too, without clicking controls or changing camera.
        candidates += [(round(x * width / 20), round(y * height / 20))
                       for y in range(4, 17) for x in range(4, 19)]
        screen_x, screen_y, hovered = find_projection(process_id, 65, candidates, mouse_options)
        first['hover_point'] = [screen_x, screen_y]
        genie = next(footprint for footprint in first['footprints'] if footprint['size'] == 2)
        if not all(anchor - 1 <= coordinate <= anchor for anchor, coordinate in zip(genie['cell'], hovered['cell'])):
            raise RuntimeError('Genie hover is outside its reserved square: ' + json.dumps(hovered))
        before_click = capture(process_id, 'before-rmb')
        before_click_text = ' '.join(line['Text'] for line in before_click['Lines']).lower()
        first['text_before_right_click'] = before_click_text
        first['input_transport'] = result['input_transport']
        first['clicks'] = []
        # This public base type has two possible upgrades. RMB must cycle full
        # reference cards, never the old compact/detailed toggle.
        for label, hold in (('short-rmb-1', 100), ('short-rmb-2', 100), ('held-rmb', 700)):
            current = diagnostics(process_id)
            if current['models'] != 3 or current['hovered'] != 65:
                raise RuntimeError('Deployment/hover changed before RMB: ' + json.dumps(current))
            command('powershell', '-ExecutionPolicy', 'Bypass', '-File', str(GAME_UI), 'right-click', *mouse_options,
                    '-GameProcessId', str(process_id), '-X', str(screen_x), '-Y', str(screen_y),
                    '-HoldMilliseconds', str(hold))
            time.sleep(0.25)
            card = capture(process_id, label)
            visible_text = ' '.join(line['Text'] for line in card['Lines']).lower()
            current = diagnostics(process_id)
            details = (sum(word in visible_text for word in ('мана', 'выстрелы', 'умения', 'защита', 'инициатива',
                                                             'нападение', 'урон', 'скорость', 'боевой дух', 'удача', 'дальность')) >= 3
                       and 'существо' in visible_text)
            first['clicks'].append({'label': label, 'hold_ms': hold, 'text': visible_text,
                                    'detailed': details, 'image': card['Image'], 'diagnostics': current})
            # Two independent core fields also exist in the compact card.
            # The partial stem tolerates the stock font's Н/К OCR confusion.
            if (current['models'] != 3 or current['hovered'] != 65
                    or not (details or sum(word in visible_text for word in ('падение', 'защита', 'урон', 'жизни')) >= 2)):
                raise RuntimeError('Creature card/hover missing after RMB: ' + visible_text)
        if not all(step['detailed'] for step in first['clicks']):
            raise RuntimeError('An uncertain-grade projection displayed a compact card')
        if len({step['text'] for step in first['clicks']}) != 3:
            raise RuntimeError('Three RMB actions did not produce three distinct public-grade cards')
        first['card_visible_after_right_click'] = True
        first['text_after_right_click'] = first['clicks'][0]['text']
        first['right_click_changed_ocr_text'] = first['clicks'][0]['text'] != before_click_text
        command('powershell', '-ExecutionPolicy', 'Bypass', '-File', str(GAME_UI), 'move', *mouse_options, '-GameProcessId', str(process_id),
                '-X', str(round(width * 0.08)), '-Y', str(round(height * 0.55)))
        time.sleep(0.25)
        if diagnostics(process_id)['hovered'] != 0:
            raise RuntimeError('The card dismissal control point still hovers a projection')
        cleared = capture(process_id, 'cursor-away')
        clear_text = ' '.join(line['Text'] for line in cleared['Lines']).lower()
        if any(word in clear_text for word in ('мана', 'выстрелы', 'умения', 'защита', 'падение')):
            raise RuntimeError('Creature card survived moving onto empty ground: ' + clear_text)
        # A normal modal must retain input priority above the projection.
        control('event', 'input_combat_options')
        command('powershell', '-ExecutionPolicy', 'Bypass', '-File', str(GAME_UI), 'right-click', *mouse_options,
                '-GameProcessId', str(process_id), '-X', str(screen_x), '-Y', str(screen_y))
        modal = capture(process_id, 'modal-block')
        modal_text = ' '.join(line['Text'] for line in modal['Lines']).lower()
        first['modal_image'] = modal['Image']
        if 'загрузить' not in modal_text or any(word in modal_text for word in ('защита', 'падение', 'умения')):
            raise RuntimeError('Combat menu missing or projection card appeared through it: ' + modal_text)
        control('event', 'close_menu')
        # Change type, keeping the resulting card open while confirming placement.
        golem_x, golem_y, golem = find_projection(process_id, 61, candidates, mouse_options)
        command('powershell', '-ExecutionPolicy', 'Bypass', '-File', str(GAME_UI), 'right-click', *mouse_options,
                '-GameProcessId', str(process_id), '-X', str(golem_x), '-Y', str(golem_y))
        golem_card = capture(process_id, 'golem-card')
        golem_text = ' '.join(line['Text'] for line in golem_card['Lines']).lower()
        first['type_switch'] = {'hover': golem, 'image': golem_card['Image'], 'text': golem_text}
        if 'голем' not in golem_text or sum(word in golem_text for word in ('защита', 'падение', 'урон')) < 2:
            raise RuntimeError('Type change did not display the golem card: ' + golem_text)
        first['card_open_before_start'] = True
        result['battles'].append({'pack': 'pack_8', 'projection': first, 'hover': hovered,
                                  'result': complete_battle(process_id, first, observe=not options.late_install)})
        for pack, count in (('pack_12', 4), ('pack_15', 7), ('pack_0', 1), ('pack_1', 1)):
            control('interact', 'Brem', pack)
            projection = wait_for_models(process_id, count)
            if projection['generation'] <= result['battles'][-1]['projection']['generation']:
                raise RuntimeError('A new battle reused a prior placement generation')
            result['battles'].append({'pack': pack, 'projection': projection,
                                      'result': complete_battle(process_id, projection, observe=not options.late_install)})
    except Exception as error:
        result['error'] = str(error)
        raise
    finally:
        try:
            result['close'] = control('quit')
        except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
            result['control_close_error'] = str(error)
            try:
                result['close'] = json.loads(command('powershell', '-ExecutionPolicy', 'Bypass', '-File', str(GAME_UI),
                                                    'close', '-GameProcessId', str(process_id)))
            except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as close_error:
                result['close_error'] = str(close_error)
        (ROOT / '.local/test-state/native-preview-check.json').write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    if 'close_error' in result:
        raise RuntimeError(json.dumps(result, ensure_ascii=False))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
