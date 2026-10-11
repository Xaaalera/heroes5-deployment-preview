import os
from pathlib import Path
import subprocess
import sys

MOD_ROOT = Path(__file__).resolve().parents[1]
DEVKIT = (MOD_ROOT / 'devkit').resolve()
if ((MOD_ROOT.parents[1] / 'scripts/sync-subrepos.ps1').is_file()
        and DEVKIT != (MOD_ROOT.parents[1] / 'devkit').resolve()):
    raise RuntimeError('Workshop requires the single canonical devkit; run scripts/sync-subrepos.ps1')
if not (DEVKIT / 'scripts/workspace.py').is_file():
    raise RuntimeError('Initialize pinned dependencies: git submodule update --init. Then follow README.md to link the shared Game API checkout.')
sys.path.insert(0, str(DEVKIT / 'scripts'))
WORKSPACE = Path(os.environ.get('H5_WORKSPACE') or MOD_ROOT).expanduser().resolve()
BUILD = Path(os.environ.get('H5_PREVIEW_BUILD') or MOD_ROOT / '.local/build/deployment-preview-native').resolve()


def vcvarsall():
    configured = os.environ.get('H5_VCVARSALL')
    if configured:
        return Path(configured)
    locator = Path(os.environ.get('ProgramFiles(x86)', '')) / 'Microsoft Visual Studio/Installer/vswhere.exe'
    if locator.is_file():
        result = subprocess.run([str(locator), '-latest', '-products', '*', '-requires',
                                 'Microsoft.VisualStudio.Component.VC.Tools.x86.x64', '-find',
                                 'VC/Auxiliary/Build/vcvarsall.bat'], capture_output=True, text=True, check=True)
        if result.stdout.strip():
            return Path(result.stdout.splitlines()[0])
    return MOD_ROOT / '__missing_vcvarsall__'


