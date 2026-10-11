"""Optional x86-emulator check; never starts or attaches to the game."""
import importlib.util
import os
import hashlib
import json
from pathlib import Path
import random
import re
import subprocess
import struct
import sys
import tempfile
import unittest

try:
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
    from unicorn.x86_const import (UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_ECX,
                                  UC_X86_REG_EDX, UC_X86_REG_ESI, UC_X86_REG_EDI,
                                  UC_X86_REG_EBP, UC_X86_REG_ESP, UC_X86_REG_EIP, UC_X86_REG_EFLAGS)
except ImportError:
    Uc = None

try:
    import keystone
except ImportError:
    keystone = None

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tests'))
from preview_support import MOD_ROOT, DEVKIT, WORKSPACE, BUILD, vcvarsall, preview_source
sys.path.insert(0, str(DEVKIT / 'scripts'))
SPEC = importlib.util.spec_from_file_location('native_probe', DEVKIT / 'scripts/native-probe.py')
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)



class ComparisonTests(unittest.TestCase):
    def test_frozen_deployment_matching_and_observed_differences(self):
        if not vcvarsall().is_file():
            self.fail('MSVC is required for the player comparison acceptance check')
        driver = r'''#include "deployment_comparison.hpp"
#include <algorithm>
#include <cassert>
#include <iostream>
using namespace h5_preview;
int main() {
 ComparisonStack forecast[7]{{3,10,1,1,1},{3,20,1,1,2}};
 ComparisonStack actual[7]{forecast[1],forecast[0]};
 auto result=CompareDeployments(forecast,2,actual,2);
 assert(result.valid && result.exactCount==2 && result.positionMatchCount==2);
 assert(result.entries[0].actualIndex==1 && result.entries[1].actualIndex==0);
 // A tempting same-cell match must not steal the correct equal-count stack.
 actual[0]={3,20,1,1,1};actual[1]={3,10,1,1,3};
 result=CompareDeployments(forecast,2,actual,2);
 assert(result.entries[0].actualIndex==1 && result.entries[1].actualIndex==0);
 assert(result.exactCount==0 && !result.splitChanged && !result.totalsChanged);
 forecast[0]={3,30,1,1,1};actual[0]={3,10,1,1,1};actual[1]={3,20,1,1,3};
 result=CompareDeployments(forecast,1,actual,2);
 assert(result.valid && result.splitChanged && !result.totalsChanged && !result.typesChanged);
 assert(result.entryCount==2 && result.exactCount==0);
 forecast[0]={3,31,1,1,1};actual[0]={3,30,1,1,1};
 result=CompareDeployments(forecast,1,actual,1);
 assert(result.totalsChanged && !result.splitChanged);
 assert(result.entries[0].difference==DeploymentDifference::QuantityChanged);
 forecast[0].quantity=0;
 result=CompareDeployments(forecast,1,actual,1);
 assert(result.valid && !result.quantitiesKnown && !result.totalsChanged && !result.splitChanged);
 assert(result.exactCount==0 && result.positionMatchCount==1);
 assert(result.entries[0].difference==DeploymentDifference::PositionOnlyKnown);
 forecast[0]={3,30,2,1,1};
 result=CompareDeployments(forecast,1,actual,1);
 assert(result.positionMatchCount==0 && result.entries[0].difference==DeploymentDifference::Moved);
 actual[0].type=4;
 result=CompareDeployments(forecast,1,actual,1);
 assert(result.typesChanged && result.entryCount==2 && result.entries[0].difference==DeploymentDifference::Missing);
 assert(result.entries[1].difference==DeploymentDifference::Unpredicted);
 assert(!CompareDeployments(forecast,8,actual,1).valid);
 assert(!CompareDeployments(forecast,1,actual,0).valid);
 actual[0].quantity=0;assert(!CompareDeployments(forecast,1,actual,1).valid);
 actual[0].quantity=1;actual[0].x=-1;assert(!CompareDeployments(forecast,1,actual,1).valid);
 actual[0].x=1;
 result=CompareDeployments(nullptr,0,actual,1);
 assert(result.valid && result.entryCount==1 && !result.quantitiesKnown);
 std::array<unsigned,7> order{0,1,2,3,4,5,6};
 for(unsigned index=0;index<7;++index) forecast[index]={3+index%2,10+index%3,1,1,static_cast<int>(index)};
 unsigned permutations=0;
 do {
  for(unsigned index=0;index<7;++index) actual[index]=forecast[order[index]];
  result=CompareDeployments(forecast,7,actual,7);
  assert(result.valid && result.exactCount==7 && result.positionMatchCount==7);
  assert(!result.splitChanged && !result.totalsChanged && !result.typesChanged);
  ++permutations;
 } while(std::next_permutation(order.begin(),order.end()));
 assert(permutations==5040);
 // Full-reference explanations are admitted only for a complete exact pack.
 PlacementDecisionTrace trace{};
 trace.version=1;trace.placementGeneration=17;trace.count=7;trace.complete=1;
 for(unsigned index=0;index<7;++index) {
  const auto& stack=forecast[index];
  trace.records[index]={stack.type,stack.quantity,stack.footprint,index+1,0,0,
   stack.x,stack.y,0,10,PlacementDecisionRule::RankedRow,0,0};
 }
 std::reverse(actual,actual+7);
 auto reference=CompareReferenceDecisions(trace,actual,7);
 assert(reference.status==ReferenceDecisionStatus::MatchesFact);
 for(unsigned index=0;index<7;++index) {
  const auto& decision=trace.records[reference.decisionForActual[index]];
  assert(decision.quantity==actual[index].quantity && decision.y==actual[index].y);
 }
 ++actual[0].y;
 reference=CompareReferenceDecisions(trace,actual,7);
 assert(reference.status==ReferenceDecisionStatus::DisagreesWithFact);
 for(auto index:reference.decisionForActual) assert(index==-1);
 --actual[0].y;
 assert(CompareReferenceDecisions(trace,actual,6).status==ReferenceDecisionStatus::DisagreesWithFact);
 trace.complete=0;
 assert(CompareReferenceDecisions(trace,actual,7).status==ReferenceDecisionStatus::Unavailable);
 trace.complete=1;trace.records[0].order=2;
 assert(CompareReferenceDecisions(trace,actual,7).status==ReferenceDecisionStatus::Unavailable);
 trace.records[0].order=1;trace.records[0].rule=static_cast<PlacementDecisionRule>(7);
 assert(CompareReferenceDecisions(trace,actual,7).status==ReferenceDecisionStatus::Unavailable);
 trace.records[0].rule=PlacementDecisionRule::RankedRow;trace.records[0].phase=8;
 assert(CompareReferenceDecisions(trace,actual,7).status==ReferenceDecisionStatus::Unavailable);
 trace.records[0].phase=0;
 trace.records[0].rule=PlacementDecisionRule::RankedRow;trace.records[0].quantity=0;
 assert(CompareReferenceDecisions(trace,actual,7).status==ReferenceDecisionStatus::Unavailable);
 assert(CompareReferenceDecisions(trace,nullptr,7).status==ReferenceDecisionStatus::Unavailable);
 std::cout << "PASS: duplicates, unknown quantities, split/totals/types, malformed input, 5040 permutations\n";
}
'''
        with tempfile.TemporaryDirectory(prefix='h5-comparison-') as directory:
            temporary = Path(directory)
            (temporary / 'comparison.cpp').write_text(driver, encoding='utf-8')
            (temporary / 'build.cmd').write_text(
                f'@call "{vcvarsall()}" x86 >nul\n@if errorlevel 1 exit /b 1\n'
                f'@cl /nologo /EHsc /O2 /std:c++20 /I"{MOD_ROOT / "src"}" /Fe:comparison.exe comparison.cpp\n',
                encoding='utf-8')
            build = subprocess.run(['cmd', '/d', '/c', str(temporary / 'build.cmd')], cwd=temporary, capture_output=True)
            self.assertEqual(build.returncode, 0, build.stdout.decode(errors='replace') + build.stderr.decode(errors='replace'))
            result = subprocess.run([str(temporary / 'comparison.exe')], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stdout.decode(errors='replace') + result.stderr.decode(errors='replace'))


@unittest.skipIf(Uc is None, 'Unicorn is required for emulation checks')
class NativeTests(unittest.TestCase):
    def test_strategy_verifier_matches_army_and_lifetime_instead_of_policy_label(self):
        import copy
        specification = importlib.util.spec_from_file_location('policy_verifier', MOD_ROOT / 'scripts/check.py')
        verifier = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(verifier)
        report = {'generation': 7, 'strategy_generation': 7, 'failures': 0, 'overflow': 0,
                  'strategy_mask': 3, 'army_identities': [100, 200], 'strategies': [0, 1],
                  'events': [
                      {'kind': 'capability_input', 'army_identity': 100},
                      {'kind': 'capability_result', 'evaluation_identity': 10},
                      {'kind': 'decision', 'evaluation_identity': 10, 'defensive': 0},
                      {'kind': 'capability_input', 'army_identity': 200},
                      {'kind': 'capability_result', 'evaluation_identity': 20},
                      {'kind': 'decision', 'evaluation_identity': 20, 'defensive': 1}],
                  'policies': [{'side': 1, 'evaluation_identity': 10, 'events_seen': 3, 'defensive': 0}]}
        accepted = verifier.verify_policy_decisions(report)
        self.assertTrue(accepted['ok'])
        self.assertEqual(accepted['policies'][0]['army_index'], 0)
        self.assertEqual(accepted['policies'][0]['policy_label'], 1)
        self.assertFalse(accepted['goal_complete'])
        reused = copy.deepcopy(report)
        reused['events'] += [
            {'kind': 'capability_input', 'army_identity': 200},
            {'kind': 'capability_result', 'evaluation_identity': 10},
            {'kind': 'decision', 'evaluation_identity': 10, 'defensive': 1}]
        self.assertTrue(verifier.verify_policy_decisions(reused)['ok'], 'Future reuse cannot change the prior observation')
        mismatch = copy.deepcopy(report)
        mismatch['strategies'][0] = 1
        self.assertFalse(verifier.verify_policy_decisions(mismatch)['ok'])
        for mutation in ('stale', 'overflow', 'unknown_army', 'wrong_context', 'reversed_call', 'future_policy', 'missing_decision'):
            broken = copy.deepcopy(report)
            if mutation == 'stale': broken['strategy_generation'] = 6
            elif mutation == 'overflow': broken['overflow'] = 1
            elif mutation == 'unknown_army': broken['events'][0]['army_identity'] = 300
            elif mutation == 'wrong_context': broken['events'][1]['evaluation_identity'] = 30
            elif mutation == 'reversed_call': broken['events'][:2] = reversed(broken['events'][:2])
            elif mutation == 'future_policy': broken['policies'][0]['events_seen'] = 2
            else: broken['events'] = []
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                verifier.verify_policy_decisions(broken)

    def test_renderer_adapter_preserves_native_arguments_and_caller_guard(self):
        source = (MOD_ROOT / 'src/preview_plugin.cpp').read_text(encoding='utf-8')
        hook = '__declspec(naked) void RendererHook() {' + source.split(
            '__declspec(naked) void RendererHook() {', 1)[1].split(
            '__declspec(naked) void __stdcall UpdatePlacementHover(', 1)[0]
        # Replace only the final native continuation; exercise the production argument adapter.
        hook = hook.replace('        push ebp\n        mov ebp, esp\n        and esp, 0xfffffff8\n'
                            '        mov eax, 0x577016\n        jmp eax', '        ret 36')
        wrapper = 'void __stdcall RenderPlacementPreview(' + source.split(
            'void __stdcall RenderPlacementPreview(', 1)[1].split(
            'bool PlanReferencePlacement(', 1)[0]
        driver = r'''#include <cstdint>
#include <cassert>
uint32_t received[5]{};
void __stdcall RenderPlacementPreview(uint32_t owner, uint32_t caller, uint32_t root,
    uint32_t factory, uint32_t angle) { received[0]=owner;received[1]=caller;received[2]=root;received[3]=factory;received[4]=angle; }
HOOK
namespace guarded {
namespace h5 { namespace hooks { constexpr uint32_t PlacementRendererCaller = 0x57788f; } }
void* g_placementOwner=reinterpret_cast<void*>(0x1234);
uint32_t g_rendererRootArgument=0,g_rendererFactoryArgument=0,renderedOwner=0;
bool g_superadminEnabled=false,g_neutralTypesUnknown=false;
int g_plannedProjectionCount=3,g_renderedGeneration=-1,g_placementGeneration=4;
unsigned char g_outputStorage[1024]{};
void __stdcall RenderPlacementModels(uint32_t owner, uint32_t root, uint32_t factory, uint32_t angle) {
 renderedOwner=owner;g_rendererRootArgument=root;g_rendererFactoryArgument=factory;
 *reinterpret_cast<uint32_t*>(g_outputStorage+8+760)=angle+180u;
}
WRAPPER
}
int main() {
 uint32_t expectedCaller=0;
 __asm {
  lea eax, continuation
  mov expectedCaller,eax
  push edi
  mov edi,0x1234
  push 0x900
  push 0x800
  push 0x700
  push 0x600
  push 0x500
  push 0x400
  push 0x300
  push 0x200
  push 0x100
  call RendererHook
 continuation:
  pop edi
 }
 assert(received[0]==0x1234 && received[1]==expectedCaller);
 assert(received[2]==0x500 && received[3]==0x900 && received[4]==0x700);
 guarded::RenderPlacementPreview(0x9999,0x57788f,1,2,3);
 assert(!guarded::renderedOwner && !guarded::g_rendererRootArgument);
 guarded::RenderPlacementPreview(0x1234,0x111111,1,2,3);
 assert(!guarded::renderedOwner && !guarded::g_rendererRootArgument);
 guarded::RenderPlacementPreview(0x1234,0x57788f,1,2,30);
 assert(guarded::renderedOwner==0x1234 && guarded::g_rendererRootArgument==1 && guarded::g_rendererFactoryArgument==2);
 assert(*reinterpret_cast<uint32_t*>(guarded::g_outputStorage+8+760)==210);
 guarded::renderedOwner=0;guarded::g_neutralTypesUnknown=true;
 guarded::RenderPlacementPreview(0x1234,0x57788f,1,2,30);
 assert(!guarded::renderedOwner && !guarded::g_plannedProjectionCount);
 assert(guarded::g_renderedGeneration==guarded::g_placementGeneration);
 guarded::g_superadminEnabled=true;
 guarded::RenderPlacementPreview(0x1234,0x57788f,1,2,30);
 assert(guarded::renderedOwner==0x1234);
 return 0;
}
'''.replace('HOOK', hook).replace('WRAPPER', wrapper)
        with tempfile.TemporaryDirectory(prefix='xkit-renderer-adapter-') as directory:
            temporary = Path(directory)
            (temporary / 'adapter.cpp').write_text(driver, encoding='utf-8')
            admission = r'''#define H5_PREVIEW_MANAGED_SDK 1
#include "REFERENCE_SOURCE"
#include <cassert>
int main() {
 g_placementOwner=reinterpret_cast<void*>(0x1234);
 g_placementGeneration=g_renderedGeneration=17;
 g_rendererRootArgument=11;g_rendererFactoryArgument=22;
 *reinterpret_cast<uint32_t*>(g_outputStorage+8+760)=33;
 const LONG renders=g_renderCalls;
 RenderPlacementPreview(0x1234,h5::hooks::PlacementRendererCaller,111,222,333);
 assert(g_rendererRootArgument==11 && g_rendererFactoryArgument==22);
 assert(*reinterpret_cast<uint32_t*>(g_outputStorage+8+760)==33);
 assert(g_renderCalls==renders);
 *reinterpret_cast<uint32_t*>(g_outputStorage+8+496)=1;
 *reinterpret_cast<uint32_t*>(g_outputStorage+8+600)=2;
 *reinterpret_cast<uint32_t*>(g_outputStorage+8+640)=13;
 g_cell[0]=5;g_cell[1]=5;
 const int cell[2]{4,4};UpdatePlacementHover(77,cell);
 assert(g_hoverX==4 && g_hoverY==4 && HoveredProjectionSlot()==0);
 assert(*reinterpret_cast<uint32_t*>(g_outputStorage+8+508)==77);
 const int away[2]{0,0};UpdatePlacementHover(88,away);
 assert(HoveredProjectionSlot()==-1);
 int bounds[4]{11,22,33,44};uint32_t highlight[3]{};
 ApplyProjectionOutline(0x9999,highlight,bounds,false);
 assert(bounds[0]==11 && bounds[3]==44);
 return 0;
}
'''.replace('REFERENCE_SOURCE', (MOD_ROOT / 'src/preview_plugin.cpp').as_posix())
            (temporary / 'admission.cpp').write_text(admission, encoding='utf-8')
            (temporary / 'build.cmd').write_text(
                f'@call "{vcvarsall()}" x86 >nul\n@if errorlevel 1 exit /b 1\n'
                f'@cl /nologo /EHsc /O2 /std:c++20 /c /Fo:preview.obj "{MOD_ROOT / "src/preview_plugin.cpp"}"\n'
                '@if errorlevel 1 exit /b 1\n@cl /nologo /EHsc /O2 /std:c++20 /Fe:adapter.exe adapter.cpp\n'
                '@if errorlevel 1 exit /b 1\n@cl /nologo /EHsc /O2 /std:c++20 /Fe:admission.exe admission.cpp user32.lib\n', encoding='utf-8')
            build = subprocess.run(['cmd', '/d', '/c', str(temporary / 'build.cmd')], cwd=temporary, capture_output=True)
            self.assertEqual(build.returncode, 0, build.stdout.decode(errors='replace') + build.stderr.decode(errors='replace'))
            result = subprocess.run([str(temporary / 'adapter.exe')], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
            result = subprocess.run([str(temporary / 'admission.exe')], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))

    def test_managed_source_capture_keeps_unique_rows_and_freezes_at_start(self):
        """Execute the managed implementation: capacity, phases, reset and privacy."""
        if not vcvarsall().is_file():
            self.fail('MSVC x86 is required for the managed capture acceptance')
        source = (MOD_ROOT / 'src/preview_sdk.cpp').as_posix()
        driver = r'''
#include <cassert>
#include <cstring>
#include "MANAGED_SOURCE"
#include <cstdio>
#include <xmmintrin.h>
#undef assert
#define assert(condition) do { if (!(condition)) { fprintf(stderr, "Failed line %d: %s\n", __LINE__, #condition); return 1; } } while (false)
unsigned releasedModels=0,releasedCaches=0,releasedGlows=0;
void __fastcall ReleaseModelBoundary(uint32_t* holder,void*) { ++releasedModels;holder[0]=0; }
void __fastcall ReleaseCacheBoundary(uint32_t*,void*) { ++releasedCaches; }
void __fastcall ReleaseGlowBoundary(uint32_t*,void*,uint32_t) { ++releasedGlows; }
uint32_t fixtureDefinition[70]{};bool useFixtureDefinition=false;
const uint32_t* __fastcall PublicDefinitionBoundary(uint32_t) { return useFixtureDefinition ? fixtureDefinition : nullptr; }
unsigned char fixtureVisual[0xe8]{};bool useFixtureVisual=false;
uintptr_t fixtureLocalizedText[3]{};
bool fixtureTextThrows=false;
void* __fastcall CreatureVisualBoundary(void* reference) {
    return useFixtureVisual && reference==reinterpret_cast<unsigned char*>(fixtureDefinition)+0xf4 ? fixtureVisual : nullptr;
}
const uintptr_t* __fastcall CreatureTextBoundary(void* reference,void*) {
    _mm_setcsr(_mm_getcsr() ^ 0x6000);
    __asm { fldpi }
    if (fixtureTextThrows) { RaiseException(0xe0001236,0,0,nullptr); }
    return reference==fixtureVisual+0x44 ? fixtureLocalizedText : nullptr;
}
uint32_t* __fastcall EmptyTooltipBoundary(uint32_t* output,void*) { memset(output,0,16);return output; }
bool __fastcall ActiveScreenBoundary(void*) { return true; }
int scoutedMastery=0;
int __fastcall ScoutingMasteryBoundary(const void*,void*,int skill) { return skill==20 ? scoutedMastery : 0; }
uint32_t wornArtifactSet=0;bool fixtureCrownWorn=false;
const void* __fastcall WornArtifactSetBoundary(const void*,void*) { return &wornArtifactSet; }
bool __fastcall WornArtifactContainsBoundary(const void* set,void*,int artifact) {
    return set==&wornArtifactSet && artifact==12 && fixtureCrownWorn;
}
bool failReferenceRenderer=false;
void __stdcall ReferenceRendererBoundary(uint32_t,uint32_t,uint32_t,uint32_t) {
    if(!g_superadminEnabled || !g_referenceCalculationActive ||
        *reinterpret_cast<uint32_t*>(g_outputStorage+8+1364)!=1) { RaiseException(0xe0001235,0,0,nullptr); }
    g_publicCount=7;g_publicTypes[0]=999;g_publicBands[0]=99;
    g_cell[0]=31;g_position[0]=30;g_knownHeroAttack=999;
    g_root=reinterpret_cast<void*>(0x9999);g_grid=reinterpret_cast<void*>(0x8888);
    memset(g_outputStorage,0x5a,sizeof(g_outputStorage));
    auto& trace=*reinterpret_cast<h5_preview::PlacementDecisionTrace*>(g_outputStorage+8+976);
    trace={};trace.version=1;trace.placementGeneration=g_placementGeneration;trace.count=1;trace.complete=1;
    if(failReferenceRenderer) RaiseException(0xe0001234,0,0,nullptr);
}
int main() {
    // A payload replacement must preserve the precise calculation's inputs,
    // without treating capture admission as the forecast mode.
    assert(SetEnvironmentVariableW(L"H5_PREVIEW_SUPERADMIN",nullptr));
    assert(SetEnvironmentVariableW(L"H5_PREVIEW_SUPERADMIN_SPREAD",nullptr));
    assert(SetEnvironmentVariableW(L"H5_PREVIEW_NEUTRAL_TYPES",nullptr));
    ConfigureResearchMode(); assert(!g_neutralTypesUnknown);
    assert(SetNeutralTypeKnowledge(false));
    assert(!g_neutralTypesUnknown); // Changes apply to the next attack.
    ConfigureResearchMode(); assert(g_neutralTypesUnknown);
    assert(SetNeutralTypeKnowledge(true)); assert(g_neutralTypesUnknown);
    ConfigureResearchMode(); assert(!g_neutralTypesUnknown);
    assert(ParseDisclosedQuantity(L"40",2)==40);
    assert(ParseDisclosedQuantity(L"2147483647",10)==2147483647u);
    assert(!ParseDisclosedQuantity(L"2147483648",10));
    assert(!ParseDisclosedQuantity(L"1-4",3));
    assert(!ParseDisclosedQuantity(L"40?",3));
    assert(!ParseDisclosedQuantity(L"0",1));
    assert(!ParseDisclosedQuantity(nullptr,2));
    wchar_t publicRange[32]{};
    const wchar_t rangeLabel[]=L"word <color=#ed760e>(20-49)";
    assert(!CopyPublicQuantityLabel(rangeLabel,_countof(rangeLabel)-1,publicRange));
    assert(!wcscmp(publicRange,L"20-49"));
    assert(CopyPublicQuantityLabel(L"40",2,publicRange)==40 && !wcscmp(publicRange,L"40"));
    assert(!CopyPublicQuantityLabel(L"(49-20)",7,publicRange) && !publicRange[0]);
    assert(!CopyPublicQuantityLabel(L"<color=#123456>",15,publicRange) && !publicRange[0]);
    const wchar_t mergedRange[]=L"word (1-9)";
    assert(!CopyPublicQuantityLabel(mergedRange,_countof(mergedRange)-1,g_publicQuantityLabels[0]));
    g_publicBands[0]=1;
    assert(PublicQuantityEstimate(0,false)==5 && PublicQuantityEstimate(0,true)==1);
    assert(!g_publicKnownCounts[0]);
    const wchar_t upperRange[]=L"word (1000+)";
    assert(!CopyPublicQuantityLabel(upperRange,_countof(upperRange)-1,g_publicQuantityLabels[0]));
    assert(!wcscmp(g_publicQuantityLabels[0],L"1000+"));
    assert(PublicQuantityEstimate(0,false)==1000 && PublicQuantityEstimate(0,true)==1000);
    const wchar_t maximumRange[]=L"(2147483646-2147483647)";
    CopyPublicQuantityLabel(maximumRange,_countof(maximumRange)-1,g_publicQuantityLabels[0]);
    assert(PublicQuantityEstimate(0,false)==2147483647u);
    g_publicKnownCounts[0]=8;
    assert(PublicQuantityEstimate(0,false)==8 && PublicQuantityEstimate(0,true)==8);
    g_publicKnownCounts[0]=0;g_publicBands[0]=0;
    memset(g_publicQuantityLabels,0,sizeof(g_publicQuantityLabels));
    assert(!PublicQuantityEstimate(0,false) && !PublicQuantityEstimate(7,false));
    uint32_t publicModel[24]{};wchar_t exactPublicLabel[]=L"40";
    publicModel[0x24/4]=reinterpret_cast<uint32_t>(exactPublicLabel);
    publicModel[0x28/4]=reinterpret_cast<uint32_t>(exactPublicLabel+2);
    CapturePublicBands(publicModel);
    assert(g_publicKnownCounts[0]==40 && !g_publicKnownCounts[1] && !g_publicBands[0]);
    uint32_t publicRows[12]{};wchar_t secondPublicLabel[]=L"21";
    publicModel[0x50/4]=reinterpret_cast<uint32_t>(publicRows);
    publicModel[0x54/4]=reinterpret_cast<uint32_t>(publicRows+12);
    publicRows[3]=reinterpret_cast<uint32_t>(exactPublicLabel);
    publicRows[4]=reinterpret_cast<uint32_t>(exactPublicLabel+2);
    publicRows[9]=reinterpret_cast<uint32_t>(secondPublicLabel);
    publicRows[10]=reinterpret_cast<uint32_t>(secondPublicLabel+2);
    CapturePublicBands(publicModel);
    assert(g_publicKnownCounts[0]==40 && g_publicKnownCounts[1]==21 && !g_publicKnownCounts[2]);
    // Sorted records are not emitted slots: shooters can precede a large stack.
    wchar_t emittedLabels[7][32]{};
    g_publicCount=3;
    auto* sourceToSorted=reinterpret_cast<uint32_t*>(g_outputStorage+8+924);
    auto* emittedToSorted=reinterpret_cast<uint32_t*>(g_outputStorage+8+1368);
    *reinterpret_cast<uint32_t*>(g_outputStorage+8+496)=3;
    for(unsigned index=0;index<3;++index) sourceToSorted[index]=index;
    emittedToSorted[0]=1;emittedToSorted[1]=2;emittedToSorted[2]=0;
    wcscpy_s(g_publicQuantityLabels[0],L"5-9");
    wcscpy_s(g_publicQuantityLabels[1],L"20-49");
    wcscpy_s(g_publicQuantityLabels[2],L"1000+");
    CopyRenderedQuantityLabels(emittedLabels);
    assert(!wcscmp(emittedLabels[0],L"20-49") && !wcscmp(emittedLabels[1],L"1000+") && !wcscmp(emittedLabels[2],L"5-9"));
    // Equal creature types retain distinct original record identities.
    g_publicCount=2;g_publicTypes[0]=g_publicTypes[1]=3;
    *reinterpret_cast<uint32_t*>(g_outputStorage+8+496)=2;
    sourceToSorted[0]=1;sourceToSorted[1]=0;
    emittedToSorted[0]=1;emittedToSorted[1]=0;
    CopyRenderedQuantityLabels(emittedLabels);
    assert(!wcscmp(emittedLabels[0],L"5-9") && !wcscmp(emittedLabels[1],L"20-49") && !emittedLabels[2][0]);
    emittedToSorted[0]=7;CopyRenderedQuantityLabels(emittedLabels);
    assert(!emittedLabels[0][0] && !wcscmp(emittedLabels[1],L"20-49"));
    g_neutralTypesUnknown=true;CopyRenderedQuantityLabels(emittedLabels);
    assert(!emittedLabels[0][0] && !emittedLabels[1][0]);
    g_neutralTypesUnknown=false;g_publicCount=0;memset(g_outputStorage,0,sizeof(g_outputStorage));
    PublicPlannerState{}.Load();
    assert(!g_publicKnownCounts[0] && !g_publicKnownCounts[1]);
    static PreciseResearchState research{};
    g_superadminEnabled=true;g_attackGeneration=17;
    ResetSuperadminInputCapture();
    g_actorInputCount=256;g_actorInputs[255].type=57;g_actorInputs[255].quantity=80;
    g_superadminSourceCount=7;g_superadminSourceTypes[6]=65;g_superadminSourceCounts[6]=12;
    g_sourceStrengthCount=256;g_sourceStrengthInputs[255].ownWords[1]=123;
    g_sourceSplitSeed[1]=456;g_sourceComposition[23]=789;
    g_heroCorrectionCount=64;g_heroCorrections[63].firstScalar=19;
    g_auxiliaryInputCount=256;g_auxiliaryInputs[255].value=31;
    g_areaInputCount=128;g_areaInputs[127].spellWords[287]=43;
    g_strategyTrace[9]=59;g_protectiveCellCount=120;g_protectiveCells[119]=61;
    research.Save();
    assert(research.sequence==2);
    g_superadminEnabled=false;ResetSuperadminInputCapture();
    memset(g_actorInputs,0,sizeof(g_actorInputs));
    memset(g_superadminSourceCounts,0,sizeof(g_superadminSourceCounts));
    memset(g_areaInputs,0,sizeof(g_areaInputs));
    g_actorInputBusy=g_sourceStrengthBusy=g_areaInputBusy=true;
    assert(research.Load());
    assert(g_superadminEnabled && g_actorInputGeneration==17 && g_actorInputCount==256);
    assert(g_actorInputs[255].type==57 && g_actorInputs[255].quantity==80);
    assert(g_superadminSourceCount==7 && g_superadminSourceTypes[6]==65 && g_superadminSourceCounts[6]==12);
    assert(g_sourceStrengthCount==256 && g_sourceStrengthInputs[255].ownWords[1]==123);
    assert(g_sourceSplitSeed[1]==456 && g_sourceComposition[23]==789);
    assert(g_heroCorrectionCount==64 && g_heroCorrections[63].firstScalar==19);
    assert(g_auxiliaryInputCount==256 && g_auxiliaryInputs[255].value==31);
    assert(g_areaInputCount==128 && g_areaInputs[127].spellWords[287]==43);
    assert(g_strategyTrace[9]==59 && g_protectiveCellCount==120 && g_protectiveCells[119]==61);
    assert(!g_actorInputBusy && !g_sourceStrengthBusy && !g_areaInputBusy);
    research.version=4;g_superadminEnabled=false;
    assert(!research.Load() && !g_superadminEnabled);
    research.version=3;research.actorInputCount=h5_preview::PlacementActorInputCapacity+1;
    assert(!research.Load() && !g_superadminEnabled);
    research.actorInputCount=256;research.areaInputCount=129;
    assert(!research.Load() && !g_superadminEnabled);
    research.areaInputCount=128;research.enabled=false;
    assert(research.Load() && !g_superadminEnabled);
    ResetSuperadminInputCapture();
    struct Guarded { uint64_t before; PreviewInputCapture capture; uint64_t after; } guarded{};
    guarded.before = 0x1122334455667788; guarded.after = 0x8877665544332211;
    auto& capture = guarded.capture;
    h5::army::SourceStrengthSample sample{};
    sample.type = 13; sample.input.quantity = 10; sample.calculated = 1234;
    capture.Begin();
    capture.Append(1, 2, sample); capture.Append(1, 2, sample);
    assert(capture.count == 1 && capture.observations == 2 && !capture.overflow);
    assert(capture.sequence == 6);
    sample.phase = 1; capture.Append(1, 2, sample);
    capture.Append(3, 2, sample); capture.Append(3, 4, sample);
    assert(capture.count == 4);
    sample.input.quantity = 11; capture.Append(3, 4, sample);
    assert(capture.count == 5 && capture.records[0].sample.input.quantity == 10);
    capture.frozen = 1; capture.Append(5, 6, sample); assert(capture.count == 5);
    capture.Begin(); assert(capture.count == 0 && capture.generation == 2 && !capture.frozen);
    for (uint32_t index = 0; index < 256; ++index) { capture.Append(index, 2, sample); }
    assert(capture.count == 256 && !capture.overflow);
    capture.Append(255, 2, sample); assert(!capture.overflow);
    capture.Append(256, 2, sample); assert(capture.count == 256 && capture.overflow);
    assert((capture.sequence & 1) == 0);
    assert(guarded.before == 0x1122334455667788 && guarded.after == 0x8877665544332211);
    capture.Begin(); assert(!capture.overflow && capture.count == 0);

    auto* resident = static_cast<unsigned char*>(VirtualAlloc(nullptr,
        heroes5_sdk::ContextCapacity, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE));
    assert(resident);
    auto& projectionState = *reinterpret_cast<PublicProjectionState*>(resident + PublicProjectionOffset);
    projectionState.Save();
    assert(projectionState.research.version==0); // Ordinary mode keeps hidden inputs absent.
    g_superadminEnabled=true;g_actorInputCount=1;g_actorInputs[0].quantity=37;
    projectionState.Save();
    assert(projectionState.research.version==3 && projectionState.research.enabled);
    g_superadminEnabled=false;g_actorInputCount=0;g_actorInputs[0].quantity=0;
    projectionState.Load();
    assert(g_superadminEnabled && g_actorInputCount==1 && g_actorInputs[0].quantity==37);
    g_superadminEnabled=false;projectionState.Save();
    g_superadminEnabled=true;projectionState.Load();
    assert(!g_superadminEnabled && !projectionState.research.enabled);
    assert(g_actorInputCount==0 && g_superadminSourceCount==0 && !g_sourceSimpleLayout);
    assert(projectionState.research.actorInputCount==1 && projectionState.research.actorInputs[0].quantity==37);
    // Borrowing full inputs must restore every public output on success/failure.
    static PreciseResearchState referenceInputs{};
    referenceInputs.version=3;referenceInputs.actorInputGeneration=g_attackGeneration;
    referenceInputs.superadminSourceCount=1;referenceInputs.superadminSourceGeneration=g_placementGeneration;
    referenceInputs.superadminSourceTypes[0]=57;referenceInputs.superadminSourceCounts[0]=80;
    referenceInputs.superadminSourceKind=1;
    uint32_t scoutingOwner[40]{},scoutingHolder[5]{},scoutingHero[2]{},scoutingMethods[100]{};
    scoutingOwner[0x98/4]=reinterpret_cast<uint32_t>(scoutingHolder);
    scoutingHolder[0x10/4]=reinterpret_cast<uint32_t>(scoutingHero);
    scoutingHero[0]=reinterpret_cast<uint32_t>(scoutingMethods);
    scoutingMethods[0x174/4]=reinterpret_cast<uint32_t>(&ScoutingMasteryBoundary);
    g_publicCount=1;g_publicTypes[0]=3;g_publicKnownCounts[0]=0;
    assert(!ApplyScoutedSource(referenceInputs,scoutingOwner));
    assert(g_publicTypes[0]==3 && !g_publicKnownCounts[0]);
    scoutedMastery=1;assert(ApplyScoutedSource(referenceInputs,scoutingOwner));
    assert(g_publicTypes[0]==57 && g_publicKnownCounts[0]==80 && !wcscmp(g_publicQuantityLabels[0],L"80"));
    g_neutralTypesUnknown=true;g_publicTypes[0]=3;g_publicKnownCounts[0]=0;
    assert(!ApplyScoutedSource(referenceInputs,scoutingOwner));
    assert(g_publicTypes[0]==3 && !g_publicKnownCounts[0]);
    g_neutralTypesUnknown=false;
    assert(!g_superadminEnabled && g_actorInputCount==0);
    scoutedMastery=0;scoutingMethods[0x74/4]=reinterpret_cast<uint32_t>(&WornArtifactSetBoundary);
    void* containsPage=VirtualAlloc(reinterpret_cast<void*>(0x4b0000),65536,MEM_RESERVE|MEM_COMMIT,PAGE_EXECUTE_READWRITE);
    assert(containsPage==reinterpret_cast<void*>(0x4b0000));
    auto* containsBoundary=reinterpret_cast<unsigned char*>(0x4ba880);
    containsBoundary[0]=0xe9;
    *reinterpret_cast<int32_t*>(containsBoundary+1)=reinterpret_cast<unsigned char*>(&WornArtifactContainsBoundary)-containsBoundary-5;
    FlushInstructionCache(GetCurrentProcess(),containsBoundary,5);
    g_publicKnownCounts[0]=0;g_publicTypes[0]=3;
    assert(!ApplyScoutedSource(referenceInputs,scoutingOwner) && !g_publicKnownCounts[0]);
    fixtureCrownWorn=true;assert(ApplyScoutedSource(referenceInputs,scoutingOwner));
    assert(g_publicKnownCounts[0]==80 && g_publicTypes[0]==57);
    assert(VirtualFree(containsPage,0,MEM_RELEASE));
    scoutedMastery=1;
    referenceInputs.superadminSourceKind=2;assert(!ApplyScoutedSource(referenceInputs,scoutingOwner));
    referenceInputs.superadminSourceKind=1;referenceInputs.superadminSourceGeneration++;
    assert(!ApplyScoutedSource(referenceInputs,scoutingOwner));
    referenceInputs.superadminSourceGeneration--;
    g_placementOwner=reinterpret_cast<void*>(0x1234);g_publicCount=1;
    g_publicTypes[0]=3;g_publicBands[0]=5;g_cell[0]=13;g_position[0]=12;
    g_knownHeroAttack=0;g_root=reinterpret_cast<void*>(0x1111);g_grid=reinterpret_cast<void*>(0x2222);
    memset(g_outputStorage,0,sizeof(g_outputStorage));g_outputStorage[800]=0x77;
    unsigned char savedRenderer[5];auto* renderer=reinterpret_cast<unsigned char*>(&RenderPlacementModels);
    memcpy(savedRenderer,renderer,5);DWORD oldProtection=0;
    assert(VirtualProtect(renderer,5,PAGE_EXECUTE_READWRITE,&oldProtection));
    renderer[0]=0xe9;*reinterpret_cast<int32_t*>(renderer+1)=reinterpret_cast<unsigned char*>(&ReferenceRendererBoundary)-renderer-5;
    FlushInstructionCache(GetCurrentProcess(),renderer,5);
    g_neutralTypesUnknown=true;
    // Ordinary rendering must not enter the full-only boundary below.
    RenderPlacementPreview(0x1234,h5::hooks::PlacementRendererCaller,1,2,3);
    assert(g_outputStorage[800]==0x77 && g_publicTypes[0]==3);
    assert(g_renderedGeneration==g_placementGeneration && !g_plannedProjectionCount);
    for(unsigned failure=0;failure<2;++failure) {
        failReferenceRenderer=failure!=0;h5_preview::PlacementDecisionTrace decisions{};
        assert(PlanReferencePlacement(referenceInputs,0x1234,1,2,3,decisions)==!failReferenceRenderer);
        assert(!g_superadminEnabled && !g_referenceCalculationActive && g_actorInputCount==0);
        assert(g_publicCount==1 && g_publicTypes[0]==3 && g_publicBands[0]==5);
        assert(g_cell[0]==13 && g_position[0]==12 && g_knownHeroAttack==0);
        assert(g_root==reinterpret_cast<void*>(0x1111) && g_grid==reinterpret_cast<void*>(0x2222));
        assert(g_outputStorage[800]==0x77 && !*reinterpret_cast<uint32_t*>(g_outputStorage+8+1364));
        assert(decisions.complete==(failReferenceRenderer ? 0u : 1u));
        assert(g_neutralTypesUnknown); // Full reference preserves public policy.
    }
    g_neutralTypesUnknown=false;
    memcpy(renderer,savedRenderer,5);FlushInstructionCache(GetCurrentProcess(),renderer,5);
    DWORD ignoredProtection=0;assert(VirtualProtect(renderer,5,oldProtection,&ignoredProtection));
    g_placementOwner=nullptr;
    memset(&projectionState,0,sizeof(projectionState));ResetSuperadminInputCapture();
    projectionState.version = 1;projectionState.publicCount = 2;
    projectionState.publicTypes[0] = 13;projectionState.publicTypes[1] = 27;
    projectionState.models[2048] = 0x5a;projectionState.cells[0] = 12;
    projectionState.Load();
    assert(g_publicCount == 2 && g_publicTypes[1] == 27 && g_outputStorage[2048] == 0x5a && g_cell[0] == 12);
    *reinterpret_cast<uint32_t*>(g_outputStorage + 8 + 736) = reinterpret_cast<uint32_t>(g_cell);
    projectionState.Save();
    assert(*reinterpret_cast<uint32_t*>(projectionState.models + 8 + 736) == 0);
    memset(g_outputStorage,0,sizeof(g_outputStorage));g_publicCount=0;
    projectionState.Load();assert(g_publicCount==2 && g_outputStorage[2048]==0x5a);
    g_neutralTypesUnknown=true;projectionState.Save();g_neutralTypesUnknown=false;
    projectionState.Load();assert(g_neutralTypesUnknown);
    projectionState.publicPolicyVersion=0xf0505302u;
    projectionState.Load();assert(!g_neutralTypesUnknown && g_publicCount==2);
    memset(&projectionState,0,sizeof(projectionState));memset(g_outputStorage,0,sizeof(g_outputStorage));g_publicCount=0;
    assert(previewInterceptionApi.base.base.base.abi==heroes5_sdk::InterceptionPluginAbi);
    assert(previewInterceptionApi.interceptions.count==16 && previewInterceptionApi.base.hooks.count==14);
    PostStartVerification postStart{};
    heroes5_sdk::EngineContext postContext{};
    char unitName[]="CREATURE_ARCHER_1";
    uint32_t unitNameVector[2]{reinterpret_cast<uint32_t>(unitName),reinterpret_cast<uint32_t>(unitName)+sizeof(unitName)-1};
    int32_t positionFrame[9]{};positionFrame[7]=13;positionFrame[8]=6;
    postContext.registers.esi=reinterpret_cast<uint32_t>(unitNameVector);
    postContext.registers.ebp=postContext.registers.esi;
    postContext.registers.savedEsp=reinterpret_cast<uint32_t>(positionFrame)-4;
    postContext.registers.eax=40;
    ObservePostStartResult(31,postContext,postStart);assert(!postStart.positionCount);
    postStart.generation=8;postStart.armed=1;
    ObservePostStartResult(31,postContext,postStart);
    ObservePostStartResult(32,postContext,postStart);
    assert(postStart.positionCount==1 && postStart.quantityCount==1 && postStart.sequence==4);
    assert(postStart.positions[0].x==13 && postStart.positions[0].y==6);
    assert(postStart.quantities[0].quantity==40 && !strcmp(postStart.positions[0].name,unitName));
    positionFrame[7]=32;ObservePostStartResult(31,postContext,postStart);
    assert(postStart.failures==1 && postStart.positionCount==1);
    postContext.registers.eax=0;ObservePostStartResult(32,postContext,postStart);
    assert(postStart.failures==2 && postStart.quantityCount==1);
    postContext.registers.ebp=0;postContext.registers.eax=40;
    ObservePostStartResult(32,postContext,postStart);assert(postStart.failures==3);
    postContext.registers.ebp=reinterpret_cast<uint32_t>(unitNameVector);postContext.registers.eax=0x7fffffff;
    ObservePostStartResult(32,postContext,postStart);
    assert(postStart.quantityCount==2 && postStart.quantities[1].quantity==0x7fffffff);
    postContext.registers.eax=0x80000000;
    ObservePostStartResult(32,postContext,postStart);assert(postStart.failures==4);
    positionFrame[7]=13;
    for(unsigned index=0;index<7;++index) { ObservePostStartResult(31,postContext,postStart); }
    assert(postStart.positionCount==7 && postStart.overflow);
    const auto postSequence=postStart.sequence;
    postStart.Reset();
    assert(postStart.sequence==postSequence+2 && !postStart.armed && !postStart.generation);
    assert(!postStart.positionCount && !postStart.quantityCount && !postStart.positions[0].nameLength);
    assert(postStart.version==2 && !postStart.rosterObserved && !postStart.defenderCount);
    uint32_t rosterArguments[14]{};rosterArguments[0]=1;rosterArguments[7]=1;
    uint32_t rosterUnits[4]{};
    uint32_t rosterStack[12]{};
    rosterStack[0x14/4]=reinterpret_cast<uint32_t>(rosterUnits);
    rosterStack[0x18/4]=rosterStack[0x14/4]+sizeof(rosterUnits);
    rosterStack[0x20/4]=reinterpret_cast<uint32_t>(rosterArguments);
    rosterStack[0x24/4]=rosterStack[0x20/4]+sizeof(rosterArguments);
    heroes5_sdk::EngineContext rosterContext{};
    rosterContext.registers.savedEsp=reinterpret_cast<uint32_t>(rosterStack)-4;
    rosterContext.registers.ebp=1;
    postStart.armed=1;postStart.generation=9;
    ObservePostStartResult(33,rosterContext,postStart);
    assert(postStart.rosterObserved && postStart.defenderCount==4 && !postStart.rosterFailures);
    // Equal two-record prefixes cannot satisfy this independent four-unit roster.
    postStart.positionCount=postStart.quantityCount=2;
    assert(postStart.positionCount!=postStart.defenderCount);
    rosterArguments[0]=0;
    rosterStack[0x18/4]=rosterStack[0x14/4]+4;
    ObservePostStartResult(33,rosterContext,postStart);
    assert(postStart.defenderCount==4 && !postStart.rosterFailures); // attacker ignored
    rosterArguments[0]=1;rosterArguments[7]=2;rosterContext.registers.ebp=2;
    ObservePostStartResult(33,rosterContext,postStart);
    assert(postStart.defenderCount==4 && !postStart.rosterFailures); // war machines ignored
    rosterArguments[7]=1;rosterContext.registers.ebp=1;
    ObservePostStartResult(33,rosterContext,postStart);
    assert(postStart.rosterFailures==1); // a changing defender roster fails closed
    rosterStack[0x18/4]=rosterStack[0x14/4]+sizeof(rosterUnits)+1;
    ObservePostStartResult(33,rosterContext,postStart);
    assert(postStart.rosterFailures==2); // misaligned vector cannot certify completeness
    rosterStack[0x18/4]=rosterStack[0x14/4]+8*4;
    ObservePostStartResult(33,rosterContext,postStart);
    assert(postStart.rosterFailures==3); // defender capacity is bounded at seven
    rosterStack[0x18/4]=rosterStack[0x14/4]+sizeof(rosterUnits);
    rosterStack[0x20/4]=0;
    ObservePostStartResult(33,rosterContext,postStart);
    assert(postStart.rosterFailures==4);
    postStart.Reset();
    assert(!postStart.rosterObserved && !postStart.defenderCount && !postStart.rosterFailures);
    assert(previewInterceptionApi.interceptions.entries[0].policy.stackPopBytes==8);
    assert(previewInterceptionApi.interceptions.entries[1].readOnlyReentry==1);
    uint32_t decoration[1]{0xe2ff58}, ordinary[1]{0x123456}, ownTip[1]{0xe73c70}, otherTip[1]{0xe73c70};
    uint32_t controller[18]{},provider[20]{};
    controller[0x44/4]=reinterpret_cast<uint32_t>(provider);
    provider[2]=reinterpret_cast<uint32_t>(ownTip)+0x130;
    assert(ProjectionTooltipWindowIsDecoration(decoration,controller));
    assert(!ProjectionTooltipWindowIsDecoration(ordinary,controller));
    assert(ProjectionTooltipWindowIsDecoration(ownTip,controller));
    assert(!ProjectionTooltipWindowIsDecoration(otherTip,controller));
    projectionState.version=1;projectionState.uiVersion=1;projectionState.publicCount=1;
    projectionState.placementOwner=0x1234;
    *reinterpret_cast<uint32_t*>(projectionState.models+8+496)=1;
    *reinterpret_cast<uint32_t*>(projectionState.models+8+504)=13;
    uint32_t tooltipStack[4]{0,reinterpret_cast<uint32_t>(controller),0,0x6b8aad};
    uint32_t windowTable[1]{reinterpret_cast<uint32_t>(decoration)};
    uint32_t windowTableAddress=reinterpret_cast<uint32_t>(windowTable);
    heroes5_sdk::EngineInterceptionContext tooltipContext;
    tooltipContext.engine.residentData=resident;tooltipContext.engine.residentSchema=6;
    tooltipContext.engine.residentBytes=heroes5_sdk::ContextCapacity;tooltipContext.engine.hasRegisters=1;
    tooltipContext.engine.registers.savedEsp=reinterpret_cast<uint32_t>(tooltipStack)-4;
    tooltipContext.engine.registers.edi=reinterpret_cast<uint32_t>(&windowTableAddress)+0x68;
    assert(HandlePreviewInterception(17,tooltipContext) && tooltipContext.action==heroes5_sdk::EngineCallAction::Branch);
    assert(tooltipContext.engine.registers.eax==reinterpret_cast<uint32_t>(decoration));
    tooltipStack[3]=0x111111;tooltipContext.action=heroes5_sdk::EngineCallAction::Continue;
    assert(HandlePreviewInterception(17,tooltipContext) && tooltipContext.action==heroes5_sdk::EngineCallAction::Continue);
    tooltipStack[3]=0x6b8aad;tooltipContext.readOnly=1;projectionState.Load();
    static unsigned char retainedProjection[sizeof(PublicProjectionState)]{};
    memcpy(retainedProjection,&projectionState,sizeof(projectionState));
    assert(HandlePreviewInterception(17,tooltipContext) && tooltipContext.action==heroes5_sdk::EngineCallAction::Branch);
    assert(memcmp(retainedProjection,&projectionState,sizeof(projectionState))==0);
    assert(!HandlePreviewInterception(15,tooltipContext));
    tooltipContext.readOnly=0;tooltipContext.action=heroes5_sdk::EngineCallAction::Continue;
    projectionState.cells[0]=5;projectionState.cells[1]=5;projectionState.hoverX=4;projectionState.hoverY=4;
    *reinterpret_cast<uint32_t*>(projectionState.models+8+600)=2;
    *reinterpret_cast<uint32_t*>(projectionState.models+8+640)=13;
    uint32_t previewScreen[292]{},otherScreen[292]{},untouchedOutput[4]{};int cursor[2]{4,4};
    previewScreen[0]=otherScreen[0]=0xe1da84;previewScreen[0x488/4]=otherScreen[0x488/4]=0x1234;
    projectionState.projectionScreen=reinterpret_cast<uint32_t>(previewScreen);
    tooltipContext.engine.registers.ecx=reinterpret_cast<uint32_t>(otherScreen)+0x18c;
    tooltipStack[1]=reinterpret_cast<uint32_t>(untouchedOutput);tooltipStack[2]=reinterpret_cast<uint32_t>(cursor);
    assert(HandlePreviewInterception(15,tooltipContext) && tooltipContext.action==heroes5_sdk::EngineCallAction::Continue);
    assert(untouchedOutput[0]==0 && untouchedOutput[3]==0);
    assert(VirtualAlloc(reinterpret_cast<void*>(0x890000),65536,MEM_RESERVE|MEM_COMMIT,PAGE_EXECUTE_READWRITE));
    assert(VirtualAlloc(reinterpret_cast<void*>(0x540000),65536,MEM_RESERVE|MEM_COMMIT,PAGE_EXECUTE_READWRITE));
    const uintptr_t tooltipSites[]{0x89fbf0,0x54e440};
    const uintptr_t tooltipTargets[]{reinterpret_cast<uintptr_t>(&PublicDefinitionBoundary),reinterpret_cast<uintptr_t>(&EmptyTooltipBoundary)};
    for (unsigned index=0;index<2;++index) {
        auto* instruction=reinterpret_cast<unsigned char*>(tooltipSites[index]);instruction[0]=0xe9;
        const auto relative=static_cast<uint32_t>(tooltipTargets[index]-tooltipSites[index]-5);
        memcpy(instruction+1,&relative,4);assert(FlushInstructionCache(GetCurrentProcess(),instruction,5));
    }
    assert(VirtualAlloc(reinterpret_cast<void*>(0x20070000),65536,MEM_RESERVE|MEM_COMMIT,PAGE_EXECUTE_READWRITE));
    assert(VirtualAlloc(reinterpret_cast<void*>(0x20080000),65536,MEM_RESERVE|MEM_COMMIT,PAGE_EXECUTE_READWRITE));
    const uintptr_t nameSites[]{0x4bdad0,0x4c7430};
    const uintptr_t nameTargets[]{reinterpret_cast<uintptr_t>(&CreatureVisualBoundary),reinterpret_cast<uintptr_t>(&CreatureTextBoundary)};
    for(unsigned index=0;index<2;++index) {
        auto* instruction=reinterpret_cast<unsigned char*>(nameSites[index]);instruction[0]=0xe9;
        *reinterpret_cast<uint32_t*>(instruction+1)=nameTargets[index]-nameSites[index]-5;
        assert(FlushInstructionCache(GetCurrentProcess(),instruction,5));
    }
    wchar_t nativeName[]=L"\u041b\u0443\u0447\u043d\u0438\u043a\u0438";
    struct NameGuard { uint32_t prefix;wchar_t text[16];uint32_t suffix; } nameGuard{123,{},456};
    useFixtureDefinition=useFixtureVisual=true;
    fixtureLocalizedText[0]=reinterpret_cast<uintptr_t>(nativeName);
    fixtureLocalizedText[1]=reinterpret_cast<uintptr_t>(nativeName+_countof(nativeName)-1);
    uint16_t previousTop=0,followingTop=0;const unsigned previousMxcsr=_mm_getcsr();
    __asm { fnstsw previousTop }
    assert(h5::army::ReadCreatureDisplayName(3,nameGuard.text,16));
    __asm { fnstsw followingTop }
    assert(!wcscmp(nameGuard.text,nativeName) && nameGuard.prefix==123 && nameGuard.suffix==456);
    assert(_mm_getcsr()==previousMxcsr && (previousTop&0x3800)==(followingTop&0x3800));
    assert(!h5::army::ReadCreatureDisplayName(3,nameGuard.text,2) && !nameGuard.text[0]);
    fixtureLocalizedText[1]=fixtureLocalizedText[0]+1;
    assert(!h5::army::ReadCreatureDisplayName(3,nameGuard.text,16));
    assert(!h5::army::ReadCreatureDisplayName(0,nameGuard.text,16));
    assert(!h5::army::ReadCreatureDisplayName(512,nameGuard.text,16));
    assert(!h5::army::ReadCreatureDisplayName(3,nullptr,16));
    fixtureTextThrows=true;
    assert(!h5::army::ReadCreatureDisplayName(3,nameGuard.text,16) && !nameGuard.text[0]);
    fixtureTextThrows=false;
    __asm { fnstsw followingTop }
    assert(_mm_getcsr()==previousMxcsr && (previousTop&0x3800)==(followingTop&0x3800));
    useFixtureDefinition=useFixtureVisual=false;
    uint32_t cachedTooltip[3]{0,0,1};
    *reinterpret_cast<uint32_t*>(projectionState.models+8+700)=reinterpret_cast<uint32_t>(cachedTooltip);
    *reinterpret_cast<uint32_t*>(projectionState.models+8+716)=13;
    tooltipContext.engine.registers.ecx=reinterpret_cast<uint32_t>(previewScreen);
    assert(HandlePreviewInterception(15,tooltipContext) && tooltipContext.action==heroes5_sdk::EngineCallAction::Continue);
    tooltipContext.engine.registers.ecx=reinterpret_cast<uint32_t>(previewScreen)+0x18c;
    assert(HandlePreviewInterception(15,tooltipContext) && tooltipContext.action==heroes5_sdk::EngineCallAction::ReturnEax);
    assert(tooltipContext.result==reinterpret_cast<uint32_t>(untouchedOutput));
    assert(untouchedOutput[3]==reinterpret_cast<uint32_t>(cachedTooltip) && cachedTooltip[2]==2);
    uint32_t upgrades[2]{14,15};useFixtureDefinition=true;
    fixtureDefinition[0x104/4]=reinterpret_cast<uint32_t>(upgrades);
    fixtureDefinition[0x108/4]=reinterpret_cast<uint32_t>(upgrades+2);
    provider[0]=0xe34b74;provider[3]=reinterpret_cast<uint32_t>(cachedTooltip);
    controller[0x10/4]=reinterpret_cast<uint32_t>(previewScreen)+0x18c;
    tooltipStack[1]=reinterpret_cast<uint32_t>(controller);tooltipStack[3]=0x6b8aad;
    tooltipContext.action=heroes5_sdk::EngineCallAction::Continue;
    assert(HandlePreviewInterception(17,tooltipContext));
    assert(projectionState.uiVersion==4 && projectionState.tooltipController==reinterpret_cast<uint32_t>(controller));
    tooltipContext.engine.registers.ecx=reinterpret_cast<uint32_t>(provider);
    tooltipContext.action=heroes5_sdk::EngineCallAction::Continue;
    assert(HandlePreviewInterception(20,tooltipContext) && provider[4]==1);
    assert(tooltipContext.action==heroes5_sdk::EngineCallAction::Continue);
    provider[4]=0;tooltipContext.readOnly=1;
    assert(!HandlePreviewInterception(20,tooltipContext) && !provider[4]);tooltipContext.readOnly=0;
    controller[0x10/4]=reinterpret_cast<uint32_t>(otherScreen)+0x18c;
    assert(HandlePreviewInterception(20,tooltipContext) && !provider[4]);
    assert(HandlePreviewInterception(21,tooltipContext) && !provider[4]);
    assert(projectionState.tooltipChoice[0]==0);
    controller[0x10/4]=reinterpret_cast<uint32_t>(previewScreen)+0x18c;
    uint32_t foreignProvider[20]{0xe34b74};foreignProvider[3]=reinterpret_cast<uint32_t>(cachedTooltip);
    tooltipContext.engine.registers.ecx=reinterpret_cast<uint32_t>(foreignProvider);
    assert(HandlePreviewInterception(20,tooltipContext) && !foreignProvider[4]);
    assert(HandlePreviewInterception(21,tooltipContext) && !foreignProvider[4]);
    uint32_t rotatorReferenceOffsets[3]{0,12,12};
    uint32_t ownedRotator[10]{0xe4046c},foreignRotator[10]{0xe4046c};
    ownedRotator[1]=reinterpret_cast<uint32_t>(rotatorReferenceOffsets);ownedRotator[6]=1;
    projectionState.Load();BindProjectionDetailsRotator(ownedRotator,0,true);
    assert(ownedRotator[6]==2 && g_detailsRotatorOwned);
    BindProjectionDetailsRotator(ownedRotator,0,true);assert(ownedRotator[6]==2);
    projectionState.Save();
    tooltipContext.engine.callSite=h5::hooks::ProjectionDetailsCanRotate.address;
    tooltipContext.engine.registers.esi=reinterpret_cast<uint32_t>(ownedRotator);
    tooltipContext.readOnly=1;tooltipContext.action=heroes5_sdk::EngineCallAction::Continue;
    static unsigned char readonlyDetails[sizeof(PublicProjectionState)]{};
    memcpy(readonlyDetails,&projectionState,sizeof(projectionState));
    assert(HandlePreviewInterception(22,tooltipContext) && tooltipContext.action==heroes5_sdk::EngineCallAction::Branch);
    assert(tooltipContext.engine.registers.eax==1 && tooltipContext.engine.registers.ecx==reinterpret_cast<uint32_t>(ownedRotator));
    assert(memcmp(readonlyDetails,&projectionState,sizeof(projectionState))==0);
    auto* managedMethods=reinterpret_cast<uint32_t*>(resident+DetailsNativeMethodsOffset);
    memcpy(managedMethods,h5::hooks::DetailsRotatorMethods,64);
    managedMethods[5]=h5::hooks::DetailsRotationAvailable.address;
    ownedRotator[0]=foreignRotator[0]=reinterpret_cast<uint32_t>(managedMethods+1);
    tooltipContext.action=heroes5_sdk::EngineCallAction::Continue;
    assert(HandlePreviewInterception(22,tooltipContext) && tooltipContext.action==heroes5_sdk::EngineCallAction::Branch);
    assert(tooltipContext.engine.registers.eax==1);
    assert(!HandlePreviewInterception(23,tooltipContext));
    tooltipContext.engine.registers.esi=reinterpret_cast<uint32_t>(foreignRotator);
    tooltipContext.action=heroes5_sdk::EngineCallAction::Continue;
    assert(HandlePreviewInterception(22,tooltipContext) && tooltipContext.action==heroes5_sdk::EngineCallAction::Continue);
    tooltipContext.engine.registers.esi=reinterpret_cast<uint32_t>(ownedRotator);tooltipContext.engine.callSite=1;
    assert(HandlePreviewInterception(22,tooltipContext) && tooltipContext.action==heroes5_sdk::EngineCallAction::Continue);
    ReleaseProjectionDetailsRotator();assert(ownedRotator[6]==1 && !g_detailsRotatorOwned);
    assert(ownedRotator[0]==0xe4046c && foreignRotator[0]==reinterpret_cast<uint32_t>(managedMethods+1));
    ReleaseProjectionDetailsRotator();assert(ownedRotator[6]==1);
    projectionState.Save();tooltipContext.readOnly=0;
    useFixtureDefinition=false;
    assert(VirtualFree(reinterpret_cast<void*>(0x890000),0,MEM_RELEASE));
    assert(VirtualFree(reinterpret_cast<void*>(0x540000),0,MEM_RELEASE));
    memset(&projectionState,0,sizeof(projectionState));memset(g_outputStorage,0,sizeof(g_outputStorage));g_publicCount=0;
    ResetProjectionTooltipChoices();
    heroes5_sdk::EngineContext finalContext;
    finalContext.residentSchema=6;finalContext.residentBytes=heroes5_sdk::ContextCapacity;finalContext.residentData=resident;
    assert(!Heroes5PluginFinalize(&finalContext));
    finalContext.window=CreateWindowExW(0,L"STATIC",L"Isolated predictor cleanup",0,0,0,1,1,nullptr,nullptr,GetModuleHandleW(nullptr),nullptr);
    assert(finalContext.window);
    assert(VirtualAlloc(reinterpret_cast<void*>(0x20050000),65536,MEM_RESERVE|MEM_COMMIT,PAGE_EXECUTE_READWRITE));
    auto* activeInstruction=reinterpret_cast<unsigned char*>(0x20059e10);activeInstruction[0]=0xe9;
    const auto activeRelative=static_cast<uint32_t>(reinterpret_cast<uintptr_t>(&ActiveScreenBoundary)-0x20059e10-5);
    memcpy(activeInstruction+1,&activeRelative,4);assert(FlushInstructionCache(GetCurrentProcess(),activeInstruction,5));
    projectionState.version=1;projectionState.uiVersion=1;projectionState.publicCount=1;
    projectionState.placementOwner=0x1234;projectionState.projectionScreen=reinterpret_cast<uint32_t>(previewScreen);
    projectionState.cells[0]=5;projectionState.cells[1]=5;projectionState.hoverX=4;projectionState.hoverY=4;
    *reinterpret_cast<uint32_t*>(projectionState.models+8+496)=1;
    *reinterpret_cast<uint32_t*>(projectionState.models+8+504)=13;
    *reinterpret_cast<uint32_t*>(projectionState.models+8+600)=2;
    *reinterpret_cast<uint32_t*>(projectionState.models+8+640)=13;
    heroes5_sdk::WindowInputContext input;input.engine=finalContext;input.message=WM_LBUTTONDBLCLK;
    input.lparam=MAKELPARAM(120,230);
    assert(Heroes5PluginWindowInput(&input));
    assert(projectionState.uiVersion==4 && projectionState.detailsSlot==0 && projectionState.detailsPoint[0]==120 && projectionState.detailsPoint[1]==230);
    g_detailsSlot=-1;projectionState.Load();assert(g_detailsSlot==0 && g_detailsGeneration==projectionState.placementGeneration);
    auto* retainedMethods=reinterpret_cast<uint32_t*>(resident+DetailsNativeMethodsOffset);
    memcpy(retainedMethods,h5::hooks::DetailsRotatorMethods,64);
    retainedMethods[5]=h5::hooks::DetailsRotationAvailable.address;
    assert(EnsurePreviewStorage(finalContext) && g_detailsNativeMethods==retainedMethods+1);
    BindProjectionDetailsRotator(ownedRotator,0,true);
    ownedRotator[0]=reinterpret_cast<uint32_t>(g_detailsNativeMethods);
    projectionState.Save();
    assert(Heroes5PluginPrepareReplace(&finalContext));
    assert(projectionState.projectionScreen==reinterpret_cast<uint32_t>(previewScreen));
    assert(!projectionState.detailsRotatorOwned && ownedRotator[6]==1 && ownedRotator[0]==0xe4046c);
    assert(retainedMethods[5]==h5::hooks::DetailsRotationAvailable.address);
    assert(Heroes5PluginWindowInput(&input) && projectionState.detailsSlot==0);
    input.version=2;assert(!Heroes5PluginWindowInput(&input));
    assert(VirtualFree(reinterpret_cast<void*>(0x20050000),0,MEM_RELEASE));
    projectionState.version=1;projectionState.uiVersion=1;projectionState.publicCount=1;
    projectionState.placementOwner=0x1234;projectionState.root=0x5678;projectionState.grid=0x9abc;
    projectionState.projectionScreen=0x1234;projectionState.tooltipClickSlot=2;projectionState.tooltipChoice[2]=1;
    assert(VirtualAlloc(reinterpret_cast<void*>(0x570000),65536,MEM_RESERVE|MEM_COMMIT,PAGE_EXECUTE_READWRITE));
    assert(VirtualAlloc(reinterpret_cast<void*>(0x8c0000),65536,MEM_RESERVE|MEM_COMMIT,PAGE_EXECUTE_READWRITE));
    const uintptr_t boundarySites[]{0x576b40,0x8c6150,0x8c61d0};
    const uintptr_t boundaryTargets[]{reinterpret_cast<uintptr_t>(&ReleaseModelBoundary),
        reinterpret_cast<uintptr_t>(&ReleaseCacheBoundary),reinterpret_cast<uintptr_t>(&ReleaseGlowBoundary)};
    for (unsigned index=0;index<3;++index) {
        auto* instruction=reinterpret_cast<unsigned char*>(boundarySites[index]);instruction[0]=0xe9;
        const auto relative=static_cast<uint32_t>(boundaryTargets[index]-boundarySites[index]-5);
        memcpy(instruction+1,&relative,4);assert(FlushInstructionCache(GetCurrentProcess(),instruction,5));
    }
    uint32_t cacheObject[3]{0,0,1},glowNode[2]{0,1},glowColor[2]{0,1};
    *reinterpret_cast<uint32_t*>(projectionState.models+8+728)=0x1234;
    *reinterpret_cast<uint32_t*>(projectionState.models+8+700)=reinterpret_cast<uint32_t>(cacheObject);
    *reinterpret_cast<uint32_t*>(projectionState.models+8+716)=13;
    *reinterpret_cast<uint32_t*>(projectionState.models+8+496)=1;
    projectionState.glows[0].node=glowNode;projectionState.glows[0].color=glowColor;
    assert(Heroes5PluginFinalize(&finalContext));
    assert(releasedModels==7 && releasedCaches==1 && releasedGlows==2 && cacheObject[2]==0);
    assert(!projectionState.glows[0].node && !projectionState.glows[0].color);
    assert(!*reinterpret_cast<uint32_t*>(projectionState.models+8+700));
    assert(!*reinterpret_cast<uint32_t*>(projectionState.models+8+728));
    assert(!projectionState.publicCount && !projectionState.placementOwner && !projectionState.root && !projectionState.grid);
    assert(!projectionState.projectionScreen && projectionState.tooltipClickSlot==-1 && !projectionState.tooltipChoice[2]);
    assert(Heroes5PluginFinalize(&finalContext));
    assert(releasedModels==7 && releasedCaches==1 && releasedGlows==2);
    assert(VirtualFree(reinterpret_cast<void*>(0x570000),0,MEM_RELEASE));
    assert(VirtualFree(reinterpret_cast<void*>(0x8c0000),0,MEM_RELEASE));
    assert(DestroyWindow(finalContext.window));
    PreviewSessionState state{}; heroes5_sdk::EngineContext context{};
    context.residentSchema = 6; context.residentBytes = heroes5_sdk::ContextCapacity;
    context.residentData = resident; context.hasRegisters = 1;
    uint32_t result = 99;
    auto& journal = *reinterpret_cast<PreviewInputCapture*>(resident + 8192);
    memset(resident + 4096, 0xa5, sizeof(sample));
    assert(DispatchPreview(12, reinterpret_cast<uint32_t>(&context), &state, sizeof(state), &result));
    assert(journal.count == 0 && resident[4096] == 0xa5);
    assert(DispatchPreview(18, 1, &state, sizeof(state), &result) && result == 1);
    assert(DispatchPreview(3, reinterpret_cast<uint32_t>(&context), &state, sizeof(state), &result));
    assert(DispatchPreview(12, reinterpret_cast<uint32_t>(&context), &state, sizeof(state), &result));
    assert(journal.count == 1 && journal.records[0].sample.unsupported == 2);
    uint32_t stack[13]{};
    stack[10] = 55; stack[12] = 0x123;
    context.registers.savedEsp = reinterpret_cast<uint32_t>(stack) - 4;
    context.registers.edi = 88; context.registers.ebp = 77;
    assert(DispatchPreview(9, reinterpret_cast<uint32_t>(&context), &state, sizeof(state), &result));
    assert(journal.actorCount == 1 && !journal.actorOverflow);
    assert(journal.actors[0].unsupported == 1 && journal.actors[0].damage == 77);
    assert(journal.actors[0].aggregateIdentity == 88 && journal.actors[0].specialCategory == 0x23);
    assert(journal.actors[0].attackGeneration == 1);
    context.registers.savedEsp = 0;
    assert(DispatchPreview(9, reinterpret_cast<uint32_t>(&context), &state, sizeof(state), &result));
    assert(journal.actorCount == 2 && journal.actors[1].unsupported == 0x80000000u);
    context.registers.savedEsp = reinterpret_cast<uint32_t>(stack) - 4;
    context.registers.ebx = static_cast<uint32_t>(-17); context.registers.eax = 23;
    assert(DispatchPreview(10, reinterpret_cast<uint32_t>(&context), &state, sizeof(state), &result));
    assert(journal.heroCorrectionCount == 1 && !journal.heroCorrectionOverflow);
    assert(journal.heroCorrections[0].aggregateIdentity == 88 && journal.heroCorrections[0].inputCount == 2);
    assert(journal.heroCorrections[0].firstScalar == -17 && journal.heroCorrections[0].secondScalar == 23);
    assert(journal.heroCorrections[0].attackGeneration == 1);
    stack[0] = 99; stack[3] = static_cast<uint32_t>(-42); stack[7] = 0xbfbb90;
    assert(DispatchPreview(11, reinterpret_cast<uint32_t>(&context), &state, sizeof(state), &result));
    assert(journal.auxiliaryCount == 1 && journal.auxiliaryInputs[0].inputCount == 2);
    assert(journal.auxiliaryInputs[0].aggregateIdentity == 99 && journal.auxiliaryInputs[0].value == -42);
    assert(journal.auxiliaryInputs[0].caller == 0xbfbb90 && journal.auxiliaryInputs[0].attackGeneration == 1);
    stack[7] = 0x111111;
    assert(DispatchPreview(11, reinterpret_cast<uint32_t>(&context), &state, sizeof(state), &result));
    assert(journal.auxiliaryCount == 1 && journal.auxiliaryFrameFailures == 0);
    context.registers.savedEsp = 0;
    assert(DispatchPreview(11, reinterpret_cast<uint32_t>(&context), &state, sizeof(state), &result));
    assert(journal.auxiliaryCount == 1 && journal.auxiliaryFrameFailures == 1);
    context.registers.savedEsp = reinterpret_cast<uint32_t>(stack) - 4;
    stack[7] = 0xbfbbc3;
    journal.heroCorrectionCount = h5_preview::PlacementHeroCorrectionCapacity-1;
    assert(DispatchPreview(10, reinterpret_cast<uint32_t>(&context), &state, sizeof(state), &result));
    assert(journal.heroCorrectionCount == h5_preview::PlacementHeroCorrectionCapacity && !journal.heroCorrectionOverflow);
    assert(DispatchPreview(10, reinterpret_cast<uint32_t>(&context), &state, sizeof(state), &result));
    assert(journal.heroCorrectionCount == h5_preview::PlacementHeroCorrectionCapacity && journal.heroCorrectionOverflow);
    journal.auxiliaryCount = h5_preview::PlacementAuxiliaryInputCapacity-1;
    assert(DispatchPreview(11, reinterpret_cast<uint32_t>(&context), &state, sizeof(state), &result));
    assert(journal.auxiliaryCount == h5_preview::PlacementAuxiliaryInputCapacity && !journal.auxiliaryOverflow);
    assert(DispatchPreview(11, reinterpret_cast<uint32_t>(&context), &state, sizeof(state), &result));
    assert(journal.auxiliaryCount == h5_preview::PlacementAuxiliaryInputCapacity && journal.auxiliaryOverflow);
    journal.actorCount = h5_preview::PlacementActorInputCapacity-1;
    assert(DispatchPreview(9, reinterpret_cast<uint32_t>(&context), &state, sizeof(state), &result));
    assert(journal.actorCount == h5_preview::PlacementActorInputCapacity && !journal.actorOverflow);
    assert(DispatchPreview(9, reinterpret_cast<uint32_t>(&context), &state, sizeof(state), &result));
    assert(journal.actorCount == h5_preview::PlacementActorInputCapacity && journal.actorOverflow);
    assert(DispatchPreview(8, reinterpret_cast<uint32_t>(&context), &state, sizeof(state), &result));
    assert(journal.frozen && journal.count == 1);
    assert(journal.coreMask == 0 && journal.coreErrors == 1);
    assert((journal.sequence & 1) == 0);
    auto& factsOnly = *reinterpret_cast<PostStartVerification*>(resident + PostStartVerificationOffset);
    assert(factsOnly.playerFrozen==1 && factsOnly.playerGeneration==projectionState.attackGeneration &&
        factsOnly.playerForecastCount==0);
    assert(DispatchPreview(12, reinterpret_cast<uint32_t>(&context), &state, sizeof(state), &result));
    assert(journal.count == 1 && journal.observations == 1);
    assert(DispatchPreview(9, reinterpret_cast<uint32_t>(&context), &state, sizeof(state), &result));
    assert(journal.actorCount == h5_preview::PlacementActorInputCapacity);
    assert(DispatchPreview(10, reinterpret_cast<uint32_t>(&context), &state, sizeof(state), &result));
    assert(DispatchPreview(11, reinterpret_cast<uint32_t>(&context), &state, sizeof(state), &result));
    assert(journal.heroCorrectionCount == h5_preview::PlacementHeroCorrectionCapacity && journal.auxiliaryCount == h5_preview::PlacementAuxiliaryInputCapacity);
    assert(DispatchPreview(3, reinterpret_cast<uint32_t>(&context), &state, sizeof(state), &result));
    assert(journal.count == 0 && journal.generation == 2 && !journal.frozen);
    assert(journal.actorCount == 0 && !journal.actorOverflow);
    assert(journal.heroCorrectionCount == 0 && !journal.heroCorrectionOverflow);
    assert(journal.auxiliaryCount == 0 && !journal.auxiliaryOverflow && journal.auxiliaryFrameFailures == 0);
    assert(DispatchPreview(18, 0, &state, sizeof(state), &result) && result == 0);
    assert(DispatchPreview(12, reinterpret_cast<uint32_t>(&context), &state, sizeof(state), &result));
    assert(journal.count == 0);
    assert(DispatchPreview(9, reinterpret_cast<uint32_t>(&context), &state, sizeof(state), &result));
    assert(journal.actorCount == 0);
    assert(DispatchPreview(10, reinterpret_cast<uint32_t>(&context), &state, sizeof(state), &result));
    assert(DispatchPreview(11, reinterpret_cast<uint32_t>(&context), &state, sizeof(state), &result));
    assert(journal.heroCorrectionCount == 0 && journal.auxiliaryCount == 0);
    context.residentSchema = 1;
    assert(!DispatchPreview(12, reinterpret_cast<uint32_t>(&context), &state, sizeof(state), &result));
    context.residentSchema = 2;
    assert(!DispatchPreview(12, reinterpret_cast<uint32_t>(&context), &state, sizeof(state), &result));
    context.residentSchema = 3;
    assert(!DispatchPreview(12, reinterpret_cast<uint32_t>(&context), &state, sizeof(state), &result));
    context.residentSchema = 4;
    assert(!DispatchPreview(12, reinterpret_cast<uint32_t>(&context), &state, sizeof(state), &result));
    context.residentSchema = 5;
    assert(!DispatchPreview(12, reinterpret_cast<uint32_t>(&context), &state, sizeof(state), &result));
    context.residentSchema = 6;
    journal.version = 4; journal.count = 1;
    journal.records[0].sample.input.quantity = 123;
    const auto callsBefore = *reinterpret_cast<uint32_t*>(resident);
    const auto sequenceBefore = journal.sequence;
    assert(!DispatchPreview(3, reinterpret_cast<uint32_t>(&context), &state, sizeof(state), &result));
    assert(journal.version == 4 && journal.count == 1 && journal.records[0].sample.input.quantity == 123);
    assert(journal.sequence == sequenceBefore && *reinterpret_cast<uint32_t*>(resident) == callsBefore);
    assert(previewApi.base.residentSchema == 6);
    uint32_t world[37]{}, firstArmy[1]{0xe17bcc}, secondArmy[1]{0xe17bcc}, sides[2]{};
    world[0] = 0xe79d3c;
    world[0x8c/4] = reinterpret_cast<uint32_t>(firstArmy);
    world[0x90/4] = reinterpret_cast<uint32_t>(secondArmy);
    assert(h5::army::ReadActorArmySides(reinterpret_cast<uint32_t>(world), sides));
    assert(sides[0] == world[0x8c/4] && sides[1] == world[0x90/4]);
    assert(!h5::army::ReadActorArmySides(0, sides) && sides[0] == 0 && sides[1] == 0);
    secondArmy[0] = 0;
    assert(!h5::army::ReadActorArmySides(reinterpret_cast<uint32_t>(world), sides));
    secondArmy[0] = 0xe17bcc;
    assert(h5::army::ReadActorArmySides(reinterpret_cast<uint32_t>(world), sides));
    journal.Begin();journal.frozen = 1;
    journal.worldIdentity = reinterpret_cast<uint32_t>(world);
    journal.armyIdentities[0] = sides[0];journal.armyIdentities[1] = sides[1];
    journal.actorCount = 2;
    for (uint32_t side = 0; side < 2; ++side) {
        auto& actor = journal.actors[side];actor = {};
        actor.world = journal.worldIdentity;actor.army = sides[side];actor.source = 100 + side;
        actor.type = 13 + side;actor.quantity = 10;actor.damage = 20;actor.attack = 4;
        actor.defence = 5;actor.health = 100;actor.initiative = 10;actor.speed = 4;
        actor.category = 2;actor.eligible = 1;actor.controlWord = 0x0c7f;
        actor.aggregateIdentity = 200 + side;actor.attackGeneration = journal.generation;
    }
    journal.CalculateCores();
    assert(journal.coreMask == 3 && journal.coreErrors == 0);
    assert(journal.coreStackCounts[0] == 1 && journal.coreStackCounts[1] == 1);
    assert(journal.coreInputEnds[0] == 1 && journal.coreInputEnds[1] == 2);
    assert(journal.coreAggregates[0].damage == 20 && journal.coreAggregates[1].health == 100);
    journal.auxiliaryCount = 2;
    journal.auxiliaryInputs[0] = {200, 1, 56, h5::army::ActorProtectionCapacity, 0x0c7f, journal.generation};
    journal.auxiliaryInputs[1] = {200, 1, 0x3f000000, h5::army::ActorProtectionFraction, 0x0c7f, journal.generation};
    journal.CalculateCores();
    assert(journal.coreMask == 3 && journal.coreCorrectionMasks[0] == 4);
    assert(journal.coreAggregates[0].health == 300 && journal.coreAggregates[0].eligibleHealth == 300);
    assert(journal.coreAggregates[0].defence == 6 && journal.coreAggregates[0].damage == 20);
    assert(journal.coreAggregates[1].health == 100);
    journal.auxiliaryCount = 1;journal.CalculateCores();
    assert(journal.coreMask == 2); // An unpaired protection primitive is incomplete.
    journal.auxiliaryCount = 3;journal.auxiliaryInputs[2] = journal.auxiliaryInputs[0];journal.CalculateCores();
    assert(journal.coreMask == 2); // Duplicate state cannot be silently combined.
    journal.auxiliaryCount = 0;journal.CalculateCores();
    const float strategySettings[4]{0.05f, 0.025f, 0.2f, 1.3f};
    journal.CalculateCores(strategySettings);
    assert(journal.strategyMask == 0); // Missing full army size is not a complete policy input.
    journal.actors[0].armySize = journal.actors[1].armySize = 1;
    journal.CalculateCores(strategySettings);
    assert(journal.strategyMask == 3 && journal.strategyTrace[0][0] == 1 && journal.strategyTrace[1][0] == 1);
    assert(!journal.strategyTrace[0][1] && !journal.strategyTrace[1][1]);
    journal.actors[0].rangedCapability = 1;
    journal.CalculateCores(strategySettings);
    assert(journal.strategyTrace[0][1] && !journal.strategyTrace[1][1]);
    journal.actors[0].rangedCapability = 0;

    journal.actorOverflow = 1;journal.CalculateCores();
    assert(journal.coreMask == 0 && journal.coreErrors == 1 && journal.coreAggregates[0].damage == 0 && journal.strategyMask == 0 && journal.strategyTrace[0][0] == 0);
    journal.actorOverflow = 0;journal.sideConflict = 1;journal.CalculateCores();
    assert(journal.coreMask == 0 && journal.coreErrors == 1);
    journal.sideConflict = 0;journal.CalculateCores();
    h5_preview::PlacementAggregate expectedCores[2];
    memcpy(expectedCores, journal.coreAggregates, sizeof(expectedCores));
    journal.frozen = 0;journal.version = 7;
    assert(DispatchPreview(18, 1, &state, sizeof(state), &result));
    context.registers.ecx = 0x1234;
    assert(DispatchPreview(6, reinterpret_cast<uint32_t>(&context), &state, sizeof(state), &result));
    context.registers.edi = 0x9999;
    context.registers.savedEsp = reinterpret_cast<uint32_t>(stack) - 4;
    stack[0] = h5::hooks::PlacementRendererCaller;
    assert(DispatchPreview(4, reinterpret_cast<uint32_t>(&context), &state, sizeof(state), &result));
    assert(!journal.frozen);
    context.registers.edi = 0x1234;stack[0] = 0x111111;
    assert(DispatchPreview(4, reinterpret_cast<uint32_t>(&context), &state, sizeof(state), &result));
    assert(!journal.frozen);
    context.registers.savedEsp = 0;
    assert(DispatchPreview(4, reinterpret_cast<uint32_t>(&context), &state, sizeof(state), &result));
    assert(!journal.frozen);
    context.registers.savedEsp = reinterpret_cast<uint32_t>(stack) - 4;
    stack[0] = h5::hooks::PlacementRendererCaller;
    __asm { fninit }
    __asm { fld1 }
    __asm { fld1 }
    __asm { fld1 }
    __asm { fld1 }
    __asm { fld1 }
    __asm { fld1 }
    __asm { fld1 }
    __asm { fld1 }
    assert(DispatchPreview(4, reinterpret_cast<uint32_t>(&context), &state, sizeof(state), &result));
    for (uint32_t index = 0; index < 8; ++index) {
        float restoredValue = 0;
        __asm { fstp restoredValue }
        assert(restoredValue == 1.0f);
    }
    __asm { fninit }
    assert(journal.frozen && journal.coreMask == 3 && journal.coreErrors == 0);
    assert(memcmp(expectedCores, journal.coreAggregates, sizeof(expectedCores)) == 0);
    assert(DispatchPreview(8, reinterpret_cast<uint32_t>(&context), &state, sizeof(state), &result));
    assert(memcmp(expectedCores, journal.coreAggregates, sizeof(expectedCores)) == 0);
    auto& verification = *reinterpret_cast<PolicyVerification*>(resident + PolicyVerificationOffset);
    verification = {};verification.version = 2;verification.generation = journal.generation;
    memset(journal.auxiliaryInputs, 0x5a, sizeof(journal.auxiliaryInputs));
    unsigned char retainedAuxiliary[sizeof(journal.auxiliaryInputs)];
    memcpy(retainedAuxiliary, journal.auxiliaryInputs, sizeof(retainedAuxiliary));
    uint32_t policy[53]{};
    policy[0] = 1;policy[0xd0/4] = 1;
    for (uint32_t index = 0; index < 36; ++index) { policy[0x38/4+index] = 100+index; }
    context.registers.ecx = reinterpret_cast<uint32_t>(policy);
    journal.frozen = 0;
    const auto retainedMask = journal.coreMask;
    journal.coreMask = 0;
    const uint32_t expectedPolicyInputCounts[]{journal.actorCount, journal.auxiliaryCount, journal.heroCorrectionCount};
    ObserveNativePolicy(context, journal, verification, state.adminCapture == 1);
    assert(!journal.frozen && journal.coreMask == 0);
    journal.frozen = 1;journal.coreMask = retainedMask;
    assert(verification.count == 1 && verification.observations[0].side == 1);
    assert(verification.intervalVersion == 1 && verification.intervalGeneration == journal.generation);
    assert(memcmp(verification.capturedInputCounts[0], expectedPolicyInputCounts, sizeof(expectedPolicyInputCounts)) == 0);
    assert(verification.observations[0].aggregates[1][17] == 135);
    assert(verification.capabilityArmyCounts[0][2] == 0); // Missing army context is not a valid zero-sized list.
    assert(verification.capabilityContexts[0][7] == 1);
    int32_t capabilityMetadata[2]{};
    uint32_t capabilityArmy[13]{};capabilityArmy[0]=0xe17bcc;
    capabilityArmy[1]=reinterpret_cast<uint32_t>(capabilityMetadata);
    capabilityArmy[0x28/4]=0x1000;capabilityArmy[0x2c/4]=0x1004;
    uint32_t capabilityArgument=0xabcdef00; // Native bool uses the low byte only.
    heroes5_sdk::EngineInterceptionContext capabilityCall;
    capabilityCall.engine=context;
    capabilityCall.engine.callSite=h5::hooks::DefensiveCapabilityFirst.address;
    capabilityCall.engine.registers.ecx=reinterpret_cast<uint32_t>(capabilityArmy);
    capabilityCall.engine.registers.savedEsp=reinterpret_cast<uint32_t>(&capabilityArgument)-4;
    ObserveNativeCapabilityCall(25,capabilityCall.engine,journal,verification,state.adminCapture==1);
    assert(capabilityCall.action==heroes5_sdk::EngineCallAction::Continue);
    assert(verification.capabilityCallCount==1 && verification.capabilityCalls[0][2]==1);
    assert(verification.capabilityCalls[0][3]==0 && verification.capabilityCalls[0][4]==0);
    capabilityArmy[0x2c/4]=0x1000;capabilityArmy[2]=0x80000000;
    capabilityArgument=1;capabilityCall.engine.callSite=h5::hooks::DefensiveCapabilitySecond.address;
    ObserveNativeCapabilityCall(26,capabilityCall.engine,journal,verification,state.adminCapture==1);
    assert(verification.capabilityCallCount==2 && verification.capabilityCalls[1][2]==0);
    assert(verification.capabilityCalls[1][3]==1 && verification.capabilityCalls[1][4]==1);
    capabilityArmy[0x28/4]=0x1001;capabilityArmy[0x2c/4]=0x1005;
    ObserveNativeCapabilityCall(26,capabilityCall.engine,journal,verification,state.adminCapture==1);
    assert(verification.capabilityCallCount==2 && verification.capabilityCallFailures==1);
    capabilityArmy[0x2c/4]=0x1001;
    ObserveNativeCapabilityCall(26,capabilityCall.engine,journal,verification,state.adminCapture==1);
    assert(verification.capabilityCallCount==2 && verification.capabilityCallFailures==2);
    capabilityCall.engine.registers.eax=0xffffff01;
    ObserveNativeCapabilityCall(27,capabilityCall.engine,journal,verification,true);
    assert(verification.capabilityCallCount==3 && verification.capabilityCalls[2][1]==1);
    capabilityCall.engine.registers.eax=0xffffff00;
    ObserveNativeCapabilityCall(28,capabilityCall.engine,journal,verification,true);
    assert(verification.capabilityCallCount==4 && verification.capabilityCalls[3][1]==0);
    capabilityCall.engine.registers.ebp=1234;
    ObserveNativeCapabilityCall(29,capabilityCall.engine,journal,verification,true);
    assert(verification.capabilityCallCount==5 && verification.capabilityCalls[4][1]==0);
    assert(verification.capabilityCalls[4][2]==1234);
    assert(verification.policyCallContexts[0][0]==reinterpret_cast<uint32_t>(policy));
    capabilityArmy[0x28/4]=capabilityArmy[0x2c/4]=0;
    verification.capabilityCallCount=8;
    ObserveNativeCapabilityCall(26,capabilityCall.engine,journal,verification,state.adminCapture==1);
    assert(verification.capabilityCallCount==9 && !verification.capabilityCallOverflow);
    assert(verification.capabilityCalls[8][0]==26);
    verification.capabilityCallCount=CapabilityCallCapacity;
    ObserveNativeCapabilityCall(26,capabilityCall.engine,journal,verification,state.adminCapture==1);
    assert(verification.capabilityCallCount==CapabilityCallCapacity && verification.capabilityCallOverflow==1);
    assert(DispatchPreview(18,0,&state,sizeof(state),&result));
    capabilityCall.engine.registers.ecx=0;
    ObserveNativeCapabilityCall(26,capabilityCall.engine,journal,verification,state.adminCapture==1);
    assert(verification.capabilityCallFailures==2);
    assert(DispatchPreview(18,1,&state,sizeof(state),&result));
    assert(memcmp(expectedCores, journal.coreAggregates, sizeof(expectedCores)) == 0);
    context.registers.ecx = 0;
    ObserveNativePolicy(context, journal, verification, state.adminCapture == 1);
    assert(verification.count == 1 && verification.failures == 1);
    context.registers.ecx = reinterpret_cast<uint32_t>(policy);
    verification.count = 8;
    ObserveNativePolicy(context, journal, verification, state.adminCapture == 1);
    assert(verification.count == 9 && !verification.overflow);
    verification.count = PolicyObservationCapacity;
    ObserveNativePolicy(context, journal, verification, state.adminCapture == 1);
    assert(verification.count == PolicyObservationCapacity && verification.overflow);
    assert(DispatchPreview(18, 0, &state, sizeof(state), &result));
    const auto failures = verification.failures;
    context.registers.ecx = 0;
    ObserveNativePolicy(context, journal, verification, state.adminCapture == 1);
    assert(verification.failures == failures);
    assert(previewVerificationApi.hooks.count == 16 && previewVerificationApi.hooks.entries[15].command == 19);
    assert(memcmp(retainedAuxiliary, journal.auxiliaryInputs, sizeof(retainedAuxiliary)) == 0);
    assert(!PolicyVerificationAvailable());
    assert(!DispatchPreview(19, 1, &state, sizeof(state), &result));
    assert(!DispatchPreview(31, 1, &state, sizeof(state), &result));
    assert(!DispatchPreview(32, 1, &state, sizeof(state), &result));
    // Precise mode uses the preserved configuration, not diagnostic admission.
    assert(DispatchPreview(18,0,&state,sizeof(state),&result));
    assert(!DispatchPreview(30,2,&state,sizeof(state),&result));
    assert(!DispatchPreview(37,2,&state,sizeof(state),&result));
    assert(DispatchPreview(37,0,&state,sizeof(state),&result) && result==0);
    assert(!g_neutralTypesUnknown); // A command does not mutate the current plan.
    ConfigureResearchMode();assert(g_neutralTypesUnknown);
    assert(DispatchPreview(37,1,&state,sizeof(state),&result) && result==1);
    assert(g_neutralTypesUnknown);
    ConfigureResearchMode();assert(!g_neutralTypesUnknown);
    assert(DispatchPreview(30,1,&state,sizeof(state),&result) && result==1);
    assert(!projectionState.research.enabled); // Takes effect at the next attack.
    assert(SetEnvironmentVariableW(L"H5_PREVIEW_SUPERADMIN_SPREAD",L"1"));
    context.registers.eax=0;
    assert(DispatchPreview(3,reinterpret_cast<uint32_t>(&context),&state,sizeof(state),&result));
    assert(projectionState.research.version==3 && projectionState.research.enabled);
    assert(!projectionState.research.actorInputsFrozen && projectionState.research.useSpreadRows);
    assert(projectionState.research.superadminSourceCount==0);
    context.registers.edi=99;context.registers.ebx=static_cast<uint32_t>(-4);context.registers.eax=2;
    assert(DispatchPreview(10,reinterpret_cast<uint32_t>(&context),&state,sizeof(state),&result));
    assert(projectionState.research.heroCorrectionCount==1);
    assert(projectionState.research.heroCorrections[0].aggregateIdentity==99);
    assert(projectionState.research.heroCorrections[0].firstScalar==-4);
    assert(projectionState.research.heroCorrections[0].secondScalar==2);
    assert(!journal.heroCorrectionCount); // Research did not turn diagnostic capture on.
    uint32_t researchRandom[3]{0xe51284,0,123456};
    context.registers.eax=reinterpret_cast<uint32_t>(researchRandom);
    assert(DispatchPreview(13,reinterpret_cast<uint32_t>(&context),&state,sizeof(state),&result));
    assert(projectionState.research.sourceSplitSeed[1]==123456);
    uint32_t researchStack[13]{};
    researchStack[0]=99;researchStack[3]=static_cast<uint32_t>(-7);
    researchStack[7]=0xbfbb90;researchStack[8]=4;researchStack[9]=1;
    context.registers.esi=0;context.registers.savedEsp=reinterpret_cast<uint32_t>(researchStack)-4;
    assert(DispatchPreview(11,reinterpret_cast<uint32_t>(&context),&state,sizeof(state),&result));
    assert(projectionState.research.auxiliaryInputCount==1 && projectionState.research.auxiliaryInputs[0].value==-7);
    assert(projectionState.research.areaInputCount==1 && (projectionState.research.areaInputs[0].metadata[5]&1));
    // A missing actor frame invalidates the precise input set instead of forging a stack.
    context.registers.savedEsp=0;
    assert(DispatchPreview(9,reinterpret_cast<uint32_t>(&context),&state,sizeof(state),&result));
    assert(projectionState.research.actorInputOverflow && projectionState.research.sourceStrengthOverflow);
    // Scripted combat may be the first event; its source vector is borrowed synchronously.
    memset(&projectionState,0,sizeof(projectionState));
    uint32_t scriptedStacks[4]{57,80,65,12},scriptedFrame[32]{};
    scriptedFrame[21]=reinterpret_cast<uint32_t>(scriptedStacks);
    scriptedFrame[22]=reinterpret_cast<uint32_t>(scriptedStacks+4);
    scriptedFrame[23]=scriptedFrame[22];
    context.registers.savedEsp=reinterpret_cast<uint32_t>(scriptedFrame)-4;
    assert(DispatchPreview(14,reinterpret_cast<uint32_t>(&context),&state,sizeof(state),&result));
    assert(projectionState.research.enabled && projectionState.attackGeneration==1);
    assert(projectionState.research.superadminSourceKind==2 && projectionState.research.superadminSourceCount==2);
    assert(projectionState.research.superadminSourceTypes[0]==57 && projectionState.research.superadminSourceCounts[0]==80);
    context.registers.ecx=0x1234;
    assert(DispatchPreview(6,reinterpret_cast<uint32_t>(&context),&state,sizeof(state),&result));
    assert(projectionState.research.superadminSourceGeneration==projectionState.placementGeneration);
    assert(DispatchPreview(30,0,&state,sizeof(state),&result) && result==0);
    assert(projectionState.research.enabled); // Does not change the current snapshot.
    context.registers.eax=0;
    assert(DispatchPreview(3,reinterpret_cast<uint32_t>(&context),&state,sizeof(state),&result));
    assert(!projectionState.research.enabled && !projectionState.research.superadminSourceCount);
    const auto researchCorrections=projectionState.research.heroCorrectionCount;
    assert(DispatchPreview(10,reinterpret_cast<uint32_t>(&context),&state,sizeof(state),&result));
    assert(projectionState.research.heroCorrectionCount==researchCorrections+1);
    assert(!g_superadminEnabled && g_heroCorrectionCount==0 && g_actorInputCount==0);
    projectionState.research.actorInputsFrozen=true;
    const auto frozenSequence=projectionState.research.sequence;
    g_actorInputCount=123;
    assert(DispatchPreview(10,reinterpret_cast<uint32_t>(&context),&state,sizeof(state),&result));
    assert(projectionState.research.heroCorrectionCount==researchCorrections+1 &&
        projectionState.research.sequence==frozenSequence && g_actorInputCount==123);
    g_actorInputCount=0;
    // Scripted ordinary encounters retain their lifetime, not hidden portraits.
    memset(&projectionState,0,sizeof(projectionState));
    context.registers.savedEsp=reinterpret_cast<uint32_t>(scriptedFrame)-4;
    assert(DispatchPreview(14,reinterpret_cast<uint32_t>(&context),&state,sizeof(state),&result));
    assert(projectionState.attackGeneration==1 && projectionState.publicCount==0);
    assert(!projectionState.research.enabled && projectionState.research.superadminSourceCount==2);
    assert(projectionState.publicTypes[0]==0 && g_superadminSourceCount==0 && g_actorInputCount==0);
    assert(DispatchPreview(8,reinterpret_cast<uint32_t>(&context),&state,sizeof(state),&result));
    assert(factsOnly.playerGeneration==1 && factsOnly.playerFrozen==1 && factsOnly.playerForecastCount==0);
    printf("Capture layout: bytes=%u actors=%u actorCount=%u corrections=%u correctionCount=%u auxiliary=%u auxiliaryCount=%u cores=%u coreMask=%u policy=%u\n",
        unsigned(sizeof(PreviewInputCapture)),unsigned(offsetof(PreviewInputCapture,actors)),
        unsigned(offsetof(PreviewInputCapture,actorCount)),unsigned(offsetof(PreviewInputCapture,heroCorrections)),
        unsigned(offsetof(PreviewInputCapture,heroCorrectionCount)),unsigned(offsetof(PreviewInputCapture,auxiliaryInputs)),
        unsigned(offsetof(PreviewInputCapture,auxiliaryCount)),unsigned(offsetof(PreviewInputCapture,coreAggregates)),
        unsigned(offsetof(PreviewInputCapture,coreMask)),unsigned(PolicyVerificationOffset));
    printf("Research layout: offset=%u bytes=%u enabled=%u actors=%u actorCount=%u actorFrozen=%u sourceCount=%u sourceTypes=%u sourceCounts=%u coreMask=%u strategy=%u composition=%u areaCount=%u sequence=%u\n",
        unsigned(offsetof(PublicProjectionState,research)),unsigned(sizeof(PreciseResearchState)),
        unsigned(offsetof(PreciseResearchState,enabled)),unsigned(offsetof(PreciseResearchState,actorInputs)),
        unsigned(offsetof(PreciseResearchState,actorInputCount)),unsigned(offsetof(PreciseResearchState,actorInputsFrozen)),
        unsigned(offsetof(PreciseResearchState,superadminSourceCount)),unsigned(offsetof(PreciseResearchState,superadminSourceTypes)),
        unsigned(offsetof(PreciseResearchState,superadminSourceCounts)),unsigned(offsetof(PreciseResearchState,actorCoreMask)),
        unsigned(offsetof(PreciseResearchState,strategyTrace)),unsigned(offsetof(PreciseResearchState,sourceComposition)),
        unsigned(offsetof(PreciseResearchState,areaInputCount)),unsigned(offsetof(PreciseResearchState,sequence)));
    auto* migrationBytes = static_cast<unsigned char*>(VirtualAlloc(nullptr, heroes5_sdk::ContextCapacity, MEM_RESERVE|MEM_COMMIT, PAGE_READWRITE));
    assert(migrationBytes);
    auto migrationContext = context;migrationContext.residentData = migrationBytes;
    auto& previousCapture = *reinterpret_cast<PreviewInputCapture*>(migrationBytes+8192);
    previousCapture.version=6;previousCapture.generation=91;
    auto& previousPublic = *reinterpret_cast<PublicProjectionState*>(migrationBytes+192*1024);
    auto* permanentMethods=reinterpret_cast<uint32_t*>(migrationBytes+DetailsNativeMethodsOffset);
    memcpy(permanentMethods,h5::hooks::DetailsRotatorMethods,64);
    permanentMethods[5]=h5::hooks::DetailsRotationAvailable.address;
    memset(&previousPublic,0xa5,offsetof(PublicProjectionState,research));
    previousPublic.version=1;previousPublic.publicCount=7;previousPublic.uiVersion=5;previousPublic.detailsRotatorOwned=0;
    assert(!EnsurePreviewStorage(migrationContext) && previousCapture.version==6 && previousCapture.generation==91);
    previousPublic.uiVersion=4;
    unsigned char preservedPrefix[offsetof(PublicProjectionState,research)];
    memcpy(preservedPrefix,&previousPublic,sizeof(preservedPrefix));
    assert(EnsurePreviewStorage(migrationContext));
    assert(g_detailsNativeMethods==permanentMethods+1);
    const auto& migratedPublic = *reinterpret_cast<const PublicProjectionState*>(migrationBytes+PublicProjectionOffset);
    assert(memcmp(preservedPrefix,&migratedPublic,sizeof(preservedPrefix))==0);
    assert(previousCapture.version==7 && previousCapture.generation==91 && previousCapture.sequence==2);
    assert(!previousCapture.actorCount && !previousCapture.heroCorrectionCount && !previousCapture.auxiliaryCount);
    assert(!migratedPublic.research.version && !migratedPublic.research.enabled);
    assert(EnsurePreviewStorage(migrationContext));
    assert(g_detailsNativeMethods==permanentMethods+1);
    permanentMethods[6]^=1;
    assert(EnsurePreviewStorage(migrationContext) && !g_detailsNativeMethods);
    assert(permanentMethods[6]==(h5::hooks::DetailsRotatorMethods[6]^1));
    assert(VirtualFree(migrationBytes,0,MEM_RELEASE));
    printf("Policy layout: bytes=%u contexts=%u armyCounts=%u callCounts=%u calls=%u policyContexts=%u interval=%u inputCounts=%u capacity=%u callCapacity=%u postStart=%u public=%u publicBytes=%u\n",
        unsigned(sizeof(PolicyVerification)),unsigned(offsetof(PolicyVerification,capabilityContexts)),
        unsigned(offsetof(PolicyVerification,capabilityArmyCounts)),unsigned(offsetof(PolicyVerification,capabilityCallCount)),
        unsigned(offsetof(PolicyVerification,capabilityCalls)),unsigned(offsetof(PolicyVerification,policyCallContexts)),
        unsigned(offsetof(PolicyVerification,intervalVersion)),unsigned(offsetof(PolicyVerification,capturedInputCounts)),
        unsigned(PolicyObservationCapacity),unsigned(CapabilityCallCapacity),unsigned(PostStartVerificationOffset),
        unsigned(PublicProjectionOffset),unsigned(sizeof(PublicProjectionState)));
    assert(VirtualFree(resident, 0, MEM_RELEASE));
    return 0;
}
'''.replace('MANAGED_SOURCE', source)
        with tempfile.TemporaryDirectory(prefix='workshop-managed-capture-') as directory:
            temporary = Path(directory)
            # Substitute only pinned native calls in the isolated executable.
            # Reserve fixture pages away from the host image/low-address heaps.
            native_boundaries = {
                '0x89fbf0': '0x2001fbf0', '0x54e440': '0x2002e440',
                '0x576b40': '0x20036b40', '0x8c6150': '0x20046150', '0x8c61d0': '0x200461d0',
                '0x669e10': '0x20059e10',
                '0x4ba880': '0x2006a880',
                '0x4bdad0': '0x2007dad0', '0x4c7430': '0x20087430',
            }
            fixture_plugin = (MOD_ROOT / 'src/preview_plugin.cpp').read_text(encoding='utf-8')
            for native, boundary in native_boundaries.items():
                fixture_plugin = fixture_plugin.replace(native, boundary)
                driver = driver.replace(native, boundary)
            for original, boundary in {'0x890000': '0x20010000', '0x540000': '0x20020000',
                                       '0x570000': '0x20030000', '0x8c0000': '0x20040000',
                                       '0x4b0000': '0x20060000'}.items():
                driver = driver.replace(original, boundary)
            fixture_adapter = Path(source).read_text(encoding='utf-8')
            fixture_actor = (MOD_ROOT / 'game-api/include/h5/actor_input.hpp').read_text(encoding='utf-8')
            for native, boundary in native_boundaries.items():
                fixture_actor = fixture_actor.replace(native, boundary)
            fixture_actor = fixture_actor.replace('"hooks.hpp"', '"' + (MOD_ROOT / 'game-api/include/h5/hooks.hpp').as_posix() + '"')
            (temporary / 'actor_input.hpp').write_text(fixture_actor, encoding='utf-8')
            fixture_calculations = (MOD_ROOT / 'src/placement_calculations.hpp').read_text(encoding='utf-8')
            fixture_calculations = fixture_calculations.replace('../game-api/include/h5/actor_input.hpp',
                (temporary / 'actor_input.hpp').as_posix())
            (temporary / 'placement_calculations.hpp').write_text(fixture_calculations, encoding='utf-8')
            for header in ('hooks.hpp', 'actor_input.hpp'):
                include = '../game-api/include/h5/' + header
                absolute = (MOD_ROOT / 'game-api/include/h5' / header).as_posix()
                if header == 'actor_input.hpp': absolute = (temporary / 'actor_input.hpp').as_posix()
                fixture_adapter = fixture_adapter.replace(include, absolute)
                fixture_plugin = fixture_plugin.replace(include, absolute)
            (temporary / 'preview_plugin.cpp').write_text(fixture_plugin, encoding='utf-8')
            (temporary / 'preview_sdk.cpp').write_text(fixture_adapter, encoding='utf-8')
            driver = driver.replace(source, (temporary / 'preview_sdk.cpp').as_posix())
            (temporary / 'capture.cpp').write_text(driver, encoding='utf-8')
            (temporary / 'build.cmd').write_text(
                f'@call "{vcvarsall()}" x86 >nul\n@if errorlevel 1 exit /b 1\n'
                f'@cl /nologo /EHsc /O2 /std:c++20 /I"{DEVKIT / "native"}" /I"{MOD_ROOT / "src"}" /Fe:capture.exe capture.cpp user32.lib /link /BASE:0x10000000 /DYNAMICBASE:NO /FIXED\n',
                encoding='utf-8')
            build = subprocess.run(['cmd', '/d', '/c', str(temporary / 'build.cmd')],
                                   cwd=temporary, capture_output=True)
            self.assertEqual(build.returncode, 0, build.stdout.decode(errors='replace') + build.stderr.decode(errors='replace'))
            result = subprocess.run([str(temporary / 'capture.exe')], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stdout.decode(errors='replace') + result.stderr.decode(errors='replace'))
            layout_report = os.environ.get('H5_PREVIEW_LAYOUT_REPORT')
            if layout_report:
                layouts = {}
                for line in result.stdout.decode().splitlines():
                    if line.startswith(('Research layout:', 'Capture layout:', 'Policy layout:')):
                        label, values = line.split(' layout: ', 1)
                        layouts[label.lower()] = {key: int(value) for key, value in
                                                 (entry.split('=') for entry in values.split())}
                assert len(layouts) == 3
                Path(layout_report).write_text(json.dumps(layouts, indent=2)+'\n', encoding='utf-8')
            runtime_driver = r'''
#include <cassert>
#include "plugin_runtime.hpp"
int wmain(int count, wchar_t** arguments) {
    if (count != 2) { return 1; }
    heroes5_sdk::PluginRuntime runtime;
    if (runtime.Replace(arguments[1]) != heroes5_sdk::RuntimeResult::Ok) { return 2; }
    if (runtime.HookSettings().count != 15) { return 3; }
    uint32_t result = 0;
    if (runtime.Invoke(19, 1, result) != heroes5_sdk::RuntimeResult::CallRejected) { return 4; }
    if (runtime.Invoke(20, 1, result) != heroes5_sdk::RuntimeResult::CallRejected) { return 6; }
    if (runtime.Invoke(21, 1, result) != heroes5_sdk::RuntimeResult::CallRejected) { return 7; }
    for (uint32_t command=22;command<=29;++command) {
        if (runtime.Invoke(command,1,result)!=heroes5_sdk::RuntimeResult::CallRejected) { return 8; }
    }
    if (runtime.Invoke(0, 0, result) != heroes5_sdk::RuntimeResult::Ok || result != 1) { return 5; }
    return 0;
}
'''
            (temporary / 'runtime.cpp').write_text(runtime_driver, encoding='utf-8')
            (temporary / 'runtime-build.cmd').write_text(
                f'@call "{vcvarsall()}" x86 >nul\n@if errorlevel 1 exit /b 1\n'
                f'@cl /nologo /EHsc /O2 /std:c++20 /I"{DEVKIT / "native"}" /LD /Fe:preview.dll "{source}" user32.lib\n'
                '@if errorlevel 1 exit /b 1\n'
                f'@cl /nologo /EHsc /O2 /std:c++20 /I"{DEVKIT / "native"}" /Fe:runtime.exe runtime.cpp\n',
                encoding='utf-8')
            build = subprocess.run(['cmd', '/d', '/c', str(temporary / 'runtime-build.cmd')],
                                   cwd=temporary, capture_output=True)
            self.assertEqual(build.returncode, 0, build.stdout.decode(errors='replace') + build.stderr.decode(errors='replace'))
            result = subprocess.run([str(temporary / 'runtime.exe'), str(temporary / 'preview.dll')], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stdout.decode(errors='replace') + result.stderr.decode(errors='replace'))

    def test_forced_cleanup_refuses_missing_or_reused_creation_identity(self):
        import ast
        import ctypes
        from ctypes import wintypes
        from unittest.mock import Mock
        source = (MOD_ROOT / 'scripts/accuracy-campaign.py').read_text(encoding='utf-8')
        function = next(node for node in ast.parse(source).body
                        if isinstance(node, ast.FunctionDef) and node.name == 'stop_hung_owned_sandbox')
        kernel = Mock()
        kernel.OpenProcess.return_value = 77
        def process_times(handle, created, *unused):
            created._obj.dwLowDateTime = 999
            created._obj.dwHighDateTime = 0
            return True
        kernel.GetProcessTimes.side_effect = process_times
        library = Mock(return_value=kernel)
        namespace = {'ctypes': Mock(wraps=ctypes, WinDLL=library), 'wintypes': wintypes, 'Path': Path}
        exec(compile(ast.Module(body=[function], type_ignores=[]), '<forced-cleanup>', 'exec'), namespace)
        with self.assertRaisesRegex(RuntimeError, 'creation identity is required'):
            namespace['stop_hung_owned_sandbox'](123, None, WORKSPACE)
        library.assert_not_called()
        with self.assertRaisesRegex(RuntimeError, 'reused PID'):
            namespace['stop_hung_owned_sandbox'](123, 456, WORKSPACE)
        kernel.TerminateProcess.assert_not_called()
        kernel.QueryFullProcessImageNameW.assert_not_called()
        kernel.CloseHandle.assert_called_once_with(77)
        def process_path(handle, flags, destination, length):
            destination.value = str((WORKSPACE / '.local/test-game/bin/H5_Game.exe').resolve())
            return True
        kernel.QueryFullProcessImageNameW.side_effect = process_path
        kernel.TerminateProcess.return_value = True
        result = namespace['stop_hung_owned_sandbox'](123, 999, WORKSPACE)
        self.assertEqual(result['status'], 'terminated_hung_owned_sandbox')
        kernel.TerminateProcess.assert_called_once_with(77, 1)
        self.assertEqual(kernel.CloseHandle.call_count, 2)
        kernel.TerminateProcess.reset_mock()
        def foreign_path(handle, flags, destination, length):
            destination.value = str(WORKSPACE / 'other-session/H5_Game.exe')
            return True
        kernel.QueryFullProcessImageNameW.side_effect = foreign_path
        with self.assertRaisesRegex(RuntimeError, 'outside the owned test sandbox'):
            namespace['stop_hung_owned_sandbox'](123, 999, WORKSPACE)
        kernel.TerminateProcess.assert_not_called()
        self.assertEqual(kernel.CloseHandle.call_count, 3)

    def test_custom_hero_army_requires_known_distinct_positive_bounded_counts(self):
        import ast
        source=(MOD_ROOT/'scripts/accuracy-campaign.py').read_text()
        function=next(node for node in ast.parse(source).body if isinstance(node,ast.FunctionDef) and node.name=='parse_hero_army')
        namespace={'re':re}
        exec(compile(ast.Module(body=[function],type_ignores=[]),'<hero-army-control>','exec'),namespace)
        names=['CREATURE_UNKNOWN','CREATURE_ARCHER','CREATURE_PEASANT','CREATURE_ANGEL','CREATURE_TITAN']
        self.assertEqual(namespace['parse_hero_army'](['CREATURE_ARCHER:100','CREATURE_PEASANT:1000'],names),
                         {'CREATURE_ARCHER':100,'CREATURE_PEASANT':1000})
        self.assertEqual(namespace['parse_hero_army']([],names),{})
        for specifications in (['CREATURE_ARCHER:0'],['CREATURE_ARCHER:-1'],['CREATURE_ARCHER:1000001'],
                               ['CREATURE_UNKNOWN:1'],['CREATURE_MISSING:1'],['CREATURE_ARCHER:1','CREATURE_ARCHER:2'],
                               ['CREATURE_ARCHER:2;quit'],['CREATURE_ARCHER:1']*7):
            with self.subTest(specifications=specifications),self.assertRaises(ValueError):
                namespace['parse_hero_army'](specifications,names)

    def test_control_queue_wait_does_not_confuse_listeners_with_adventure_readiness(self):
        import ast
        from types import SimpleNamespace
        from unittest.mock import Mock
        source=(MOD_ROOT/'scripts/native-preview-check.py').read_text()
        function=next(node for node in ast.parse(source).body if isinstance(node,ast.FunctionDef) and node.name=='wait_for_control_queues')
        states=[{'stable':True,'event_commands_pending':True,
                 'script_contexts':{'adventure':{'registered_listener_count':0,'script_commands_pending':False}}},
                {'stable':True,'event_commands_pending':False,
                 'script_contexts':{'adventure':{'registered_listener_count':0,'script_commands_pending':True}}},
                {'stable':True,'event_commands_pending':False,
                 'script_contexts':{'adventure':{'registered_listener_count':0,'script_commands_pending':False}}}]
        command=Mock(side_effect=states)
        namespace={'control':command,'json':json,'time':SimpleNamespace(monotonic=Mock(side_effect=[0,0,1,2]),sleep=Mock())}
        exec(compile(ast.Module(body=[function],type_ignores=[]),'<queue-wait>','exec'),namespace)
        self.assertEqual(namespace['wait_for_control_queues'](),states[-1])
        self.assertEqual(command.call_count,3)
        self.assertTrue(all(call.args==('runtime-state',) for call in command.call_args_list))
        namespace['control']=Mock(return_value=states[0]);namespace['time'].monotonic=Mock(side_effect=[0,0,2])
        with self.assertRaisesRegex(RuntimeError,'queues did not drain'):namespace['wait_for_control_queues'](timeout=1)

    def test_capture_failure_does_not_hide_native_failure_diagnostics(self):
        import ast
        from types import SimpleNamespace
        from unittest.mock import Mock
        source = (MOD_ROOT / 'scripts/accuracy-campaign.py').read_text(encoding='utf-8')
        function = next(node for node in ast.parse(source).body
                        if isinstance(node, ast.FunctionDef) and node.name == 'run_map')
        handler = next(node.handlers[0] for node in function.body
                       if isinstance(node, ast.Try) and node.handlers)
        primary = RuntimeError('Projection readiness timed out')
        command = Mock(side_effect=[RuntimeError('Game capture contains no rendered content'),
                                   json.dumps({'frozen': False}), json.dumps({'generation': 0})])
        run = {}; save = Mock()
        namespace = {'primary': primary, 'Exception': Exception, 'json': json, 'run': run, 'pid': 1,
                     'report': {'mode': 'superadmin_source_research'}, 'destination': 'report.json',
                     'save': save, 'check': SimpleNamespace(command=command, GAME_UI='game-ui.ps1',
                     LOADER='loader.exe', PLUGIN='preview.dll', control=Mock(return_value={'status': 'captured'}),
                     diagnostics=Mock(return_value={'public': 0, 'models': 0}))}
        body = ast.Try(body=[ast.Raise(exc=ast.Name(id='primary', ctx=ast.Load()), cause=None)],
                       handlers=[handler], orelse=[], finalbody=[])
        tree = ast.fix_missing_locations(ast.Module(body=[body], type_ignores=[]))
        with self.assertRaisesRegex(RuntimeError, 'Projection readiness timed out'):
            exec(compile(tree, '<failure-diagnostics>', 'exec'), namespace)
        self.assertEqual(run['failure_capture_error'], 'Game capture contains no rendered content')
        self.assertEqual(run['failure_owned_inputs'], {'frozen': False})
        self.assertEqual(run['failure_source_trace'], {'generation': 0})
        self.assertNotIn('failure_image', run)
        self.assertEqual(run['error'], str(primary))
        save.assert_called_once()

    def test_generated_readiness_error_survives_unavailable_adventure_query(self):
        import ast
        from unittest.mock import Mock
        from types import SimpleNamespace
        source = (MOD_ROOT / 'scripts/accuracy-campaign.py').read_text(encoding='utf-8')
        function = next(node for node in ast.parse(source).body
                        if isinstance(node, ast.FunctionDef) and node.name == 'enter_generated_battle')
        readiness_error = RuntimeError('Projection readiness timed out: public2/models0')
        transition_error = RuntimeError('Command remains pending')
        control = Mock(side_effect=[{'x': 10, 'y': 10}, {'status': 'dispatched'}, transition_error])
        check = SimpleNamespace(control=control,
                                wait_for_models=Mock(side_effect=readiness_error),
                                diagnostics=Mock(return_value={'public': 2, 'models': 0}))
        namespace = {'check': check, 'json': json}
        exec(compile(ast.Module(body=[function], type_ignores=[]), '<generated-readiness>', 'exec'), namespace)
        with self.assertRaisesRegex(RuntimeError, 'Projection readiness timed out') as caught:
            namespace['enter_generated_battle'](1, 'Hero7', {'x': 11, 'y': 10, 'name': 'pack'}, 2)
        self.assertIs(caught.exception, readiness_error)
        self.assertIs(caught.exception.__cause__, transition_error)
        self.assertEqual([call.args for call in control.call_args_list],
                         [('hero', 'Hero7'), ('interact', 'Hero7', 'pack'), ('hero', 'Hero7')])

    def test_after_start_evidence_is_saved_before_adventure_cleanup_can_fail(self):
        import ast
        from types import SimpleNamespace
        source=(MOD_ROOT/'scripts/native-preview-check.py').read_text()
        function=next(node for node in ast.parse(source).body if isinstance(node,ast.FunctionDef) and node.name=='complete_battle')
        order=[];saved=[]
        def command(*arguments):
            order.append(arguments[0])
            if arguments[0]=='deployment-observation':
                if len(arguments)>1:return {'sequence':7}
                return {'sequence':7,'units':[{'creature':'CREATURE_PEASANT','cell':[12,6],'quantity':30}]}
            if arguments[0]=='runtime-state':return {'stable':True,'event_commands_pending':False}
            if arguments[0]=='hero':raise RuntimeError('adventure transition unavailable')
            return {'status':'completed'}
        def preserve(observation):
            order.append('saved');saved.append(json.loads(json.dumps(observation)))
        namespace={'control':command,'time':SimpleNamespace(sleep=lambda seconds:None),
                   'diagnostics':lambda pid:{'models':0,'hovered':0},'json':json,'Counter':__import__('collections').Counter,
                   'wait_for_control_queues':lambda:{'stable':True}}
        exec(compile(ast.Module(body=[function],type_ignores=[]),'<battle-completion>', 'exec'),namespace)
        with self.assertRaisesRegex(RuntimeError,'transition unavailable'):
            namespace['complete_battle'](1,{},creature_ids={'CREATURE_PEASANT':1},on_observation=preserve)
        self.assertEqual(saved[0]['units'][0]['type'],1)
        self.assertEqual(saved[0]['units'][0]['quantity'],30)
        self.assertLess(order.index('saved'),order.index('finish'))
        self.assertLess(order.index('saved'),order.index('hero'))

    def test_battle_cleanup_detects_level_dialog_before_level_commit(self):
        import ast
        from types import SimpleNamespace
        source=(MOD_ROOT/'scripts/native-preview-check.py').read_text()
        function=next(node for node in ast.parse(source).body if isinstance(node,ast.FunctionDef) and node.name=='complete_battle')
        for dialogs,expected in (([False],0),([True,False],1),([True,True,False],2)):
            events=[];level=[1];screens=iter(dialogs)
            def control(*arguments):
                if arguments[0]=='hero':return {'level':level[0]}
                if arguments[0]=='levelup-state':return {'available':True,'stable':True,'open':next(screens)}
                if arguments[0]=='event':
                    events.append(arguments[1])
                    if arguments[1]=='MB_Button_Ok':level[0]+=1
                return {'status':'completed'}
            namespace={'control':control,'time':SimpleNamespace(sleep=lambda seconds:None),'json':json,
                       'diagnostics':lambda pid:{'models':0,'hovered':0},'wait_for_control_queues':lambda:{'stable':True},
                       'capture':lambda *args:{'Lines':[{'Text':next(screens)}],'Image':'fixture.png'}}
            exec(compile(ast.Module(body=[function],type_ignores=[]),'<level-cleanup>','exec'),namespace)
            result=namespace['complete_battle'](1,{'hero_level_before_start':1},observe=False)
            self.assertEqual(events,['skill_1','MB_Button_Ok']*expected)
            self.assertEqual(len(result['levelup_choices']),expected)
            self.assertEqual(result['hero']['level'],1+expected)

    def test_battle_cleanup_rejects_unavailable_native_dialog_observer(self):
        import ast
        from types import SimpleNamespace
        from unittest.mock import Mock
        source = (MOD_ROOT / 'scripts/native-preview-check.py').read_text(encoding='utf-8')
        function = next(node for node in ast.parse(source).body
                        if isinstance(node, ast.FunctionDef) and node.name == 'complete_battle')
        for observer in ({'available': False, 'stable': False}, {'available': True, 'stable': False}):
            def command(*arguments):
                if arguments[0] == 'hero': return {'level': 1}
                if arguments[0] == 'levelup-state': return observer
                return {'status': 'completed'}
            calls = Mock(side_effect=command)
            namespace = {'control': calls, 'time': SimpleNamespace(sleep=lambda seconds: None), 'json': json,
                         'diagnostics': lambda pid: {'models': 0, 'hovered': 0},
                         'wait_for_control_queues': lambda: {'stable': True}}
            exec(compile(ast.Module(body=[function], type_ignores=[]), '<native-dialog-guard>', 'exec'), namespace)
            with self.assertRaisesRegex(RuntimeError, 'unavailable or unstable'):
                namespace['complete_battle'](1, {'hero_level_before_start': 1}, observe=False)
            self.assertNotIn('event', [call.args[0] for call in calls.call_args_list])

    def test_superadmin_report_gate_rejects_spatial_only_and_incomplete_evidence(self):
        import copy
        specification=importlib.util.spec_from_file_location('admin_verifier',MOD_ROOT/'scripts/check.py')
        verifier=importlib.util.module_from_spec(specification);specification.loader.exec_module(verifier)
        packs={family:[family+'_0',family+'_1'] for family in ('polygon','rmg_a','rmg_b')}
        report={'mode':'superadmin_source_research','requested_rounds':10,'fixtures':{family:{'name':family} for family in packs},'runs':[]}
        for index in range(10):
            family=('polygon','rmg_a','rmg_b')[index%3];battles=[]
            for pack in packs[family]:
                predicted=[{'type':1,'quantity':10,'cell':[12,4]},{'type':3,'quantity':5,'cell':[13,8]}]
                battles.append({'pack':pack,'prediction':predicted,'observed':copy.deepcopy(predicted),
                    'prediction_complete':True,'full_match':True,'fixture':{'public_count':2},
                    'comparison':{'full_composition_match':True,'quantities_checked':True},
                    'prediction_sha256':hashlib.sha256(json.dumps(predicted,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
                    'prediction_frozen_at_utc':'2026-10-03T12:00:00+00:00','observation_captured_at_utc':'2026-10-03T12:00:01+00:00',
                    'observed_after_start_before_cleanup':{'units':copy.deepcopy(predicted)}})
            report['runs'].append({'round':index+1,'map':family,'close':{'status':'game_closed'},'battles':battles})
        report['acceptance']={'full_matches':20,'battles':20,'mixed_full_matches':20,'mixed_battles':20,'solo_full_matches':0,'solo_battles':0,'passed':False}
        result=verifier.verify_admin_data(report,packs)
        self.assertTrue(result['ok']);self.assertFalse(result['goal_complete'])
        for mutation in ('missing_load','swapped_types','quantity','hash','timestamp','partial','stale_observation','missing_pack','totals'):
            broken=copy.deepcopy(report);battle=broken['runs'][0]['battles'][0]
            if mutation=='missing_load':broken['runs'].pop()
            elif mutation=='swapped_types':battle['observed'][0]['type'],battle['observed'][1]['type']=3,1
            elif mutation=='quantity':battle['observed'][0]['quantity']=11
            elif mutation=='hash':battle['prediction_sha256']='changed'
            elif mutation=='timestamp':battle['prediction_frozen_at_utc']='2026-10-03T12:00:02+00:00'
            elif mutation=='partial':battle['prediction_complete']=False
            elif mutation=='stale_observation':battle['observed_after_start_before_cleanup']['units'][0]['quantity']=11
            elif mutation=='missing_pack':broken['runs'][0]['battles'].pop()
            else:broken['acceptance']['full_matches']=19
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):verifier.verify_admin_data(broken,packs)

    def test_accuracy_report_atomic_save_retries_windows_locks_without_losing_old_evidence(self):
        import ast
        from types import SimpleNamespace
        from unittest.mock import Mock, patch
        source = (MOD_ROOT / 'scripts/accuracy-campaign.py').read_text()
        function = next(node for node in ast.parse(source).body if isinstance(node, ast.FunctionDef) and node.name == 'save')
        sleeper = Mock()
        namespace = {'json': json, 'time': SimpleNamespace(sleep=sleeper), '_completed_battle_json': {}}
        exec(compile(ast.Module(body=[function], type_ignores=[]), '<atomic-report-save>', 'exec'), namespace)
        with tempfile.TemporaryDirectory(prefix='workshop-atomic-report-') as directory:
            target = Path(directory) / 'evidence.json'
            target.write_text('{"old": true}', encoding='utf-8')
            original = Path.replace
            blocked = PermissionError('temporary Windows lock');blocked.winerror = 5
            calls = []
            def replace(path, destination):
                calls.append(path)
                if len(calls) == 1:
                    self.assertEqual(json.loads(target.read_text()), {'old': True})
                    raise blocked
                return original(path, destination)
            with patch.object(Path, 'replace', replace):
                namespace['save']({'new': True}, target)
            self.assertEqual(json.loads(target.read_text()), {'new': True})
            self.assertEqual(len(calls), 2)
            self.assertFalse(target.with_suffix('.tmp').exists())
            with patch.object(Path, 'replace', side_effect=blocked) as replacing:
                with self.assertRaises(PermissionError):namespace['save']({'pending': True}, target)
                self.assertEqual(replacing.call_count, 21)
            self.assertEqual(json.loads(target.read_text()), {'new': True})
            self.assertEqual(json.loads(target.with_suffix('.tmp').read_text()), {'pending': True})
            with patch.object(Path, 'replace', side_effect=PermissionError('other denial')) as replacing:
                with self.assertRaises(PermissionError):namespace['save']({'fatal': True}, target)
                self.assertEqual(replacing.call_count, 1)
            # Completed raw evidence is encoded once; active records and run
            # metadata still update, and the persisted full JSON remains exact.
            completed = {'pack': 'done', 'prediction': [{'quantity': 10, 'cell': [13, 2]}],
                         'raw_words': [0, 4294967295], 'label': 'бой'}
            active = {'pack': 'next', 'stage': 'before_start', 'raw_words': [1, 2]}
            report = {'schema': 1, 'runs': [{'round': 1, 'battles': [completed, active]}]}
            serializer = Mock(wraps=json.dumps)
            namespace['json'] = SimpleNamespace(dumps=serializer)
            namespace['save'](report, target, completed_battle=completed)
            active.update(stage='after_start', actual=[{'quantity': 3, 'cell': [12, 1]}])
            report['runs'][0]['close'] = {'status': 'game_closed'}
            namespace['save'](report, target)
            self.assertEqual(json.loads(target.read_text(encoding='utf-8')), report)
            self.assertEqual(sum(call.args[0] is completed for call in serializer.call_args_list), 1)
            self.assertFalse(target.with_suffix('.tmp').exists())

    def test_generated_approach_refuses_unchecked_tiles_and_preserves_floor(self):
        import ast
        from types import SimpleNamespace
        text = (MOD_ROOT / 'scripts/accuracy-campaign.py').read_text()
        function = next(node for node in ast.parse(text).body if isinstance(node, ast.FunctionDef)
                        and node.name == 'enter_generated_battle')
        for destination in ('none', '99,100'):
            calls = []
            state = {'x': 0, 'y': 0, 'floor': 1}
            def command(*arguments):
                calls.append(arguments)
                if arguments[0] == 'hero': return dict(state)
                if arguments[0] == 'console':
                    self.assertIn('IsTilePassable(cell[1],cell[2],1)', arguments[1])
                    return {'status': 'completed'}
                if arguments[0] == 'eval': return {'result': destination}
                if arguments[0] == 'teleport':
                    self.assertEqual(arguments[2:], ('99', '100', '--floor', '1'))
                    self.assertEqual(calls[-2][0], 'eval')
                    state.update(x=99, y=100)
                    return {'status': 'completed'}
                return {'status': 'completed'}
            fake = SimpleNamespace(control=command, wait_for_models=lambda *args, **kwargs: {'ready': True})
            namespace = {'check': fake, 'json': json}
            exec(compile(ast.Module(body=[function], type_ignores=[]), '<generated-approach>', 'exec'), namespace)
            if destination == 'none':
                with self.assertRaisesRegex(RuntimeError, 'verified approaches'):
                    namespace['enter_generated_battle'](7, 'Brem', {'x': 100, 'y': 100, 'name': 'pack'}, 2)
                self.assertFalse(any(call[0] in ('teleport', 'interact') for call in calls))
            else:
                projection, attempts = namespace['enter_generated_battle'](7, 'Brem', {'x': 100, 'y': 100, 'name': 'pack'}, 2)
                self.assertTrue(projection['ready'])
                self.assertEqual(attempts[0]['teleport_destination'], [99, 100, 1])
                self.assertEqual(attempts[0]['validated_by'], 'IsTilePassable')

    def test_owned_physical_area_power_matches_original_shot_and_melee_branches(self):
        import pefile, itertools
        from unicorn.x86_const import UC_X86_REG_FPCW
        source = preview_source()
        calculation = 'int CalculateAreaPhysicalPower(' + source.split('int CalculateAreaPhysicalPower(', 1)[1].split(
            '// Initial-state arithmetic', 1)[0]
        driver = r'''
#include <cstdint>
#include <iostream>
CALCULATION
int main() {
    int quantity,ranged,canShoot,half,wide;uint32_t sumBits,control;
    while(std::cin>>quantity>>sumBits>>ranged>>canShoot>>half>>wide>>control) {
        uint16_t original,captured=static_cast<uint16_t>(control),after;
        __asm fnstcw original
        __asm fldcw captured
        const int result=CalculateAreaPhysicalPower(quantity,*reinterpret_cast<float*>(&sumBits),ranged!=0,canShoot!=0,half!=0,wide!=0);
        __asm fnstcw after
        __asm fldcw original
        std::cout<<result<<' '<<after<<'\n';
    }
}
'''.replace('CALCULATION', calculation)
        game = WORKSPACE / '.local/test-game/bin/H5_Game.exe'
        self.assertEqual(hashlib.sha256(game.read_bytes()).hexdigest(), probe.HASHES['H5_Game.exe'])
        pe = pefile.PE(str(game)); base = pe.OPTIONAL_HEADER.ImageBase
        cpu = Uc(UC_ARCH_X86, UC_MODE_32)
        cpu.mem_map(base, (pe.OPTIONAL_HEADER.SizeOfImage + 4095) & ~4095)
        cpu.mem_write(base, pe.get_memory_mapped_image()); cpu.mem_map(0x2000000,65536)
        wrapper,node,actor,table,stack=0x2001000,0x2002000,0x2003000,0x2004000,0x2008000
        cpu.mem_write(wrapper+4,struct.pack('<I',node));cpu.mem_write(node+8,struct.pack('<I',actor-wrapper-4))
        cpu.mem_write(actor,struct.pack('<I',table))
        assembler=keystone.Ks(keystone.KS_ARCH_X86,keystone.KS_MODE_32)
        for offset,assembly in ((0x1ec,'fld dword ptr [0x2006000]; ret'),(0x1f0,'fld dword ptr [0x2006004]; ret')):
            address=0x2005000+offset*8
            cpu.mem_write(table+offset,struct.pack('<I',address));cpu.mem_write(address,bytes(assembler.asm(assembly,address)[0]))
        sumCode='fld dword ptr [0x2006004]; fadd dword ptr [0x2006000]; fstp dword ptr [0x2006008]'
        cpu.mem_write(0x2007000,bytes(assembler.asm(sumCode,0x2007000)[0]));sumEnd=0x2007000+len(assembler.asm(sumCode,0x2007000)[0])
        payload,expected=[],[]
        for quantity,damages,ranged,canShoot,half,wide,control in itertools.product(
                (0,1,3,10,1000,123456789),((1,2),(1.25,7.75),(-5,0),(100000.5,999999.5)),
                (0,1),(0,1),(0,1),(0,1),(0x027f,0x0c7f)):
            for offset,assembly in ((0x1d8,f'mov eax,{quantity}; ret'),(0xb8,f'mov eax,{canShoot}; ret 12'),
                    (0x28c,f'cmp dword ptr [esp+4],4; jne area; mov eax,{half}; ret 4; area: mov eax,{wide}; ret 4')):
                address=0x2005000+offset*8
                cpu.mem_write(table+offset,struct.pack('<I',address));cpu.mem_write(address,bytes(assembler.asm(assembly,address)[0]))
                cpu.ctl_remove_cache(address,address+64)
            cpu.mem_write(0x2006000,struct.pack('<2f',*damages));cpu.reg_write(UC_X86_REG_FPCW,control)
            cpu.emu_start(0x2007000,sumEnd,count=100)
            sumBits=struct.unpack('<I',cpu.mem_read(0x2006008,4))[0]
            cpu.mem_write(stack,bytes(128));cpu.mem_write(stack+0x24,struct.pack('<I',0x2009000))
            cpu.reg_write(UC_X86_REG_ESP,stack);cpu.reg_write(UC_X86_REG_ESI,wrapper)
            cpu.reg_write(UC_X86_REG_EBX,0);cpu.reg_write(UC_X86_REG_FPCW,control)
            cpu.emu_start(0xa2ffd9 if ranged else 0xa3009b,0xa30149,count=1000)
            result=struct.unpack('<i',cpu.mem_read(stack+0x1c,4))[0]
            expected.append([result,control]);self.assertEqual(cpu.reg_read(UC_X86_REG_FPCW),control)
            payload.append(' '.join(map(str,(quantity,sumBits,ranged,canShoot,half,wide,control))))
        with tempfile.TemporaryDirectory(prefix='workshop-physical-area-') as directory:
            folder=Path(directory);(folder/'physical.cpp').write_text(driver,encoding='utf-8')
            (folder/'build.cmd').write_text(f'@call "{vcvarsall()}" x86 >nul\n@if errorlevel 1 exit /b 1\n'
                                           '@cl /nologo /EHsc /O2 /std:c++20 /Fe:physical.exe physical.cpp\n',encoding='utf-8')
            built=subprocess.run(['cmd','/d','/c',str(folder/'build.cmd')],cwd=folder,capture_output=True)
            self.assertEqual(built.returncode,0,built.stdout.decode(errors='replace')+built.stderr.decode(errors='replace'))
            completed=subprocess.run([str(folder/'physical.exe')],input='\n'.join(payload)+'\n',text=True,capture_output=True)
            self.assertEqual(completed.returncode,0,completed.stderr)
            self.assertEqual([list(map(int,row.split())) for row in completed.stdout.splitlines()],expected)

    def test_hero_attack_target_scalar_rounds_remaining_unit_hp_and_clamps_to_one(self):
        import pefile
        from unicorn import UC_HOOK_CODE
        from unicorn.x86_const import UC_X86_REG_FPCW
        executable = pefile.PE(str(WORKSPACE / '.local/test-game/bin/H5_Game.exe'))
        base = executable.OPTIONAL_HEADER.ImageBase
        machine = Uc(UC_ARCH_X86, UC_MODE_32)
        machine.mem_map(base, (executable.OPTIONAL_HEADER.SizeOfImage + 4095) & ~4095)
        machine.mem_write(base, executable.get_memory_mapped_image());machine.mem_map(0x2000000, 65536)
        actor, table, getter, stack, stop = 0x2001000, 0x2002000, 0x2003000, 0x2004000, 0x2005000
        machine.mem_write(actor - 0xa8, struct.pack('<I', table))
        machine.mem_write(table + 0x50, struct.pack('<I', getter))
        maximum_hp = [1]
        def stat_boundary(emulator, address, size, user):
            # Only max-HP retrieval is substituted; original fraction/rounding code runs.
            if address != getter:return
            emulator.reg_write(UC_X86_REG_EAX, maximum_hp[0])
            pointer = emulator.reg_read(UC_X86_REG_ESP)
            destination = struct.unpack('<I', emulator.mem_read(pointer, 4))[0]
            emulator.reg_write(UC_X86_REG_ESP, pointer + 4);emulator.reg_write(UC_X86_REG_EIP, destination)
        machine.hook_add(UC_HOOK_CODE, stat_boundary)
        def single_chop(value):
            bits = struct.unpack('<I', struct.pack('<f', value))[0]
            rounded = struct.unpack('<f', struct.pack('<I', bits))[0]
            if abs(rounded) > abs(value):bits -= 1
            return struct.unpack('<f', struct.pack('<I', bits))[0]
        cases = 0
        for health in (1, 3, 10, 30, 250, 1000, 100000):
            maximum_hp[0] = health
            for fraction in (-.2, 0, .1, .25, .5, .75, .9, 1, 1.5):
                fraction = struct.unpack('<f', struct.pack('<f', fraction))[0]
                machine.mem_write(actor - 0x50, struct.pack('<f', fraction))
                machine.mem_write(stack, struct.pack('<I', stop))
                machine.reg_write(UC_X86_REG_ESP, stack);machine.reg_write(UC_X86_REG_ECX, actor)
                machine.reg_write(UC_X86_REG_FPCW, 0xc7f)
                machine.emu_start(0x8a0f30, stop, count=5000)
                expected = max(1, int(single_chop(single_chop(single_chop(1 - fraction) * health) + .5)))
                self.assertEqual(machine.reg_read(UC_X86_REG_EAX), expected, (health, fraction))
                self.assertEqual(machine.reg_read(UC_X86_REG_FPCW), 0xc7f)
                cases += 1
        self.assertEqual(cases, 63)
        executable.close()

    def test_hero_baseline_interpolation_matches_original_tier_level_and_scalar_boundaries(self):
        import pefile
        from unicorn import UC_HOOK_CODE
        from unicorn.x86_const import UC_X86_REG_FPCW
        executable = pefile.PE(str(WORKSPACE / '.local/test-game/bin/H5_Game.exe'))
        data = executable.get_memory_mapped_image();base = executable.OPTIONAL_HEADER.ImageBase
        machine = Uc(UC_ARCH_X86, UC_MODE_32)
        machine.mem_map(base, (executable.OPTIONAL_HEADER.SizeOfImage + 4095) & ~4095)
        machine.mem_write(base, data);machine.mem_map(0x2000000, 0x20000)
        holder, settings, low_pointer, high_pointer, stack, stop = (
            0x2002000, 0x2002000, 0x2004000, 0x2004100, 0x2008000, 0x2009000)
        low = list(struct.unpack('<8f', struct.pack('<8f', .125, .2, .35, .5, .625, .7, .875, 1)))
        high = list(struct.unpack('<8f', struct.pack('<8f', 1.25, 1.4, 1.75, 2, 2.25, 2.4, 2.75, 3)))
        machine.mem_write(low_pointer, struct.pack('<8f', *low))
        machine.mem_write(high_pointer, struct.pack('<8f', *high))
        machine.mem_write(settings + 0x788, struct.pack('<3I', low_pointer, low_pointer + 32, low_pointer + 32))
        machine.mem_write(settings + 0x794, struct.pack('<3I', high_pointer, high_pointer + 32, high_pointer + 32))
        hero_boundaries = {}
        def resource_boundary(emulator, address, size, user):
            # Only the external settings singleton/resource lookup is substituted.
            # Arithmetic, vector validation and reference handling stay original.
            if address not in (0xbcb3f0, 0x420df0) and address not in hero_boundaries:return
            pointer = emulator.reg_read(UC_X86_REG_ESP)
            cleanup = 0
            if address in hero_boundaries:
                # Hero characteristics are external to this arithmetic oracle.
                result, argument = hero_boundaries[address]
                if isinstance(result, dict):
                    actual_argument = struct.unpack('<I', emulator.mem_read(pointer + 4, 4))[0]
                    self.assertIn(actual_argument, result)
                    result = result[actual_argument]
                    cleanup = 4
                elif argument is not None:
                    self.assertEqual(struct.unpack('<I', emulator.mem_read(pointer + 4, 4))[0], argument)
                    cleanup = 4
            else:
                result = holder if address == 0xbcb3f0 else settings
            emulator.reg_write(UC_X86_REG_EAX, result)
            destination = struct.unpack('<I', emulator.mem_read(pointer, 4))[0]
            emulator.reg_write(UC_X86_REG_ESP, pointer + 4 + cleanup);emulator.reg_write(UC_X86_REG_EIP, destination)
        machine.hook_add(UC_HOOK_CODE, resource_boundary)
        factor = struct.unpack_from('<f', data, 0xe84984 - base)[0]
        def single_chop(value):
            bits = struct.unpack('<I', struct.pack('<f', value))[0]
            if struct.unpack('<f', struct.pack('<I', bits))[0] > value:bits -= 1
            return struct.unpack('<f', struct.pack('<I', bits))[0]
        cases = 0
        # Second table pair is the exact pre-Start words captured in PID48664.
        loaded_low = list(struct.unpack('<8f', struct.pack('<8I',
            1073741824, 1065353216, 1061997773, 1056964608,
            1050253721, 1045220557, 1036831949, 1008981770)))
        loaded_high = list(struct.unpack('<8f', struct.pack('<8I',
            1094713344, 1091567616, 1087373312, 1083179008,
            1077936128, 1073741824, 1069547520, 1041865113)))
        for low, high in ((low, high), (loaded_low, loaded_high)):
            machine.mem_write(low_pointer, struct.pack('<8f', *low))
            machine.mem_write(high_pointer, struct.pack('<8f', *high))
            for tier in (-1, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 20):
                for level in (1, 2, 5, 7, 10, 20, 30, 31, 40, 60):
                    for scalar in (0, 1, 4, 30, 100, 1000):
                        machine.mem_write(holder + 8, struct.pack('<I', 1))
                        machine.mem_write(stack, struct.pack('<3I', stop, scalar, level))
                        machine.reg_write(UC_X86_REG_ESP, stack)
                        machine.reg_write(UC_X86_REG_EAX, tier & 0xffffffff)
                        machine.reg_write(UC_X86_REG_FPCW, 0xc7f)
                        machine.emu_start(0xbc1a50, stop, count=5000)
                        index = min(8, max(1, tier)) - 1
                        value = single_chop(high[index] - low[index])
                        value = single_chop(value * (level - 1))
                        value = single_chop(value * factor)
                        value = single_chop(value + low[index])
                        expected = int(single_chop(value * scalar))
                        self.assertEqual(machine.reg_read(UC_X86_REG_EAX), expected, (tier, level, scalar))
                        self.assertEqual(machine.reg_read(UC_X86_REG_FPCW), 0xc7f)
                        self.assertEqual(struct.unpack('<I', machine.mem_read(holder + 8, 4))[0], 1)
                        cases += 1
        self.assertEqual(cases, 1440)
        # Full null-target caller: original bc1b90, bc1a50 and bcdf10 run.
        # Combined flags below are synthetic branch coverage, not legal hero builds.
        hero, virtual_base, methods, information, information_table = (
            0x200a000, 0x200b000, 0x200c000, 0x200d000, 0x200e000)
        machine.mem_write(hero + 4, struct.pack('<I', virtual_base))
        machine.mem_write(virtual_base + 8, struct.pack('<I', 0x1c))
        machine.mem_write(hero + 0x20, struct.pack('<I', methods))
        for offset, address in ((0x23c, 0x2010000), (0x290, 0x2010100),
                                (8, 0x2010200), (0x294, 0x2010400)):
            machine.mem_write(methods + offset, struct.pack('<I', address))
        machine.mem_write(information, struct.pack('<I', information_table))
        machine.mem_write(information_table + 0x3c, struct.pack('<I', 0x2010300))
        # Live hero slots290/294 forward to owner174/190. Keep those
        # original thunks/forwarders; substitute only owner characteristics.
        owner, owner_methods = 0x201b000, 0x201c000
        machine.mem_write(hero + 0x20 - 0x6c, struct.pack('<I', owner))
        machine.mem_write(owner, struct.pack('<I', owner_methods))
        machine.mem_write(owner_methods + 0x174, struct.pack('<I', 0x2010100))
        machine.mem_write(owner_methods + 0x190, struct.pack('<I', 0x2010400))
        machine.mem_write(methods + 0x290, struct.pack('<I', 0xbc32d0))
        machine.mem_write(methods + 0x294, struct.pack('<I', 0xbc32e0))
        for skill_level in (-1, 0, 1, 3, 100):
            hero_boundaries[0x2010100] = (skill_level & 0xffffffff, 91)
            machine.mem_write(stack, struct.pack('<2I', stop, 91))
            machine.reg_write(UC_X86_REG_ESP, stack)
            machine.reg_write(UC_X86_REG_ECX, hero + 0x20)
            machine.emu_start(0xbc32d0, stop, count=1000)
            self.assertEqual(machine.reg_read(UC_X86_REG_EAX) & 255, int(skill_level > 0), skill_level)
        # Live CHero owner190 is exact enum equality against its field8c.
        # Arithmetic combinations below still substitute that owner boundary,
        # allowing deliberately synthetic combinations of specialization flags.
        for actual_specialization in (0, 17, 73, 74, 100):
            machine.mem_write(owner + 0x8c, struct.pack('<I', actual_specialization))
            for requested_specialization in (0, 17, 73, 74, 100):
                machine.mem_write(stack, struct.pack('<2I', stop, requested_specialization))
                machine.reg_write(UC_X86_REG_ESP, stack)
                machine.reg_write(UC_X86_REG_ECX, owner)
                machine.emu_start(0xb4b5a0, stop, count=1000)
                self.assertEqual(machine.reg_read(UC_X86_REG_EAX),
                                 int(actual_specialization == requested_specialization),
                                 (actual_specialization, requested_specialization))
        coefficient = struct.unpack('<f', struct.pack('<f', .03))[0]
        machine.mem_write(settings + 0x964, struct.pack('<f', coefficient))
        caller_cases = 0
        for level in (1, 2, 5, 7, 10, 20, 30, 31, 40, 60):
            for level_bonus in (False, True):
                for specialization in (0, 73, 74, 75, 100):
                    for offender in (False, True):
                        hero_boundaries.update({
                            0x2010000: (level, None), 0x2010100: (int(level_bonus), 0x41),
                            0x2010200: (information, None), 0x2010300: (specialization, None),
                            0x2010400: (int(offender), 0x4a)})
                        machine.mem_write(holder + 8, struct.pack('<I', 1))
                        machine.mem_write(stack, struct.pack('<3I', stop, 0, 0))
                        machine.reg_write(UC_X86_REG_ESP, stack)
                        machine.reg_write(UC_X86_REG_ECX, hero + 0xa0)
                        machine.reg_write(UC_X86_REG_FPCW, 0xc7f)
                        machine.emu_start(0xbc1b90, stop, count=10000)
                        value = single_chop(high[2] - low[2])
                        value = single_chop(value * (level + 3 * level_bonus - 1))
                        value = single_chop(value * factor)
                        value = single_chop(value + low[2])
                        expected = int(single_chop(value * 30))
                        if specialization in (73, 75):expected += expected // 2
                        if offender:
                            multiplier = single_chop(single_chop(level * coefficient) + 1)
                            expected = int(single_chop(multiplier * expected))
                        self.assertEqual(machine.reg_read(UC_X86_REG_EAX), max(1, expected),
                                         (level, level_bonus, specialization, offender))
                        self.assertEqual(machine.reg_read(UC_X86_REG_FPCW), 0xc7f)
                        self.assertEqual(struct.unpack('<I', machine.mem_read(holder + 8, 4))[0], 1)
                        caller_cases += 1
        self.assertEqual(caller_cases, 200)
        # Target-present caller retains the original remaining-unit-HP getter.
        target, target_methods, descriptor, descriptor_methods, definition = (
            0x2015000, 0x2016000, 0x2017000, 0x2017100, 0x2017200)
        fallback, fallback_methods, eligibility, eligibility_methods, hp_methods = (
            0x2017300, 0x2017400, 0x2017500, 0x2017600, 0x2018000)
        machine.mem_write(target, struct.pack('<I', target_methods))
        machine.mem_write(target - 4, struct.pack('<I', 0))
        machine.mem_write(target - 0xa8, struct.pack('<I', hp_methods))
        machine.mem_write(target - 0x50, struct.pack('<f', .25))
        machine.mem_write(hp_methods + 0x50, struct.pack('<I', 0x2010600))
        for offset, address in ((0x1a8, 0x8ae6a0), (0x6c, 0x2010800),
                                (0x8c, 0x2010900), (0x1d4, 0x8aec90)):
            machine.mem_write(target_methods + offset, struct.pack('<I', address))
        history, history_records = 0x2019000, 0x201a000
        machine.mem_write(target - 0x98, struct.pack('<I', history))
        # Live records are16 bytes; getter reads end-8 (record word2).
        # Empty history returns the zero-valued global sentinel, not minimum1.
        for records in ((), (17,), (999, 23), (999, 23, 0), (0, 17, 100000)):
            machine.mem_write(history + 0x1c, struct.pack('<2I', history_records,
                                                       history_records + 16 * len(records)))
            for index, value in enumerate(records):
                machine.mem_write(history_records + 16 * index, struct.pack('<4I', 66, 77, value, 88))
            machine.mem_write(stack, struct.pack('<I', stop))
            machine.reg_write(UC_X86_REG_ESP, stack)
            machine.reg_write(UC_X86_REG_ECX, target)
            machine.emu_start(0x8aec90, stop, count=1000)
            self.assertEqual(machine.reg_read(UC_X86_REG_EAX), records[-1] if records else 0, records)
        machine.mem_write(descriptor, struct.pack('<I', descriptor_methods))
        machine.mem_write(descriptor_methods, struct.pack('<I', 0x2010d00))
        machine.mem_write(descriptor_methods + 0x1c, struct.pack('<I', 0x2010700))
        machine.mem_write(definition + 0x1c, struct.pack('<I', 123))
        machine.mem_write(fallback, struct.pack('<I', fallback_methods))
        machine.mem_write(fallback_methods, struct.pack('<I', 0x2010a00))
        machine.mem_write(hero + 0xa0, struct.pack('<I', methods))
        machine.mem_write(methods, struct.pack('<I', 0x2010b00))
        machine.mem_write(information_table + 0x25c, struct.pack('<I', 0x2010c00))
        machine.mem_write(eligibility, struct.pack('<I', eligibility_methods))
        machine.mem_write(eligibility_methods + 0xc, struct.pack('<I', 0x2010e00))
        target_cases = 0
        for route in ('creature', 'fallback', 'neither'):
            for tier in (-1, 1, 3, 8, 9, 20):
                for health in (1, 30, 1000):
                    for level in (1, 31):
                        for level_bonus in (False, True):
                            for eligible, floor_above in ((False, False), (False, True),
                                                          (True, False), (True, True)):
                                scalar = max(1, int(single_chop(single_chop(.75 * health) + .5)))
                                index = min(8, max(1, tier if route != 'neither' else 3)) - 1
                                value = single_chop(high[index] - low[index])
                                value = single_chop(value * (level + 3 * level_bonus - 1))
                                value = single_chop(value * factor)
                                value = single_chop(value + low[index])
                                expected = int(single_chop(value * scalar))
                                expected += expected // 2
                                floor_value = 2 * expected + 7 if floor_above else max(1, expected // 2)
                                machine.mem_write(history + 0x1c, struct.pack('<2I', history_records,
                                                                           history_records + 32))
                                machine.mem_write(history_records, struct.pack('<8I',
                                    66, 77, floor_value + 1000, 88, 55, 99, floor_value, 111))
                                if route == 'creature' and level_bonus and eligible:
                                    expected = max(2 * expected, floor_value)
                                multiplier = single_chop(single_chop(level * coefficient) + 1)
                                expected = max(1, int(single_chop(multiplier * expected)))
                                hero_boundaries.update({
                                    0x2010000: (level, None), 0x2010100: (int(level_bonus), 0x41),
                                    0x2010300: (73, None), 0x2010400: (1, 0x4a),
                                    0x2010600: (health, None), 0x2010700: (tier & 0xffffffff, None),
                                    0x2010800: (descriptor if route == 'creature' else 0, None),
                                    0x2010900: (fallback if route == 'fallback' else 0, None),
                                    0x2010a00: (tier & 0xffffffff, None), 0x2010b00: (information, None),
                                    0x2010c00: (eligibility, None), 0x2010d00: (definition, None),
                                    0x2010e00: (int(eligible), 123)})
                                machine.mem_write(holder + 8, struct.pack('<I', 1))
                                machine.mem_write(stack, struct.pack('<3I', stop, 0, target))
                                machine.reg_write(UC_X86_REG_ESP, stack)
                                machine.reg_write(UC_X86_REG_ECX, hero + 0xa0)
                                machine.reg_write(UC_X86_REG_FPCW, 0xc7f)
                                machine.emu_start(0xbc1b90, stop, count=10000)
                                self.assertEqual(machine.reg_read(UC_X86_REG_EAX), expected,
                                                 (route, tier, health, level, level_bonus, eligible, floor_above))
                                self.assertEqual(machine.reg_read(UC_X86_REG_FPCW), 0xc7f)
                                self.assertEqual(struct.unpack('<I', machine.mem_read(holder + 8, 4))[0], 1)
                                target_cases += 1
        self.assertEqual(target_cases, 864)
        # Universe replaces only the final stage at bc1d09. Its pinned DLL
        # supplies the settings call, predicate IDs, constants and return slot.
        universe = pefile.PE(str(WORKSPACE / '.local/test-game/bin/uni.dll'))
        universe_base = universe.OPTIONAL_HEADER.ImageBase
        universe_data = universe.get_memory_mapped_image()
        machine.mem_map(universe_base, (universe.OPTIONAL_HEADER.SizeOfImage + 4095) & ~4095)
        machine.mem_write(universe_base, universe_data)
        self.assertEqual(struct.unpack_from('<I', universe_data, 0xbc9a0)[0], 0xbc1d87)
        self.assertEqual(struct.unpack_from('<I', universe_data, 0xbc998)[0], 0xbcb3f0)
        predicate_ids = tuple(struct.unpack_from('<I', universe_data, offset)[0]
                              for offset in (0xbd50c, 0xbd508, 0xbd504))
        self.assertEqual(predicate_ids, (91, 74, 17))
        half_bonus = struct.unpack_from('<f', universe_data, 0xbc99c)[0]
        per_level_bonus = struct.unpack_from('<f', universe_data, 0xbc994)[0]
        self.assertEqual((half_bonus, per_level_bonus), (.5, 4))
        machine.mem_write(0xbc1d09, b'\xe9' + struct.pack('<i', universe_base + 0x37d10 - 0xbc1d09 - 5))
        machine.ctl_remove_cache(0xbc1b90, 0xbc1e86)
        hero_boundaries.update({0x2010600: (30, None), 0x2010700: (3, None),
                                0x2010800: (descriptor, None), 0x2010e00: (1, 123)})
        machine.mem_write(history + 0x1c, struct.pack('<2I', history_records, history_records + 16))
        machine.mem_write(history_records, struct.pack('<4I', 66, 77, 20, 88))
        universe_cases = 0
        for target_argument, level in ((target_argument, level) for target_argument in (0, target)
                                       for level in (1, 2, 5, 7, 10, 20, 30, 31, 40, 60)):
            for level_bonus in (False, True):
                for specialization in (0, 73):
                    for half_enabled in (False, True):
                        for offender in (False, True):
                            for per_level_enabled in (False, True):
                                hero_boundaries.update({
                                    0x2010000: (level, None),
                                    0x2010100: ({0x41: int(level_bonus), 91: int(half_enabled)}, None),
                                    0x2010300: (specialization, None),
                                    0x2010400: ({74: int(offender), 17: int(per_level_enabled)}, None)})
                                machine.mem_write(holder + 8, struct.pack('<I', 1))
                                machine.mem_write(stack, struct.pack('<3I', stop, 0, target_argument))
                                machine.reg_write(UC_X86_REG_ESP, stack)
                                machine.reg_write(UC_X86_REG_ECX, hero + 0xa0)
                                machine.reg_write(UC_X86_REG_FPCW, 0xc7f)
                                machine.emu_start(0xbc1b90, stop, count=10000)
                                value = single_chop(high[2] - low[2])
                                value = single_chop(value * (level + 3 * level_bonus - 1))
                                value = single_chop(value * factor)
                                value = single_chop(value + low[2])
                                damage = int(single_chop(value * (23 if target_argument else 30)))
                                if specialization == 73:damage += damage // 2
                                if target_argument and level_bonus:damage = max(2 * damage, 20)
                                bonus = single_chop(damage * half_bonus) if half_enabled else 0
                                if offender:
                                    term = single_chop(single_chop(level * coefficient) * damage)
                                    bonus = single_chop(term + bonus)
                                if per_level_enabled:
                                    bonus = single_chop(single_chop(level * per_level_bonus) + bonus)
                                expected = max(1, int(single_chop(damage + bonus)))
                                self.assertEqual(machine.reg_read(UC_X86_REG_EAX), expected,
                                                 (target_argument, level, level_bonus, specialization, half_enabled,
                                                  offender, per_level_enabled))
                                self.assertEqual(machine.reg_read(UC_X86_REG_FPCW), 0xc7f)
                                self.assertEqual(struct.unpack('<I', machine.mem_read(holder + 8, 4))[0], 1)
                                universe_cases += 1
        self.assertEqual(universe_cases, 640)
        # Owner174 Universe patch: artifact91 increases skill2 mastery.
        # Execute original artifact search and original final0..4 clamp.
        self.assertEqual(struct.unpack_from('<I', universe_data, 0xbc44c)[0], 0xca6680)
        self.assertEqual(struct.unpack_from('<I', universe_data, 0xbc450)[0], 0xb4d181)
        self.assertEqual(struct.unpack_from('<I', universe_data, 0xbd4dc)[0], 91)
        machine.mem_write(owner_methods + 0x258, struct.pack('<I', 0x201d000))
        hero_boundaries[0x201d000] = (1, None)  # External owner class; native class1 maps to skill13.
        artifact_vector, artifact_base, artifact_objects = 0x201e000, 0x201e800, 0x201f000
        machine.mem_write(artifact_base, struct.pack('<2I', 0, 0))
        artifact_cases = ((), ((90, 0),), ((91, 0),), ((91, 0x80),),
                          ((91, 0), (91, 0)), (None, (91, 0)),
                          ((90, 0), (91, 0x80), (91, 0)), ((91, 0), (15, 0)))
        mastery_cases = 0
        for artifacts in artifact_cases:
            for index, artifact in enumerate(artifacts):
                address = artifact_objects + index * 128 if artifact is not None else 0
                machine.mem_write(artifact_vector + index * 4, struct.pack('<I', address))
                if artifact is not None:
                    record = bytearray(64)
                    struct.pack_into('<I', record, 4, artifact_base)
                    struct.pack_into('<I', record, 0x28, artifact[0]);record[0xb] = artifact[1]
                    machine.mem_write(address, bytes(record))
            machine.mem_write(owner + 0x18, struct.pack('<2I', artifact_vector,
                                                       artifact_vector + len(artifacts) * 4))
            for mastery in (-1, 0, 1, 3, 4, 5):
                for skill in (1, 2, 13, 91):
                    machine.mem_write(stack, struct.pack('<5I', 0, 0, 0, stop, skill))
                    machine.reg_write(UC_X86_REG_ESP, stack)
                    machine.reg_write(UC_X86_REG_EAX, mastery & 0xffffffff)
                    machine.reg_write(UC_X86_REG_EBX, skill);machine.reg_write(UC_X86_REG_ESI, owner)
                    machine.reg_write(UC_X86_REG_FPCW, 0xc7f)
                    machine.emu_start(universe_base + 0x23480, stop, count=10000)
                    active = {artifact[0] for artifact in artifacts
                              if artifact is not None and not artifact[1] & 0x80}
                    expected = mastery + int(skill == 2 and 91 in active) + int(skill == 13 and 15 in active)
                    if expected < 0 or expected > 4:expected = 0
                    self.assertEqual(machine.reg_read(UC_X86_REG_EAX), expected, (artifacts, mastery, skill))
                    self.assertEqual(machine.reg_read(UC_X86_REG_FPCW), 0xc7f)
                    mastery_cases += 1
        self.assertEqual(mastery_cases, 192)
        # Nonzero action dispatch: real single-enum owner specialization.
        machine.mem_write(owner_methods + 0x190, struct.pack('<I', 0xb4b5a0))
        machine.mem_write(hero + 0xb0, struct.pack('<I', owner))
        machine.mem_write(history + 0x1c, struct.pack('<2I', history_records, history_records + 16))
        machine.mem_write(history_records, struct.pack('<4I', 66, 77, 20, 88))
        action_cases = 0
        for action in (1, 52, 53, 54, 56, 60, 61, 62, 291, 292, 293, 305, 306):
            for jousting_coefficient in ((-1, 0, .03, 150) if action == 53 else (.03,)):
                jousting_coefficient = struct.unpack('<f', struct.pack('<f', jousting_coefficient))[0]
                machine.mem_write(settings + 0x810, struct.pack('<f', jousting_coefficient))
                for level in (1, 7, 31):
                    for target_argument in (0, target):
                        for specialization in (0, 3, 17, 74):
                            machine.mem_write(owner + 0x8c, struct.pack('<I', specialization))
                            for absolute_charge in (False, True):
                                for level_bonus in (False, True):
                                    hero_boundaries.update({
                                        0x2010000: (level, None),
                                        0x2010100: ({65: int(level_bonus), 85: int(absolute_charge), 91: 0}, None),
                                        0x2010300: (specialization, None)})
                                    machine.mem_write(holder + 8, struct.pack('<I', 1))
                                    machine.mem_write(stack, struct.pack('<3I', stop, action, target_argument))
                                    machine.reg_write(UC_X86_REG_ESP, stack)
                                    machine.reg_write(UC_X86_REG_ECX, hero + 0xa0)
                                    machine.reg_write(UC_X86_REG_FPCW, 0xc7f)
                                    machine.emu_start(0xbc1b90, stop, count=10000)
                                    damage = 0
                                    if action in (53, 56, 61, 292, 305):
                                        effective_level = level + (0 if action == 292 else 3)
                                        value = single_chop(high[2] - low[2])
                                        value = single_chop(value * (effective_level - 1))
                                        value = single_chop(value * factor)
                                        value = single_chop(value + low[2])
                                        damage = int(single_chop(value * (23 if target_argument else 30)))
                                    if action == 53:
                                        if specialization == 3:
                                            clamped = min(100, max(0, jousting_coefficient))
                                            multiplier = single_chop(single_chop(clamped * level) + 1)
                                            damage = int(single_chop(multiplier * damage))
                                        if absolute_charge:damage *= 3
                                    bonus = 0
                                    if specialization == 74:
                                        bonus = single_chop(single_chop(level * coefficient) * damage)
                                    elif specialization == 17:
                                        bonus = single_chop(level * per_level_bonus)
                                    expected = max(1, int(single_chop(damage + bonus)))
                                    self.assertEqual(machine.reg_read(UC_X86_REG_EAX), expected,
                                                     (action, jousting_coefficient, level, target_argument,
                                                      specialization, absolute_charge, level_bonus))
                                    self.assertEqual(machine.reg_read(UC_X86_REG_FPCW), 0xc7f)
                                    self.assertEqual(struct.unpack('<I', machine.mem_read(holder + 8, 4))[0], 1)
                                    action_cases += 1
        self.assertEqual(action_cases, 1536)
        universe.close()
        executable.close()

    def test_owned_area_spell_power_matches_original_four_and_ten_turn_paths(self):
        import pefile
        from unicorn import UC_HOOK_CODE
        source = preview_source()
        calculation = 'struct AreaSpellInput {' + source.split('struct AreaSpellInput {', 1)[1].split(
            '// Initial-state arithmetic', 1)[0]
        driver = r'''
#include <cstdint>
#include <iostream>
CALCULATION
int main() {
    int baseline, resources, horizon, areaOnly; uint32_t count;
    while (std::cin >> baseline >> resources >> horizon >> areaOnly >> count) {
        AreaSpellInput spells[32]{};
        for (uint32_t index=0;index<count;++index) {
            auto& spell=spells[index];
            std::cin >> spell.identifier >> spell.usable >> spell.areaAllowed >> spell.damaging
                >> spell.excluded >> spell.damage >> spell.limited >> spell.charges >> spell.cost;
        }
        std::cout << CalculateAreaSpellPower(baseline,resources,horizon,areaOnly!=0,spells,count) << '\n';
    }
}
'''.replace('CALCULATION', calculation)
        game = WORKSPACE / '.local/test-game/bin/H5_Game.exe'
        self.assertEqual(hashlib.sha256(game.read_bytes()).hexdigest(), probe.HASHES['H5_Game.exe'])
        pe = pefile.PE(str(game))
        base = pe.OPTIONAL_HEADER.ImageBase
        cpu = Uc(UC_ARCH_X86, UC_MODE_32)
        cpu.mem_map(base, (pe.OPTIONAL_HEADER.SizeOfImage + 4095) & ~4095)
        cpu.mem_write(base, pe.get_memory_mapped_image())
        cpu.mem_map(0x2000000, 65536)
        actor, table, vector, entries, stack, stop = 0x2001000, 0x2002000, 0x2003000, 0x2004000, 0x2008000, 0x2009000
        cpu.mem_write(actor, struct.pack('<I', table))
        methods = {0x78: 0x2006000, 0x234: 0x2006010, 0x248: 0x2006020, 0x220: 0x2006030, 8: 0x2006040}
        for offset, address in methods.items(): cpu.mem_write(table + offset, struct.pack('<I', address))
        cpu.mem_write(0x2006100, struct.pack('<I', 0x2006200))
        cpu.mem_write(0x2006208, struct.pack('<I', 0x2006050))
        current = {}
        def supply_primitive(cpu, address, size, data):
            result, popped = None, 0
            index = (cpu.reg_read(UC_X86_REG_EDI) - entries) // 20
            spell = current['spells'][index] if 0 <= index < len(current['spells']) else [0] * 9
            if address == methods[0x78]: result = 0x2006100 if current['has_baseline'] else 0
            elif address == methods[0x234]: result = current['resources']
            elif address == methods[0x248]: result = vector
            elif address == methods[0x220]: result, popped = spell[1], 4
            elif address == methods[8]: result = 0x2001000
            elif address == 0x2006050:
                sp = cpu.reg_read(UC_X86_REG_ESP)
                self.assertEqual(struct.unpack('<2I', cpu.mem_read(sp + 4, 8)), (0, 0))
                current['baseline_calls'] += 1
                result, popped = current['baseline'], 8
            elif address == 0xa34670: result = spell[2]
            elif address == 0x982be0:
                sp = cpu.reg_read(UC_X86_REG_ESP)
                self.assertEqual(struct.unpack('<I', cpu.mem_read(sp + 4, 4))[0], cpu.reg_read(UC_X86_REG_EDI))
                result, popped = spell[3], 4
            elif address == 0x9785e0: result = spell[4]
            elif address == 0x977c80: result, popped = spell[5], 4
            elif address == 0xa34470: result = spell[6]
            elif address == 0xa34490:
                result = 0x2006300
                cpu.mem_write(result + 0x20, struct.pack('<i', spell[7]))
            elif address == 0x9781e0: result, popped = spell[8], 4
            if result is not None:
                sp = cpu.reg_read(UC_X86_REG_ESP)
                destination = struct.unpack('<I', cpu.mem_read(sp, 4))[0]
                cpu.reg_write(UC_X86_REG_EAX, result & 0xffffffff)
                cpu.reg_write(UC_X86_REG_ESP, sp + 4 + popped)
                cpu.reg_write(UC_X86_REG_EIP, destination)
        cpu.hook_add(UC_HOOK_CODE, supply_primitive)
        generator = random.Random(20261004)
        fixtures = [(0, 0, []), (24, 0, []), (-3, -5, []),
                    (0, 1, [[1, 1, 1, 1, 0, 97, 0, 0, 1]])]
        for index in range(120):
            spells = []
            for spellIndex in range(1 + index % 5):
                spells.append([generator.choice((1, 2, 0xa2, 0x13c)),
                               generator.randrange(2), generator.randrange(2), generator.randrange(2),
                               generator.randrange(2), generator.choice((-100, 0, 1, 24, 97, 2147483647)),
                               generator.randrange(2), generator.choice((-1, 0, 1, 3, 4, 10, 100)),
                               generator.choice((-2, 0, 1, 5, 100))])
            fixtures.append((generator.choice((-3, 0, 24, 100)), generator.choice((-1, 0, 1, 7, 1000)), spells))
        # Explicit eligible cases exercise casts, wrap, excluded IDs and competing maxima.
        for damage in (-100, 1, 24, 97, 2147483647):
            for limited in (0, 1):
                for budget in (-1, 0, 1, 3, 4, 10, 100):
                    fixtures.append((24, budget, [[1, 1, 1, 1, 0, damage, limited, budget, 1]]))
        payload, expected = [], []
        for baseline, resources, spells in fixtures:
            for horizon, areaOnly in ((4, 1), (10, 0), (4, 0), (10, 1)):
                current.update(baseline=baseline, resources=resources, spells=spells,
                               has_baseline=baseline != 0, baseline_calls=0)
                cpu.mem_write(vector, struct.pack('<3I', entries, entries + 20 * len(spells), entries + 20 * len(spells)))
                for index, spell in enumerate(spells):
                    cpu.mem_write(entries + index * 20, struct.pack('<5I', 0, spell[0], 0, 0, 0))
                cpu.mem_write(stack, struct.pack('<3I', stop, horizon, areaOnly))
                cpu.reg_write(UC_X86_REG_ESP, stack)
                cpu.reg_write(UC_X86_REG_ESI, actor)
                cpu.emu_start(0xbfa360, stop, count=20000)
                self.assertEqual(current['baseline_calls'], int(baseline != 0))
                result = cpu.reg_read(UC_X86_REG_EAX)
                expected.append(result - 0x100000000 if result & 0x80000000 else result)
                words = [baseline, resources, horizon, areaOnly, len(spells)]
                for spell in spells: words.extend(spell)
                payload.append(' '.join(map(str, words)))
        self.assertEqual(expected[12:16], [24, 9, 24, 9])
        with tempfile.TemporaryDirectory(prefix='workshop-area-spells-') as directory:
            folder = Path(directory)
            (folder / 'area.cpp').write_text(driver, encoding='utf-8')
            (folder / 'build.cmd').write_text(f'@call "{vcvarsall()}" x86 >nul\n@if errorlevel 1 exit /b 1\n'
                                            '@cl /nologo /EHsc /O2 /std:c++20 /Fe:area.exe area.cpp\n', encoding='utf-8')
            built = subprocess.run(['cmd', '/d', '/c', str(folder / 'build.cmd')], cwd=folder, capture_output=True)
            self.assertEqual(built.returncode, 0, built.stdout.decode(errors='replace') + built.stderr.decode(errors='replace'))
            completed = subprocess.run([str(folder / 'area.exe')], input='\n'.join(payload) + '\n', text=True, capture_output=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(list(map(int, completed.stdout.split())), expected)

    def test_owned_spread_denominator_matches_original_power_and_conditional_extra(self):
        import pefile
        from unicorn.x86_const import UC_X86_REG_FPCW
        source = preview_source()
        aggregate = 'struct PlacementAggregate {' + source.split('struct PlacementAggregate {', 1)[1].split(
            'struct BaselineActionFactorInput {', 1)[0]
        calculation = 'int CalculatePlacementPower(' + source.split('int CalculatePlacementPower(', 1)[1].split(
            'void NormalizePlacementAggregate(', 1)[0]
        driver = r'''
#include <cstdint>
#include <iostream>
AGGREGATE
CALCULATION
int main() {
    uint32_t words[36], increaseBits, decreaseBits, control;
    while (std::cin >> control >> increaseBits >> decreaseBits) {
        for (auto& word : words) std::cin >> word;
        const auto& own = *reinterpret_cast<const PlacementAggregate*>(words);
        const auto& enemy = *reinterpret_cast<const PlacementAggregate*>(words + 18);
        const float increase = *reinterpret_cast<float*>(&increaseBits);
        const float decrease = *reinterpret_cast<float*>(&decreaseBits);
        uint16_t original, captured = static_cast<uint16_t>(control);
        __asm fnstcw original
        __asm fldcw captured
        const int total = CalculatePlacementPower(own, enemy, increase, decrease, false);
        const int ranged = CalculatePlacementPower(own, enemy, increase, decrease, true);
        uint16_t after;
        __asm fnstcw after
        const int defensiveTotal = CalculateDefensivePower(own, enemy, increase, decrease, false);
        const int defensiveRanged = CalculateDefensivePower(own, enemy, increase, decrease, true);
        __asm fnstcw after
        __asm fldcw original
        std::cout << total << ' ' << ranged << ' ' << defensiveTotal << ' ' << defensiveRanged << ' ' << after << '\n';
    }
}
'''.replace('AGGREGATE', aggregate).replace('CALCULATION', calculation)
        pe = pefile.PE(str(WORKSPACE / '.local/test-game/bin/H5_Game.exe'))
        base = pe.OPTIONAL_HEADER.ImageBase
        cpu = Uc(UC_ARCH_X86, UC_MODE_32)
        cpu.mem_map(base, (pe.OPTIONAL_HEADER.SizeOfImage + 4095) & ~4095)
        cpu.mem_write(base, pe.get_memory_mapped_image())
        cpu.mem_map(0x2000000, 65536)
        own, enemy, settings, stack, stop = 0x2001000, 0x2002000, 0x2003000, 0x2008000, 0x2009000
        cpu.mem_write(0xbcb3f0, bytes(keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32).asm(
            f'mov eax,{settings}; ret', 0xbcb3f0)[0]))
        bits = lambda value: struct.unpack('<I', struct.pack('<f', value))[0]
        generator = random.Random(20261003)
        pairs = []
        for index in range(160):
            pair = []
            for side in range(2):
                damage = generator.choice((0, 1, 40, 50, 9999, 2147483))
                words = [generator.randrange(40), generator.randrange(100), generator.randrange(50), damage,
                         bits(generator.choice((-2.5, 0, 4.525, 6.2, 50.99999))),
                         bits(generator.choice((0, 1, 1.147644, 1.486641, 3.5))),
                         100, bits(7.5), 100,
                         bits(generator.choice((-2.5, 0, 7.11888, 7.999999, 30))),
                         bits(generator.choice((0, 0.5, 18.408852, 1000))),
                         bits(generator.choice((0, 6, 12.75))),
                         bits(generator.choice((0, 1, 20))), bits(4),
                         bits(generator.choice((1, 56.629536, 100))), bits(6),
                         generator.randrange(40), 0]
                pair.append(words)
            pairs.append(pair)
        # Defensive total refuses negative/oversized subtotals before adding magic.
        for fixed_extra in (0x70000000, 0x70000001, 0x80000000, 0xffffffff):
            first = [fixed_extra, 0, 0, 0, bits(1), bits(1), 0, bits(1), 0, bits(1),
                     bits(0), bits(1), bits(0), bits(1), bits(0), bits(1), 3, 0]
            pairs.append([first, list(first)])
        report = WORKSPACE / '.local/test-state/accuracy-campaign-20261003T074143Z-9312-rmg_b-admin.json'
        if report.exists():
            for run in json.loads(report.read_text(encoding='utf-8'))['runs']:
                words = run['battles'][0]['hidden_source_pre_start']['owned_actor_inputs']['core_aggregate_words']
                pairs.extend((words, list(reversed(words))))
        payload, expected = [], []
        for control in (0x027f, 0x0c7f):
            for index, pair in enumerate(pairs):
                increase, decrease = ((0.05, 0.05), (0, -0.1), (0.125, 0.025))[index % 3]
                cpu.mem_write(settings + 0x1d0, struct.pack('<f', increase))
                cpu.mem_write(settings + 0x1d8, struct.pack('<f', decrease))
                cpu.mem_write(own, struct.pack('<18I', *pair[0]))
                cpu.mem_write(enemy, struct.pack('<18I', *pair[1]))
                results = []
                for entry in (0xbfa1b0, 0xbf9cc0, 0xbfc4a0, 0xbf9d30):
                    cpu.mem_write(stack, struct.pack('<2I', stop, enemy))
                    cpu.reg_write(UC_X86_REG_ESP, stack)
                    cpu.reg_write(UC_X86_REG_ECX, own)
                    cpu.reg_write(UC_X86_REG_FPCW, control)
                    cpu.emu_start(entry, stop, count=10000)
                    result = cpu.reg_read(UC_X86_REG_EAX)
                    results.append(result - 0x100000000 if result & 0x80000000 else result)
                    self.assertEqual(cpu.reg_read(UC_X86_REG_FPCW), control)
                expected.append(results + [control])
                payload.append(' '.join(map(str, [control, bits(increase), bits(decrease)] + pair[0] + pair[1])))
        with tempfile.TemporaryDirectory(prefix='workshop-spread-power-') as directory:
            folder = Path(directory)
            (folder / 'power.cpp').write_text(driver, encoding='utf-8')
            (folder / 'build.cmd').write_text(f'@call "{vcvarsall()}" x86 >nul\n@if errorlevel 1 exit /b 1\n'
                                            '@cl /nologo /EHsc /O2 /std:c++20 /Fe:power.exe power.cpp\n', encoding='utf-8')
            built = subprocess.run(['cmd', '/d', '/c', str(folder / 'build.cmd')], cwd=folder, capture_output=True)
            self.assertEqual(built.returncode, 0, built.stdout.decode(errors='replace') + built.stderr.decode(errors='replace'))
            completed = subprocess.run([str(folder / 'power.exe')], input='\n'.join(payload) + '\n', capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            actual = [list(map(int, row.split())) for row in completed.stdout.splitlines()]
            for index, (ours, native) in enumerate(zip(actual, expected)):
                self.assertEqual(ours, native, f"case={index} input={payload[index]}")
            self.assertEqual(len(actual), len(expected))

    def test_special_damage_category_matches_original_flags_and_exclusion_priority(self):
        import pefile,itertools
        from unicorn import UC_HOOK_CODE
        text=preview_source()
        calculation='unsigned SelectPlacementDamageCategory(' + text.split('unsigned SelectPlacementDamageCategory(',1)[1].split('// category:',1)[0]
        pe=pefile.PE(str(WORKSPACE/'.local/test-game/bin/H5_Game.exe'));base=pe.OPTIONAL_HEADER.ImageBase
        cpu=Uc(UC_ARCH_X86,UC_MODE_32);cpu.mem_map(base,(pe.OPTIONAL_HEADER.SizeOfImage+4095)&~4095)
        cpu.mem_write(base,pe.get_memory_mapped_image());cpu.mem_map(0x2000000,65536)
        actor,table,stack=0x2001000,0x2002000,0x2008000
        cpu.mem_write(actor,struct.pack('<I',table))
        assembler=keystone.Ks(keystone.KS_ARCH_X86,keystone.KS_MODE_32)
        target={0xbfbbf3:3,0xbfbbc8:0,0xbfbb62:1,0xbfbb95:2};selected=[]
        def stop(cpu,address,size,data):
            if address in target:selected.append(target[address]);cpu.emu_stop()
        cpu.hook_add(UC_HOOK_CODE,stop)
        cases=[]
        for excluded,shooter,flying,special,flag37,flag5 in itertools.product((0,1),repeat=6):
            selected.clear()
            for offset,result in ((0x7c,0x2007000 if excluded else 0),(0x1e0,shooter),(0x190,flying)):
                address=0x2003000+offset*8
                cpu.mem_write(table+offset,struct.pack('<I',address))
                cpu.mem_write(address,bytes(assembler.asm(f'mov eax,{result}; ret',address)[0]))
                cpu.ctl_remove_cache(address,address+32)
            cpu.mem_write(0x2007000,struct.pack('<I',0x2007100));cpu.mem_write(0x2007100,struct.pack('<I',0x2007200))
            cpu.mem_write(0x2007200,bytes(assembler.asm('mov eax,0x2007300; ret',0x2007200)[0]))
            cpu.mem_write(0x200731c,struct.pack('<I',2));cpu.mem_write(table+0x28c,struct.pack('<I',0x2007400))
            flags=f'cmp dword ptr [esp+4],0x37; jne second; mov eax,{flag37}; ret 4; second: mov eax,{flag5}; ret 4'
            cpu.mem_write(0x2007400,bytes(assembler.asm(flags,0x2007400)[0]));cpu.ctl_remove_cache(0x2007400,0x2007480)
            cpu.mem_write(stack+0x30,struct.pack('<I',special));cpu.mem_write(stack+0x24,struct.pack('<f',1.0))
            cpu.reg_write(UC_X86_REG_ESP,stack);cpu.reg_write(UC_X86_REG_ESI,actor);cpu.reg_write(UC_X86_REG_ECX,actor)
            cpu.emu_start(0xbfbb12,0xbfbc00,count=1000)
            self.assertEqual(len(selected),1)
            cases.append((excluded,shooter,flying,special,int(flag37 and flag5),selected[0]))
        driver='#include <cassert>\n'+calculation+'\nint main(){\n'
        for case in cases:driver+='assert(SelectPlacementDamageCategory('+','.join(map(str,case[:5]))+')=='+str(case[5])+');\n'
        driver+='}\n'
        with tempfile.TemporaryDirectory(prefix='workshop-category-') as directory:
            folder=Path(directory);(folder/'category.cpp').write_text(driver,encoding='utf8')
            (folder/'build.cmd').write_text(f'@call "{vcvarsall()}" x86 >nul\n@if errorlevel 1 exit /b 1\n'
                                           '@cl /nologo /EHsc /O2 /std:c++20 /Fe:category.exe category.cpp\n',encoding='utf8')
            built=subprocess.run(['cmd','/d','/c',str(folder/'build.cmd')],cwd=folder,capture_output=True)
            self.assertEqual(built.returncode,0,built.stdout.decode(errors='replace')+built.stderr.decode(errors='replace'))
            completed=subprocess.run([str(folder/'category.exe')],capture_output=True)
            self.assertEqual(completed.returncode,0,completed.stderr.decode(errors='replace'))
    def test_split_simple_cells_match_original_whole_uniform_placement(self):
        import pefile,itertools
        from unicorn import UC_HOOK_CODE
        text=preview_source()
        calculation='int ChooseSourceSimpleCell() {'+text.split('int ChooseSourceSimpleCell() {',1)[1].split('bool FinalizeSourceSimplePlan(',1)[0]
        driver=r'''
#include <cstdint>
#include <cstring>
#include <iostream>
bool g_sourceSimpleLayout=true,g_projectionPlanning=true;unsigned char g_outputStorage[4104]{};
int g_sourceSimpleColumns=2,g_sourceFallbackCells[4]{};
uint32_t g_definitionMaximum=0;
int ChooseSourceFallbackCell() { return -1; } // This fixture isolates original857380; fallback has its own native oracle.
void* g_creatureDefinition=nullptr;int g_plannedProjectionCount=0;
uint32_t g_orderedPublicTypes[7]{};uint32_t definitions[3][80]{};
const uint32_t* __fastcall Definition(uint32_t type) { return definitions[type]; }
const uintptr_t kCreatureDefinition=reinterpret_cast<uintptr_t>(&Definition);
CALCULATION
int main() {
    int height,count,blockedCount;
    definitions[1][0xdc/4]=1;definitions[2][0xdc/4]=2;
    while(std::cin>>height>>count>>blockedCount) {
        memset(g_outputStorage,0,sizeof(g_outputStorage));g_plannedProjectionCount=count;
        *reinterpret_cast<int*>(g_outputStorage+8+384)=16;
        *reinterpret_cast<int*>(g_outputStorage+8+388)=height;
        *reinterpret_cast<int*>(g_outputStorage+8+524)=2;
        for(int index=0;index<count;++index) std::cin>>g_orderedPublicTypes[index];
        for(int index=0;index<blockedCount;++index) {
            int column,row;std::cin>>column>>row;
            const int x=13-column,y=row+1;
            g_outputStorage[8+1536+y*2+x/8]|=1<<(x&7);
        }
        for(int index=0;index<count;++index) {
            const int size=g_orderedPublicTypes[index];g_creatureDefinition=reinterpret_cast<void*>(size);
            const int result=ChooseSourceSimpleCell();std::cout<<result<<' ';
            if(result<0) continue;
            const int x=result>>8,y=result&255;
            for(int dy=0;dy<size;++dy) for(int dx=0;dx<size;++dx)
                g_outputStorage[8+1536+(y-dy)*2+(x-dx)/8]|=1<<((x-dx)&7);
        }
        std::cout<<'\n';
    }
}
'''.replace('CALCULATION',calculation)
        pe=pefile.PE(str(WORKSPACE/'.local/test-game/bin/H5_Game.exe'));base=pe.OPTIONAL_HEADER.ImageBase
        cpu=Uc(UC_ARCH_X86,UC_MODE_32);cpu.mem_map(base,(pe.OPTIONAL_HEADER.SizeOfImage+4095)&~4095)
        cpu.mem_write(base,pe.get_memory_mapped_image());cpu.mem_map(0x2000000,65536)
        context,table,cells,vector,descriptors,stack,stop=0x2001000,0x2002000,0x2003000,0x2004000,0x2005000,0x2008000,0x2009000
        sizes={}
        def supply_definition(cpu,address,size,data):
            if address==0x89fbf0:
                pointer=0x200a000+cpu.reg_read(UC_X86_REG_ECX)*512
                cpu.reg_write(UC_X86_REG_EAX,pointer)
                sp=cpu.reg_read(UC_X86_REG_ESP);destination=struct.unpack('<I',cpu.mem_read(sp,4))[0]
                cpu.reg_write(UC_X86_REG_ESP,sp+4);cpu.reg_write(UC_X86_REG_EIP,destination)
        cpu.hook_add(UC_HOOK_CODE,supply_definition)
        for size in (1,2):cpu.mem_write(0x200a000+size*512+0xdc,struct.pack('<I',size))
        expected,payload=[],[]
        armies=((1,),(1,1),(1,1,1),(1,1,1,1),(2,),(2,2),(1,2,1),(2,1,2))
        for height,army,blocked in itertools.product((8,12),armies,((),((0,2),),((0,4),(1,4)),tuple((c,r) for c in (0,1) for r in range(10)))):
            rows=height-2;blocked=tuple((c,r) for c,r in blocked if r<rows)
            cpu.mem_write(context,bytes(128));cpu.mem_write(context+8,struct.pack('<3I',table,2,rows))
            cpu.mem_write(context+0x15,b'\x01');cpu.mem_write(context+0x18,struct.pack('<2I',16,height))
            cpu.mem_write(vector,struct.pack('<3I',descriptors,descriptors+len(army)*36,descriptors+len(army)*36))
            cpu.mem_write(descriptors,bytes(7*36))
            for row in range(rows):
                cpu.mem_write(table+row*4,struct.pack('<I',cells+row*2));cpu.mem_write(cells+row*2,bytes(2))
            for column,row in blocked:cpu.mem_write(cells+row*2+column,b'\x01')
            for index,size in enumerate(army):cpu.mem_write(descriptors+index*36+0x1c,struct.pack('<I',size))
            cpu.mem_write(stack,struct.pack('<2I',stop,vector));cpu.reg_write(UC_X86_REG_ESP,stack);cpu.reg_write(UC_X86_REG_ECX,context)
            cpu.emu_start(0x857380,stop,count=50000)
            result=[]
            for index in range(len(army)):
                record=bytes(cpu.mem_read(descriptors+index*36,36))
                x,y=struct.unpack_from('<2i',record,20);result.append((x<<8)|y if record[16] else -1)
            expected.append(result)
            payload.append(' '.join(map(str,(height,len(army),len(blocked),*army,*[value for pair in blocked for value in pair]))))
        with tempfile.TemporaryDirectory(prefix='workshop-simple-cells-') as directory:
            folder=Path(directory);(folder/'cells.cpp').write_text(driver,encoding='utf8')
            (folder/'build.cmd').write_text(f'@call "{vcvarsall()}" x86 >nul\n@if errorlevel 1 exit /b 1\n'
                                           '@cl /nologo /EHsc /O2 /std:c++20 /Fe:cells.exe cells.cpp\n',encoding='utf8')
            built=subprocess.run(['cmd','/d','/c',str(folder/'build.cmd')],cwd=folder,capture_output=True)
            self.assertEqual(built.returncode,0,built.stdout.decode(errors='replace')+built.stderr.decode(errors='replace'))
            result=subprocess.run([str(folder/'cells.exe')],input='\n'.join(payload),text=True,capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual([list(map(int,line.split())) for line in result.stdout.splitlines()],expected)

    def test_source_simple_selector_uses_fallback_cache_after_partial_failure(self):
        source = preview_source()
        implementation = 'bool CalculateSourceFallbackCells(' + source.split('bool CalculateSourceFallbackCells(', 1)[1].split('bool __fastcall PublicPlacementPairBefore(', 1)[0]
        driver = r'''
#include <cstdint>
#include <cstring>
#include <cassert>
#include <climits>
using LONG=long;
bool g_sourceSimpleLayout=true,g_sourceFallbackPrepared=false,g_projectionPlanning=true;
LONG g_publicCount=3;
uint32_t g_predictionExcludedMask=0;
int g_cell[14]{};
int g_sourceSimpleColumns=2,g_sourceFallbackCells[4]{},g_plannedProjectionCount=3;
unsigned char g_outputStorage[4104]{};
uint32_t g_definitionMaximum=0,g_orderedPublicTypes[7]{1,1,1};
void* g_creatureDefinition=reinterpret_cast<void*>(1);
int definition[80]{};
const int* __fastcall Definition(uint32_t) { return definition; }
const uintptr_t kCreatureDefinition=reinterpret_cast<uintptr_t>(&Definition);
IMPLEMENTATION
int main() {
 definition[0xdc/4]=1;definition[0x4c/4]=1;
 *reinterpret_cast<int*>(g_outputStorage+8+384)=16;
 *reinterpret_cast<int*>(g_outputStorage+8+388)=12;
 *reinterpret_cast<int*>(g_outputStorage+8+524)=2;
 for(int row=2;row<10;++row) for(int column=0;column<2;++column) {
  const int x=13-column,y=row+1;g_outputStorage[8+1536+y*2+x/8]|=1<<(x&7);
 }
 const int expected[3]={(13<<8)|2,(13<<8)|1,(12<<8)|1};
 for(uint32_t slot=0;slot<3;++slot) {
  g_definitionMaximum=slot;const int cell=ChooseSourceSimpleCell();assert(cell==expected[slot]);
  const int x=cell>>8,y=cell&255;g_outputStorage[8+1536+y*2+x/8]|=1<<(x&7);
  *reinterpret_cast<uint32_t*>(g_outputStorage+8+908)|=1u<<slot;
 }
 assert(g_sourceFallbackPrepared);
 for(int slot=0;slot<3;++slot) {
  g_cell[slot*2]=expected[slot]>>8;g_cell[slot*2+1]=expected[slot]&255;
 }
 *reinterpret_cast<uint32_t*>(g_outputStorage+8+496)=3;
 assert(FinalizeSourceSimplePlan());assert(g_plannedProjectionCount==3);assert(g_predictionExcludedMask==0);
 g_projectionPlanning=false;g_sourceFallbackPrepared=false;
 for(uint32_t slot=0;slot<3;++slot) {
  g_definitionMaximum=slot;assert(ChooseSourceSimpleCell()==expected[slot]);
 }
 // Preserve source slots0/2 and their quantities without recalculating rows
 // for the shorter render order, even when slot1 never found a free cell.
 g_orderedPublicTypes[0]=1;g_orderedPublicTypes[1]=2;g_orderedPublicTypes[2]=3;
 auto quantities=reinterpret_cast<uint32_t*>(g_outputStorage+8+832);
 quantities[0]=10;quantities[1]=20;quantities[2]=30;
 *reinterpret_cast<uint32_t*>(g_outputStorage+8+908)=5;
 *reinterpret_cast<uint32_t*>(g_outputStorage+8+496)=2;
 g_cell[0]=13;g_cell[1]=2;g_cell[2]=12;g_cell[3]=1;
 assert(FinalizeSourceSimplePlan());assert(g_plannedProjectionCount==2);assert(g_predictionExcludedMask==2);
 assert(g_orderedPublicTypes[0]==1&&g_orderedPublicTypes[1]==3);
 assert(quantities[0]==10&&quantities[1]==30);
 g_definitionMaximum=0;assert(ChooseSourceSimpleCell()==((13<<8)|2));
 g_definitionMaximum=1;assert(ChooseSourceSimpleCell()==((12<<8)|1));
 *reinterpret_cast<uint32_t*>(g_outputStorage+8+908)=0;
 assert(!FinalizeSourceSimplePlan());
}
'''.replace('IMPLEMENTATION', implementation)
        with tempfile.TemporaryDirectory(prefix='workshop-simple-fallback-cache-') as directory:
            folder=Path(directory);(folder/'cache.cpp').write_text(driver,encoding='utf-8')
            (folder/'build.cmd').write_text(f'@call "{vcvarsall()}" x86 >nul\n@if errorlevel 1 exit /b 1\n@cl /nologo /EHsc /O2 /std:c++20 /Fe:cache.exe cache.cpp\n',encoding='utf-8')
            result=subprocess.run(['cmd','/d','/c',str(folder/'build.cmd')],cwd=folder,capture_output=True)
            self.assertEqual(result.returncode,0,result.stdout.decode(errors='replace')+result.stderr.decode(errors='replace'))
            result=subprocess.run([str(folder/'cache.exe')],capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr.decode(errors='replace'))

    def test_source_fallback_matches_native_mixed_column_passes(self):
        import pefile, random
        from unicorn import UC_HOOK_CODE
        source = preview_source()
        implementation = 'bool CalculateSourceFallbackCells(' + source.split('bool CalculateSourceFallbackCells(', 1)[1].split('int ChooseSourceFallbackCell()', 1)[0]
        driver = r'''
#include <cstdint>
#include <cstring>
#include <iostream>
IMPLEMENTATION
int main() {
 int columns,count,blocked;unsigned placed;
 while(std::cin>>columns>>count>>placed>>blocked) {
  int sizes[7],output[7];bool shooters[7];unsigned char occupancy[24]{};
  for(int index=0;index<count;++index) { int type;std::cin>>type;sizes[index]=(type-1)%2+1;shooters[index]=type>=3; }
  for(int index=0;index<blocked;++index) { int column,row;std::cin>>column>>row;int x=13-column,y=row+1;occupancy[y*2+x/8]|=1<<(x&7); }
  if(!CalculateSourceFallbackCells(16,12,columns,sizes,shooters,count,placed,occupancy,2,output)) return 2;
  for(int index=0;index<count;++index) std::cout<<output[index]<<' ';
  std::cout<<'\n';
 }
}
'''.replace('IMPLEMENTATION', implementation)
        executable = pefile.PE(str(WORKSPACE / '.local/test-game/bin/H5_Game.exe'))
        machine = Uc(UC_ARCH_X86, UC_MODE_32); base = executable.OPTIONAL_HEADER.ImageBase
        machine.mem_map(base, (executable.OPTIONAL_HEADER.SizeOfImage + 4095) & ~4095)
        machine.mem_write(base, executable.get_memory_mapped_image()); machine.mem_map(0x2000000, 65536)
        context, table, cells, vector, records, stack, stop = 0x2001000,0x2002000,0x2003000,0x2004000,0x2005000,0x2008000,0x2009000
        for creature in range(1,5):
            pointer = 0x200a000 + creature*256
            machine.mem_write(pointer+0xdc, struct.pack('<I',(creature-1)%2+1))
            machine.mem_write(pointer+0x4c, struct.pack('<I',int(creature>=3)))
        def boundary(emulator,address,size,data):
            arguments=0
            if address==0x89fbf0:
                emulator.reg_write(UC_X86_REG_EAX,0x200a000+emulator.reg_read(UC_X86_REG_ECX)*256)
            elif address==0x858ba0:
                arguments=4  # Copy order established separately; no placement decisions replaced.
            else:return
            pointer=emulator.reg_read(UC_X86_REG_ESP);destination=struct.unpack('<I',emulator.mem_read(pointer,4))[0]
            emulator.reg_write(UC_X86_REG_ESP,pointer+4+arguments);emulator.reg_write(UC_X86_REG_EIP,destination)
        machine.hook_add(UC_HOOK_CODE,boundary)
        generator=random.Random(859930);payload=[];expected=[]
        for case in range(240):
            columns=2+case%2;count=1+case%7;types=[generator.randrange(1,5) for _ in range(count)]
            placed=generator.randrange(1<<count)
            blocked=[(column,row) for column in range(columns) for row in range(10) if generator.random()<.35]
            machine.mem_write(context,bytes(512));machine.mem_write(context+8,struct.pack('<3I',table,columns,10))
            machine.mem_write(context+0x18,struct.pack('<2I',16,12));machine.mem_write(context+0x20,bytes([columns==3]))
            machine.mem_write(context+0x34,struct.pack('<I',vector));machine.mem_write(context+0xf0,struct.pack('<I',vector))
            machine.mem_write(vector,struct.pack('<3I',records,records+count*36,records+count*36))
            for row in range(10):machine.mem_write(table+row*4,struct.pack('<I',cells+row*columns));machine.mem_write(cells+row*columns,bytes(columns))
            for column,row in blocked:machine.mem_write(cells+row*columns+column,b'\x01')
            for index,creature in enumerate(types):
                machine.mem_write(records+index*36,bytes(36));machine.mem_write(records+index*36+0x1c,struct.pack('<I',creature))
                machine.mem_write(records+index*36+0x10,bytes([bool(placed&(1<<index))]))
            machine.mem_write(stack,struct.pack('<I',stop));machine.reg_write(UC_X86_REG_ESP,stack);machine.reg_write(UC_X86_REG_ECX,context)
            machine.emu_start(0x859930,stop,count=50000)
            results=[]
            for index in range(count):
                record=bytes(machine.mem_read(records+index*36,36));x,y=struct.unpack_from('<2i',record,20)
                results.append((x<<8)|y if record[16] and not placed&(1<<index) else -1)
            expected.append(results);payload.append(' '.join(map(str,(columns,count,placed,len(blocked),*types,*[v for pair in blocked for v in pair]))))
        with tempfile.TemporaryDirectory(prefix='workshop-source-fallback-') as directory:
            folder=Path(directory);(folder/'fallback.cpp').write_text(driver,encoding='utf-8')
            (folder/'build.cmd').write_text(f'@call "{vcvarsall()}" x86 >nul\n@if errorlevel 1 exit /b 1\n@cl /nologo /EHsc /O2 /std:c++20 /Fe:fallback.exe fallback.cpp\n',encoding='utf-8')
            built=subprocess.run(['cmd','/d','/c',str(folder/'build.cmd')],cwd=folder,capture_output=True)
            self.assertEqual(built.returncode,0,built.stdout.decode(errors='replace')+built.stderr.decode(errors='replace'))
            result=subprocess.run([str(folder/'fallback.exe')],input='\n'.join(payload),capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual([list(map(int,line.split())) for line in result.stdout.splitlines()],expected)
        executable.close()

    def test_native_simple_failure_keeps_partial_cells_and_fallback_fills_front_rows(self):
        import pefile
        from unicorn import UC_HOOK_CODE
        executable = pefile.PE(str(WORKSPACE / '.local/test-game/bin/H5_Game.exe'))
        base = executable.OPTIONAL_HEADER.ImageBase
        machine = Uc(UC_ARCH_X86, UC_MODE_32)
        machine.mem_map(base, (executable.OPTIONAL_HEADER.SizeOfImage + 4095) & ~4095)
        machine.mem_write(base, executable.get_memory_mapped_image())
        machine.mem_map(0x2000000, 65536)
        context, table, cells, vector, records = 0x2001000, 0x2002000, 0x2003000, 0x2004000, 0x2005000
        stack, stop, definition = 0x2008000, 0x2009000, 0x200a000
        machine.mem_write(context, bytes(512))
        machine.mem_write(context + 8, struct.pack('<3I', table, 2, 10))
        machine.mem_write(context + 0x15, b'\x01')
        machine.mem_write(context + 0x18, struct.pack('<2I', 16, 12))
        machine.mem_write(context + 0x34, struct.pack('<I', vector))
        machine.mem_write(context + 0xf0, struct.pack('<I', vector))
        machine.mem_write(vector, struct.pack('<3I', records, records + 108, records + 108))
        for row in range(10):
            machine.mem_write(table + row * 4, struct.pack('<I', cells + row * 2))
            machine.mem_write(cells + row * 2, b'\x00\x00' if row < 2 else b'\x01\x01')
        for index in range(3):
            machine.mem_write(records + index * 36, bytes(36))
            machine.mem_write(records + index * 36 + 0x1c, struct.pack('<I', 1))
        machine.mem_write(definition + 0xdc, struct.pack('<I', 1))
        def boundary(emulator, address, size, data):
            arguments = 0
            if address == 0x89fbf0:
                emulator.reg_write(UC_X86_REG_EAX, definition)
            elif address == 0x4d89f0:
                emulator.reg_write(UC_X86_REG_EAX, 1)  # Three identical ranged 1x1 records.
            elif address == 0x858ba0:
                arguments = 4  # Native record-copy boundary, source order preserved.
            else:
                return
            pointer = emulator.reg_read(UC_X86_REG_ESP)
            destination = struct.unpack('<I', emulator.mem_read(pointer, 4))[0]
            emulator.reg_write(UC_X86_REG_ESP, pointer + 4 + arguments)
            emulator.reg_write(UC_X86_REG_EIP, destination)
        machine.hook_add(UC_HOOK_CODE, boundary)
        machine.mem_write(stack, struct.pack('<2I', stop, vector))
        machine.reg_write(UC_X86_REG_ESP, stack); machine.reg_write(UC_X86_REG_ECX, context)
        machine.emu_start(0x857380, stop, count=50000)
        self.assertEqual(machine.reg_read(UC_X86_REG_EAX) & 255, 0)
        self.assertEqual([machine.mem_read(records + index * 36 + 16, 1)[0] for index in range(3)], [1, 0, 0])
        first = bytes(machine.mem_read(records, 36))
        machine.mem_write(stack, struct.pack('<I', stop))
        machine.reg_write(UC_X86_REG_ESP, stack); machine.reg_write(UC_X86_REG_ECX, context)
        machine.emu_start(0x859930, stop, count=50000)
        self.assertEqual(bytes(machine.mem_read(records, 36)), first)
        self.assertEqual([machine.mem_read(records + index * 36 + 16, 1)[0] for index in range(3)], [1, 1, 1])
        self.assertEqual([struct.unpack('<2i', machine.mem_read(records + index * 36 + 20, 8))
                          for index in range(3)], [(13, 2), (13, 1), (12, 1)])
        executable.close()

    def test_reference_geometry_entry_preserves_visible_model_ownership(self):
        from unicorn import UC_HOOK_CODE
        source = preview_source()
        assembly = 'source_ready:' + source.split('    source_ready:', 1)[1].split(
            '        mov eax, dword ptr [esp + 44]', 1)[0]
        assembly += '\nresume: jmp 0x306000'
        assembly = '\n'.join(line.split('//', 1)[0] for line in assembly.splitlines())
        assembly = re.sub(r'offset g_outputStorage((?: \+ \d+)*)',
                          lambda match: hex(0x303000 + sum(map(int, re.findall(r'\d+', match[1])))), assembly)
        symbols = {'g_outputStorage': '0x303000', 'g_publicCount': '0x302000',
                   'g_superadminEnabled': '0x302004', 'g_placementGeneration': '0x302008',
                   'g_renderedGeneration': '0x30200c', 'g_renderCalls': '0x302010'}
        for symbol, address in symbols.items():
            assembly = assembly.replace(symbol, address)
        code = bytes(keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32).asm(assembly, 0x300000)[0])
        for geometry_only in (False, True):
            with self.subTest(geometry_only=geometry_only):
                machine = Uc(UC_ARCH_X86, UC_MODE_32)
                machine.mem_map(0x300000, 65536)
                machine.mem_map(0x576000, 4096)
                machine.mem_write(0x300000, code)
                machine.mem_write(0x302000, struct.pack('<5I', 2, 1, 17, 16, 6))
                machine.mem_write(0x303008 + 1364, struct.pack('<I', geometry_only))
                machine.mem_write(0x303008 + 728, struct.pack('<I', 1234))
                machine.reg_write(UC_X86_REG_EDI, 5678)
                machine.reg_write(UC_X86_REG_ESP, 0x30f000)
                releases = []

                def boundary(emulator, address, size, unused):
                    if address == 0x306000:
                        emulator.emu_stop()
                    elif address == 0x576b40:
                        releases.append(emulator.reg_read(UC_X86_REG_ECX))
                        stack = emulator.reg_read(UC_X86_REG_ESP)
                        destination = struct.unpack('<I', emulator.mem_read(stack, 4))[0]
                        emulator.reg_write(UC_X86_REG_ESP, stack + 4)
                        emulator.reg_write(UC_X86_REG_EIP, destination)

                machine.hook_add(UC_HOOK_CODE, boundary)
                machine.emu_start(0x300000, 0x306000, count=1000)
                self.assertEqual(len(releases), 0 if geometry_only else 7)
                self.assertEqual(struct.unpack('<2I', machine.mem_read(0x30200c, 8)),
                                 (16, 6) if geometry_only else (17, 7))
                self.assertEqual(struct.unpack('<I', machine.mem_read(0x303008 + 728, 4))[0],
                                 1234 if geometry_only else 5678)
                self.assertEqual(struct.unpack('<4I', machine.mem_read(0x303008 + 976, 16)), (1, 17, 0, 0))

    def test_rendered_slot_identity_is_retained_in_direct_and_planned_paths(self):
        source = preview_source()
        assembly = 'cell_selected:' + source.split('    cell_selected:', 1)[1].split('    decision_record_ready:', 1)[0]
        assembly += '\ndecision_record_ready: jmp 0x306000'
        assembly = '\n'.join(line.split('//', 1)[0] for line in assembly.splitlines())
        assembly = re.sub(r'offset g_outputStorage((?: \+ \d+)*)',
            lambda match: hex(0x303000 + sum(map(int, re.findall(r'\d+', match[1])))), assembly)
        symbols = {'g_outputStorage': '0x303000', 'g_cell': '0x305000',
            'g_projectionPlanning': '0x302000', 'g_definitionMaximum': '0x302004',
            'g_creatureDefinition': '0x302008', 'g_candidateIdentity': '0x30200c',
            'g_predictedDefensive': '0x302010', 'g_useSpreadRows': '0x302011'}
        for symbol, address in symbols.items():
            assembly = assembly.replace(symbol, address)
        code = bytes(keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32).asm(assembly, 0x300000)[0])
        for planned in (False, True):
            with self.subTest(planned=planned):
                machine = Uc(UC_ARCH_X86, UC_MODE_32)
                machine.mem_map(0x300000, 65536)
                machine.mem_write(0x300000, code)
                machine.mem_write(0x302000, struct.pack('<4I2B', planned, 5, 2, 1, 0, 1))
                machine.mem_write(0x303008 + 496, struct.pack('<I', 2))
                machine.mem_write(0x303008 + 1368, b'\xff' * 28)
                machine.reg_write(UC_X86_REG_ESP, 0x308000)
                machine.reg_write(UC_X86_REG_EDX, 0x305010)
                machine.reg_write(UC_X86_REG_ESI, 13)
                machine.reg_write(UC_X86_REG_EDI, 2)
                machine.emu_start(0x300000, 0x306000, count=1000)
                self.assertEqual(struct.unpack('<I', machine.mem_read(0x303008 + 1376, 4))[0], 5)
                self.assertEqual(struct.unpack('<I', machine.mem_read(0x303008 + 984, 4))[0], 3 if planned else 0)
                self.assertEqual(machine.reg_read(UC_X86_REG_ESP), 0x308000)
                self.assertEqual(machine.reg_read(UC_X86_REG_EDX), 0x305010)

    def test_exhausted_spread_keeps_stack_for_native_residual_column_pass(self):
        import pefile
        from unicorn import UC_HOOK_CODE
        game = WORKSPACE / '.local/test-game/bin/H5_Game.exe'
        self.assertEqual(hashlib.sha256(game.read_bytes()).hexdigest(), probe.HASHES['H5_Game.exe'])
        executable = pefile.PE(str(game))
        machine = Uc(UC_ARCH_X86, UC_MODE_32)
        machine.mem_map(executable.OPTIONAL_HEADER.ImageBase,
                        (executable.OPTIONAL_HEADER.SizeOfImage + 4095) & ~4095)
        machine.mem_write(executable.OPTIONAL_HEADER.ImageBase, executable.get_memory_mapped_image())
        machine.mem_map(0x2000000, 65536)
        context, table, cells, vector, record = 0x2001000, 0x2002000, 0x2003000, 0x2004000, 0x2005000
        pending, candidates, candidate_vector = 0x2006000, 0x2007000, 0x2007100
        stack, stop, definition = 0x2008000, 0x2009000, 0x200a000
        machine.mem_write(context + 8, struct.pack('<3I', table, 2, 10))
        machine.mem_write(context + 0x18, struct.pack('<2I', 16, 12))
        machine.mem_write(context + 0x34, struct.pack('<I', vector))
        machine.mem_write(context + 0xf0, struct.pack('<I', vector))
        machine.mem_write(vector, struct.pack('<3I', record, record + 36, record + 36))
        machine.mem_write(record + 0x1c, struct.pack('<I', 1))
        machine.mem_write(definition + 0xdc, struct.pack('<I', 1))
        # Generation1194, immediately before Peasant40: six earlier stacks.
        occupied = {(13, 1), (13, 2), (12, 3), (13, 3), (12, 4), (13, 4),
                    (13, 6), (12, 10), (12, 5)}
        for row in range(10):
            machine.mem_write(table + row * 4, struct.pack('<I', cells + row * 2))
            machine.mem_write(cells + row * 2, bytes(int((13-column, row+1) in occupied)
                                                     for column in range(2)))
        machine.mem_write(pending, struct.pack('<3I', pending + 16, pending + 20, pending + 20))
        machine.mem_write(pending + 16, struct.pack('<I', record))
        machine.mem_write(candidates, struct.pack('<4I', 1, 4, 1, 9))
        machine.mem_write(candidate_vector, struct.pack('<3I', candidates, candidates + 16, candidates + 16))

        def primitive_boundary(emulator, address, size, unused):
            argument_bytes = 0
            if address == 0x89fbf0:
                emulator.reg_write(UC_X86_REG_EAX, definition)
            elif address == 0x4d89f0:
                emulator.reg_write(UC_X86_REG_EAX, 0)  # Peasant has no physical shot.
            elif address == 0x858ba0:
                argument_bytes = 4  # Existing record-copy boundary.
            else:
                return
            pointer = emulator.reg_read(UC_X86_REG_ESP)
            destination = struct.unpack('<I', emulator.mem_read(pointer, 4))[0]
            emulator.reg_write(UC_X86_REG_ESP, pointer + 4 + argument_bytes)
            emulator.reg_write(UC_X86_REG_EIP, destination)

        machine.hook_add(UC_HOOK_CODE, primitive_boundary)
        machine.mem_write(stack, struct.pack('<3I', stop, pending, candidate_vector))
        machine.reg_write(UC_X86_REG_ESP, stack)
        machine.reg_write(UC_X86_REG_ECX, context)
        machine.emu_start(0x857880, stop, count=50000)
        self.assertEqual(machine.mem_read(record + 16, 1)[0], 0,
                         'Exhausted selected rows must leave the record unplaced')
        # Extended dispatcher8598e0 visits column0 before column1, unlike the
        # independent simple-layout fallback859930.
        machine.mem_write(stack, struct.pack('<4I', stop, vector, 0, 0))
        machine.reg_write(UC_X86_REG_ESP, stack)
        machine.reg_write(UC_X86_REG_ECX, context)
        machine.emu_start(0x857780, stop, count=50000)
        self.assertEqual(machine.mem_read(record + 16, 1)[0], 1)
        self.assertEqual(struct.unpack('<2I', machine.mem_read(record + 20, 8)), (13, 5))
        executable.close()

        source = preview_source()
        assembly = 'rank_done:' + source.split('    rank_done:', 1)[1].split('    rank_selected:', 1)[0]
        assembly += '\nrank_selected: jmp 0x306000\nnext_model: jmp 0x306100\nrank_next: jmp 0x306200'
        assembly = '\n'.join(line.split('//', 1)[0] for line in assembly.splitlines())
        for symbol, address in {'g_outputStorage': '0x303000', 'g_useSpreadRows': '0x302000',
                                'g_spreadFallback': '0x302001', 'g_superadminEnabled': '0x302002'}.items():
            assembly = assembly.replace(symbol, address)
        code = bytes(keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32).asm(assembly, 0x300000)[0])
        for admin, destination in ((1, 0x306100), (0, 0x306200)):
            with self.subTest(superadmin=admin):
                translated = Uc(UC_ARCH_X86, UC_MODE_32)
                translated.mem_map(0x300000, 65536)
                translated.mem_write(0x300000, code)
                translated.mem_write(0x302000, bytes((1, 0, admin)))
                translated.mem_write(0x303008 + 744, struct.pack('<i', -1))
                translated.hook_add(UC_HOOK_CODE, lambda emulator, address, size, unused:
                                    emulator.emu_stop() if address in (0x306000, 0x306100, 0x306200) else None)
                translated.emu_start(0x300000, destination, count=1000)
                self.assertEqual(translated.reg_read(UC_X86_REG_EIP), destination)
                self.assertEqual(translated.mem_read(0x302001, 1)[0], 0 if admin else 1)

    def test_protective_placement_matches_original_candidates_and_footprints(self):
        import pefile
        import random
        from unicorn import UC_HOOK_CODE
        game = WORKSPACE / '.local/test-game/bin/H5_Game.exe'
        self.assertEqual(hashlib.sha256(game.read_bytes()).hexdigest(), probe.HASHES['H5_Game.exe'])
        executable = pefile.PE(str(game))
        machine = Uc(UC_ARCH_X86, UC_MODE_32)
        machine.mem_map(executable.OPTIONAL_HEADER.ImageBase,
                        (executable.OPTIONAL_HEADER.SizeOfImage + 4095) & ~4095)
        machine.mem_write(executable.OPTIONAL_HEADER.ImageBase, executable.get_memory_mapped_image())
        machine.mem_map(0x2000000, 0x40000)
        context, table, cells, pending, records = 0x2001000, 0x2002000, 0x2003000, 0x2004000, 0x2005000
        weights, weight_values, pointers = 0x2006000, 0x2006100, 0x2006200
        stack, stop = 0x2008000, 0x2009000
        allocation = [0x2010000]
        footprint = [1]

        def primitive_boundary(emulator, address, size, unused):
            if address not in (0x8791f0, 0x879240, 0x4d89d0):
                return
            pointer = emulator.reg_read(UC_X86_REG_ESP)
            returned = struct.unpack('<I', emulator.mem_read(pointer, 4))[0]
            if address == 0x8791f0:
                length = struct.unpack('<I', emulator.mem_read(pointer + 4, 4))[0]
                self.assertLess(allocation[0] + length, 0x2040000)
                emulator.reg_write(UC_X86_REG_EAX, allocation[0])
                allocation[0] += (length + 15) & ~15
            elif address == 0x4d89d0:
                emulator.reg_write(UC_X86_REG_EAX, footprint[0])
            emulator.reg_write(UC_X86_REG_ESP, pointer + 4)
            emulator.reg_write(UC_X86_REG_EIP, returned)

        machine.hook_add(UC_HOOK_CODE, primitive_boundary)
        cases, expected = [], []
        generator = random.Random(1194)
        for height in (8, 12):
            rows = height - 2
            masks = [0, (1 << (rows * 2)) - 1]
            masks += [generator.getrandbits(rows * 2) for _ in range(14)]
            for window in (0, rows - 1):
                for window_length in (1, 3):
                    selected = {(window + index) % rows for index in range(window_length)}
                    row_weights = [2 if row in selected else 1 if row-1 in selected or row+1 in selected else 0
                                   for row in range(rows)]
                    for size in (1, 2):
                        for count in (1, 3):
                            for mask in masks:
                                footprint[0] = size
                                allocation[0] = 0x2010000
                                machine.mem_write(context, bytes(512))
                                machine.mem_write(context + 8, struct.pack('<3I', table, 2, rows))
                                machine.mem_write(context + 0x18, struct.pack('<2I', 16, height))
                                for row in range(rows):
                                    machine.mem_write(table + row * 4, struct.pack('<I', cells + row * 2))
                                    machine.mem_write(cells + row * 2, bytes((mask >> (row * 2 + column)) & 1
                                                                          for column in range(2)))
                                machine.mem_write(records, bytes(36 * count))
                                machine.mem_write(pointers, struct.pack('<' + str(count) + 'I',
                                                                       *(records + index * 36 for index in range(count))))
                                machine.mem_write(pending, struct.pack('<3I', pointers, pointers + count * 4,
                                                                      pointers + count * 4))
                                machine.mem_write(weights, struct.pack('<I', weight_values))
                                machine.mem_write(weight_values, struct.pack('<' + str(rows) + 'I', *row_weights))
                                machine.mem_write(stack, struct.pack('<3I', stop, pending, weights))
                                machine.reg_write(UC_X86_REG_ESP, stack)
                                machine.reg_write(UC_X86_REG_ECX, context)
                                machine.emu_start(0x857cc0, stop, count=200000)
                                self.assertEqual(machine.reg_read(UC_X86_REG_EIP), stop)
                                result = []
                                for index in range(count):
                                    placed = machine.mem_read(records + index * 36 + 16, 1)[0]
                                    result.extend(struct.unpack('<2i', machine.mem_read(records + index * 36 + 20, 8))
                                                  if placed else (-1, -1))
                                cases.append((height, window, window_length, size, count, mask))
                                expected.append(result)
        executable.close()
        source = preview_source()
        implementation = 'void PrepareProtectiveCandidates() {' + source.split('void PrepareProtectiveCandidates() {', 1)[1].split(
            'bool PlacementHasPhysicalShot(uint32_t type) {', 1)[0]
        driver = r'''
#include <cstdint>
#include <cstring>
#include <iostream>
int g_protectiveCellCount=0, g_protectiveCells[120]{};
unsigned char g_outputStorage[4104]{};
bool g_superadminEnabled=true;
void* g_creatureDefinition=nullptr;
''' + implementation + r'''
int main() {
    int height,window,length,size,count; uint32_t mask;
    while(std::cin>>height>>window>>length>>size>>count>>mask) {
        memset(g_outputStorage,0,sizeof(g_outputStorage));
        *reinterpret_cast<int*>(g_outputStorage+8+384)=16;
        *reinterpret_cast<int*>(g_outputStorage+8+388)=height;
        *reinterpret_cast<int*>(g_outputStorage+8+524)=2;
        *reinterpret_cast<int*>(g_outputStorage+8+784)=window;
        *reinterpret_cast<int*>(g_outputStorage+8+796)=length;
        for(int row=0;row<height-2;++row)for(int column=0;column<2;++column) {
            const int x=13-column;
            if(mask&(1u<<(row*2+column)))g_outputStorage[8+1536+(row+1)*2+x/8]|=1<<(x&7);
        }
        g_creatureDefinition=reinterpret_cast<void*>(size);
        PrepareProtectiveCandidates();
        for(int index=0;index<count;++index) {
            const int cell=ChooseProtectiveCell();
            if(cell<0) { std::cout<<"-1 -1 "; continue; }
            const int x=cell>>8,y=cell&255;
            std::cout<<x<<' '<<y<<' ';
            for(int row=y-size+1;row<=y;++row)for(int column=x-size+1;column<=x;++column)
                g_outputStorage[8+1536+row*2+column/8]|=1<<(column&7);
        }
        std::cout<<'\n';
    }
}
'''
        with tempfile.TemporaryDirectory(prefix='workshop-protective-oracle-') as directory:
            folder = Path(directory)
            (folder / 'protective.cpp').write_text(driver, encoding='utf-8')
            (folder / 'build.cmd').write_text(f'@call "{vcvarsall()}" x86 >nul\n@if errorlevel 1 exit /b 1\n'
                                             '@cl /nologo /EHsc /O2 /std:c++20 /Fe:protective.exe protective.cpp\n', encoding='utf-8')
            built = subprocess.run(['cmd', '/d', '/c', str(folder / 'build.cmd')], cwd=folder, capture_output=True)
            self.assertEqual(built.returncode, 0, built.stdout.decode(errors='replace') + built.stderr.decode(errors='replace'))
            completed = subprocess.run([str(folder / 'protective.exe')], input='\n'.join(' '.join(map(str, case)) for case in cases),
                                       text=True, capture_output=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            actual = [list(map(int, line.split())) for line in completed.stdout.splitlines()]
            self.assertEqual(len(actual), len(expected))
            for case, own, native in zip(cases, actual, expected):
                with self.subTest(height=case[0], window=case[1], length=case[2], footprint=case[3], count=case[4], mask=case[5]):
                    self.assertEqual(own, native)

    def test_runic_contribution_matches_original_descriptor_states(self):
        import itertools
        import pefile
        from unicorn import UC_HOOK_CODE
        from unicorn.x86_const import UC_X86_REG_FPCW
        game = WORKSPACE / '.local/test-game/bin/H5_Game.exe'
        self.assertEqual(hashlib.sha256(game.read_bytes()).hexdigest(), probe.HASHES['H5_Game.exe'])
        executable = pefile.PE(str(game))
        machine = Uc(UC_ARCH_X86, UC_MODE_32)
        machine.mem_map(executable.OPTIONAL_HEADER.ImageBase,
                        (executable.OPTIONAL_HEADER.SizeOfImage + 4095) & ~4095)
        machine.mem_write(executable.OPTIONAL_HEADER.ImageBase, executable.get_memory_mapped_image())
        machine.mem_map(0x2000000, 65536)
        actor, methods, vector, descriptors = 0x2001000, 0x2002000, 0x2003000, 0x2005000
        stack, stop, output, definitions = 0x2008000, 0x2009000, 0x200c000, 0x200d000
        machine.mem_write(actor, struct.pack('<I', methods))
        machine.mem_write(methods + 0x248, struct.pack('<I', 0x200a000))
        machine.mem_write(0x200a000, b'\xb8' + struct.pack('<I', vector) + b'\xc3')
        machine.mem_write(stop, b'\xd9\x1d' + struct.pack('<I', output))

        def primitive_boundary(emulator, address, size, unused):
            if address not in (0x41a5c0, 0x41a570, 0x879240, 0x41a040, 0x8496a0):
                return
            pointer = emulator.reg_read(UC_X86_REG_ESP)
            returned = struct.unpack('<I', emulator.mem_read(pointer, 4))[0]
            arguments = 0
            if address == 0x41a5c0:
                # Descriptor-vector copy is a lifetime boundary, not scoring.
                source = struct.unpack('<I', emulator.mem_read(pointer + 4, 4))[0]
                destination = emulator.reg_read(UC_X86_REG_ECX)
                emulator.mem_write(destination, bytes(emulator.mem_read(source, 12)))
                emulator.reg_write(UC_X86_REG_EAX, destination)
                arguments = 4
            elif address == 0x41a040:
                descriptor = emulator.reg_read(UC_X86_REG_ECX)
                state = struct.unpack('<I', emulator.mem_read(descriptor + 8, 4))[0]
                emulator.reg_write(UC_X86_REG_EAX, state)
            elif address == 0x8496a0:
                spell = emulator.reg_read(UC_X86_REG_ECX)
                emulator.reg_write(UC_X86_REG_EAX, definitions + (spell - 1) * 256)
            emulator.reg_write(UC_X86_REG_ESP, pointer + 4 + arguments)
            emulator.reg_write(UC_X86_REG_EIP, returned)

        machine.hook_add(UC_HOOK_CODE, primitive_boundary)
        properties = ((5, 0), (5, 1), (5, 2), (5, 3), (0, 0), (6, 0))
        combinations = [items for count in range(4) for items in itertools.product(properties, repeat=count)]
        combinations += [((5,0),(5,1),(5,2),(5,3)), ((0,0),(6,0),(5,3),(5,1)), ((5,3),)*4]
        payload, expected = [], []
        for control in (0x037f, 0x0c7f):
            for items in combinations:
                machine.mem_write(vector, struct.pack('<3I', descriptors, descriptors + len(items) * 20,
                                                      descriptors + len(items) * 20))
                for index, (school, state) in enumerate(items):
                    machine.mem_write(descriptors + index * 20, struct.pack('<5I', 0, index + 1, state, 0, 0))
                    machine.mem_write(definitions + index * 256 + 0x88, struct.pack('<I', school))
                machine.mem_write(stack, struct.pack('<I', stop))
                machine.reg_write(UC_X86_REG_ESP, stack)
                machine.reg_write(UC_X86_REG_ECX, actor)
                machine.reg_write(UC_X86_REG_FPCW, control)
                machine.emu_start(0xbfb3d0, stop + 6, count=20000)
                self.assertEqual(machine.reg_read(UC_X86_REG_ESP), stack + 4)
                expected.append(struct.unpack('<I', machine.mem_read(output, 4))[0])
                payload.append(' '.join(map(str, (control, len(items), *(value for item in items for value in item)))))
        executable.close()
        header = (MOD_ROOT / 'src/placement_calculations.hpp').as_posix()
        driver = r'''
#include <windows.h>
#include <cstdint>
#include <cstring>
#include <iostream>
#include "HEADER"
int main() {
    uint32_t control,count;
    while(std::cin>>control>>count) {
        h5::army::ActorInput input{};input.aggregateIdentity=1;input.attackGeneration=2;input.controlWord=control;
        h5::army::AuxiliaryPowerInput rows[257]{};
        rows[0]={1,7,0,h5::army::ActorRunicDescriptorCount,control,2};uint32_t length=1;
        for(uint32_t index=0;index<count;++index) {
            int school,state;std::cin>>school>>state;
            if(school!=5)continue;
            ++rows[0].value;rows[length++]={1,7,state,h5::army::ActorRunicAvailability,control,2};
        }
        int32_t numerator=0,denominator=0;
        if(!h5_preview::ReadFrozenRunicContribution(input,7,rows,length,numerator,denominator))return 2;
        uint16_t selected=static_cast<uint16_t>(control);float fraction=0;
        __asm { fldcw selected }
        if(denominator) { __asm { fild numerator } __asm { fidiv denominator } __asm { fstp fraction } }
        uint32_t bits;memcpy(&bits,&fraction,sizeof(bits));std::cout<<bits<<'\n';
    }
}
'''.replace('HEADER', header)
        with tempfile.TemporaryDirectory(prefix='workshop-runic-descriptors-') as directory:
            folder = Path(directory);(folder / 'runic.cpp').write_text(driver, encoding='utf-8')
            (folder / 'build.cmd').write_text(f'@call "{vcvarsall()}" x86 >nul\n@if errorlevel 1 exit /b 1\n'
                                             '@cl /nologo /EHsc /O2 /std:c++20 /Fe:runic.exe runic.cpp\n', encoding='utf-8')
            built = subprocess.run(['cmd', '/d', '/c', str(folder / 'build.cmd')], cwd=folder, capture_output=True)
            self.assertEqual(built.returncode, 0, built.stdout.decode(errors='replace') + built.stderr.decode(errors='replace'))
            completed = subprocess.run([str(folder / 'runic.exe')], input='\n'.join(payload), text=True, capture_output=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            actual = [int(line) for line in completed.stdout.splitlines()]
            self.assertEqual(len(actual), len(expected))
            for case, own, native in zip(payload, actual, expected):
                with self.subTest(properties=case):self.assertEqual(own, native)

    def test_source_composition_matches_original_rng_grade_and_quantity_branches(self):
        import pefile,itertools
        from unicorn import UC_HOOK_CODE
        from unicorn.x86_const import UC_X86_REG_FPCW
        text=preview_source()
        implementation='uint32_t DrawSourceRandom(' + text.split('uint32_t DrawSourceRandom(',1)[1].split('struct PlacementAggregate {',1)[0]
        driver=r'''
#include <cstdint>
#include <cstring>
#include <iostream>
IMPLEMENTATION
int main() {
    int64_t own,enemy;uint32_t seed,word,quantity,upgradeCount;int size;
    uint32_t upgrades[2]{102,103},result[24];
    while(std::cin>>own>>enemy>>seed>>word>>quantity>>size>>upgradeCount) {
        if(!CalculateSourceComposition(own,enemy,seed,static_cast<uint16_t>(word),101,quantity,
                                       size,upgrades,upgradeCount,.5,1.0,result)) return 2;
        for(uint32_t value:result) std::cout<<value<<' ';
        std::cout<<'\n';
    }
}
'''.replace('IMPLEMENTATION',implementation)
        pe=pefile.PE(str(WORKSPACE/'.local/test-game/bin/H5_Game.exe'))
        base=pe.OPTIONAL_HEADER.ImageBase
        cpu=Uc(UC_ARCH_X86,UC_MODE_32);cpu.mem_map(base,(pe.OPTIONAL_HEADER.SizeOfImage+4095)&~4095)
        cpu.mem_write(base,pe.get_memory_mapped_image());cpu.mem_map(0x2000000,65536)
        stack,stop,random,vector,descriptor,definition,world=0x2008000,0x2003000,0x2002000,0x2004000,0x2005000,0x2006000,0x2007000
        cpu.mem_write(0x50c020,b'\xc3')
        cpu.mem_write(0x89fbf0,b'\xb8'+struct.pack('<I',definition)+b'\xc3')
        cpu.mem_write(0x2009000,b'\xb8'+struct.pack('<I',random)+b'\xc3')
        cpu.mem_write(world,struct.pack('<I',world+256));cpu.mem_write(world+256+12,struct.pack('<I',0x2009000))
        cpu.mem_write(vector,struct.pack('<I',descriptor));cpu.mem_write(descriptor+0x1c,struct.pack('<I',101))
        cpu.mem_write(0x200a000,struct.pack('<2I',102,103))
        cpu.mem_write(random,struct.pack('<I',0xe51284))
        observed={};stop_at=[0]
        def watch(cpu,address,size,data):
            if address==stop_at[0]:cpu.emu_stop();return
            if address in (0x8554c6,0x8554ef):observed[address]=cpu.reg_read(UC_X86_REG_EAX)
        cpu.hook_add(UC_HOOK_CODE,watch)
        assembler=keystone.Ks(keystone.KS_ARCH_X86,keystone.KS_MODE_32)
        setup=bytes(assembler.asm('fninit; fldcw word ptr [0x200b000]; fild qword ptr [0x200b008]; '
                                 'fild qword ptr [0x200b010]; fdivp st(1),st(0); '
                                 'fst qword ptr [0x200b018]; jmp 0x85541b',0x2001000)[0])
        cpu.mem_write(0x2001000,setup)
        payload,expected=[],[]
        pairs=((0,100),(49,100),(50,100),(99,100),(100,100),((1<<60)-1,1<<60),((1<<60)+1,1<<60))
        for (own,enemy),seed,word,quantity,size,upgrade_count in itertools.product(
                pairs,(0,1,2,3,4,123456789,0xffffffff),(0x37f,0xc7f),(1,4,5,30),(1,3),(0,1,2)):
            observed.clear();maximum=2 if size>2 else 4
            cpu.mem_write(0x200b000,struct.pack('<H',word));cpu.mem_write(0x200b008,struct.pack('<2q',own,enemy))
            cpu.reg_write(UC_X86_REG_EBP,maximum);cpu.reg_write(UC_X86_REG_ESP,stack)
            stop_at[0]=0x855444
            cpu.emu_start(0x2001000,0x855444,count=1000);initial=cpu.reg_read(UC_X86_REG_EDI)
            ratio=bytes(cpu.mem_read(0x200b018,8))
            cpu.mem_write(random+8,struct.pack('<I',seed));cpu.mem_write(stack,struct.pack('<3I',stop,1,100))
            cpu.reg_write(UC_X86_REG_ECX,random);cpu.reg_write(UC_X86_REG_ESP,stack)
            stop_at[0]=stop
            cpu.emu_start(0x8c04c0,stop,count=1000);roll=cpu.reg_read(UC_X86_REG_EAX)
            cpu.mem_write(stack+0x34,struct.pack('<I',vector));cpu.mem_write(stack+0x18,struct.pack('<I',descriptor))
            cpu.mem_write(stack+0x44,struct.pack('<I',world));cpu.mem_write(descriptor+0x20,struct.pack('<I',quantity))
            cpu.mem_write(definition+0x104,struct.pack('<2I',0x200a000,0x200a000+upgrade_count*4))
            cpu.reg_write(UC_X86_REG_ESP,stack);cpu.reg_write(UC_X86_REG_EBP,maximum)
            cpu.reg_write(UC_X86_REG_EDI,initial);cpu.reg_write(UC_X86_REG_EAX,roll);cpu.reg_write(UC_X86_REG_EBX,world)
            stop_at[0]=0x8554fb
            try:
                cpu.emu_start(0x85545c,0x8554fb,count=3000)
            except Exception as error:
                raise AssertionError((own,enemy,seed,word,quantity,size,upgrade_count,
                                      hex(cpu.reg_read(UC_X86_REG_EIP)),hex(cpu.reg_read(UC_X86_REG_ESP)),
                                      hex(cpu.reg_read(UC_X86_REG_EBP)))) from error
            final=struct.unpack('<I',cpu.mem_read(stack+0x48,4))[0]
            result=[1,*struct.unpack('<2I',struct.pack('<q',own)),*struct.unpack('<2I',struct.pack('<q',enemy)),
                    *struct.unpack('<2I',ratio),maximum,initial,roll,observed.get(0x8554c6,0),
                    observed.get(0x8554ef,0),final,struct.unpack('<I',cpu.mem_read(random+8,4))[0],word,0]
            for index in range(final):
                cpu.mem_write(stack+0x4c,struct.pack('<I',index));cpu.reg_write(UC_X86_REG_ESP,stack)
                stop_at[0]=0x855557
                cpu.emu_start(0x8554fb if index==0 else 0x85551e,0x855557,count=1000)
                result.extend((cpu.reg_read(UC_X86_REG_EDI),cpu.reg_read(UC_X86_REG_EBP)))
            result.extend([0]*(24-len(result)));expected.append(result)
            payload.append(' '.join(map(str,(own,enemy,seed,word,quantity,size,upgrade_count))))
        with tempfile.TemporaryDirectory(prefix='workshop-composition-') as directory:
            folder=Path(directory);(folder/'composition.cpp').write_text(driver,encoding='utf8')
            (folder/'build.cmd').write_text(f'@call "{vcvarsall()}" x86 >nul\n@if errorlevel 1 exit /b 1\n'
                                           '@cl /nologo /EHsc /O2 /std:c++20 /Fe:composition.exe composition.cpp\n',encoding='utf8')
            build=subprocess.run(['cmd','/d','/c',str(folder/'build.cmd')],cwd=folder,capture_output=True)
            self.assertEqual(build.returncode,0,build.stdout.decode(errors='replace')+build.stderr.decode(errors='replace'))
            completed=subprocess.run([str(folder/'composition.exe')],input='\n'.join(payload),text=True,capture_output=True)
            self.assertEqual(completed.returncode,0,completed.stderr)
            self.assertEqual([list(map(int,line.split())) for line in completed.stdout.splitlines()],expected)

    def test_source_strength_matches_original_staged_conversions(self):
        import pefile
        import itertools
        from unicorn import UC_HOOK_CODE
        from unicorn.x86_const import UC_X86_REG_FPCW
        source_text = preview_source()
        implementation = 'struct SourceStrengthInput {' + source_text.split(
            'struct SourceStrengthInput {', 1)[1].split('struct PlacementAggregate {', 1)[0]
        driver = r'''
#include <cstdint>
#include <cstring>
#include <iostream>
IMPLEMENTATION
int main() {
    unsigned word;
    while (std::cin >> word) {
        SourceStrengthInput input{};
        std::cin >> input.baseValue >> input.quantity;
        for (int& delta : input.deltas) std::cin >> delta;
        std::cin >> input.modifierA >> input.modifierB;
        uint32_t bits;
        for (uint32_t& word : input.initiativeBits) std::cin >> word;
        int bonus,penalty;
        std::cin >> input.baseInitiative >> bonus >> penalty;
        input.shooterBonus=bonus!=0; input.modifierPenalty=penalty!=0;
        for (float& coefficient : input.coefficients) {
            std::cin >> bits; memcpy(&coefficient,&bits,4);
        }
        input.baseScale=100.0; input.one=1.0;
        unsigned short original,selected=static_cast<unsigned short>(word),restored;
        __asm { fnstcw original }
        __asm { fldcw selected }
        const int64_t value=CalculateSourceStrength(input);
        __asm { fnstcw restored }
        __asm { fldcw original }
        std::cout << value << ' ' << restored << '\n';
    }
}
'''.replace('IMPLEMENTATION', implementation)
        executable = pefile.PE(str(WORKSPACE / '.local/test-game/bin/H5_Game.exe'))
        machine = Uc(UC_ARCH_X86, UC_MODE_32)
        image_base = executable.OPTIONAL_HEADER.ImageBase
        machine.mem_map(image_base, (executable.OPTIONAL_HEADER.SizeOfImage+4095)&~4095)
        machine.mem_write(image_base,executable.get_memory_mapped_image())
        machine.mem_map(0x2000000,65536)
        descriptor,definition,settings,stack,stop = 0x2001000,0x2002000,0x2003000,0x2008000,0x2004000
        context,context_table,owner,owner_table = 0x2007000,0x2007100,0x2006000,0x2006100
        machine.mem_write(context,struct.pack('<I',context_table))
        machine.mem_write(context_table+0x324,struct.pack('<I',0x2005000))
        machine.mem_write(context_table+0x54,struct.pack('<I',0x2005010))
        machine.mem_write(owner,struct.pack('<I',owner_table))
        machine.mem_write(owner_table+0x34,struct.pack('<I',0x2005020))
        machine.mem_write(0x4bc190,b'\xdb\x2d'+struct.pack('<I',descriptor+0x100)+b'\xc2\x08\x00')
        machine.mem_write(stop,b'\xdb\xe3')
        fixture = {}
        getters = {0x4bc470:('health',8),0x4bbfb0:('maximum',8),0x4bc020:('minimum',8),
                   0x4bb170:('attack',8),0x4bb2a0:('defence',8),
                   0x4bb3c0:('modifier_a',4),0x4bb3f0:('modifier_b',8)}
        def return_getter(cpu,arguments):
            pointer=cpu.reg_read(UC_X86_REG_ESP)
            address=struct.unpack('<I',cpu.mem_read(pointer,4))[0]
            cpu.reg_write(UC_X86_REG_ESP,pointer+4+arguments)
            cpu.reg_write(UC_X86_REG_EIP,address)
        def supply_input(cpu,address,size,data):
            if address in (0x89fbf0,0xc02a80,0x2005000,0x2005010,0x2005020):
                value = {0x89fbf0:definition,0xc02a80:settings,0x2005000:fixture['bonus'],
                         0x2005010:owner if fixture['penalty'] else 0,0x2005020:1}[address]
                cpu.reg_write(UC_X86_REG_EAX,value)
                return_getter(cpu,4 if address==0x2005020 else 0)
            elif address in getters:
                name,arguments=getters[address]
                cpu.reg_write(UC_X86_REG_EAX,fixture[name]&0xffffffff)
                return_getter(cpu,arguments)
            elif address==0xc0a200:
                return_getter(cpu,0)
            elif address==0xc0a2c0:
                pointer=cpu.reg_read(UC_X86_REG_ESP)
                destination=struct.unpack('<I',cpu.mem_read(pointer+4,4))[0]
                raw=bytearray(14)
                for offset,value in zip((8,9,12),fixture['extras']): raw[offset]=value&255
                cpu.mem_write(destination,bytes(raw)); return_getter(cpu,4)
        machine.hook_add(UC_HOOK_CODE,supply_input)
        coefficients = ([.5,.25,.5,.25,.5,.25,.25,.25,.5,.25,.5],
                        [.10000000149011612,.5,1,1,1,1,.10000000149011612,
                         .017299998551607132,.012199998833239079,
                         .017299998551607132,.08329999446868896])
        payload,expected = [],[]
        for coefficient_set,word,base_value,delta,modifiers,quantity,bonus,penalty in itertools.product(
                coefficients,(0x37f,0xc7f),(-5,1,7,100000,2147483647),
                (-3,0,5,16777217),((-2,-1),(0,0),(1,2)),(1,9),(0,1),(0,1)):
            fixture=dict(health=10+delta,maximum=5+delta,minimum=3,attack=4+delta,defence=6,
                         modifier_a=modifiers[0],modifier_b=modifiers[1],extras=(-2,1,3),bonus=bonus,penalty=penalty)
            machine.mem_write(descriptor+0x1c,struct.pack('<2i',1,quantity))
            initiative=8+delta
            exponent=initiative.bit_length()-1
            extended=struct.pack('<QH',initiative<<(63-exponent),16383+exponent)+bytes(2)
            machine.mem_write(descriptor+0x100,extended)
            for offset,value in [(0x84,base_value),(0x4c,bonus),(0x64,10),(0x54,5),(0x50,3),(0x44,4),(0x48,6),(0x5c,8)]:
                machine.mem_write(definition+offset,struct.pack('<i',value))
            for index,value in enumerate(coefficient_set):
                machine.mem_write(settings+0x250+index*4,struct.pack('<f',value))
            machine.emu_start(stop,stop+2)
            machine.mem_write(stack,struct.pack('<2I',stop,0))
            machine.reg_write(UC_X86_REG_ESP,stack);machine.reg_write(UC_X86_REG_ECX,descriptor)
            machine.reg_write(UC_X86_REG_EDX,context);machine.reg_write(UC_X86_REG_FPCW,word)
            machine.emu_start(0x4e9b90,stop,count=10000)
            value=machine.reg_read(UC_X86_REG_EAX)|(machine.reg_read(UC_X86_REG_EDX)<<32)
            expected.append((value if value<1<<63 else value-(1<<64),word))
            self.assertEqual(machine.reg_read(UC_X86_REG_ESP),stack+8)
            bits=lambda value:struct.unpack('<I',struct.pack('<f',value))[0]
            payload.append(' '.join(map(str,[word,base_value,quantity,delta,delta,delta,-2,1,3,
                                           *modifiers,*struct.unpack('<3I',extended),8,bonus,penalty,
                                           *map(bits,coefficient_set)])))
        # A value near eight can lose its fractional part if narrowed before
        # native FISUB. Compare both representations against the full original.
        precision_pairs = []
        for word,fraction_power,sign in itertools.product((0x37f,0xc7f),(30,40),(-1,1)):
            pair = []
            for preserve in (True,False):
                fixture=dict(health=10,maximum=5,minimum=3,attack=4,defence=6,
                             modifier_a=0,modifier_b=0,extras=(0,0,0),bonus=0,penalty=0)
                exponent=16386
                mantissa=1<<63
                if preserve and sign>0:
                    mantissa+=1<<(60-fraction_power)
                elif preserve:
                    # Below eight the normalized exponent decreases to two.
                    exponent=16385
                    mantissa=(1<<64)-(1<<(61-fraction_power))
                extended=struct.pack('<QH',mantissa,exponent)+bytes(2)
                machine.mem_write(descriptor+0x1c,struct.pack('<2i',1,1))
                machine.mem_write(descriptor+0x100,extended)
                for offset,value in [(0x84,2147483647),(0x4c,0),(0x64,10),(0x54,5),(0x50,3),(0x44,4),(0x48,6),(0x5c,8)]:
                    machine.mem_write(definition+offset,struct.pack('<i',value))
                for index,value in enumerate(coefficients[1]):
                    machine.mem_write(settings+0x250+index*4,struct.pack('<f',value))
                machine.emu_start(stop,stop+2)
                machine.mem_write(stack,struct.pack('<2I',stop,0))
                machine.reg_write(UC_X86_REG_ESP,stack);machine.reg_write(UC_X86_REG_ECX,descriptor)
                machine.reg_write(UC_X86_REG_EDX,context);machine.reg_write(UC_X86_REG_FPCW,word)
                machine.emu_start(0x4e9b90,stop,count=10000)
                value=machine.reg_read(UC_X86_REG_EAX)|(machine.reg_read(UC_X86_REG_EDX)<<32)
                expected.append((value,word));pair.append(value)
                payload.append(' '.join(map(str,[word,2147483647,1,*([0]*6),0,0,
                                               *struct.unpack('<3I',extended),8,0,0,
                                               *map(bits,coefficients[1]) ])))
            precision_pairs.append(pair)
        self.assertTrue(any(full!=narrowed for full,narrowed in precision_pairs),precision_pairs)
        with tempfile.TemporaryDirectory(prefix='workshop-source-strength-') as directory:
            temporary=Path(directory)
            (temporary/'strength.cpp').write_text(driver,encoding='utf8')
            (temporary/'build.cmd').write_text(
                f'@call "{vcvarsall()}" x86 >nul\n@if errorlevel 1 exit /b 1\n'
                '@cl /nologo /EHsc /O2 /std:c++20 /Fe:strength.exe strength.cpp\n',encoding='utf8')
            build=subprocess.run(['cmd','/d','/c',str(temporary/'build.cmd')],cwd=temporary,capture_output=True)
            self.assertEqual(build.returncode,0,build.stdout.decode(errors='replace')+build.stderr.decode(errors='replace'))
            result=subprocess.run([str(temporary/'strength.exe')],input='\n'.join(payload),text=True,capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)
            actual=[tuple(map(int,line.split())) for line in result.stdout.splitlines()]
            self.assertEqual(actual,expected)

    def test_large_candidate_shift_keeps_original_rank_row_and_checks_full_footprint(self):
        source = preview_source()
        probe_code = 'rank_column:' + source.split('    rank_column:', 1)[1].split('    rank_lane:', 1)[0]
        footprint = 'footprint_free:' + source.split('    footprint_free:', 1)[1].split('    footprint_occupy:', 1)[0]
        assembly = probe_code + '\nrank_lane: jmp 0x306000\nrank_advance: jmp 0x306100\n' + footprint
        assembly = '\n'.join(line.split('//', 1)[0] for line in assembly.splitlines())
        for symbol, address in {'g_outputStorage': '0x303000', 'g_superadminEnabled': '0x302000',
                                'g_creatureDefinition': '0x302004'}.items():
            assembly = assembly.replace(symbol, address)
        code = bytes(keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32).asm(assembly, 0x300000)[0])
        for admin, row, blocked, expected_row, destination in (
                (1,9,(8,),10,0x306000), (1,1,(),2,0x306000),
                (1,9,(8,10),9,0x306100), (0,9,(8,),9,0x306100)):
            with self.subTest(admin=admin, row=row, blocked=blocked):
                machine = Uc(UC_ARCH_X86, UC_MODE_32)
                machine.mem_map(0x200000,65536);machine.mem_map(0x300000,65536)
                machine.mem_write(0x300000,code)
                machine.mem_write(0x302000,struct.pack('<2I',admin,2))
                machine.mem_write(0x303008+384,struct.pack('<2I',16,12))
                machine.mem_write(0x303008+524,struct.pack('<2I',2,12))
                for occupied_row in blocked:
                    machine.mem_write(0x303008+1536+occupied_row*2+1,b'\x30')
                machine.reg_write(UC_X86_REG_ESP,0x208000)
                machine.reg_write(UC_X86_REG_ESI,13)
                machine.reg_write(UC_X86_REG_EDI,row)
                machine.emu_start(0x300000,destination,count=10000)
                self.assertEqual(machine.reg_read(UC_X86_REG_EDI),row)
                self.assertEqual(machine.reg_read(UC_X86_REG_ESP),0x208000)
                self.assertEqual(struct.unpack('<I',machine.mem_read(0x303008+904,4))[0],expected_row)

        residual = 'residual_cell:' + source.split('    residual_cell:', 1)[1].split(
            '    linked_cell_unavailable:', 1)[0]
        assembly = residual + '\ncell_selected: jmp 0x306000\nresidual_pass_done: jmp 0x306100\n' + footprint
        assembly = '\n'.join(line.split('//', 1)[0] for line in assembly.splitlines())
        for symbol, address in {'g_outputStorage': '0x303000', 'g_candidateIdentity': '0x302000',
                                'g_creatureDefinition': '0x302004', 'g_cell': '0x305000'}.items():
            assembly = assembly.replace(symbol, address)
        code = bytes(keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32).asm(assembly, 0x300000)[0])
        for phase, size, column, cursor, occupied, expected, destination in (
                (6,2,0,2,(),2,0x306000), (6,2,0,2,(2,),4,0x306000),
                (6,2,0,6,(6,),8,0x306000), (6,2,1,2,(),None,0x306100),
                (7,1,1,1,(1,2),3,0x306000),
                (6,2,0,2,tuple(range(1,11)),None,0x306100)):
            with self.subTest(residual_phase=phase, column=column, occupied=occupied):
                machine = Uc(UC_ARCH_X86, UC_MODE_32)
                machine.mem_map(0x200000,65536); machine.mem_map(0x300000,65536)
                machine.mem_write(0x300000,code)
                machine.mem_write(0x302000,struct.pack('<2I',phase,size))
                machine.mem_write(0x303008+384,struct.pack('<2I',16,12))
                machine.mem_write(0x303008+524,struct.pack('<2I',2,12))
                machine.mem_write(0x303008+912,struct.pack('<3I',column,cursor,cursor))
                for row in occupied:
                    machine.mem_write(0x303008+1536+row*2+1,b'\x30')
                machine.reg_write(UC_X86_REG_ESP,0x208000)
                machine.emu_start(0x300000,destination,count=10000)
                self.assertEqual(machine.reg_read(UC_X86_REG_ESP),0x208000)
                if expected is not None:
                    self.assertEqual(machine.reg_read(UC_X86_REG_EDI),expected)
                    self.assertEqual(machine.reg_read(UC_X86_REG_ESI),13-column)
                    saved_cursor = 916 if phase == 6 else 920
                    self.assertEqual(struct.unpack('<I',machine.mem_read(0x303008+saved_cursor,4))[0],expected)

    def test_spread_large_shooter_preserves_candidate_window_score(self):
        # Retained RMG-B generation440: the minimum shooter window is local1,
        # while spread retains local0,4,9. Local0 shifts its large anchor to
        # y2, but must not acquire local1's window score. Native chose y10.
        source = preview_source()
        assembly = 'lane_done:' + source.split('    lane_done:', 1)[1].split('    rank_advance:', 1)[0]
        assembly += '\nrank_advance: jmp 0x306000'
        assembly = '\n'.join(line.split('//', 1)[0] for line in assembly.splitlines())
        symbols = {'g_outputStorage': '0x303000', 'g_creatureDefinition': '0x302000',
                   'g_useSpreadRows': '0x302004', 'g_spreadFallback': '0x302005',
                   'g_superadminEnabled': '0x302006'}
        for symbol, address in symbols.items():
            assembly = assembly.replace(symbol, address)
        code = bytes(keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32).asm(assembly, 0x300000)[0])
        for spread, fallback, window, expected in ((1,0,1,10), (0,0,1,2), (1,1,1,2), (1,0,0,2)):
            with self.subTest(spread=spread, fallback=fallback, window=window):
                machine = Uc(UC_ARCH_X86, UC_MODE_32)
                machine.mem_map(0x200000,65536); machine.mem_map(0x300000,65536)
                machine.mem_write(0x300000,code)
                machine.mem_write(0x302000,struct.pack('<I3B',2,spread,fallback,1))
                machine.mem_write(0x303008+388,struct.pack('<I',12))
                machine.mem_write(0x303008+740,struct.pack('<3i',1,-1,-1))
                machine.mem_write(0x303008+784,struct.pack('<I',window))
                machine.mem_write(0x303008+796,struct.pack('<I',1))
                for row in (2,5,10):
                    machine.mem_write(0x303008+904,struct.pack('<I',row))
                    machine.reg_write(UC_X86_REG_ESP,0x208000)
                    machine.reg_write(UC_X86_REG_EDI,row)
                    machine.emu_start(0x300000,0x306000,count=10000)
                    self.assertEqual(machine.reg_read(UC_X86_REG_ESP),0x208000)
                self.assertEqual(struct.unpack('<I',machine.mem_read(0x303008+744,4))[0],expected)

    def test_native_spread_shooter_sort_keeps_original_row_before_anchor_shift(self):
        import pefile
        from unicorn import UC_HOOK_CODE
        game = WORKSPACE / '.local/test-game/bin/H5_Game.exe'
        if not game.is_file():
            self.skipTest('Pinned game EXE is needed for the native row-sort oracle')
        self.assertEqual(hashlib.sha256(game.read_bytes()).hexdigest(), probe.HASHES['H5_Game.exe'])
        executable = pefile.PE(str(game), fast_load=True)
        image = executable.get_memory_mapped_image()
        base = executable.OPTIONAL_HEADER.ImageBase
        executable.close()
        machine = Uc(UC_ARCH_X86, UC_MODE_32)
        machine.mem_map(base, (len(image)+4095)&~4095)
        machine.mem_write(base, image)
        machine.mem_map(0x200000,0x20000); machine.mem_map(0x300000,0x10000)
        allocations = [0x210000]

        def allocation_boundary(emulator, address, size, unused):
            if address not in (0x8791f0,0x879240):
                return
            stack = emulator.reg_read(UC_X86_REG_ESP)
            returned = struct.unpack('<I',emulator.mem_read(stack,4))[0]
            if address == 0x8791f0:
                length = struct.unpack('<I',emulator.mem_read(stack+4,4))[0]
                emulator.reg_write(UC_X86_REG_EAX,allocations[0])
                allocations[0] += (length+15)&~15
            emulator.reg_write(UC_X86_REG_ESP,stack+4)
            emulator.reg_write(UC_X86_REG_EIP,returned)

        machine.hook_add(UC_HOOK_CODE,allocation_boundary)
        # Generation440: one-row window at local1; spread selects local0,4,9.
        # Original sorting/copy instructions run unchanged; only heap allocation
        # and release are supplied by the fixture.
        machine.mem_write(0x302000,struct.pack('<I',0x302100))
        machine.mem_write(0x302100,struct.pack('<10I',*[int(row==1) for row in range(10)]))
        machine.mem_write(0x301000,b''.join(struct.pack('<2I',0,row) for row in range(10)))
        machine.mem_write(0x208000,struct.pack('<2I',0x30f000,0x302000))
        machine.reg_write(UC_X86_REG_ECX,0x301000)
        machine.reg_write(UC_X86_REG_EDX,0x301050)
        machine.reg_write(UC_X86_REG_ESP,0x208000)
        machine.emu_start(0x85a9b0,0x30f000,count=100000)
        ranked = [struct.unpack('<2I',machine.mem_read(0x301000+index*8,8))[1] for index in range(10)]
        self.assertEqual([row for row in ranked if row in (0,4,9)],[9,4,0])
        self.assertEqual(machine.reg_read(UC_X86_REG_ESP),0x208008)

        # Generation30: seven spread records retain local row1 separately
        # from local0. Both reach large anchor y2; row1 keeps its own priority.
        # Scores are the retained terrain's two-row free approaches, with
        # local0 using its single valid row as in the original candidate pass.
        approach_scores = [10,10,10,4,4,1,1,6,10,6]
        machine.mem_write(0x301000,b''.join(struct.pack('<2I',score,row)
            for row,score in enumerate(approach_scores)))
        machine.mem_write(0x208000,struct.pack('<2I',0x30f000,0x85a4f0))
        machine.reg_write(UC_X86_REG_ECX,0x301000)
        machine.reg_write(UC_X86_REG_EDX,0x301050)
        machine.reg_write(UC_X86_REG_ESP,0x208000)
        machine.emu_start(0x85a700,0x30f000,count=100000)
        ranked = [struct.unpack('<2I',machine.mem_read(0x301000+index*8,8))[1] for index in range(10)]
        retained_rows = {0,1,2,3,4,5,9}
        self.assertEqual(next(row for row in ranked if row in retained_rows),1)
        self.assertEqual(machine.reg_read(UC_X86_REG_ESP),0x208008)

    def test_retry_excludes_global_weakest_and_resets_only_owned_occupancy(self):
        source = preview_source()
        implementation = 'bool ExcludeWeakestProjection() {' + source.split(
            'bool ExcludeWeakestProjection() {', 1)[1].split('bool CaptureSourceSimpleColumns()', 1)[0]
        driver = r'''
#include <windows.h>
#include <cstdint>
#include <cstring>
#include <cassert>
#include <algorithm>
bool g_superadminEnabled=false;
bool g_sourceSimpleLayout=false;
bool g_sourceFallbackPrepared=false;
uint32_t g_predictionExcludedMask=0;
LONG g_publicCount=7;
int g_publicPlacementScore[7]={300,200,100,2,1,600,500};
int g_plannedProjectionCount=7;
int g_protectiveCellCount=4;
uint32_t g_definitionMaximum=6,g_candidateIdentity=5;
bool g_predictedDefensive=false;
unsigned char g_outputStorage[4104]{};
int preparations=0;
bool PreparePublicOrder() {
    ++preparations;g_plannedProjectionCount=0;
    for(int index=0;index<7;++index)if(!(g_predictionExcludedMask&(1u<<index)))++g_plannedProjectionCount;
    return g_plannedProjectionCount>0;
}
struct FixturePair { int score; uint32_t sourceIndex; };
void __fastcall Sort(FixturePair* first,FixturePair* last,uintptr_t) {
    // No ties here: this boundary fixture checks exclusion/reset, not sort tie order.
    std::sort(first,last,[](const auto& left,const auto& right){return left.score>right.score;});
}
''' + implementation + r'''
int main() {
    assert(!ExcludeWeakestProjection() && preparations==0 && g_predictionExcludedMask==0);
    g_superadminEnabled=true;
    assert(ExcludeWeakestProjection() && g_predictionExcludedMask==(1u<<4) && g_plannedProjectionCount==6);
    *reinterpret_cast<int*>(g_outputStorage+8+496)=5; // failed attempt already placed five units
    *reinterpret_cast<uint32_t*>(g_outputStorage+8+640)=79;
    assert(ExcludeWeakestProjection() && g_predictionExcludedMask==24 && g_plannedProjectionCount==5);
    *reinterpret_cast<int*>(g_outputStorage+8+524)=2;
    *reinterpret_cast<int*>(g_outputStorage+8+528)=12;
    memset(g_outputStorage+8+1536,0xa5,1024);
    memset(g_outputStorage+8+2560,0x5a,1024);
    *reinterpret_cast<uint32_t*>(g_outputStorage+8+952)=7;
    ResetProjectionAttempt();
    assert(*reinterpret_cast<int*>(g_outputStorage+8+496)==0);
    assert(*reinterpret_cast<uint32_t*>(g_outputStorage+8+952)==0);
    assert(g_definitionMaximum==0 && g_candidateIdentity==0 && g_protectiveCellCount==0);
    assert(g_predictionExcludedMask==24 && preparations==2);
    for(int index=0;index<24;++index)assert(g_outputStorage[8+1536+index]==0x5a);
    assert(g_outputStorage[8+1536+24]==0xa5);
    for(int index=0;index<1024;++index)assert(g_outputStorage[8+2560+index]==0x5a);
    g_predictedDefensive=true;ResetProjectionAttempt();assert(g_candidateIdentity==1);
    g_predictionExcludedMask=0x7e;
    assert(!ExcludeWeakestProjection() && g_predictionExcludedMask==0x7e);
}
'''
        driver = driver.replace('0x85a700', 'reinterpret_cast<uintptr_t>(&::Sort)')
        with tempfile.TemporaryDirectory(prefix='workshop-placement-retry-') as directory:
            temporary = Path(directory)
            (temporary / 'retry.cpp').write_text(driver, encoding='utf-8')
            (temporary / 'build.cmd').write_text(
                f'@call "{vcvarsall()}" x86 >nul\n@if errorlevel 1 exit /b 1\n'
                '@cl /nologo /EHsc /O2 /std:c++20 /Fe:retry.exe retry.cpp\n', encoding='utf-8')
            build = subprocess.run(['cmd','/d','/c',str(temporary/'build.cmd')],cwd=temporary,capture_output=True)
            self.assertEqual(build.returncode,0,build.stdout.decode(errors='replace')+build.stderr.decode(errors='replace'))
            completed = subprocess.run([str(temporary/'retry.exe')],capture_output=True)
            self.assertEqual(completed.returncode,0,completed.stderr.decode(errors='replace'))

    def test_weakest_stack_observer_captures_native_exclusion_without_changing_registers(self):
        source = (MOD_ROOT / 'scripts/accuracy-campaign.py').read_text()
        assembly = source.split("        removal_assembly = f'''", 1)[1].split("'''", 1)[0]
        for symbol, base in (('records', 0x304000), ('removals', 0x305000)):
            assembly = re.sub(r'\{' + symbol + r'(?: \+ (\d+))?\}',
                              lambda match: str(base + int(match.group(1) or 0)), assembly)
        code = bytes(keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32).asm(assembly, 0x300000)[0])
        for actor_present, count in ((False, 0), (True, 0), (True, 15), (False, 16)):
            with self.subTest(actor_present=actor_present, count=count):
                machine = Uc(UC_ARCH_X86, UC_MODE_32)
                machine.mem_map(0x200000, 65536)
                machine.mem_map(0x300000, 65536)
                machine.mem_write(0x300000, code)
                machine.mem_write(0x303008, struct.pack('<I', 0x306000))
                machine.mem_write(0x304000, struct.pack('<3I', 2, 0, 0))
                machine.mem_write(0x304ff0, b'\xa5' * 1088)
                machine.mem_write(0x305000, struct.pack('<2I', count, 0))
                machine.mem_write(0x306000, struct.pack('<9I', 0x307000 if actor_present else 0,
                                                       3, 8, 0, 1, 13, 8, 65, 0))
                machine.mem_write(0x30701c, struct.pack('<2I', 79, 5))
                machine.reg_write(UC_X86_REG_EAX, 2)
                machine.reg_write(UC_X86_REG_ESI, 0x303000)
                machine.reg_write(UC_X86_REG_EDX, 0x1234)
                machine.reg_write(UC_X86_REG_ESP, 0x208000)
                machine.reg_write(UC_X86_REG_EFLAGS, 0x246)
                machine.emu_start(0x300000, 0x859b9e, count=1000)
                self.assertEqual(struct.unpack('<2I', machine.mem_read(0x305000, 8)),
                                 (count + int(count < 16), int(count >= 16)))
                if count < 16:
                    expected = (0, 1, 0x306000, 79 if actor_present else 65,
                                5 if actor_present else 8, 1, 0, 3)
                    self.assertEqual(struct.unpack('<8I', machine.mem_read(0x305010 + count * 64, 32)), expected)
                self.assertEqual(struct.unpack('<I', machine.mem_read(0x306020, 4))[0], 1)
                self.assertEqual(machine.reg_read(UC_X86_REG_ECX), 0x306000)
                self.assertEqual(machine.reg_read(UC_X86_REG_EAX), 2)
                self.assertEqual(machine.reg_read(UC_X86_REG_ESI), 0x303000)
                self.assertEqual(machine.reg_read(UC_X86_REG_EDX), 0x1234)
                self.assertEqual(machine.reg_read(UC_X86_REG_ESP), 0x208000)
                self.assertEqual(machine.reg_read(UC_X86_REG_EFLAGS), 0x246)
                self.assertEqual(bytes(machine.mem_read(0x304ff0, 16)), b'\xa5' * 16)
                self.assertEqual(bytes(machine.mem_read(0x305410, 16)), b'\xa5' * 16)

    def test_superadmin_role_comparator_matches_original_engine_at_flight_speed_and_score_boundaries(self):
        import itertools
        import pefile
        from unicorn import UC_HOOK_CODE
        game = WORKSPACE / '.local/test-game/bin/H5_Game.exe'
        if not game.is_file():
            self.skipTest('Pinned game EXE is needed for the native placement comparator oracle')
        self.assertEqual(hashlib.sha256(game.read_bytes()).hexdigest(), probe.HASHES['H5_Game.exe'])
        executable = pefile.PE(str(game))
        native = executable.get_data(0x85aba0 - executable.OPTIONAL_HEADER.ImageBase, 0x1e9)
        descriptor_getter = executable.get_data(0x4d8ed0 - executable.OPTIONAL_HEADER.ImageBase, 0x22)
        executable.close()
        cases = []
        for left_flying, right_flying, left_speed, right_speed, scores in itertools.product(
                (0, 1), (0, 1), (7, 8, 9), (7, 8, 9), ((3, 5), (5, 3), (5, 5))):
            left_score, right_score = scores
            machine = Uc(UC_ARCH_X86, UC_MODE_32)
            for address in (0x200000, 0x300000):
                machine.mem_map(address, 65536)
            for address in (0x85a000, 0x4d8000, 0x4ba000, 0x4bc000, 0x434000):
                machine.mem_map(address, 4096)
            machine.mem_write(0x85aba0, native)
            machine.mem_write(0x4d8ed0, descriptor_getter)
            machine.mem_write(0x302000, struct.pack('<I', 8))
            machine.mem_write(0x303000, struct.pack('<4I', left_score, 0x304000, right_score, 0x304040))
            machine.mem_write(0x304000, struct.pack('<I', 0x306000))
            machine.mem_write(0x304040, struct.pack('<I', 0x306040))
            machine.mem_write(0x307000, bytes(8))
            for actor, flying, speed in ((0x306000, left_flying, left_speed),
                                         (0x306040, right_flying, right_speed)):
                machine.mem_write(actor + 4, struct.pack('<4I', 0x307000, 100, flying, speed))
            machine.mem_write(0x208000, struct.pack('<3I', 0x30f000, 0x303000, 0x303008))
            machine.reg_write(UC_X86_REG_ECX, 0x302000)
            machine.reg_write(UC_X86_REG_ESP, 0x208000)

            # Boundary getters expose fixture attributes. The comparator and
            # descriptor resolution execute unchanged pinned EXE instructions.
            def attribute_boundary(emulator, address, size, unused):
                if address not in (0x4ba950, 0x4bc0b0, 0x434460):
                    return
                stack = emulator.reg_read(UC_X86_REG_ESP)
                returned = struct.unpack('<I', emulator.mem_read(stack, 4))[0]
                actor = emulator.reg_read(UC_X86_REG_ECX)
                arguments = 1 if address == 0x4bc0b0 else 0
                if address == 0x434460:
                    actor = struct.unpack('<I', emulator.mem_read(actor, 4))[0]
                    if actor:
                        references = struct.unpack('<I', emulator.mem_read(actor + 8, 4))[0]
                        emulator.mem_write(actor + 8, struct.pack('<I', references - 1))
                else:
                    attribute = actor + (12 if address == 0x4ba950 else 16)
                    emulator.reg_write(UC_X86_REG_EAX, struct.unpack('<I', emulator.mem_read(attribute, 4))[0])
                emulator.reg_write(UC_X86_REG_ESP, stack + 4 + arguments * 4)
                emulator.reg_write(UC_X86_REG_EIP, returned)

            machine.hook_add(UC_HOOK_CODE, attribute_boundary)
            machine.emu_start(0x85aba0, 0x30f000, count=10000)
            self.assertEqual(machine.reg_read(UC_X86_REG_ESP), 0x20800c)
            self.assertEqual(struct.unpack('<I', machine.mem_read(0x306008, 4))[0], 100)
            self.assertEqual(struct.unpack('<I', machine.mem_read(0x306048, 4))[0], 100)
            cases.append((left_flying, right_flying, left_speed, right_speed,
                          left_score, right_score, machine.reg_read(UC_X86_REG_EAX) & 255))
        source = preview_source()
        implementation = 'bool __fastcall PublicPlacementPairBefore(const int* left, const int* right) {' + source.split(
            'bool __fastcall PublicPlacementPairBefore(const int* left, const int* right) {', 1)[1].split(
            'int PublicPlacementRole(uint32_t type) {', 1)[0]
        driver = r'''
#include <windows.h>
#include <cstdint>
#include <cassert>
#include <iostream>
int32_t g_publicSortSpeed[7]{};
uint32_t g_publicSortFlying[7]{};
int g_publicSortDistance=8;
''' + implementation + r'''
int main() {
    int leftFlying,rightFlying,leftSpeed,rightSpeed,leftScore,rightScore,expected;
    while(std::cin>>leftFlying>>rightFlying>>leftSpeed>>rightSpeed>>leftScore>>rightScore>>expected) {
        g_publicSortFlying[0]=leftFlying;g_publicSortFlying[1]=rightFlying;
        g_publicSortSpeed[0]=leftSpeed;g_publicSortSpeed[1]=rightSpeed;
        const int left[]={leftScore,0},right[]={rightScore,1};
        assert(PublicPlacementPairBefore(left,right)==static_cast<bool>(expected));
    }
}
'''
        with tempfile.TemporaryDirectory(prefix='workshop-role-comparator-') as directory:
            temporary = Path(directory)
            (temporary / 'comparator.cpp').write_text(driver, encoding='utf-8')
            (temporary / 'build.cmd').write_text(
                f'@call "{vcvarsall()}" x86 >nul\n@if errorlevel 1 exit /b 1\n'
                '@cl /nologo /EHsc /O2 /std:c++20 /Fe:comparator.exe comparator.cpp\n', encoding='utf-8')
            build = subprocess.run(['cmd','/d','/c',str(temporary/'build.cmd')],cwd=temporary,capture_output=True)
            self.assertEqual(build.returncode,0,build.stdout.decode(errors='replace')+build.stderr.decode(errors='replace'))
            payload = ''.join(' '.join(map(str, case)) + '\n' for case in cases)
            completed = subprocess.run([str(temporary/'comparator.exe')],input=payload,capture_output=True,text=True)
            self.assertEqual(completed.returncode,0,completed.stderr)

    def test_physical_shooter_uses_frozen_original_army_not_ammo_or_stale_rows(self):
        source=preview_source()
        declarations='struct FrozenActorInput {'+source.split('struct FrozenActorInput {',1)[1].split('void* g_creatureDefinition',1)[0]
        implementation='bool PlacementHasPhysicalShot(uint32_t type) {'+source.split('bool PlacementHasPhysicalShot(uint32_t type) {',1)[1].split('bool PreparePublicOrder()',1)[0]
        driver=r"""
#include <windows.h>
#include <cstdint>
#include <cstring>
#include <cassert>
bool g_superadminEnabled=false;
LONG g_publicCount=3;
uint32_t g_publicTypes[7]{117,130,3};
LONG g_attackGeneration=1,g_placementGeneration=1,g_superadminSourceGeneration=1,g_superadminSourceCount=2;
int definitions[256][80]{};
const int* __fastcall Definition(uint32_t type) { return type<256 ? definitions[type] : nullptr; }
const uintptr_t kCreatureDefinition=reinterpret_cast<uintptr_t>(&Definition);
bool __fastcall TestAbility(uint32_t ability,uint32_t type) { return ability==0x7a && type==130; }
"""+declarations+implementation.replace('reinterpret_cast<Ability>(0xb61ba0)', 'reinterpret_cast<Ability>(&TestAbility)')+r"""
int main() {
    definitions[3][0x4c/4]=10;
    assert(!PlacementHasPhysicalShot(130) && PlacementHasPhysicalShot(3));
    g_superadminEnabled=true;g_actorInputsFrozen=true;g_actorCoreMask=3;g_actorInputGeneration=1;
    g_actorInputWorld=1;g_actorInputCount=2;g_actorCoreInputEnds[1]=2;g_actorCoreStackCounts[1]=2;
    for (auto& row:g_actorInputs) { row.world=1;row.army=2;row.attackGeneration=1; }
    g_actorInputs[0].type=117;g_actorInputs[0].quantity=40;
    g_actorInputs[1].type=130;g_actorInputs[1].quantity=3;g_actorInputs[1].skipSpeed=4;
    assert(PlacementHasPhysicalShot(130) && !PlacementHasPhysicalShot(117)); // zero-ammo thrower
    g_actorInputs[0].type=3;assert(!PlacementHasPhysicalShot(3)); // physical state overrides definition
    assert(PlacementHasShooterCategory(3)); // source category uses declared shots, not actor state
    g_superadminEnabled=false;assert(PlacementHasPhysicalShot(3) && !PlacementHasPhysicalShot(130));
    g_superadminEnabled=true;g_sourceSimpleLayout=true;assert(!PlacementHasPhysicalShot(130));
    g_sourceSimpleLayout=false;g_actorInputGeneration=2;assert(!PlacementHasPhysicalShot(130));
    g_actorInputGeneration=1;g_superadminSourceGeneration=2;assert(!PlacementHasPhysicalShot(130));
    g_superadminSourceGeneration=1;g_actorCoreStackCounts[1]=1;assert(!PlacementHasPhysicalShot(130));
    g_actorCoreStackCounts[1]=2;g_actorInputs[1].world=3;assert(!PlacementHasPhysicalShot(130));
    g_actorInputs[1].world=1;g_actorInputs[1].unsupported=1;assert(!PlacementHasPhysicalShot(130));
    g_actorInputs[1].unsupported=0;g_actorInputs[1].skipSpeed=0;
    assert(!PlacementHasPhysicalShot(130) && PlacementHasShooterCategory(130));
    g_publicTypes[0]=1;assert(!PlacementHasShooterCategory(130));
    g_actorInputs[1].skipSpeed=4;
    assert(PlacementHasPhysicalShot(130) && !PlacementHasShooterCategory(130));
    g_actorInputs[1].skipSpeed=0;
    definitions[118][0x100/4]=117;g_publicTypes[0]=118;assert(PlacementHasShooterCategory(130));
    g_superadminEnabled=false;assert(!PlacementHasShooterCategory(130));
    g_superadminEnabled=true;g_sourceSimpleLayout=true;assert(!PlacementHasShooterCategory(130));
}
"""
        with tempfile.TemporaryDirectory(prefix='workshop-physical-role-') as directory:
            temporary=Path(directory);(temporary/'physical.cpp').write_text(driver,encoding='utf-8')
            (temporary/'build.cmd').write_text(f'@call "{vcvarsall()}" x86 >nul\n@if errorlevel 1 exit /b 1\n@cl /nologo /EHsc /O2 /std:c++20 /Fe:physical.exe physical.cpp\n',encoding='utf-8')
            build=subprocess.run(['cmd','/d','/c',str(temporary/'build.cmd')],cwd=temporary,capture_output=True)
            self.assertEqual(build.returncode,0,build.stdout.decode(errors='replace')+build.stderr.decode(errors='replace'))
            completed=subprocess.run([str(temporary/'physical.exe')],capture_output=True)
            self.assertEqual(completed.returncode,0,completed.stderr.decode(errors='replace'))

    def test_ground_retry_combines_support_linked_and_ground_without_replacing_source_indices(self):
        source = preview_source()
        quantity_helpers = 'uint32_t ParseDisclosedQuantity(' + source.split('uint32_t ParseDisclosedQuantity(',1)[1].split('// The stock public model',1)[0]
        ordering = 'bool PreparePublicOrder() {' + source.split('bool PreparePublicOrder() {',1)[1].split('bool ExcludeWeakestProjection()',1)[0]
        aggregate = 'struct PlacementAggregate {' + source.split('struct PlacementAggregate {',1)[1].split('struct PlacementWeights',1)[0]
        comparator = 'bool __fastcall PublicPlacementPairBefore(const int* left, const int* right) {' + source.split('bool __fastcall PublicPlacementPairBefore(const int* left, const int* right) {',1)[1].split('int PublicPlacementRole(uint32_t type) {',1)[0]
        driver = r"""
#include <windows.h>
#include <cstdint>
#include <cstring>
#include <cassert>
#include <algorithm>
bool g_superadminEnabled=true,g_sourceSimpleLayout=false,g_predictedDefensive=false,g_useSpreadRows=false;
LONG g_publicCount=5,g_superadminSourceCount=5,g_superadminSourceGeneration=1,g_placementGeneration=1;
uint32_t g_sourceComposition[24]{},g_groundRetryOrder[7]{},g_predictionExcludedMask=0;
uint32_t g_publicTypes[7]{10,11,12,14,13},g_orderedPublicTypes[7]{};
uint32_t g_publicKnownCounts[7]{};
wchar_t g_publicQuantityLabels[7][32]{};uint32_t g_publicBands[7]{};
uint32_t g_superadminSourceTypes[7]{10,11,12,14,13},g_superadminSourceCounts[7]{10,20,30,40,50};
int32_t g_superadminSourceSpeed[7]{4,4,4,4,4},g_publicSortSpeed[7]{};
uint32_t g_superadminSourceFlying[7]{},g_publicSortFlying[7]{};
int g_publicPlacementScore[7]{},g_publicSortDistance=8,g_plannedProjectionCount=0;
unsigned char g_outputStorage[4104]{};
int definitions[32][80]{};
const int* __fastcall Definition(uint32_t type) { return definitions[type]; }
const uintptr_t kCreatureDefinition=reinterpret_cast<uintptr_t>(&Definition);
bool PlacementHasPhysicalShot(uint32_t type) { return definitions[type][0x4c/4]>0; }
bool PlacementHasShooterCategory(uint32_t type) { return PlacementHasPhysicalShot(type); }
int PublicPlacementRole(uint32_t type) { if (!g_superadminEnabled || g_predictedDefensive) return definitions[type][0x4c/4]>0 ? 1 : definitions[type][0xdc/4]==2 ? 0 : 2; return type==10 ? 4 : type==11 ? 5 : type==12 ? 2 : type==14 ? 1 : 0; }
""" + aggregate + comparator + r"""
int __fastcall Evaluate(const PlacementAggregate* value,void*,const PlacementAggregate*) { return value->damage+value->health; }
struct SortPair { int score; uint32_t source; };
void __fastcall Sort(SortPair* begin,SortPair* end,uintptr_t comparator) {
    std::stable_sort(begin,end,[&](const SortPair& left,const SortPair& right) {
        if (comparator==0x85a4f0) return left.score>right.score;
        return PublicPlacementPairBefore(reinterpret_cast<const int*>(&left),reinterpret_cast<const int*>(&right));
    });
}
""" + quantity_helpers + ordering + r"""
int main() {
    *reinterpret_cast<int*>(g_outputStorage+8+384)=16;
    for (auto& definition:definitions) {
        definition[0xdc/4]=1;definition[0x50/4]=definition[0x54/4]=definition[0x64/4]=1;
    }
    definitions[13][0xdc/4]=2;definitions[14][0x4c/4]=10;
    g_publicTypes[0]=9; // public image/base identity differs from exact source10
    assert(PreparePublicOrder());
    assert(g_publicTypes[0]==10);
    assert(g_orderedPublicTypes[g_groundRetryOrder[0]]==12);
    assert(g_orderedPublicTypes[g_groundRetryOrder[1]]==11);
    assert(g_orderedPublicTypes[g_groundRetryOrder[2]]==10);
    assert(g_groundRetryOrder[3]==UINT_MAX);
    g_superadminSourceCounts[0]=20;assert(PreparePublicOrder());
    assert(g_orderedPublicTypes[g_groundRetryOrder[1]]==10); // original source tie
    assert(g_orderedPublicTypes[g_groundRetryOrder[2]]==11);
    g_superadminSourceFlying[0]=1;assert(PreparePublicOrder());
    assert(g_orderedPublicTypes[g_groundRetryOrder[2]]==10);
    g_predictionExcludedMask=1;assert(PreparePublicOrder());
    assert(g_orderedPublicTypes[g_groundRetryOrder[0]]==12 && g_groundRetryOrder[2]==UINT_MAX);
    g_predictedDefensive=true;assert(PreparePublicOrder());assert(g_groundRetryOrder[0]==UINT_MAX);
    g_predictionExcludedMask=0;g_superadminSourceFlying[0]=0;g_superadminSourceSpeed[0]=8;
    assert(PreparePublicOrder() && g_orderedPublicTypes[2]==12); // defence alone: score
    g_useSpreadRows=true;
    assert(PreparePublicOrder() && g_orderedPublicTypes[2]==10); // remaining spread troops: ordinary speed priority
    g_useSpreadRows=false;
    g_superadminSourceGeneration=0;assert(!PreparePublicOrder());
    g_superadminSourceGeneration=1;g_superadminSourceCount=4;assert(!PreparePublicOrder());
    g_superadminSourceCount=5;g_superadminEnabled=false;g_publicTypes[0]=9;
    assert(PreparePublicOrder() && g_publicTypes[0]==9); // ordinary identity stays public
    memcpy(g_publicQuantityLabels[0],L"10-19",sizeof(L"10-19"));
    assert(PreparePublicOrder() && g_publicPlacementScore[0]==30);
    const auto estimatedDestination=reinterpret_cast<uint32_t*>(g_outputStorage+8+924)[0];
    assert(reinterpret_cast<uint32_t*>(g_outputStorage+8+832)[estimatedDestination]==0);
    g_publicKnownCounts[0]=20;assert(PreparePublicOrder() && g_publicPlacementScore[0]==40);
    const auto disclosedDestination=reinterpret_cast<uint32_t*>(g_outputStorage+8+924)[0];
    assert(reinterpret_cast<uint32_t*>(g_outputStorage+8+832)[disclosedDestination]==20);
    g_publicKnownCounts[0]=0;memset(g_publicQuantityLabels,0,sizeof(g_publicQuantityLabels));
    g_superadminEnabled=true;g_sourceSimpleLayout=true;g_publicCount=2;g_superadminSourceCount=1;
    g_sourceComposition[0]=1;g_sourceComposition[12]=2;
    g_sourceComposition[17]=5;g_sourceComposition[19]=6;
    assert(PreparePublicOrder() && g_orderedPublicTypes[0]==9); // generated identity is retained
}
"""
        driver=driver.replace('0xbf9b80','reinterpret_cast<uintptr_t>(&::Evaluate)').replace('0x85a700','reinterpret_cast<uintptr_t>(&::Sort)')
        with tempfile.TemporaryDirectory(prefix='workshop-ground-retry-') as directory:
            temporary=Path(directory)
            (temporary/'ground.cpp').write_text(driver,encoding='utf-8')
            (temporary/'build.cmd').write_text(f'@call "{vcvarsall()}" x86 >nul\n@if errorlevel 1 exit /b 1\n@cl /nologo /EHsc /O2 /std:c++20 /Fe:ground.exe ground.cpp\n',encoding='utf-8')
            build=subprocess.run(['cmd','/d','/c',str(temporary/'build.cmd')],cwd=temporary,capture_output=True)
            self.assertEqual(build.returncode,0,build.stdout.decode(errors='replace')+build.stderr.decode(errors='replace'))
            completed=subprocess.run([str(temporary/'ground.exe')],capture_output=True)
            self.assertEqual(completed.returncode,0,completed.stderr.decode(errors='replace'))
        assembly='primary_model_index:' + source.split('    primary_model_index:',1)[1].split('    unplaced_model_index:',1)[0]
        assembly += '\nunplaced_model_index: jmp 0x306000\nnext_model: jmp 0x306100\nrestore: jmp 0x306200'
        for symbol,address in {'g_candidateIdentity':'0x302000','g_plannedProjectionCount':'0x302004',
                'g_superadminEnabled':'0x302008','g_predictedDefensive':'0x302009',
                'g_definitionMaximum':'0x30200c','g_groundRetryOrder':'0x302020','g_outputStorage':'0x303000'}.items():
            assembly=assembly.replace(symbol,address)
        code=bytes(keystone.Ks(keystone.KS_ARCH_X86,keystone.KS_MODE_32).asm(assembly,addr=0x300000)[0])
        for phase,admin,defensive,occupied,expected,stop in (
                (5,1,0,0,4,0x306000),(5,1,0,16,4,0x306100),
                (5,0,0,16,0,0x306000),(5,1,1,0,0,0x306000),(4,1,0,0,0,0x306000)):
            machine=Uc(UC_ARCH_X86,UC_MODE_32);machine.mem_map(0x200000,65536);machine.mem_map(0x300000,65536)
            machine.mem_write(0x300000,code);machine.mem_write(0x302000,struct.pack('<2I',phase,5)+bytes([admin,defensive]))
            machine.mem_write(0x302020,struct.pack('<I',4));machine.mem_write(0x303000+8+908,struct.pack('<I',occupied))
            machine.reg_write(UC_X86_REG_ESP,0x208000);machine.emu_start(0x300000,stop,count=1000)
            self.assertEqual(struct.unpack('<I',machine.mem_read(0x30200c,4))[0],expected)

        # Retained Archer100/pack25: native ground row is8, not residual row1.
        # Reconstruct only the recorded inner-lane obstacles from approach scores;
        # the footprint boundary is supplied separately, not a full arena replay.
        assembly='rank_window_ready:' + source.split('    rank_window_ready:',1)[1].split('    rank_selected:',1)[0]
        assembly='\n'.join(line.split('//',1)[0] for line in assembly.splitlines())
        assembly += '\nrank_selected: jmp 0x306000\nnext_model: jmp 0x306100\nfootprint_free: mov eax,1; ret\nSpreadRowAllowed: mov eax,1; ret\nSpreadSecondRowUsesOwnPriority: mov eax,1; ret'
        for symbol,address in {'g_candidateIdentity':'0x302000','g_creatureDefinition':'0x302004',
                'g_superadminEnabled':'0x302008','g_useSpreadRows':'0x302009',
                'g_spreadFallback':'0x30200a','g_outputStorage':'0x303000'}.items():
            assembly=assembly.replace(symbol,address)
        code=bytes(keystone.Ks(keystone.KS_ARCH_X86,keystone.KS_MODE_32).asm(assembly,addr=0x300000)[0])
        machine=Uc(UC_ARCH_X86,UC_MODE_32);machine.mem_map(0x200000,65536);machine.mem_map(0x300000,65536)
        machine.mem_write(0x300000,code);machine.mem_write(0x302000,struct.pack('<2I',5,1)+bytes([1,0,0]))
        machine.mem_write(0x303000+8+384,struct.pack('<2I',16,12));machine.mem_write(0x303000+8+524,struct.pack('<I',2))
        obstacles=bytearray(24)
        for row,approach in enumerate((10,10,10,1,5,10,10,10,10,10),1):
            if approach<10:
                column=11-approach;obstacles[row*2+column//8]|=1<<(column%8)
        machine.mem_write(0x303000+8+2560,bytes(obstacles));machine.reg_write(UC_X86_REG_ESP,0x208000)
        machine.emu_start(0x300000,0x306000,count=10000)
        self.assertEqual(struct.unpack('<I',machine.mem_read(0x303000+8+744,4))[0],8)

        # Retained default/Cyclops counterexample: physical shooter overlaps
        # large category2; ordinary phase0 keeps a maximum-approach row, not
        # the shooter shelter window. Only inner-lane geometry is replayed.
        machine=Uc(UC_ARCH_X86,UC_MODE_32);machine.mem_map(0x200000,65536);machine.mem_map(0x300000,65536)
        machine.mem_write(0x300000,code);machine.mem_write(0x302000,struct.pack('<2I',0,2)+bytes([1,0,0]))
        machine.mem_write(0x303000+8+384,struct.pack('<2I',16,12));machine.mem_write(0x303000+8+524,struct.pack('<I',2))
        machine.mem_write(0x303000+8+780,struct.pack('<I',1))
        obstacles=bytearray(24);obstacles[7*2+6//8]|=1<<(6%8)
        machine.mem_write(0x303000+8+2560,bytes(obstacles));machine.reg_write(UC_X86_REG_ESP,0x208000)
        machine.emu_start(0x300000,0x306000,count=10000)
        self.assertEqual(struct.unpack('<I',machine.mem_read(0x303000+8+744,4))[0],4)

    def test_partial_projection_is_explicit_research_evidence_and_never_ready_by_default(self):
        from unittest.mock import patch, Mock
        from types import SimpleNamespace
        specification = importlib.util.spec_from_file_location(
            'partial_projection_check', MOD_ROOT / 'scripts/native-preview-check.py')
        check = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(check)
        trace = {'abi': 8, 'public': 7, 'models': 5, 'planned_models': 7, 'excluded_source_mask': 0,
                 'grid': [16, 12], 'generation': 1,
                 'slots': [{'type': index + 1, 'quantity': 3, 'cell': [13, 2 + index * 2], 'size': 2}
                           for index in range(5)],
                 'public_bands': [1] * 7, 'predicted_spread': False, 'predicted_defensive': False,
                 'estimated_spread_denominator': 0, 'known_hero_attack': 1, 'known_hero_battle_frenzy': False}
        for allow_partial in (False, True):
            with self.subTest(allow_partial=allow_partial), \
                 patch.object(check, 'diagnostics', return_value={'public': 7, 'models': 5}), \
                 patch.object(check, 'command', return_value=json.dumps(trace)), \
                 patch.object(check.time, 'monotonic', side_effect=[0, 0, 9.6, 10.1]), \
                 patch.object(check.time, 'sleep'):
                if allow_partial:
                    result = check.wait_for_models(123, 7, allow_partial=True)
                    self.assertFalse(result['prediction_complete'])
                    self.assertEqual(len(result['footprints']), 5)
                    self.assertEqual(result['public'], 7)
                else:
                    with self.assertRaisesRegex(RuntimeError, 'Projection readiness timed out'):
                        check.wait_for_models(123, 7)
        with patch.object(check, 'diagnostics', side_effect=[
                RuntimeError('Projection snapshot is busy; retry capture (Win32 error 0)'),
                {'public': 7, 'models': 5}]), \
             patch.object(check, 'command', return_value=json.dumps(trace)), \
             patch.object(check.time, 'monotonic', side_effect=[0, 0, 0, 9.6]), \
             patch.object(check.time, 'sleep') as sleep:
            result = check.wait_for_models(123, 7, allow_partial=True)
            self.assertFalse(result['prediction_complete'])
            sleep.assert_called_once_with(0.05)
        with patch.object(check, 'diagnostics', side_effect=RuntimeError('Unsupported ABI')), \
             patch.object(check.time, 'monotonic', side_effect=[0, 0]), \
             patch.object(check.time, 'sleep') as sleep:
            with self.assertRaisesRegex(RuntimeError, 'Unsupported ABI'):
                check.wait_for_models(123, 7)
            sleep.assert_not_called()
        complete_reduced = dict(trace, planned_models=5, excluded_source_mask=96)
        with patch.object(check, 'diagnostics', return_value={'public': 7, 'models': 5}), \
             patch.object(check, 'command', return_value=json.dumps(complete_reduced)), \
             patch.object(check.time, 'monotonic', side_effect=[0, 0]), \
             patch.object(check.time, 'sleep') as sleep:
            result = check.wait_for_models(123, 7, allow_partial=True)
            self.assertTrue(result['prediction_complete'])
            self.assertEqual(result['planned_models'], 5)
            self.assertEqual(result['excluded_source_mask'], 96)
            sleep.assert_not_called()
        with patch.object(check, 'diagnostics', return_value={'public': 7, 'models': 5}), \
             patch.object(check, 'command', return_value=json.dumps(trace)) as command, \
             patch.object(check.time, 'monotonic', side_effect=[0, 0, 1, 2, 9.6]), \
             patch.object(check.time, 'sleep') as sleep:
            result = check.wait_for_models(123, 7, allow_partial=True)
            self.assertFalse(result['prediction_complete'])
            self.assertEqual(command.call_count, 2)
            sleep.assert_called_once_with(0.5)
        dispatcher = SimpleNamespace(main=Mock(side_effect=[{'pid': 123, 'result': '1'}, OSError('PID unavailable')]))
        with patch.object(check, '_control_module', dispatcher):
            self.assertEqual(check.control('day'), {'pid': 123, 'result': '1'})
            with self.assertRaisesRegex(RuntimeError, 'PID unavailable') as failure:
                check.control('day')
            self.assertIsInstance(failure.exception.__cause__, OSError)

    def test_superadmin_spread_rows_follow_native_integer_spacing(self):
        source = preview_source()
        implementation = 'bool __cdecl SpreadRowAllowed(' + source.split('bool __cdecl SpreadRowAllowed(', 1)[1].split(
            '// Configuration changes apply at the next attack', 1)[0]
        driver = r'''
#include <windows.h>
#include <cstdint>
#include <cassert>
#include <cstring>
bool g_useSpreadRows=false;
bool g_spreadFallback=false;
bool g_superadminEnabled=false;
LONG g_publicCount=0;
unsigned char g_outputStorage[4104]{};
void* g_creatureDefinition=reinterpret_cast<void*>(1);
'''+implementation+r'''
int main() {
    *reinterpret_cast<int*>(g_outputStorage+8+388)=12;
    g_publicCount=2;
    for(int row=1;row<=10;row++)assert(SpreadRowAllowed(2,row));
    g_useSpreadRows=true;
    for(int count=2;count<=4;count++) {
        g_publicCount=count;
        for(int row=1;row<=10;row++) {
            bool expected=(row==10);
            for(int index=0;index<count-1;index++)expected|=(row==1+index*(9/(count-1)));
            assert(SpreadRowAllowed(2,row)==expected);
        }
    }
    g_publicCount=1;
    for(int row=1;row<=10;row++)assert(SpreadRowAllowed(2,row));
    g_publicCount=2;g_creatureDefinition=reinterpret_cast<void*>(2);
    assert(SpreadRowAllowed(0,1) && SpreadRowAllowed(0,2) && SpreadRowAllowed(0,10));
    for(int row=3;row<=9;row++)assert(!SpreadRowAllowed(0,row));
    g_publicCount=3;
    assert(SpreadRowAllowed(0,5) && !SpreadRowAllowed(0,6));
    *reinterpret_cast<int*>(g_outputStorage+8+384)=16;
    *reinterpret_cast<int*>(g_outputStorage+8+524)=2;
    assert(SpreadRowAllowed(0,2));
    int anchors[]={5,10};
    for(int y : anchors) {
        for(int row=y-1;row<=y;row++)for(int x=12;x<=13;x++)
            g_outputStorage[8+1536+row*2+x/8]|=1<<(x&7);
    }
    assert(SpreadRowAllowed(0,2));
    memset(g_outputStorage+8+1536,0,1024);
    // A/RMG160: y=2 remains a scored candidate after y=10 is occupied;
    // native row priority, not candidate deletion, decides against y=2.
    g_publicCount=4;
    for(int row=9;row<=10;row++)for(int x=12;x<=13;x++)
        g_outputStorage[8+1536+row*2+x/8]|=1<<(x&7);
    assert(SpreadRowAllowed(0,2) && SpreadRowAllowed(0,7));
    memset(g_outputStorage+8+1536,0,1024);
    assert(SpreadRowAllowed(-1,5) && SpreadRowAllowed(3,5));
    g_creatureDefinition=reinterpret_cast<void*>(1);g_publicCount=3;
    *reinterpret_cast<int*>(g_outputStorage+8+384)=16;
    *reinterpret_cast<int*>(g_outputStorage+8+524)=2;
    g_outputStorage[8+1536+10*2+13/8]|=1<<(13&7);
    assert(!SpreadRowAllowed(2,10));
    assert(SpreadRowAllowed(2,1) && SpreadRowAllowed(2,5));
    g_outputStorage[8+1536+1*2+13/8]|=1<<(13&7);
    g_outputStorage[8+1536+5*2+13/8]|=1<<(13&7);
    assert(SpreadRowAllowed(2,10));
    g_spreadFallback=true;
    assert(SpreadRowAllowed(2,6));
    g_spreadFallback=false;g_superadminEnabled=true;
    memset(g_outputStorage+8+1536,0,1024);
    g_publicCount=2;
    for(int role=0;role<=5;++role) {
        for(int row=1;row<=10;++row)assert(SpreadRowAllowed(role,row)==(row==1 || row==10));
    }
    assert(SpreadRowAllowed(6,8) && SpreadRowAllowed(7,4)); // native leftover passes remain unrestricted
    g_spreadFallback=true;assert(SpreadRowAllowed(5,8));
    g_spreadFallback=false;
    for(int count=2;count<=7;++count) {
        g_publicCount=count;
        assert(SpreadSecondRowUsesOwnPriority()==(count>=6));
    }
    *reinterpret_cast<int*>(g_outputStorage+8+388)=4;g_publicCount=2;
    assert(SpreadSecondRowUsesOwnPriority());
}
'''
        with tempfile.TemporaryDirectory(prefix='workshop-spread-') as directory:
            temporary = Path(directory)
            (temporary / 'spread.cpp').write_text(driver, encoding='utf-8')
            (temporary / 'build.cmd').write_text(
                f'@call "{vcvarsall()}" x86 >nul\n@if errorlevel 1 exit /b 1\n'
                '@cl /nologo /EHsc /O2 /std:c++20 /Fe:spread.exe spread.cpp\n', encoding='utf-8')
            build = subprocess.run(['cmd','/d','/c',str(temporary/'build.cmd')],cwd=temporary,capture_output=True)
            self.assertEqual(build.returncode,0,build.stdout.decode(errors='replace')+build.stderr.decode(errors='replace'))
            completed = subprocess.run([str(temporary/'spread.exe')],capture_output=True)
            self.assertEqual(completed.returncode,0,completed.stderr.decode(errors='replace'))

        # B/089 and B/105: an illegal 2x2 local row zero falls back to y=2,
        # but keeps local zero's low tie rank. Ordinary y=2 keeps its rank.
        rank = 'rank_compare:' + source.split('    rank_compare:', 1)[1].split('    rank_advance:', 1)[0]
        rank += '\nrank_advance: jmp 0x306000'
        rank = '\n'.join(line.split('//', 1)[0] for line in rank.splitlines())
        for symbol, address in {'g_outputStorage': '0x303000', 'g_useSpreadRows': '0x302000',
                                'g_spreadFallback': '0x302001', 'g_creatureDefinition': '0x302004',
                                'g_superadminEnabled': '0x302008'}.items():
            rank = rank.replace(symbol, address)
        code = bytes(keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32).asm(rank, addr=0x300000)[0])
        for spread, scored_rows, selected, own_priority in ((0, ((2, 10), (5, 10)), 2, 0),
                                              (1, ((2, 10), (5, 10)), 5, 0),
                                              (1, ((2, 10), (10, 0)), 2, 0),
                                              (1, ((2, 10), (3, 10)), 2, 1)):
            machine = Uc(UC_ARCH_X86, UC_MODE_32)
            machine.mem_map(0x200000, 65536)
            machine.mem_map(0x300000, 65536)
            machine.mem_write(0x300000, code)
            machine.mem_write(0x302000, bytes([spread, 0, 0, 0]) + struct.pack('<I', 2))
            machine.mem_write(0x303008 + 744, struct.pack('<2i', -1, -1))
            machine.mem_write(0x303008 + 1396, struct.pack('<I', own_priority))
            machine.reg_write(UC_X86_REG_ESP, 0x208000)
            for row, score in scored_rows:
                machine.reg_write(UC_X86_REG_EDI, row)
                machine.reg_write(UC_X86_REG_EBP, score)
                machine.emu_start(0x300000, 0x306000, count=1000)
            self.assertEqual(struct.unpack('<i', machine.mem_read(0x303008 + 744, 4))[0], selected)

    def test_superadmin_source_requires_opt_in_and_expires_with_placement(self):
        game = WORKSPACE / '.local/test-game/bin/H5_Game.exe'
        if game.is_file():
            import pefile
            executable = pefile.PE(str(game))
            self.assertEqual(executable.get_data(0xbfacfb - executable.OPTIONAL_HEADER.ImageBase, 3),
                             bytes.fromhex('c2 10 00'))  # Aggregate builder owns all four stack arguments.
            executable.close()
        source = preview_source()
        capture = 'void CaptureSuperadminSource(' + source.split('void CaptureSuperadminSource(', 1)[1].split(
            '// The stock public model', 1)[0]
        scripted = 'void __cdecl CaptureScriptedSource(' + source.split('void __cdecl CaptureScriptedSource(', 1)[1].split(
            '__declspec(naked) void ScriptedSourceHook()', 1)[0]
        binding = 'bool PrepareScriptedPreviewSource() {' + source.split('bool PrepareScriptedPreviewSource() {', 1)[1].split(
            'void CaptureSuperadminSource(', 1)[0]
        export = 'extern "C" __declspec(dllexport) unsigned long __stdcall WorkshopDeploymentPreviewSuperadminSourceTrace(' + source.split(
            'extern "C" __declspec(dllexport) unsigned long __stdcall WorkshopDeploymentPreviewSuperadminSourceTrace(', 1)[1].split(
            '#pragma comment(linker, "/EXPORT:WorkshopDeploymentPreviewProjectionTrace', 1)[0]
        driver = r'''
#include <windows.h>
#include <cstdint>
#include <cstring>
#include <cassert>
bool g_superadminEnabled=false;
uint32_t g_superadminSourceTypes[7]{},g_superadminSourceCounts[7]{};
uint32_t g_superadminSourcePointers[7]{};
uint32_t g_superadminSourceKind=0;
bool g_superadminSourceModifiersKnown=false;
volatile LONG g_attackGeneration=0,g_publicCount=0;
uint32_t g_publicTypes[7]{};
int resetCalls=0;
void ResetSuperadminInputCapture() { ++resetCalls; }
struct FrozenActorInput { uint32_t world,army,source,type,quantity,attackGeneration,unsupported; };
constexpr uint32_t kActorInputCapacity=1024;
FrozenActorInput g_actorInputs[kActorInputCapacity]{};
volatile LONG g_actorInputCount=0,g_actorInputGeneration=0;
bool g_actorInputOverflow=false;
uint32_t g_publicBands[7]{};
uint32_t g_publicKnownCounts[7]{};wchar_t g_publicQuantityLabels[7][32]{};
int expectedAggregateCount=2;
int32_t g_superadminSourceSpeed[7]{};
uint32_t g_superadminSourceFlying[7]{};
uint32_t g_superadminSourceAggregate[18]{};
bool g_superadminTerrainKnown=false;
uint32_t g_superadminTerrainMask=0,g_superadminTerrainType=0;
bool g_superadminRngKnown=false;
uint32_t g_superadminRngState=0;
volatile LONG g_superadminSourceCount=0,g_superadminSourceGeneration=-1;
void* g_grid=nullptr;
volatile LONG g_placementGeneration=1;
int getterCalls=0;
int __fastcall SourceSpeed(const uint32_t* descriptor,void*,const void*) {
    ++getterCalls;return descriptor[7]==57 ? 7 : 4;
}
bool __fastcall SourceFlying(const uint32_t* descriptor,void*) { return descriptor[7]==57; }
void __stdcall SourceAggregate(uint32_t* output,const uint32_t* const* vector,const void* hero,const void* context) {
    assert(hero==nullptr && context==nullptr);
    assert(vector[1]-vector[0]==expectedAggregateCount);
    memset(output,0,18*sizeof(uint32_t));output[3]=115;output[6]=700;
}
'''+scripted+binding+capture+export+r'''
int main() {
    uint32_t buffer[60]{};buffer[0]=0x55aa55aa;buffer[59]=0xaa55aa55;
    uint32_t* output=buffer+1;
    CaptureScriptedSource(reinterpret_cast<uint32_t*>(1));
    assert(resetCalls==0 && g_attackGeneration==0);
    g_superadminEnabled=false;
    CaptureSuperadminSource(reinterpret_cast<uint32_t*>(1));
    assert(WorkshopDeploymentPreviewSuperadminSourceTrace(output)==1);
    assert(output[0]==7 && output[1]==0 && output[3]==0 && output[55]==0 && getterCalls==0);
    uint32_t first[9]{},second[9]{};
    first[7]=57;first[8]=80;second[7]=61;second[8]=35;
    uint32_t pointers[]={reinterpret_cast<uint32_t>(first),reinterpret_cast<uint32_t>(second)};
    uint32_t object[0x100/4]{};
    object[0xe0/4]=reinterpret_cast<uint32_t>(pointers);
    object[0xe4/4]=reinterpret_cast<uint32_t>(pointers+2);
    g_superadminEnabled=true;
    CaptureSuperadminSource(object);
    assert(WorkshopDeploymentPreviewSuperadminSourceTrace(output)==1);
    assert(output[1]==1 && output[2]==1 && output[3]==2);
    assert(output[56]==1 && output[57]==1);
    assert(output[4]==57 && output[5]==80 && output[6]==61 && output[7]==35);
    assert(output[18]==7 && output[19]==4 && output[25]==1 && output[26]==0 && getterCalls==2);
    assert(output[35]==115 && output[38]==700);
    assert(output[53]==0 && output[54]==0);
    g_superadminRngKnown=true;g_superadminRngState=0x81234567;
    assert(WorkshopDeploymentPreviewSuperadminSourceTrace(output)==1);
    assert(output[53]==1 && output[54]==0x81234567);
    g_superadminTerrainKnown=true;g_grid=reinterpret_cast<void*>(0x12345678);
    assert(WorkshopDeploymentPreviewSuperadminSourceTrace(output)==1 && output[55]==0x12345678);
    ++g_placementGeneration;
    assert(WorkshopDeploymentPreviewSuperadminSourceTrace(output)==1 && output[3]==0 && output[53]==0 && output[55]==0);
    g_superadminSourceCount=0;
    assert(WorkshopDeploymentPreviewSuperadminSourceTrace(output)==1 && output[3]==0);
    uint32_t scriptedStacks[]={1,80,5,35,9,12};
    uint32_t scriptedVector[]={reinterpret_cast<uint32_t>(scriptedStacks),
        reinterpret_cast<uint32_t>(scriptedStacks+6),reinterpret_cast<uint32_t>(scriptedStacks+6)};
    g_placementGeneration=3;g_publicCount=2;g_publicTypes[0]=57;
    CaptureScriptedSource(scriptedVector);
    assert(resetCalls==1 && g_attackGeneration==1 && g_publicCount==0 && g_publicTypes[0]==0);
    assert(WorkshopDeploymentPreviewSuperadminSourceTrace(output)==1);
    assert(output[2]==3 && output[3]==3 && output[56]==2 && output[57]==0);
    assert(output[4]==1 && output[5]==80 && output[6]==5 && output[7]==35 && output[8]==9 && output[9]==12);
    assert(output[50]==0 && output[53]==0 && output[55]==0);
    for(int index=18;index<50;++index) assert(output[index]==0);
    uint32_t world[0x94/4]{};world[0]=0xe79d3c;world[0x90/4]=1234;
    uint32_t descriptors[3][9]{};
    for(uint32_t slot=0;slot<3;++slot) {
        descriptors[slot][7]=scriptedStacks[slot*2];descriptors[slot][8]=scriptedStacks[slot*2+1];
        g_actorInputs[slot]={reinterpret_cast<uint32_t>(world),1234,reinterpret_cast<uint32_t>(descriptors[slot]),
            scriptedStacks[slot*2],scriptedStacks[slot*2+1],static_cast<uint32_t>(g_attackGeneration),0};
    }
    g_actorInputCount=3;g_actorInputGeneration=g_attackGeneration;expectedAggregateCount=3;
    g_actorInputs[0].army=9876;assert(!PrepareScriptedPreviewSource() && g_publicCount==0);
    g_actorInputs[0].army=1234;g_actorInputs[0].quantity=79;assert(!PrepareScriptedPreviewSource());
    g_actorInputs[0].quantity=80;g_actorInputs[0].attackGeneration=0;assert(!PrepareScriptedPreviewSource());
    g_actorInputs[0].attackGeneration=g_attackGeneration;g_actorInputOverflow=true;assert(!PrepareScriptedPreviewSource());
    g_actorInputOverflow=false;g_actorInputGeneration=0;assert(!PrepareScriptedPreviewSource());
    g_actorInputGeneration=g_attackGeneration;g_actorInputs[0].unsupported=1;assert(!PrepareScriptedPreviewSource());
    g_actorInputs[0].unsupported=0;
    g_superadminSourceGeneration=2;assert(!PrepareScriptedPreviewSource());g_superadminSourceGeneration=3;
    world[0]=0;assert(!PrepareScriptedPreviewSource());world[0]=0xe79d3c;
    g_superadminSourceTypes[1]=1;g_superadminSourceCounts[1]=80;assert(!PrepareScriptedPreviewSource());
    g_superadminSourceTypes[1]=5;g_superadminSourceCounts[1]=35;
    uint32_t conflicting[9]{};conflicting[7]=1;conflicting[8]=80;
    g_actorInputs[3]=g_actorInputs[0];g_actorInputs[3].source=reinterpret_cast<uint32_t>(conflicting);
    g_actorInputCount=4;assert(!PrepareScriptedPreviewSource());g_actorInputCount=3;
    assert(PrepareScriptedPreviewSource());
    assert(g_publicCount==3 && g_publicTypes[0]==1 && g_superadminSourceModifiersKnown);
    assert(g_superadminSourcePointers[0]==reinterpret_cast<uint32_t>(descriptors[0]));
    assert(WorkshopDeploymentPreviewSuperadminSourceTrace(output)==1 && output[57]==1 && output[18]==4);
    scriptedVector[1]=scriptedVector[0]+3;
    CaptureScriptedSource(scriptedVector);
    assert(g_superadminSourceCount==0 && resetCalls==2);
    scriptedVector[1]=scriptedVector[0]+64;scriptedVector[2]=scriptedVector[1];
    CaptureScriptedSource(scriptedVector);assert(g_superadminSourceCount==0);
    scriptedVector[1]=scriptedVector[0]+24;scriptedVector[2]=scriptedVector[1]-4;
    CaptureScriptedSource(scriptedVector);assert(g_superadminSourceCount==0);
    scriptedVector[2]=scriptedVector[1];scriptedStacks[3]=0;
    CaptureScriptedSource(scriptedVector);assert(g_superadminSourceCount==0);
    CaptureScriptedSource(nullptr);assert(g_superadminSourceCount==0);
    assert(buffer[0]==0x55aa55aa && buffer[59]==0xaa55aa55);
}
'''
        driver = driver.replace('0x4bc0b0', 'reinterpret_cast<uintptr_t>(&::SourceSpeed)').replace(
            '0x4ba950', 'reinterpret_cast<uintptr_t>(&::SourceFlying)').replace(
            '0xbfaa70', 'reinterpret_cast<uintptr_t>(&::SourceAggregate)')
        with tempfile.TemporaryDirectory(prefix='workshop-admin-source-') as directory:
            temporary = Path(directory)
            (temporary / 'source.cpp').write_text(driver, encoding='utf-8')
            (temporary / 'build.cmd').write_text(
                f'@call "{vcvarsall()}" x86 >nul\n@if errorlevel 1 exit /b 1\n'
                '@cl /nologo /EHsc /O2 /std:c++20 /Fe:source.exe source.cpp\n', encoding='utf-8')
            build = subprocess.run(['cmd', '/d', '/c', str(temporary / 'build.cmd')], cwd=temporary, capture_output=True)
            self.assertEqual(build.returncode, 0, build.stdout.decode(errors='replace') + build.stderr.decode(errors='replace'))
            result = subprocess.run([str(temporary / 'source.exe')], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))

    def test_protective_phase_stops_after_shooters_large_and_small(self):
        source = preview_source()
        assembly = 'next_model:' + source.split('    next_model:', 1)[1].split('    footprint_free:', 1)[0]
        assembly = assembly.replace('call PrepareProtectiveCandidates', 'nop')
        for symbol, address in {'g_definitionMaximum':'0x302000', 'g_publicCount':'0x302004',
                                'g_plannedProjectionCount':'0x302004',
                                'g_candidateIdentity':'0x302008', 'g_predictedDefensive':'0x30200c',
                                'g_superadminEnabled':'0x30200d', 'g_sourceSimpleLayout':'0x30200e', 'g_outputStorage':'0x303000'}.items():
            assembly = assembly.replace(symbol,address)
        assembly += '\nmodel_loop: jmp 0x306000\nrestore: jmp 0x306100'
        code = bytes(keystone.Ks(keystone.KS_ARCH_X86,keystone.KS_MODE_32).asm(assembly,addr=0x300000)[0])
        for admin, defensive, current, expected, stop in (
                (0,1,1,0,0x306000),(0,1,0,2,0x306000),(0,1,2,2,0x306100),
                (1,0,2,3,0x306000),(1,0,4,5,0x306000),(1,0,5,6,0x306000),
                (1,1,2,6,0x306000)):
            machine = Uc(UC_ARCH_X86, UC_MODE_32)
            machine.mem_map(0x200000,65536);machine.mem_map(0x300000,65536)
            machine.mem_write(0x300000,code)
            machine.mem_write(0x302000,struct.pack('<3I',7,7,current)+bytes([defensive,admin]))
            machine.mem_write(0x303000+8+952,struct.pack('<I',7))
            machine.reg_write(UC_X86_REG_ESP,0x208000)
            machine.emu_start(0x300000,stop,count=1000)
            self.assertEqual(machine.reg_read(UC_X86_REG_EIP),stop)
            self.assertEqual(struct.unpack('<I',machine.mem_read(0x302008,4))[0],expected)

    def test_superadmin_goblin_adjacency_uses_carrier_lists_and_native_ties(self):
        source = preview_source()
        implementation = 'int PublicPlacementRole(uint32_t type) {' + source.split(
            'int PublicPlacementRole(uint32_t type) {', 1)[1].split('bool __cdecl SpreadRowAllowed(', 1)[0]
        driver = r'''
#include <windows.h>
#include <cstdint>
#include <cassert>
#include <cstring>
bool g_superadminEnabled=false;
uint32_t g_predictionExcludedMask=0;
LONG g_publicCount=2;
bool g_predictedDefensive=false;
uint32_t g_publicTypes[7]{117,124};
uint32_t g_orderedPublicTypes[7]{117};
uint32_t g_definitionMaximum=0;
unsigned char g_outputStorage[4104]{};
int g_cell[14]{};
int definitions[512][80]{};
bool abilities[512][128]{};
const int* __fastcall Definition(uint32_t type) { return type<512 ? definitions[type] : nullptr; }
bool __fastcall Ability(uint32_t ability,uint32_t type) { return type<512 && ability<128 && abilities[type][ability]; }
bool dynamicThrower=false;
bool PlacementHasPhysicalShot(uint32_t type) { return (g_superadminEnabled && dynamicThrower && type==130) || definitions[type][0x4c/4]>0; }
bool PlacementHasShooterCategory(uint32_t type) { return PlacementHasPhysicalShot(type); }
const uintptr_t kCreatureDefinition=reinterpret_cast<uintptr_t>(&Definition);
''' + implementation + r'''
int main() {
    definitions[117][0xdc/4]=1;
    definitions[118][0xdc/4]=1;
    definitions[118][0x100/4]=117;
    definitions[124][0xdc/4]=1;
    abilities[124][0x72]=true;
    definitions[126][0xdc/4]=2;
    abilities[126][0x79]=true;
    definitions[5][0xdc/4]=1;abilities[5][0x1b]=true;
    definitions[6][0xdc/4]=2;abilities[6][0x2f]=true;
    assert(PublicPlacementRole(124)==2 && PublicPlacementRole(126)==0);
    assert(ChooseLinkedGoblinCell()==-1);
    g_superadminEnabled=true;
    assert(PublicPlacementRole(124)==2 && PublicPlacementRole(117)==3);
    assert(PublicPlacementRole(118)==3 && PublicPlacementRole(126)==0);
    assert(PublicPlacementRole(5)==4 && PublicPlacementRole(6)==4);
    definitions[130][0xdc/4]=2;dynamicThrower=true;
    assert(PublicPlacementRole(130)==0); // ordinary large phase precedes special-shooter phase
    g_predictedDefensive=true;assert(PublicPlacementRole(130)==1); // defence starts with shooters
    g_predictedDefensive=false;g_superadminEnabled=false;assert(PublicPlacementRole(130)==0);
    g_superadminEnabled=true;dynamicThrower=false;
    *reinterpret_cast<int*>(g_outputStorage+8+384)=16;
    *reinterpret_cast<int*>(g_outputStorage+8+388)=12;
    *reinterpret_cast<int*>(g_outputStorage+8+524)=2;
    *reinterpret_cast<int*>(g_outputStorage+8+496)=1;
    *reinterpret_cast<uint32_t*>(g_outputStorage+8+640)=124;
    g_cell[0]=12;g_cell[1]=10;
    g_outputStorage[8+1536+10*2+12/8]|=1<<(12&7);
    assert(ChooseLinkedGoblinCell()==(13<<8|10)); // recorded pack27
    g_orderedPublicTypes[0]=118;
    assert(ChooseLinkedGoblinCell()==(13<<8|10)); // 4babf0 resolves the upgraded Goblin's base
    g_orderedPublicTypes[0]=117;
    g_outputStorage[8+1536+10*2+13/8]|=1<<(13&7);
    assert(ChooseLinkedGoblinCell()==(12<<8|9)); // blocked right and clipped upper edge
    *reinterpret_cast<int*>(g_outputStorage+8+496)=2;
    *reinterpret_cast<uint32_t*>(g_outputStorage+8+644)=117;
    g_cell[2]=13;g_cell[3]=10;
    assert(ChooseLinkedGoblinCell()==-1); // the previous goblin consumed the carrier list
    memset(g_outputStorage+8+1536,0,1024);
    *reinterpret_cast<uint32_t*>(g_outputStorage+8+644)=124;
    g_cell[0]=12;g_cell[1]=8;g_cell[2]=12;g_cell[3]=10;
    g_outputStorage[8+1536+8*2+12/8]|=1<<(12&7);
    g_outputStorage[8+1536+10*2+12/8]|=1<<(12&7);
    assert(ChooseLinkedGoblinCell()==(13<<8|9)); // shared candidate, first ring tie
    *reinterpret_cast<int*>(g_outputStorage+8+496)=0;
    g_publicCount=1;
    assert(PublicPlacementRole(117)==5 && ChooseLinkedGoblinCell()==-1);
    *reinterpret_cast<int*>(g_outputStorage+8+496)=1;
    *reinterpret_cast<uint32_t*>(g_outputStorage+8+640)=126;
    g_publicCount=2;g_publicTypes[1]=126;
    memset(g_outputStorage+8+1536,0,1024);
    g_cell[0]=13;g_cell[1]=8;
    for(int y=7;y<=8;++y)for(int x=12;x<=13;++x)
        g_outputStorage[8+1536+y*2+x/8]|=1<<(x&7);
    assert(PublicPlacementRole(117)==3);
    assert(ChooseLinkedGoblinCell()==(13<<8|9)); // earlier category2 carrier still anchors category8
    g_predictedDefensive=true;
    assert(PublicPlacementRole(117)==2 && PublicPlacementRole(124)==2);
    g_predictedDefensive=false;
    *reinterpret_cast<int*>(g_outputStorage+8+384)=33;
    assert(ChooseLinkedGoblinCell()==-1);
}
'''
        driver = driver.replace('0xb61ba0', 'reinterpret_cast<uintptr_t>(&::Ability)')
        with tempfile.TemporaryDirectory(prefix='workshop-goblin-adjacency-') as directory:
            temporary = Path(directory)
            (temporary / 'adjacency.cpp').write_text(driver, encoding='utf-8')
            (temporary / 'build.cmd').write_text(
                f'@call "{vcvarsall()}" x86 >nul\n@if errorlevel 1 exit /b 1\n'
                '@cl /nologo /EHsc /O2 /std:c++20 /Fe:adjacency.exe adjacency.cpp\n', encoding='utf-8')
            build = subprocess.run(['cmd','/d','/c',str(temporary/'build.cmd')],cwd=temporary,capture_output=True)
            self.assertEqual(build.returncode,0,build.stdout.decode(errors='replace')+build.stderr.decode(errors='replace'))
            completed = subprocess.run([str(temporary/'adjacency.exe')],capture_output=True)
            self.assertEqual(completed.returncode,0,completed.stderr.decode(errors='replace'))

    def test_known_hero_policy_uses_own_counts_sizes_and_runtime_threshold(self):
        source = preview_source()
        quantity_helpers = 'uint32_t ParseDisclosedQuantity(' + source.split('uint32_t ParseDisclosedQuantity(',1)[1].split('// The stock public model',1)[0]
        implementation = 'struct PlacementAggregate {' + source.split('struct PlacementAggregate {', 1)[1].split(
            'bool PlacementHasPhysicalShot(uint32_t type) {', 1)[0]
        driver = r'''
#include <windows.h>
#include <cstdint>
#include <climits>
#include <cassert>
#include <cstring>
bool g_knownHeroLarge=false;
void FreezeSuperadminInputCapture() {}
void PrepareSuperadminAggregates() {}
void PrepareSuperadminStrategy() {}
bool g_superadminTerrainKnown=false;
uint32_t g_superadminTerrainMask=0,g_superadminTerrainType=0;
bool g_superadminRngKnown=false;
uint32_t g_superadminRngState=0;
void* g_grid=nullptr;
bool g_predictedDefensive=false;
bool g_superadminEnabled=false;
bool g_useSpreadRows=false;
uint32_t g_estimatedSpreadDenominator=0;
int32_t g_knownHeroAttack=-1;
bool g_knownHeroBattleFrenzy=false;
LONG g_publicCount=7;
uint32_t g_publicTypes[7]{},g_publicBands[7]{},g_publicKnownCounts[7]{};
wchar_t g_publicQuantityLabels[7][32]{};
unsigned char g_outputStorage[4104]{};
int g_cell[14]{};
int g_protectiveCells[120]{},g_protectiveCellCount=0;
void* g_creatureDefinition=nullptr;
void* g_placementOwner=nullptr;
int definitions[3][80]{};
const int* __fastcall Definition(uint32_t type) { return type<3 ? definitions[type] : nullptr; }
const uintptr_t kCreatureDefinition=reinterpret_cast<uintptr_t>(&Definition);
unsigned char settings[4096]{};
const unsigned char* Settings() { return settings; }
struct PlacementAggregate;
int __fastcall Score(const PlacementAggregate*,void*,const PlacementAggregate*);
int __fastcall HeroAttack(const void* value, void*) { return *static_cast<const int*>(value); }
int mockFrenzy=0;
int __fastcall HeroSkill(const void*, void*, int skill) { return skill==36?mockFrenzy:0; }
void PrepareSourceComposition(const uint32_t*) {}
volatile LONG g_actorInputSequence=0;
struct FrozenSourceStrength { uint32_t metadata[8],inputWords[30],ownWords[2]; };
FrozenSourceStrength g_sourceStrengthInputs[256]{};
uint32_t g_sourceStrengthCount=0;
LONG g_superadminSourceCount=0;
uint32_t g_superadminSourcePointers[7]{},g_superadminSourceTypes[7]{},g_superadminSourceCounts[7]{};
'''+quantity_helpers+implementation+r'''
int __fastcall Score(const PlacementAggregate* value,void*,const PlacementAggregate*) { return value->health; }
int main() {
    definitions[1][0xdc/4]=1;definitions[1][0x64/4]=10;
    definitions[2][0xdc/4]=2;definitions[2][0x64/4]=100;
    int stacks[2][9]{};stacks[0][2]=1;stacks[0][7]=2;
    stacks[1][2]=5;stacks[1][7]=1;
    uint32_t owner[40]{};
    owner[3]=reinterpret_cast<uint32_t>(stacks);
    owner[4]=reinterpret_cast<uint32_t>(stacks+2);
    g_placementOwner=owner;
    *reinterpret_cast<float*>(settings+0xbf4)=0.55f;
    PrepareKnownHeroPolicy();assert(g_knownHeroLarge);
    stacks[1][2]=20;PrepareKnownHeroPolicy();assert(!g_knownHeroLarge);
    *reinterpret_cast<float*>(settings+0xbf4)=0.25f;
    PrepareKnownHeroPolicy();assert(g_knownHeroLarge);
    stacks[0][2]=0;PrepareKnownHeroPolicy();assert(!g_knownHeroLarge);
    stacks[0][2]=1;stacks[1][2]=0;PrepareKnownHeroPolicy();assert(g_knownHeroLarge);
    g_placementOwner=nullptr;PrepareKnownHeroPolicy();assert(!g_knownHeroLarge);
    g_placementOwner=owner;owner[4]++;PrepareKnownHeroPolicy();assert(!g_knownHeroLarge);
    owner[4]--;
    *reinterpret_cast<int*>(g_outputStorage+8+780)=3;
    stacks[0][2]=0;stacks[1][2]=20;PrepareKnownHeroPolicy();assert(!g_predictedDefensive);
    stacks[0][2]=1;stacks[1][2]=0;PrepareKnownHeroPolicy();assert(!g_predictedDefensive);
    stacks[0][2]=0;stacks[1][2]=20;
    g_publicCount=2;
    g_publicTypes[0]=1;g_publicTypes[1]=2;
    g_publicBands[0]=4;g_publicBands[1]=3;
    definitions[1][0x50/4]=2;definitions[1][0x54/4]=2;
    definitions[1][0x44/4]=5;definitions[1][0x48/4]=2;
    definitions[2][0x48/4]=20;
    definitions[2][0x50/4]=10;definitions[2][0x54/4]=10;
    definitions[2][0x4c/4]=1;
    *reinterpret_cast<float*>(settings+0x1d0)=0.05f;
    *reinterpret_cast<float*>(settings+0x1d8)=0.05f;
    *reinterpret_cast<float*>(settings+0xbf8)=0.35f;
    *reinterpret_cast<float*>(settings+0xbfc)=0.2f;
    *reinterpret_cast<float*>(settings+0xc00)=1.3f;
    PrepareKnownHeroPolicy();assert(g_useSpreadRows && g_predictedDefensive);
    g_publicTypes[1]=1;
    PrepareKnownHeroPolicy();assert(!g_useSpreadRows && !g_predictedDefensive);
    g_publicBands[0]=0;
    PrepareKnownHeroPolicy();assert(!g_useSpreadRows);
    g_publicBands[0]=4;g_publicTypes[1]=2;
    g_publicCount=7;
    *reinterpret_cast<int*>(g_outputStorage+8+384)=16;
    *reinterpret_cast<int*>(g_outputStorage+8+388)=12;
    *reinterpret_cast<int*>(g_outputStorage+8+524)=2;
    *reinterpret_cast<int*>(g_outputStorage+8+496)=3;
    // Recorded Polygon round 10: shooters at y10,9,1; native protective
    // attempts put the large stack at (13,8), then small at 12,9/1/10.
    *reinterpret_cast<int*>(g_outputStorage+8+784)=8;
    *reinterpret_cast<int*>(g_outputStorage+8+796)=3;
    const int shooterRows[]={1,9,10};
    for(int y:shooterRows)g_outputStorage[8+1536+y*2+13/8]|=1<<(13&7);
    PrepareProtectiveCandidates();
    g_creatureDefinition=reinterpret_cast<void*>(2);
    assert(ChooseProtectiveCell()==(13<<8|8));
    const int guardRows[]={7,8},guardColumns[]={12,13};
    for(int y:guardRows)for(int x:guardColumns)g_outputStorage[8+1536+y*2+x/8]|=1<<(x&7);
    PrepareProtectiveCandidates();
    g_creatureDefinition=reinterpret_cast<void*>(1);
    assert(ChooseProtectiveCell()==(12<<8|9));
    g_outputStorage[8+1536+9*2+12/8]|=1<<(12&7);
    assert(ChooseProtectiveCell()==(12<<8|1));
    g_outputStorage[8+1536+1*2+12/8]|=1<<(12&7);
    assert(ChooseProtectiveCell()==(12<<8|10));
    struct DefensiveFixture { int start; int shooters[3]; int largeRow; int smallRows[3]; };
    const DefensiveFixture earlier[] = {
        {7,{8,9,10},7,{9,8,10}}, // recorded Polygon round 1, native defensive
        {6,{7,8,9},6,{8,7,9}},  // recorded Polygon round 4
    };
    for(const auto& fixture:earlier) {
        memset(g_outputStorage+8+1536,0,1024);
        *reinterpret_cast<int*>(g_outputStorage+8+784)=fixture.start;
        for(int y:fixture.shooters)g_outputStorage[8+1536+y*2+13/8]|=1<<(13&7);
        PrepareProtectiveCandidates();
        g_creatureDefinition=reinterpret_cast<void*>(2);
        assert(ChooseProtectiveCell()==(13<<8|fixture.largeRow));
        for(int y=fixture.largeRow-1;y<=fixture.largeRow;y++)for(int x:guardColumns)
            g_outputStorage[8+1536+y*2+x/8]|=1<<(x&7);
        PrepareProtectiveCandidates();
        g_creatureDefinition=reinterpret_cast<void*>(1);
        for(int y:fixture.smallRows) {
            assert(ChooseProtectiveCell()==(12<<8|y));
            g_outputStorage[8+1536+y*2+12/8]|=1<<(12&7);
        }
    }
    memset(g_outputStorage+8+1536,0,1024);
    g_protectiveCellCount=0;
    memset(g_outputStorage+8+1536,0,1024);
    g_protectiveCellCount=1;g_protectiveCells[0]=13;g_protectiveCells[1]=7;
    g_creatureDefinition=reinterpret_cast<void*>(2);
    g_outputStorage[8+1536+6*2+13/8]|=1<<(13&7);
    g_superadminEnabled=false;assert(ChooseProtectiveCell()==-1);
    g_superadminEnabled=true;assert(ChooseProtectiveCell()==(13<<8|8));
    g_outputStorage[8+1536+8*2+13/8]|=1<<(13&7);
    assert(ChooseProtectiveCell()==-1);
    memset(g_outputStorage+8+1536,0,1024);
    g_protectiveCells[0]=12;g_protectiveCells[1]=2;
    assert(ChooseProtectiveCell()==(13<<8|2));
    g_superadminEnabled=false;
    uint32_t hero[8]{};
    uint32_t methods[0x174/4+1]{};
    methods[0x174/4]=reinterpret_cast<uint32_t>(&HeroSkill);
    hero[0]=reinterpret_cast<uint32_t>(methods);
    int32_t relative=12;
    hero[1]=reinterpret_cast<uint32_t>(&relative);
    uint32_t holder[5]{};
    holder[4]=reinterpret_cast<uint32_t>(hero);
    owner[0x98/4]=reinterpret_cast<uint32_t>(holder);
    g_publicCount=2;
    g_publicTypes[0]=1;g_publicTypes[1]=2;
    g_publicBands[0]=4;g_publicBands[1]=3;
    hero[4]=3;
    mockFrenzy=1;
    CaptureKnownHeroModifiers(owner);assert(g_knownHeroAttack==-1 && !g_knownHeroBattleFrenzy);
    PrepareKnownHeroPolicy();assert(g_knownHeroAttack==-1 && !g_knownHeroBattleFrenzy);
    const uint32_t baseDenominator=g_estimatedSpreadDenominator;
    mockFrenzy=0;
    PrepareKnownHeroPolicy();assert(g_estimatedSpreadDenominator==baseDenominator);
    hero[4]=0;
    PrepareKnownHeroPolicy();assert(g_knownHeroAttack==-1 && !g_knownHeroBattleFrenzy);
    hero[4]=1001;
    CaptureKnownHeroModifiers(owner);assert(g_knownHeroAttack==-1);
    owner[0x98/4]=1; // Inaccessible hero metadata must never be read in ordinary mode.
    PrepareKnownHeroPolicy();assert(g_estimatedSpreadDenominator==baseDenominator);
    owner[0x98/4]=reinterpret_cast<uint32_t>(holder);
    g_superadminEnabled=true;
    g_sourceStrengthCount=3;
    g_sourceStrengthInputs[0].metadata[1]=reinterpret_cast<uint32_t>(hero);
    g_sourceStrengthInputs[0].metadata[3]=stacks[1][7];g_sourceStrengthInputs[0].inputWords[1]=stacks[1][2];
    g_superadminSourceCount=1;
    g_superadminSourcePointers[0]=0x11223344;g_superadminSourceTypes[0]=1;g_superadminSourceCounts[0]=30;
    g_sourceStrengthInputs[1].metadata[0]=0x11223344;g_sourceStrengthInputs[1].metadata[3]=1;
    g_sourceStrengthInputs[1].inputWords[1]=30;
    g_sourceStrengthInputs[2]=g_sourceStrengthInputs[1];g_sourceStrengthInputs[2].inputWords[1]=31;
    CaptureKnownHeroModifiers(owner);
    assert(g_sourceStrengthInputs[0].metadata[7]==1 && g_sourceStrengthInputs[1].metadata[7]==2);
    assert(g_sourceStrengthInputs[2].metadata[7]==0);
}
'''
        driver = driver.replace('0xbf9b80', 'reinterpret_cast<uintptr_t>(&::Score)').replace(
            '0xbcb3f0', 'reinterpret_cast<uintptr_t>(&Settings)').replace(
            '0x5d4a40', 'reinterpret_cast<uintptr_t>(&HeroAttack)')
        with tempfile.TemporaryDirectory(prefix='workshop-own-army-') as directory:
            temporary = Path(directory)
            (temporary / 'policy.cpp').write_text(driver, encoding='utf-8')
            (temporary / 'build.cmd').write_text(
                f'@call "{vcvarsall()}" x86 >nul\n@if errorlevel 1 exit /b 1\n'
                '@cl /nologo /EHsc /O2 /std:c++20 /Fe:policy.exe policy.cpp\n', encoding='utf-8')
            build = subprocess.run(['cmd','/d','/c',str(temporary/'build.cmd')],cwd=temporary,capture_output=True)
            self.assertEqual(build.returncode,0,build.stdout.decode(errors='replace')+build.stderr.decode(errors='replace'))
            completed = subprocess.run([str(temporary/'policy.exe')],capture_output=True)
            self.assertEqual(completed.returncode,0,completed.stderr.decode(errors='replace'))

    def test_shooter_window_replays_recorded_large_hero_counterexample(self):
        source = preview_source()
        assembly = source.split('        // Nival 0x857e60:',1)[1].split('    rank_window_ready:',1)[0]
        assembly = '// Nival 0x857e60:' + assembly + '\nrank_window_ready: jmp 0x306000'
        assembly = '\n'.join(line.split('//',1)[0] for line in assembly.splitlines())
        assembly = assembly.replace('g_outputStorage','0x303000').replace('g_knownHeroLarge','0x302000')
        code = bytes(keystone.Ks(keystone.KS_ARCH_X86,keystone.KS_MODE_32).asm(assembly,addr=0x300000)[0])
        # Recorded defender approach lengths, PID13044: 10,10,10,10,10,10,1,2,10,10.
        # Native enemyLarge=1 selects rows 7..9; the old single-row pass selected 6..8.
        for large, expected in ((0,5),(1,6)):
            machine = Uc(UC_ARCH_X86, UC_MODE_32)
            machine.mem_map(0x200000,65536);machine.mem_map(0x300000,65536)
            machine.mem_write(0x300000,code)
            machine.mem_write(0x302000,bytes([large]))
            machine.mem_write(0x303008+384,struct.pack('<2I',16,12))
            machine.mem_write(0x303008+524,struct.pack('<I',2))
            machine.mem_write(0x303008+780,struct.pack('<I',3))
            bits=bytearray(24)
            for x,y in ((10,7),(9,8)):bits[y*2+x//8]|=1<<(x%8)
            machine.mem_write(0x303008+2560,bytes(bits))
            machine.reg_write(UC_X86_REG_ESP,0x208000)
            machine.emu_start(0x300000,0x306000,count=100000)
            self.assertEqual(struct.unpack('<I',machine.mem_read(0x303008+784,4))[0],expected)

        # Archer100 retained negatives: only the recorded approach rows are
        # reconstructed here; this checks window arithmetic, not whole arenas.
        for approaches, shifts, shooter_count in (
                ((10,5,6,10,0,10,10,1,10,10),(2,3),3),
                ((4,10,10,10,1,10,10,10,5,10),(8,3),3),
                ((10,10,10,10,10,10,2,2,10,10),(6,6),1)):
            for large,expected in enumerate(shifts):
                machine=Uc(UC_ARCH_X86,UC_MODE_32)
                machine.mem_map(0x200000,65536);machine.mem_map(0x300000,65536)
                machine.mem_write(0x300000,code);machine.mem_write(0x302000,bytes([large]))
                machine.mem_write(0x303008+384,struct.pack('<2I',16,12))
                machine.mem_write(0x303008+524,struct.pack('<I',2));machine.mem_write(0x303008+780,struct.pack('<I',shooter_count))
                obstacles=bytearray(24)
                for row,approach in enumerate(approaches,1):
                    if approach<10:
                        column=11-approach;obstacles[row*2+column//8]|=1<<(column%8)
                machine.mem_write(0x303008+2560,bytes(obstacles));machine.reg_write(UC_X86_REG_ESP,0x208000)
                machine.emu_start(0x300000,0x306000,count=100000)
                self.assertEqual(struct.unpack('<I',machine.mem_read(0x303008+784,4))[0],expected)

    def test_projection_cards_range_and_details_use_public_selected_grade(self):
        # Setup: exercise production selection/provider callbacks with a fake
        # engine definition registry and native card provider at their ABI seam.
        source = preview_source()
        implementation = 'int HoveredProjectionSlot() {' + source.split('int HoveredProjectionSlot() {', 1)[1].split(
            '// The deployment title is', 1)[0]
        implementation += 'int ComputeProjectionRange(' + source.split('int ComputeProjectionRange(', 1)[1].split(
            'void __stdcall ApplyProjectionOutline(', 1)[0]
        implementation += 'bool __fastcall ProjectionDetailsCanRotate(' + source.split('bool __fastcall ProjectionDetailsCanRotate(', 1)[1].split(
            'int HoveredProjectionSlot() {', 1)[0]
        implementation += 'void ObserveProjectionWindowInput(' + source.split('void ObserveProjectionWindowInput(', 1)[1].split(
            'BOOL CALLBACK FindProjectionWindow(', 1)[0]
        implementation = 'void ProcessProjectionDetails(bool installRotatorCallbacks = true);\nvoid ReleaseProjectionDetailsRotator();\n' + implementation
        setup = vcvarsall()
        if not setup.is_file():
            self.skipTest('MSVC x86 is required for production tooltip callback checks')
        driver = r'''
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <limits>
#include <cstdlib>
#define CHECK(condition) do { if (!(condition)) { std::cerr << "check failed at " << __LINE__ << ": " << #condition; ExitProcess(3); } } while (0)
unsigned char g_outputStorage[4104]{};
unsigned g_tooltipChoice[7]{};
int g_tooltipClickSlot=-1;
uint32_t* g_tooltipController=nullptr;
uint32_t* g_projectionScreen=nullptr;
int g_detailsSlot=-1;
LONG g_detailsGeneration=-1;
int g_detailsPoint[2]{};
bool g_detailsHitTest=false;
uint32_t* g_detailsRotator=nullptr;
bool g_detailsRotatorOwned=false;
const uint32_t* g_detailsNativeMethods=nullptr;
unsigned g_detailsProjectionSlot=7;
LONG g_detailsRotatorGeneration=-1;
LRESULT CALLBACK OriginalWindow(HWND,UINT,WPARAM,LPARAM) { return 73; }
WNDPROC g_originalGameWindowProc=OriginalWindow;
LRESULT DispatchWindow(WNDPROC proc,HWND window,UINT msg,WPARAM w,LPARAM l) { return proc(window,msg,w,l); }
LONG g_placementGeneration=1;
uint32_t descriptors[2048][3]{};
uint32_t DescriptorAddress(uint32_t type) { return reinterpret_cast<uint32_t>(descriptors[type]); }
uint32_t g_hoverX=13,g_hoverY=8;
int g_cell[14]={13,8,12,4};
void* g_placementOwner=reinterpret_cast<void*>(1);
uint32_t definition[80]{}, leaf[80]{}, alternate[80]{}, other[80]{};
uint32_t upgrades[]={58,59}, otherUpgrade[]={2};
const uint32_t* __fastcall Definition(uint32_t type) {
    return type==57?definition:(type==1?other:(type==59?alternate:(type==58||type==2?leaf:nullptr)));
}
const uintptr_t kCreatureDefinition=reinterpret_cast<uintptr_t>(&Definition);
unsigned nativeClicks=0,nativeWindows=0;
uint32_t __fastcall Window(uint32_t* provider,void*) { ++nativeWindows;return provider[3]; }
void __fastcall Click(uint32_t* provider,void*) { ++nativeClicks;++provider[4];provider[2]=0; }
void __fastcall Descriptor(uint32_t* provider,void*,uint32_t descriptor,const uint32_t* rectangle,uint32_t context) {
    CHECK(rectangle==provider+6 && rectangle[0]==123 && rectangle[1]==456 && context==789);
    provider[3]=descriptor;provider[4]=0;
}
uint32_t originalMethods[]={0x12345678,0x6b7eb0,0x6b7790,3,4,5,0x6b7880,7,8};
uint32_t creatureObject[12]{},alternateObject[12]{},rotatorObject[10]{},referenceOffsets[]={0,12,12};
uint32_t originalRotatorMethods[16]={0x87654321,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15};
unsigned queuedDetails=0,detailsType=0;
bool blockDetails=false,failCreature=false,failRotator=false,failCommand=false;
bool detailsScreenActive=true;
bool __cdecl NativeCapabilityAvailable() { return true; }
bool __fastcall ActiveDetailsScreen(void*) { return detailsScreenActive; }
bool __fastcall HitWindow(void*,void*,const int* point) {
    CHECK(g_detailsHitTest && point[0]==120 && point[1]==230);return blockDetails;
}
uint32_t* __fastcall CreateCreature(uint32_t* creature) {
    CHECK(creature[1]==1);detailsType=creature[0];
    if(failCreature)return nullptr;
    auto* object=creatureObject[6]==0?creatureObject:alternateObject;
    CHECK(object[6]==0);object[1]=reinterpret_cast<uint32_t>(referenceOffsets);return object;
}
uint32_t* __fastcall CreateRotator(void* creature) {
    CHECK(creature==creatureObject);if(failRotator)return nullptr;
    ++creatureObject[6];rotatorObject[1]=reinterpret_cast<uint32_t>(referenceOffsets);
    rotatorObject[2]=reinterpret_cast<uint32_t>(creature);
    rotatorObject[0]=reinterpret_cast<uint32_t>(originalRotatorMethods+1);return rotatorObject;
}
void* __fastcall CreateDetails(uint32_t world,uint32_t player,void* rotator,uint32_t upgrade,uint32_t dismiss,
    uint32_t view,uint32_t hero,uint32_t client,uint32_t mode,uint32_t combat,uint32_t listener,uint32_t extra) {
    CHECK(world==111 && player==222 && rotator==rotatorObject && upgrade==0 && dismiss==0 && view==1);
    CHECK(hero==0 && client==333 && mode==0 && combat==1 && listener==0 && extra==0);
    if(failCommand)return nullptr;
    ++rotatorObject[6];return reinterpret_cast<void*>(444);
}
void __fastcall SubmitDetails(void* command) { CHECK(command==reinterpret_cast<void*>(444));++queuedDetails; }
void __fastcall ReleaseDetails(uint32_t* reference) {
    if(reference==rotatorObject+4) {
        auto* current=reinterpret_cast<uint32_t*>(rotatorObject[2]);
        CHECK(rotatorObject[6]==0 && current[6]>0);--current[6];
    } else CHECK((reference==creatureObject+4 || reference==alternateObject+4) && reference[2]==0);
}
IMPLEMENTATION
uint32_t ProjectionTooltipDescriptor(uint32_t type) {
    *reinterpret_cast<uint32_t*>(g_outputStorage+8+716)=type;
    *reinterpret_cast<uint32_t*>(g_outputStorage+8+700)=DescriptorAddress(type);
    descriptors[type][2]=8;return DescriptorAddress(type);
}
int main() {
    definition[0x104/4]=reinterpret_cast<uint32_t>(upgrades);
    definition[0x108/4]=reinterpret_cast<uint32_t>(upgrades+2);
    other[0x104/4]=reinterpret_cast<uint32_t>(otherUpgrade);
    other[0x108/4]=reinterpret_cast<uint32_t>(otherUpgrade+1);
    uint32_t variants[3]{};
    CHECK(PublicTooltipVariants(57,variants)==3 && variants[0]==57 && variants[1]==58 && variants[2]==59);
    CHECK(PublicTooltipVariants(58,variants)==1 && variants[0]==58);
    CHECK(PublicTooltipVariants(1,variants)==2 && variants[1]==2);
    auto* output=g_outputStorage+8;
    *reinterpret_cast<uint32_t*>(output+496)=2;
    *reinterpret_cast<uint32_t*>(output+504)=57;
    *reinterpret_cast<uint32_t*>(output+600)=2;
    *reinterpret_cast<uint32_t*>(output+604)=1;
    *reinterpret_cast<uint32_t*>(output+640)=57;
    *reinterpret_cast<uint32_t*>(output+644)=1;
    uint32_t provider[20]{};provider[0]=reinterpret_cast<uint32_t>(originalMethods+1);
    provider[6]=123;provider[7]=456;provider[11]=789;
    unsigned char controller[80]{};
    *reinterpret_cast<uint32_t**>(controller+0x44)=provider;
    AttachProjectionTooltipProvider(controller);
    CHECK(provider[0]==reinterpret_cast<uint32_t>(originalMethods+1));
    auto* methods=reinterpret_cast<const uint32_t*>(provider[0]);
    CHECK(methods[-1]==originalMethods[0] && methods[2]==originalMethods[3]);
    CHECK(originalMethods[1]==reinterpret_cast<uint32_t>(ProjectionProviderWindow));
    CHECK(originalMethods[2]==reinterpret_cast<uint32_t>(ProjectionProviderRightClick));
    provider[3]=ProjectionTooltipDescriptor(57);
    *reinterpret_cast<uint32_t*>(output+384)=18;
    *reinterpret_cast<uint32_t*>(output+388)=12;
    *reinterpret_cast<uint32_t*>(output+524)=3;
    definition[0xdc/4]=leaf[0xdc/4]=alternate[0xdc/4]=2;
    definition[0x58/4]=2;leaf[0x58/4]=4;alternate[0x58/4]=6;
    // Native updater + cache must use the same choice as the RMB card.
    // The arena, slot and generation deliberately stay unchanged.
    auto range = [&]() {
        uint32_t frame[11]{};
        UpdateProjectionRange(0,frame);
        unsigned count=(frame[9]-frame[8])/8;
        free(reinterpret_cast<void*>(frame[8]));
        return count;
    };
    const unsigned baseRange=range();
    CHECK(baseRange>0 && range()==baseRange);
    unsigned upgradeRange=0;
    // Hover/auto-display must not consume the first explicit RMB.
    CHECK(ProjectionProviderWindow(provider,nullptr)==DescriptorAddress(57) && provider[4]==1);
    for (uint32_t type : {57u,58u,59u,57u,58u}) {
        ProjectionProviderRightClick(provider,nullptr);
        CHECK(ProjectionProviderWindow(provider,nullptr)==DescriptorAddress(type) && provider[4]==1);
        CHECK(g_tooltipController[9]==DescriptorAddress(type));
        CHECK(descriptors[type][2]==9);
        const unsigned selectedRange=range();
        if(type==58) { CHECK(selectedRange>baseRange);upgradeRange=selectedRange; }
        if(type==59) CHECK(selectedRange>upgradeRange);
        if(type==57) CHECK(selectedRange==baseRange);
    }
    CHECK(nativeClicks==5 && nativeWindows==6);
    // Another projection must not inherit a grade or cycle a stale descriptor.
    g_hoverX=12;g_hoverY=4;*reinterpret_cast<uint32_t*>(output+504)=1;
    ProjectionProviderRightClick(provider,nullptr);CHECK(g_tooltipChoice[1]==0);
    provider[3]=ProjectionTooltipDescriptor(1);
    ProjectionProviderRightClick(provider,nullptr);CHECK(provider[3]==DescriptorAddress(1) && provider[4]==1);
    ProjectionProviderRightClick(provider,nullptr);CHECK(provider[3]==DescriptorAddress(2) && provider[4]==1);
    CHECK(g_tooltipChoice[0]==1 && g_tooltipChoice[1]==1);
    // Known upgraded portraits keep stock compact/detailed mode behavior.
    *reinterpret_cast<uint32_t*>(output+644)=58;*reinterpret_cast<uint32_t*>(output+504)=58;
    provider[3]=ProjectionTooltipDescriptor(58);provider[4]=0;
    ProjectionProviderWindow(provider,nullptr);CHECK(provider[4]==0);
    ProjectionProviderRightClick(provider,nullptr);ProjectionProviderRightClick(provider,nullptr);
    CHECK(provider[4]==2 && provider[3]==DescriptorAddress(58));
    // Other providers, locked cards, empty ground and post-Start do not cycle.
    g_hoverX=13;g_hoverY=8;*reinterpret_cast<uint32_t*>(output+504)=57;
    provider[3]=9999;unsigned choice=g_tooltipChoice[0];ProjectionProviderRightClick(provider,nullptr);
    CHECK(g_tooltipChoice[0]==choice && provider[3]==9999);
    provider[3]=ProjectionTooltipDescriptor(58);provider[15]=1;ProjectionProviderRightClick(provider,nullptr);
    CHECK(g_tooltipChoice[0]==choice);provider[15]=0;
    g_hoverX=5;g_hoverY=5;ProjectionProviderRightClick(provider,nullptr);CHECK(g_tooltipChoice[0]==choice);
    g_hoverX=13;g_hoverY=8;*reinterpret_cast<uint32_t*>(output+496)=0;
    ProjectionProviderRightClick(provider,nullptr);CHECK(g_tooltipChoice[0]==choice);
    ResetProjectionTooltipChoices();for(unsigned item:g_tooltipChoice)CHECK(item==0);
    CHECK(g_tooltipClickSlot==-1);
    // Malformed or duplicate public links never cause out-of-bounds traversal.
    upgrades[1]=58;CHECK(PublicTooltipVariants(57,variants)==2);
    definition[0x108/4]=definition[0x104/4]+12;CHECK(PublicTooltipVariants(57,variants)==1);
    definition[0x108/4]=definition[0x104/4]-4;CHECK(PublicTooltipVariants(57,variants)==1);
    definition[0x108/4]=definition[0x104/4]+8;upgrades[1]=59;
    // Double LMB is delegated normally, but queues a read-only screen for the
    // selected public type. A blocking window and stale generations reject it.
    uint32_t screen[0x48c/4]{}, root[8]{}, windowMethods[16]{}, player[4]{};
    screen[0]=0xe1da84;screen[0x488/4]=reinterpret_cast<uint32_t>(g_placementOwner);
    screen[0xa0/4]=reinterpret_cast<uint32_t>(root);root[1]=reinterpret_cast<uint32_t>(referenceOffsets);
    root[4]=reinterpret_cast<uint32_t>(windowMethods);windowMethods[0x34/4]=reinterpret_cast<uint32_t>(HitWindow);
    screen[0x2b4/4]=reinterpret_cast<uint32_t>(player);player[3]=222;
    screen[0x2a8/4]=111;screen[0xf4/4]=333;g_projectionScreen=screen;
    *reinterpret_cast<uint32_t*>(output+496)=2;g_tooltipChoice[0]=1;
    const LPARAM point=MAKELPARAM(120,230);
    CHECK(ProjectionWindowProc(nullptr,WM_LBUTTONDOWN,0,point)==73 && g_detailsSlot==-1);
    detailsScreenActive=false;
    CHECK(ProjectionWindowProc(nullptr,WM_LBUTTONDBLCLK,0,point)==73 && g_detailsSlot==-1);
    detailsScreenActive=true;
    CHECK(ProjectionWindowProc(nullptr,WM_LBUTTONDBLCLK,0,point)==73 && g_detailsSlot==0);
    detailsScreenActive=false;
    ProjectionWindowProc(nullptr,WM_MOUSEMOVE,0,point);CHECK(g_detailsSlot==-1);
    detailsScreenActive=true;
    ProjectionWindowProc(nullptr,WM_LBUTTONDBLCLK,0,point);
    blockDetails=true;ProcessProjectionDetails();CHECK(queuedDetails==0 && !g_detailsHitTest);
    blockDetails=false;
    ProjectionWindowProc(nullptr,WM_LBUTTONDBLCLK,0,point);++g_placementGeneration;
    ProcessProjectionDetails();CHECK(queuedDetails==0);
    for(int failure=1;failure<=3;++failure) {
        failCreature=failure==1;failRotator=failure==2;failCommand=failure==3;
        ProjectionWindowProc(nullptr,WM_LBUTTONDBLCLK,0,point);ProcessProjectionDetails();
        CHECK(queuedDetails==0 && creatureObject[6]==0 && rotatorObject[6]==0);
    }
    failCreature=failRotator=failCommand=false;
    ProjectionWindowProc(nullptr,WM_LBUTTONDBLCLK,0,point);ProcessProjectionDetails();
    CHECK(queuedDetails==1 && detailsType==58 && creatureObject[6]==1 && rotatorObject[6]==1);
    CHECK(ProjectionDetailsCanRotate(rotatorObject,nullptr));
    ProjectionDetailsNext(rotatorObject,nullptr);CHECK(detailsType==59 && g_tooltipChoice[0]==2);
    ProjectionDetailsNext(rotatorObject,nullptr);CHECK(detailsType==57 && g_tooltipChoice[0]==0);
    ProjectionDetailsPrevious(rotatorObject,nullptr);CHECK(detailsType==59 && g_tooltipChoice[0]==2);
    failCreature=true;ProjectionDetailsNext(rotatorObject,nullptr);CHECK(g_tooltipChoice[0]==2);failCreature=false;
    *reinterpret_cast<uint32_t*>(output+640)=58;
    CHECK(!ProjectionDetailsCanRotate(rotatorObject,nullptr));
    ProjectionDetailsNext(rotatorObject,nullptr);CHECK(g_tooltipChoice[0]==2);
    *reinterpret_cast<uint32_t*>(output+640)=57;
    --rotatorObject[6];ReleaseDetails(rotatorObject+4);
    CHECK(creatureObject[6]==0 && alternateObject[6]==0);
    ReleaseProjectionDetailsRotator();
    // Managed refresh calls the rotator capability directly, outside the
    // intercepted factory call. It must stay enabled with native-only methods.
    uint32_t residentMethods[16];memcpy(residentMethods,originalRotatorMethods,sizeof(residentMethods));
    residentMethods[5]=reinterpret_cast<uint32_t>(NativeCapabilityAvailable);
    g_detailsNativeMethods=residentMethods+1;
    ProjectionWindowProc(nullptr,WM_LBUTTONDBLCLK,0,point);ProcessProjectionDetails(false);
    CHECK(queuedDetails==2 && g_detailsRotatorOwned && rotatorObject[6]==2);
    CHECK(rotatorObject[0]==reinterpret_cast<uint32_t>(g_detailsNativeMethods));
    auto* nativeMethods=reinterpret_cast<const uint32_t*>(rotatorObject[0]);
    CHECK(nativeMethods[-1]==originalRotatorMethods[0]);
    CHECK(reinterpret_cast<bool(__thiscall*)(void*)>(nativeMethods[4])(rotatorObject));
    ProjectionDetailsNext(rotatorObject,nullptr);CHECK(g_tooltipChoice[0]==0);
    ProjectionDetailsPrevious(rotatorObject,nullptr);CHECK(g_tooltipChoice[0]==2);
    ReleaseProjectionDetailsRotator();
    CHECK(rotatorObject[0]==reinterpret_cast<uint32_t>(originalRotatorMethods+1));
    CHECK(rotatorObject[6]==1); // Native screen still owns its reference.
    --rotatorObject[6];ReleaseDetails(rotatorObject+4);
    failCommand=true;
    ProjectionWindowProc(nullptr,WM_LBUTTONDBLCLK,0,point);ProcessProjectionDetails(false);
    CHECK(!g_detailsRotatorOwned && rotatorObject[6]==0);
    CHECK(rotatorObject[0]==reinterpret_cast<uint32_t>(originalRotatorMethods+1));
    failCommand=false;
    *reinterpret_cast<uint32_t*>(output+640)=58;
    *reinterpret_cast<uint32_t*>(output+504)=58;
    ProjectionWindowProc(nullptr,WM_LBUTTONDBLCLK,0,point);ProcessProjectionDetails(false);
    CHECK(queuedDetails==3);
    CHECK(rotatorObject[0]==reinterpret_cast<uint32_t>(originalRotatorMethods+1));
    CHECK(!ProjectionDetailsCanRotate(rotatorObject,nullptr));
    ReleaseProjectionDetailsRotator();--rotatorObject[6];ReleaseDetails(rotatorObject+4);
    *reinterpret_cast<uint32_t*>(output+496)=0;
    ProjectionWindowProc(nullptr,WM_LBUTTONDBLCLK,0,point);ProcessProjectionDetails();CHECK(queuedDetails==3);
    std::cout<<"public upgrade cycle and native fallback passed";
}
'''.replace('IMPLEMENTATION', implementation)
        for address, replacement in {'0x6b7eb0': 'reinterpret_cast<uintptr_t>(&Window)',
                                      '0x6b7790': 'reinterpret_cast<uintptr_t>(&Click)',
                                      '0x6b7880': 'reinterpret_cast<uintptr_t>(&Descriptor)',
                                      '0x878fd0': 'reinterpret_cast<uintptr_t>(&malloc)',
                                      '0x8790b0': 'reinterpret_cast<uintptr_t>(&free)',
                                      '0x4bd550': 'reinterpret_cast<uintptr_t>(&CreateCreature)',
                                      '0x789010': 'reinterpret_cast<uintptr_t>(&CreateRotator)',
                                      '0x789600': 'reinterpret_cast<uintptr_t>(&CreateDetails)',
                                      '0x838c10': 'reinterpret_cast<uintptr_t>(&SubmitDetails)',
                                      '0x8c6150': 'reinterpret_cast<uintptr_t>(&ReleaseDetails)',
                                      '0x669e10': 'reinterpret_cast<uintptr_t>(&ActiveDetailsScreen)',
                                      'CallWindowProcW': 'DispatchWindow',
                                      '0xe40468': 'reinterpret_cast<uintptr_t>(originalRotatorMethods)',
                                      '0xe4046c': 'reinterpret_cast<uintptr_t>(originalRotatorMethods+1)',
                                      '0xe34b70': 'reinterpret_cast<uintptr_t>(originalMethods)',
                                      '0xe34b74': 'reinterpret_cast<uintptr_t>(originalMethods+1)'}.items():
            driver = driver.replace(address, replacement)
        with tempfile.TemporaryDirectory(prefix='workshop-tooltip-') as directory:
            temporary=Path(directory)
            (temporary/'tooltip.cpp').write_text(driver, encoding='utf-8')
            (temporary/'build.cmd').write_text(f'@call "{setup}" x86 >nul\n@if errorlevel 1 exit /b 1\n'
                                              '@cl /nologo /EHsc /O2 /std:c++20 /Fe:tooltip.exe tooltip.cpp\n', encoding='utf-8')
            build=subprocess.run(['cmd','/d','/c',str(temporary/'build.cmd')],cwd=temporary,capture_output=True)
            self.assertEqual(build.returncode,0,build.stdout.decode(errors='replace')+build.stderr.decode(errors='replace'))
            completed=subprocess.run([str(temporary/'tooltip.exe')],capture_output=True,text=True)
            self.assertEqual(completed.returncode,0,completed.stdout+completed.stderr)
            self.assertIn('passed',completed.stdout)

    def test_projection_glow_owns_only_its_effect_and_releases_failures(self):
        # Setup: compile the production glow code. Fake only the fixed native
        # engine boundary; no game, windows, cursor or real rendering is used.
        source = preview_source()
        implementation = 'struct ProjectionGlow {' + source.split('struct ProjectionGlow {', 1)[1].split(
            'struct PlacementAggregate {', 1)[0]
        setup = vcvarsall()
        if not setup.is_file():
            self.skipTest('MSVC x86 build tools are required for native glow ownership checks')
        driver = r'''
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <cstdint>
#include <cstring>
#include <cstdlib>
#include <cassert>
#include <set>
#include <map>
#include <iostream>
#undef assert
#define assert(condition) do { if (!(condition)) { std::cerr << "check failed at " << __LINE__ << ": " << #condition << " error=" << GetLastError(); ExitProcess(3); } } while (0)
uint32_t g_rendererFactoryArgument = 0, g_hoverX = 31, g_hoverY = 31;
unsigned char g_outputStorage[4104]{};
int g_cell[14]{};
unsigned g_glowPreset = 0;
void UpdateProjectionGlowPreset() {} // OS keyboard/window boundary is excluded here.
uint32_t* __cdecl Allocate(unsigned bytes);
void __fastcall ReleaseStrong(uint32_t* object, void*, uint32_t mask);
void __fastcall ReleaseHolder(uint32_t* object, void*);
void __fastcall Colorer(uint32_t* object, void*, uint32_t* color);
uint32_t* __fastcall Bind(void* view, void*, const uint32_t* parts, uint32_t* colorer);
IMPLEMENTATION
std::set<uint32_t*> allocated;
std::map<uint32_t*, uint32_t*> bindings;
unsigned allocations = 0, failAt = 0;
bool failBinding = false, emptyBinding = false;
uint32_t* expectedParts = nullptr;
uint32_t* __cdecl Allocate(unsigned bytes) {
    ++allocations;
    if (allocations == failAt) return nullptr;
    auto* object = static_cast<uint32_t*>(calloc(1, bytes));
    assert(object); allocated.insert(object); return object;
}
void Destroy(uint32_t* object) {
    assert(allocated.count(object));
    if ((object[1] & 0x7fffffff) || object[2]) return;
    if (object[0] == 0xe807d8 && bindings.count(object)) {
        auto* colorer = bindings.at(object); bindings.erase(object);
        assert(colorer[2] > 0); --colorer[2]; Destroy(colorer);
    } else if (object[0] == 0xe30b08) {
        auto* color = reinterpret_cast<uint32_t*>(object[3]);
        assert(color[1] > 0); --color[1]; Destroy(color);
    }
    allocated.erase(object); free(object);
}
void __fastcall ReleaseStrong(uint32_t* object, void*, uint32_t mask) {
    assert(mask == 0xfffff); Destroy(object);
}
void __fastcall ReleaseHolder(uint32_t* object, void*) { Destroy(object); }
void __fastcall Colorer(uint32_t* object, void*, uint32_t* color) {
    assert(allocated.count(object) && allocated.count(color));
    object[0] = 0xe30b08; object[3] = reinterpret_cast<uint32_t>(color); ++color[1];
}
uint32_t* __fastcall Bind(void* view, void*, const uint32_t* parts, uint32_t* colorer) {
    assert(reinterpret_cast<uint32_t>(view) == g_rendererFactoryArgument);
    assert(parts == expectedParts && parts[0] != parts[1]);
    assert(colorer[0] == 0xe30b08 && colorer[2] == 1);
    if (failBinding) return nullptr;
    auto* node = Allocate(0x18); assert(node); node[0] = 0xe807d8;
    if (!emptyBinding) {
        node[3] = parts[0]; node[4] = parts[1]; node[5] = parts[2];
        ++colorer[2]; bindings[node] = colorer;
    }
    return node;
}
int main() {
    uint32_t methods[40]{}; methods[31]=0xb75ed0;
    uint32_t view[]={reinterpret_cast<uint32_t>(methods)};
    uint32_t parts[]={0x123400};
    uint32_t node[]={0xe807d8,0,0,reinterpret_cast<uint32_t>(parts),reinterpret_cast<uint32_t>(parts+1),reinterpret_cast<uint32_t>(parts+1)};
    uint32_t fader[]={0xe8bfc4,0,0,0,0,reinterpret_cast<uint32_t>(node)};
    expectedParts=node+3; g_rendererFactoryArgument=reinterpret_cast<uint32_t>(view);
    auto* output=g_outputStorage+8;
    for(unsigned index=0;index<7;++index) {
        *reinterpret_cast<uint32_t*>(output+index*32)=reinterpret_cast<uint32_t>(fader);
        *reinterpret_cast<uint32_t*>(output+600+index*4)=2;
        g_cell[index*2]=13; g_cell[index*2+1]=8;
    }
    // Exercise + Verify: empty and foreign inputs have no engine allocations.
    UpdateProjectionGlows(); assert(allocated.empty() && allocations==0);
    *reinterpret_cast<uint32_t*>(output+496)=1;
    methods[31]=0; UpdateProjectionGlows(); assert(allocated.empty()); methods[31]=0xb75ed0;
    fader[0]=0; UpdateProjectionGlows(); assert(allocated.empty()); fader[0]=0xe8bfc4;
    // Exercise + Verify: seven effects persist, update color without allocation,
    // and release all effect/color ownership exactly once on cleanup.
    *reinterpret_cast<uint32_t*>(output+496)=7;
    UpdateProjectionGlows(); assert(allocated.size()==21 && bindings.size()==7);
    const auto before=allocations; UpdateProjectionGlows(); assert(allocations==before);
    g_hoverX=13;g_hoverY=8; UpdateProjectionGlows(); assert(allocations==before);
    for(auto& glow:g_glows) {
        assert(glow.node && glow.color && glow.preset==0);
        assert(reinterpret_cast<float*>(glow.color+5)[3]==0.06f);
    }
    g_hoverX=31;g_hoverY=31;UpdateProjectionGlows();
    for(auto& glow:g_glows) assert(glow.preset==0 && reinterpret_cast<float*>(glow.color+5)[3]==0.06f);
    for (unsigned preset=0;preset<5;++preset) {
        g_glowPreset=preset;UpdateProjectionGlows();assert(allocations==before);
        for (auto& glow:g_glows) {
            assert(glow.preset==preset);
            assert(memcmp(glow.color+5,kGlowPresets[preset],16)==0);
        }
    }
    ReleaseProjectionGlows();ReleaseProjectionGlows();assert(allocated.empty() && bindings.empty());
    // Exercise + Verify: every preparation failure leaves no owned object behind.
    *reinterpret_cast<uint32_t*>(output+496)=1;
    for(unsigned scenario=1;scenario<=4;++scenario) {
        allocations=0; failAt=scenario<=2?scenario:0;
        failBinding=scenario==3;emptyBinding=scenario==4;
        UpdateProjectionGlows(); assert(allocated.empty() && bindings.empty());
        assert(!g_glows[0].node && !g_glows[0].color);
    }
    std::cout << "glow ownership, hover, foreign inputs and allocation failures passed";
}
'''.replace('IMPLEMENTATION', implementation)
        # Substitute only native entry addresses, preserving all production
        # branches/refcounts and the x86 thiscall/cdecl stack contracts.
        for address, boundary in {'0x878fd0': 'Allocate', '0x6804e0': 'Colorer', '0xb75ed0': 'Bind',
                                  '0x8c61d0': 'ReleaseStrong', '0x8c6150': 'ReleaseHolder'}.items():
            driver = driver.replace(address, f'reinterpret_cast<uintptr_t>(&{boundary})')
        with tempfile.TemporaryDirectory(prefix='workshop-glow-') as directory:
            temporary = Path(directory)
            (temporary / 'glow.cpp').write_text(driver, encoding='utf-8')
            (temporary / 'build.cmd').write_text(
                f'@call "{setup}" x86 >nul\n@if errorlevel 1 exit /b 1\n'
                '@cl /nologo /EHsc /O2 /std:c++20 /Fe:glow.exe glow.cpp\n', encoding='utf-8')
            build = subprocess.run(['cmd', '/d', '/c', str(temporary / 'build.cmd')], cwd=temporary, capture_output=True)
            self.assertEqual(build.returncode, 0, build.stdout.decode(errors='replace') + build.stderr.decode(errors='replace'))
            completed = subprocess.run([str(temporary / 'glow.exe')], capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            self.assertIn('passed', completed.stdout)

    def test_public_movement_range_obeys_costs_obstacles_flight_and_full_footprints(self):
        # Setup: compile the production calculation itself as a standalone x86
        # program. No process memory, game, renderer or hidden army is involved.
        source = preview_source()
        calculation = 'int ComputeProjectionRange(' + source.split('int ComputeProjectionRange(', 1)[1].split(
            '// Native highlight vectors', 1)[0]
        compiler_setup = vcvarsall()
        if not compiler_setup.is_file():
            self.skipTest('MSVC x86 build tools are required for the production range calculation')
        driver = r'''
#include <iostream>
#include <limits>
CALCULATION
int main() {
    int width, height, x, y, size, speed, flying;
    std::cin >> width >> height >> x >> y >> size >> speed >> flying;
    unsigned char blocked[1024]{};
    for (int index = 0; index < width * height && index < 1024; ++index) {
        int value; std::cin >> value; blocked[index] = static_cast<unsigned char>(value);
    }
    int guarded[2050];
    for (int& value : guarded) value = 0x12345678;
    int count = ComputeProjectionRange(blocked, width, height, x, y, size, speed, flying != 0, guarded + 1);
    if (guarded[0] != 0x12345678 || guarded[2049] != 0x12345678) return 2;
    std::cout << count;
    for (int index = 0; index < count * 2; ++index) std::cout << ' ' << guarded[index + 1];
}
'''.replace('CALCULATION', calculation)
        with tempfile.TemporaryDirectory(prefix='workshop-range-') as directory:
            temporary = Path(directory)
            (temporary / 'range.cpp').write_text(driver, encoding='utf-8')
            (temporary / 'build.cmd').write_text(
                f'@call "{compiler_setup}" x86 >nul\n@if errorlevel 1 exit /b 1\n'
                '@cl /nologo /EHsc /O2 /std:c++20 /Fe:range.exe range.cpp\n', encoding='utf-8')
            build = subprocess.run(['cmd', '/d', '/c', str(temporary / 'build.cmd')],
                                   cwd=temporary, capture_output=True)
            self.assertEqual(build.returncode, 0, build.stdout.decode(errors='replace') + build.stderr.decode(errors='replace'))

            def run_case(width, height, origin, size, speed, flying, blocked):
                payload = ' '.join(map(str, (width, height, *origin, size, speed, int(flying)))) + '\n'
                payload += ' '.join(str(int((index % width, index // width) in blocked))
                                    for index in range(min(width * height, 1024)))
                # Exercise: call the compiled production code and retain buffer guards.
                completed = subprocess.run([str(temporary / 'range.exe')], input=payload,
                                           text=True, capture_output=True, check=True)
                numbers = [int(value) for value in completed.stdout.split()]
                self.assertEqual(len(numbers), 1 + max(0, numbers[0]) * 2)
                return numbers[0], set(zip(numbers[1::2], numbers[2::2]))

            # Verify: a one-step budget excludes diagonals; a two-step budget
            # includes one diagonal but excludes two. This distinguishes 2/3
            # native costs from Chebyshev and Manhattan radius shortcuts.
            count, reached = run_case(16, 12, (8, 6), 1, 1, False, set())
            self.assertEqual(reached, {(8, 6), (7, 6), (9, 6), (8, 5), (8, 7)})
            self.assertEqual(count, 5)
            _, reached = run_case(16, 12, (8, 6), 1, 2, False, set())
            self.assertIn((9, 7), reached)
            self.assertIn((10, 6), reached)
            self.assertNotIn((10, 8), reached)

            wall = {(7, row) for row in range(1, 11)}
            for flying in (False, True):
                with self.subTest(flying=flying):
                    _, reached = run_case(16, 12, (5, 5), 1, 5, flying, wall)
                    self.assertEqual((9, 5) in reached, flying)
                    self.assertFalse(reached & wall)

            # A single-cell corridor admits a small creature, never a 2x2 one.
            corridor = {(7, row) for row in range(1, 11) if row == 1 or row >= 3}
            _, small = run_case(16, 12, (5, 2), 1, 8, False, corridor)
            _, large = run_case(16, 12, (5, 2), 2, 8, False, corridor)
            self.assertIn((9, 2), small)
            self.assertFalse(any(x >= 7 for x, y in large))
            _, large_flying = run_case(16, 12, (5, 2), 2, 8, True, corridor)
            self.assertIn((9, 2), large_flying)
            self.assertFalse(large_flying & corridor)
            self.assertEqual(run_case(16, 12, (5, 2), 2, 0, False, set())[1], {(4, 1), (5, 1), (4, 2), (5, 2)})
            self.assertEqual(run_case(16, 12, (5, 2), 2, 8, False, {(4, 1)})[0], 0)
            for width, height, origin, size, speed in ((33, 12, (5, 2), 1, 2), (16, 12, (2, 2), 2, 2),
                                                      (16, 12, (5, 2), 3, 2), (16, 12, (5, 2), 1, -1)):
                with self.subTest(invalid=(width, height, origin, size, speed)):
                    self.assertEqual(run_case(width, height, origin, size, speed, False, set())[0], -1)
            count, reached = run_case(32, 32, (16, 16), 1, 2147483647, False, set())
            self.assertEqual(count, 28 * 30)
            self.assertTrue(all(2 <= x <= 29 and 1 <= y <= 30 for x, y in reached))

            # Independent oracle: execute the pinned engine's actual path walk
            # against authored masks. Only malloc/free are replaced; the native
            # queue, neighbour expansion and cost arithmetic run unmodified.
            import pefile
            from unicorn import UC_HOOK_CODE
            from unicorn.x86_const import UC_X86_REG_EIP
            executable_path = WORKSPACE / '.local/test-game/bin/H5_Game.exe'
            if not executable_path.is_file():
                self.skipTest('Pinned game EXE is needed for the native movement oracle')
            self.assertEqual(hashlib.sha256(executable_path.read_bytes()).hexdigest(), probe.HASHES['H5_Game.exe'])
            executable = pefile.PE(str(executable_path))
            image_base = executable.OPTIONAL_HEADER.ImageBase
            native_image = executable.get_memory_mapped_image()

            def native_reached(origin, size, speed, flying, obstacles):
                width, height = 16, 12
                free = {(x, y) for y in range(size, height - 1) for x in range(size + 1, width - 2)
                        if not any((column, row) in obstacles for row in range(y - size + 1, y + 1)
                                   for column in range(x - size + 1, x + 1))}
                machine = Uc(UC_ARCH_X86, UC_MODE_32)
                machine.mem_map(image_base, (executable.OPTIONAL_HEADER.SizeOfImage + 4095) & ~4095)
                machine.mem_write(image_base, native_image)
                machine.mem_map(0x2000000, 0x600000)
                nodes, rows, context, starting, stop = 0x2200000, 0x2210000, 0x2220000, 0x2220100, 0x2230000
                for y in range(height):
                    machine.mem_write(rows + y * 4, struct.pack('<I', nodes + y * width * 8))
                    for x in range(width):
                        blocked = (x < size + 1 or x > width - 3 or y < size or y > height - 2
                                   or (not flying and (x, y) not in free))
                        machine.mem_write(nodes + (y * width + x) * 8,
                                          struct.pack('<2I', 0, x | (y << 6) | (0x800000 if blocked else 0)))
                machine.mem_write(context, struct.pack('<6I', nodes, rows, width, height, 1, speed * 2))
                machine.mem_write(starting, struct.pack('<2I', *origin))
                machine.mem_write(0x2080000, struct.pack('<2I', stop, starting))
                machine.reg_write(UC_X86_REG_ESP, 0x2080000)
                machine.reg_write(UC_X86_REG_ECX, context)
                heap = [0x2400000]

                def allocate_boundary(cpu, address, instruction_size, user_data):
                    if address in (0x878fd0, 0x8791f0, 0x8790b0, 0x879240):
                        stack = cpu.reg_read(UC_X86_REG_ESP)
                        returned, argument = struct.unpack('<2I', cpu.mem_read(stack, 8))
                        if address in (0x878fd0, 0x8791f0):
                            allocated = heap[0]
                            heap[0] += (argument + 15) & ~15
                            self.assertLess(heap[0], 0x2600000)
                            cpu.reg_write(UC_X86_REG_EAX, allocated)
                        cpu.reg_write(UC_X86_REG_ESP, stack + 4)
                        cpu.reg_write(UC_X86_REG_EIP, returned)

                machine.hook_add(UC_HOOK_CODE, allocate_boundary)
                machine.emu_start(0xb5f0d0, stop, count=2000000)
                self.assertEqual(machine.reg_read(UC_X86_REG_EIP), stop)
                anchors = {(x, y) for x, y in free if struct.unpack('<I', machine.mem_read(
                    nodes + (y * width + x) * 8 + 4, 4))[0] & 0x1000}
                return {(column, row) for x, y in anchors for row in range(y - size + 1, y + 1)
                        for column in range(x - size + 1, x + 1)}

            generator = random.Random(20260923)
            for size in (1, 2):
                origin = (8, 6)
                for flying in (False, True):
                    for speed in (0, 1, 3, 7):
                        obstacles = {(x, y) for y in range(1, 11) for x in range(2, 14)
                                     if generator.random() < 0.18}
                        obstacles -= {(x, y) for x in range(9 - size, 9) for y in range(7 - size, 7)}
                        with self.subTest(native_oracle=(size, flying, speed)):
                            actual = run_case(16, 12, origin, size, speed, flying, obstacles)[1]
                            self.assertEqual(actual, native_reached(origin, size, speed, flying, obstacles))

    def test_native_battle_rng_uses_two_steps_and_signed_shift(self):
        import pefile
        from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
        from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_ECX, UC_X86_REG_EAX
        game = WORKSPACE / '.local/test-game/bin/H5_Game.exe'
        if not game.is_file():
            self.skipTest('Pinned game EXE is needed for the native RNG oracle')
        self.assertEqual(hashlib.sha256(game.read_bytes()).hexdigest(), probe.HASHES['H5_Game.exe'])
        executable = pefile.PE(str(game))
        image_base = executable.OPTIONAL_HEADER.ImageBase
        machine = Uc(UC_ARCH_X86, UC_MODE_32)
        machine.mem_map(image_base, (executable.OPTIONAL_HEADER.SizeOfImage + 4095) & ~4095)
        machine.mem_write(image_base, executable.get_memory_mapped_image())
        machine.mem_map(0x2000000, 0x10000)
        # Persistence notification is the sole replaced helper. Original
        # overflow, arithmetic shift, XOR, remainder and x87 conversion execute.
        machine.mem_write(0x50c020, b'\xc3')
        actor, stack, stop, output = 0x2001000, 0x2008000, 0x2002000, 0x2003000
        for seed in (0, 1, 0x75bcd15, 0x7fffffff, 0x80000000, 0xffffffff):
            state = seed
            machine.mem_write(actor + 8, struct.pack('<I', state))
            for bound in (0, 1, 7, 0xffffffff, 0x80000000):
                with self.subTest(seed=seed, bound=bound):
                    previous = state
                    if bound:
                        first = (state * 0x343fd + 0x269ec3) & 0xffffffff
                        state = (first * 0x343fd + 0x269ec3) & 0xffffffff
                        signed = first if first < 0x80000000 else first - 0x100000000
                        mixed = ((signed >> 7) ^ (state << 6)) & 0xffffffff
                        expected = mixed % bound
                    else:
                        expected = 0
                    machine.mem_write(stack, struct.pack('<2I', stop, bound))
                    machine.reg_write(UC_X86_REG_ESP, stack)
                    machine.reg_write(UC_X86_REG_ECX, actor)
                    machine.emu_start(0x8c0470, stop, count=1000)
                    self.assertEqual(machine.reg_read(UC_X86_REG_EAX), expected)
                    self.assertEqual(struct.unpack('<I', machine.mem_read(actor + 8, 4))[0], state)
                    self.assertEqual(machine.reg_read(UC_X86_REG_ESP), stack + 8)
                    if not bound:
                        self.assertEqual(state, previous)
            for _ in range(8):
                first = (state * 0x343fd + 0x269ec3) & 0xffffffff
                state = (first * 0x343fd + 0x269ec3) & 0xffffffff
                signed = first if first < 0x80000000 else first - 0x100000000
                mixed = ((signed >> 7) ^ (state << 6)) & 0xffffffff
                expected_bytes = struct.pack('<f', mixed * 0.25 / 0x100000000)
                machine.mem_write(stop, b'\xd9\x1d' + struct.pack('<I', output))
                machine.mem_write(stack, struct.pack('<Iff', stop, 0.0, 0.25))
                machine.reg_write(UC_X86_REG_ESP, stack)
                machine.reg_write(UC_X86_REG_ECX, actor)
                machine.emu_start(0x8c04e0, stop + 6, count=1000)
                self.assertEqual(bytes(machine.mem_read(output, 4)), expected_bytes)
                self.assertEqual(struct.unpack('<I', machine.mem_read(actor + 8, 4))[0], state)
                self.assertEqual(machine.reg_read(UC_X86_REG_ESP), stack + 12)

        observer_source = (MOD_ROOT / 'scripts/accuracy-campaign.py').read_text()
        assembly = observer_source.split('def install_initial_atb_observer(', 1)[1].split(
            "        assembly = f'''", 1)[1].split("'''", 1)[0]
        assembly = re.sub(r'\{records(?: \+ (\d+))?\}',
                          lambda match: str(0x305000 + int(match.group(1) or 0)), assembly)
        code = bytes(keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32).asm(assembly, 0x300000)[0])
        for armed, count, caller in ((0, 0, 0xa74107), (1, 0, 0xa74107),
                                     (1, 127, 0xa74107), (1, 128, 0xa74107), (1, 0, 0x111111)):
            with self.subTest(observer=(armed, count, caller)):
                cpu = Uc(UC_ARCH_X86, UC_MODE_32)
                cpu.mem_map(0x200000, 65536)
                cpu.mem_map(0x300000, 65536)
                cpu.mem_write(0x300000, code)
                cpu.mem_write(0x304ff0, b'\xa5' * (16 + 2576 + 16))
                cpu.mem_write(0x305000, struct.pack('<4I', armed, count, 0, 0))
                cpu.mem_write(0x204008, struct.pack('<I', 0x81234567))
                cpu.mem_write(0x208000, struct.pack('<Iff', caller, 0.0, 0.25))
                cpu.reg_write(UC_X86_REG_ESP, 0x208000)
                cpu.reg_write(UC_X86_REG_ECX, 0x204000)
                cpu.emu_start(0x300000, 0x8c04e6, count=1000)
                accepted = armed and caller == 0xa74107 and count < 128
                self.assertEqual(struct.unpack('<2I', cpu.mem_read(0x305004, 8)),
                                 (count + int(accepted), int(armed and caller == 0xa74107 and count >= 128)))
                if accepted:
                    self.assertEqual(struct.unpack('<5I', cpu.mem_read(0x305010 + count * 20, 20)),
                                     (0x204000, 0x81234567, caller, 0, 0x3e800000))
                else:
                    self.assertEqual(bytes(cpu.mem_read(0x305010, 2560)), b'\xa5' * 2560)
                self.assertEqual(bytes(cpu.mem_read(0x304ff0, 16)), b'\xa5' * 16)
                self.assertEqual(bytes(cpu.mem_read(0x305a10, 16)), b'\xa5' * 16)
                self.assertEqual(cpu.reg_read(UC_X86_REG_ESP), 0x208000)
                self.assertEqual(cpu.reg_read(UC_X86_REG_ECX), 0x203fe4)
                self.assertEqual(cpu.reg_read(UC_X86_REG_EAX), 0x81234567)
                self.assertEqual(struct.unpack('<I', cpu.mem_read(0x204008, 4))[0], 0x81234567)

    def test_auxiliary_bridge_captures_return_value_and_preserves_epilogue(self):
        from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
        from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_EAX, UC_X86_REG_EDI, UC_X86_REG_FPCW
        source = preview_source()
        assembly = source.split('__declspec(naked) void AuxiliaryPowerHook()', 1)[1].split('__asm {', 1)[1].split('}', 1)[0]
        assembly = assembly.replace('CaptureSuperadminAuxiliaryPower','0x300800').replace(
            'CaptureAreaSpellInput','0x300900').replace('kAuxiliaryPowerResume','0xbfa4aa')
        assembler = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32)
        cpu=Uc(UC_ARCH_X86,UC_MODE_32)
        cpu.mem_map(0x200000,65536);cpu.mem_map(0x300000,65536)
        cpu.mem_write(0x300200,bytes(assembler.asm(assembly,0x300200)[0]))
        callback=('mov eax,dword ptr [esp+4]; mov dword ptr [0x301100],eax; '
                  'mov eax,dword ptr [esp+8]; mov dword ptr [0x301104],eax; '
                  'mov eax,dword ptr [esp+12]; mov dword ptr [0x301108],eax; fninit; ret')
        cpu.mem_write(0x300800,bytes(assembler.asm(callback,0x300800)[0]))
        cpu.mem_write(0x300900,bytes(assembler.asm(callback.replace('0x30110','0x30120'),0x300900)[0]))
        cpu.mem_write(0x208000,struct.pack('<I',0x205000))
        cpu.mem_write(0x20800c,struct.pack('<I',24))
        cpu.mem_write(0x20801c,struct.pack('<I',0xbfbb90))
        cpu.mem_write(0x208020,struct.pack('<2I',4,1))
        cpu.reg_write(UC_X86_REG_ESI,0x206000)
        cpu.reg_write(UC_X86_REG_ESP,0x208000);cpu.reg_write(UC_X86_REG_EDI,0x204000)
        cpu.reg_write(UC_X86_REG_FPCW,0x0c7f)
        cpu.emu_start(0x300200,0xbfa4aa,count=2000)
        self.assertEqual(struct.unpack('<3I',cpu.mem_read(0x301100,12)),(0x205000,24,0xbfbb90))
        self.assertEqual(struct.unpack('<3I',cpu.mem_read(0x301200,12)),(0x206000,4,1))
        self.assertEqual(cpu.reg_read(UC_X86_REG_ESP),0x208004)
        self.assertEqual(cpu.reg_read(UC_X86_REG_EAX),24)
        self.assertEqual(cpu.reg_read(UC_X86_REG_EDI),0x205000)
        self.assertEqual(cpu.reg_read(UC_X86_REG_FPCW),0x0c7f)

    def test_hero_bridge_captures_scalars_and_replays_integer_add(self):
        from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
        from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_EDI, UC_X86_REG_FPCW
        source = preview_source()
        assembly = source.split('__declspec(naked) void HeroCorrectionHook()', 1)[1].split('__asm {', 1)[1].split('}', 1)[0]
        assembly = assembly.replace('CaptureSuperadminHeroCorrection', '0x300800').replace('kHeroCorrectionResume', '0xbfc135')
        assembler = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32)
        cpu = Uc(UC_ARCH_X86, UC_MODE_32)
        cpu.mem_map(0x200000, 65536)
        cpu.mem_map(0x300000, 65536)
        cpu.mem_write(0x300200, bytes(assembler.asm(assembly, 0x300200)[0]))
        callback = ('mov eax,dword ptr [esp+4]; mov dword ptr [0x301100],eax; '
                    'mov eax,dword ptr [esp+8]; mov dword ptr [0x301104],eax; '
                    'mov eax,dword ptr [esp+12]; mov dword ptr [0x301108],eax; fninit; mov eax,123; ret')
        cpu.mem_write(0x300800, bytes(assembler.asm(callback, 0x300800)[0]))
        cpu.mem_write(0x208028, struct.pack('<I', 0x11223344))
        for register, value in ((UC_X86_REG_ESP,0x208000),(UC_X86_REG_EAX,2),(UC_X86_REG_EBX,3),
                                (UC_X86_REG_EDI,0x205000),(UC_X86_REG_FPCW,0x0c7f)):
            cpu.reg_write(register,value)
        cpu.emu_start(0x300200,0xbfc135,count=2000)
        self.assertEqual(struct.unpack('<3I',cpu.mem_read(0x301100,12)),(0x205000,3,2))
        self.assertEqual(cpu.reg_read(UC_X86_REG_EBX),5)
        self.assertEqual(cpu.reg_read(UC_X86_REG_EAX),0x11223344)
        self.assertEqual(cpu.reg_read(UC_X86_REG_ESP),0x208000)
        self.assertEqual(cpu.reg_read(UC_X86_REG_FPCW),0x0c7f)

    def test_hero_action_correction_matches_original_scalar_arithmetic(self):
        import pefile
        from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
        from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_EDI, UC_X86_REG_FPCW
        game = WORKSPACE / '.local/test-game/bin/H5_Game.exe'
        self.assertTrue(game.is_file(), 'Pinned EXE required for the hero-correction oracle')
        self.assertEqual(hashlib.sha256(game.read_bytes()).hexdigest(), probe.HASHES['H5_Game.exe'])
        executable = pefile.PE(str(game))
        base = executable.OPTIONAL_HEADER.ImageBase
        cpu = Uc(UC_ARCH_X86, UC_MODE_32)
        cpu.mem_map(base, (executable.OPTIONAL_HEADER.SizeOfImage + 4095) & ~4095)
        cpu.mem_write(base, executable.get_memory_mapped_image())
        cpu.mem_map(0x2000000, 65536)
        cases = []
        for control in (0x037f, 0x0c7f):
            for factor, first, second in ((1.337, 0, 2), (0.5, 0, 0), (1.125, 7, 3),
                                          (0.9, -4, 1), (1.0, 2147483647, 1)):
                cpu.mem_write(0x2001014, struct.pack('<f', factor))
                cpu.mem_write(0x2008000, bytes(80))
                cpu.reg_write(UC_X86_REG_ESP, 0x2008000)
                cpu.reg_write(UC_X86_REG_EAX, second)
                cpu.reg_write(UC_X86_REG_EBX, first & 0xffffffff)
                cpu.reg_write(UC_X86_REG_EDI, 0x2001000)
                cpu.reg_write(UC_X86_REG_FPCW, control)
                cpu.emu_start(0xbfc12f, 0xbfc149, count=1000)
                # Native cleanup between the two arithmetic segments is not
                # executed; it does not transform the saved float adjustment.
                cpu.emu_start(0xbfc172, 0xbfc182, count=1000)
                expected = struct.unpack('<I', cpu.mem_read(0x2001014, 4))[0]
                cases.append(f'{{{control}, {repr(float(factor))}f, {first}, {second}, {expected}u}}')
        source = preview_source()
        implementation = 'struct PlacementAggregate {' + source.split(
            'struct PlacementAggregate {', 1)[1].split('void CaptureKnownHeroModifiers(', 1)[0]
        driver = '#include <cstdint>\n#include <cstring>\n#include <cassert>\n' + implementation
        driver += 'int main() { struct Case { unsigned short control; float factor; int first,second; uint32_t expected; };'
        driver += 'const Case cases[]={' + ','.join(cases) + '};'
        driver += ('for(const auto& item:cases) { unsigned short control=item.control; __asm { fldcw control }'
                   'float result=ApplyHeroActionCorrection(item.factor,item.first,item.second); uint32_t bits;'
                   'memcpy(&bits,&result,4); assert(bits==item.expected); } return 0;}')
        with tempfile.TemporaryDirectory(prefix='workshop-hero-correction-') as directory:
            temporary = Path(directory)
            (temporary / 'hero.cpp').write_text(driver, encoding='utf-8')
            (temporary / 'build.cmd').write_text(
                f'@call "{vcvarsall()}" x86 >nul\n@if errorlevel 1 exit /b 1\n'
                '@cl /nologo /EHsc /O2 /std:c++20 /Fe:hero.exe hero.cpp\n', encoding='utf-8')
            build = subprocess.run(['cmd', '/d', '/c', str(temporary / 'build.cmd')], cwd=temporary, capture_output=True)
            self.assertEqual(build.returncode, 0, build.stdout.decode(errors='replace') + build.stderr.decode(errors='replace'))
            result = subprocess.run([str(temporary / 'hero.exe')], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))

    def test_owned_defence_selection_uses_frozen_capabilities_strict_thresholds_and_guards(self):
        source = preview_source()
        declarations = 'struct FrozenActorInput {' + source.split('struct FrozenActorInput {', 1)[1].split('void* g_creatureDefinition', 1)[0]
        core = 'struct PlacementAggregate {' + source.split('struct PlacementAggregate {', 1)[1].split('void CaptureKnownHeroModifiers(', 1)[0]
        builder = 'bool ReadFrozenRunicContribution(' + source.split('bool ReadFrozenRunicContribution(', 1)[1].split('void PrepareSuperadminAggregates()', 1)[0]
        strategy = 'bool BuildFrozenOwnSubset(' + source.split('bool BuildFrozenOwnSubset(', 1)[1].split('void __cdecl CaptureScriptedSource(', 1)[0]
        driver = r'''
#include <windows.h>
#include <cstdint>
#include <cstring>
#include <cassert>
bool g_superadminEnabled=true,g_predictedDefensive=false;
bool g_useSpreadRows=false,g_knownHeroLarge=false;
uint32_t g_estimatedSpreadDenominator=0;
volatile LONG g_attackGeneration=1,g_placementGeneration=1,g_superadminSourceGeneration=1,g_superadminSourceCount=2;
uint32_t g_superadminSourceTypes[7]{3,6},g_superadminSourceCounts[7]{40,15};
'''+declarations+core+builder+r'''
const uintptr_t kCreatureDefinition=0x89fbf0;
int definition[64]{};
const int* __fastcall Definition(uint32_t) { return definition; }
int __fastcall Evaluate(const PlacementAggregate* aggregate,void*,const PlacementAggregate*) { return aggregate->extra2; }
int totalPower=100,enemyRanged=40,ownRanged=20;
unsigned char settings[0xc04]{};
int __fastcall Total(const PlacementAggregate*,void*,const PlacementAggregate*) { return totalPower; }
int __fastcall Ranged(const PlacementAggregate* aggregate,void*,const PlacementAggregate*) {
    return aggregate==reinterpret_cast<const PlacementAggregate*>(g_actorCoreWords[1]) ? enemyRanged : ownRanged;
}
const unsigned char* __cdecl Settings() { return settings; }
'''+strategy+r'''
int main() {
    *reinterpret_cast<float*>(settings+0xbfc)=0.2f;
    *reinterpret_cast<float*>(settings+0xc00)=1.3f;
    g_actorInputsFrozen=true;g_actorInputGeneration=1;g_actorCoreMask=3;g_actorInputCount=3;
    g_actorCoreInputEnds[0]=1;g_actorCoreStackCounts[0]=1;
    g_actorCoreInputEnds[1]=3;g_actorCoreStackCounts[1]=2;
    g_actorInputs[0].armySize=1;
    g_actorInputs[1].armySize=g_actorInputs[2].armySize=2;
    g_actorInputs[1].type=3;g_actorInputs[1].quantity=40;g_actorInputs[1].rangedCapability=1;
    g_actorInputs[2].type=6;g_actorInputs[2].quantity=15;
    g_actorInputs[2].controlWord=0x0c7f;
    PrepareSuperadminStrategy();assert(g_strategyTrace[0]==1 && g_predictedDefensive);
    g_actorInputs[0].rangedCapability=1;
    PrepareSuperadminStrategy();assert(g_strategyTrace[0]==1 && !g_predictedDefensive);
    g_actorInputs[0].rangedCapability=0;
    enemyRanged=20;ownRanged=10;
    PrepareSuperadminStrategy();assert(!g_predictedDefensive); // strict share == threshold
    enemyRanged=40;ownRanged=20;g_actorInputs[2].quantity=16;
    PrepareSuperadminStrategy();assert(g_strategyTrace[0]==0 && !g_predictedDefensive);
    g_actorInputs[2].quantity=15;g_actorInputs[2].armySize=3;
    PrepareSuperadminStrategy();assert(g_strategyTrace[0]==0 && !g_predictedDefensive);
    g_actorInputs[2].armySize=2;g_actorInputGeneration=2;
    PrepareSuperadminStrategy();assert(g_strategyTrace[0]==0 && !g_predictedDefensive);
    g_actorInputGeneration=1;g_actorInputs[2].ignoreWhenNoRanged=1;
    assert(!FrozenArmyRangedCapability(g_actorInputs,3,2,false));
    assert(FrozenArmyRangedCapability(g_actorInputs,3,2,true));
    g_actorInputs[2].ignoreWhenNoRanged=0;
    g_actorInputs[2].rangedCapability=2; // Native list excludes this actor before capability testing.
    assert(FrozenArmyRangedCapability(g_actorInputs,3,2,false));
    g_actorInputs[2].rangedCapability=0;
    assert(!FrozenArmyRangedCapability(g_actorInputs,3,2,false));

    g_actorInputWorld=1;g_actorInputs[0].army=2;g_actorInputs[0].source=3;
    g_actorInputs[0].type=4;g_actorInputs[0].quantity=9;g_actorInputs[0].controlWord=0x0c7f;
    g_areaInputCount=2;
    auto& area=g_areaInputs[0];area.metadata[1]=1;area.metadata[2]=2;
    area.metadata[3]=1;area.metadata[4]=0x0c7f;
    area.physicalWords[0]=1;area.physicalWords[1]=3;area.physicalWords[2]=4;area.physicalWords[3]=9;
    auto& hero=g_areaInputs[1];hero.metadata[0]=7;hero.metadata[1]=1;hero.metadata[2]=2;
    hero.metadata[3]=1;hero.metadata[4]=0x0c7f;hero.metadata[6]=24;hero.physicalWords[0]=2;
    int numerator=0;assert(CalculateFrozenAreaNumerator(numerator) && numerator==24);
    auto& own=*reinterpret_cast<PlacementAggregate*>(g_actorCoreWords[0]);
    own.damage=40;own.attack=6;own.multiplier=1;
    auto& opponent=*reinterpret_cast<PlacementAggregate*>(g_actorCoreWords[1]);opponent.eligibleDefence=6;
    *reinterpret_cast<float*>(settings+0xbf8)=0.35f;
    PrepareSuperadminStrategy();assert(g_useSpreadRows && g_areaPolicyTrace[0]==1);
    assert(g_areaPolicyTrace[1]==24 && g_areaPolicyTrace[2]==40);
    own.damage=48;*reinterpret_cast<float*>(settings+0xbf8)=0.5f;
    PrepareSuperadminStrategy();assert(!g_useSpreadRows && g_areaPolicyTrace[0]==1);
    area.physicalWords[3]=10;PrepareSuperadminStrategy();assert(!g_useSpreadRows && g_areaPolicyTrace[0]==0);
    area.physicalWords[3]=9;g_areaInputs[2]=hero;g_areaInputs[2].metadata[6]=25;g_areaInputCount=3;
    assert(!CalculateFrozenAreaNumerator(numerator));
    g_areaInputCount=1;assert(!CalculateFrozenAreaNumerator(numerator));
    g_areaInputCount=2;area.metadata[5]=2;assert(!CalculateFrozenAreaNumerator(numerator));
    area.metadata[5]=0;g_areaInputOverflow=1;assert(!CalculateFrozenAreaNumerator(numerator));
    g_areaInputOverflow=0;g_areaInputCount=2;
    auto& actor=g_actorInputs[0];actor.world=1;actor.attackGeneration=1;
    actor.aggregateIdentity=7;actor.damage=300;actor.health=700;actor.initiative=10;
    actor.armySize=1;actor.category=1;actor.eligible=1;
    definition[0xdc/4]=1;area.physicalWords[4]=10;
    g_auxiliaryInputCount=1;g_auxiliaryInputs[0].aggregateIdentity=7;
    g_auxiliaryInputs[0].attackGeneration=1;g_auxiliaryInputs[0].inputCount=1;
    g_auxiliaryInputs[0].caller=0xbfc194;g_auxiliaryInputs[0].value=24;
    *reinterpret_cast<float*>(settings+0xbf4)=0.55f;
    PrepareSuperadminStrategy();assert(g_largePolicyTrace[0]==1 && g_knownHeroLarge);
    assert(g_largePolicyTrace[1]==24 && g_largePolicyTrace[2]==24);
    PlacementAggregate subset;assert(BuildFrozenOwnSubset(0,subset));
    assert(subset.damage==0 && subset.health==0 && subset.extra2==24);
    *reinterpret_cast<float*>(settings+0xbf4)=1.0f;
    PrepareSuperadminStrategy();assert(g_largePolicyTrace[0]==1 && !g_knownHeroLarge);
    area.metadata[5]=2;PrepareSuperadminStrategy();assert(g_largePolicyTrace[0]==0);
    area.metadata[5]=0;area.physicalWords[4]=0;actor.category=2;
    g_auxiliaryInputs[0].value=11;
    g_auxiliaryInputCount=2;g_auxiliaryInputs[1]=g_auxiliaryInputs[0];
    g_auxiliaryInputs[1].caller=0xbfbb90;g_auxiliaryInputs[1].value=9;
    // Captured round-toward-zero CW:11/20 stores exactly runtime0.549999952.
    *reinterpret_cast<uint32_t*>(settings+0xbf4)=0x3f0ccccc;
    PrepareSuperadminStrategy();assert(g_largePolicyTrace[0]==1 && !g_knownHeroLarge);
    assert(g_largePolicyTrace[1]==11 && g_largePolicyTrace[2]==20 && g_largePolicyTrace[3]==0x3f0ccccc);
    g_auxiliaryInputs[1].value=8;PrepareSuperadminStrategy();assert(g_knownHeroLarge);
    g_auxiliaryInputs[1].value=10;PrepareSuperadminStrategy();assert(!g_knownHeroLarge);
    return 0;
}
'''
        driver = driver.replace('0xbfc4a0','reinterpret_cast<uintptr_t>(&::Total)').replace(
            '0xbf9d30','reinterpret_cast<uintptr_t>(&::Ranged)').replace('0xbcb3f0','reinterpret_cast<uintptr_t>(&::Settings)').replace('0xbf9b80','reinterpret_cast<uintptr_t>(&::Evaluate)').replace('(kCreatureDefinition)', '(reinterpret_cast<uintptr_t>(&::Definition))')
        with tempfile.TemporaryDirectory(prefix='workshop-defence-') as directory:
            temporary=Path(directory)
            (temporary/'defence.cpp').write_text(driver,encoding='utf-8')
            (temporary/'build.cmd').write_text(f'@call "{vcvarsall()}" x86 >nul\n@if errorlevel 1 exit /b 1\n@cl /nologo /EHsc /O2 /std:c++20 /Fe:defence.exe defence.cpp\n',encoding='utf-8')
            build=subprocess.run(['cmd','/d','/c',str(temporary/'build.cmd')],cwd=temporary,capture_output=True)
            self.assertEqual(build.returncode,0,build.stdout.decode(errors='replace')+build.stderr.decode(errors='replace'))
            result=subprocess.run([str(temporary/'defence.exe')],capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr.decode(errors='replace'))

    def test_frozen_core_uses_latest_contiguous_batch_and_restores_control_word(self):
        source = preview_source()
        declarations = 'struct FrozenActorInput {' + source.split('struct FrozenActorInput {', 1)[1].split(
            'void* g_creatureDefinition', 1)[0]
        core = 'struct PlacementAggregate {' + source.split('struct PlacementAggregate {', 1)[1].split(
            'void CaptureKnownHeroModifiers(', 1)[0]
        builder = 'bool ReadFrozenRunicContribution(' + source.split('bool ReadFrozenRunicContribution(', 1)[1].split(
            'void PrepareSuperadminAggregates()', 1)[0]
        driver = '#include <windows.h>\n#include <cstdint>\n#include <cstring>\n#include <cassert>\n'
        driver += declarations + core + builder + r'''
int main() {
    FrozenActorInput rows[5]{};
    for(auto& row:rows) {
        row.world=1;row.army=2;row.attackGeneration=3;row.source=101;row.type=3;row.quantity=40;
        row.damage=120;row.attack=5;row.defence=4;row.health=280;row.initiative=9;row.atb=0.01f;
        row.speed=4;row.category=0;row.eligible=1;row.skipSpeed=1;row.retaliationBonus=1;
        row.controlWord=0x0c7f;row.aggregateIdentity=9;
    }
    rows[1].source=102;rows[1].type=6;rows[1].quantity=15;rows[1].damage=52;
    rows[1].attack=6;rows[1].defence=10;rows[1].health=390;rows[1].initiative=8;
    rows[1].category=2;rows[1].skipSpeed=0;
    rows[2].army=99;rows[2].unsupported=1;
    rows[3]=rows[0];rows[3].source=201;rows[3].aggregateIdentity=10;rows[3].damage=180;
    rows[4]=rows[1];rows[4].source=202;rows[4].aggregateIdentity=10;
    unsigned short original=0x037f;__asm { fldcw original }
    PlacementAggregate result{};uint32_t count=0;
    assert(BuildFrozenPlacementCore(rows,5,1,2,3,result,count));
    unsigned short restored;__asm { fnstcw restored }
    assert(restored==original && count==2 && result.damage==232 && result.health==670);
    PlacementAggregate expected;PlacementWeights weights;
    InitializePlacementAggregate(expected,weights);
    unsigned short captured=0x0c7f;__asm { fldcw captured }
    for(unsigned index=3;index<5;++index) {
        const auto& row=rows[index];
        BaselineActionFactorInput action{row.morale,row.luck,row.speed,row.initiative,row.atb,
            row.skipSpeed!=0,row.selected!=0,row.retaliationBonus!=0};
        AccumulatePlacementDamage(expected,weights,row.damage,row.attack,BaselineActionFactor(action),row.category);
        AccumulatePlacementHealth(expected,weights,row.health,row.defence,row.defence,row.eligible!=0);
    }
    NormalizePlacementAggregate(expected,weights);__asm { fldcw original }
    assert(memcmp(&result,&expected,sizeof(result))==0);
    PlacementAggregate retained=result;
    FrozenAuxiliaryPower extras[5]{{10,4,7,0xbfbb90,0x0c7f,3},
        {10,5,-2,0xbfbbc3,0x0c7f,3},{10,5,11,0xbfc194,0x0c7f,3},
        {9,5,100,0xbfbb90,0x0c7f,3},{10,5,100,0xbfbb90,0x0c7f,2}};
    FrozenHeroCorrection corrections[3]{{10,5,3,4,0x0c7f,3},
        {10,5,7,8,0x0c7f,3},{9,5,100,100,0x0c7f,3}};
    PlacementAggregate corrected=result;
    uint32_t applied=0;
    assert(ApplyCapturedPlacementCorrections(rows,5,3,5,3,extras,5,corrections,3,corrected,applied));
    assert(applied==3 && corrected.extra2==result.extra2+16);
    __asm { fldcw captured }
    const float expectedCorrection=ApplyHeroActionCorrection(result.multiplier,7,8);
    __asm { fldcw original }
    assert(corrected.multiplier==expectedCorrection);
    __asm { fnstcw restored }
    assert(restored==original);
    corrected=result;
    assert(ApplyCapturedPlacementCorrections(rows,5,3,5,3,extras,5,corrections,3,corrected,applied,1));
    assert(corrected.extra2==result.extra2+18 && applied==3);
    corrected=result;
    assert(ApplyCapturedPlacementCorrections(rows,5,3,5,3,extras,5,corrections,3,corrected,applied,2));
    assert(corrected.extra2==result.extra2+9 && applied==3);
    corrected=result;extras[0].inputCount=6;
    assert(!ApplyCapturedPlacementCorrections(rows,5,3,5,3,extras,5,corrections,3,corrected,applied));
    assert(memcmp(&corrected,&result,sizeof(result))==0 && applied==0);
    extras[0].inputCount=4;corrections[1].controlWord=0x10000;
    assert(!ApplyCapturedPlacementCorrections(rows,5,3,5,3,extras,5,corrections,3,corrected,applied));
    assert(memcmp(&corrected,&result,sizeof(result))==0);
    corrections[1].controlWord=0x0c7f;
    assert(!ApplyCapturedPlacementCorrections(rows,5,4,3,3,extras,5,corrections,3,corrected,applied));
    assert(!ApplyCapturedPlacementCorrections(rows,5,3,5,3,nullptr,1,corrections,3,corrected,applied));
    rows[4].source=rows[3].source;
    assert(!BuildFrozenPlacementCore(rows,5,1,2,3,result,count) && count==0);
    assert(memcmp(&result,&retained,sizeof(result))==0);
    rows[4].source=202;rows[4].unsupported=64;
    assert(!BuildFrozenPlacementCore(rows,5,1,2,3,result,count));
    rows[4].unsupported=0;
    rows[3].unsupported=rows[4].unsupported=32;
    FrozenAuxiliaryPower runes[4]{};
    for(unsigned index=0;index<2;++index) {
        const auto& row=rows[3+index];
        runes[index*2]={row.aggregateIdentity,4+index,1,0xbfb3dbu,row.controlWord,row.attackGeneration};
        runes[index*2+1]={row.aggregateIdentity,4+index,static_cast<int32_t>(index),0xbfb430u,row.controlWord,row.attackGeneration};
    }
    assert(!BuildFrozenPlacementCore(rows,5,1,2,3,result,count)); // legacy unsupported32 has no primitive proof
    assert(BuildFrozenPlacementCore(rows,5,1,2,3,result,count,nullptr,UINT_MAX,runes,4));
    PlacementAggregate subset{};uint32_t subsetCount=0;
    assert(BuildFrozenPlacementCore(rows+3,2,1,2,3,subset,subsetCount,nullptr,UINT_MAX,runes,4,3));
    assert(subsetCount==2 && memcmp(&subset,&result,sizeof(result))==0);
    runes[0].value=2;
    assert(!BuildFrozenPlacementCore(rows,5,1,2,3,result,count,nullptr,UINT_MAX,runes,4));
    runes[0].value=1;runes[1].controlWord^=1;
    assert(!BuildFrozenPlacementCore(rows,5,1,2,3,result,count,nullptr,UINT_MAX,runes,4));
    runes[1].controlWord^=1;runes[1].caller=0xbfb3dbu;
    assert(!BuildFrozenPlacementCore(rows,5,1,2,3,result,count,nullptr,UINT_MAX,runes,4));
    runes[1].caller=0xbfb430u;runes[1].attackGeneration=4;
    assert(!BuildFrozenPlacementCore(rows,5,1,2,3,result,count,nullptr,UINT_MAX,runes,4));
    rows[3].unsupported=rows[4].unsupported=0;
    assert(!BuildFrozenPlacementCore(rows,5,1,2,4,result,count));
    assert(!BuildFrozenPlacementCore(rows,0,1,2,3,result,count));
    __asm { fnstcw restored }
    assert(restored==original);
    return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix='workshop-frozen-core-') as directory:
            temporary = Path(directory)
            (temporary / 'core.cpp').write_text(driver, encoding='utf-8')
            (temporary / 'build.cmd').write_text(
                f'@call "{vcvarsall()}" x86 >nul\n@if errorlevel 1 exit /b 1\n'
                '@cl /nologo /EHsc /O2 /std:c++20 /Fe:core.exe core.cpp\n', encoding='utf-8')
            build = subprocess.run(['cmd', '/d', '/c', str(temporary / 'build.cmd')], cwd=temporary, capture_output=True)
            self.assertEqual(build.returncode, 0, build.stdout.decode(errors='replace') + build.stderr.decode(errors='replace'))
            result = subprocess.run([str(temporary / 'core.exe')], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))

    def test_owned_actor_capture_is_opt_in_bounded_frozen_and_reset_per_attack(self):
        source = preview_source()
        declarations = 'struct FrozenActorInput {' + source.split('struct FrozenActorInput {', 1)[1].split(
            'void* g_creatureDefinition', 1)[0]
        implementation = 'void ResetSuperadminInputCapture() {' + source.split(
            'void ResetSuperadminInputCapture() {', 1)[1].split('__declspec(naked) void ActorInputHook()', 1)[0]
        implementation += 'void __cdecl CaptureSuperadminAuxiliaryPower(' + source.split(
            'void __cdecl CaptureSuperadminAuxiliaryPower(', 1)[1].split('__declspec(naked) void AuxiliaryPowerHook()', 1)[0]
        export = 'unsigned long __stdcall WorkshopDeploymentPreviewSuperadminInputTrace(void* destination) {' + source.split(
            'WorkshopDeploymentPreviewSuperadminInputTrace(void* destination) {', 1)[1].split('BOOL WINAPI DllMain', 1)[0]
        driver = ('#include <windows.h>\n#include <cstdint>\n#include <cstring>\n#include <cassert>\n'
                  'bool g_superadminEnabled=false; volatile LONG g_attackGeneration=1; void* g_grid=nullptr;\n')
        strength = 'struct SourceStrengthInput {' + source.split('struct SourceStrengthInput {',1)[1].split(
            'struct PlacementAggregate {',1)[0]
        capture = 'void __cdecl CaptureSourceStrengthInput(' + source.split('void __cdecl CaptureSourceStrengthInput(',1)[1].split(
            '__declspec(naked) void SourceStrengthHook()',1)[0]
        seed = 'void __cdecl CaptureSourceSplitSeed(' + source.split('void __cdecl CaptureSourceSplitSeed(',1)[1].split('__declspec(naked) void SplitSeedHook()',1)[0]
        category='unsigned SelectPlacementDamageCategory(' + source.split('unsigned SelectPlacementDamageCategory(',1)[1].split('// category:',1)[0]
        area = 'struct AreaSpellInput {' + source.split('struct AreaSpellInput {', 1)[1].split('// Initial-state arithmetic', 1)[0]
        areaCapture = 'void __cdecl CaptureAreaSpellInput(' + source.split('void __cdecl CaptureAreaSpellInput(', 1)[1].split('void __cdecl CaptureSuperadminAuxiliaryPower(', 1)[0]
        mocks = r'''
uint32_t areaDescriptor[5]{0,1,0,0,0}, areaVector[3]{};
uint32_t __fastcall AreaWorld(const void*,void*) { return 11; }
uint32_t __fastcall AreaArmy(const void*,void*) { return 22; }
int areaKind=2;
uint32_t __fastcall AreaKind(const void*,void*) { return areaKind; }
uint32_t physicalDescriptor[9]{},physicalSource[1]{},physicalSourceMethods[1]{};
const uint32_t* __fastcall PhysicalSource(const void*,void*) { return physicalSource; }
const uint32_t* __fastcall PhysicalDescriptor(const void*,void*) { return physicalDescriptor; }
int __fastcall PhysicalQuantity(const void*,void*) { return 3; }
int __fastcall PhysicalAmmo(const void*,void*) { return 1; }
int __fastcall PhysicalShot(const void*,void*,int,int,int) { return 1; }
bool __fastcall PhysicalFlag(const void*,void*,uint32_t flag) { return flag==4 || flag==43; }
float __fastcall PhysicalMinimum(const void*,void*) { return 1; }
float __fastcall PhysicalMaximum(const void*,void*) { return 2; }
const void* __fastcall AreaCaster(const void*,void*) { return nullptr; }
int __fastcall AreaResources(const void*,void*) { return 1; }
const uint32_t* __fastcall AreaVector(const void*,void*) { return areaVector; }
bool __fastcall AreaUsable(const void*,void*,const void*) { return true; }
bool __fastcall AreaAllowed(uint32_t) { return true; }
bool __fastcall AreaDamaging(uint32_t,const void*,const void*) { return true; }
bool __fastcall AreaExcluded(const void*,const void*) { return false; }
int __fastcall AreaDamage(const void*,const void*,int) { return 97; }
bool __fastcall AreaLimited(const void*) { return false; }
int __fastcall AreaCost(const void*,const void*,int) { return 1; }
'''
        for address, name in (('0xa34670','AreaAllowed'),('0x982be0','AreaDamaging'),
                              ('0x9785e0','AreaExcluded'),('0x977c80','AreaDamage'),
                              ('0xa34470','AreaLimited'),('0x9781e0','AreaCost')):
            areaCapture = areaCapture.replace(address, 'reinterpret_cast<uintptr_t>(&::' + name + ')')
        driver += 'const uintptr_t kCreatureDefinition=0x89fbf0;\n' + strength + category + declarations + implementation + capture + seed + area + mocks + areaCapture + export
        driver += r'''
int main() {
    constexpr unsigned legacyWords=8+256*36+39+3+64*6+3+256*6+10+2+256*40+4+24;
    constexpr unsigned words=legacyWords+2+128*316+8;
    uint32_t buffer[words+2]{};buffer[0]=0x55aa55aa;buffer[words+1]=0xaa55aa55;
    uint32_t* output=buffer+1;
    ResetSuperadminInputCapture();
    CaptureSourceStrengthInput(nullptr,nullptr,17);
    assert(g_sourceStrengthCount==0);
    CaptureSuperadminActorInput(nullptr,11,17,0,0);
    assert(g_actorInputCount==0);
    assert(WorkshopDeploymentPreviewSuperadminInputTrace(output)==1 && output[1]==0 && output[3]==0);
    g_superadminEnabled=true;
    ResetSuperadminInputCapture();
    CaptureSuperadminActorInput(nullptr,11,17,0,0);
    assert(g_actorInputCount==1 && g_actorInputs[0].unsupported==1);
    assert(g_actorInputs[0].damage==17 && g_actorInputs[0].aggregateIdentity==11);
    CaptureSuperadminAuxiliaryPower(11,999,0x111111);
    assert(g_auxiliaryInputCount==0);
    CaptureSuperadminAuxiliaryPower(11,24,0xbfbb90);
    assert(g_auxiliaryInputCount==1 && g_auxiliaryInputs[0].value==24 && g_auxiliaryInputs[0].inputCount==1);
    g_grid=reinterpret_cast<void*>(0x11223344);
    FreezeSuperadminInputCapture();
    FrozenActorInput frozen=g_actorInputs[0];
    CaptureSuperadminActorInput(nullptr,22,34,0,0);
    CaptureSuperadminAuxiliaryPower(22,99,0xbfbb90);
    assert(g_auxiliaryInputCount==1);
    assert(g_actorInputCount==1 && memcmp(&frozen,g_actorInputs,sizeof(frozen))==0);
    assert(WorkshopDeploymentPreviewSuperadminInputTrace(output)==1);
    assert(output[0]==15 && output[1]==1 && output[2]==1 && output[3]==1);
    assert(output[5]==1 && output[6]==0x11223344 && output[7]==36);
    ++g_attackGeneration;
    ResetSuperadminInputCapture();
    assert(g_auxiliaryInputCount==0 && g_auxiliaryInputOverflow==0);
    assert(WorkshopDeploymentPreviewSuperadminInputTrace(output)==1 && output[2]==2 && output[3]==0);
    for(unsigned index=8;index<words;++index) assert(output[index]==0);
    for(unsigned index=0;index<kActorInputCapacity+1;++index) CaptureSuperadminActorInput(nullptr,11,index,0,0);
    assert(g_actorInputCount==kActorInputCapacity && g_actorInputOverflow==1);
    output[0]=0x12345678;output[words-1]=0x87654321;
    assert(WorkshopDeploymentPreviewSuperadminInputTrace(output)==0);
    assert(output[0]==0x12345678 && output[words-1]==0x87654321); // old caller buffer untouched
    constexpr unsigned auxiliaryCapacity=sizeof(g_auxiliaryInputs)/sizeof(g_auxiliaryInputs[0]);
    for(unsigned index=0;index<auxiliaryCapacity+1;++index) CaptureSuperadminAuxiliaryPower(11,index,0xbfbb90);
    assert(g_auxiliaryInputCount==auxiliaryCapacity && g_auxiliaryInputOverflow==1);
    assert(WorkshopDeploymentPreviewSuperadminInputTrace(output)==0);
    ResetSuperadminInputCapture();
    ++g_actorInputSequence;
    assert(WorkshopDeploymentPreviewSuperadminInputTrace(output)==2);
    ++g_actorInputSequence;
    g_superadminEnabled=false;
    assert(WorkshopDeploymentPreviewSuperadminInputTrace(output)==1 && output[1]==0 && output[3]==0);
    for(unsigned index=8;index<words;++index) assert(output[index]==0);
    assert(buffer[0]==0x55aa55aa && buffer[words+1]==0xaa55aa55);
    g_superadminEnabled=true;
    ResetSuperadminInputCapture();
    g_heroCorrectionCount=65;
    output[0]=0x12345678;output[words-1]=0x87654321;
    assert(WorkshopDeploymentPreviewSuperadminInputTrace(output)==0);
    assert(output[0]==0x12345678 && output[words-1]==0x87654321);
    assert(buffer[0]==0x55aa55aa && buffer[words+1]==0xaa55aa55);
    ResetSuperadminInputCapture();
    CaptureSourceStrengthInput(nullptr,nullptr,17);
    assert(g_sourceStrengthCount==1 && g_sourceStrengthInputs[0].metadata[6]==2);
    assert(g_sourceStrengthInputs[0].metadata[2]==17 && g_sourceStrengthInputs[0].metadata[5]==g_attackGeneration);
    CaptureSourceStrengthInput(nullptr,nullptr,17);
    assert(g_sourceStrengthCount==1);
    FreezeSuperadminInputCapture();
    CaptureSourceStrengthInput(nullptr,nullptr,18);
    assert(g_sourceStrengthCount==1);
    ResetSuperadminInputCapture();
    g_sourceStrengthBusy=true;
    CaptureSourceStrengthInput(nullptr,nullptr,17);
    assert(g_sourceStrengthCount==0);
    g_sourceStrengthBusy=false;
    for(unsigned index=0;index<257;++index) CaptureSourceStrengthInput(nullptr,nullptr,index);
    assert(g_sourceStrengthCount==256 && g_sourceStrengthOverflow==1);
    assert(WorkshopDeploymentPreviewSuperadminInputTrace(output)==1);
    assert(output[legacyWords-256*40-30]==256 && output[legacyWords-256*40-29]==1);
    assert(buffer[0]==0x55aa55aa && buffer[words+1]==0xaa55aa55);
    ++g_attackGeneration;
    CaptureSourceStrengthInput(nullptr,nullptr,17);
    assert(g_sourceStrengthCount==256);
    ResetSuperadminInputCapture();
    assert(g_sourceStrengthCount==0 && g_sourceStrengthOverflow==0);
    uint32_t random[3]{0xe51284,0,0x12345678};
    CaptureSourceSplitSeed(random);
    assert(g_sourceSplitSeed[0]==reinterpret_cast<uint32_t>(random) && g_sourceSplitSeed[1]==0x12345678);
    assert(g_sourceSplitSeed[2]==g_attackGeneration);
    FreezeSuperadminInputCapture();random[2]=55;CaptureSourceSplitSeed(random);
    assert(g_sourceSplitSeed[1]==0x12345678);
    ResetSuperadminInputCapture();random[0]=0;CaptureSourceSplitSeed(random);
    assert(g_sourceSplitSeed[0]==0);
    g_superadminEnabled=false;CaptureAreaSpellInput(nullptr,4,1);assert(g_areaInputCount==0);
    g_superadminEnabled=true;ResetSuperadminInputCapture();
    CaptureAreaSpellInput(nullptr,4,1);assert(g_areaInputCount==1 && g_areaInputs[0].metadata[5]==1);
    CaptureAreaSpellInput(nullptr,4,1);assert(g_areaInputCount==1);
    g_areaInputBusy=true;CaptureAreaSpellInput(nullptr,10,0);assert(g_areaInputCount==1);
    CaptureSuperadminAuxiliaryPower(11,24,0xbfbb90);assert(g_auxiliaryInputCount==0);
    g_areaInputBusy=false;FreezeSuperadminInputCapture();
    CaptureAreaSpellInput(nullptr,10,0);assert(g_areaInputCount==1);
    assert(WorkshopDeploymentPreviewSuperadminInputTrace(output)==1 && output[legacyWords]==1);
    assert(output[legacyWords+2+5]==1 && output[legacyWords+2+10]==4);
    ResetSuperadminInputCapture();assert(g_areaInputCount==0 && g_areaInputOverflow==0);
    g_areaInputCount=128;memset(g_areaInputs,0,sizeof(g_areaInputs));
    CaptureAreaSpellInput(nullptr,4,1);assert(g_areaInputCount==128 && g_areaInputOverflow==1);
    assert(WorkshopDeploymentPreviewSuperadminInputTrace(output)==1 && output[legacyWords+1]==1);
    assert(buffer[0]==0x55aa55aa && buffer[words+1]==0xaa55aa55);
    ResetSuperadminInputCapture();
    uintptr_t areaMethods[0x28c/4+1]{};
    areaMethods[0]=reinterpret_cast<uintptr_t>(&AreaKind);
    areaMethods[8/4]=reinterpret_cast<uintptr_t>(&AreaWorld);
    areaMethods[0xc/4]=reinterpret_cast<uintptr_t>(&AreaArmy);
    areaMethods[0x78/4]=reinterpret_cast<uintptr_t>(&AreaCaster);
    areaMethods[0x234/4]=reinterpret_cast<uintptr_t>(&AreaResources);
    areaMethods[0x248/4]=reinterpret_cast<uintptr_t>(&AreaVector);
    areaMethods[0x220/4]=reinterpret_cast<uintptr_t>(&AreaUsable);
    uint32_t areaActor[1]{reinterpret_cast<uint32_t>(areaMethods)};
    areaVector[0]=reinterpret_cast<uint32_t>(areaDescriptor);areaVector[1]=areaVector[0]+20;
    CaptureAreaSpellInput(areaActor,10,0);
    assert(g_areaInputCount==1 && g_areaInputs[0].metadata[5]==0);
    assert(g_areaInputs[0].metadata[1]==11 && g_areaInputs[0].metadata[2]==22);
    assert(g_areaInputs[0].metadata[8]==1 && g_areaInputs[0].metadata[12]==24 && g_areaInputs[0].metadata[13]==9);
    assert(g_areaInputs[0].spellWords[5]==97 && g_areaInputs[0].spellWords[8]==1);
    CaptureAreaSpellInput(areaActor,10,0);assert(g_areaInputCount==1);
    areaVector[1]=areaVector[0]+33*20;CaptureAreaSpellInput(areaActor,10,0);
    assert(g_areaInputCount==2 && (g_areaInputs[1].metadata[5]&8));
    areaVector[1]=areaVector[0]+1;CaptureAreaSpellInput(areaActor,10,0);
    assert(g_areaInputCount==3 && (g_areaInputs[2].metadata[5]&4));
    CaptureAreaSpellInput(reinterpret_cast<const uint32_t*>(1),10,0);
    assert(g_areaInputCount==4 && (g_areaInputs[3].metadata[5]&2));
    ResetSuperadminInputCapture();areaKind=1;areaVector[1]=areaVector[0]+20;
    physicalDescriptor[0x1c/4]=1;physicalDescriptor[0x20/4]=3;
    physicalSourceMethods[0]=reinterpret_cast<uint32_t>(&PhysicalDescriptor);
    physicalSource[0]=reinterpret_cast<uint32_t>(physicalSourceMethods);
    areaMethods[0x6c/4]=reinterpret_cast<uintptr_t>(&PhysicalSource);
    areaMethods[0x1d8/4]=reinterpret_cast<uintptr_t>(&PhysicalQuantity);
    areaMethods[0x1a0/4]=reinterpret_cast<uintptr_t>(&PhysicalAmmo);
    areaMethods[0xb8/4]=reinterpret_cast<uintptr_t>(&PhysicalShot);
    areaMethods[0x28c/4]=reinterpret_cast<uintptr_t>(&PhysicalFlag);
    areaMethods[0x1ec/4]=reinterpret_cast<uintptr_t>(&PhysicalMinimum);
    areaMethods[0x1f0/4]=reinterpret_cast<uintptr_t>(&PhysicalMaximum);
    CaptureAreaSpellInput(areaActor,10,0);
    assert(g_areaInputCount==1 && g_areaInputs[0].metadata[5]==0);
    const auto* physical=g_areaInputs[0].physicalWords;
    assert(physical[0]==1 && physical[1]==reinterpret_cast<uint32_t>(physicalDescriptor));
    assert(physical[2]==1 && physical[3]==3 && physical[4]==1 && physical[5]==1);
    assert(physical[7]==1 && physical[8]==1 && physical[9]==6);
    assert(*reinterpret_cast<const float*>(physical+6)==3 && *reinterpret_cast<const float*>(physical+10)==1);
    return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix='workshop-actor-capture-') as directory:
            temporary = Path(directory)
            (temporary / 'capture.cpp').write_text(driver, encoding='utf-8')
            (temporary / 'build.cmd').write_text(
                f'@call "{vcvarsall()}" x86 >nul\n@if errorlevel 1 exit /b 1\n'
                '@cl /nologo /EHsc /O2 /std:c++20 /Fe:capture.exe capture.cpp user32.lib\n', encoding='utf-8')
            build = subprocess.run(['cmd', '/d', '/c', str(temporary / 'build.cmd')], cwd=temporary, capture_output=True)
            self.assertEqual(build.returncode, 0, build.stdout.decode(errors='replace') + build.stderr.decode(errors='replace'))
            result = subprocess.run([str(temporary / 'capture.exe')], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))

    def test_attack_reset_preserves_portrait_input_registers_and_fpu(self):
        from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
        from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EDX, UC_X86_REG_FPCW
        source = preview_source()
        assembly = source.split('__declspec(naked) void AttackHook()', 1)[1].split('__asm {', 1)[1].split(
            'push dword ptr [esp + 12]', 1)[0]
        for symbol, replacement in (('g_fpu', '0x304000'), ('g_attackGeneration', '0x302000'),
                                     ('g_cell', '0x303000'), ('CapturePublicPortraits', '0x300900'),
                                     ('ResetSuperadminInputCapture', '0x300800')):
            assembly = assembly.replace(symbol, replacement)
        assembler = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32)
        code = bytes(assembler.asm(assembly + '\njmp 0x30f000', 0x300000)[0])
        cpu = Uc(UC_ARCH_X86, UC_MODE_32)
        cpu.mem_map(0x200000, 65536)
        cpu.mem_map(0x300000, 65536)
        cpu.mem_write(0x300000, code)
        cpu.mem_write(0x300800, bytes(assembler.asm(
            'mov eax, 123; mov ecx, 456; mov edx, 789; fninit; ret', 0x300800)[0]))
        cpu.mem_write(0x300900, bytes(assembler.asm(
            'mov dword ptr [0x301100], eax; mov dword ptr [0x301104], ecx; '
            'mov dword ptr [0x301108], edx; fnstcw word ptr [0x30110c]; ret', 0x300900)[0]))
        for register, value in ((UC_X86_REG_ESP, 0x208000), (UC_X86_REG_EAX, 0x11001100),
                                (UC_X86_REG_ECX, 0x22002200), (UC_X86_REG_EDX, 0x33003300),
                                (UC_X86_REG_FPCW, 0x0c7f)):
            cpu.reg_write(register, value)
        cpu.emu_start(0x300000, 0x30f000, count=1000)
        self.assertEqual(struct.unpack('<3I', cpu.mem_read(0x301100, 12)),
                         (0x11001100, 0x22002200, 0x33003300))
        self.assertEqual(struct.unpack('<H', cpu.mem_read(0x30110c, 2))[0], 0x0c7f)
        self.assertEqual(cpu.reg_read(UC_X86_REG_ESP), 0x208000)
        self.assertEqual(struct.unpack('<I', cpu.mem_read(0x302000, 4))[0], 1)

    def test_actor_input_bridge_preserves_fpu_registers_and_replays_original(self):
        from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
        from unicorn.x86_const import (UC_X86_REG_ESP, UC_X86_REG_ESI, UC_X86_REG_EDI,
                                      UC_X86_REG_EBX, UC_X86_REG_EBP, UC_X86_REG_EFLAGS,
                                      UC_X86_REG_FPCW, UC_X86_REG_MXCSR, UC_X86_REG_XMM0)
        source = preview_source()
        assembly = source.split('__declspec(naked) void ActorInputHook()', 1)[1].split(
            '__asm {', 1)[1].split('}', 1)[0]
        assembly = assembly.replace('CaptureSuperadminActorInput', '0x300800').replace(
            'kActorInputResume', '0xbfbb0f')
        assembler = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32)
        cpu = Uc(UC_ARCH_X86, UC_MODE_32)
        cpu.mem_map(0x200000, 65536)
        cpu.mem_map(0x300000, 65536)
        code = bytes(assembler.asm(assembly, 0x300200)[0])
        cpu.mem_write(0x300200, code)
        cpu.mem_write(0x304000, struct.pack('<f', 1.25))
        cpu.mem_write(0x304004, struct.pack('<I', 0x1f80))
        cpu.mem_write(0x300000, bytes(assembler.asm('fld dword ptr [0x304000]; jmp 0x300200', 0x300000)[0]))
        callback = ('mov eax, dword ptr [esp + 4]; mov dword ptr [0x301100], eax; '
                    'mov eax, dword ptr [esp + 8]; mov dword ptr [0x301104], eax; '
                    'mov eax, dword ptr [esp + 12]; mov dword ptr [0x301108], eax; '
                    'mov eax, dword ptr [esp + 16]; mov dword ptr [0x30110c], eax; '
                    'mov eax, dword ptr [esp + 20]; mov dword ptr [0x301110], eax; '
                    'fninit; fld dword ptr [0x304000]; ldmxcsr dword ptr [0x304004]; '
                    'pxor xmm0, xmm0; mov eax, 123; mov ecx, 456; mov edx, 789; ret')
        cpu.mem_write(0x300800, bytes(assembler.asm(callback, 0x300800)[0]))
        cpu.mem_write(0x208024, struct.pack('<f', 3.25))
        cpu.mem_write(0x208028, struct.pack('<I', 0x212121))
        cpu.mem_write(0x208030, struct.pack('<I', 0))
        cpu.mem_write(0x203004, struct.pack('<f', 2.5))
        for register, value in ((UC_X86_REG_ESP, 0x208000), (UC_X86_REG_EBX, 0x203000),
                                (UC_X86_REG_ESI, 0x204000), (UC_X86_REG_EDI, 0x205000),
                                (UC_X86_REG_EBP, 120), (UC_X86_REG_EFLAGS, 0x246),
                                (UC_X86_REG_FPCW, 0x0c7f), (UC_X86_REG_MXCSR, 0x3f80),
                                (UC_X86_REG_XMM0, 0x112233445566778899aabbccddeeff00)):
            cpu.reg_write(register, value)
        cpu.emu_start(0x300000, 0xbfbb0f, count=2000)
        self.assertEqual(struct.unpack('<5I', cpu.mem_read(0x301100, 20)),
                         (0x204000, 0x205000, 120, 0x212121, 0))
        for register, value in ((UC_X86_REG_ESP, 0x208000), (UC_X86_REG_EBX, 0x203000),
                                (UC_X86_REG_ESI, 0x204000), (UC_X86_REG_EDI, 0x205000),
                                (UC_X86_REG_EBP, 120), (UC_X86_REG_EFLAGS, 0x246),
                                (UC_X86_REG_FPCW, 0x0c7f), (UC_X86_REG_MXCSR, 0x3f80),
                                (UC_X86_REG_XMM0, 0x112233445566778899aabbccddeeff00)):
            self.assertEqual(cpu.reg_read(register), value)
        stores = bytes(assembler.asm('fstp dword ptr [0x301200]; fstp dword ptr [0x301204]', 0x300c00)[0])
        cpu.mem_write(0x300c00, stores)
        cpu.emu_start(0x300c00, 0x300c00 + len(stores), count=100)
        self.assertEqual(struct.unpack('<2f', cpu.mem_read(0x301200, 8)), (5.75, 1.25))

        assembly = source.split('__declspec(naked) void SourceStrengthHook()',1)[1].split(
            '__asm {',1)[1].split('}',1)[0]
        assembly=assembly.replace('CaptureSourceStrengthInput','0x300800').replace(
            'kSourceStrengthResume','0x4e9c54')
        cpu=Uc(UC_ARCH_X86,UC_MODE_32)
        cpu.mem_map(0x200000,65536);cpu.mem_map(0x300000,65536)
        cpu.mem_write(0x300200,bytes(assembler.asm(assembly,0x300200)[0]))
        cpu.mem_write(0x300800,bytes(assembler.asm(callback,0x300800)[0]))
        cpu.mem_write(0x304000,struct.pack('<f',1.25))
        cpu.mem_write(0x304004,struct.pack('<I',0x1f80))
        cpu.mem_write(0x300000,bytes(assembler.asm('fld dword ptr [0x304000]; jmp 0x300200',0x300000)[0]))
        cpu.mem_write(0x20800c,struct.pack('<I',0x212121))
        cpu.mem_write(0x206008,struct.pack('<I',17))
        for register,value in ((UC_X86_REG_ESP,0x208000),(UC_X86_REG_EBX,0x203000),
                               (UC_X86_REG_ESI,0x204000),(UC_X86_REG_EDI,0x205000),
                               (UC_X86_REG_EBP,0x206000),(UC_X86_REG_EFLAGS,0x246),
                               (UC_X86_REG_FPCW,0xc7f),(UC_X86_REG_MXCSR,0x3f80),
                               (UC_X86_REG_XMM0,0x112233445566778899aabbccddeeff00)):
            cpu.reg_write(register,value)
        cpu.emu_start(0x300000,0x4e9c54,count=2000)
        self.assertEqual(struct.unpack('<3I',cpu.mem_read(0x301100,12)),(0x204000,0x212121,17))
        for register,value in ((UC_X86_REG_ESP,0x208000),(UC_X86_REG_EBX,0x203000),
                               (UC_X86_REG_ESI,0x204000),(UC_X86_REG_EDI,17),
                               (UC_X86_REG_EDX,0x212121),(UC_X86_REG_EBP,0x206000),
                               (UC_X86_REG_EFLAGS,0x246),(UC_X86_REG_FPCW,0xc7f),
                               (UC_X86_REG_MXCSR,0x3f80),
                               (UC_X86_REG_XMM0,0x112233445566778899aabbccddeeff00)):
            self.assertEqual(cpu.reg_read(register),value)
        store=bytes(assembler.asm('fstp dword ptr [0x301200]',0x300c00)[0])
        cpu.mem_write(0x300c00,store);cpu.emu_start(0x300c00,0x300c00+len(store),count=100)
        self.assertEqual(struct.unpack('<f',cpu.mem_read(0x301200,4))[0],1.25)
        assembly=source.split('__declspec(naked) void SplitSeedHook()',1)[1].split('__asm {',1)[1].split('}',1)[0]
        assembly=assembly.replace('CaptureSourceSplitSeed','0x300800').replace('kSplitSeedResume','0x855457')
        cpu=Uc(UC_ARCH_X86,UC_MODE_32);cpu.mem_map(0x200000,65536);cpu.mem_map(0x300000,65536)
        cpu.mem_write(0x300200,bytes(assembler.asm(assembly,0x300200)[0]))
        cpu.mem_write(0x300800,bytes(assembler.asm(callback,0x300800)[0]))
        cpu.mem_write(0x304000,struct.pack('<f',1.25));cpu.mem_write(0x304004,struct.pack('<I',0x1f80))
        cpu.mem_write(0x205000,struct.pack('<I',0xe51284))
        cpu.mem_write(0x300000,bytes(assembler.asm('fld dword ptr [0x304000]; jmp 0x300200',0x300000)[0]))
        for register,value in ((UC_X86_REG_ESP,0x208000),(UC_X86_REG_EAX,0x205000),(UC_X86_REG_EBX,0x203000),
                               (UC_X86_REG_ESI,0x204000),(UC_X86_REG_EBP,0x206000),(UC_X86_REG_EFLAGS,0x246),
                               (UC_X86_REG_FPCW,0xc7f),(UC_X86_REG_MXCSR,0x3f80),
                               (UC_X86_REG_XMM0,0x112233445566778899aabbccddeeff00)):
            cpu.reg_write(register,value)
        cpu.emu_start(0x300000,0x855457,count=2000)
        self.assertEqual(struct.unpack('<I',cpu.mem_read(0x301100,4))[0],0x205000)
        self.assertEqual(struct.unpack('<2I',cpu.mem_read(0x207ff8,8)),(1,100))
        for register,value in ((UC_X86_REG_ESP,0x207ff8),(UC_X86_REG_EAX,0x205000),(UC_X86_REG_EBX,0x203000),
                               (UC_X86_REG_EDX,0xe51284),(UC_X86_REG_ESI,0x204000),(UC_X86_REG_EBP,0x206000),
                               (UC_X86_REG_EFLAGS,0x246),(UC_X86_REG_FPCW,0xc7f),(UC_X86_REG_MXCSR,0x3f80),
                               (UC_X86_REG_XMM0,0x112233445566778899aabbccddeeff00)):
            self.assertEqual(cpu.reg_read(register),value)
        cpu.mem_write(0x300c00,store);cpu.emu_start(0x300c00,0x300c00+len(store),count=100)
        self.assertEqual(struct.unpack('<f',cpu.mem_read(0x301200,4))[0],1.25)

    def test_action_factor_observer_preserves_x87_inputs_and_bounds(self):
        from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
        from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_ESI, UC_X86_REG_EBP, UC_X86_REG_EFLAGS, UC_X86_REG_FPCW, UC_X86_REG_MXCSR
        source = (MOD_ROOT / 'scripts/accuracy-campaign.py').read_text()
        assembly = source.split('def install_action_factor_observer(', 1)[1].split(
            "        assembly = f'''", 1)[1].split("'''", 1)[0]
        assembly = re.sub(r'\{records(?: \+ (\d+))?\}',
                          lambda match: str(0x305000 + int(match.group(1) or 0)), assembly)
        assembler = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32)
        code = bytes(assembler.asm(assembly, 0x300010)[0])
        setup = bytes(assembler.asm('fld dword ptr [0x300800]; jmp 0x300010', 0x300000)[0])
        arithmetic = bytes(assembler.asm(
            'fmul st(1); fstp dword ptr [0x300900]; fstp dword ptr [0x300904]', 0x300400)[0])
        for armed, count, table in ((0, 0, 0xe4fba4), (1, 0, 0xe4fba4),
                                     (1, 255, 0xe4fba4), (1, 256, 0xe4fba4), (1, 0, 0x111111)):
            with self.subTest(inputs=(armed, count, table)):
                cpu = Uc(UC_ARCH_X86, UC_MODE_32)
                cpu.mem_map(0x200000, 65536)
                cpu.mem_map(0x300000, 65536)
                cpu.mem_write(0x300000, setup)
                cpu.mem_write(0x300010, code)
                cpu.mem_write(0x300400, arithmetic)
                cpu.mem_write(0x300800, struct.pack('<f', 1.25))
                cpu.mem_write(0x304ff0, b'\xa5' * (16 + 40976 + 16))
                cpu.mem_write(0x305000, struct.pack('<4I', armed, count, 0, 0))
                cpu.mem_write(0x305010, bytes(40960))
                cpu.mem_map(0xe4f000, 4096)
                cpu.mem_map(0xbfb000, 4096)
                cpu.mem_write(0xbfb3d0, bytes(assembler.asm('fld dword ptr [0x300810]; ret', 0xbfb3d0)[0]))
                cpu.mem_map(0x4ba000, 4096)
                cpu.mem_write(0x4bab70, bytes(assembler.asm('mov eax, 1; ret', 0x4bab70)[0]))
                cpu.mem_write(0x4bab80, bytes(assembler.asm('xor eax, eax; ret', 0x4bab80)[0]))
                cpu.mem_write(0x206000, struct.pack('<I', 0x206100))
                cpu.mem_write(0x206004, struct.pack('<I', 0x206300))
                cpu.mem_write(0x206308, struct.pack('<I', 0x20))
                cpu.mem_write(0x206024, struct.pack('<I', 0x206400))
                cpu.mem_write(0x206458, struct.pack('<I', 0x300ba0))
                cpu.mem_write(0x300ba0, bytes(assembler.asm('xor eax, eax; ret', 0x300ba0)[0]))
                cpu.mem_write(0x20621c, struct.pack('<2I', 3, 40))
                cpu.mem_write(0x207000, struct.pack('<I', 0xe79d3c))
                cpu.mem_write(0x20708c, struct.pack('<2I', 0x207100, 0x207200))
                for army, begin, army_count in ((0x207100, 0x207400, 1), (0x207200, 0x207500, 2)):
                    cpu.mem_write(army, struct.pack('<I', 0xe17bcc))
                    cpu.mem_write(army + 0x28, struct.pack('<2I', begin, begin + army_count * 4))
                for offset, address, stub in ((0, 0x300b00, 'mov eax, 0x206200; ret'),
                                              (0x2c, 0x300b20, 'mov eax, 1; ret'),
                                              (0x34, 0x300b40, 'xor eax, eax; ret')):
                    cpu.mem_write(0x206100 + offset, struct.pack('<I', address))
                    cpu.mem_write(address, bytes(assembler.asm(stub, address)[0]))
                for offset, address, stub in (
                        (0x1ac, 0x300a00, 'mov eax, 1; ret'),
                        (0x1b0, 0x300a20, 'xor eax, eax; ret'),
                        (0x1bc, 0x300a40, 'fld dword ptr [0x300810]; ret'),
                        (0x48, 0x300a60, 'mov eax, 5; ret'),
                        (0x28c, 0x300a80, 'mov eax, 1; ret 4'),
                        (0x1e0, 0x300aa0, 'mov eax, 1; ret'),
                        (0x238, 0x300ac0, 'xor eax, eax; ret'),
                        (0x234, 0x300ae0, 'xor eax, eax; ret'),
                        (0x6c, 0x300b60, 'mov eax, 0x206000; ret'),
                        (0x1e4, 0x300b80, 'mov eax, 1; ret'),
                        (0, 0x300bc0, 'mov eax, 1; ret'),
                        (8, 0x300be0, 'mov eax, 0x207000; ret'),
                        (0xc, 0x300c00, 'mov eax, 0x207100; ret'),
                        (0x198, 0x300c20, 'mov eax, 5; ret'),
                        (0x19c, 0x300c40, 'mov eax, 3; ret'),
                        (0x20, 0x300c60, 'mov eax, 40; ret'),
                        (0x1dc, 0x300c80, 'mov eax, 280; ret 4'),
                        (0x190, 0x300ca0, 'xor eax, eax; ret'),
                        (0x7c, 0x300cc0, 'xor eax, eax; ret')):
                    cpu.mem_write(0xe4fba4 + offset, struct.pack('<I', address))
                    cpu.mem_write(address, bytes(assembler.asm(stub, address)[0]))
                cpu.mem_write(0x300810, struct.pack('<f', 9.0))
                cpu.mem_write(0x204000, struct.pack('<I', table))
                cpu.mem_write(0x203ffc, struct.pack('<I', 0))
                cpu.mem_write(0x203efc, struct.pack('<I', 0x204100))
                cpu.mem_write(0x20411c, struct.pack('<f', 0.125))
                cpu.mem_write(0x208020, struct.pack('<I', 120))
                cpu.mem_write(0x208028, struct.pack('<I', 0xdeadbeef))
                cpu.reg_write(UC_X86_REG_ESP, 0x208000)
                cpu.reg_write(UC_X86_REG_ESI, 0x204000)
                cpu.reg_write(UC_X86_REG_EBP, 120)
                cpu.reg_write(UC_X86_REG_EFLAGS, 0x246)
                cpu.reg_write(UC_X86_REG_FPCW, 0x0f7f)
                cpu.reg_write(UC_X86_REG_MXCSR, 0x1f80)
                cpu.emu_start(0x300000, 0xbfbb00, count=1000)
                accepted = armed and count < 256
                self.assertEqual(struct.unpack('<2I', cpu.mem_read(0x305004, 8)),
                                 (count + int(accepted), int(armed and count >= 256)))
                if accepted:
                    record = struct.unpack('<3I2f3I2ifiIf2I8i16I', cpu.mem_read(0x305010 + count * 160, 160))
                    self.assertEqual(record[:4], (0x204000, 0xdeadbeef, 120, 1.25))
                    self.assertEqual(record[4:7], (0.125 if table == 0xe4fba4 else 0,
                                                  table, 0x204100 if table == 0xe4fba4 else 0))
                    self.assertEqual(record[8:12], (1, 0, 9.0, 5) if table == 0xe4fba4 else (0, 0, 0, 0))
                    self.assertEqual(record[16:22], (0, 0, 1, 1, 0, 0) if table == 0xe4fba4 else (0,) * 6)
                    self.assertEqual(record[22:24], (1, 1) if table == 0xe4fba4 else (0, 0))
                    if table == 0xe4fba4:
                        self.assertEqual(record[7], 0x207000)
                        self.assertEqual(record[24:37], (0xe79d3c, 0x207100, 3, 40, 5, 3, 280, 1, 1, 1, 2, 0, 0))
                    self.assertEqual(record[38:40], (0x0f7f, 0x1f80))
                else:
                    self.assertEqual(bytes(cpu.mem_read(0x305010, 40960)), bytes(40960))
                self.assertEqual(bytes(cpu.mem_read(0x304ff0, 16)), b'\xa5' * 16)
                self.assertEqual(bytes(cpu.mem_read(0x30f010, 16)), b'\xa5' * 16)
                self.assertEqual(cpu.reg_read(UC_X86_REG_ESP), 0x208000)
                self.assertEqual(cpu.reg_read(UC_X86_REG_ESI), 0x204000)
                self.assertEqual(cpu.reg_read(UC_X86_REG_EBP), 120)
                self.assertEqual(cpu.reg_read(UC_X86_REG_EFLAGS), 0x246)
                cpu.emu_start(0x300400, 0x300400 + len(arithmetic), count=1000)
                self.assertEqual(struct.unpack('<2f', cpu.mem_read(0x300900, 8)), (150.0, 1.25))

    def test_native_initial_action_factor_includes_initiative_speed_and_atb(self):
        import pefile
        from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
        from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_FPCW
        game = WORKSPACE / '.local/test-game/bin/H5_Game.exe'
        if not game.is_file():
            self.skipTest('Pinned game EXE is needed for the native action-factor oracle')
        self.assertEqual(hashlib.sha256(game.read_bytes()).hexdigest(), probe.HASHES['H5_Game.exe'])
        executable = pefile.PE(str(game))
        image_base = executable.OPTIONAL_HEADER.ImageBase
        image = executable.get_memory_mapped_image()
        # Execute original arithmetic. Only actor getters and two unrelated
        # status/ability evaluators are replaced with explicit baseline inputs.
        compiled_cases = []
        inputs = (
                (1, 3, 0, 0, 0, False, False, False, False),
                (10, 5, 0, 0, 0.5, False, False, False, False),
                (40, 8, 2, -1, 1, False, False, False, False),
                (10, 4, 0, 0, 1.5, False, False, False, False),
                (10, 4, 0, 0, -0.5, False, False, False, False),
                (10, 4, 0, 0, 0, True, False, False, False),
                (8.999999046325684, 4, 0, 0, 0.0679397, False, True, True, False),
                (7.999999046325684, 4, 0, 0, 0.03743747, False, False, True, False),
                (10.999999046325684, 6, 0, 1, 0.08015966, False, False, True, False),
                (8, 4, 0, 0, 0.5, False, False, True, True),
                (8.999999046325684, 5, 0, 0, 0.037011224776506424, False, False, True, False))
        resources = (((0,0,0),(0,0,0)), ((10,0,0),(10,0,0)), ((0,1,1),(0,1,1)),
                     ((4,8,20),(0,2,5)), ((0,0,20),(99,99,0)))
        for control_word, (initiative, speed, morale, luck, atb, selected, skip_speed, retaliation, blocked), maximum, current, half_speed, runic_numerator, runic_denominator in (
                (control, inputs_case, maximum, current, half_speed, numerator, denominator) for control in (0x037f, 0x0c7f)
                for inputs_case in inputs for maximum, current in resources for half_speed in (False, True)
                for numerator, denominator in ((0,0),(1,3),(3,3),(4,6))):
            with self.subTest(control_word=control_word, inputs=(initiative, speed, morale, luck, atb, selected)):
                machine = Uc(UC_ARCH_X86, UC_MODE_32)
                machine.mem_map(image_base, (executable.OPTIONAL_HEADER.SizeOfImage + 4095) & ~4095)
                machine.mem_write(image_base, image)
                machine.mem_map(0x2000000, 0x20000)
                actor, table, timer = 0x2001000, 0x2002000, 0x2003000
                stop, output, stack = 0x2004000, 0x2005000, 0x2018000
                machine.mem_write(actor, struct.pack('<I', table))
                machine.mem_write(timer + 0x1c, struct.pack('<f', atb))
                for offset, value, floating, cleanup in (
                        (0x1ac, morale, False, 0), (0x1b0, luck, False, 0),
                        (0x1bc, initiative, True, 0), (0x48, speed, False, 0),
                        (0x184, timer, False, 0), (0x28, 0, False, 4),
                        (0x28c, 0, False, 4), (0x1e0, int(skip_speed or half_speed), False, 0),
                        (0x238, maximum[0], False, 0), (0x234, current[0], False, 0),
                        (0x6c, 0x2015000 if maximum[1] or maximum[2] else 0, False, 0), (0x1e4, int(retaliation), False, 0)):
                    address = 0x2006000 + offset * 16
                    machine.mem_write(table + offset, struct.pack('<I', address))
                    if floating:
                        machine.mem_write(address + 32, struct.pack('<f', value))
                        code = b'\xd9\x05' + struct.pack('<I', address + 32)
                    else:
                        code = b'\xb8' + struct.pack('<I', value & 0xffffffff)
                    machine.mem_write(address, code + (b'\xc2\x04\x00' if cleanup else b'\xc3'))
                assembler = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32)
                machine.mem_write(0x2015000,struct.pack('<I',0x2015100))
                for offset, address, assembly in ((0,0x2016000,'mov eax,0x2015200; ret'),
                                                (0x2c,0x2016040,f'mov eax,{current[1]}; ret'),
                                                (0x34,0x2016080,f'mov eax,{current[2]}; ret')):
                    machine.mem_write(0x2015100+offset,struct.pack('<I',address))
                    machine.mem_write(address,bytes(assembler.asm(assembly,address)[0]))
                for address,value in ((0x4bab70,maximum[1]),(0x4bab80,maximum[2])):
                    machine.mem_write(address,bytes(assembler.asm(f'mov eax,{value}; ret',address)[0]))
                flags = (f'cmp dword ptr [esp + 4], 1; jne other_flag; mov eax, {int(skip_speed)}; ret 4; '
                         f'other_flag: cmp dword ptr [esp + 4], 0x22; jne no_flag; mov eax, {int(blocked)}; ret 4; '
                         f'no_flag: cmp dword ptr [esp+4],4; jne absent; mov eax,{int(half_speed)}; ret 4; '
                         'absent: xor eax, eax; ret 4')
                machine.mem_write(0x2006000 + 0x28c * 16, bytes(keystone.Ks(
                    keystone.KS_ARCH_X86, keystone.KS_MODE_32).asm(flags, 0x2006000 + 0x28c * 16)[0]))
                machine.mem_write(0x4e4920, b'\xd9\xee\xc3')
                if runic_denominator:
                    machine.mem_write(0x2017000,struct.pack('<2i',runic_numerator,runic_denominator))
                    rune_code='fild dword ptr [0x2017000]; fidiv dword ptr [0x2017004]; fstp dword ptr [0x2017010]; fld dword ptr [0x2017010]; ret'
                    machine.mem_write(0xbfb3d0,bytes(assembler.asm(rune_code,0xbfb3d0)[0]))
                else:
                    machine.mem_write(0xbfb3d0, b'\xd9\xee\xc3')
                machine.mem_write(stop, b'\xd9\x1d' + struct.pack('<I', output))
                machine.mem_write(stack, struct.pack('<3I', stop, actor, actor if selected else 0))
                machine.reg_write(UC_X86_REG_ESP, stack)
                machine.reg_write(UC_X86_REG_ESI, 0x1234)
                machine.reg_write(UC_X86_REG_EDI, 0x5678)
                machine.reg_write(UC_X86_REG_FPCW, control_word)
                machine.emu_start(0xbfb4b0, stop + 6, count=10000)
                actual = struct.unpack('<f', machine.mem_read(output, 4))[0]
                expected = ((1 + morale * 0.1) * (1 + luck * 0.1)
                            * min(30, max(2, initiative)) * 0.1)
                if half_speed:
                    expected *= 0.5
                if not skip_speed:
                    expected *= 1 + (speed - 5) * 0.05
                if not selected:
                    expected *= 0.95 + min(1, max(0, atb)) * 0.1
                for resource_maximum, resource_current in zip(maximum,current):
                    if resource_maximum>0: expected *= 1+0.1*resource_current/resource_maximum
                if runic_denominator:
                    expected *= 1+0.1*runic_numerator/runic_denominator
                if retaliation and not blocked:
                    expected *= 1.100000023841858
                self.assertAlmostEqual(actual, min(13, max(0, expected)), places=4)
                self.assertEqual(machine.reg_read(UC_X86_REG_ESP), stack + 12)
                self.assertEqual(machine.reg_read(UC_X86_REG_ESI), 0x1234)
                self.assertEqual(machine.reg_read(UC_X86_REG_EDI), 0x5678)
                compiled_cases.append('{ ' + str(control_word) + ', {' + ','.join((str(morale), str(luck), str(speed),
                    repr(float(initiative)) + 'f', repr(float(atb)) + 'f',
                    str(skip_speed).lower(), str(selected).lower(), str(retaliation and not blocked).lower()))
                    + ', {'+','.join(map(str,maximum))+'}, {'+','.join(map(str,current))+'}, '+str(half_speed).lower()+','+str(runic_numerator)+','+str(runic_denominator)+'}, '
                    + str(struct.unpack('<I', machine.mem_read(output, 4))[0]) + 'u }')

        source = preview_source()
        implementation = 'struct PlacementAggregate {' + source.split(
            'struct PlacementAggregate {', 1)[1].split('void CaptureKnownHeroModifiers(', 1)[0]
        driver = '#include <cstdint>\n#include <cstring>\n#include <cassert>\n' + implementation
        driver += '\nint main() { struct Case { uint16_t control; BaselineActionFactorInput input; uint32_t expected; };'
        driver += ' const Case cases[] = {' + ','.join(compiled_cases) + '};'
        driver += (' for (const auto& item : cases) { unsigned short control=item.control; __asm { fldcw control }'
                   ' float result = BaselineActionFactor(item.input);'
                   ' uint32_t bits; memcpy(&bits, &result, 4); assert(bits == item.expected); } }')
        with tempfile.TemporaryDirectory(prefix='workshop-action-factor-') as directory:
            temporary = Path(directory)
            (temporary / 'factor.cpp').write_text(driver, encoding='utf-8')
            (temporary / 'build.cmd').write_text(
                f'@call "{vcvarsall()}" x86 >nul\n@if errorlevel 1 exit /b 1\n'
                '@cl /nologo /EHsc /O2 /std:c++20 /Fe:factor.exe factor.cpp\n', encoding='utf-8')
            build = subprocess.run(['cmd', '/d', '/c', str(temporary / 'build.cmd')], cwd=temporary, capture_output=True)
            self.assertEqual(build.returncode, 0, build.stdout.decode(errors='replace') + build.stderr.decode(errors='replace'))
            result = subprocess.run([str(temporary / 'factor.exe')], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))

    def test_owned_damage_accumulation_matches_original_categories_and_rounding(self):
        import pefile
        from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
        from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_ECX
        game = WORKSPACE / '.local/test-game/bin/H5_Game.exe'
        if not game.is_file():
            self.skipTest('Pinned game EXE is needed for the native accumulation oracle')
        self.assertEqual(hashlib.sha256(game.read_bytes()).hexdigest(), probe.HASHES['H5_Game.exe'])
        executable = pefile.PE(str(game))
        base = executable.OPTIONAL_HEADER.ImageBase
        machine = Uc(UC_ARCH_X86, UC_MODE_32)
        machine.mem_map(base, (executable.OPTIONAL_HEADER.SizeOfImage + 4095) & ~4095)
        machine.mem_write(base, executable.get_memory_mapped_image())
        machine.mem_map(0x2000000, 65536)
        assembler = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32)
        actor, table, aggregate, weights, stack = 0x2001000, 0x2002000, 0x2003000, 0x2004000, 0x2008000
        machine.mem_write(actor, struct.pack('<I', table))
        initial = bytearray(72)
        struct.pack_into('<f', initial, 20, 1.0)
        machine.mem_write(aggregate, bytes(initial))
        machine.mem_write(weights, bytes(28))
        inputs = ((120, 5, 0.94722575, 0), (52, 6, 0.7998795, 2),
                  (450, 23, 1.3388745, 1), (9, 1, 0.01234567, 3),
                  (1, 30, 0.0000001, 0), (123456, 15, 12.9, 2),
                  (0, 4, 1.0, 1), (2147483647, 2, 0.125, 3))
        expected = []
        for damage, attack, factor, category in inputs:
            machine.mem_write(0x2000500, struct.pack('<f', factor))
            machine.mem_write(0x2000510, struct.pack('<f', 1.0))
            for offset, value in ((0x84, 0), (0x198, attack), (0x1e0, int(category == 0)),
                                  (0x190, int(category == 1)), (0x7c, 0x2007000 if category == 3 else 0)):
                address = 0x2006000 + offset * 16
                machine.mem_write(table + offset, struct.pack('<I', address))
                machine.mem_write(address, bytes(assembler.asm(f'mov eax, {value}; ret', address)[0]))
                machine.ctl_remove_cache(address, address + 32)
            machine.mem_write(0x2007000, struct.pack('<I', 0x2007100))
            machine.mem_write(0x2007100, struct.pack('<I', 0x2007200))
            machine.mem_write(0x2007200, bytes(assembler.asm('mov eax, 0x2007300; ret', 0x2007200)[0]))
            machine.mem_write(0x200731c, struct.pack('<I', 2))
            # Only external attribute/damage/factor/magic evaluators are stubs.
            # The native weighting, x87 stores and classification run unchanged.
            for address, assembly in (
                    (0xbfb880, f'mov eax, {damage}; ret 8'),
                    (0xbfb4b0, 'fld dword ptr [0x2000500]; ret 8'),
                    (0xbfb950, 'fld dword ptr [0x2000510]; ret 8'),
                    (0xbfa360, 'xor eax, eax; ret 8')):
                machine.mem_write(address, bytes(assembler.asm(assembly, address)[0]))
                machine.ctl_remove_cache(address, address + 32)
            machine.mem_write(stack, struct.pack('<7I', 0x2009000, weights, aggregate, actor, 0, 0, 0))
            machine.reg_write(UC_X86_REG_ESP, stack)
            machine.reg_write(UC_X86_REG_ECX, 0x2005000)
            try:
                machine.emu_start(0xbfba50, 0xbfbbf3, count=10000)
            except Exception as error:
                from unicorn.x86_const import UC_X86_REG_EIP
                self.fail(f'Native accumulation inputs={(damage, attack, factor, category)}, '
                          f'pc={machine.reg_read(UC_X86_REG_EIP):08x}: {error}')
            self.assertEqual(machine.reg_read(UC_X86_REG_ESP), stack - 24)
            raw = bytes(machine.mem_read(aggregate, 72))
            sums = bytes(machine.mem_read(weights, 28))
            # This oracle stops before health/status processing; those untouched
            # bytes must remain explicit rather than implied as covered.
            self.assertEqual(raw[24:40], bytes(16))
            self.assertEqual(raw[64:72], bytes(8))
            expected.append((raw, sums))
        source = preview_source()
        implementation = 'struct PlacementAggregate {' + source.split(
            'struct PlacementAggregate {', 1)[1].split('void CaptureKnownHeroModifiers(', 1)[0]
        driver = '#include <cstdint>\n#include <cstring>\n#include <cassert>\n' + implementation
        driver += '\n#include <cstdio>\nint main() { PlacementAggregate aggregate{}; aggregate.multiplier=1; PlacementWeights weights{};'
        for (damage, attack, factor, category), (raw, sums) in zip(inputs, expected):
            driver += f' AccumulatePlacementDamage(aggregate, weights, {damage}, {attack}, {repr(float(factor))}f, {category});'
            for target, data in (('aggregate', raw), ('weights', sums)):
                encoded = ','.join(str(value) + 'u' for value in struct.unpack('<' + str(len(data) // 4) + 'I', data))
                driver += ' { const uint32_t expected[] = {' + encoded + '};'
                driver += f' uint32_t actual[{len(data)//4}]; memcpy(actual, &{target}, {len(data)});'
                driver += f' for(unsigned word=0; word<{len(data)//4}; ++word) if(actual[word]!=expected[word]) {{'
                driver += f' fprintf(stderr, "damage={damage} category={category} {target} word=%u actual=%08x expected=%08x", word, actual[word], expected[word]); return 1; }} }}'
        machine.mem_write(stack, struct.pack('<3I', 0x2009000, weights, aggregate))
        machine.reg_write(UC_X86_REG_ESP, stack)
        machine.emu_start(0xbf9ee0, 0x2009000, count=1000)
        normalized = struct.unpack('<18I', machine.mem_read(aggregate, 72))
        driver += ' NormalizePlacementAggregate(aggregate, weights);'
        driver += ' { const uint32_t expected[] = {' + ','.join(str(value) + 'u' for value in normalized) + '};'
        driver += ' assert(memcmp(&aggregate, expected, 72)==0); } return 0;}'
        with tempfile.TemporaryDirectory(prefix='workshop-accumulation-') as directory:
            temporary = Path(directory)
            (temporary / 'accumulation.cpp').write_text(driver, encoding='utf-8')
            (temporary / 'build.cmd').write_text(
                f'@call "{vcvarsall()}" x86 >nul\n@if errorlevel 1 exit /b 1\n'
                '@cl /nologo /EHsc /O2 /std:c++20 /Fe:accumulation.exe accumulation.cpp\n', encoding='utf-8')
            build = subprocess.run(['cmd', '/d', '/c', str(temporary / 'build.cmd')], cwd=temporary, capture_output=True)
            self.assertEqual(build.returncode, 0, build.stdout.decode(errors='replace') + build.stderr.decode(errors='replace'))
            result = subprocess.run([str(temporary / 'accumulation.exe')], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))

    def test_health_scale_matches_native_flag_status_and_integer_conversion(self):
        import pefile
        from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
        from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_ESI, UC_X86_REG_EBP, UC_X86_REG_FPCW
        game=WORKSPACE/'.local/test-game/bin/H5_Game.exe'
        self.assertTrue(game.is_file(),'Pinned EXE required for health scaling oracle')
        self.assertEqual(hashlib.sha256(game.read_bytes()).hexdigest(),probe.HASHES['H5_Game.exe'])
        executable=pefile.PE(str(game));base=executable.OPTIONAL_HEADER.ImageBase
        cpu=Uc(UC_ARCH_X86,UC_MODE_32)
        cpu.mem_map(base,(executable.OPTIONAL_HEADER.SizeOfImage+4095)&~4095)
        cpu.mem_write(base,executable.get_memory_mapped_image());cpu.mem_map(0x2000000,65536)
        assembler=keystone.Ks(keystone.KS_ARCH_X86,keystone.KS_MODE_32)
        cpu.mem_write(0x2001000,struct.pack('<I',0x2002000))
        cases=[]
        for control in (0x037f,0x0c7f):
            for health in (0,1,7,260,123456789,2147483647,-17):
                for active,alternative in ((False,False),(True,False),(True,True)):
                    for offset,address,assembly in ((0x20,0x2004000,'xor eax,eax; ret'),
                            (0x1dc,0x2004040,f'mov eax,{health}; ret 4'),
                            (0x28c,0x2004080,f'mov eax,{int(active)}; ret 4'),
                            (0x28,0x20040c0,f'mov eax,{int(alternative)}; ret 4')):
                        code=bytes(assembler.asm(assembly,address)[0]);cpu.mem_write(address,code)
                        cpu.mem_write(0x2002000+offset,struct.pack('<I',address));cpu.ctl_remove_cache(address,address+len(code))
                    cpu.mem_write(0x2008000,bytes(80));cpu.reg_write(UC_X86_REG_ESP,0x2008000)
                    cpu.reg_write(UC_X86_REG_ESI,0x2001000);cpu.reg_write(UC_X86_REG_FPCW,control)
                    cpu.emu_start(0xbfbbf3,0xbfbc7f,count=1000)
                    self.assertEqual(cpu.reg_read(UC_X86_REG_FPCW),control)
                    expected=cpu.reg_read(UC_X86_REG_EBP)
                    scale=struct.unpack('<2I',executable.get_data((0xe72bf8 if alternative else 0xe87cf8)-base,8))
                    flags=0 if not active else 3 if alternative else 1
                    cases.append(f'{{{control},{health},{flags},{{{scale[0]}u,{scale[1]}u}},{expected}u}}')
        # Execute the original protection branch. Substitute only its combat
        # state getter; its cap/division/truncation/addition remain game code.
        protection_cases=[]
        code=bytes(assembler.asm('xor eax,eax; ret 4',0x20040c0)[0])
        cpu.mem_write(0x20040c0,code);cpu.ctl_remove_cache(0x20040c0,0x20040c0+len(code))
        for control in (0x037f,0x0c7f):
            for health in (0,1,42,260,2147483647,-17):
                for capacity in (0,1,56,1000):
                    for fraction in (0.0,0.5,0.99,1.0):
                        bits=struct.unpack('<I',struct.pack('<f',fraction))[0]
                        code=bytes(assembler.asm(f'mov dword ptr [edx],{bits}; mov eax,[esp+4]; '
                            f'mov dword ptr [eax],{capacity}; ret 4',0xa5b780)[0])
                        cpu.mem_write(0xa5b780,code);cpu.ctl_remove_cache(0xa5b780,0xa5b780+len(code))
                        cpu.mem_write(0x2008000,bytes(80));cpu.mem_write(0x2008024,struct.pack('<i',health))
                        cpu.reg_write(UC_X86_REG_ESP,0x2008000);cpu.reg_write(UC_X86_REG_ESI,0x2001000)
                        cpu.reg_write(UC_X86_REG_EBP,health);cpu.reg_write(UC_X86_REG_FPCW,control)
                        cpu.emu_start(0xbfbcf3,0xbfbdb8,count=1000)
                        self.assertEqual(cpu.reg_read(UC_X86_REG_FPCW),control)
                        expected=cpu.reg_read(UC_X86_REG_EBP)
                        protection_cases.append(f'{{{control},{health},{capacity},{bits}u,{expected}u}}')
        source=preview_source()
        implementation='struct PlacementAggregate {'+source.split('struct PlacementAggregate {',1)[1].split('void CaptureKnownHeroModifiers(',1)[0]
        driver='#include <cstdint>\n#include <cstring>\n#include <cassert>\n#include <cstdio>\n'+implementation
        driver+='int main(){ struct Case {unsigned short control; int32_t health; uint32_t flags,scale[2],expected;};'
        driver+='const Case cases[]={'+','.join(cases)+'};'
        driver+=('for(const auto& item:cases){unsigned short control=item.control; __asm {fldcw control}'
                 'uint32_t result=static_cast<uint32_t>(TransformPlacementHealth(item.health,item.flags,item.scale));'
                 'assert(result==item.expected); unsigned short restored; __asm {fnstcw restored}'
                 'assert(restored==control);}')
        driver+='struct ProtectionCase {unsigned short control; int32_t health,capacity; uint32_t fraction,expected;};'
        driver+='const ProtectionCase protection[]={'+','.join(protection_cases)+'};'
        driver+=('for(const auto& item:protection){unsigned short control=item.control; __asm {fldcw control}'
                 'float fraction; memcpy(&fraction,&item.fraction,4);'
                 'uint32_t result=static_cast<uint32_t>(TransformPlacementProtection(item.health,item.capacity,fraction));'
                 'if(result!=item.expected){fprintf(stderr,"control=%x health=%d capacity=%d fraction=%x actual=%u expected=%u",'
                 'control,item.health,item.capacity,item.fraction,result,item.expected);return 1;}'
                 'unsigned short restored; __asm {fnstcw restored}'
                 'assert(restored==control);} return 0;}')
        with tempfile.TemporaryDirectory(prefix='workshop-health-scale-') as directory:
            temporary=Path(directory);(temporary/'scale.cpp').write_text(driver,encoding='utf-8')
            (temporary/'build.cmd').write_text(f'@call "{vcvarsall()}" x86 >nul\n@if errorlevel 1 exit /b 1\n@cl /nologo /EHsc /O2 /std:c++20 /Fe:scale.exe scale.cpp\n',encoding='utf-8')
            build=subprocess.run(['cmd','/d','/c',str(temporary/'build.cmd')],cwd=temporary,capture_output=True)
            self.assertEqual(build.returncode,0,build.stdout.decode(errors='replace')+build.stderr.decode(errors='replace'))
            result=subprocess.run([str(temporary/'scale.exe')],capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr.decode(errors='replace'))

    def test_owned_health_accumulation_matches_native_subset_and_distinct_defence(self):
        import pefile
        from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
        from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_EBX
        game = WORKSPACE / '.local/test-game/bin/H5_Game.exe'
        if not game.is_file():
            self.skipTest('Pinned game EXE is needed for the native health oracle')
        self.assertEqual(hashlib.sha256(game.read_bytes()).hexdigest(), probe.HASHES['H5_Game.exe'])
        executable = pefile.PE(str(game))
        base = executable.OPTIONAL_HEADER.ImageBase
        machine = Uc(UC_ARCH_X86, UC_MODE_32)
        machine.mem_map(base, (executable.OPTIONAL_HEADER.SizeOfImage + 4095) & ~4095)
        machine.mem_write(base, executable.get_memory_mapped_image())
        machine.mem_map(0x2000000, 65536)
        assembler = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32)
        actor, table, aggregate, weights, stack = 0x2001000, 0x2002000, 0x2003000, 0x2004000, 0x2008000
        machine.mem_write(actor, struct.pack('<I', table))
        machine.mem_write(aggregate, bytes(72))
        machine.mem_write(weights, bytes(28))
        machine.mem_write(0x2006004, struct.pack('<I', 0x2006200))
        machine.mem_write(0x2006208, struct.pack('<I', 0x20))
        machine.mem_write(0x2006024, struct.pack('<I', 0x2006300))
        machine.mem_write(0x2006358, struct.pack('<I', 0x2006400))
        # External health-adjustment evaluator writes neutral outputs; native
        # final health/defence accumulation and eligibility branches are intact.
        machine.mem_write(0xa5b780, bytes(assembler.asm(
            'mov dword ptr [edx], 0; mov eax, dword ptr [esp + 4]; mov dword ptr [eax], 0; ret 4', 0xa5b780)[0]))
        inputs = ((280, 3, False, 1, False), (390, 9, False, 1, False),
                  (0, 7, False, 1, False), (55, 4, False, 1, True),
                  (89, 5, True, 1, False), (17, 2, False, 2, False),
                  (2147483647, 2, False, 1, True))
        expected = []
        for health, defence, doubled, actor_type, excluded in inputs:
            for offset, assembly in ((0, f'mov eax, {actor_type}; ret'),
                                     (0x20, 'xor eax, eax; ret'),
                                     (0x1dc, f'mov eax, {health}; ret 4'),
                                     (0x19c, f'mov eax, {defence}; ret'),
                                     (0x28c, 'xor eax, eax; ret 4'),
                                     (0x6c, 'mov eax, 0x2006000; ret'),
                                     (0x28, 'cmp dword ptr [esp + 4], 0x13d; jne none; '
                                      f'mov eax, {int(doubled)}; ret 4; none: xor eax, eax; ret 4')):
                address = 0x200a000 + offset * 16
                code = bytes(assembler.asm(assembly, address)[0])
                machine.mem_write(table + offset, struct.pack('<I', address))
                machine.mem_write(address, code)
                machine.ctl_remove_cache(address, address + len(code))
            code = bytes(assembler.asm(f'mov eax, {int(excluded)}; ret', 0x2006400)[0])
            machine.mem_write(0x2006400, code)
            machine.ctl_remove_cache(0x2006400, 0x2006420)
            machine.mem_write(stack, bytes(64))
            machine.reg_write(UC_X86_REG_ESP, stack)
            machine.reg_write(UC_X86_REG_ESI, actor)
            machine.reg_write(UC_X86_REG_EDI, aggregate)
            machine.reg_write(UC_X86_REG_EBX, weights)
            machine.emu_start(0xbfbbf3, 0xbfbe43, count=10000)
            self.assertEqual(machine.reg_read(UC_X86_REG_ESP), stack)
            raw = bytes(machine.mem_read(aggregate, 72))
            sums = bytes(machine.mem_read(weights, 28))
            self.assertEqual(raw[:24], bytes(24))
            self.assertEqual(raw[40:], bytes(32))
            expected.append((raw, sums))
        source = preview_source()
        implementation = 'struct PlacementAggregate {' + source.split(
            'struct PlacementAggregate {', 1)[1].split('void CaptureKnownHeroModifiers(', 1)[0]
        driver = '#include <cstdint>\n#include <cstring>\n#include <cassert>\n' + implementation
        driver += '\nint main() { PlacementAggregate aggregate{}; PlacementWeights weights{};'
        for (health, defence, doubled, actor_type, excluded), (raw, sums) in zip(inputs, expected):
            eligible = actor_type == 1 and not excluded
            driver += (f' AccumulatePlacementHealth(aggregate, weights, {health}, '
                       f'{defence * (2 if doubled else 1)}, {defence}, {str(eligible).lower()});')
            for target, data in (('aggregate', raw), ('weights', sums)):
                encoded = ','.join(str(value) + 'u' for value in struct.unpack('<' + str(len(data) // 4) + 'I', data))
                driver += ' { const uint32_t expected[] = {' + encoded + '};'
                driver += f' assert(memcmp(&{target}, expected, {len(data)})==0); }}'
        machine.mem_write(stack, struct.pack('<3I', 0x2009000, weights, aggregate))
        machine.reg_write(UC_X86_REG_ESP, stack)
        machine.emu_start(0xbf9ee0, 0x2009000, count=1000)
        normalized = struct.unpack('<18I', machine.mem_read(aggregate, 72))
        driver += ' NormalizePlacementAggregate(aggregate, weights);'
        driver += ' { const uint32_t expected[] = {' + ','.join(str(value) + 'u' for value in normalized) + '};'
        driver += ' assert(memcmp(&aggregate, expected, 72)==0); } return 0;}'
        with tempfile.TemporaryDirectory(prefix='workshop-health-') as directory:
            temporary = Path(directory)
            (temporary / 'health.cpp').write_text(driver, encoding='utf-8')
            (temporary / 'build.cmd').write_text(
                f'@call "{vcvarsall()}" x86 >nul\n@if errorlevel 1 exit /b 1\n'
                '@cl /nologo /EHsc /O2 /std:c++20 /Fe:health.exe health.cpp\n', encoding='utf-8')
            build = subprocess.run(['cmd', '/d', '/c', str(temporary / 'build.cmd')], cwd=temporary, capture_output=True)
            self.assertEqual(build.returncode, 0, build.stdout.decode(errors='replace') + build.stderr.decode(errors='replace'))
            result = subprocess.run([str(temporary / 'health.exe')], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))

    def test_owned_aggregate_initialization_seeds_action_before_damage(self):
        import pefile
        from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
        from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_ECX
        game = WORKSPACE / '.local/test-game/bin/H5_Game.exe'
        if not game.is_file():
            self.skipTest('Pinned game EXE is needed for the native initialization oracle')
        self.assertEqual(hashlib.sha256(game.read_bytes()).hexdigest(), probe.HASHES['H5_Game.exe'])
        executable = pefile.PE(str(game))
        base = executable.OPTIONAL_HEADER.ImageBase
        machine = Uc(UC_ARCH_X86, UC_MODE_32)
        machine.mem_map(base, (executable.OPTIONAL_HEADER.SizeOfImage + 4095) & ~4095)
        machine.mem_write(base, executable.get_memory_mapped_image())
        machine.mem_map(0x2000000, 65536)
        aggregate, army, table, getter, stack = 0x2001000, 0x2002000, 0x2003000, 0x2004000, 0x2008000
        machine.mem_write(army, struct.pack('<I', table))
        machine.mem_write(table, struct.pack('<I', getter))
        machine.mem_write(getter, bytes(keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32).asm(
            'mov eax, 0x2005000; ret', getter)[0]))
        machine.mem_write(stack, struct.pack('<4I', 0x2009000, aggregate, 0, army))
        machine.reg_write(UC_X86_REG_ESP, stack)
        machine.reg_write(UC_X86_REG_ECX, 0x2006000)
        # Stop before auxiliary native-helper allocation; the fresh helper slot
        # is neutral here and its lifetime is outside this initializer's scope.
        machine.emu_start(0xbfbe50, 0xbfbece, count=1000)
        raw = bytes(machine.mem_read(aggregate, 72))
        weights = bytes(machine.mem_read(machine.reg_read(UC_X86_REG_ESP) + 0x2c, 28))
        self.assertEqual(struct.unpack('<f', weights[4:8])[0], 1.0)
        self.assertEqual(struct.unpack('<f', raw[20:24])[0], 1.0)
        source = preview_source()
        implementation = 'struct PlacementAggregate {' + source.split(
            'struct PlacementAggregate {', 1)[1].split('void CaptureKnownHeroModifiers(', 1)[0]
        driver = '#include <cstdint>\n#include <cstring>\n#include <cassert>\n' + implementation
        driver += '\nint main() { PlacementAggregate aggregate; PlacementWeights weights;'
        driver += ' InitializePlacementAggregate(aggregate,weights);'
        for target, data in (('aggregate', raw), ('weights', weights)):
            encoded = ','.join(str(value) + 'u' for value in struct.unpack('<' + str(len(data) // 4) + 'I', data))
            driver += ' { const uint32_t expected[] = {' + encoded + '};'
            driver += f' assert(memcmp(&{target}, expected, {len(data)})==0); }}'
        driver += 'return 0;}'
        with tempfile.TemporaryDirectory(prefix='workshop-aggregate-init-') as directory:
            temporary = Path(directory)
            (temporary / 'init.cpp').write_text(driver, encoding='utf-8')
            (temporary / 'build.cmd').write_text(
                f'@call "{vcvarsall()}" x86 >nul\n@if errorlevel 1 exit /b 1\n'
                '@cl /nologo /EHsc /O2 /std:c++20 /Fe:init.exe init.cpp\n', encoding='utf-8')
            build = subprocess.run(['cmd', '/d', '/c', str(temporary / 'build.cmd')], cwd=temporary, capture_output=True)
            self.assertEqual(build.returncode, 0, build.stdout.decode(errors='replace') + build.stderr.decode(errors='replace'))
            result = subprocess.run([str(temporary / 'init.exe')], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))

    def test_owned_aggregate_normalization_matches_original_words_and_zero_gates(self):
        import pefile
        from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
        from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_FPCW
        game = WORKSPACE / '.local/test-game/bin/H5_Game.exe'
        if not game.is_file():
            self.skipTest('Pinned game EXE is needed for the native aggregate oracle')
        self.assertEqual(hashlib.sha256(game.read_bytes()).hexdigest(), probe.HASHES['H5_Game.exe'])
        executable = pefile.PE(str(game))
        base = executable.OPTIONAL_HEADER.ImageBase
        image = executable.get_memory_mapped_image()
        machine = Uc(UC_ARCH_X86, UC_MODE_32)
        machine.mem_map(base, (executable.OPTIONAL_HEADER.SizeOfImage + 4095) & ~4095)
        machine.mem_write(base, image)
        machine.mem_map(0x2000000, 65536)
        cases = []
        for control_word, index in ((control, index) for control in (0x037f, 0x0c7f) for index in range(10)):
            raw = bytearray(struct.pack('<18I', *([0x3f012345 + index] * 18)))
            for offset, value in ((12, 172 if index != 1 else 0),
                                  (24, 670 if index != 2 else 0), (32, 670 if index != 3 else 0)):
                struct.pack_into('<i', raw, offset, value)
            for offset, value in ((44, 720.0 + index * 0.25), (52, 48.0 + index), (60, 364.0 + index)):
                struct.pack_into('<f', raw, offset, value)
            weights = struct.pack('<ifi4i', 1084 + index, 156.020065 + index * 0.01, 5690 + index,
                                  5690 - index, 120 if index != 4 else 0,
                                  8 if index != 5 else 0, 52 if index != 6 else 0)
            if index == 7:
                weights = bytes(28)
                for offset in (12, 24, 32):
                    struct.pack_into('<i', raw, offset, 0)
            if index == 8:
                struct.pack_into('<i', raw, 12, 2147483647)
            if index == 9:
                struct.pack_into('<i', raw, 24, -670)
            machine.mem_write(0x2001000, bytes(raw))
            machine.mem_write(0x2002000, weights)
            machine.mem_write(0x2008000, struct.pack('<3I', 0x2003000, 0x2002000, 0x2001000))
            machine.reg_write(UC_X86_REG_ESP, 0x2008000)
            machine.reg_write(UC_X86_REG_FPCW, control_word)
            # Original function and all arithmetic execute without stubs.
            machine.emu_start(0xbf9ee0, 0x2003000, count=1000)
            self.assertEqual(machine.reg_read(UC_X86_REG_ESP), 0x200800c)
            result = bytes(machine.mem_read(0x2001000, 72))
            for word in (0, 1, 2, 3, 6, 8, 10, 12, 14, 16, 17):
                self.assertEqual(result[word * 4:word * 4 + 4], raw[word * 4:word * 4 + 4])
            if index == 7:
                self.assertEqual(result, raw)
            encoded = []
            for data in (raw, weights, result):
                words = struct.unpack('<' + str(len(data) // 4) + 'I', data)
                encoded.append('{' + ','.join(str(value) + 'u' for value in words) + '}')
            cases.append('{' + str(control_word) + ',' + ','.join(encoded) + '}')
        source = preview_source()
        implementation = 'struct PlacementAggregate {' + source.split(
            'struct PlacementAggregate {', 1)[1].split('void CaptureKnownHeroModifiers(', 1)[0]
        driver = '#include <cstdint>\n#include <cstring>\n#include <cassert>\n' + implementation
        driver += ('\nint main() { struct Case { uint16_t control; uint32_t input[18], weights[7], expected[18]; };'
                   ' const Case cases[] = {' + ','.join(cases) + '};'
                   ' for (const auto& item : cases) { PlacementAggregate aggregate; PlacementWeights weights;'
                   ' unsigned short control=item.control; __asm { fldcw control }'
                   ' memcpy(&aggregate, item.input, 72); memcpy(&weights, item.weights, 28);'
                   ' NormalizePlacementAggregate(aggregate, weights);'
                   ' assert(memcmp(&aggregate, item.expected, 72) == 0); } }')
        with tempfile.TemporaryDirectory(prefix='workshop-aggregate-') as directory:
            temporary = Path(directory)
            (temporary / 'aggregate.cpp').write_text(driver, encoding='utf-8')
            (temporary / 'build.cmd').write_text(
                f'@call "{vcvarsall()}" x86 >nul\n@if errorlevel 1 exit /b 1\n'
                '@cl /nologo /EHsc /O2 /std:c++20 /Fe:aggregate.exe aggregate.cpp\n', encoding='utf-8')
            build = subprocess.run(['cmd', '/d', '/c', str(temporary / 'build.cmd')], cwd=temporary, capture_output=True)
            self.assertEqual(build.returncode, 0, build.stdout.decode(errors='replace') + build.stderr.decode(errors='replace'))
            result = subprocess.run([str(temporary / 'aggregate.exe')], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))

    def test_compiled_projection_snapshot_keeps_all_slots_and_buffer_guards(self):
        try:
            import pefile
            import capstone
            from capstone.x86_const import X86_OP_MEM, X86_OP_IMM, X86_REG_EAX
        except ImportError:
            self.skipTest('Compiled snapshot check needs pefile and Capstone')
        artifact = BUILD / 'WorkshopDeploymentPreview.dll'
        if not artifact.is_file():
            self.skipTest('Build the native DLL before checking its snapshot ABI')
        executable = pefile.PE(str(artifact))
        base = executable.OPTIONAL_HEADER.ImageBase
        offset = next(export.address for export in executable.DIRECTORY_ENTRY_EXPORT.symbols
                      if export.name == b'WorkshopDeploymentPreviewProjectionTrace')
        disassembler = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        disassembler.detail = True
        instructions = list(disassembler.disasm(executable.get_data(offset, 256), base + offset))
        # Locate actual linked globals through the compiled export's loads.
        absolute_loads = [instruction for instruction in instructions if instruction.mnemonic == 'mov'
                          and instruction.operands[1].type == X86_OP_MEM
                          and not instruction.operands[1].mem.base and not instruction.operands[1].mem.index]
        count_register = next(instruction.operands[0].reg for instruction in instructions
                              if instruction.mnemonic == 'cmp' and len(instruction.operands) == 2
                              and instruction.operands[1].type == X86_OP_IMM
                              and instruction.operands[1].imm == 7)
        count_address = next(instruction.operands[1].mem.disp for instruction in absolute_loads
                             if instruction.operands[0].reg == count_register)
        generation_address = next(instruction.operands[1].mem.disp for instruction in absolute_loads
                                  if instruction.operands[0].reg != count_register)
        public_address = next(instruction.operands[1].mem.disp for instruction in absolute_loads
                              if instruction.operands[0].reg == X86_REG_EAX)
        cell_address = next(instruction.operands[1].mem.disp for instruction in instructions
                            if instruction.mnemonic == 'mov' and instruction.operands[1].type == X86_OP_MEM
                            and instruction.operands[1].mem.scale == 8)
        output = count_address - 496
        slots = [(400000 + index, 25 - index, 30 - index * 3, 1 + index % 2) for index in range(7)]
        for count in (0, 1, 7, 8):
            with self.subTest(models=count):
                machine = Uc(UC_ARCH_X86, UC_MODE_32)
                machine.mem_map(base, executable.OPTIONAL_HEADER.SizeOfImage)
                machine.mem_write(base, executable.get_memory_mapped_image())
                machine.mem_map(0x200000, 0x20000)
                machine.mem_map(0x300000, 0x10000)
                machine.mem_write(count_address, struct.pack('<I', count))
                machine.mem_write(public_address, struct.pack('<I', 7))
                machine.mem_write(generation_address, struct.pack('<I', 123))
                machine.mem_write(output + 384, struct.pack('<2I', 32, 32))
                for index, (creature, x, y, size) in enumerate(slots):
                    machine.mem_write(output + 640 + index * 4, struct.pack('<I', creature))
                    machine.mem_write(output + 600 + index * 4, struct.pack('<I', size))
                    machine.mem_write(output + 864 + index * 4, struct.pack('<I', 15 + index))
                    machine.mem_write(cell_address + index * 8, struct.pack('<2I', x, y))
                machine.mem_write(0x307ff0, b'\xa5' * 248)
                machine.mem_write(0x218000, struct.pack('<2I', 0x30f000, 0x308000))
                machine.reg_write(UC_X86_REG_ESP, 0x218000)
                machine.emu_start(base + offset, 0x30f000, count=10000)
                self.assertEqual(machine.reg_read(UC_X86_REG_ESP), 0x218008)
                self.assertEqual(bytes(machine.mem_read(0x307ff0, 16)), b'\xa5' * 16)
                self.assertEqual(bytes(machine.mem_read(0x3080d8, 16)), b'\xa5' * 16)
                if count > 7:
                    self.assertEqual(machine.reg_read(UC_X86_REG_EAX), 0)
                    self.assertEqual(bytes(machine.mem_read(0x308000, 216)), b'\xa5' * 216)
                else:
                    self.assertEqual(machine.reg_read(UC_X86_REG_EAX), 1)
                    expected = [8, 7, count, 123, 32, 32]
                    expected += [value for slot in slots[:count] for value in slot]
                    expected += [0] * (38 - count * 4) + [0xffffffff, 0]
                    expected += [15 + index for index in range(count)] + [0] * (7 - count)
                    expected += [0]
                    self.assertEqual(struct.unpack('<54I', machine.mem_read(0x308000, 216)), tuple(expected))
        executable.close()

    def test_launcher_bootstrap_preserves_entry_state_and_exits_on_failure(self):
        from unicorn import UC_HOOK_CODE
        from unicorn.x86_const import UC_X86_REG_EIP
        source = (MOD_ROOT / 'src/preview_loader.cpp').read_text()
        assembly = source.split('unsigned char startupCode[] = {', 1)[1].split('};', 1)[0]
        assembly = '\n'.join(line.split('//', 1)[0] for line in assembly.splitlines())
        code = bytearray(int(value, 0) for value in re.findall(r'0x[0-9a-f]+|\b0\b', assembly))
        code[3:7] = struct.pack('<I', 0x301000)
        for failure in range(8):
            with self.subTest(failed_stage=failure):
                machine = Uc(UC_ARCH_X86, UC_MODE_32)
                machine.mem_map(0x200000, 0x20000)
                machine.mem_map(0x300000, 0x10000)
                machine.mem_map(0xe0a000, 4096)
                machine.mem_write(0x300000, bytes(code))
                for offset, value in ((16, b'LoadLibraryW'), (48, b'kernel32.dll'),
                                      (80, b'WorkshopDeploymentPreviewInstall'),
                                      (128, b'WorkshopDeploymentPreviewVersion')):
                    machine.mem_write(0x301000 + offset, value + b'\0')
                machine.mem_write(0xe0a0d4, struct.pack('<I', 0x302000))
                machine.mem_write(0xe0a044, struct.pack('<I', 0x302100))
                machine.mem_write(0xe0a160, struct.pack('<I', 0x302500))
                calls = []
                exited = []

                def startup_api(emulator, address, size, unused):
                    if not 0x302000 <= address <= 0x302500:
                        return
                    stack = emulator.reg_read(UC_X86_REG_ESP)
                    values = struct.unpack('<3I', emulator.mem_read(stack, 12))
                    if address == 0x302500:
                        exited.append(values[1])
                        emulator.emu_stop()
                        return
                    calls.append(address)
                    arguments, result = (1, 0x7777) if address == 0x302000 else (0, 1)
                    if address == 0x302100:
                        name = bytes(emulator.mem_read(values[2], 64)).split(b'\0', 1)[0]
                        arguments = 2
                        result = {b'LoadLibraryW': 0x302200, b'WorkshopDeploymentPreviewVersion': 0x302300,
                                  b'WorkshopDeploymentPreviewInstall': 0x302400}[name]
                    elif address == 0x302200:
                        arguments, result = 1, 0x8888
                        self.assertEqual(values[1], 0x301100)
                    if len(calls) == failure:
                        result = 0
                    emulator.reg_write(UC_X86_REG_EAX, result)
                    emulator.reg_write(UC_X86_REG_ESP, stack + 4 + arguments * 4)
                    emulator.reg_write(UC_X86_REG_EIP, values[0])

                preserved = {UC_X86_REG_EBX: 0x12, UC_X86_REG_ECX: 0x34, UC_X86_REG_EDX: 0x56,
                             UC_X86_REG_ESI: 0x78, UC_X86_REG_EDI: 0x90, UC_X86_REG_EBP: 0x218100,
                             UC_X86_REG_ESP: 0x218000, UC_X86_REG_EFLAGS: 0x246}
                for register, value in preserved.items():
                    machine.reg_write(register, value)
                machine.reg_write(UC_X86_REG_EAX, 0x300000)
                machine.hook_add(UC_HOOK_CODE, startup_api)
                machine.emu_start(0x300000, 0xd11e1c, count=1000)
                status = struct.unpack('<I', machine.mem_read(0x301000, 4))[0]
                if failure:
                    self.assertEqual(exited, [1])
                    self.assertEqual(status, 0xffffffff)
                    self.assertEqual(len(calls), failure)
                else:
                    self.assertEqual(exited, [])
                    self.assertEqual(status, 2)
                    self.assertEqual(len(calls), 7)
                    self.assertEqual(machine.reg_read(UC_X86_REG_EAX), 0xd11e1c)
                    for register, value in preserved.items():
                        self.assertEqual(machine.reg_read(register), value)

    def test_compiled_installer_preparation_failures_leave_original_code(self):
        # Integration tier: executes the current x86 DLL, not a Python rewrite.
        try:
            import pefile
            from unicorn import UC_HOOK_CODE
            from unicorn.x86_const import UC_X86_REG_EIP
        except ImportError:
            self.skipTest('Compiled-DLL check needs pefile and Unicorn')
        artifact = BUILD / 'WorkshopDeploymentPreview.dll'
        if not artifact.is_file():
            self.skipTest('Build the native plugin to test its compiled installer')
        executable = pefile.PE(str(artifact))
        base = executable.OPTIONAL_HEADER.ImageBase
        entry = base + next(export.address for export in executable.DIRECTORY_ENTRY_EXPORT.symbols
                            if export.name == b'WorkshopDeploymentPreviewInstall')
        originals = {0x433440: '83ec505355', 0x577010: '558bec83e4f8', 0x5767a0: '81ecbc000000',
                     0x546f40: '81ec14070000', 0x578986: '8b56408b463c', 0x577e70: '5333db568bf1',
                     0x579370: '568bf18b8698000000', 0x541fa0: '515333db56', 0xa4eb10: '8b4f988b04b1'}
        failures = [None] + [('VirtualProtect', index) for index in range(1, 12)]
        failures += [(operation, index) for operation in ('VirtualAlloc', 'FlushInstructionCache') for index in (1, 2)]
        for admin, failure in [(admin, failure) for admin in (False, True) for failure in failures] + [(True, ('VirtualProtect', index)) for index in (12,13,14,15,16,17)]:
            with self.subTest(admin=admin, failure=failure):
                machine = Uc(UC_ARCH_X86, UC_MODE_32)
                machine.mem_map(base, executable.OPTIONAL_HEADER.SizeOfImage)
                machine.mem_write(base, executable.get_memory_mapped_image())
                machine.mem_map(0x400000, 0x200000)
                machine.mem_map(0xa4e000, 4096)
                machine.mem_map(0xbfb000, 4096)
                machine.mem_map(0xbfc000, 4096)
                machine.mem_map(0xbfa000, 4096)
                machine.mem_map(0x200000, 0x20000)
                machine.mem_map(0x300000, 0x10000)
                for address, original in originals.items():
                    machine.mem_write(address, bytes.fromhex(original))
                machine.mem_write(0xbfbb08, bytes.fromhex('d9442424d84304'))
                machine.mem_write(0xbfc12f, bytes.fromhex('03d88b442428'))
                machine.mem_write(0xbfa4a5, bytes.fromhex('8b44240c5f'))
                machine.mem_write(0x4e9c4d, bytes.fromhex('8b7d088b54240c'))
                machine.mem_map(0x855000,4096)
                machine.mem_write(0x855451,bytes.fromhex('8b106a646a01'))
                machine.mem_write(0x5d434c,bytes.fromhex('8d8c2484000000'))
                imports, calls, protections = {}, {}, {}
                allocated, freed = [], []
                for library in executable.DIRECTORY_ENTRY_IMPORT:
                    for imported in library.imports:
                        address = 0x300000 + len(imports) * 16
                        imports[address] = imported.name.decode()
                        machine.mem_write(imported.address, struct.pack('<I', address))

                def windows_api(emulator, address, size, unused):
                    if address not in imports:
                        return
                    operation = imports[address]
                    calls[operation] = calls.get(operation, 0) + 1
                    stack = emulator.reg_read(UC_X86_REG_ESP)
                    arguments = struct.unpack('<5I', emulator.mem_read(stack, 20))
                    result = int(failure != (operation, calls[operation]))
                    if operation == 'VirtualAlloc':
                        count = 4
                        if result:
                            result = 0x310000 + len(allocated) * 4096
                            emulator.mem_map(result, 4096)
                            allocated.append(result)
                            protections[result] = arguments[4]
                    elif operation == 'VirtualProtect':
                        count = 4
                        if result:
                            page = arguments[1] & ~4095
                            emulator.mem_write(arguments[4], struct.pack('<I', protections.get(page, 0x20)))
                            protections[page] = arguments[3]
                    elif operation == 'VirtualFree':
                        count = 3
                        freed.append(arguments[1])
                    elif operation == 'FlushInstructionCache':
                        count = 3
                    elif operation == 'GetCurrentProcess':
                        count, result = 0, 0xffffffff
                    elif operation == 'GetEnvironmentVariableW':
                        count, result = 3, 0
                        name = bytes(emulator.mem_read(arguments[1], 42)).decode('utf-16-le').split('\0')[0]
                        if admin and name == 'H5_PREVIEW_SUPERADMIN':
                            emulator.mem_write(arguments[2], '1\0'.encode('utf-16-le'))
                            result = 1
                    else:
                        self.fail('Unexpected installer API: ' + operation)
                    emulator.reg_write(UC_X86_REG_EAX, result)
                    emulator.reg_write(UC_X86_REG_ESP, stack + 4 + count * 4)
                    emulator.reg_write(UC_X86_REG_EIP, arguments[0])

                machine.hook_add(UC_HOOK_CODE, windows_api)
                machine.reg_write(UC_X86_REG_ESP, 0x218000)
                machine.mem_write(0x218000, struct.pack('<I', 0x30f000))
                machine.emu_start(entry, 0x30f000, count=100000)
                self.assertEqual(machine.reg_read(UC_X86_REG_EAX), int(failure is None))
                self.assertEqual(machine.reg_read(UC_X86_REG_ESP), 0x218004)
                for address, original in originals.items():
                    if failure is None:
                        self.assertEqual(bytes(machine.mem_read(address, 1)), b'\xe9')
                    else:
                        self.assertEqual(bytes(machine.mem_read(address, len(bytes.fromhex(original)))), bytes.fromhex(original))
                    self.assertEqual(protections.get(address & ~4095, 0x20), 0x20)
                if admin and failure is None:
                    self.assertEqual(bytes(machine.mem_read(0xbfbb08, 1)), b'\xe9')
                else:
                    self.assertEqual(bytes(machine.mem_read(0xbfbb08, 7)), bytes.fromhex('d9442424d84304'))
                self.assertEqual(protections.get(0xbfb000, 0x20), 0x20)
                if admin and failure is None:
                    self.assertEqual(bytes(machine.mem_read(0xbfc12f, 1)), b'\xe9')
                else:
                    self.assertEqual(bytes(machine.mem_read(0xbfc12f, 6)), bytes.fromhex('03d88b442428'))
                self.assertEqual(protections.get(0xbfc000, 0x20), 0x20)
                if admin and failure is None:
                    self.assertEqual(bytes(machine.mem_read(0xbfa4a5, 1)), b'\xe9')
                else:
                    self.assertEqual(bytes(machine.mem_read(0xbfa4a5, 5)), bytes.fromhex('8b44240c5f'))
                self.assertEqual(protections.get(0xbfa000, 0x20), 0x20)
                if admin and failure is None:
                    self.assertEqual(bytes(machine.mem_read(0x5d434c, 1)), b'\xe9')
                else:
                    self.assertEqual(bytes(machine.mem_read(0x5d434c, 7)), bytes.fromhex('8d8c2484000000'))
                self.assertEqual(protections.get(0x5d4000, 0x20), 0x20)
                if failure is None:
                    self.assertEqual(len(allocated), 2)
                    self.assertEqual(freed, [])
                    self.assertTrue(all(protections[address] == 0x20 for address in allocated))
                else:
                    self.assertEqual(sorted(allocated), sorted(freed))
        executable.close()

    @unittest.skipIf(keystone is None, 'Optional keystone assembler is not installed')
    def test_projection_tooltip_hit_test_preserves_other_windows_and_callers(self):
        source = preview_source()
        assembly = source.split('void ProjectionTooltipHitTestHook()', 1)[1].split('__asm {', 1)[1].split('}', 1)[0]
        assembly = re.sub(r'//[^\n]*', '', assembly).replace('g_outputStorage', '0x303000')
        assembly = assembly.replace('g_fpu', '0x30a000').replace('AttachProjectionTooltipProvider', '0x30b000')
        assembly = assembly.replace('g_detailsHitTest', '0x30c000').replace('g_tooltipController', '0x30c004')
        assembly = assembly.replace('ProjectionTooltipWindowIsDecoration', '0x30d000')
        code = bytes(keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32).asm(assembly, addr=0x300000)[0])
        cases = [
            ('deployment title', 0xe2ff58, 3, 65, 0x6b8aad, 0, True),
            ('own card', 0xe73c70, 3, 65, 0x6b8aad, 0x304130, True),
            ('other gathering window', 0xe73c70, 3, 65, 0x6b8aad, 0x305130, False),
            ('ordinary control', 0xe12345, 3, 65, 0x6b8aad, 0x304130, False),
            ('empty ground', 0xe2ff58, 3, 0, 0x6b8aad, 0, False),
            ('no projection', 0xe2ff58, 0, 65, 0x6b8aad, 0, False),
            ('another caller', 0xe2ff58, 3, 65, 0x123456, 0, False),
        ]
        cases = [(*case, False) for case in cases] + [
            ('details title', 0xe2ff58, 3, 65, 0x123456, 0, True, True),
            ('details own card', 0xe73c70, 3, 65, 0x123456, 0x304130, True, True),
            ('details other card', 0xe73c70, 3, 65, 0x123456, 0x305130, False, True),
            ('details modal', 0xe12345, 3, 65, 0x123456, 0, False, True),
        ]
        for name, vtable, models, hovered, caller, card, skips, details in cases:
            with self.subTest(name=name):
                machine = Uc(UC_ARCH_X86, UC_MODE_32)
                machine.mem_map(0x200000, 65536)
                machine.mem_map(0x300000, 65536)
                machine.mem_map(0xa4e000, 4096)
                machine.mem_write(0x300000, code)
                # Production decoration policy has its own direct C++ tests;
                # this boundary verifies hook routing, arguments and state.
                decoration = ('mov eax,[esp+4]; cmp dword ptr [eax],0xe2ff58; je yes; '
                              'cmp dword ptr [eax],0xe73c70; jne no; mov edx,[esp+8]; '
                              'cmp byte ptr [0x30c000],0; je controller_ready; mov edx,[0x30c004]; '
                              'controller_ready: test edx,edx; jz no; mov edx,[edx+0x44]; '
                              'test edx,edx; jz no; mov edx,[edx+8]; sub edx,0x130; cmp eax,edx; jne no; '
                              'yes: mov eax,1; ret 8; no: xor eax,eax; ret 8')
                machine.mem_write(0x30d000,bytes(keystone.Ks(keystone.KS_ARCH_X86,keystone.KS_MODE_32).asm(
                    decoration,addr=0x30d000)[0]))
                machine.mem_write(0x30b000, bytes(keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32).asm(
                    'mov eax, [esp+4]; mov [0x30b100], eax; ret 4', addr=0x30b000)[0]))
                machine.mem_write(0x303008 + 496, struct.pack('<I', models))
                machine.mem_write(0x303008 + 504, struct.pack('<I', hovered))
                machine.mem_write(0x304000, struct.pack('<I', vtable))
                machine.mem_write(0x306000, struct.pack('<I', 0x304000))
                machine.mem_write(0x307000 - 0x68, struct.pack('<I', 0x306000))
                machine.mem_write(0x208000, struct.pack('<4I', 0, 0x308000, 0, caller))
                machine.mem_write(0x308044, struct.pack('<I', 0x309000))
                machine.mem_write(0x309008, struct.pack('<I', card))
                machine.mem_write(0x30c000, struct.pack('<2I', int(details), 0x308000))
                machine.reg_write(UC_X86_REG_EDI, 0x307000)
                machine.reg_write(UC_X86_REG_ESI, 0)
                machine.reg_write(UC_X86_REG_EDX, 0x13579)
                machine.reg_write(UC_X86_REG_ESP, 0x208000)
                machine.reg_write(UC_X86_REG_EFLAGS, 0x246)
                machine.emu_start(0x300000, 0xa4eb2c if skips else 0xa4eb16, count=100)
                self.assertEqual(machine.reg_read(UC_X86_REG_ESP), 0x208000)
                self.assertEqual(machine.reg_read(UC_X86_REG_EDX), 0x13579)
                self.assertEqual(machine.reg_read(UC_X86_REG_EFLAGS), 0x246)
                self.assertEqual(machine.reg_read(UC_X86_REG_EAX), 0x304000)
                self.assertEqual(machine.reg_read(UC_X86_REG_ECX), 0x306000)
                attached = struct.unpack('<I', machine.mem_read(0x30b100, 4))[0]
                self.assertEqual(attached, 0x308000 if models and hovered and caller == 0x6b8aad else 0)

    def test_native_solo_placement_uses_center_then_free_columns_and_rows(self):
        source = preview_source()
        assembly = source.split('        // 0x857380, one assumed unsplit defender:', 1)[1].split('    rank_row:', 1)[0]
        assembly = '// 0x857380, one assumed unsplit defender:' + assembly
        assembly += '\nrank_row: xor eax, eax\njmp 0x306000\ncell_selected: mov eax, 1\njmp 0x306000\nfootprint_free:'
        assembly += source.split('    footprint_free:', 1)[1].split('    footprint_occupy:', 1)[0]
        assembly = '\n'.join(line.split('//', 1)[0] for line in assembly.splitlines())
        for symbol, address in {'g_creatureDefinition': '0x302000', 'g_outputStorage': '0x303000', 'g_cell': '0x302100'}.items():
            assembly = assembly.replace(symbol, address)
        code = bytes(keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32).asm(assembly, addr=0x300000)[0])
        cases = [
            ('small center', 1, set(), (13, 6)),
            ('large center', 2, set(), (13, 6)),
            ('small adjacent column', 1, {(13, 6)}, (12, 6)),
            ('small next row', 1, {(13, 6), (12, 6)}, (13, 7)),
            ('large full footprint', 2, {(12, 5)}, (13, 7)),
            ('large two rows blocked', 2, {(12, 6)}, (13, 8)),
            ('exhausted uses fallback', 1, {(x, y) for x in (12, 13) for y in range(6, 11)}, None),
        ]
        for name, size, obstacles, expected in cases:
            with self.subTest(name=name):
                machine = Uc(UC_ARCH_X86, UC_MODE_32)
                machine.mem_map(0x200000, 65536)
                machine.mem_map(0x300000, 65536)
                machine.mem_write(0x300000, code)
                machine.mem_write(0x302000, struct.pack('<I', size))
                machine.mem_write(0x303008 + 384, struct.pack('<II', 16, 12))
                machine.mem_write(0x303008 + 524, struct.pack('<I', 2))
                bits = bytearray(24)
                for x, y in obstacles:
                    bits[y * 2 + x // 8] |= 1 << (x % 8)
                machine.mem_write(0x303008 + 1536, bytes(bits))
                machine.reg_write(UC_X86_REG_ESP, 0x208000)
                machine.emu_start(0x300000, 0x306000, count=10000)
                self.assertEqual(machine.reg_read(UC_X86_REG_EAX), int(expected is not None))
                if expected is not None:
                    self.assertEqual((machine.reg_read(UC_X86_REG_ESI), machine.reg_read(UC_X86_REG_EDI)), expected)
                self.assertEqual(bytes(machine.mem_read(0x303008 + 1536, 24)), bytes(bits))

    @unittest.skipIf(keystone is None, 'Optional keystone assembler is not installed')
    def test_native_outline_tracks_full_hovered_square_and_preserves_stock_frame(self):
        source = preview_source()
        hovered = 'int HoveredProjectionSlot() {' + source.split('int HoveredProjectionSlot() {', 1)[1].split('unsigned PublicTooltipVariants(', 1)[0]
        outline = 'void __stdcall ApplyProjectionOutline(' + source.split('void __stdcall ApplyProjectionOutline(', 1)[1].split('__declspec(naked) void ProjectionOutlineHook()', 1)[0]
        driver = r'''
#include <windows.h>
#include <cstdint>
#include <cstring>
#include <cassert>
void* g_placementOwner=reinterpret_cast<void*>(0x205000);
uint32_t g_hoverX=0,g_hoverY=0;
int g_cell[14]{12,3,13,6};
unsigned char g_outputStorage[4104]{};
unsigned rangeCalls=0,rangeSlot=99,glowCalls=0,detailsCalls=0;
uint32_t* rangeHighlight=nullptr;
void UpdateProjectionGlows() { ++glowCalls; }
void ProcessProjectionDetails() { ++detailsCalls; }
void UpdateProjectionRange(unsigned slot,uint32_t* highlight) { ++rangeCalls;rangeSlot=slot;rangeHighlight=highlight; }
''' + hovered + outline + r'''
int main() {
    struct Case { uint32_t x,y,hovered,count; bool owned; int bounds[4]; int slot; };
    const Case cases[]={
        {12,3,65,2,true,{11,3,12,2},0},
        {12,5,65,2,true,{11,6,13,4},1}, {13,5,65,2,true,{11,6,13,4},1},
        {12,6,65,2,true,{11,6,13,4},1}, {13,6,65,2,true,{11,6,13,4},1},
        {11,5,65,2,true,{91,92,93,94},-1}, {14,6,65,2,true,{91,92,93,94},-1},
        {12,5,0,2,true,{91,92,93,94},-1}, {12,5,65,0,true,{91,92,93,94},-1},
        {12,5,65,2,false,{91,92,93,94},-1}
    };
    for(const auto& item:cases) {
        g_hoverX=item.x;g_hoverY=item.y;
        *reinterpret_cast<uint32_t*>(g_outputStorage+8+496)=item.count;
        *reinterpret_cast<uint32_t*>(g_outputStorage+8+504)=item.hovered;
        *reinterpret_cast<uint32_t*>(g_outputStorage+8+600)=1;
        *reinterpret_cast<uint32_t*>(g_outputStorage+8+604)=2;
        *reinterpret_cast<uint32_t*>(g_outputStorage+8+640)=65;
        *reinterpret_cast<uint32_t*>(g_outputStorage+8+644)=65;
        int frame[12];for(auto& value:frame)value=0x55aa55aa;
        int* bounds=frame+4;bounds[0]=91;bounds[1]=92;bounds[2]=93;bounds[3]=94;
        uint32_t highlight[4]{};rangeCalls=glowCalls=detailsCalls=0;
        ApplyProjectionOutline(item.owned ? 0x205000 : 0x206000,highlight,bounds,true);
        assert(memcmp(bounds,item.bounds,sizeof(item.bounds))==0);
        for(int index=0;index<4;++index)assert(frame[index]==0x55aa55aa && frame[index+8]==0x55aa55aa);
        assert(rangeCalls==(item.slot>=0 ? 1u : 0u));
        assert(glowCalls==(item.owned ? 1u : 0u) && detailsCalls==glowCalls);
        if(rangeCalls)assert(rangeSlot==static_cast<unsigned>(item.slot) && rangeHighlight==highlight);
    }
}
'''
        with tempfile.TemporaryDirectory(prefix='workshop-outline-') as directory:
            folder=Path(directory);(folder/'outline.cpp').write_text(driver,encoding='utf-8')
            (folder/'build.cmd').write_text(f'@call "{vcvarsall()}" x86 >nul\n@if errorlevel 1 exit /b 1\n@cl /nologo /EHsc /O2 /std:c++20 /Fe:outline.exe outline.cpp\n',encoding='utf-8')
            built=subprocess.run(['cmd','/d','/c',str(folder/'build.cmd')],cwd=folder,capture_output=True)
            self.assertEqual(built.returncode,0,built.stdout.decode(errors='replace')+built.stderr.decode(errors='replace'))
            checked=subprocess.run([str(folder/'outline.exe')],capture_output=True)
            self.assertEqual(checked.returncode,0,checked.stderr.decode(errors='replace'))
        assembly=source.split('void ProjectionOutlineHook()',1)[1].split('__asm {',1)[1].split('}',1)[0]
        assembly='\n'.join(line.split('//',1)[0] for line in assembly.splitlines()).replace('ApplyProjectionOutline','0x309000')
        code=bytes(keystone.Ks(keystone.KS_ARCH_X86,keystone.KS_MODE_32).asm(assembly,addr=0x300000)[0])
        machine=Uc(UC_ARCH_X86,UC_MODE_32);machine.mem_map(0x200000,65536);machine.mem_map(0x300000,65536)
        machine.mem_write(0x300000,code)
        boundary='mov eax,[esp+4]; mov [0x309100],eax; mov eax,[esp+8]; mov [0x309104],eax; mov eax,[esp+12]; mov [0x309108],eax; mov eax,[esp+16]; mov [0x30910c],eax; xor eax,eax; xor ecx,ecx; xor edx,edx; ret 16'
        machine.mem_write(0x309000,bytes(keystone.Ks(keystone.KS_ARCH_X86,keystone.KS_MODE_32).asm(boundary,addr=0x309000)[0]))
        machine.mem_write(0x20503c,struct.pack('<2I',0x123,0x456))
        machine.reg_write(UC_X86_REG_ESP,0x208000);machine.reg_write(UC_X86_REG_ESI,0x205000)
        machine.reg_write(UC_X86_REG_EBX,0x987);machine.reg_write(UC_X86_REG_EFLAGS,0x246)
        machine.emu_start(0x300000,0x57898c,count=1000)
        self.assertEqual(struct.unpack('<4I',machine.mem_read(0x309100,16)),(0x205000,0x208040,0x208090,1))
        self.assertEqual(machine.reg_read(UC_X86_REG_ESP),0x208000)
        self.assertEqual(machine.reg_read(UC_X86_REG_ESI),0x205000)
        self.assertEqual(machine.reg_read(UC_X86_REG_EBX),0x987)
        self.assertEqual(machine.reg_read(UC_X86_REG_EFLAGS),0x246)
        self.assertEqual(machine.reg_read(UC_X86_REG_EAX),0x123)
        self.assertEqual(machine.reg_read(UC_X86_REG_EDX),0x456)

        # Check the renderer ABI too: the opposite-facing angle must not depend
        # on the address of the native model root (which changes each launch).
        renderer = source.split('void __stdcall RenderPlacementModels(', 1)[1]
        assembly = renderer.split('        mov eax, dword ptr [esp + 44]', 1)[1].split('        mov dword ptr [g_root], edi', 1)[0]
        assembly = 'mov eax, dword ptr [esp + 44]\n' + assembly
        assembly = '\n'.join(line.split('//', 1)[0] for line in assembly.splitlines())
        for symbol, address in {'g_rendererRootArgument': '0x303000',
                                'g_rendererFactoryArgument': '0x303004',
                                'g_outputStorage': '0x304000'}.items():
            assembly = assembly.replace(symbol, address)
        code = bytes(keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32).asm(assembly, addr=0x300000)[0])
        for address in (0x12340000, 0x56780000):
            for angle in (0, 90, 180, 270):
                machine = Uc(UC_ARCH_X86, UC_MODE_32)
                machine.mem_map(0x200000, 65536)
                machine.mem_map(0x300000, 65536)
                machine.mem_write(0x300000, code)
                machine.reg_write(UC_X86_REG_ESP, 0x208000)
                machine.mem_write(0x20802c, struct.pack('<3I', address, 0x9876, angle))
                machine.emu_start(0x300000, 0x300000 + len(code), count=100)
                self.assertEqual(struct.unpack('<I', machine.mem_read(0x304008 + 760, 4))[0], angle + 180)
                self.assertEqual(struct.unpack('<2I', machine.mem_read(0x303000, 8)), (address, 0x9876))
