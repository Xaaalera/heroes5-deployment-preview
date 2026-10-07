"""Ten fresh-map cycles through every authored neutral pack; development only."""
import argparse
from collections import Counter
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import struct
import sys
import shutil
import time
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED
import xml.etree.ElementTree as ET

MOD = Path(__file__).resolve().parents[1]
os.environ.setdefault('H5_WORKSPACE', str(MOD.parents[1]))
os.environ.setdefault('H5_PREVIEW_BUILD', str(MOD / '.local/player-build/Release'))
spec = importlib.util.spec_from_file_location('native_preview_check', Path(__file__).with_name('native-preview-check.py'))
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)
sys.path.insert(0, str(check.PROBE.parent))
probe_spec = importlib.util.spec_from_file_location('native_probe', check.PROBE)
probe = importlib.util.module_from_spec(probe_spec)
probe_spec.loader.exec_module(probe)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def allocate_low_probe(kernel, process, size):
    # Absolute x86 addresses in Keystone's diagnostic trampolines must stay
    # below the 2 GiB boundary; the game itself is still a 32-bit process.
    for hint in (0x20000000, 0x30000000, 0x40000000, 0x50000000, None):
        address = kernel.VirtualAllocEx(process, hint, size, 0x3000, 0x04)
        if not address:
            continue
        if address + size < 0x80000000:
            return address
        kernel.VirtualFreeEx(process, address, 0, 0x8000)
    raise RuntimeError('Cannot allocate a low x86 diagnostic code buffer')


_completed_battle_json = {}


def save(report, target, completed_battle=None):
    temporary = target.with_suffix('.tmp')
    target_key = str(target.resolve())
    if completed_battle is not None:
        # The caller marks the battle only after its final comparison and all
        # raw observations are written. That record is immutable thereafter.
        _completed_battle_json[(target_key, id(completed_battle))] = (
            completed_battle, json.dumps(completed_battle, ensure_ascii=False, separators=(',', ':')))
    with temporary.open('w', encoding='utf-8') as output:
        if 'runs' not in report:
            output.write(json.dumps(report, ensure_ascii=False, separators=(',', ':')))
        else:
            header = {key: value for key, value in report.items() if key != 'runs'}
            output.write(json.dumps(header, ensure_ascii=False, separators=(',', ':'))[:-1])
            output.write(',' if header else '')
            output.write('"runs":[')
            for run_index, run in enumerate(report['runs']):
                if run_index:
                    output.write(',')
                if 'battles' not in run:
                    output.write(json.dumps(run, ensure_ascii=False, separators=(',', ':')))
                    continue
                run_header = {key: value for key, value in run.items() if key != 'battles'}
                output.write(json.dumps(run_header, ensure_ascii=False, separators=(',', ':'))[:-1])
                output.write(',' if run_header else '')
                output.write('"battles":[')
                for battle_index, battle in enumerate(run['battles']):
                    if battle_index:
                        output.write(',')
                    cached = _completed_battle_json.get((target_key, id(battle)))
                    output.write(cached[1] if cached is not None and cached[0] is battle
                                 else json.dumps(battle, ensure_ascii=False, separators=(',', ':')))
                output.write(']}')
            output.write(']}')
        output.write('\n')
    for attempt in range(21):
        try:
            temporary.replace(target)
            return
        except PermissionError as error:
            if getattr(error, 'winerror', None) not in (5, 32, 33) or attempt == 20:
                raise
            time.sleep(0.05)


def stop_hung_owned_sandbox(pid, created, workspace):
    if type(created) is not int or created <= 0:
        raise RuntimeError('Owned game creation identity is required before forced cleanup')
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                                  wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    kernel.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel.TerminateProcess.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    kernel.GetProcessTimes.restype = wintypes.BOOL
    process = kernel.OpenProcess(0x1001, False, pid)
    if not process:
        return {'status': 'already_exited'}
    try:
        times = [wintypes.FILETIME() for _ in range(4)]
        if not kernel.GetProcessTimes(process, *[ctypes.byref(value) for value in times]):
            raise RuntimeError('Cannot verify the hung game creation identity')
        actual_created = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
        if actual_created != created:
            raise RuntimeError('Refusing to stop a reused PID belonging to another game session')
        path = ctypes.create_unicode_buffer(1024)
        length = wintypes.DWORD(len(path))
        if not kernel.QueryFullProcessImageNameW(process, 0, path, ctypes.byref(length)):
            raise RuntimeError('Cannot verify the hung game process path')
        expected = workspace / '.local/test-game/bin/H5_Game.exe'
        if Path(path.value).resolve() != expected.resolve():
            raise RuntimeError('Refusing to stop a process outside the owned test sandbox')
        if not kernel.TerminateProcess(process, 1):
            raise RuntimeError('Failed to stop the hung owned test game')
        return {'status': 'terminated_hung_owned_sandbox'}
    finally:
        kernel.CloseHandle(process)


def prepare_rmg_fixture(root, source_name, label, identifier):
    """Tag generator-made monsters for commands; preserve all their army data."""
    source = root / '.local/test-game/Maps' / source_name
    target = root / '.local/test-game/Maps' / f'WorkshopRmgTagged{label}.h5m'
    with ZipFile(source) as archive:
        entries = {name: archive.read(name) for name in archive.namelist()}
    old_map = next(name for name in entries if name.endswith('/map.xdb'))
    old_identifier = old_map.split('/')[2]
    new_map = old_map.replace(old_identifier, identifier)
    prefix = new_map[:-len('map.xdb')]
    description = ET.fromstring(entries[old_map])
    for hero in description.findall('.//AdvMapHero'):
        allowed = hero.find('AllowQuickCombat')
        if allowed is None:
            allowed = ET.SubElement(hero, 'AllowQuickCombat')
        allowed.text = 'false'
    monsters = [element for element in description.iter() if element.tag == 'AdvMapMonster']
    towns = [(int(element.findtext('Pos/x')), int(element.findtext('Pos/y')))
             for element in description.iter() if element.tag == 'AdvMapTown']
    if not monsters or not towns:
        raise RuntimeError('RMG source lacks expected generated monsters or towns')
    selected = []
    for index, monster in enumerate(monsters):
        if monster.findtext('Name'):
            raise RuntimeError('RMG source monster unexpectedly has a named identity')
        monster.find('Name').text = f'rmg_{label.lower()}_{index:03}'
        monster.find('CombatScript').set('href', '/' + prefix + 'CombatScript.xdb#xpointer(/Script)')
        courage = monster.find('Courage')
        if courage is None:
            raise RuntimeError('RMG monster lacks the courage field required for forced test combat')
        courage.text = 'MONSTER_COURAGE_ALWAYS_FIGHT'
        allowed = monster.find('AllowQuickCombat')
        if allowed is None:
            allowed = ET.SubElement(monster, 'AllowQuickCombat')
        allowed.text = 'false'
    for stack_count in range(1, 5):
        candidates = [(min(abs(int(monster.findtext('Pos/x')) - x) + abs(int(monster.findtext('Pos/y')) - y)
                           for x, y in towns), index, monster)
                      for index, monster in enumerate(monsters)
                      if 1 + len(monster.findall('AdditionalStacks/Item')) == stack_count]
        for _, index, monster in sorted(candidates, key=lambda item: (item[0], item[1]))[:6]:
            selected.append({'name': f'rmg_{label.lower()}_{index:03}', 'public_count': stack_count,
                             'x': int(monster.findtext('Pos/x')), 'y': int(monster.findtext('Pos/y')),
                             'source_index': index, 'shared': monster.find('Shared').get('href')})
    files = {}
    for name, data in entries.items():
        if name == old_map:
            data = ET.tostring(description, encoding='utf-8', xml_declaration=True)
        files[name.replace(old_identifier, identifier)] = data.replace(old_identifier.encode(), identifier.encode())
    files[prefix + 'CombatScript.xdb'] = b'<Script><FileName href="CombatScript.lua"/></Script>'
    files[prefix + 'CombatScript.lua'] = (b'function Start()\n for index, unit in GetDefenderCreatures() do\n'
                                           b'  local count = GetCreatureNumber(unit);\n'
                                           b'  local x, y = GetUnitPosition(unit);\n end;\nend;\n')
    temporary = target.with_suffix('.tmp')
    with ZipFile(temporary, 'w', ZIP_DEFLATED) as archive:
        for name, data in files.items():
            entry = ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            entry.compress_type = ZIP_DEFLATED
            archive.writestr(entry, data)
    temporary.replace(target)
    with ZipFile(target) as archive:
        if archive.testzip() is not None:
            raise RuntimeError('Generated RMG test fixture has a corrupt ZIP member')
    return {'name': target.stem, 'kind': 'tagged_universe_rmg', 'source_name': source.name,
            'source_sha256': sha256(source), 'map_sha256': sha256(target),
            'change': 'Names, forced full combat (no flee/join/quick combat), and after-Start observer; generator armies and amounts unchanged',
            'packs': sorted(selected, key=lambda item: item['source_index'])}


def creature_families(game_data):
    """Resolve a grade to its base using the installed game's own enum and XDBs."""
    with ZipFile(game_data / 'a2p1-data.pak') as archive:
        enum_bytes = archive.read('types.xml')
    enum_root = ET.fromstring(enum_bytes)
    entries = next(item.findall('EnumEntries/Item') for item in enum_root.findall('.//Tables/Item')
                   if item.findtext('dbid/XPointer', '').endswith('/Table_Creature_CreatureType)'))
    names = [item.text for item in entries]
    ids = {name: index for index, name in enumerate(names)}
    definitions = {}
    table_bytes = None
    for archive_name in ('data.pak', 'a2p1-data.pak', 'Universe_mod.pak'):
        with ZipFile(game_data / archive_name) as archive:
            for path in archive.namelist():
                if path == 'GameMechanics/RefTables/Creatures.xdb':
                    table_bytes = archive.read(path)
                elif path.startswith('GameMechanics/Creature/Creatures/') and path.endswith('.xdb'):
                    definitions[path] = archive.read(path)
    if table_bytes is None:
        raise RuntimeError('Installed game lacks the creature reference table')
    table = ET.fromstring(table_bytes)
    base = {}
    for item in table.findall('objects/Item'):
        name = item.findtext('ID')
        object_ref = item.find('Obj')
        if name not in ids or object_ref is None:
            continue
        path = object_ref.get('href', '').split('#')[0].lstrip('/')
        if path not in definitions:
            continue
        root = ET.fromstring(definitions[path])
        parent = root.findtext('BaseCreature')
        if parent in ids and parent != 'CREATURE_UNKNOWN':
            base[name] = parent
    families = {}
    for name, identifier in ids.items():
        current = name
        visited = set()
        while current in base and current not in visited:
            visited.add(current)
            current = base[current]
        families[identifier] = ids.get(current, identifier)
    return families, {'types_xml_sha256': hashlib.sha256(enum_bytes).hexdigest(),
                      'creature_table_sha256': hashlib.sha256(table_bytes).hexdigest()}, names


def install_initial_atb_observer(pid):
    from keystone import Ks, KS_ARCH_X86, KS_MODE_32
    kernel = probe.api()
    process = probe.checked(kernel.OpenProcess(0x1038, False, pid))
    try:
        entry = 0x8c04e0
        original = bytes.fromhex('8b 41 08 83 c1 e4')
        if probe.read(kernel, process, entry, len(original)) != original:
            raise RuntimeError('Unexpected initial-ATB RNG hook site')
        allocation = allocate_low_probe(kernel, process, 8192)
        records = allocation + 4096
        assembly = f'''
            pushfd
            pushad
            cmp dword ptr [{records}], 1
            jne atb_done
            cmp dword ptr [esp + 36], 0xa74107
            jne atb_done
            mov edi, dword ptr [{records + 4}]
            cmp edi, 128
            jae atb_full
            imul edi, edi, 20
            add edi, {records + 16}
            mov eax, dword ptr [esp + 24]
            mov dword ptr [edi], eax
            mov eax, dword ptr [eax + 8]
            mov dword ptr [edi + 4], eax
            mov eax, dword ptr [esp + 36]
            mov dword ptr [edi + 8], eax
            mov eax, dword ptr [esp + 40]
            mov dword ptr [edi + 12], eax
            mov eax, dword ptr [esp + 44]
            mov dword ptr [edi + 16], eax
            inc dword ptr [{records + 4}]
            jmp atb_done
        atb_full:
            mov dword ptr [{records + 8}], 1
        atb_done:
            popad
            popfd
            mov eax, dword ptr [ecx + 8]
            add ecx, -0x1c
            jmp 0x8c04e6
        '''
        code = bytes(Ks(KS_ARCH_X86, KS_MODE_32).asm(assembly, allocation)[0])
        probe.write(kernel, process, allocation, code)
        integer_entry = 0x8c04c0
        integer_original = bytes.fromhex('8b 54 24 08 8b 01')
        if probe.read(kernel, process, integer_entry, 6) != integer_original:
            raise RuntimeError('Unexpected neutral split range-RNG site')
        integer_records = records + 3072
        integer_assembly = f'''
            pushfd
            pushad
            cmp dword ptr [{records}], 1
            jne range_done
            mov eax, dword ptr [esp + 36]
            cmp eax, 0x85545c
            je range_capture
            cmp eax, 0x8554c6
            je range_capture
            cmp eax, 0x8554ef
            jne range_done
        range_capture:
            mov edi, dword ptr [{integer_records + 4}]
            cmp edi, 32
            jae range_full
            imul edi, edi, 20
            add edi, {integer_records + 16}
            mov dword ptr [edi + 8], eax
            mov eax, dword ptr [esp + 24]
            mov dword ptr [edi], eax
            mov eax, dword ptr [eax + 8]
            mov dword ptr [edi + 4], eax
            mov eax, dword ptr [esp + 40]
            mov dword ptr [edi + 12], eax
            mov eax, dword ptr [esp + 44]
            mov dword ptr [edi + 16], eax
            inc dword ptr [{integer_records + 4}]
            jmp range_done
        range_full:
            mov dword ptr [{integer_records + 8}], 1
        range_done:
            popad
            popfd
            mov edx, dword ptr [esp + 8]
            mov eax, dword ptr [ecx]
            jmp 0x8c04c6
        '''
        integer_code = bytes(Ks(KS_ARCH_X86, KS_MODE_32).asm(integer_assembly, allocation + 2048)[0])
        probe.write(kernel, process, allocation + 2048, integer_code)
        old, ignored = wintypes.DWORD(), wintypes.DWORD()
        probe.checked(kernel.VirtualProtectEx(process, allocation, 4096, 0x20, ctypes.byref(old)))
        probe.checked(kernel.VirtualProtectEx(process, entry, len(original), 0x40, ctypes.byref(old)))
        probe.write(kernel, process, entry, b'\xe9' + struct.pack('<i', allocation - entry - 5) + b'\x90')
        probe.checked(kernel.VirtualProtectEx(process, entry, len(original), old.value, ctypes.byref(ignored)))
        probe.checked(kernel.VirtualProtectEx(process, integer_entry, 6, 0x40, ctypes.byref(old)))
        probe.write(kernel, process, integer_entry,
                    b'\xe9' + struct.pack('<i', allocation + 2048 - integer_entry - 5) + b'\x90')
        probe.checked(kernel.VirtualProtectEx(process, integer_entry, 6, old.value, ctypes.byref(ignored)))
        probe.checked(kernel.FlushInstructionCache(process, None, 0))
        return records
    finally:
        kernel.CloseHandle(process)


