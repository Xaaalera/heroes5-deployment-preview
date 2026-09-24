"""Optional x86-emulator check; never starts or attaches to the game."""
import importlib.util
import hashlib
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
                                  UC_X86_REG_EBP, UC_X86_REG_ESP, UC_X86_REG_EFLAGS)
except ImportError:
    Uc = None

try:
    import keystone
except ImportError:
    keystone = None

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tests'))
from preview_support import MOD_ROOT, DEVKIT, WORKSPACE, BUILD, vcvarsall
sys.path.insert(0, str(DEVKIT / 'scripts'))
SPEC = importlib.util.spec_from_file_location('native_probe', DEVKIT / 'scripts/native-probe.py')
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)



@unittest.skipIf(Uc is None, 'Unicorn is required for emulation checks')
class NativeTests(unittest.TestCase):
    def test_projection_cards_range_and_details_use_public_selected_grade(self):
        # Setup: exercise production selection/provider callbacks with a fake
        # engine definition registry and native card provider at their ABI seam.
        source = (MOD_ROOT / 'src/preview_plugin.cpp').read_text()
        implementation = 'int HoveredProjectionSlot() {' + source.split('int HoveredProjectionSlot() {', 1)[1].split(
            '// The deployment title is', 1)[0]
        implementation += 'int ComputeProjectionRange(' + source.split('int ComputeProjectionRange(', 1)[1].split(
            '__declspec(naked) void ProjectionOutlineHook()', 1)[0]
        implementation += 'bool __fastcall ProjectionDetailsCanRotate(' + source.split('bool __fastcall ProjectionDetailsCanRotate(', 1)[1].split(
            'int HoveredProjectionSlot() {', 1)[0]
        implementation += 'LRESULT CALLBACK ProjectionWindowProc(' + source.split('LRESULT CALLBACK ProjectionWindowProc(', 1)[1].split(
            'BOOL CALLBACK FindProjectionWindow(', 1)[0]
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
    *reinterpret_cast<uint32_t*>(output+496)=0;
    ProjectionWindowProc(nullptr,WM_LBUTTONDBLCLK,0,point);ProcessProjectionDetails();CHECK(queuedDetails==1);
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
        source = (MOD_ROOT / 'src/preview_plugin.cpp').read_text()
        implementation = 'struct ProjectionGlow {' + source.split('struct ProjectionGlow {', 1)[1].split(
            '// Synthetic quantity=1', 1)[0]
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
        source = (MOD_ROOT / 'src/preview_plugin.cpp').read_text()
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

    def test_compiled_projection_snapshot_keeps_all_slots_and_buffer_guards(self):
        try:
            import pefile
            import capstone
            from capstone.x86_const import X86_OP_MEM, X86_REG_EDI, X86_REG_EBX, X86_REG_EAX
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
        count_address = next(instruction.operands[1].mem.disp for instruction in absolute_loads
                             if instruction.operands[0].reg == X86_REG_EDI)
        generation_address = next(instruction.operands[1].mem.disp for instruction in absolute_loads
                                  if instruction.operands[0].reg == X86_REG_EBX)
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
                    machine.mem_write(cell_address + index * 8, struct.pack('<2I', x, y))
                machine.mem_write(0x307ff0, b'\xa5' * 168)
                machine.mem_write(0x218000, struct.pack('<2I', 0x30f000, 0x308000))
                machine.reg_write(UC_X86_REG_ESP, 0x218000)
                machine.emu_start(base + offset, 0x30f000, count=10000)
                self.assertEqual(machine.reg_read(UC_X86_REG_ESP), 0x218008)
                self.assertEqual(bytes(machine.mem_read(0x307ff0, 16)), b'\xa5' * 16)
                self.assertEqual(bytes(machine.mem_read(0x308088, 16)), b'\xa5' * 16)
                if count > 7:
                    self.assertEqual(machine.reg_read(UC_X86_REG_EAX), 0)
                    self.assertEqual(bytes(machine.mem_read(0x308000, 136)), b'\xa5' * 136)
                else:
                    self.assertEqual(machine.reg_read(UC_X86_REG_EAX), 1)
                    expected = [1, 7, count, 123, 32, 32]
                    expected += [value for slot in slots[:count] for value in slot]
                    expected += [0] * (28 - count * 4)
                    self.assertEqual(struct.unpack('<34I', machine.mem_read(0x308000, 136)), tuple(expected))
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
        for failure in failures:
            with self.subTest(failure=failure):
                machine = Uc(UC_ARCH_X86, UC_MODE_32)
                machine.mem_map(base, executable.OPTIONAL_HEADER.SizeOfImage)
                machine.mem_write(base, executable.get_memory_mapped_image())
                machine.mem_map(0x400000, 0x200000)
                machine.mem_map(0xa4e000, 4096)
                machine.mem_map(0x200000, 0x20000)
                machine.mem_map(0x300000, 0x10000)
                for address, original in originals.items():
                    machine.mem_write(address, bytes.fromhex(original))
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
                if failure is None:
                    self.assertEqual(len(allocated), 2)
                    self.assertEqual(freed, [])
                    self.assertTrue(all(protections[address] == 0x20 for address in allocated))
                else:
                    self.assertEqual(sorted(allocated), sorted(freed))
        executable.close()

    @unittest.skipIf(keystone is None, 'Optional keystone assembler is not installed')
    def test_projection_tooltip_hit_test_preserves_other_windows_and_callers(self):
        source = (MOD_ROOT / 'src/preview_plugin.cpp').read_text()
        assembly = source.split('void ProjectionTooltipHitTestHook()', 1)[1].split('__asm {', 1)[1].split('}', 1)[0]
        assembly = re.sub(r'//[^\n]*', '', assembly).replace('g_outputStorage', '0x303000')
        assembly = assembly.replace('g_fpu', '0x30a000').replace('AttachProjectionTooltipProvider', '0x30b000')
        assembly = assembly.replace('g_detailsHitTest', '0x30c000').replace('g_tooltipController', '0x30c004')
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
        source = (MOD_ROOT / 'src/preview_plugin.cpp').read_text()
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
        source = (MOD_ROOT / 'src/preview_plugin.cpp').read_text()
        assembly = source.split('void ProjectionOutlineHook()', 1)[1].split('__asm {', 1)[1].split('}', 1)[0]
        assembly = '\n'.join(line.split('//', 1)[0] for line in assembly.splitlines())
        for symbol, address in {'g_placementOwner': '0x303000', 'g_hoverX': '0x303010',
                                'g_hoverY': '0x303014', 'g_cell': '0x303200', 'g_outputStorage': '0x304000',
                                'g_fpu': '0x305000', 'UpdateProjectionRange': '0x306000',
                                'UpdateProjectionGlows': '0x307000', 'ProcessProjectionDetails': '0x308000'}.items():
            assembly = assembly.replace(symbol, address)
        code = bytes(keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32).asm(assembly, addr=0x300000)[0])
        unchanged = (91, 92, 93, 94)
        cases = [(12, 3, 65, 2, True, (11, 3, 12, 2))]
        cases += [(x, y, 65, 2, True, (11, 6, 13, 4)) for x in (12, 13) for y in (5, 6)]
        cases += [(11, 5, 65, 2, True, unchanged), (14, 6, 65, 2, True, unchanged),
                  (12, 5, 0, 2, True, unchanged), (12, 5, 65, 0, True, unchanged),
                  (12, 5, 65, 2, False, unchanged)]
        for x, y, hovered, count, same_owner, expected in cases:
            with self.subTest(cell=(x, y), hovered=hovered, count=count, same_owner=same_owner):
                machine = Uc(UC_ARCH_X86, UC_MODE_32)
                machine.mem_map(0x200000, 65536)
                machine.mem_map(0x300000, 65536)
                machine.mem_write(0x300000, code)
                # Native bridge boundary: record its ABI independently of the
                # pure path algorithm below; live tests cover allocator/rendering.
                bridge = bytes(keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32).asm(
                    'mov eax, [esp+4]; mov [0x306100], eax; mov eax, [esp+8]; mov [0x306104], eax; '
                    'inc dword ptr [0x306108]; xor eax, eax; xor ecx, ecx; xor edx, edx; ret 8', addr=0x306000)[0])
                machine.mem_write(0x306000, bridge)
                machine.mem_write(0x307000, b'\xc3')
                machine.mem_write(0x308000, b'\xc3')
                machine.mem_write(0x303000, struct.pack('<I', 0x205000 if same_owner else 0x206000))
                machine.mem_write(0x303010, struct.pack('<II', x, y))
                machine.mem_write(0x303200, struct.pack('<4I', 12, 3, 13, 6))
                machine.mem_write(0x304008 + 496, struct.pack('<I', count))
                machine.mem_write(0x304008 + 504, struct.pack('<I', hovered))
                machine.mem_write(0x304008 + 600, struct.pack('<2I', 1, 2))
                machine.mem_write(0x304008 + 640, struct.pack('<2I', 65, 65))
                machine.mem_write(0x20503c, struct.pack('<2I', 0x123, 0x456))
                machine.mem_write(0x208080, b'\xa5' * 48)
                machine.mem_write(0x208090, struct.pack('<4I', *unchanged))
                machine.reg_write(UC_X86_REG_ESP, 0x208000)
                machine.reg_write(UC_X86_REG_ESI, 0x205000)
                machine.reg_write(UC_X86_REG_EBX, 0x987)
                machine.reg_write(UC_X86_REG_EFLAGS, 0x246)
                machine.emu_start(0x300000, 0x57898c, count=1000)
                self.assertEqual(struct.unpack('<4I', machine.mem_read(0x208090, 16)), expected)
                self.assertEqual(bytes(machine.mem_read(0x208080, 16)), b'\xa5' * 16)
                self.assertEqual(bytes(machine.mem_read(0x2080a0, 16)), b'\xa5' * 16)
                self.assertEqual(machine.reg_read(UC_X86_REG_ESP), 0x208000)
                self.assertEqual(machine.reg_read(UC_X86_REG_ESI), 0x205000)
                self.assertEqual(machine.reg_read(UC_X86_REG_EBX), 0x987)
                self.assertEqual(machine.reg_read(UC_X86_REG_EFLAGS), 0x246)
                self.assertEqual(machine.reg_read(UC_X86_REG_EAX), 0x123)
                self.assertEqual(machine.reg_read(UC_X86_REG_EDX), 0x456)
                slot, frame, calls = struct.unpack('<3I', machine.mem_read(0x306100, 12))
                self.assertEqual(calls, int(expected != unchanged))
                if calls:
                    self.assertEqual(frame, 0x208040)
                    self.assertEqual(slot, 0 if (x, y) == (12, 3) else 1)

        # Check the renderer ABI too: the opposite-facing angle must not depend
        # on the address of the native model root (which changes each launch).
        assembly = source.split('        mov eax, dword ptr [esp + 56]', 1)[1].split('        mov dword ptr [g_root], edi', 1)[0]
        assembly = 'mov eax, dword ptr [esp + 56]\n' + assembly
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
                machine.mem_write(0x208038, struct.pack('<5I', address, 0, angle, 2, 0x9876))
                machine.emu_start(0x300000, 0x300000 + len(code), count=100)
                self.assertEqual(struct.unpack('<I', machine.mem_read(0x304008 + 760, 4))[0], angle + 180)
                self.assertEqual(struct.unpack('<2I', machine.mem_read(0x303000, 8)), (address, 0x9876))
