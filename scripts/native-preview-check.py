"""End-to-end WorkshopPolygon check for the compiled deployment-preview DLL."""
import json
import hashlib
import os
import argparse
from collections import Counter
import ctypes
from ctypes import wintypes
import importlib.util
from pathlib import Path
import re
import subprocess
import sys
import struct
import time
import uuid


MOD_ROOT = Path(__file__).resolve().parents[1]
DEVKIT = Path(os.environ.get('H5_PREVIEW_DEVKIT') or MOD_ROOT / 'devkit').expanduser().resolve()
if ((MOD_ROOT.parents[1] / 'scripts/sync-subrepos.ps1').is_file()
        and DEVKIT != (MOD_ROOT.parents[1] / 'devkit').resolve()):
    raise RuntimeError('Workshop requires the single canonical devkit; run scripts/sync-subrepos.ps1')
if not (DEVKIT / 'scripts/native-probe.py').is_file():
    raise RuntimeError('Initialize pinned dependencies: git submodule update --init. Then follow README.md to link the shared Game API checkout.')
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
_control_module = None


class ManagedPlayerSession:
    """Borrow one guarded player process; closing this client leaves it running."""

    class MemoryRegion(ctypes.Structure):
        _fields_ = [('base', ctypes.c_void_p), ('allocation', ctypes.c_void_p),
                    ('allocation_protection', wintypes.DWORD), ('size', ctypes.c_size_t),
                    ('state', wintypes.DWORD), ('protection', wintypes.DWORD), ('type', wintypes.DWORD)]

    def __init__(self, record, directory, probe):
        self.probe, self.kernel = probe, probe.api()
        self.handle = self.client = None
        self.query_regions = []
        self.owner = record['owner']
        if set(self.owner) != {'pid', 'created'} or any(type(value) is not int or value <= 0 for value in self.owner.values()):
            raise ValueError('Managed session requires PID and creation identity')
        self.game = ROOT / '.local/test-game/bin/H5_Game.exe'
        self.plugin = self.game.parent / 'Heroes5Mods/Plugins/deployment-preview.dll'
        if hashlib.sha256(self.game.read_bytes()).hexdigest() != probe.HASHES['H5_Game.exe']:
            raise RuntimeError('Managed diagnostics require the pinned game executable')
        controller = Path(record['controller']).resolve()
        if hashlib.sha256(controller.read_bytes()).hexdigest() != record['controller_sha256']:
            raise RuntimeError('Managed controller changed')
        if hashlib.sha256(self.plugin.read_bytes()).hexdigest() != record['installed_plugin_sha256']:
            raise RuntimeError('Managed installed player DLL changed')
        try:
            self.handle = probe.checked(self.kernel.OpenProcess(0x410, False, self.owner['pid']))
            self.check_owner()
            filename = ctypes.create_unicode_buffer(32768)
            length = wintypes.DWORD(len(filename))
            probe.checked(self.kernel.QueryFullProcessImageNameW(self.handle, 0, filename, ctypes.byref(length)))
            if Path(filename.value).resolve() != self.game.resolve():
                raise RuntimeError('Managed session points outside its owned test game')
            self.user = ctypes.WinDLL('user32', use_last_error=True)
            self.user.GetPropW.argtypes = [wintypes.HWND, wintypes.LPCWSTR]
            self.user.GetPropW.restype = ctypes.c_void_p
            candidates, errors = [], []

            @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
            def collect(window, unused):
                process_id = wintypes.DWORD()
                self.user.GetWindowThreadProcessId(window, ctypes.byref(process_id))
                if process_id.value != self.owner['pid']:
                    return True
                registry = self.user.GetPropW(window, 'Heroes5SDK.ResidentBuffers.v1')
                if not registry:
                    return True
                try:
                    header = struct.unpack('<6I', self.read(registry, 24))
                    if header[:5] != (0x42523548, 2, 472, self.owner['pid'], int(window)):
                        raise RuntimeError('Managed resident registry identity changed')
                    for index in range(16):
                        key, schema, size, address = struct.unpack('<4I', self.read(registry + 24 + index * 28, 16))
                        if key and schema == 6 and size == 1048576 and address:
                            candidates.append((int(window), address))
                except (OSError, RuntimeError, ValueError) as error:
                    errors.append(str(error))
                return True

            if not self.user.EnumWindows(collect, 0) or errors or len(set(candidates)) != 1:
                raise RuntimeError('Managed predictor resident data is missing, ambiguous or invalid: ' + repr(errors))
            self.window, self.resident = candidates[0]
            self.public_address = self.resident + 352 * 1024
            self.comparison_address = self.resident + 336 * 1024
            sys.path.insert(0, str(DEVKIT / 'scripts'))
            from plugin_core import CoreClient
            self.client = CoreClient([str(controller), '--owned-command', str(self.owner['pid']),
                str(self.owner['created']), str(self.game.resolve()), str(self.plugin.resolve())], Path(directory))
        except Exception:
            self.close()
            raise

    def check_owner(self):
        if self.probe.creation_time(self.kernel, self.handle) != self.owner['created']:
            raise RuntimeError('Managed process creation identity changed')

    def read(self, address, length):
        self.check_owner()
        return self.probe.read(self.kernel, self.handle, address, length)

    def command(self, text, timeout=None):
        self.check_owner()
        response = self.client.request(text) if timeout is None else self.client.request(text, timeout=timeout)
        if response['status'] != 0:
            raise RuntimeError('Managed command refused: ' + repr(response))
        return response

    def screens(self):
        word = lambda address: struct.unpack('<I', self.read(address, 4))[0]
        head = word(0xfe719c)
        node, result = word(head), []
        while node != head and len(result) < 16:
            screen = word(node + 8)
            descriptor = word(word(word(screen) - 4) + 12)
            result.append(self.read(descriptor + 8, 100).split(b'\0')[0].decode('ascii'))
            node = word(node)
        if node != head:
            raise RuntimeError('Managed screen list is not a complete bounded chain')
        return result

    def wait_screen(self, fragment, timeout):
        deadline = time.perf_counter() + timeout
        while True:
            current = self.screens()
            if current and fragment in current[-1]:
                return current
            if time.perf_counter() >= deadline:
                raise TimeoutError('Managed native phase pending; submitted action is not replayed')
            time.sleep(0.01)

    def query(self, preparation, fields, timeout=5):
        """Read fresh stock-Lua scalars; cache only regions containing this nonce."""
        if not fields or not 0 < timeout <= 10:
            raise ValueError('Managed scalar query requires fields and a bounded timeout')
        deadline = time.perf_counter() + timeout
        nonce = 'XKIT_PLAYER_' + uuid.uuid4().hex + ':'
        expression = "..':'..".join('(' + field + ')' for field in fields)
        self.command('game-script ' + preparation + "SetGameVar('XKIT_PLAYER_Q','" + nonce + "'.." + expression + "..':END')",
                     timeout=deadline - time.perf_counter())
        baseline = struct.unpack('<I', self.read(self.resident, 4))[0]
        while struct.unpack('<I', self.read(self.resident, 4))[0] < baseline + 3:
            if time.perf_counter() >= deadline:
                raise TimeoutError('Managed query frame pending; Lua is not replayed')
            time.sleep(0.001)
        self.kernel.VirtualQueryEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p,
            ctypes.POINTER(self.MemoryRegion), ctypes.c_size_t]
        self.kernel.VirtualQueryEx.restype = ctypes.c_size_t
        scalar = rb'[A-Za-z0-9_., \-]*'
        pattern = re.compile(re.escape(nonce.encode()) + b'(' + scalar + (b':' + scalar) * (len(fields) - 1) + rb'):END')
        scanned, results, matched_regions = 0, set(), []

        def scan_region(start, size):
            nonlocal scanned
            tail = b''
            for offset in range(start, start + size, 1048576):
                if time.perf_counter() >= deadline:
                    raise TimeoutError('Managed scalar read exceeded its deadline; query is not replayed')
                try:
                    content = self.probe.read(self.kernel, self.handle, offset, min(1048576, start + size - offset))
                except OSError:
                    tail = b''
                    continue
                if time.perf_counter() >= deadline:
                    raise TimeoutError('Managed scalar read returned after its deadline')
                scanned += len(content)
                combined = tail + content
                for match in pattern.finditer(combined):
                    results.add(tuple(match.group(1).decode('ascii').split(':')))
                    if (start, size) not in matched_regions:
                        matched_regions.append((start, size))
                tail = combined[-8192:]

        for start, size in self.query_regions:
            region = self.MemoryRegion()
            if (self.kernel.VirtualQueryEx(self.handle, start, ctypes.byref(region), ctypes.sizeof(region)) and
                    region.base == start and region.state == 0x1000 and region.type == 0x20000 and
                    not region.protection & 0x101 and region.protection & 255 in (4, 8, 0x40, 0x80)):
                scan_region(start, min(size, region.size))
        if not results:
            address = 0
            while address < 0x100000000:
                if time.perf_counter() >= deadline:
                    raise TimeoutError('Managed region enumeration exceeded its deadline')
                region = self.MemoryRegion()
                if not self.kernel.VirtualQueryEx(self.handle, address, ctypes.byref(region), ctypes.sizeof(region)):
                    break
                start, size = region.base or 0, region.size
                if not size or start + size <= address:
                    raise RuntimeError('Managed memory-region enumeration did not advance')
                address = start + size
                if (region.state == 0x1000 and region.type == 0x20000 and not region.protection & 0x101 and
                        region.protection & 255 in (4, 8, 0x40, 0x80)):
                    scan_region(start, min(size, 0x100000000 - start))
        self.check_owner()
        if time.perf_counter() >= deadline:
            raise TimeoutError('Managed scalar result arrived after its deadline')
        if len(results) != 1:
            raise RuntimeError('Fresh managed scalar result is missing or ambiguous: ' +
                repr({'matches': sorted(results), 'bytes_scanned': scanned}))
        self.query_regions = matched_regions
        return {'values': list(results.pop()), 'bytes_scanned': scanned, 'cached_regions': len(matched_regions)}

    def close(self):
        try:
            if self.client:
                self.client.close()
        finally:
            self.client = None
            if self.handle:
                self.kernel.CloseHandle(self.handle)
                self.handle = None