def initial_atb_records(pid, address, arm=False, integer=False):
    kernel = probe.api()
    process = probe.checked(kernel.OpenProcess(0x1038, False, pid))
    try:
        if arm:
            probe.write(kernel, process, address, bytes(16 + 128 * 20))
            probe.write(kernel, process, address + 3072, bytes(16 + 32 * 20))
            probe.write(kernel, process, address, struct.pack('<I', 1))
            return []
        data = probe.read(kernel, process, address, 16 + 128 * 20)
        if integer:
            data = probe.read(kernel, process, address + 3072, 16 + 32 * 20)
            count, overflow = struct.unpack_from('<2I', data, 4)
            if count > 32 or overflow:
                raise RuntimeError('Neutral split range-RNG observer overflowed')
            return [dict(zip(('rng_interface', 'state_before', 'caller', 'minimum', 'maximum'),
                             struct.unpack_from('<5I', data, 16 + index * 20)))
                    for index in range(count)]
        count, overflow = struct.unpack_from('<2I', data, 4)
        if count > 128 or overflow:
            raise RuntimeError('Initial-ATB observer overflowed')
        result = []
        for index in range(count):
            random, state, caller, minimum, maximum = struct.unpack_from('<5I', data, 16 + index * 20)
            result.append({'rng_interface': random, 'state_before': state, 'caller': caller,
                           'minimum': struct.unpack('<f', struct.pack('<I', minimum))[0],
                           'maximum': struct.unpack('<f', struct.pack('<I', maximum))[0]})
        return result
    finally:
        kernel.CloseHandle(process)


def install_action_factor_observer(pid):
    from keystone import Ks, KS_ARCH_X86, KS_MODE_32
    kernel = probe.api()
    process = probe.checked(kernel.OpenProcess(0x1038, False, pid))
    try:
        entry = 0xbfbafa
        original = bytes.fromhex('8b ce db 44 24 20')
        if probe.read(kernel, process, entry, len(original)) != original:
            raise RuntimeError('Unexpected battle action-factor return site')
        allocation = allocate_low_probe(kernel, process, 65536)
        records = allocation + 4096
        assembly = f'''
            pushfd
            pushad
            cmp dword ptr [{records}], 1
            jne factor_done
            mov edi, dword ptr [{records + 4}]
            cmp edi, 256
            jae factor_full
            imul edi, edi, 160
            add edi, {records + 16}
            mov dword ptr [edi], esi
            mov eax, dword ptr [esp + 76]
            mov dword ptr [edi + 4], eax
            mov dword ptr [edi + 8], ebp
            fnstcw word ptr [edi + 152]
            stmxcsr dword ptr [edi + 156]
            fld st(0)
            fstp dword ptr [edi + 12]
            mov eax, dword ptr [esi]
            mov dword ptr [edi + 20], eax
            cmp eax, 0xe4fba4
            jne factor_recorded
            mov eax, esi
            sub eax, dword ptr [esi - 4]
            mov eax, dword ptr [eax - 0x104]
            mov dword ptr [edi + 24], eax
            test eax, eax
            jz factor_recorded
            mov eax, dword ptr [eax + 0x1c]
            mov dword ptr [edi + 16], eax
            sub esp, 12
            fstp tbyte ptr [esp]
            mov ecx, esi
            mov eax, dword ptr [esi]
            call dword ptr [eax + 8]
            mov dword ptr [edi + 28], eax
            test eax, eax
            jz factor_world_done
            mov edx, dword ptr [eax]
            mov dword ptr [edi + 96], edx
            cmp edx, 0xe79d3c
            jne factor_world_done
            mov edx, dword ptr [eax + 0x8c]
            test edx, edx
            jz factor_world_second
            cmp dword ptr [edx], 0xe17bcc
            jne factor_world_second
            mov ecx, dword ptr [edx + 0x2c]
            sub ecx, dword ptr [edx + 0x28]
            shr ecx, 2
            mov dword ptr [edi + 132], ecx
        factor_world_second:
            mov edx, dword ptr [eax + 0x90]
            test edx, edx
            jz factor_world_done
            cmp dword ptr [edx], 0xe17bcc
            jne factor_world_done
            mov ecx, dword ptr [edx + 0x2c]
            sub ecx, dword ptr [edx + 0x28]
            shr ecx, 2
            mov dword ptr [edi + 136], ecx
        factor_world_done:
            mov ecx, esi
            mov eax, dword ptr [esi]
            call dword ptr [eax + 0xc]
            mov dword ptr [edi + 100], eax
            mov ecx, esi
            mov eax, dword ptr [esi]
            call dword ptr [eax + 0x198]
            mov dword ptr [edi + 112], eax
            mov ecx, esi
            mov eax, dword ptr [esi]
            call dword ptr [eax + 0x19c]
            mov dword ptr [edi + 116], eax
            mov ecx, esi
            mov eax, dword ptr [esi]
            call dword ptr [eax + 0x20]
            push eax
            mov ecx, esi
            mov eax, dword ptr [esi]
            call dword ptr [eax + 0x1dc]
            mov dword ptr [edi + 120], eax
            mov ecx, esi
            mov eax, dword ptr [esi]
            call dword ptr [eax]
            mov dword ptr [edi + 124], eax
            mov ecx, esi
            mov eax, dword ptr [esi]
            call dword ptr [eax + 0x190]
            movzx eax, al
            mov dword ptr [edi + 140], eax
            mov ecx, esi
            mov eax, dword ptr [esi]
            call dword ptr [eax + 0x7c]
            test eax, eax
            jz factor_category_done
            mov ecx, eax
            mov edx, dword ptr [eax]
            call dword ptr [edx]
            cmp dword ptr [eax + 0x1c], 2
            sete al
            movzx eax, al
            mov dword ptr [edi + 144], eax
        factor_category_done:
            mov ecx, esi
            mov eax, dword ptr [esi]
            call dword ptr [eax + 0x1ac]
            mov dword ptr [edi + 32], eax
            mov ecx, esi
            mov eax, dword ptr [esi]
            call dword ptr [eax + 0x1b0]
            mov dword ptr [edi + 36], eax
            mov ecx, esi
            mov eax, dword ptr [esi]
            call dword ptr [eax + 0x1bc]
            fstp dword ptr [edi + 40]
            mov ecx, esi
            mov eax, dword ptr [esi]
            call dword ptr [eax + 0x48]
            mov dword ptr [edi + 44], eax
            mov ecx, esi
            mov eax, dword ptr [esi]
            push 1
            call dword ptr [eax + 0x28c]
            movzx eax, al
            mov dword ptr [edi + 48], eax
            mov ecx, esi
            call 0xbfb3d0
            fstp dword ptr [edi + 52]
            mov ecx, esi
            mov eax, dword ptr [esi]
            call dword ptr [eax + 0x1e0]
            movzx eax, al
            mov dword ptr [edi + 56], eax
            mov ecx, esi
            mov eax, dword ptr [esi]
            push 4
            call dword ptr [eax + 0x28c]
            movzx eax, al
            mov dword ptr [edi + 60], eax
            mov ecx, esi
            mov eax, dword ptr [esi]
            call dword ptr [eax + 0x238]
            mov dword ptr [edi + 64], eax
            mov ecx, esi
            mov eax, dword ptr [esi]
            call dword ptr [eax + 0x234]
            mov dword ptr [edi + 68], eax
            mov ecx, esi
            mov eax, dword ptr [esi]
            call dword ptr [eax + 0x6c]
            mov ebx, eax
            test ebx, ebx
            jz factor_restore
            mov ecx, ebx
            mov eax, dword ptr [ebx]
            call dword ptr [eax]
            mov edx, dword ptr [eax + 0x1c]
            mov dword ptr [edi + 104], edx
            mov edx, dword ptr [eax + 0x20]
            mov dword ptr [edi + 108], edx
            mov ecx, eax
            call 0x4bab70
            mov dword ptr [edi + 72], eax
            mov ecx, ebx
            mov eax, dword ptr [ebx]
            call dword ptr [eax + 0x2c]
            mov dword ptr [edi + 76], eax
            mov ecx, ebx
            mov eax, dword ptr [ebx]
            call dword ptr [eax]
            mov ecx, eax
            call 0x4bab80
            mov dword ptr [edi + 80], eax
            mov ecx, ebx
            mov eax, dword ptr [ebx]
            call dword ptr [eax + 0x34]
            mov dword ptr [edi + 84], eax
            cmp dword ptr [edi + 124], 1
            jne factor_restore
            mov eax, dword ptr [ebx + 4]
            mov edx, dword ptr [eax + 8]
            lea ecx, [edx + ebx + 4]
            mov eax, dword ptr [ecx]
            call dword ptr [eax + 0x58]
            test al, al
            sete al
            movzx eax, al
            mov dword ptr [edi + 128], eax
        factor_restore:
            mov ecx, esi
            mov eax, dword ptr [esi]
            call dword ptr [eax + 0x1e4]
            movzx eax, al
            mov dword ptr [edi + 88], eax
            mov ecx, esi
            mov eax, dword ptr [esi]
            push 0x22
            call dword ptr [eax + 0x28c]
            movzx eax, al
            mov dword ptr [edi + 92], eax
            fld tbyte ptr [esp]
            add esp, 12
        factor_recorded:
            inc dword ptr [{records + 4}]
            jmp factor_done
        factor_full:
            mov dword ptr [{records + 8}], 1
        factor_done:
            popad
            popfd
            mov ecx, esi
            fild dword ptr [esp + 0x20]
            jmp 0xbfbb00
        '''
        code = bytes(Ks(KS_ARCH_X86, KS_MODE_32).asm(assembly, allocation)[0])
        probe.write(kernel, process, allocation, code)
        old, ignored = wintypes.DWORD(), wintypes.DWORD()
        probe.checked(kernel.VirtualProtectEx(process, allocation, 4096, 0x20, ctypes.byref(old)))
        probe.checked(kernel.VirtualProtectEx(process, entry, len(original), 0x40, ctypes.byref(old)))
        probe.write(kernel, process, entry, b'\xe9' + struct.pack('<i', allocation - entry - 5) + b'\x90')
        probe.checked(kernel.VirtualProtectEx(process, entry, len(original), old.value, ctypes.byref(ignored)))
        return records
    finally:
        kernel.CloseHandle(process)


def action_factor_records(pid, address, arm=False, stop=False):
    kernel = probe.api()
    process = probe.checked(kernel.OpenProcess(0x1038, False, pid))
    try:
        if arm:
            probe.write(kernel, process, address, bytes(16 + 256 * 160))
            probe.write(kernel, process, address, struct.pack('<I', 1))
            return []
        if stop:
            # Combat AI can evaluate hundreds of factors after Start. This
            # observer verifies early primitives; freeze it with the prediction.
            probe.write(kernel, process, address, struct.pack('<I', 0))
        data = probe.read(kernel, process, address, 16 + 256 * 160)
        count, overflow = struct.unpack_from('<2I', data, 4)
        if count > 256 or overflow:
            raise RuntimeError('Action-factor observer overflowed')
        result = []
        for index in range(count):
            start = 16 + index * 160
            (actor, selected, damage, factor, atb, table, timer, world,
             morale, luck, initiative, speed, flag_one, action_score, shooter, flag_four,
             actor_max, actor_current, first_max, first_current, second_max, second_current,
             property_one_e_four, flag_twenty_two) = struct.unpack_from('<3I2f3I2ifiIf2I8i', data, start)
            record = {'actor': actor, 'selected_actor': selected, 'damage': damage,
                 'factor': factor, 'atb': atb if timer else None, 'actor_vtable': table,
                 'actor_world': world,
                 'morale': morale, 'luck': luck, 'initiative': initiative, 'speed': speed,
                 'flag_1': flag_one, 'action_score': action_score, 'shooter': shooter, 'flag_4': flag_four,
                 'actor_counter_max': actor_max, 'actor_counter_current': actor_current,
                 'definition_counter_78_max': first_max, 'definition_counter_78_current': first_current,
                 'definition_counter_7c_max': second_max, 'definition_counter_7c_current': second_current,
                 'property_1e4': property_one_e_four, 'flag_22': flag_twenty_two}
            for offset, label in ((96, 'actor_world_vtable'), (100, 'actor_army'),
                                  (104, 'source_type'), (108, 'source_quantity'),
                                  (112, 'attack_getter'), (116, 'defence_getter'),
                                  (120, 'health_getter'), (124, 'actor_kind'),
                                  (128, 'eligible_health'), (132, 'world_army_one_count'),
                                  (136, 'world_army_zero_count'), (140, 'flying'),
                                  (144, 'category_excluded'), (152, 'x87_control_word'), (156, 'mxcsr')):
                record[label] = struct.unpack_from('<I', data, start + offset)[0]
            result.append(record)
        return result
    finally:
        kernel.CloseHandle(process)