def preview_source():
    """Expand the canonical calculation header for existing native extraction fixtures."""
    source = (MOD_ROOT / "src/preview_plugin.cpp").read_text(encoding="utf-8")
    header = (MOD_ROOT / "src/placement_calculations.hpp").read_text(encoding="utf-8")
    body = header.split("namespace h5_preview {\n", 1)[1].rsplit("}\n#endif", 1)[0]
    calculations, actor_builder = body.split('// Actor aggregate reconstruction.\n', 1)
    body = calculations
    actor_builder = actor_builder.replace('h5::army::ActorInput', 'FrozenActorInput').replace(
        'h5::army::HeroCorrectionInput', 'FrozenHeroCorrection').replace(
        'h5::army::AuxiliaryPowerInput', 'FrozenAuxiliaryPower').replace(
        'count > PlacementActorInputCapacity', 'count > kActorInputCapacity')
    actor_builder = actor_builder.replace('h5::army::ActorProtectionCapacity', '0xa5b780u').replace(
        'h5::army::ActorProtectionFraction', '0xa5b89fu')
    actor_builder = actor_builder.replace('h5::army::ActorRunicDescriptorCount', '0xbfb3dbu').replace(
        'h5::army::ActorRunicAvailability', '0xbfb430u')
    source = source.replace('// Shared actor aggregate builder: placement_calculations.hpp.\n\n', actor_builder)
    inputs = (MOD_ROOT / "game-api/include/h5/source_strength.hpp").read_text(encoding="utf-8")
    definition = "struct SourceStrengthInput {" + inputs.split("struct SourceStrengthInput {", 1)[1].split("struct SourceStrengthSample {", 1)[0]
    body = body.replace("using SourceStrengthInput = h5::army::SourceStrengthInput;\n\n", definition)
    actors = (MOD_ROOT / 'game-api/include/h5/actor_input.hpp').read_text(encoding='utf-8')
    actor_definition = 'struct FrozenActorInput {' + actors.split('struct ActorInput {', 1)[1].split(
        'using ActorCategorySelector', 1)[0].replace('sizeof(ActorInput)', 'sizeof(FrozenActorInput)')
    source = source.replace('using FrozenActorInput = h5::army::ActorInput;\n', actor_definition)
    for legacy_name, shared_name in (('FrozenHeroCorrection', 'HeroCorrectionInput'),
                                     ('FrozenAuxiliaryPower', 'AuxiliaryPowerInput')):
        fields = actors.split('struct ' + shared_name + ' {', 1)[1].split('};', 1)[0]
        source = source.replace('using ' + legacy_name + ' = h5::army::' + shared_name + ';\n',
                                'struct ' + legacy_name + ' {' + fields + '};\n')
    protection = 'inline bool ReadActorProtectionInputs(' + actors.split(
        'inline bool ReadActorProtectionInputs(', 1)[1].split('enum class AuxiliaryReadResult', 1)[0]
    protection = protection.replace('const ActorInput&', 'const FrozenActorInput&').replace(
        'AuxiliaryPowerInput (&outputs)', 'FrozenAuxiliaryPower (&outputs)').replace(
        'ActorProtectionCapacity', '0xa5b780u').replace('ActorProtectionFraction', '0xa5b89fu')
    source = source.replace('void __cdecl CaptureSuperadminActorInput(', protection + '\nvoid __cdecl CaptureSuperadminActorInput(', 1)
    runic = 'inline bool ReadActorRunicInputs(' + actors.split('inline bool ReadActorRunicInputs(', 1)[1].split(
        'inline bool ReadActorProtectionInputs(', 1)[0]
    runic = runic.replace('const ActorInput&', 'const FrozenActorInput&').replace(
        'AuxiliaryPowerInput (&outputs)', 'FrozenAuxiliaryPower (&outputs)').replace(
        'ActorRunicInputCapacity', '257').replace('ActorRunicDescriptorCount', '0xbfb3dbu').replace(
        'ActorRunicAvailability', '0xbfb430u')
    source = source.replace('void __cdecl CaptureSuperadminActorInput(', runic + '\nvoid __cdecl CaptureSuperadminActorInput(', 1)
    source = source.replace('h5::army::AuxiliaryPowerInput runic[h5::army::ActorRunicInputCapacity]',
        'FrozenAuxiliaryPower runic[257]').replace('h5::army::ReadActorRunicInputs(', 'ReadActorRunicInputs(')
    source = source.replace('h5::army::AuxiliaryPowerInput protection[2]', 'FrozenAuxiliaryPower protection[2]').replace(
        'h5::army::ReadActorProtectionInputs(', 'ReadActorProtectionInputs(')
    actor_body = actors.split('    input.damage = damage;', 1)[1].split(
        '\n}\ninline void ReadActorInputFrame', 1)[0]
    actor_body = ('    input.damage = damage;' + actor_body).replace(
        'input.attackGeneration = generation;', 'input.attackGeneration = g_attackGeneration;').replace(
        'categorySelector(', 'SelectPlacementDamageCategory(')
    source = source.replace(
        '    h5::army::ReadActorInputValues(actor, aggregateIdentity, damage, selected, specialCategory,\n'
        '        static_cast<uint32_t>(g_attackGeneration), input, SelectPlacementDamageCategory);\n',
        actor_body + '\n')
    # Extraction fixtures have no production namespace. Resolve only capacity
    # references from the canonical header, retaining every calculation body.
    for name in ('PlacementActorInputCapacity', 'PlacementAuxiliaryInputCapacity', 'PlacementHeroCorrectionCapacity'):
        value = header.split('inline constexpr uint32_t ' + name + ' = ', 1)[1].split(';', 1)[0]
        source = source.replace('h5_preview::' + name, value)
        if name == 'PlacementAuxiliaryInputCapacity':
            source = source.replace('auxiliaryCount > ' + name, 'auxiliaryCount > ' + value)
        if name == 'PlacementHeroCorrectionCapacity':
            source = source.replace('correctionCount > ' + name, 'correctionCount > ' + value)
    return source.replace(
        "// Shared pure placement calculations: placement_calculations.hpp.\n\n", body
    ).replace('using namespace h5_preview;', '').replace('#include "placement_calculations.hpp"', '').replace(
        '#include "../game-api/include/h5/actor_input.hpp"', '')