def command(*arguments, allowed=(0,)):
    completed = subprocess.run(arguments, cwd=ROOT, text=True, encoding='utf-8', capture_output=True)
    if completed.returncode not in allowed:
        raise RuntimeError((completed.stdout + completed.stderr).strip())
    return completed.stdout + completed.stderr


def control(*arguments):
    global _control_module
    if _control_module is None:
        if str(CONTROL.parent) not in sys.path:
            sys.path.insert(0, str(CONTROL.parent))
        specification = importlib.util.spec_from_file_location('native_preview_control', CONTROL)
        module = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(module)
        _control_module = module
    try:
        return _control_module.main(list(arguments))
    except RuntimeError:
        raise
    except Exception as error:
        raise RuntimeError(str(error)) from error


def diagnostics(process_id):
    # This loader EXE can install an absent DLL. A normal-start acceptance
    # probe must wait for the bootstrap's renderer hook, never install it.
    if str(PROBE.parent) not in sys.path:
        sys.path.insert(0, str(PROBE.parent))
    specification = importlib.util.spec_from_file_location('preview_readonly_probe', PROBE)
    native_probe = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(native_probe)
    kernel = native_probe.api()
    process = native_probe.checked(kernel.OpenProcess(0x1010, False, process_id))
    try:
        renderer = native_probe.read(kernel, process, 0x577010, 6)
    finally:
        kernel.CloseHandle(process)
    if renderer == bytes.fromhex('55 8b ec 83 e4 f8'):
        return {'public': 0, 'models': 0, 'hovered': 0, 'cell': [31, 31],
                'alignment': 8, 'loader_status': 'not_yet_auto_loaded'}
    trace = json.loads(command(str(LOADER), '--pid', str(process_id), '--dll', str(PLUGIN),
                               '--projection-trace'))
    if trace['models'] == 0:
        return {'public': trace['public'], 'models': 0, 'hovered': 0, 'cell': [31, 31],
                'alignment': 8, 'loader_status': 'loaded_without_projection'}
    output = command(str(LOADER), '--pid', str(process_id), '--dll', str(PLUGIN), allowed=(1,))
    match = DIAGNOSTIC.search(output)
    if match is None:
        raise RuntimeError('Expected native preview diagnostics: ' + output.strip())
    public, models, hovered, x, y, alignment = (int(value) for value in match.groups())
    return {'public': public, 'models': models, 'hovered': hovered, 'cell': [x, y], 'alignment': alignment}