def install_policy_observer(pid):
    from keystone import Ks, KS_ARCH_X86, KS_MODE_32
    kernel = probe.api()
    process = probe.checked(kernel.OpenProcess(0x1038, False, pid))
    try:
        entry = 0x8598e0
        original = bytes.fromhex('56 8b f1 80 be d0 00 00 00 00')
        if probe.read(kernel, process, entry, len(original)) != original:
            raise RuntimeError('Unexpected native placement-policy hook site')
        allocation = allocate_low_probe(kernel, process, 12288)
        records = allocation + 4096
        removals = allocation + 8448
        assembly = f'''
            pushfd
            pushad
            mov eax, dword ptr [{records}]
            cmp eax, 8
            jae full
            shl eax, 9
            lea edi, [eax + {records + 16}]
            mov ebx, ecx
            mov eax, dword ptr [ecx]
            stosd
            and eax, 255
            mov dword ptr [{records + 8}], eax
            mov eax, dword ptr [ecx + 0xd0]
            stosd
            mov eax, dword ptr [ecx + 0xdc]
            stosd
            mov eax, dword ptr [ecx + 0x10c]
            stosd
            mov eax, dword ptr [ecx + 0x110]
            stosd
            mov eax, dword ptr [ecx + 0xc]
            stosd
            mov eax, dword ptr [ecx + 0x18]
            stosd
            mov eax, dword ptr [ecx + 0x1c]
            stosd
            mov esi, dword ptr [ebx + 0xf4]
            mov ecx, dword ptr [ebx + 0xf8]
            sub ecx, esi
            shr ecx, 2
            cmp ecx, 32
            ja full
            mov eax, ecx
            stosd
            cld
            rep movs dword ptr es:[edi], dword ptr [esi]
            mov esi, dword ptr [ebx + 0x100]
            mov ecx, dword ptr [ebx + 0x104]
            sub ecx, esi
            shr ecx, 2
            cmp ecx, 32
            ja full
            mov eax, ecx
            stosd
            rep movs dword ptr es:[edi], dword ptr [esi]
            lea esi, [ebx + 0x38]
            mov ecx, 36
            rep movs dword ptr es:[edi], dword ptr [esi]
            inc dword ptr [{records}]
            jmp done
        full:
            mov dword ptr [{records + 4}], 1
        done:
            popad
            popfd
            push esi
            mov esi, ecx
            cmp byte ptr [esi + 0xd0], 0
            jmp {entry + len(original)}
        '''
        code = bytes(Ks(KS_ARCH_X86, KS_MODE_32).asm(assembly, allocation)[0])
        probe.write(kernel, process, allocation, code)
        old, ignored = wintypes.DWORD(), wintypes.DWORD()
        probe.checked(kernel.VirtualProtectEx(process, allocation, 4096, 0x20, ctypes.byref(old)))
        probe.checked(kernel.VirtualProtectEx(process, entry, len(original), 0x40, ctypes.byref(old)))
        probe.write(kernel, process, entry, b'\xe9' + struct.pack('<i', allocation - entry - 5) + b'\x90' * 5)
        probe.checked(kernel.VirtualProtectEx(process, entry, len(original), old.value, ctypes.byref(ignored)))
        removal_entry = 0x859b97
        removal_original = bytes.fromhex('8b 0c 86 c6 41 20 01')
        if probe.read(kernel, process, removal_entry, len(removal_original)) != removal_original:
            raise RuntimeError('Unexpected native weakest-stack removal site')
        removal_assembly = f'''
            mov ecx, dword ptr [esi + eax * 4]
            pushfd
            pushad
            mov edi, dword ptr [{removals}]
            cmp edi, 16
            jae removal_full
            shl edi, 6
            add edi, {removals + 16}
            mov eax, dword ptr [{records + 8}]
            mov dword ptr [edi], eax
            mov eax, dword ptr [{records}]
            dec eax
            mov dword ptr [edi + 4], eax
            mov dword ptr [edi + 8], ecx
            mov edx, dword ptr [ecx]
            test edx, edx
            jz removal_descriptorless
            mov eax, dword ptr [edx + 0x1c]
            mov edx, dword ptr [edx + 0x20]
            jmp removal_attributes
        removal_descriptorless:
            mov eax, dword ptr [ecx + 0x1c]
            mov edx, dword ptr [ecx + 8]
        removal_attributes:
            mov dword ptr [edi + 12], eax
            mov dword ptr [edi + 16], edx
            movzx eax, byte ptr [ecx + 0x10]
            mov dword ptr [edi + 20], eax
            movzx eax, byte ptr [ecx + 0x20]
            mov dword ptr [edi + 24], eax
            mov eax, dword ptr [ecx + 4]
            mov dword ptr [edi + 28], eax
            inc dword ptr [{removals}]
            jmp removal_done
        removal_full:
            mov dword ptr [{removals + 4}], 1
        removal_done:
            popad
            popfd
            mov byte ptr [ecx + 0x20], 1
            jmp 0x859b9e
        '''
        removal_code = bytes(Ks(KS_ARCH_X86, KS_MODE_32).asm(removal_assembly, allocation + 2048)[0])
        if len(code) > 2048 or len(removal_code) > 2048:
            raise RuntimeError('Placement observer exceeds its reserved code regions')
        # The shared page is already RX; temporarily make only the owned page writable.
        probe.checked(kernel.VirtualProtectEx(process, allocation, 4096, 0x40, ctypes.byref(old)))
        probe.write(kernel, process, allocation + 2048, removal_code)
        probe.checked(kernel.VirtualProtectEx(process, allocation, 4096, old.value, ctypes.byref(ignored)))
        probe.checked(kernel.VirtualProtectEx(process, removal_entry, len(removal_original), 0x40, ctypes.byref(old)))
        probe.write(kernel, process, removal_entry, b'\xe9' + struct.pack('<i', allocation + 2048 - removal_entry - 5)
                    + b'\x90' * (len(removal_original) - 5))
        probe.checked(kernel.VirtualProtectEx(process, removal_entry, len(removal_original), old.value, ctypes.byref(ignored)))
        probe.checked(kernel.FlushInstructionCache(process, None, 0))
        return records
    finally:
        kernel.CloseHandle(process)


def policy_records(pid, address, arm=False):
    kernel = probe.api()
    process = probe.checked(kernel.OpenProcess(0x1038, False, pid))
    try:
        if arm:
            probe.write(kernel, process, address, bytes(12))
            probe.write(kernel, process, address + 4352, bytes(8))
            return []
        data = probe.read(kernel, process, address, 16 + 8 * 512)
        count, overflow = struct.unpack_from('<2I', data)
        if count > 8 or overflow:
            raise RuntimeError('Native placement-policy observation overflowed')
        result = []
        for index in range(count):
            start = 16 + index * 512
            side, mode, policy, shooters, shift, depth, width, height = struct.unpack_from('<8i', data, start)
            small_count = struct.unpack_from('<i', data, start + 32)[0]
            if small_count < 0 or small_count > 32:
                raise RuntimeError('Invalid observed ordinary approach vector length')
            ordinary = list(struct.unpack_from('<' + 'i' * small_count, data, start + 36))
            large_start = start + 36 + small_count * 4
            large_count = struct.unpack_from('<i', data, large_start)[0]
            if large_count < 0 or large_count > 32:
                raise RuntimeError('Invalid observed large approach vector length')
            large = list(struct.unpack_from('<' + 'i' * large_count, data, large_start + 4))
            aggregate_start = large_start + 4 + large_count * 4
            aggregate_words = list(struct.unpack_from('<36I', data, aggregate_start))
            result.append({'side': side & 255, 'defensive': mode & 255,
                           'enemy_large': (policy >> 16) & 255, 'spread': (policy >> 24) & 255,
                           'shooter_count': shooters, 'window_shift': shift,
                           'depth': depth, 'grid': [width, height],
                           'ordinary_approach_rows': ordinary, 'large_approach_rows': large,
                           'aggregate_a_words': aggregate_words[:18], 'aggregate_b_words': aggregate_words[18:],
                           'removed_stacks': []})
        removed = probe.read(kernel, process, address + 4352, 16 + 16 * 64)
        removal_count, removal_overflow = struct.unpack_from('<2I', removed)
        if removal_count > 16 or removal_overflow:
            raise RuntimeError('Native weakest-stack removal observation overflowed')
        for index in range(removal_count):
            side, stage, record, creature, quantity, placed, excluded, ordinal = struct.unpack_from(
                '<8I', removed, 16 + index * 64)
            if stage >= len(result) or side != result[stage]['side']:
                raise RuntimeError('Native removal does not belong to a recorded placement stage')
            result[stage]['removed_stacks'].append({'record': record, 'type': creature, 'quantity': quantity,
                                                   'placed_before_removal': bool(placed),
                                                   'excluded_before_removal': bool(excluded),
                                                   'source_ordinal': ordinal})
        return result
    finally:
        kernel.CloseHandle(process)


def install_split_observer(pid):
    """Observe the game's split decision without supplying it to the DLL."""
    from keystone import Ks, KS_ARCH_X86, KS_MODE_32
    kernel = probe.api()
    process = probe.checked(kernel.OpenProcess(0x1038, False, pid))
    try:
        original = {0x855444: bytes.fromhex('8b 5c 24 44 dd d8'),
                    0x855472: bytes.fromhex('8b 44 24 34 8b 08'),
                    0x855496: bytes.fromhex('83 7c 24 48 02')}
        for entry, expected in original.items():
            if probe.read(kernel, process, entry, len(expected)) != expected:
                raise RuntimeError(f'Unexpected native split site {entry:x}')
        allocation = allocate_low_probe(kernel, process, 12288)
        records = allocation + 4096
        fpu = allocation + 8192
        bodies = {
            0x855444: f'''
                pushfd
                pushad
                mov eax, dword ptr [{records}]
                cmp eax, 8
                jae first_done
                shl eax, 6
                lea edi, [eax + {records + 16}]
                mov edx, dword ptr [esp]
                mov dword ptr [edi], edx
                mov edx, dword ptr [esp + 8]
                mov dword ptr [edi + 4], edx
                mov edx, dword ptr [esp + 0x58]
                mov edx, dword ptr [edx]
                mov edx, dword ptr [edx + 0x20]
                mov dword ptr [edi + 8], edx
                fxsave [{fpu}]
                fst qword ptr [edi + 24]
                fxrstor [{fpu}]
                inc dword ptr [{records}]
                jmp first_done
            first_done:
                popad
                popfd
                mov ebx, dword ptr [esp + 0x44]
                fstp st(0)
                jmp 0x85544a
            ''',
            0x855472: f'''
                pushfd
                pushad
                mov edi, dword ptr [{records}]
                test edi, edi
                jz second_done
                dec edi
                shl edi, 6
                add edi, {records + 16}
                mov eax, dword ptr [esp + 28]
                mov dword ptr [edi + 12], eax
                mov eax, dword ptr [esp]
                mov dword ptr [edi + 16], eax
            second_done:
                popad
                popfd
                mov eax, dword ptr [esp + 0x34]
                mov ecx, dword ptr [eax]
                jmp 0x855478
            ''',
            0x855496: f'''
                pushfd
                pushad
                mov edi, dword ptr [{records}]
                test edi, edi
                jz final_done
                dec edi
                shl edi, 6
                add edi, {records + 16}
                mov eax, dword ptr [esp + 0x6c]
                mov dword ptr [edi + 20], eax
            final_done:
                popad
                popfd
                cmp dword ptr [esp + 0x48], 2
                jmp 0x85549b
            ''',
        }
        old, ignored = wintypes.DWORD(), wintypes.DWORD()
        for index, (entry, expected) in enumerate(original.items()):
            address = allocation + index * 1024
            code = bytes(Ks(KS_ARCH_X86, KS_MODE_32).asm(bodies[entry], address)[0])
            if len(code) > 1024:
                raise RuntimeError('Split observer trampoline exceeds its code slot')
            probe.write(kernel, process, address, code)
        probe.checked(kernel.VirtualProtectEx(process, allocation, 4096, 0x20, ctypes.byref(old)))
        for index, (entry, expected) in enumerate(original.items()):
            address = allocation + index * 1024
            probe.checked(kernel.VirtualProtectEx(process, entry, len(expected), 0x40, ctypes.byref(old)))
            probe.write(kernel, process, entry, b'\xe9' + struct.pack('<i', address - entry - 5)
                        + b'\x90' * (len(expected) - 5))
            probe.checked(kernel.VirtualProtectEx(process, entry, len(expected), old.value, ctypes.byref(ignored)))
        probe.checked(kernel.FlushInstructionCache(process, None, 0))
        return records
    finally:
        kernel.CloseHandle(process)


def split_records(pid, address, arm=False):
    kernel = probe.api()
    process = probe.checked(kernel.OpenProcess(0x1038, False, pid))
    try:
        if arm:
            probe.write(kernel, process, address, bytes(16))
            return []
        data = probe.read(kernel, process, address, 16 + 8 * 64)
        count = struct.unpack_from('<I', data)[0]
        if count > 8:
            raise RuntimeError('Native split observer overflowed')
        result = []
        for index in range(count):
            start = 16 + index * 64
            initial, maximum, quantity, roll, after_roll, final = struct.unpack_from('<6i', data, start)
            ratio = struct.unpack_from('<d', data, start + 24)[0]
            result.append({'initial_stacks': initial, 'maximum_stacks': maximum,
                           'source_quantity': quantity, 'strength_ratio': ratio,
                           'random_roll': roll, 'after_roll': after_roll, 'final_stacks': final})
        return result
    finally:
        kernel.CloseHandle(process)


def install_spread_decision_observer(pid):
    """Capture the actual area-attack ratio at the native spread comparison."""
    from keystone import Ks, KS_ARCH_X86, KS_MODE_32
    kernel = probe.api()
    process = probe.checked(kernel.OpenProcess(0x1038, False, pid))
    try:
        entry = 0xa3029d
        expected = bytes.fromhex('88 85 a7 00 00 00')
        inputs_entry = 0xa3025e
        inputs_expected = bytes.fromhex('d9 44 24 10 d8 98 f4 0b 00 00')
        capability_sites = ((0xa2fe26, bytes.fromhex('e8 e5 f8 ff ff')),
                            (0xa2fe83, bytes.fromhex('e8 88 f8 ff ff')))
        large_score_sites = ((0xa301e8, bytes.fromhex('8b f0 8b 85 b0 00 00 00'), 0xe4),
                             (0xa30226, bytes.fromhex('89 44 24 1c db 44 24 1c'), 0x48))
        if probe.read(kernel, process, entry, len(expected)) != expected:
            raise RuntimeError('Unexpected native spread-decision site')
        if probe.read(kernel, process, inputs_entry, len(inputs_expected)) != inputs_expected:
            raise RuntimeError('Unexpected native spread-input site')
        if any(probe.read(kernel, process, site, len(original)) != original
               for site, original in capability_sites):
            raise RuntimeError('Unexpected native ranged-capability call site')
        if any(probe.read(kernel, process, site, len(original)) != original
               for site, original, _ in large_score_sites):
            raise RuntimeError('Unexpected native large-policy score return')
        allocation = allocate_low_probe(kernel, process, 32768)
        records = allocation + 4096
        capability_records = records + 2304
        assembly = f'''
            pushfd
            pushad
            mov edi, dword ptr [{records}]
            cmp edi, 16
            jae overflow
            shl edi, 7
            add edi, {records + 16}
            mov eax, dword ptr [esp + 8]
            mov dword ptr [edi], eax
            movzx edx, byte ptr [eax + 0xa6]
            mov dword ptr [edi + 124], edx
            mov eax, dword ptr [esp + 28]
            mov dword ptr [edi + 4], eax
            mov eax, dword ptr [esp + 0x2c]
            mov dword ptr [edi + 8], eax
            inc dword ptr [{records}]
            jmp done
        overflow:
            mov dword ptr [{records + 4}], 1
        done:
            popad
            popfd
            mov byte ptr [ebp + 0xa7], al
            jmp 0xa302a3
        '''
        code = bytes(Ks(KS_ARCH_X86, KS_MODE_32).asm(assembly, allocation)[0])
        probe.write(kernel, process, allocation, code)
        inputs_assembly = f'''
            pushfd
            pushad
            mov edi, dword ptr [{records}]
            cmp edi, 16
            jae inputs_done
            shl edi, 7
            add edi, {records + 16}
            mov eax, dword ptr [esp + 0x40]
            mov dword ptr [edi + 12], eax
            mov eax, dword ptr [esp + 0x2c]
            mov dword ptr [edi + 16], eax
            mov eax, dword ptr [esp + 28]
            mov eax, dword ptr [eax + 0xbf8]
            mov dword ptr [edi + 20], eax
            mov eax, dword ptr [ebp + 0xc]
            mov dword ptr [edi + 24], eax
            mov eax, dword ptr [ebp + 0x10]
            mov dword ptr [edi + 28], eax
            mov eax, dword ptr [ebp + 0x14]
            mov dword ptr [edi + 32], eax
            mov eax, dword ptr [ebp]
            mov dword ptr [edi + 36], eax
            mov eax, dword ptr [ebp + 0x40]
            mov dword ptr [edi + 40], eax
            mov eax, dword ptr [ebp + 0x6c]
            mov dword ptr [edi + 44], eax
            mov eax, dword ptr [ebp + 0x80]
            mov dword ptr [edi + 48], eax
            mov eax, dword ptr [ebp + 0x78]
            mov dword ptr [edi + 52], eax
            mov eax, dword ptr [ebp + 0x70]
            mov dword ptr [edi + 56], eax
            mov eax, dword ptr [ebp + 4]
            mov dword ptr [edi + 60], eax
            mov eax, dword ptr [esp + 28]
            mov edx, dword ptr [eax + 0x1d0]
            mov dword ptr [edi + 64], edx
            mov edx, dword ptr [eax + 0x1d8]
            mov dword ptr [edi + 68], edx
            mov eax, dword ptr [ebp + 0x28]
            mov dword ptr [edi + 72], eax
            mov eax, dword ptr [ebp + 0x2c]
            mov dword ptr [edi + 76], eax
            mov eax, dword ptr [ebp + 0x54]
            mov dword ptr [edi + 80], eax
            mov eax, dword ptr [ebp + 0x58]
            mov dword ptr [edi + 84], eax
            mov eax, dword ptr [ebp + 0x5c]
            mov dword ptr [edi + 88], eax
            mov eax, dword ptr [ebp + 0x70]
            mov dword ptr [edi + 92], eax
            mov eax, dword ptr [ebp + 0x74]
            mov dword ptr [edi + 96], eax
            mov eax, dword ptr [esp + 0x34]
            mov dword ptr [edi + 100], eax
            mov eax, dword ptr [esp + 28]
            mov eax, dword ptr [eax + 0xbf4]
            mov dword ptr [edi + 104], eax
        inputs_done:
            popad
            popfd
            fld dword ptr [esp + 0x10]
            fcomp dword ptr [eax + 0xbf4]
            jmp 0xa30268
        '''
        probe.write(kernel, process, allocation + 1024,
                    bytes(Ks(KS_ARCH_X86, KS_MODE_32).asm(inputs_assembly, allocation + 1024)[0]))
        for index, (site, _) in enumerate(capability_sites):
            trampoline = allocation + 2048 + index * 1024
            # Site one resumes at two native float comparisons. pushfd/pushad
            # add 36 bytes to the stack, so capture their four operands there.
            capability_assembly = f'''
                pushfd
                pushad
                mov edi, dword ptr [{capability_records}]
                cmp edi, 32
                jae before_done
                imul edi, 40
                add edi, {capability_records + 16}
                mov dword ptr [edi], {index + 1}
                mov dword ptr [edi + 4], ecx
                mov dword ptr [edi + 8], ebp
                mov eax, dword ptr [ebp + 0xc]
                mov dword ptr [edi + 32], eax
                mov eax, dword ptr [ebp + 0x54]
                mov dword ptr [edi + 36], eax
            before_done:
                popad
                popfd
                call 0xa2f710
                pushfd
                pushad
                mov edi, dword ptr [{capability_records}]
                cmp edi, 32
                jae after_done
                imul edi, 40
                add edi, {capability_records + 16}
                mov dword ptr [edi + 12], eax
            ''' + ('''
                mov eax, dword ptr [esp + 0x4c]
                mov dword ptr [edi + 16], eax
                mov eax, dword ptr [esp + 0x34]
                mov dword ptr [edi + 20], eax
                mov eax, dword ptr [esp + 0x44]
                mov dword ptr [edi + 24], eax
                mov eax, dword ptr [esp + 0x3c]
                mov dword ptr [edi + 28], eax
            ''' if index == 0 else '') + f'''
                inc dword ptr [{capability_records}]
            after_done:
                popad
                popfd
                jmp {site + 5}
            '''
            code = bytes(Ks(KS_ARCH_X86, KS_MODE_32).asm(capability_assembly, trampoline)[0])
            if len(code) > 1024:
                raise RuntimeError('Ranged-capability trampoline exceeds its code slot')
            probe.write(kernel, process, trampoline, code)
        for index, (site, original, pair_offset) in enumerate(large_score_sites):
            trampoline = allocation + 16384 + index * 1024
            replay = ('mov esi,eax; mov eax,dword ptr [ebp+0xb0]' if index == 0
                      else 'mov dword ptr [esp+0x1c],eax; fild dword ptr [esp+0x1c]')
            assembly = f'''
                pushfd
                pushad
                mov edx,dword ptr [{records}]
                cmp edx,16
                jae done
                mov eax,edx
                shl eax,7
                add eax,{records + 16}
                mov ecx,dword ptr [esp+28]
                mov dword ptr [eax+{108 + index * 4}],ecx
                mov ecx,dword ptr [esp+{0x50 if index == 0 else 0x60}]
                mov ebx,dword ptr [esp+{0x54 if index == 0 else 0x64}]
                sub ebx,ecx
                sar ebx,2
                mov dword ptr [eax+{116 + index * 4}],ebx
                imul edx,288
                add edx,{records + 4096 + index * 144}
                mov edi,edx
                lea esi,[esp+{36 + pair_offset}]
                mov ecx,36
                cld
                rep movs dword ptr es:[edi], dword ptr [esi]
            done:
                popad
                popfd
                {replay}
                jmp {site + len(original)}
            '''
            code = bytes(Ks(KS_ARCH_X86, KS_MODE_32).asm(assembly, trampoline)[0])
            if len(code) > 1024:
                raise RuntimeError('Large-policy trampoline exceeds its slot')
            probe.write(kernel, process, trampoline, code)
        old, ignored = wintypes.DWORD(), wintypes.DWORD()
        probe.checked(kernel.VirtualProtectEx(process, allocation, 4096, 0x20, ctypes.byref(old)))
        probe.checked(kernel.VirtualProtectEx(process, allocation + 16384, 4096, 0x20, ctypes.byref(old)))
        probe.checked(kernel.VirtualProtectEx(process, inputs_entry, len(inputs_expected), 0x40, ctypes.byref(old)))
        probe.write(kernel, process, inputs_entry,
                    b'\xe9' + struct.pack('<i', allocation + 1024 - inputs_entry - 5)
                    + b'\x90' * (len(inputs_expected) - 5))
        probe.checked(kernel.VirtualProtectEx(process, inputs_entry, len(inputs_expected), old.value,
                                              ctypes.byref(ignored)))
        probe.checked(kernel.VirtualProtectEx(process, entry, len(expected), 0x40, ctypes.byref(old)))
        probe.write(kernel, process, entry, b'\xe9' + struct.pack('<i', allocation - entry - 5) + b'\x90')
        probe.checked(kernel.VirtualProtectEx(process, entry, len(expected), old.value, ctypes.byref(ignored)))
        for index, (site, original) in enumerate(capability_sites):
            trampoline = allocation + 2048 + index * 1024
            probe.checked(kernel.VirtualProtectEx(process, site, len(original), 0x40, ctypes.byref(old)))
            probe.write(kernel, process, site, b'\xe9' + struct.pack('<i', trampoline - site - 5))
            probe.checked(kernel.VirtualProtectEx(process, site, len(original), old.value, ctypes.byref(ignored)))
        for index, (site, original, _) in enumerate(large_score_sites):
            trampoline = allocation + 16384 + index * 1024
            probe.checked(kernel.VirtualProtectEx(process, site, len(original), 0x40, ctypes.byref(old)))
            probe.write(kernel, process, site, b'\xe9' + struct.pack('<i', trampoline - site - 5)
                        + b'\x90' * (len(original) - 5))
            probe.checked(kernel.VirtualProtectEx(process, site, len(original), old.value, ctypes.byref(ignored)))
        probe.checked(kernel.FlushInstructionCache(process, None, 0))
        return records
    finally:
        kernel.CloseHandle(process)


def spread_decisions(pid, address, arm=False):
    kernel = probe.api()
    process = probe.checked(kernel.OpenProcess(0x1038, False, pid))
    try:
        if arm:
            probe.write(kernel, process, address, bytes(16 + 16 * 128))
            probe.write(kernel, process, address + 2304, bytes(8))
            probe.write(kernel, process, address + 4096, bytes(16 * 288))
            return [], []
        data = probe.read(kernel, process, address, 16 + 16 * 128)
        large_pairs = probe.read(kernel, process, address + 4096, 16 * 288)
        count, overflow = struct.unpack_from('<2I', data)
        if count > 16 or overflow:
            raise RuntimeError('Native spread-decision observation overflowed')
        result = []
        for index in range(count):
            start = 16 + index * 128
            pointer, decision, ratio = struct.unpack_from('<IIf', data, start)
            denominator, input_ratio, threshold = struct.unpack_from('<iff', data, start + 12)
            damage, attack, multiplier, extra0, extra16, defence, role38, role30, role28, counter = (
                struct.unpack_from('<iffiiffffi', data, start + 24))
            increase, decrease = struct.unpack_from('<ff', data, start + 64)
            (own_shooter_damage, own_shooter_attack, other_damage, other_attack, other_multiplier,
             other_shooter_damage, other_shooter_attack) = struct.unpack_from('<ffiffff', data, start + 72)
            result.append({'strategy_pointer': pointer, 'spread': decision & 255,
                           'large_melee_policy': bool(struct.unpack_from('<I', data, start + 124)[0]),
                           'enemy_area_attack_relative_power': ratio,
                           'input_ratio': input_ratio, 'aggregate_denominator': denominator,
                           'loaded_threshold': threshold,
                           'large_melee_relative_power': struct.unpack_from('<f', data, start + 100)[0],
                           'loaded_large_melee_threshold': struct.unpack_from('<f', data, start + 104)[0],
                           'large_policy_score_words': list(struct.unpack_from('<4I', data, start + 108)),
                           'large_policy_aggregate_pairs': [list(struct.unpack_from('<36I', large_pairs, index * 288 + offset))
                                                            for offset in (0, 144)],
                           'loaded_damage_coefficients': {'increase': increase, 'decrease': decrease},
                           'own_aggregate': {'damage': damage, 'attack': attack,
                                             'multiplier': multiplier, 'extra0': extra0,
                                             'extra16': extra16, 'counter': counter,
                                             'shooter_damage': own_shooter_damage,
                                             'shooter_attack': own_shooter_attack},
                           'opponent_aggregate': {'defence': defence, 'damage': other_damage,
                                                  'attack': other_attack, 'multiplier': other_multiplier,
                                                  'shooter_damage': other_shooter_damage,
                                                  'shooter_attack': other_shooter_attack,
                                                  'category_28': role28, 'category_30': role30,
                                                  'category_38': role38}})
        capability_data = probe.read(kernel, process, address + 2304, 16 + 32 * 40)
        capability_count, capability_overflow = struct.unpack_from('<2I', capability_data)
        if capability_count > 32 or capability_overflow:
            raise RuntimeError('Native ranged-capability observation overflowed')
        capability = []
        for index in range(capability_count):
            offset = 16 + index * 40
            phase, actor, strategy, value = struct.unpack_from('<4I', capability_data, offset)
            comparisons = struct.unpack_from('<4f', capability_data, offset + 16)
            own_damage, opponent_damage = struct.unpack_from('<2i', capability_data, offset + 32)
            capability.append({'phase': phase, 'actor_pointer': actor,
                               'strategy_pointer': strategy, 'result': bool(value & 255),
                               'comparison_operands': list(comparisons) if phase == 1 else None,
                               'aggregate_damage_pair': [own_damage, opponent_damage]})
        return result, capability
    finally:
        kernel.CloseHandle(process)