def wait_for_models(process_id, public_count, allow_partial=False):
    requested_public = public_count
    deadline = time.monotonic() + 10
    latest = None
    while time.monotonic() < deadline:
        try:
            latest = diagnostics(process_id)
        except RuntimeError as error:
            if not str(error).startswith('Projection snapshot is busy; retry capture'):
                raise
            time.sleep(0.05)
            continue
        if allow_partial and requested_public == 1 and latest['public'] != requested_public:
            inputs = json.loads(command(str(LOADER), '--pid', str(process_id), '--dll', str(PLUGIN), '--admin-input-trace'))
            composition = inputs.get('source_composition_words', [])
            if (inputs.get('enabled') and inputs.get('frozen') and len(composition) == 24
                    and composition[0] == 1 and 1 <= composition[12] <= 4
                    and composition[12] == latest['public']):
                public_count = composition[12]
        if latest['public'] == public_count and (latest['models'] == public_count
                or (allow_partial and 0 < latest['models'] < public_count)):
            trace = json.loads(command(str(LOADER), '--pid', str(process_id), '--dll', str(PLUGIN), '--projection-trace'))
            if (trace['abi'] != 8 or trace['public'] != public_count or trace['models'] != latest['models']
                    or not isinstance(trace.get('planned_models'), int) or not 1 <= trace['planned_models'] <= public_count
                    or not isinstance(trace.get('excluded_source_mask'), int)
                    or trace['excluded_source_mask'] < 0 or trace['excluded_source_mask'] >> public_count
                    or trace['planned_models'] != public_count - trace['excluded_source_mask'].bit_count()
                    or len(trace['slots']) != latest['models'] or len(trace.get('public_bands', [])) != public_count
                    or any(band < 0 or band > 9 for band in trace['public_bands'])
                    or not isinstance(trace.get('predicted_spread'), bool)
                    or not isinstance(trace.get('predicted_defensive'), bool)
                    or not isinstance(trace.get('estimated_spread_denominator'), int)
                    or trace['estimated_spread_denominator'] < 0
                    or not isinstance(trace.get('known_hero_attack'), int)
                    or not 0 <= trace['known_hero_attack'] <= 1000
                    or not isinstance(trace.get('known_hero_battle_frenzy'), bool)):
                raise RuntimeError('Incomplete projection snapshot: ' + json.dumps(trace))
            if trace['models'] != trace['planned_models'] and time.monotonic() < deadline - 0.5:
                time.sleep(0.5)
                continue
            occupied = set()
            width, height = trace['grid']
            for slot in trace['slots']:
                x, y = slot['cell']
                size = slot['size']
                if not isinstance(slot.get('quantity'), int) or not 0 <= slot['quantity'] <= 100000000:
                    raise RuntimeError('Invalid predicted quantity: ' + json.dumps(trace))
                if size not in (1, 2) or not (size <= x < width - 1 and size <= y < height - 1):
                    raise RuntimeError('Invalid or out-of-bounds footprint: ' + json.dumps(trace))
                cells = {(column, row) for column in range(x - size + 1, x + 1)
                         for row in range(y - size + 1, y + 1)}
                if occupied & cells:
                    raise RuntimeError('Projection cells overlap: ' + str(sorted(occupied & cells)))
                occupied.update(cells)
            latest['footprints'] = trace['slots']
            latest['public_bands'] = trace['public_bands']
            latest['predicted_spread'] = trace['predicted_spread']
            latest['predicted_defensive'] = trace['predicted_defensive']
            latest['estimated_spread_denominator'] = trace['estimated_spread_denominator']
            latest['known_hero_attack'] = trace['known_hero_attack']
            latest['known_hero_battle_frenzy'] = trace['known_hero_battle_frenzy']
            latest['generation'] = trace['generation']
            latest['prediction_complete'] = latest['models'] == trace['planned_models']
            latest['planned_models'] = trace['planned_models']
            latest['excluded_source_mask'] = trace['excluded_source_mask']
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