def install_attempt_observer(pid, source_strength=False):
    """Bounded passive cell attempts and placement-path entry snapshots."""
    from keystone import Ks, KS_ARCH_X86, KS_MODE_32
    from capstone import Cs, CS_ARCH_X86, CS_MODE_32
    import pefile
    kernel = probe.api()
    process = probe.checked(kernel.OpenProcess(0x1438, False, pid))
    try:
        base = allocate_low_probe(kernel, process, 98304)
        header, attempts = base + 4096, base + 8192
        path_header, path_rows = base + 36864, base + 40960
        strength_header = base + 65536
        entry = 0x857160
        stolen = b''
        for instruction in Cs(CS_ARCH_X86, CS_MODE_32).disasm(probe.read(kernel, process, entry, 24), entry):
            if instruction.mnemonic.startswith(('j', 'call')):
                raise RuntimeError('Cannot relocate native cell-attempt entry')
            stolen += instruction.bytes
            if len(stolen) >= 5:
                break
        if len(stolen) < 5:
            raise RuntimeError('Incomplete native cell-attempt prologue')
        return_code = f'''
            pushfd
            pushad
            mov edi, dword ptr [{header + 4}]
            mov eax, dword ptr [esp + 28]
            mov dword ptr [edi + 56], eax
            mov eax, dword ptr [edi]
            mov dword ptr [{header + 8}], eax
            mov esi, dword ptr [edi + 8]
            add edi, 60
            mov ecx, 36
            cld
            rep movs byte ptr es:[edi], byte ptr [esi]
            popad
            popfd
            jmp dword ptr [{header + 8}]
        '''
        probe.write(kernel, process, base + 2048, bytes(Ks(KS_ARCH_X86, KS_MODE_32).asm(return_code, base + 2048)[0]))
        body = f'''
            pushfd
            pushad
            mov eax, dword ptr [{header}]
            cmp eax, 256
            jae overflow
            imul eax, 96
            add eax, {attempts}
            mov dword ptr [{header + 4}], eax
            mov edx, dword ptr [esp + 36]
            mov dword ptr [eax], edx
            mov dword ptr [eax + 4], ecx
            mov esi, dword ptr [esp + 40]
            mov dword ptr [eax + 8], esi
            mov edx, dword ptr [esp + 44]
            mov dword ptr [eax + 12], edx
            mov edx, dword ptr [esp + 48]
            mov dword ptr [eax + 16], edx
            lea edi, [eax + 20]
            mov ecx, 36
            cld
            rep movs byte ptr es:[edi], byte ptr [esi]
            mov dword ptr [esp + 36], {base + 2048}
            inc dword ptr [{header}]
            jmp done
        overflow:
            mov dword ptr [{header + 16}], 1
        done:
            popad
            popfd
        '''
        encoded = bytes(Ks(KS_ARCH_X86, KS_MODE_32).asm(body, base)[0]) + stolen
        encoded += b'\xe9' + struct.pack('<i', entry + len(stolen) - (base + len(encoded) + 5))
        probe.write(kernel, process, base, encoded)
        old, ignored = wintypes.DWORD(), wintypes.DWORD()
        probe.checked(kernel.VirtualProtectEx(process, base, 4096, 0x20, ctypes.byref(old)))
        probe.checked(kernel.VirtualProtectEx(process, entry, len(stolen), 0x40, ctypes.byref(old)))
        probe.write(kernel, process, entry, b'\xe9' + struct.pack('<i', base - entry - 5)
                    + b'\x90' * (len(stolen) - 5))
        probe.checked(kernel.VirtualProtectEx(process, entry, len(stolen), old.value, ctypes.byref(ignored)))
        probe.checked(kernel.FlushInstructionCache(process, None, 0))
        # 857780 snapshots the vector after 857640's direct writes.
        cursor = base + 32768
        for entry, vector_mode in ((0x85a040, 'ecx'), (0x85a110, 'ecx'),
                                   (0x859eb0, 'ecx'), (0x857510, 'stack'),
                                   (0x8593c0, 'context'),
                                   (0x858fb0, 'context'),
                                   (0x859670, 'context'), (0x857640, 'stack'),
                                   (0x857780, 'stack'), (0x8582a7, 'support'),
                                   (0x859930, 'context')):
            original = b''
            for instruction in Cs(CS_ARCH_X86, CS_MODE_32).disasm(
                    probe.read(kernel, process, entry, 24), entry):
                if instruction.mnemonic.startswith(('j', 'call')):
                    raise RuntimeError(f'Cannot relocate placement-path entry {entry:#x}')
                original += instruction.bytes
                if len(original) >= 5:
                    break
            if len(original) < 5:
                raise RuntimeError('Incomplete placement-path prologue')
            vector_code = ('mov esi, dword ptr [esp + 24]' if vector_mode == 'ecx'
                           else 'mov esi, dword ptr [esp + 40]' if vector_mode == 'stack'
                           else 'lea esi, [esp + 0x54]' if vector_mode == 'support'
                           else 'mov esi, dword ptr [ecx + 0xf0]')
            side_code = ('mov dword ptr [edi + 32], 0xffffffff' if vector_mode == 'ecx'
                         else ('mov ecx, dword ptr [esp + 0x38]; '
                               'mov dword ptr [edi + 8], ecx; '
                               'movzx eax, byte ptr [ecx]; mov dword ptr [edi + 32], eax')
                         if vector_mode == 'support'
                         else 'movzx eax, byte ptr [ecx]; mov dword ptr [edi + 32], eax')
            element_size = 8 if vector_mode == 'support' else 36
            body = f'''
                pushfd
                pushad
                cmp dword ptr [{path_header + 8}], 0
                je done
                mov eax, dword ptr [{path_header}]
                cmp eax, 64
                jae overflow
                imul eax, 288
                lea edi, [eax + {path_rows}]
                mov dword ptr [edi], {entry}
                mov eax, dword ptr [esp + 36]
                mov dword ptr [edi + 4], eax
                mov dword ptr [edi + 8], ecx
                mov dword ptr [edi + 12], edx
                mov eax, dword ptr [esp + 40]
                mov dword ptr [edi + 16], eax
                mov eax, dword ptr [esp + 44]
                mov dword ptr [edi + 20], eax
                mov eax, dword ptr [esp + 48]
                mov dword ptr [edi + 24], eax
                mov dword ptr [edi + 28], 0
                {side_code}
                {vector_code}
                cmp esi, 0x10000
                jb invalid
                mov eax, dword ptr [esi]
                mov ecx, dword ptr [esi + 4]
                cmp eax, 0x10000
                jb invalid
                sub ecx, eax
                jb invalid
                cmp ecx, 252
                ja invalid
                mov esi, eax
                mov eax, ecx
                xor edx, edx
                mov ebx, {element_size}
                div ebx
                test edx, edx
                jnz invalid
                mov dword ptr [edi + 28], eax
                add edi, 36
                cld
                rep movs byte ptr es:[edi], byte ptr [esi]
                inc dword ptr [{path_header}]
                jmp done
            invalid:
                mov dword ptr [{path_header + 4}], 2
                jmp done
            overflow:
                mov dword ptr [{path_header + 4}], 1
            done:
                popad
                popfd
            '''
            encoded = bytes(Ks(KS_ARCH_X86, KS_MODE_32).asm(body, cursor)[0]) + original
            encoded += b'\xe9' + struct.pack('<i', entry + len(original) - (cursor + len(encoded) + 5))
            if cursor + len(encoded) > base + 36864:
                raise RuntimeError('Placement-path code capacity exceeded')
            probe.write(kernel, process, cursor, encoded)
            probe.checked(kernel.VirtualProtectEx(process, entry, len(original), 0x40, ctypes.byref(old)))
            probe.write(kernel, process, entry, b'\xe9' + struct.pack('<i', cursor - entry - 5)
                        + b'\x90' * (len(original) - 5))
            probe.checked(kernel.VirtualProtectEx(process, entry, len(original), old.value, ctypes.byref(ignored)))
            cursor += len(encoded)
        strength_entry = 0x4e9ef6
        strength_original = bytes.fromhex('5f 5e 5b 8b e5')
        if probe.read(kernel, process, strength_entry, 5) != strength_original:
            raise RuntimeError('Unexpected source-strength return site')
        source_frozen = strength_header + 12
        probe.write(kernel, process, source_frozen, b'\x01')
        if source_strength:
            # Match the DLL producer's freeze boundary. A post-freeze UI strength
            # query is outside this comparison and must not exhaust its journal.
            plugin = pefile.PE(str(check.PLUGIN))
            export = next(item.address for item in plugin.DIRECTORY_ENTRY_EXPORT.symbols
                          if item.name == b'WorkshopDeploymentPreviewSuperadminInputTrace')
            instructions = list(Cs(CS_ARCH_X86, CS_MODE_32).disasm(
                plugin.get_data(export, 512), plugin.OPTIONAL_HEADER.ImageBase + export))
            frozen_address = None
            for index, instruction in enumerate(instructions):
                if instruction.mnemonic != 'mov' or instruction.op_str != 'dword ptr [ebx + 0x14], eax':
                    continue
                for previous in reversed(instructions[max(0, index - 8):index]):
                    match = re.search(r'byte ptr \[(0x[0-9a-f]+)\]', previous.op_str)
                    if match:
                        frozen_address = int(match.group(1), 16)
                        break
            if frozen_address is None:
                raise RuntimeError('Cannot identify source-input freeze flag in this compiled DLL')
            jump = probe.read(kernel, process, 0x4e9c4d, 5)
            if jump[0] != 0xe9:
                raise RuntimeError('Owned source-strength hook is not installed')
            target = 0x4e9c4d + 5 + struct.unpack_from('<i', jump, 1)[0]
            region = ctypes.create_string_buffer(48)
            kernel.VirtualQueryEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t]
            kernel.VirtualQueryEx.restype = ctypes.c_size_t
            if kernel.VirtualQueryEx(process, target, region, len(region)) != len(region):
                raise RuntimeError('Cannot identify owned DLL allocation')
            remote_base = struct.unpack_from('<Q', region.raw, 8)[0]
            if probe.read(kernel, process, remote_base, 2) != b'MZ':
                raise RuntimeError('Source-strength target is not in a PE module')
            source_frozen = remote_base + frozen_address - plugin.OPTIONAL_HEADER.ImageBase
            if probe.read(kernel, process, source_frozen, 1) not in (b'\x00', b'\x01'):
                raise RuntimeError('Invalid source-input freeze flag')
        strength_code = f'''
            pushfd
            pushad
            cmp dword ptr [{strength_header + 8}], 1
            jne strength_done
            cmp byte ptr [{source_frozen}], 0
            jne strength_done
            mov dword ptr [{strength_header + 16}], 0
            fnstcw word ptr [{strength_header + 16}]
            mov ecx, dword ptr [{strength_header}]
            mov edi, {strength_header + 256}
        strength_scan:
            test ecx, ecx
            jz strength_new
            cmp dword ptr [edi], esi
            jne strength_advance
            cmp dword ptr [edi + 4], ebx
            jne strength_advance
            mov eax, dword ptr [ebp + 8]
            cmp dword ptr [edi + 8], eax
            jne strength_advance
            mov eax, dword ptr [esp + 28]
            cmp dword ptr [edi + 12], eax
            jne strength_advance
            mov eax, dword ptr [esp + 20]
            cmp dword ptr [edi + 16], eax
            jne strength_advance
            mov eax, dword ptr [{strength_header + 16}]
            cmp dword ptr [edi + 20], eax
            je strength_done
        strength_advance:
            add edi, 24
            dec ecx
            jmp strength_scan
        strength_new:
            mov edi, dword ptr [{strength_header}]
            cmp edi, 256
            jae strength_full
            imul edi, edi, 24
            add edi, {strength_header + 256}
            mov dword ptr [edi], esi
            mov dword ptr [edi + 4], ebx
            mov ecx, dword ptr [ebp + 8]
            mov dword ptr [edi + 8], ecx
            mov eax, dword ptr [esp + 28]
            mov edx, dword ptr [esp + 20]
            mov dword ptr [edi + 12], eax
            mov dword ptr [edi + 16], edx
            mov dword ptr [edi + 20], 0
            fnstcw word ptr [edi + 20]
            inc dword ptr [{strength_header}]
            jmp strength_done
        strength_full:
            mov dword ptr [{strength_header + 4}], 1
        strength_done:
            popad
            popfd
            pop edi
            pop esi
            pop ebx
            mov esp, ebp
            jmp 0x4e9efb
        '''
        encoded = bytes(Ks(KS_ARCH_X86, KS_MODE_32).asm(strength_code, base + 3072)[0])
        if len(encoded) > 1024:
            raise RuntimeError('Source-strength reference code capacity exceeded')
        probe.checked(kernel.VirtualProtectEx(process, base, 4096, 0x40, ctypes.byref(old)))
        probe.write(kernel, process, base + 3072, encoded)
        probe.checked(kernel.VirtualProtectEx(process, base, 4096, old.value, ctypes.byref(ignored)))
        probe.checked(kernel.VirtualProtectEx(process, strength_entry, 5, 0x40, ctypes.byref(old)))
        probe.write(kernel, process, strength_entry,
                    b'\xe9' + struct.pack('<i', base + 3072 - strength_entry - 5))
        probe.checked(kernel.VirtualProtectEx(process, strength_entry, 5, old.value, ctypes.byref(ignored)))
        probe.checked(kernel.VirtualProtectEx(process, base + 32768, 4096, 0x20, ctypes.byref(old)))
        probe.checked(kernel.FlushInstructionCache(process, None, 0))
        return header, attempts, path_header
    finally:
        kernel.CloseHandle(process)


def attempt_records(pid, addresses, arm=False, paths=False, strengths=False):
    header, attempts, path_header = addresses
    kernel = probe.api()
    process = probe.checked(kernel.OpenProcess(0x1038, False, pid))
    try:
        if arm:
            probe.write(kernel, process, header, bytes(20))
            probe.write(kernel, process, path_header, struct.pack('<3I', 0, 0, 1))
            probe.write(kernel, process, path_header + 28672, struct.pack('<3I', 0, 0, 1))
            return []
        if strengths:
            address = path_header + 28672
            count, overflow, _ = struct.unpack('<3I', probe.read(kernel, process, address, 12))
            if count > 256:
                raise RuntimeError('Invalid source-strength reference count')
            data = probe.read(kernel, process, address + 256, count * 24) if count else b''
            probe.write(kernel, process, address + 8, bytes(4))
            return {'overflow': overflow,
                    'rows': [list(struct.unpack_from('<6I', data, index * 24)) for index in range(count)]}
        if paths:
            count, overflow, _ = struct.unpack('<3I', probe.read(kernel, process, path_header, 12))
            if count > 64 or overflow:
                raise RuntimeError(f'Placement-path observation invalid/overflow: {overflow}')
            result = []
            for index in range(count):
                raw = probe.read(kernel, process, path_header + 4096 + index * 288, 288)
                entry, caller, context, other, first, second, third, size, side = struct.unpack_from('<9I', raw)
                if entry == 0x8582a7:
                    result.append({'sequence': index, 'entry': hex(entry), 'context': context,
                                   'side': side, 'support_candidates': [
                                       list(struct.unpack_from('<2i', raw, 36 + slot * 8))
                                       for slot in range(size)]})
                    continue
                stacks = []
                for slot in range(size):
                    offset = 36 + slot * 36
                    source, secondary, quantity, source_flags = struct.unpack_from('<4I', raw, offset)
                    kind = struct.unpack_from('<I', raw, offset + 28)[0]
                    stacks.append({'source': source, 'secondary': secondary,
                                   'source_flags': source_flags, 'type': kind,
                                   'quantity': quantity, 'placed': bool(raw[offset + 16]),
                                   'cell': list(struct.unpack_from('<2i', raw, offset + 20)),
                                   'excluded': bool(raw[offset + 32])})
                result.append({'sequence': index, 'entry': hex(entry), 'caller': hex(caller),
                               'context': context, 'other_argument': other,
                               'stack_arguments': [first, second, third],
                               'side': None if side == 0xffffffff else side, 'stacks': stacks})
            return result
        count, _, _, _, overflow = struct.unpack('<5I', probe.read(kernel, process, header, 20))
        if count > 256 or overflow:
            raise RuntimeError('Native cell-attempt observation overflowed')
        result = []
        for index in range(count):
            raw = probe.read(kernel, process, attempts + index * 96, 96)
            _, context, record, local_x, local_y = struct.unpack_from('<5I', raw)
            result.append({'context': context, 'record': record, 'candidate_local': [local_x, local_y],
                           'success': bool(struct.unpack_from('<I', raw, 56)[0] & 255),
                           'cell': list(struct.unpack_from('<2i', raw, 80))})
        return result
    finally:
        kernel.CloseHandle(process)


def explain(projection, observed, comparison, policy, split, attempts, paths=()):
    predicted = {slot['type']: slot['cell'] for slot in projection['footprints']}
    actual = {unit['type']: unit['cell'] for unit in observed['units']}
    differences = [{'type': kind, 'predicted_cell': predicted.get(kind), 'actual_cell': cell}
                   for kind, cell in actual.items() if predicted.get(kind) != cell]
    defender = next((entry for entry in reversed(policy) if entry['side'] == 0), None)
    removals = [removed for entry in policy if entry['side'] == 0 for removed in entry.get('removed_stacks', [])]
    if not projection.get('prediction_complete', True):
        if removals:
            return {'status': 'native_retry_exclusion',
                    'reason': ('Native retries excluded source stacks ' +
                               str([(entry['type'], entry['quantity']) for entry in removals]) +
                               '; the predictor has not reproduced the complete exclusion/retry sequence'),
                    'differences': differences, 'native_defender_policy': defender,
                    'removed_stacks_after_start': removals}
        return {'status': 'incomplete_prediction',
                'reason': f"Only {projection['models']} of {projection['public']} source portraits produced projections before Start",
                'differences': differences, 'native_defender_policy': defender,
                'cell_attempts_after_start': attempts}
    if (comparison.get('quantities_checked') and comparison['position_full_match']
            and not comparison.get('full_composition_match')):
        if comparison['exact_matches'] == comparison['predicted'] == comparison['actual']:
            status = 'quantity_mismatch'
        elif comparison['same_type_counts']:
            status = 'assignment_mismatch'
        elif comparison['same_base_counts']:
            status = 'grade_mismatch'
        else:
            status = 'type_mismatch'
        return {'status': status,
                'reason': 'Occupied cells match, but exact types/quantities assigned to those cells differ',
                'differences': differences, 'native_defender_policy': defender}
    if comparison['position_full_match']:
        return {'status': 'matched_positions',
                'reason': ('All occupied cells match; creature grades/types differ' if not comparison['same_type_counts']
                           else 'All observed occupied cells equal the pre-Start prediction'),
                'differences': differences, 'native_defender_policy': defender}
    if comparison['predicted'] != comparison['actual']:
        counts = {}
        for unit in observed['units']:
            counts[unit['type']] = counts.get(unit['type'], 0) + 1
        duplicates = [kind for kind, count in counts.items() if count > 1]
        decision = split[0] if comparison['predicted'] == 1 and len(split) == 1 else None
        split_observed = (decision is not None and comparison['actual'] > 1
                          and decision['final_stacks'] == comparison['actual'])
        if decision is not None and decision['final_stacks'] == comparison['actual']:
            cause = (f"The engine used ratio {decision['strength_ratio']:.6g} to choose "
                     f"{decision['initial_stacks']} stacks, rolled {decision['random_roll']} to get "
                     f"{decision['after_roll']}, then limited by quantity {decision['source_quantity']} "
                     f"to {decision['final_stacks']} stacks")
        else:
            cause = 'The observed stack count or types differ; the specific transformation trigger is not measured'
        return {'status': 'composition_changed',
                'reason': cause, 'observed_split': split_observed,
                'split_decision': decision,
                'duplicate_observed_types': duplicates, 'differences': differences,
                'native_defender_policy': defender}
    successful = [attempt for attempt in attempts if attempt['success'] and attempt['cell'][0] >= 8]
    chosen = [attempt['cell'] for attempt in successful]
    defender_records = {attempt['record'] for attempt in successful}
    attempted_rows = [attempt['candidate_local'][1] + 1 for attempt in attempts
                      if attempt['record'] in defender_records]
    if defender and bool(defender['spread']) != projection['predicted_spread']:
        status = 'mode_mismatch'
        cause = (f"The engine chose spread={bool(defender['spread'])} while the frozen pre-Start "
                 f"DLL choice was spread={projection['predicted_spread']}; native candidate rows "
                 f"were {attempted_rows}, with accepted cells {chosen}")
    elif defender and bool(defender['defensive']) != projection['predicted_defensive']:
        status = 'mode_mismatch'
        cause = (f"The engine chose defensive={bool(defender['defensive'])} while the frozen "
                 f"pre-Start DLL choice was defensive={projection['predicted_defensive']}; "
                 f"native accepted cells were {chosen}")
    else:
        status = 'pending_causal_reconstruction'
        cause = (f"The engine accepted native candidates at {chosen} under ordinary placement; "
                 'recorded row scores and attempts still need to identify the exact failed rule')
        footprints = {slot['type']: slot for slot in projection['footprints']}
        for difference in differences:
            kind = difference['type']
            actual_cell = difference['actual_cell']
            predicted_cell = difference['predicted_cell']
            if kind not in footprints or actual_cell is None or predicted_cell is None:
                continue
            for before, after in zip(paths, paths[1:]):
                if (before['entry'] != '0x857640' or after['entry'] != '0x857780'
                        or before['context'] != after['context'] or before['side'] != 0
                        or before['stack_arguments'][1] != after['stack_arguments'][1]):
                    continue
                pending = next((stack for stack in before['stacks']
                                if stack['type'] == kind and not stack['placed']), None)
                written = next((stack for stack in after['stacks']
                                if pending is not None and stack['source'] == pending['source']
                                and stack['type'] == kind and stack['quantity'] == pending['quantity']
                                and stack['placed'] and stack['cell'] == actual_cell), None)
                if written is not None:
                    support = [event for event in paths
                               if event['entry'] == '0x8582a7'
                               and event['context'] == before['context'] and event['side'] == 0]
                    rejected_support = bool(support and defender and defender['depth'] > 0
                        and all(event['support_candidates'] and all(
                            not (0 <= x < defender['depth'] and 0 <= y < defender['grid'][1] - 2)
                            for x, y in event['support_candidates']) for event in support))
                    return {'status': 'large_leftover_write_confirmed',
                            'reason': (f"Type {kind} was unplaced at 0x857640 entry and placed at "
                                       f"{actual_cell} by the following 0x857780 entry. "
                                       'The large leftover pass wrote this cell after the primary passes; '
                                       + ('all measured support neighbours were outside local deployment bounds'
                                          if rejected_support else
                                          'why those passes skipped the unit still requires reconstruction')),
                            'placement_path_evidence': [before, after],
                            'support_bounds_rejection_confirmed': rejected_support,
                            'support_candidate_evidence': support,
                            'differences': differences, 'native_defender_policy': defender}
            if (footprints[kind]['size'] == 2 and actual_cell not in chosen
                    and actual_cell[1] == 2):
                status = 'untraced_large_placement'
                cause = (f"Large type {kind} ended at {actual_cell}, absent from successful "
                         f"0x857160 calls; the frozen DLL selected {predicted_cell}. "
                         'A 0x857640 leftover scan or a preserved placement are hypotheses; '
                         'the entry path, direct writes and their chronology are not captured')
                break
            accepted = next((index for index, attempt in enumerate(attempts)
                             if attempt['success'] and attempt['cell'] == actual_cell), None)
            if accepted is None:
                continue
            record = attempts[accepted]['record']
            rejected = [attempt['candidate_local'] for attempt in attempts[:accepted]
                        if attempt['record'] == record and not attempt['success']]
            if (actual_cell[0] > predicted_cell[0] and rejected
                    and any(local[0] == 1 for local in rejected)):
                status = 'front_lane_after_rear_collision'
                cause = (f"Native 0x857160 rejected rear-lane local candidates {rejected} for type {kind}, "
                         f"then accepted front cell {actual_cell}; the DLL retained rear cell {predicted_cell}")
                break
            if footprints[kind]['size'] == 2 and actual_cell[1] == 2 and rejected:
                status = 'large_row_retry_order'
                cause = (f"Native 0x857160 rejected local rows {rejected} for the large type {kind}, "
                         f"then accepted its local-row-zero fallback {actual_cell}; "
                         f"the DLL selected {predicted_cell} before that retry sequence")
                break
    return {'status': status, 'reason': cause,
            'native_successful_candidates': successful, 'differences': differences,
            'native_defender_policy': defender}


def enter_generated_battle(pid, hero, pack, expected_count, allow_partial=False):
    """Move close enough for a generated map object and verify each dispatch."""
    target = (pack['x'], pack['y'])
    offsets = (None, (-3, -3), (-2, 0), (2, 0), (0, -2), (0, 2))
    attempts = []
    tried_cells = set()
    for offset in offsets:
        state = check.control('hero', hero)
        distance = abs(state['x'] - target[0]) + abs(state['y'] - target[1])
        if offset is not None or distance > 18:
            candidates = [(target[0] + dx, target[1] + dy)
                          for radius in range(1, 9)
                          for dx in range(-radius, radius + 1)
                          for dy in range(-radius, radius + 1)
                          if abs(dx) + abs(dy) == radius and (target[0] + dx, target[1] + dy) not in tried_cells]
            points = ','.join('{' + str(x) + ',' + str(y) + '}' for x, y in candidates)
            expression = ("@SetGameVar('__workshop_approach','none'); local cells={" + points + "}; for index,cell in cells do "
                          f"if IsTilePassable(cell[1],cell[2],{state['floor']}) then "
                          "SetGameVar('__workshop_approach',cell[1]..','..cell[2]); break; end; end;")
            check.control('console', expression)
            destination = check.control('eval', "GetGameVar('__workshop_approach')")['result']
            if destination == 'none':
                attempts.append({'reason': 'no engine-confirmed passable approach tile'})
                break
            destination_x, destination_y = (int(value) for value in destination.split(','))
            tried_cells.add((destination_x, destination_y))
            attempts.append({'hero_cell': [state['x'], state['y'], state['floor']],
                             'teleport_destination': [destination_x, destination_y, state['floor']],
                             'validated_by': 'IsTilePassable'})
            try:
                check.control('teleport', hero, str(destination_x), str(destination_y), '--floor', str(state['floor']))
            except RuntimeError as error:
                if 'Hero did not reach destination' not in str(error):
                    raise
            state = check.control('hero', hero)
            distance = abs(state['x'] - target[0]) + abs(state['y'] - target[1])
            if distance > 18:
                attempts.append({'hero_cell': [state['x'], state['y']], 'distance': distance,
                                 'reason': 'teleport did not reach the object vicinity'})
                continue
        check.control('interact', hero, pack['name'])
        try:
            return check.wait_for_models(pid, expected_count, allow_partial=allow_partial), attempts
        except RuntimeError as error:
            if 'Projection readiness timed out' not in str(error):
                raise
            latest = check.diagnostics(pid)
            if latest['public'] > 0 and latest['models'] > 0:
                raise
            # Preserve the readiness failure if adventure queries are unavailable.
            # A readable hero alone does not prove the current UI phase.
            try:
                state = check.control('hero', hero)
            except RuntimeError as transition_error:
                raise error from transition_error
            attempts.append({'hero_cell': [state['x'], state['y']], 'distance': distance,
                             'reason': 'no deployment after addressed interaction'})
    raise RuntimeError('Generated neutral did not enter combat after verified approaches: '
                       + json.dumps({'pack': pack['name'], 'attempts': attempts}))


def parse_hero_army(specifications, creature_names):
    if len(specifications) > 6:
        raise ValueError('Custom hero control supports at most six creature types')
    army = {}
    for specification in specifications:
        match = re.fullmatch(r'(CREATURE_[A-Z0-9_]+):([0-9]+)', specification)
        if match is None:
            raise ValueError('Expected CREATURE_NAME:positive_count')
        name, amount = match.groups()
        if name not in creature_names or creature_names.index(name) == 0 or name in army:
            raise ValueError('Unknown or repeated creature in custom hero army: ' + name)
        count = int(amount)
        if not 1 <= count <= 1000000:
            raise ValueError('Custom hero count must be in 1..1000000')
        army[name] = count
    return army