def wait_for_control_queues(timeout=15):
    deadline = time.monotonic() + timeout
    latest = None
    while time.monotonic() < deadline:
        latest = control('runtime-state')
        if (latest.get('stable') and latest.get('event_commands_pending') is False
                and latest['script_contexts']['adventure']['script_commands_pending'] is False):
            return latest
        time.sleep(0.2)
    raise RuntimeError('Native control queues did not drain: ' + json.dumps(latest))


def complete_battle(process_id, projection, observe=True, hero='Brem', creature_ids=None, on_observation=None):
    armed = control('deployment-observation', '--arm') if observe else None
    control('confirm')
    time.sleep(0.6)
    released = diagnostics(process_id)
    if released['models'] != 0 or released['hovered'] != 0:
        raise RuntimeError('Projection survived deployment confirmation: ' + json.dumps(released))
    if projection.get('card_open_before_start'):
        released['card_cleanup'] = {'status': 'not_verified', 'reason': 'Requires native UI lifetime diagnostics; image text is not an oracle'}
    observed = control('deployment-observation') if observe else None
    if observe and (observed['sequence'] != armed['sequence'] or not observed['units']):
        raise RuntimeError('No complete after-start observation for this battle: ' + json.dumps(observed))
    if observe and creature_ids is not None:
        for unit in observed['units']:
            if unit['creature'] not in creature_ids:
                raise RuntimeError('Observed creature absent from pinned enum: ' + unit['creature'])
            unit['type'] = creature_ids[unit['creature']]
    if observe and on_observation is not None:
        try:
            observed['runtime_state_after_start'] = control('runtime-state')
        except RuntimeError as error:
            observed['runtime_state_capture_error'] = str(error)
        on_observation(observed)
    control('finish', '--winner', '0')
    time.sleep(0.25)
    control('results')
    returned = wait_for_control_queues()
    result = {'release': released, 'return_runtime_state': returned, 'hero': control('hero', hero)}
    result['levelup_choices'] = []
    if projection.get('hero_level_before_start') is not None:
        for _ in range(40):
            dialog = control('levelup-state')
            if dialog.get('available') is not True or dialog.get('stable') is not True:
                raise RuntimeError('Native level-up observer is unavailable or unstable: ' + json.dumps(dialog))
            result['levelup_state_after_results'] = dialog
            if not dialog['open']:
                break
            previous_level = result['hero']['level']
            control('event', 'skill_1')
            control('event', 'MB_Button_Ok')
            result['return_runtime_state'] = wait_for_control_queues()
            result['hero'] = control('hero', hero)
            result['levelup_choices'].append({'from_level': previous_level, 'to_level': result['hero']['level'],
                                              'choice': 1, 'dialog_native_state': dialog})
        else:
            raise RuntimeError('Level-up dialogs did not settle within40 choices')
    if observe:
        # Resolve public Lua constants only after returning to adventure mode.
        # Actual combat units never feed back into DLL prediction.
        if creature_ids is None:
            expression = "''.." + "..','..".join(unit['creature'] for unit in observed['units'])
            types = [int(value) for value in control('eval', expression)['result'].split(',')]
        else:
            types = [unit['type'] for unit in observed['units']]
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
    startup = parser.add_mutually_exclusive_group()
    startup.add_argument('--late-install', dest='startup_mode', action='store_const', const='late',
                         help='Check diagnostic attach in a sandbox without DLL autoloading.')
    startup.add_argument('--auto-load', dest='startup_mode', action='store_const', const='auto',
                         help='Default: normal game startup with DLL mods installed in sandbox bin.')
    startup.add_argument('--legacy-loader', dest='startup_mode', action='store_const', const='legacy',
                         help='Developer-only historical EXE startup, without DLL autoloading.')
    parser.set_defaults(startup_mode='auto')
    parser.add_argument('--system-input', action='store_true',
                        help='Legacy compatibility option; this runner uses process diagnostics and sends no mouse input.')
    parser.add_argument('--offscreen', action='store_true',
                        help='Explicit isolated automation only; never use for a visible user demo.')
    options = parser.parse_args()
    options.auto_load = options.startup_mode == 'auto'
    options.late_install = options.startup_mode == 'late'
    if options.late_install:
        LOADER = BUILD / 'workshop_preview_loader.exe'
        PLUGIN = BUILD / 'WorkshopDeploymentPreview.dll'
    if options.auto_load:
        LOADER = BUILD / 'workshop_preview_loader.exe'
        PLUGIN = ROOT / '.local/test-game/bin/Heroes5Mods/WorkshopDeploymentPreview.dll'
        if not (ROOT / '.local/test-game/bin/dinput8.dll').is_file():
            raise RuntimeError('Install the DLL bootstrap in the sandbox before --auto-load.')
    elif (ROOT / '.local/test-game/bin/dinput8.dll').exists():
        raise RuntimeError('Legacy diagnostic modes require a sandbox without DLL autoloading.')
    if not LOADER.is_file() or not PLUGIN.is_file():
        raise RuntimeError('Build the native plugin before running this check')
    user_interface = ctypes.WinDLL('user32', use_last_error=True)
    user_interface.GetForegroundWindow.restype = wintypes.HWND
    previous_foreground = user_interface.GetForegroundWindow() or 0
    launch = json.loads(command(PYTHON, '-X', 'utf8', str(PROBE), 'launch', '--map', 'WorkshopPolygon', '--control',
                                *(['--observe-deployment'] if options.auto_load else
                                  [] if options.late_install else ['--native-loader'])))
    process_id = launch['pid']
    result = {'pid': process_id, 'native_loader': launch['native_loader'], 'auto_load': options.auto_load, 'battles': [],
              'input_transport': 'process_diagnostics'}
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
        result['placement_check'] = first
        result['ui_checks'] = {'status': 'not_run',
                               'reason': 'This legacy runner checks placement data; use the native UI controls diagnostics for cards and grades'}
        result['battles'].append({'pack': 'pack_8', 'projection': first,
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