def run_map(round_number, fixture, report, destination, creature_names, background=False):
    foreground = None
    original_clip = None
    if background:
        user32 = ctypes.WinDLL('user32', use_last_error=True)
        get_foreground = user32.GetForegroundWindow
        get_foreground.restype = ctypes.c_void_p
        foreground = get_foreground()
        if not foreground:
            raise RuntimeError('Cannot verify the current foreground window before background launch')
        original_clip = wintypes.RECT()
        user32.GetClipCursor.argtypes = [ctypes.POINTER(wintypes.RECT)]
        if not user32.GetClipCursor(ctypes.byref(original_clip)):
            raise RuntimeError('Cannot record cursor clipping before background launch')
    launch_arguments = ['launch', '--map', fixture['name'], '--control', '--observe-deployment']
    if background:
        launch_arguments.append('--background')
    launch = json.loads(check.command(check.PYTHON, '-X', 'utf8', str(check.PROBE), *launch_arguments))
    pid = launch['pid']
    created = launch.get('created')
    hero_control = 'small' if fixture['kind'] == 'authored_polygon' and round_number % 2 == 0 else 'default'
    if report.get('research_hero_army'):
        hero_control = 'custom'
    run = {'round': round_number, 'map': fixture['name'], 'map_sha256': fixture['map_sha256'],
           'hero_control': hero_control, 'pid': pid, 'background_requested': background, 'battles': []}
    report['runs'].append(run)
    save(report, destination)
    try:
        if background:
            run['background_status'] = json.loads(check.command(
                'powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(check.GAME_UI),
                'background', '-GameProcessId', str(pid), '-ReturnFocusWindow', str(foreground),
                '-RestoreClip', '-ReturnClipLeft', str(original_clip.left),
                '-ReturnClipTop', str(original_clip.top), '-ReturnClipRight', str(original_clip.right),
                '-ReturnClipBottom', str(original_clip.bottom)))
            save(report, destination)
        if fixture['kind'] == 'authored_polygon':
            hero = report.get('research_hero') or 'Brem'
        else:
            names = check.control('heroes')['result'].split()
            player = int(check.control('eval', 'GetCurrentPlayer()')['result'])
            run['player'] = player
            hero = ''
            for name in names:
                if not re.fullmatch(r'[A-Za-z0-9_]{1,70}', name):
                    raise RuntimeError('Unexpected hero identifier in the test map')
                if int(check.control('eval', f"GetObjectOwner('{name}')")['result']) == player:
                    hero = name
                    break
            if not hero:
                raise RuntimeError('RMG map has no command-addressable starting hero')
        if not re.fullmatch(r'[A-Za-z0-9_]{1,70}', hero):
            raise RuntimeError('Unexpected hero identifier in the test map')
        run['hero'] = hero
        if report.get('research_hero'):
            player = int(check.control('eval', 'GetCurrentPlayer()')['result'])
            if int(check.control('eval', f"GetObjectOwner('{hero}')")['result']) != player:
                raise RuntimeError('Requested authored hero is not owned by the current player')
        run['hero_start'] = check.control('hero', hero)
        if report.get('research_hero_skills'):
            run['hero_skill_steps'] = []
            for skill in report['research_hero_skills']:
                before = int(check.control('eval', f"GetHeroSkillMastery('{hero}',{skill})")['result'])
                accepted = check.control('eval', f"(GiveHeroSkill('{hero}',{skill}) and 1 or 0)")['result']
                check.wait_for_control_queues()
                after = int(check.control('eval', f"GetHeroSkillMastery('{hero}',{skill})")['result'])
                run['hero_skill_steps'].append({'skill': skill, 'before_mastery': before,
                                              'accepted': accepted == '1', 'after_mastery': after})
                save(report, destination)
                if accepted != '1' or after <= before:
                    raise RuntimeError(f'Requested hero skill {skill} was not granted: {before}->{after}')
        hero_stats = check.control('eval', f"GetHeroStat('{hero}',1)..','..GetHeroStat('{hero}',2)"
                                   f"..','..(HasHeroSkill('{hero}',36) and 1 or 0)")['result']
        values = [int(value) for value in hero_stats.split(',')]
        run['known_hero_attack_defence'] = values[:2]
        run['known_hero_battle_frenzy'] = bool(values[2])
        if hero_control == 'custom':
            for creature, count in report['research_hero_army'].items():
                check.control('creature', hero, creature, '--count', str(count))
            if 'CREATURE_ANGEL' not in report['research_hero_army']:
                check.control('creature', hero, 'CREATURE_ANGEL', '--count', '0')
        elif hero_control == 'small':
            check.control('creature', hero, 'CREATURE_PEASANT', '--count', '1000')
            check.control('creature', hero, 'CREATURE_ANGEL', '--count', '0')
        if report.get('research_bear_rider_count') is not None:
            check.control('creature', hero, 'CREATURE_BEAR_RIDER', '--count',
                          str(report['research_bear_rider_count']))
        names = 'a,b,c,d,e,f,g'
        joined = "..','..".join(names.split(','))
        check.control('console', f"@local {names}=GetHeroCreaturesTypes('{hero}');"
                                 f"SetGameVar('__workshop_known_hero_types',''..{joined})")
        run['known_hero_types'] = check.control('eval', "GetGameVar('__workshop_known_hero_types')")['result']
        hero_types = [int(value) for value in run['known_hero_types'].split(',') if int(value) > 0]
        hero_counts_expression = "..','..".join(f"GetHeroCreatures('{hero}',{kind})" for kind in hero_types)
        hero_state_expression = "GetDate(DAY)..','.." + hero_counts_expression
        starting_state = [int(value) for value in check.control('eval', hero_state_expression)['result'].split(',')]
        starting_counts = starting_state[1:]
        if hero_control == 'custom':
            actual = {creature_names[kind]: count for kind, count in zip(hero_types, starting_counts)}
            if actual != report['research_hero_army']:
                raise RuntimeError('Custom hero army readback differs from requested control: ' + json.dumps(actual))
            run['hero_army_readback'] = actual
        run['starting_day'] = starting_state[0]
        previous_hero_level = run['hero_start']['level']
        records = install_policy_observer(pid)
        atb_address = install_initial_atb_observer(pid)
        factor_address = install_action_factor_observer(pid)
        split_address = install_split_observer(pid)
        spread_address = install_spread_decision_observer(pid)
        attempt_address = install_attempt_observer(pid, source_strength=report['mode'] == 'superadmin_source_research')
        for authored in fixture['packs']:
            pack = authored['name']
            current_state = [int(value) for value in check.control('eval', hero_state_expression)['result'].split(',')]
            current_counts = current_state[1:]
            restored_army = False
            for kind, current, starting in zip(hero_types, current_counts, starting_counts):
                if current != starting:
                    check.control('creature', hero, creature_names[kind], '--count', str(starting))
                    restored_army = True
            policy_records(pid, records, arm=True)
            initial_atb_records(pid, atb_address, arm=True)
            action_factor_records(pid, factor_address, arm=True)
            split_records(pid, split_address, arm=True)
            spread_decisions(pid, spread_address, arm=True)
            attempt_records(pid, attempt_address, arm=True)
            if restored_army:
                current_state = [int(value) for value in check.control('eval', hero_state_expression)['result'].split(',')]
            day = current_state[0]
            hero_counts = current_state[1:]
            known_hero_army = [{'type': kind, 'count': count} for kind, count in zip(hero_types, hero_counts)]
            approach = []
            if fixture['kind'] == 'tagged_universe_rmg':
                projection, approach = enter_generated_battle(pid, hero, authored, authored['public_count'],
                                                             allow_partial=report['mode'] == 'superadmin_source_research')
            else:
                check.control('interact', hero, pack)
                projection = check.wait_for_models(pid, authored['public_count'],
                                                   allow_partial=report['mode'] == 'superadmin_source_research')
            if projection['known_hero_attack'] != run['known_hero_attack_defence'][0]:
                raise RuntimeError('Native projection read a different public hero Attack than GetHeroStat')
            if projection['known_hero_battle_frenzy'] != run['known_hero_battle_frenzy']:
                raise RuntimeError('Native projection read a different public Battle Frenzy skill than HasHeroSkill')
            hidden_source = None
            if report['mode'] == 'superadmin_source_research':
                hidden_source = json.loads(check.command(str(check.LOADER), '--pid', str(pid),
                                                         '--dll', str(check.PLUGIN), '--admin-source-trace'))
                if not hidden_source['enabled'] or not hidden_source['source_stacks']:
                    raise RuntimeError('Explicit Superadmin source was unavailable before Start')
                hidden_source['owned_actor_inputs'] = json.loads(check.command(
                    str(check.LOADER), '--pid', str(pid), '--dll', str(check.PLUGIN), '--admin-input-trace'))
                kernel = probe.api()
                process = probe.checked(kernel.OpenProcess(0x1010, False, pid))
                try:
                    # Universe can patch these bytes after EXE loading. Freeze
                    # runtime inputs before Start, separately from the oracle.
                    hidden_source['runtime_atb_limit'] = struct.unpack('<f', probe.read(
                        kernel, process, 0xa740f7, 4))[0]
                    hidden_source['runtime_action_factor_constants'] = {
                        hex(address): struct.unpack('<f', probe.read(kernel, process, address, 4))[0]
                        for address in (0xe12f10, 0xe12f18, 0xe0a7e4, 0xe0be10, 0xe87cf0, 0xe0d4b0)}
                    hidden_source['runtime_support_code_hex'] = probe.read(
                        kernel, process, 0x8580e0, 0x2e0).hex()
                    hidden_source['runtime_split_strength_code_hex'] = probe.read(
                        kernel, process, 0x4e9b90, 0x36d).hex()
                    hidden_source['runtime_split_strength_settings_ready'] = bool(probe.read(
                        kernel, process, 0x10c5178, 1)[0])
                    hidden_source['runtime_split_strength_coefficient_bits'] = list(struct.unpack('<11I',
                        probe.read(kernel, process, 0x10c5480 + 0x250, 44)))
                    hidden_source['runtime_split_strength_constants'] = list(struct.unpack('<2I',
                        probe.read(kernel, process, 0xe0d608, 8))) + list(struct.unpack('<2I',
                        probe.read(kernel, process, 0xe12e00, 8)))
                    hidden_source['runtime_support_offsets'] = list(struct.unpack('<16i', probe.read(
                        kernel, process, 0xf757c8, 64)))
                    hidden_source['runtime_action_factor_code_hex'] = probe.read(
                        kernel, process, 0xbfb4b0, 0x3c0).hex()
                    world = hidden_source['forecast_world']
                    if world:
                        armies = struct.unpack('<2I', probe.read(kernel, process, world + 0x8c, 8))
                        army_snapshots = []
                        for army in armies:
                            table = struct.unpack('<I', probe.read(kernel, process, army, 4))[0]
                            vector_method = struct.unpack('<I', probe.read(kernel, process, table + 0x68, 4))[0]
                            if table != 0xe17bcc or vector_method != 0x4da5b0:
                                raise RuntimeError('Unsupported forecast-army layout')
                            begin, end = struct.unpack('<2I', probe.read(kernel, process, army + 0x28, 8))
                            if end < begin or (end - begin) % 4 or (end - begin) // 4 > 128:
                                raise RuntimeError('Invalid forecast-army source vector')
                            source_entries = []
                            for index in range((end - begin) // 4):
                                entry = struct.unpack('<I', probe.read(kernel, process, begin + index * 4, 4))[0]
                                primary, secondary = struct.unpack('<2I', probe.read(kernel, process, entry, 8))
                                offset = struct.unpack('<i', probe.read(kernel, process, secondary + 8, 4))[0]
                                combat = entry + 4 + offset
                                combat_table = struct.unpack('<I', probe.read(kernel, process, combat, 4))[0]
                                source_entries.append({'source_entry': entry, 'primary_vtable': primary,
                                                       'combat_interface': combat, 'combat_vtable': combat_table})
                            army_snapshots.append({'army_interface': army, 'army_vtable': table,
                                                   'unit_vector_method': vector_method,
                                                   'source_entries': source_entries,
                                                   'unit_vector_method_code_hex': probe.read(
                                                       kernel, process, vector_method, 48).hex()})
                        hidden_source['forecast_armies'] = army_snapshots
                finally:
                    kernel.CloseHandle(process)
            frozen_prediction = projection['footprints']
            run['battles'].append({'pack': pack, 'day': day, 'fixture': authored, 'approach': approach,
                                   'hidden_source_pre_start': hidden_source,
                                   'placement_paths_before_start': attempt_records(pid, attempt_address, paths=True),
                                   'source_strength_reference_before_start': attempt_records(pid, attempt_address, strengths=True),
                                   'initial_atb_calls_before_start': initial_atb_records(pid, atb_address),
                                   'split_rng_calls_before_start': initial_atb_records(pid, atb_address, integer=True),
                                   'action_factors_before_start': action_factor_records(pid, factor_address, stop=True),
                                   'known_hero_army_pre_start': known_hero_army,
                                   'prediction': frozen_prediction,
                                   'prediction_complete': projection.get('prediction_complete', True),
                                   'excluded_source_mask_pre_start': projection.get('excluded_source_mask', 0),
                                   'prediction_frozen_at_utc': datetime.now(timezone.utc).isoformat(),
                                   'prediction_sha256': hashlib.sha256(json.dumps(
                                       frozen_prediction, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
                                   'public_bands_pre_start': projection['public_bands'],
                                   'predicted_policy_pre_start': {'spread': projection['predicted_spread'],
                                                                  'defensive': projection['predicted_defensive'],
                                                                  'estimated_spread_denominator': projection['estimated_spread_denominator'],
                                                                  'known_hero_attack': projection['known_hero_attack'],
                                                                  'known_hero_battle_frenzy': projection['known_hero_battle_frenzy']},
                                   'full_match': False,
                                   'explanation': {'status': 'awaiting_start', 'reason': 'Frozen prediction saved before Start'}})
            save(report, destination)
            def preserve_observation(observation):
                battle = run['battles'][-1]
                battle['observation_captured_at_utc'] = datetime.now(timezone.utc).isoformat()
                battle['observed_after_start_before_cleanup'] = observation
                predicted_tuples = Counter((unit['type'], unit['quantity'], *unit['cell'])
                                           for unit in battle['prediction'])
                observed_tuples = Counter((unit['type'], unit.get('quantity', 0), *unit['cell'])
                                          for unit in observation['units'])
                battle['comparison_before_cleanup'] = {
                    'quantities_checked': hidden_source is not None,
                    'full_composition_match': hidden_source is not None and predicted_tuples == observed_tuples,
                    'predicted': len(battle['prediction']), 'actual': len(observation['units'])}
                battle['explanation'] = {'status': 'observation_saved',
                                         'reason': 'Actual cells captured after Start; cleanup/comparison pending'}
                save(report, destination)
            projection['hero_level_before_start'] = previous_hero_level
            outcome = check.complete_battle(pid, projection, hero=hero,
                                           creature_ids={name: kind for kind, name in enumerate(creature_names)},
                                           on_observation=preserve_observation)
            run['battles'][-1]['levelup_choices'] = outcome['levelup_choices']
            run['battles'][-1]['levelup_state_after_results'] = outcome.get('levelup_state_after_results')
            previous_hero_level = outcome['hero']['level']
            owned_after_start = None
            if hidden_source is not None:
                owned_after_start = json.loads(check.command(
                    str(check.LOADER), '--pid', str(pid), '--dll', str(check.PLUGIN), '--admin-input-trace'))
                before_inputs = hidden_source['owned_actor_inputs']
                if (before_inputs['rows'] != owned_after_start['rows']
                        or before_inputs['attack_generation'] != owned_after_start['attack_generation']
                        or before_inputs['core_supported_mask'] != owned_after_start['core_supported_mask']
                        or before_inputs['core_aggregate_words'] != owned_after_start['core_aggregate_words']
                        or before_inputs['hero_corrections'] != owned_after_start['hero_corrections']
                        or before_inputs['hero_correction_mask'] != owned_after_start['hero_correction_mask']
                        or before_inputs['auxiliary_inputs'] != owned_after_start['auxiliary_inputs']
                        or before_inputs['auxiliary_mask'] != owned_after_start['auxiliary_mask']
                        or before_inputs['strategy_words'] != owned_after_start['strategy_words']
                        or before_inputs['area_inputs'] != owned_after_start['area_inputs']
                        or before_inputs['area_policy_words'] != owned_after_start['area_policy_words']
                        or before_inputs['large_policy_words'] != owned_after_start['large_policy_words']
                        or before_inputs['area_input_overflow'] != owned_after_start['area_input_overflow']):
                    raise RuntimeError('Owned primitive inputs changed after the pre-Start freeze')
            if hidden_source is not None and any('quantity' not in unit for unit in outcome['observation']['units']):
                raise RuntimeError('Superadmin verification requires every after-Start creature quantity')
            policy = policy_records(pid, records)
            atb_calls = initial_atb_records(pid, atb_address)
            factors = action_factor_records(pid, factor_address)
            split = split_records(pid, split_address)
            spread, capability = spread_decisions(pid, spread_address)
            attempts = attempt_records(pid, attempt_address)
            comparison = outcome['comparison']
            predicted_cells = Counter(tuple(slot['cell']) for slot in projection['footprints'])
            actual_cells = Counter(tuple(unit['cell']) for unit in outcome['observation']['units'])
            comparison['exact_cell_matches'] = sum((predicted_cells & actual_cells).values())
            comparison['same_base_counts'] = (
                Counter(report['creature_families'].get(str(slot['type']), slot['type'])
                        for slot in projection['footprints'])
                == Counter(report['creature_families'].get(str(unit['type']), unit['type'])
                           for unit in outcome['observation']['units']))
            spatial_full = (comparison['predicted'] == comparison['actual'] == comparison['exact_cell_matches'])
            comparison['position_full_match'] = spatial_full
            comparison['quantities_checked'] = hidden_source is not None
            predicted_complete = Counter((slot['type'], slot['quantity'], *slot['cell']) for slot in frozen_prediction)
            observed_complete = Counter((unit['type'], unit.get('quantity', 0), *unit['cell'])
                                        for unit in outcome['observation']['units'])
            comparison['full_composition_match'] = (hidden_source is not None
                                                     and predicted_complete == observed_complete)
            full = comparison['full_composition_match'] if hidden_source is not None else spatial_full
            run['battles'][-1].update({
                                   'observation_captured_at_utc': datetime.now(timezone.utc).isoformat(),
                                   'return_runtime_state': outcome['return_runtime_state'],
                                   'observed': outcome['observation']['units'],
                                   'comparison': comparison, 'full_match': full, 'policy_after_start': policy,
                                   'initial_atb_calls_observed': atb_calls,
                                   'split_rng_calls_observed': initial_atb_records(pid, atb_address, integer=True),
                                   'action_factors_after_start': factors,
                                   'owned_actor_inputs_after_start': owned_after_start,
                                   'split_after_start': split, 'spread_decision_after_start': spread,
                                   'ranged_capability_after_start': capability,
                                   'placement_paths_after_start': attempt_records(pid, attempt_address, paths=True),
                                   'cell_attempts_after_start': attempts,
                                   'explanation': explain(projection, outcome['observation'], comparison, policy,
                                                         split, attempts,
                                                         attempt_records(pid, attempt_address, paths=True))})
            save(report, destination, completed_battle=run['battles'][-1])
            print(f"round {round_number}/{report['requested_rounds']} {fixture['name']} {pack}: "
                  f"cells {comparison['exact_cell_matches']}/{comparison['predicted']}", flush=True)
    except Exception as error:
        run['error'] = str(error)
        try:
            capture = json.loads(check.command('powershell', '-NoProfile', '-File', str(check.GAME_UI),
                                              '-Action', 'capture', '-GameProcessId', str(pid)))
            image = check.ROOT / f'.local/test-state/accuracy-failure-{pid}.png'
            shutil.copyfile(capture['Image'], image)
            run['failure_image'] = str(image)
        except Exception as diagnostic_error:
            run['failure_capture_error'] = str(diagnostic_error)
        try:
            run['failure_deployment_observation'] = check.control('deployment-observation')
            run['failure_runtime_state'] = check.control('runtime-state')
            run['failure_diagnostics'] = check.diagnostics(pid)
            if report['mode'] == 'superadmin_source_research':
                run['failure_owned_inputs'] = json.loads(check.command(
                    str(check.LOADER), '--pid', str(pid), '--dll', str(check.PLUGIN), '--admin-input-trace'))
                run['failure_source_trace'] = json.loads(check.command(
                    str(check.LOADER), '--pid', str(pid), '--dll', str(check.PLUGIN), '--admin-source-trace'))
        except Exception as diagnostic_error:
            run['failure_native_diagnostics_error'] = str(diagnostic_error)
        save(report, destination)
        raise
    finally:
        try:
            run['close'] = check.control('quit')
        except Exception as error:
            run['close_error'] = str(error)
            try:
                run['close'] = stop_hung_owned_sandbox(pid, created, check.ROOT)
            except Exception as cleanup_error:
                run['close'] = {'status': 'cleanup_unconfirmed', 'reason': str(cleanup_error)}
        save(report, destination)
    if run.get('close', {}).get('status') != 'game_closed':
        raise RuntimeError(f'Round {round_number} did not close normally')


def verify_report(path):
    report = json.loads(path.read_text(encoding='utf-8'))
    if report.get('mode') != 'normal_public_prediction':
        raise RuntimeError('Only a normal public-input campaign can pass the player pre-push gate')
    if check.DEVKIT != (MOD / 'devkit').resolve():
        raise RuntimeError('Final accuracy evidence must use the pinned devkit checkout')
    root = check.ROOT
    expected = {
        'source_sha256': MOD / 'src/preview_plugin.cpp',
        'driver_sha256': Path(__file__),
        'devkit_probe_sha256': check.PROBE,
        'devkit_control_sha256': check.CONTROL,
        'devkit_ui_sha256': check.GAME_UI,
        'plugin_sha256': root / '.local/test-game/bin/Heroes5Mods/WorkshopDeploymentPreview.dll',
        'loader_sha256': check.BUILD / 'workshop_preview_loader.exe',
        'game_exe_sha256': root / '.local/test-game/bin/H5_Game.exe',
    }
    for key, filename in expected.items():
        if report.get(key) != sha256(filename):
            raise RuntimeError(f'Accuracy evidence is stale or mismatched: {key}')
    if report['plugin_sha256'] != sha256(check.BUILD / 'WorkshopDeploymentPreview.dll'):
        raise RuntimeError('Accuracy evidence DLL differs from the current x86 Release build')
    fixtures = report.get('fixtures', {})
    schedule = ('polygon', 'rmg_a', 'rmg_b')
    runs = report.get('runs', [])
    if report.get('requested_rounds') != 10 or len(runs) != 10 or report.get('error'):
        raise RuntimeError('Accuracy evidence lacks ten completed map loads')
    for family, fixture in fixtures.items():
        map_file = root / '.local/test-game/Maps' / (fixture['name'] + '.h5m')
        if fixture['map_sha256'] != sha256(map_file):
            raise RuntimeError(f'Test map changed after the campaign: {family}')
        if fixture['kind'] == 'tagged_universe_rmg':
            source = root / '.local/test-game/Maps' / fixture['source_name']
            if fixture['source_sha256'] != sha256(source):
                raise RuntimeError(f'RMG source map changed after the campaign: {family}')
    total, full, mixed_total, mixed_full = 0, 0, 0, 0
    for index, run in enumerate(runs):
        fixture = fixtures[schedule[index % 3]]
        if run['map'] != fixture['name'] or run.get('close', {}).get('status') != 'game_closed':
            raise RuntimeError(f'Map load {index + 1} is missing or did not close normally')
        if run.get('background_requested') and (run.get('background_status') or {}).get('Status') != 'background_window':
            raise RuntimeError(f'Map load {index + 1} did not verify its requested background window')
        expected_names = [pack['name'] for pack in fixture['packs']]
        if [battle['pack'] for battle in run['battles']] != expected_names:
            raise RuntimeError(f'Map load {index + 1} does not contain all selected packs in order')
        for battle in run['battles']:
            predicted = Counter(tuple(slot['cell']) for slot in battle['prediction'])
            observed = Counter(tuple(unit['cell']) for unit in battle['observed'])
            exact = len(battle['prediction']) == len(battle['observed']) and predicted == observed
            if battle['full_match'] != exact or battle['comparison']['position_full_match'] != exact:
                raise RuntimeError(f"Inconsistent position comparison in {battle['pack']}")
            if not exact:
                explanation = battle['explanation']
                if explanation['status'] == 'pending_causal_reconstruction':
                    raise RuntimeError(f"Unexplained placement mismatch in {battle['pack']}")
                if explanation['status'] == 'composition_changed' and not explanation.get('observed_split'):
                    raise RuntimeError(f"Unexplained composition change in {battle['pack']}")
                if not explanation.get('reason'):
                    raise RuntimeError(f"Missing causal explanation in {battle['pack']}")
            full += exact
            total += 1
            if battle['fixture']['public_count'] > 1:
                mixed_total += 1
                mixed_full += exact
    accepted = mixed_total > 0 and mixed_full * 10 >= mixed_total * 7
    summary = report.get('acceptance', {})
    if (summary.get('mixed_full_matches'), summary.get('mixed_battles'),
        summary.get('full_matches'), summary.get('battles')) != (mixed_full, mixed_total, full, total):
        raise RuntimeError('Stored campaign totals differ from the recorded battles')
    if not accepted or summary.get('passed') != accepted:
        raise RuntimeError(f'Mixed-pack accuracy gate failed: {mixed_full}/{mixed_total}; require at least70%')
    print(f'Mixed-pack accuracy gate passed: {mixed_full}/{mixed_total} complete formations; '
          f'overall {full}/{total} across ten map loads')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rounds', type=int, default=10, choices=range(1, 11),
                        help='Use 1 for a development smoke; final acceptance requires all 10.')
    parser.add_argument('--map', choices=('polygon', 'rmg_a', 'rmg_b'),
                        help='Development smoke on one map family; final campaign rotates all three.')
    parser.add_argument('--only-pack', help='One named pack on each development round; excludes final acceptance.')
    parser.add_argument('--smoke-packs', type=int, choices=range(1, 65),
                        help='First N selected packs on one map for a development trace.')
    parser.add_argument('--hero-bear-count', type=int, choices=(1, 2),
                        help='RMG-B research control for public own Bear Rider quantity.')
    parser.add_argument('--hero-army', action='append', default=[], metavar='CREATURE:COUNT',
                        help='Repeat for an explicit authored-Polygon Superadmin hero control.')
    parser.add_argument('--hero', help='Existing owned hero name for a single Polygon Superadmin load.')
    parser.add_argument('--hero-skill', type=int, action='append', default=[], choices=range(1, 256),
                        metavar='ID', help='Grant skills in order; repeat base skills for mastery upgrades.')
    parser.add_argument('--verify-latest', action='store_true',
                        help='Read-only pre-push gate for the newest ten-load rotation JSON.')
    parser.add_argument('--superadmin-source', action='store_true',
                        help='Explicit developer-only pre-Start hidden source trace; no exact admin prediction yet.')
    parser.add_argument('--background', action='store_true',
                        help='Start without activation, then verify the sandbox window is off-screen.')
    args = parser.parse_args()
    if args.verify_latest:
        candidates = sorted((check.ROOT / '.local/test-state').glob('accuracy-campaign-*-rotation.json'))
        if not candidates:
            raise RuntimeError('No completed ten-map accuracy campaign; run this script without --verify-latest')
        verify_report(candidates[-1])
        return
    if args.only_pack and not args.map:
        parser.error('--only-pack requires an explicit --map')
    if args.smoke_packs and (args.rounds != 1 or not args.map or args.only_pack):
        parser.error('--smoke-packs requires --rounds 1, --map and no --only-pack')
    if args.hero_bear_count and (args.rounds != 1 or args.map != 'rmg_b'):
        parser.error('--hero-bear-count requires --rounds 1 --map rmg_b')
    if args.hero_army and (args.map != 'polygon' or not args.superadmin_source or args.hero_bear_count):
        parser.error('--hero-army requires --map polygon --superadmin-source and no bear override')
    if args.hero or args.hero_skill:
        if args.rounds != 1 or args.map != 'polygon' or not args.superadmin_source:
            parser.error('--hero/--hero-skill require --rounds 1 --map polygon --superadmin-source')
        if args.hero and not re.fullmatch(r'[A-Za-z0-9_]{1,70}', args.hero):
            parser.error('--hero requires a command-addressable hero identifier')
        if len(args.hero_skill) > 32:
            parser.error('--hero-skill allows at most 32 ordered grants')
    if args.superadmin_source:
        os.environ['H5_PREVIEW_SUPERADMIN'] = '1'
    if os.environ.get('H5_WORKSPACE') is None or os.environ.get('H5_PREVIEW_BUILD') is None:
        parser.error('Set H5_WORKSPACE and H5_PREVIEW_BUILD to the owned sandbox and x86 Release build')
    check.LOADER = check.BUILD / 'workshop_preview_loader.exe'
    check.PLUGIN = check.ROOT / '.local/test-game/bin/Heroes5Mods/WorkshopDeploymentPreview.dll'
    source = MOD / 'src/preview_plugin.cpp'
    game = check.ROOT / '.local/test-game/bin/H5_Game.exe'
    map_file = check.ROOT / '.local/test-game/Maps/WorkshopPolygon.h5m'
    manifest = json.loads((check.ROOT / '.local/test-state/test-map.json').read_text(encoding='utf-8'))
    if sha256(map_file) != manifest['sha256']:
        raise RuntimeError('Test map differs from the generated manifest')
    if not check.LOADER.is_file() or not check.PLUGIN.is_file():
        raise RuntimeError('Build/install the native plugin before this campaign')
    if sha256(check.PLUGIN) != sha256(check.BUILD / 'WorkshopDeploymentPreview.dll'):
        raise RuntimeError('Sandbox DLL differs from the tested x86 Release build')
    fixtures = {
        'polygon': {'name': 'WorkshopPolygon', 'kind': 'authored_polygon',
                    'map_sha256': sha256(map_file),
                    'packs': [{'name': f'pack_{index}', 'public_count': len(army), 'army': army}
                              for index, army in enumerate(manifest['packs'])]},
        'rmg_a': prepare_rmg_fixture(check.ROOT, '1231231.h5m', 'A', 'A11CE000-0000-4000-8000-000000000001'),
        'rmg_b': prepare_rmg_fixture(check.ROOT, '12312312.h5m', 'B', 'A11CE000-0000-4000-8000-000000000002'),
    }
    if args.only_pack:
        fixture = fixtures[args.map]
        fixture['packs'] = [pack for pack in fixture['packs'] if pack['name'] == args.only_pack]
        if len(fixture['packs']) != 1:
            parser.error('Requested pack is not in the selected fixture')
    if args.smoke_packs:
        fixture = fixtures[args.map]
        fixture['packs'] = fixture['packs'][:args.smoke_packs]
    families, creature_sources, creature_names = creature_families(
        check.ROOT / 'Heroes of Might and Magic 5 Tribes of the East/data')
    try:
        custom_hero_army = parse_hero_army(args.hero_army, creature_names)
    except ValueError as error:
        parser.error(str(error))
    report = {'schema': 1, 'mode': 'superadmin_source_research' if args.superadmin_source else 'normal_public_prediction',
              'acceptance_focus': 'mixed_packs',
              'manual_spread_override': args.superadmin_source and os.environ.get('H5_PREVIEW_SUPERADMIN_SPREAD') == '1',
              'research_bear_rider_count': args.hero_bear_count,
              'research_hero_army': custom_hero_army,
              'research_hero': args.hero,
              'research_hero_skills': args.hero_skill,
              'protocol': 'all selected packs once per map load; own hero army restored to its starting counts before each battle; ten fresh loads rotate polygon and two tagged Universe RMG maps',
              'fixtures': fixtures, 'game_exe_sha256': sha256(game),
              'creature_families': {str(kind): base for kind, base in families.items()},
              'creature_sources': creature_sources,
              'plugin_sha256': sha256(check.PLUGIN), 'source_sha256': sha256(source),
              'loader_sha256': sha256(check.LOADER),
              'devkit_probe_sha256': sha256(check.PROBE),
              'devkit_control_sha256': sha256(check.CONTROL),
              'devkit_ui_sha256': sha256(check.GAME_UI),
              'driver_sha256': sha256(Path(__file__)),
              'native_check_sha256': sha256(Path(check.__file__)), 'requested_rounds': args.rounds,
              'runs': [], 'acceptance': {'required_full_match_fraction': 1.0 if args.superadmin_source else 0.7,
                                        'passed': False}}
    suffix = (args.map or 'rotation') + ('-admin' if args.superadmin_source else '')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    destination = check.ROOT / '.local/test-state' / f'accuracy-campaign-{stamp}-{os.getpid()}-{suffix}.json'
    print(f'Accuracy report: {destination}', flush=True)
    save(report, destination)
    try:
        for round_number in range(1, args.rounds + 1):
            family = args.map or ('polygon', 'rmg_a', 'rmg_b')[(round_number - 1) % 3]
            run_map(round_number, fixtures[family], report, destination, creature_names, args.background)
    except Exception as error:
        report['error'] = str(error)
        save(report, destination)
        raise
    battles = [battle for run in report['runs'] for battle in run['battles']]
    full = sum(battle['full_match'] for battle in battles)
    mixed = [battle for battle in battles if battle['fixture']['public_count'] > 1]
    solo = [battle for battle in battles if battle['fixture']['public_count'] == 1]
    by_pack = {pack: {'full_matches': sum(b['full_match'] for b in battles if b['pack'] == pack),
                      'battles': sum(b['pack'] == pack for b in battles)}
               for pack in sorted({battle['pack'] for battle in battles})}
    by_map = {family: {'full_matches': sum(b['full_match'] for run in report['runs'] if run['map'] == fixture['name']
                                           for b in run['battles']),
                       'battles': sum(len(run['battles']) for run in report['runs'] if run['map'] == fixture['name'])}
              for family, fixture in fixtures.items()}
    report['acceptance'] = {'full_matches': full, 'battles': len(battles),
                            'required_full_match_fraction': 1.0 if args.superadmin_source else 0.7,
                            'mixed_full_matches': sum(battle['full_match'] for battle in mixed),
                            'mixed_battles': len(mixed),
                            'solo_full_matches': sum(battle['full_match'] for battle in solo),
                            'solo_battles': len(solo),
                            'by_pack': by_pack, 'by_map': by_map,
                            # Source-only Superadmin research does not yet predict
                            # final quantities, upgrades or RNG transformations.
                            # It must never inherit the ordinary spatial70% gate.
                            'passed': not args.superadmin_source
                                      and args.rounds == 10 and args.map is None and args.only_pack is None
                                      and args.smoke_packs is None
                                      and args.hero_bear_count is None
                                      and len(battles) == sum(len(fixtures[('polygon', 'rmg_a', 'rmg_b')[(index - 1) % 3]]['packs']) for index in range(1, 11))
                                      and len(mixed) > 0
                                      and sum(battle['full_match'] for battle in mixed) * 10 >= len(mixed) * 7}
    save(report, destination)
    print(json.dumps(report['acceptance'], ensure_ascii=False), flush=True)
    if (args.rounds == 10 and args.map is None and args.only_pack is None
            and args.smoke_packs is None and args.hero_bear_count is None
            and not report['acceptance']['passed']):
        if args.superadmin_source:
            raise RuntimeError('Superadmin source research is not complete100% prediction acceptance')
        raise RuntimeError('Mixed-pack full formation match rate is below 70% across the ten-map campaign')


if __name__ == '__main__':
    main()
