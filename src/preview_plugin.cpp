#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <cstdint>
#include <cstring>
#include <limits>

namespace {

constexpr uintptr_t kRendererEntry = 0x577010;
constexpr uintptr_t kRendererResume = 0x577016;
constexpr uintptr_t kAttackEntry = 0x433440;
constexpr uintptr_t kAttackResume = 0x433445;
constexpr uintptr_t kHoverEntry = 0x5767a0;
constexpr uintptr_t kHoverResume = 0x5767a6;
constexpr uintptr_t kPlacementConstructorEntry = 0x577e70;
constexpr uintptr_t kPlacementConstructorResume = 0x577e76;
constexpr uintptr_t kPlacementDestructorEntry = 0x579370;
constexpr uintptr_t kPlacementDestructorResume = 0x579379;
constexpr uintptr_t kDeploymentEndEntry = 0x541fa0;
constexpr uintptr_t kDeploymentEndResume = 0x541fa5;
constexpr uintptr_t kCreatureDefinition = 0x89fbf0;
constexpr uintptr_t kModelFactory = 0x4bdad0;
constexpr uintptr_t kOpacity = 0x55b3b0;
constexpr uintptr_t kFade = 0x55b370;

volatile LONG g_renderCalls = 0;
volatile LONG g_attackGeneration = 0;
volatile LONG g_renderedGeneration = 0;
volatile LONG g_placementGeneration = 0;
volatile LONG g_publicCount = 0;
uint32_t g_publicTypes[7]{};
uint32_t g_orderedPublicTypes[7]{};
uint32_t g_candidateIdentity = 0;
uint32_t g_definitionMaximum = 0;
void* g_originalRenderer = nullptr;
void* g_originalTooltipSource = nullptr;
void* g_placementOwner = nullptr;
void* g_root = nullptr;
void* g_grid = nullptr;
void* g_creatureDefinition = nullptr;
void* g_modelDefinition = nullptr;
uint32_t g_rendererRootArgument = 0;
uint32_t g_rendererFactoryArgument = 0;
uint32_t g_hoverX = 31;
uint32_t g_hoverY = 31;
__declspec(align(16)) unsigned char g_outputStorage[4104]{};
__declspec(align(8)) int g_position[28]{};
int g_cell[14] = {13, 5, 12, 6, 12, 4, 12, 8, 11, 3, 11, 9, 10, 5};
__declspec(align(16)) unsigned char g_fpu[512]{};
unsigned g_tooltipChoice[7]{};
int g_tooltipClickSlot = -1;
uint32_t* g_tooltipController = nullptr;
void ResetProjectionTooltipChoices();
unsigned PublicTooltipVariants(uint32_t base, uint32_t* variants);
int HoveredProjectionSlot();
void ProcessProjectionDetails();
uint32_t* g_projectionScreen = nullptr;
WNDPROC g_originalGameWindowProc = nullptr;
HWND g_projectionWindow = nullptr;
int g_detailsSlot = -1;
LONG g_detailsGeneration = -1;
int g_detailsPoint[2]{};
bool g_detailsHitTest = false;
uint32_t* g_detailsRotator = nullptr;
unsigned g_detailsProjectionSlot = 7;
LONG g_detailsRotatorGeneration = -1;

LRESULT CALLBACK ProjectionWindowProc(HWND window, UINT message, WPARAM wparam, LPARAM lparam) {
    if ((message == WM_LBUTTONDBLCLK || g_detailsSlot >= 0) && g_projectionScreen != nullptr) {
        if (!reinterpret_cast<bool (__thiscall*)(void*)>(0x669e10)(g_projectionScreen)) {
            g_detailsSlot = -1;
        } else if (message == WM_LBUTTONDBLCLK) {
            const int slot = HoveredProjectionSlot();
            if (slot >= 0) {
                g_detailsSlot = slot;
                g_detailsGeneration = g_placementGeneration;
                g_detailsPoint[0] = static_cast<short>(LOWORD(lparam));
                g_detailsPoint[1] = static_cast<short>(HIWORD(lparam));
            }
        }
    }
    return CallWindowProcW(g_originalGameWindowProc, window, message, wparam, lparam);
}

BOOL CALLBACK FindProjectionWindow(HWND window, LPARAM) {
    DWORD process = 0;
    GetWindowThreadProcessId(window, &process);
    if (process != GetCurrentProcessId() || !IsWindowVisible(window) || GetWindow(window, GW_OWNER) != nullptr) return TRUE;
    SetLastError(0);
    const auto original = SetWindowLongPtrW(window, GWLP_WNDPROC, reinterpret_cast<LONG_PTR>(ProjectionWindowProc));
    if (original == 0) return TRUE;
    g_originalGameWindowProc = reinterpret_cast<WNDPROC>(original);
    g_projectionWindow = window;
    return FALSE;
}

void __stdcall AttachProjectionInput(uint32_t* screen) {
    if (screen == nullptr || *screen != 0xe1da84
        || screen[0x488 / 4] != reinterpret_cast<uint32_t>(g_placementOwner)) return;
    g_projectionScreen = screen;
    if (g_projectionWindow == nullptr) EnumWindows(FindProjectionWindow, 0);
}

unsigned g_glowPreset = 3;

void UpdateProjectionGlowPreset() {
    static bool keyWasDown = false;
    static HWND titledWindow = nullptr;
    static wchar_t originalTitle[240]{};
    static unsigned titledPreset = 5;
    const HWND foreground = GetForegroundWindow();
    DWORD processId = 0;
    if (foreground == nullptr || GetWindowThreadProcessId(foreground, &processId) == 0
        || processId != GetCurrentProcessId()) {
        keyWasDown = false;
        return;
    }
    const bool keyDown = (GetAsyncKeyState(VK_F9) & 0x8000) != 0;
    if (keyDown && !keyWasDown) g_glowPreset = (g_glowPreset + 1) % 5;
    keyWasDown = keyDown;
    if (foreground != titledWindow) {
        const int length = GetWindowTextW(foreground, originalTitle, 240);
        if (length == 0) return;
        // Preserve the game's localized title. Only append a numeric preset id.
        if (length >= 6 && originalTitle[length - 6] == L' ' && originalTitle[length - 5] == L'['
            && originalTitle[length - 3] == L'/' && originalTitle[length - 2] == L'5'
            && originalTitle[length - 1] == L']') originalTitle[length - 6] = 0;
        titledWindow = foreground;
        titledPreset = 5;
    }
    if (titledPreset != g_glowPreset) {
        wchar_t title[256]{};
        wsprintfW(title, L"%s [%u/5]", originalTitle, g_glowPreset + 1);
        SetWindowTextW(foreground, title);
        titledPreset = g_glowPreset;
    }
}

struct ProjectionGlow {
    uint32_t* node = nullptr;
    uint32_t* color = nullptr;
    unsigned preset = 5;
};
ProjectionGlow g_glows[7]{};
constexpr float kGlowPresets[5][4] = {
    {0.030f, 0.022f, 0.009f, 0.06f}, // Selected warm gold: baseline.
    {0.045f, 0.033f, 0.0135f, 0.09f}, // 1.5x.
    {0.060f, 0.044f, 0.018f, 0.12f}, // 2x.
    {0.090f, 0.066f, 0.027f, 0.18f}, // 3x.
    {0.120f, 0.088f, 0.036f, 0.24f}, // 4x.
};

void ReleaseProjectionGlow(unsigned index) {
    auto& glow = g_glows[index];
    uint32_t* references[] = {glow.node, glow.color};
    glow = {};
    for (auto* reference : references) {
        if (reference != nullptr && ((--reference[1]) & 0xfffff) == 0) {
            reinterpret_cast<void (__thiscall*)(void*, uint32_t)>(0x8c61d0)(reference, 0xfffff);
        }
    }
}

void ReleaseProjectionGlows() {
    for (unsigned index = 0; index < 7; ++index) ReleaseProjectionGlow(index);
}

void UpdateProjectionGlows() {
    const auto* output = g_outputStorage + 8;
    const auto count = *reinterpret_cast<const uint32_t*>(output + 496);
    if (count == 0 || count > 7 || g_rendererFactoryArgument == 0) return;
    auto* view = reinterpret_cast<uint32_t*>(g_rendererFactoryArgument);
    auto* methods = reinterpret_cast<const uintptr_t*>(*view);
    // This pinned CGameView method binds post-processing to the supplied parts.
    // Do not invoke an unrelated factory or modify a shared creature resource.
    if (methods[0x7c / 4] != 0xb75ed0) return;
    UpdateProjectionGlowPreset();
    if (g_glowPreset >= 5) return;
    for (unsigned index = 0; index < count; ++index) {
        auto& glow = g_glows[index];
        if (glow.node == nullptr) {
            auto* fader = *reinterpret_cast<uint32_t* const*>(output + index * 32);
            if (fader == nullptr || *fader != 0xe8bfc4) continue;
            auto* renderNode = reinterpret_cast<uint32_t*>(fader[0x14 / 4]);
            if (renderNode == nullptr || *renderNode != 0xe807d8 || renderNode[3] == renderNode[4]) continue;
            const auto allocate = reinterpret_cast<uint32_t* (__cdecl*)(unsigned)>(0x878fd0);
            auto* color = allocate(0x24);
            if (color == nullptr) continue;
            // Stock CCVec4 layout, as constructed by b166b0/b18f00. One owned
            // CPtr reference plus the colorer's own reference; version starts at 2.
            memset(color, 0, 0x24);
            color[0] = 0xe309c8;
            color[1] = 1;
            color[4] = 2;
            memcpy(color + 5, kGlowPresets[g_glowPreset], sizeof(kGlowPresets[0]));
            glow.color = color;
            auto* colorer = allocate(0x14);
            if (colorer == nullptr) {
                ReleaseProjectionGlow(index);
                continue;
            }
            reinterpret_cast<void (__thiscall*)(void*, void*)>(0x6804e0)(colorer, color);
            ++colorer[2];
            auto* node = reinterpret_cast<uint32_t* (__thiscall*)(void*, const void*, void*)>(methods[0x7c / 4])(
                view, renderNode + 3, colorer);
            if (node != nullptr) {
                ++node[1];
                glow.node = node;
            }
            if (--colorer[2] == 0) reinterpret_cast<void (__thiscall*)(void*)>(0x8c6150)(colorer);
            if (node == nullptr || node[3] == node[4]) {
                ReleaseProjectionGlow(index);
                continue;
            }
        }
        if (glow.preset != g_glowPreset) {
            memcpy(glow.color + 5, kGlowPresets[g_glowPreset], sizeof(kGlowPresets[0]));
            ++glow.color[4];
            glow.preset = g_glowPreset;
        }
    }
}

// Synthetic quantity=1, no hero, no hidden army. The engine evaluates and sorts
// these local pairs; its ordinary sort also preserves the native tie behavior.
bool PreparePublicOrder() {
    struct Aggregate {
        int extra0, unused, extra2, damage;
        float attack, multiplier;
        int health;
        float defence;
        int remaining[10];
    };
    static_assert(sizeof(Aggregate) == 0x48, "Native score aggregate layout");
    struct Pair { int score; uint32_t type; };
    using Definition = const int* (__fastcall*)(uint32_t);
    using Score = int (__thiscall*)(const Aggregate*, const Aggregate*);
    using Sort = void (__fastcall*)(Pair*, Pair*, uintptr_t);
    const auto definition = reinterpret_cast<Definition>(kCreatureDefinition);
    const auto evaluate = reinterpret_cast<Score>(0xbf9b80);
    const auto sort = reinterpret_cast<Sort>(0x85a700);
    Aggregate reference{};
    const int* peasant = definition(1);
    if (!peasant || g_publicCount < 1 || g_publicCount > 7) return false;
    reference.attack = static_cast<float>(peasant[0x44 / 4]);
    unsigned destination = 0;
    for (int role = 0; role < 3; ++role) {
        Pair pairs[7]{};
        unsigned count = 0;
        for (LONG index = 0; index < g_publicCount; ++index) {
            const int* creature = definition(g_publicTypes[index]);
            if (!creature) return false;
            const int creatureRole = creature[0x4c / 4] > 0 ? 1 :
                (creature[0xdc / 4] == 2 ? 0 : 2);
            if (creatureRole != role) continue;
            Aggregate candidate{};
            candidate.damage = (creature[0x50 / 4] + creature[0x54 / 4]) / 2;
            candidate.attack = static_cast<float>(creature[0x44 / 4]);
            candidate.multiplier = 1.0f;
            candidate.health = creature[0x64 / 4];
            candidate.defence = static_cast<float>(creature[0x48 / 4]);
            pairs[count++] = {evaluate(&candidate, &reference), g_publicTypes[index]};
        }
        sort(pairs, pairs + count, 0x85a4f0);
        for (unsigned index = 0; index < count; ++index) {
            g_orderedPublicTypes[destination++] = pairs[index].type;
        }
    }
    return destination == static_cast<unsigned>(g_publicCount);
}

// Builds the same conservative, public portrait model used by the working
// diagnostic. It deliberately never follows the defender-army pointer.
__declspec(naked) void CapturePublicPortraits() {
    __asm {
        push ebp
        push ebx
        push esi
        push edi
        mov dword ptr [g_publicCount], 0
        mov dword ptr [g_publicTypes], 0
        test eax, eax
        jz capture_done
        cmp dword ptr [eax], 0xe18f7c
        jne capture_done
        sub eax, 0x158
        lea ecx, [eax + 0xc8]
        push 0
        push 0
        push 0
        mov edx, 0x4efc30
        call edx
        test eax, eax
        jz capture_done
        mov ebp, eax
        inc dword ptr [ebp + 8]
        mov esi, dword ptr [ebp + 0x50]
        mov edx, dword ptr [ebp + 0x54]
        sub edx, esi
        test edx, edx
        jz capture_single
        cmp edx, 168
        ja capture_release
        mov eax, edx
        xor edx, edx
        mov ecx, 24
        div ecx
        test edx, edx
        jnz capture_release
        mov edi, eax
        jmp capture_portrait
    capture_single:
        lea esi, [ebp + 0x1c]
        mov edi, 1
    capture_portrait:
        mov ecx, esi
        mov eax, 0x6710a0
        call eax
        test eax, eax
        jz capture_release
        mov dword ptr [g_candidateIdentity], eax
        mov eax, 0xacb380
        call eax
        cmp eax, 2
        jb capture_release
        cmp eax, 512
        ja capture_release
        mov dword ptr [g_definitionMaximum], eax
        mov ebx, 1
    capture_definition:
        cmp ebx, dword ptr [g_definitionMaximum]
        jae capture_next_portrait
        mov ecx, ebx
        mov eax, 0x89fbf0
        call eax
        test eax, eax
        jz capture_next_definition
        lea ecx, [eax + 0xf4]
        mov eax, 0x4bdad0
        call eax
        test eax, eax
        jz capture_next_definition
        mov ecx, eax
        xor edx, edx
        mov eax, 0x4bcca0
        call eax
        cmp eax, dword ptr [g_candidateIdentity]
        jne capture_next_definition
        mov eax, dword ptr [g_publicCount]
        cmp eax, 7
        jae capture_release
        mov dword ptr [g_publicTypes + eax * 4], ebx
        inc dword ptr [g_publicCount]
        jmp capture_next_portrait
    capture_next_definition:
        inc ebx
        jmp capture_definition
    capture_next_portrait:
        add esi, 24
        dec edi
        jnz capture_portrait
    capture_release:
        dec dword ptr [ebp + 8]
        jnz capture_done
        mov ecx, ebp
        mov eax, 0x8c6150
        call eax
    capture_done:
        pop edi
        pop esi
        pop ebx
        pop ebp
        ret
    }
}

__declspec(naked) void AttackHook() {
    __asm {
        pushfd
        pushad
        fxsave [g_fpu]
        call CapturePublicPortraits
        fxrstor [g_fpu]
        mov dword ptr [g_cell], 13
        mov dword ptr [g_cell + 4], 5
        mov dword ptr [g_cell + 8], 12
        mov dword ptr [g_cell + 12], 6
        mov dword ptr [g_cell + 16], 12
        mov dword ptr [g_cell + 20], 4
        mov dword ptr [g_cell + 24], 12
        mov dword ptr [g_cell + 28], 8
        mov dword ptr [g_cell + 32], 11
        mov dword ptr [g_cell + 36], 3
        mov dword ptr [g_cell + 40], 11
        mov dword ptr [g_cell + 44], 9
        mov dword ptr [g_cell + 48], 10
        mov dword ptr [g_cell + 52], 5
        inc dword ptr [g_attackGeneration]
        popad
        popfd
        push dword ptr [esp + 12]
        push dword ptr [esp + 12]
        push dword ptr [esp + 12]
        call attack_original
        ret 12
    attack_original:
        sub esp, 0x50
        push ebx
        push ebp
        push 0x433445
        ret
    }
}

// This is the stock CPlacementInfo constructor prologue.  The renderer is
// called for other UI objects as well, so a prediction may only bind to this
// freshly constructed placement frame.
__declspec(naked) void PlacementConstructorHook() {
    __asm {
        pushfd
        pushad
        fxsave [g_fpu]
        inc dword ptr [g_placementGeneration]
        mov dword ptr [g_placementOwner], ecx
        mov dword ptr [g_outputStorage + 8 + 496], 0
        mov dword ptr [g_outputStorage + 8 + 728], 0
        fxrstor [g_fpu]
        popad
        popfd
        push ebx
        xor ebx, ebx
        push esi
        mov esi, ecx
        mov eax, kPlacementConstructorResume
        jmp eax
    }
}

__declspec(naked) void ReleaseProjectionModels() {
    __asm {
        fxsave [g_fpu]
        call ReleaseProjectionGlows
        call ResetProjectionTooltipChoices
        mov ecx, dword ptr [g_outputStorage + 8 + 700]
        mov dword ptr [g_outputStorage + 8 + 700], 0
        mov dword ptr [g_outputStorage + 8 + 716], 0
        test ecx, ecx
        jz release_models
        dec dword ptr [ecx + 8]
        jnz release_models
        mov eax, 0x8c6150
        call eax
    release_models:
        mov ecx, offset g_outputStorage + 8
        mov eax, 0x576b40
        call eax
        mov ecx, offset g_outputStorage + 8 + 32
        mov eax, 0x576b40
        call eax
        mov ecx, offset g_outputStorage + 8 + 64
        mov eax, 0x576b40
        call eax
        mov ecx, offset g_outputStorage + 8 + 96
        mov eax, 0x576b40
        call eax
        mov ecx, offset g_outputStorage + 8 + 128
        mov eax, 0x576b40
        call eax
        mov ecx, offset g_outputStorage + 8 + 160
        mov eax, 0x576b40
        call eax
        mov ecx, offset g_outputStorage + 8 + 192
        mov eax, 0x576b40
        call eax
        mov dword ptr [g_outputStorage + 8 + 496], 0
        mov dword ptr [g_outputStorage + 8 + 504], 0
        mov dword ptr [g_outputStorage + 8 + 728], 0
        mov dword ptr [g_hoverX], 31
        mov dword ptr [g_hoverY], 31
        fxrstor [g_fpu]
        ret
    }
}

__declspec(naked) void PlacementDestructorHook() {
    __asm {
        pushfd
        pushad
        cmp ecx, dword ptr [g_outputStorage + 8 + 728]
        jne placement_destructor_ready
        call ReleaseProjectionModels
        mov dword ptr [g_placementOwner], 0
    placement_destructor_ready:
        popad
        popfd
        push esi
        mov esi, ecx
        mov eax, dword ptr [esi + 0x98]
        push kPlacementDestructorResume
        ret
    }
}

// This is the native transition from placement into combat.  CPlacementInfo's
// destructor is not guaranteed to run here, so it cannot own this cleanup.
__declspec(naked) void DeploymentEndHook() {
    __asm {
        pushfd
        pushad
        call ReleaseProjectionModels
        popad
        popfd
        push ecx
        push ebx
        xor ebx, ebx
        push esi
        mov eax, kDeploymentEndResume
        jmp eax
    }
}

__declspec(naked) void RendererHook() {
    __asm {
        pushfd
        pushad
        cmp dword ptr [esp + 36], 0x57788f
        jne resume
        cmp edi, dword ptr [g_placementOwner]
        jne resume
        mov eax, dword ptr [g_placementGeneration]
        cmp eax, dword ptr [g_renderedGeneration]
        je resume
        cmp dword ptr [g_publicCount], 0
        je resume
        mov ecx, offset g_outputStorage + 8
        mov eax, 0x576b40
        call eax
        mov ecx, offset g_outputStorage + 8 + 32
        mov eax, 0x576b40
        call eax
        mov ecx, offset g_outputStorage + 8 + 64
        mov eax, 0x576b40
        call eax
        mov ecx, offset g_outputStorage + 8 + 96
        mov eax, 0x576b40
        call eax
        mov ecx, offset g_outputStorage + 8 + 128
        mov eax, 0x576b40
        call eax
        mov ecx, offset g_outputStorage + 8 + 160
        mov eax, 0x576b40
        call eax
        mov ecx, offset g_outputStorage + 8 + 192
        mov eax, 0x576b40
        call eax
          mov eax, dword ptr [g_placementGeneration]
          mov dword ptr [g_renderedGeneration], eax
          mov dword ptr [g_outputStorage + 8 + 728], edi
          inc dword ptr [g_renderCalls]
        mov eax, dword ptr [esp + 56]
        mov dword ptr [g_rendererRootArgument], eax
        mov eax, dword ptr [esp + 72]
        mov dword ptr [g_rendererFactoryArgument], eax
        // Renderer argument 7 is a degree angle, not the root-model pointer.
        // Face the public defender ghosts opposite the native attacker.
        mov eax, dword ptr [esp + 64]
        add eax, 180
        mov dword ptr [g_outputStorage + 8 + 760], eax
        mov dword ptr [g_root], edi
        fxsave [g_fpu]
        mov ecx, dword ptr [edi + 0x24]
        mov eax, dword ptr [ecx]
        call dword ptr [eax]
        mov dword ptr [g_grid], eax
        mov ecx, eax
        mov eax, dword ptr [ecx]
        push offset g_outputStorage + 8 + 388
        push offset g_outputStorage + 8 + 384
        call dword ptr [eax + 0x44]
        cmp dword ptr [g_outputStorage + 8 + 384], 8
        jl restore
        cmp dword ptr [g_outputStorage + 8 + 384], 32
        jg restore
        cmp dword ptr [g_outputStorage + 8 + 388], 4
        jl restore
        cmp dword ptr [g_outputStorage + 8 + 388], 32
        jg restore
        push 0
        push 1
        push 0
        push 0
        mov ecx, dword ptr [g_grid]
        mov edx, offset g_outputStorage + 8 + 512
        mov eax, 0xb3f120
        call eax
        mov ecx, dword ptr [g_outputStorage + 8 + 524]
        imul ecx, dword ptr [g_outputStorage + 8 + 528]
        cmp ecx, 1024
        ja restore
        mov esi, dword ptr [g_outputStorage + 8 + 516]
        test esi, esi
        jz restore
        mov edi, offset g_outputStorage + 8 + 1536
        rep movsb
        mov ecx, dword ptr [g_outputStorage + 8 + 524]
        imul ecx, dword ptr [g_outputStorage + 8 + 528]
        mov esi, offset g_outputStorage + 8 + 1536
        mov edi, offset g_outputStorage + 8 + 2560
        rep movsb
        // Public shooter count determines the cyclic shelter window. No stack
        // quantities or defender combat objects participate in this pass.
        mov dword ptr [g_outputStorage + 8 + 780], 0
        xor esi, esi
    count_public_shooters:
        cmp esi, dword ptr [g_publicCount]
        jae public_shooters_counted
        mov ecx, dword ptr [g_publicTypes + esi * 4]
        mov eax, 0x89fbf0
        call eax
        test eax, eax
        jz next_public_shooter
        cmp dword ptr [eax + 0x4c], 0
        jle next_public_shooter
        inc dword ptr [g_outputStorage + 8 + 780]
    next_public_shooter:
        inc esi
        jmp count_public_shooters
    public_shooters_counted:
        call PreparePublicOrder
        test al, al
        jz restore
        mov dword ptr [g_candidateIdentity], 0
        mov dword ptr [g_definitionMaximum], 0
        mov dword ptr [g_outputStorage + 8 + 496], 0
    model_loop:
        mov esi, dword ptr [g_definitionMaximum]
        cmp esi, dword ptr [g_publicCount]
        jae restore
        mov ecx, dword ptr [g_orderedPublicTypes + esi * 4]
        mov eax, 0x89fbf0
        call eax
        test eax, eax
        jz next_model
        mov edx, dword ptr [eax + 0xdc]
        mov dword ptr [g_creatureDefinition], edx
        mov edx, dword ptr [eax + 0x4c]
        mov dword ptr [g_outputStorage + 8 + 740], edx
        mov ecx, 1
        test edx, edx
        jg role_ready
        mov ecx, 2
        cmp dword ptr [g_creatureDefinition], 2
        jne role_ready
        xor ecx, ecx
    role_ready:
        cmp ecx, dword ptr [g_candidateIdentity]
        jne next_model
        lea ecx, [eax + 0xf4]
        mov eax, 0x4bdad0
        call eax
        test eax, eax
        jz next_model
        mov dword ptr [g_modelDefinition], eax
        mov eax, dword ptr [g_definitionMaximum]
        mov eax, dword ptr [g_orderedPublicTypes + eax * 4]
        mov esi, dword ptr [g_outputStorage + 8 + 496]
        mov dword ptr [g_outputStorage + 8 + esi * 4 + 640], eax
        mov eax, dword ptr [g_creatureDefinition]
        mov dword ptr [g_outputStorage + 8 + esi * 4 + 600], eax
        cmp dword ptr [g_publicCount], 1
        jne rank_row
        // 0x857380, one assumed unsplit defender: sum of sizes = size.
        // First local row satisfies 2*r-size+3 > playable height.
        mov edi, dword ptr [g_outputStorage + 8 + 388]
        add edi, dword ptr [g_creatureDefinition]
        sub edi, 5
        sar edi, 1
        add edi, 2
    solo_next_row:
        mov eax, dword ptr [g_outputStorage + 8 + 388]
        dec eax
        cmp edi, eax
        jge rank_row
        mov esi, dword ptr [g_outputStorage + 8 + 384]
        sub esi, 3
    solo_next_column:
        call footprint_free
        test al, al
        jnz solo_cell_selected
        dec esi
        mov eax, dword ptr [g_outputStorage + 8 + 384]
        sub eax, 5
        add eax, dword ptr [g_creatureDefinition]
        cmp esi, eax
        jge solo_next_column
        inc edi
        jmp solo_next_row
    solo_cell_selected:
        lea edx, [g_cell]
        jmp cell_selected
    rank_row:
        cmp dword ptr [g_outputStorage + 8 + 740], 0
        jle rank_window_ready
        // Nival 0x857e60: first cyclic window with minimum total approach.
        // Then 0x8585c0 sorts its membership mask, including native ties.
        mov eax, dword ptr [g_outputStorage + 8 + 388]
        sub eax, 2
        cmp eax, dword ptr [g_outputStorage + 8 + 780]
        jle window_count_ready
        mov eax, dword ptr [g_outputStorage + 8 + 780]
    window_count_ready:
        mov dword ptr [g_outputStorage + 8 + 796], eax
        mov dword ptr [g_outputStorage + 8 + 784], 0
        mov dword ptr [g_outputStorage + 8 + 788], 0x7fffffff
        xor edi, edi
    window_next:
        xor ebp, ebp
        xor esi, esi
    window_row:
        lea eax, [edi + esi]
        mov edx, dword ptr [g_outputStorage + 8 + 388]
        sub edx, 2
        cmp eax, edx
        jl window_row_ready
        sub eax, edx
    window_row_ready:
        inc eax
        imul eax, dword ptr [g_outputStorage + 8 + 524]
        lea ebx, [eax + g_outputStorage + 8 + 2560]
        mov ecx, dword ptr [g_outputStorage + 8 + 384]
        sub ecx, 5
    window_lane:
        cmp ecx, 2
        jl window_lane_done
        mov eax, ecx
        shr eax, 3
        movzx edx, byte ptr [ebx + eax]
        mov eax, ecx
        and eax, 7
        bt edx, eax
        jc window_lane_done
        inc ebp
        dec ecx
        jmp window_lane
    window_lane_done:
        inc esi
        cmp esi, dword ptr [g_outputStorage + 8 + 796]
        jl window_row
        cmp ebp, dword ptr [g_outputStorage + 8 + 788]
        jge window_advance
        mov dword ptr [g_outputStorage + 8 + 788], ebp
        mov dword ptr [g_outputStorage + 8 + 784], edi
    window_advance:
        inc edi
        mov eax, dword ptr [g_outputStorage + 8 + 388]
        sub eax, 2
        cmp edi, eax
        jl window_next
    rank_window_ready:
        mov dword ptr [g_outputStorage + 8 + 744], -1
        mov dword ptr [g_outputStorage + 8 + 748], -1
        mov edi, 1
    rank_next:
        mov eax, dword ptr [g_outputStorage + 8 + 388]
        dec eax
        cmp edi, eax
        jge rank_done
        mov esi, dword ptr [g_outputStorage + 8 + 384]
        sub esi, 4
        cmp dword ptr [g_creatureDefinition], 2
        je rank_rear_anchor
        cmp dword ptr [g_outputStorage + 8 + 740], 0
        jle rank_column
    rank_rear_anchor:
        inc esi
    rank_column:
        call footprint_free
        test eax, eax
        jz rank_advance
    rank_lane:
        mov esi, dword ptr [g_outputStorage + 8 + 384]
        sub esi, 5
        xor ebp, ebp
    lane_next:
        cmp esi, 2
        jl lane_done
        mov eax, edi
        imul eax, dword ptr [g_outputStorage + 8 + 524]
        lea ebx, [eax + g_outputStorage + 8 + 2560]
        mov eax, esi
        shr eax, 3
        movzx edx, byte ptr [ebx + eax]
        mov ecx, esi
        and ecx, 7
        bt edx, ecx
        jc lane_done
        cmp dword ptr [g_creatureDefinition], 2
        jne lane_clear
        sub ebx, dword ptr [g_outputStorage + 8 + 524]
        movzx edx, byte ptr [ebx + eax]
        bt edx, ecx
        jc lane_done
    lane_clear:
        inc ebp
        dec esi
        jmp lane_next
    lane_done:
        cmp dword ptr [g_outputStorage + 8 + 740], 0
        jle rank_compare
        mov eax, edi
        dec eax
        sub eax, dword ptr [g_outputStorage + 8 + 784]
        jns shooter_window_distance
        add eax, dword ptr [g_outputStorage + 8 + 388]
        sub eax, 2
    shooter_window_distance:
        xor ebp, ebp
        cmp eax, dword ptr [g_outputStorage + 8 + 796]
        jge rank_compare
        inc ebp
    rank_compare:
        mov eax, edi
        dec eax
        xor edx, edx
        mov ecx, 5
    rank_reverse:
        shr eax, 1
        adc edx, edx
        loop rank_reverse
        cmp dword ptr [g_outputStorage + 8 + 744], -1
        je rank_save
        cmp ebp, dword ptr [g_outputStorage + 8 + 748]
        jl rank_advance
        jg rank_save
        cmp edx, dword ptr [g_outputStorage + 8 + 752]
        jle rank_advance
    rank_save:
        mov dword ptr [g_outputStorage + 8 + 744], edi
        mov dword ptr [g_outputStorage + 8 + 748], ebp
        mov dword ptr [g_outputStorage + 8 + 752], edx
    rank_advance:
        inc edi
        jmp rank_next
    rank_done:
        mov edx, dword ptr [g_outputStorage + 8 + 744]

        cmp edx, -1
        je next_model
        mov edi, edx
        mov esi, dword ptr [g_outputStorage + 8 + 384]
        sub esi, 4
        cmp dword ptr [g_creatureDefinition], 2
        je selected_rear_anchor
        cmp dword ptr [g_outputStorage + 8 + 740], 0
        jle selected_anchor_ready
    selected_rear_anchor:
        inc esi
    selected_anchor_ready:
        mov eax, dword ptr [g_outputStorage + 8 + 496]
        lea edx, [g_cell + eax * 8]
    cell_selected:
        mov dword ptr [edx], esi
        mov dword ptr [edx + 4], edi
        mov dword ptr [g_outputStorage + 8 + 736], edx
        mov esi, dword ptr [edx]
        mov edi, dword ptr [edx + 4]
        call footprint_occupy
        mov edi, dword ptr [g_outputStorage + 8 + 496]
        shl edi, 4
        mov ecx, dword ptr [g_grid]
        mov edx, dword ptr [ecx]
        mov eax, dword ptr [g_outputStorage + 8 + 736]
        push eax
        lea eax, [g_position + edi]
        push eax
        call dword ptr [edx + 0x6c]
        mov ebx, dword ptr [g_outputStorage + 8 + 496]
        shl ebx, 5
        push dword ptr [g_rendererFactoryArgument]
        push dword ptr [g_creatureDefinition]
        push dword ptr [g_outputStorage + 8 + 760]
        lea eax, [g_position + edi]
        push eax
        push dword ptr [g_rendererRootArgument]
        push dword ptr [g_modelDefinition]
        lea eax, [g_outputStorage + 8 + ebx + 16]
        push eax
        lea eax, [g_outputStorage + 8 + ebx + 12]
        push eax
        lea eax, [g_outputStorage + 8 + ebx + 8]
        push eax
        lea edx, [g_outputStorage + 8 + ebx + 4]
        lea ecx, [g_outputStorage + 8]
        add ecx, ebx
        call dword ptr [g_originalRenderer]
        mov ecx, dword ptr [g_outputStorage + 8 + ebx + 12]
        test ecx, ecx
        jz next_model
        push 0x3f800000
        mov eax, 0x55b3b0
        call eax
        mov ecx, dword ptr [g_outputStorage + 8 + ebx + 12]
        push 0x3f800000
        mov eax, 0x55b370
        call eax
        inc dword ptr [g_outputStorage + 8 + 496]
    next_model:
        inc dword ptr [g_definitionMaximum]
        mov eax, dword ptr [g_definitionMaximum]
        cmp eax, dword ptr [g_publicCount]
        jb model_loop
        inc dword ptr [g_candidateIdentity]
        cmp dword ptr [g_candidateIdentity], 3
        jae restore
        mov dword ptr [g_definitionMaximum], 0
        jmp model_loop
    footprint_free:
        push ebp
        push ebx
        push ecx
        push edx
        push esi
        push edi
        mov ebp, dword ptr [g_creatureDefinition]
        cmp ebp, 1
        jl footprint_blocked
        cmp ebp, 2
        jg footprint_blocked
        cmp edi, ebp
        jl footprint_blocked
        mov eax, dword ptr [g_outputStorage + 8 + 384]
        sub eax, 3
        cmp esi, eax
        jg footprint_blocked
        mov eax, dword ptr [g_outputStorage + 8 + 388]
        sub eax, 2
        cmp edi, eax
        jg footprint_blocked
        mov eax, esi
        sub eax, ebp
        cmp eax, 1
        jl footprint_blocked
    footprint_row:
        mov edx, dword ptr [g_creatureDefinition]
        mov ecx, esi
    footprint_column:
        mov eax, edi
        imul eax, dword ptr [g_outputStorage + 8 + 524]
        mov ebx, ecx
        shr ebx, 3
        add eax, ebx
        movzx eax, byte ptr [g_outputStorage + 8 + eax + 1536]
        mov ebx, ecx
        and ebx, 7
        bt eax, ebx
        jc footprint_blocked
        dec ecx
        dec edx
        jnz footprint_column
        dec edi
        dec ebp
        jnz footprint_row
        mov eax, 1
        jmp footprint_done
    footprint_blocked:
        xor eax, eax
    footprint_done:
        pop edi
        pop esi
        pop edx
        pop ecx
        pop ebx
        pop ebp
        ret
    footprint_occupy:
        push ebp
        push ebx
        push ecx
        push edx
        push esi
        push edi
        mov ebp, dword ptr [g_creatureDefinition]
    occupy_row:
        mov edx, dword ptr [g_creatureDefinition]
        mov ecx, esi
    occupy_column:
        mov eax, edi
        imul eax, dword ptr [g_outputStorage + 8 + 524]
        mov ebx, ecx
        shr ebx, 3
        add eax, ebx
        mov ebx, ecx
        and ebx, 7
        push ecx
        mov cl, bl
        mov bl, 1
        shl bl, cl
        or byte ptr [g_outputStorage + 8 + eax + 1536], bl
        pop ecx
        dec ecx
        dec edx
        jnz occupy_column
        dec edi
        dec ebp
        jnz occupy_row
        pop edi
        pop esi
        pop edx
        pop ecx
        pop ebx
        pop ebp
        ret
    restore:
        fxrstor [g_fpu]
    resume:
        popad
        popfd
        push ebp
        mov ebp, esp
        and esp, 0xfffffff8
        mov eax, 0x577016
        jmp eax
    }
}

__declspec(naked) void HoverHook() {
    __asm {
        pushfd
        pushad
        fxsave [g_fpu]
        mov dword ptr [g_outputStorage + 8 + 508], edx
        cmp dword ptr [esp + 36], 0x54589e
        jne hover_input_ready
        push esi
        call AttachProjectionInput
    hover_input_ready:
        mov esi, dword ptr [esp + 44]
        mov dword ptr [g_outputStorage + 8 + 504], 0
        test esi, esi
        jz hover_done
        mov eax, dword ptr [esi]
        mov dword ptr [g_hoverX], eax
        mov eax, dword ptr [esi + 4]
        mov dword ptr [g_hoverY], eax
        xor ebx, ebx
    hover_next:
        cmp ebx, dword ptr [g_outputStorage + 8 + 496]
        jae hover_done
        mov edi, ebx
        shl edi, 3
        mov eax, dword ptr [g_cell + edi]
        sub eax, dword ptr [esi]
        mov ecx, dword ptr [g_outputStorage + 8 + ebx * 4 + 600]
        cmp eax, ecx
        jae hover_apply
        mov eax, dword ptr [g_cell + edi + 4]
        sub eax, dword ptr [esi + 4]
        cmp eax, ecx
        jae hover_apply
        mov eax, dword ptr [g_outputStorage + 8 + ebx * 4 + 640]
        mov dword ptr [g_outputStorage + 8 + 504], eax
        mov edx, 0x3f800000
        jmp hover_opacity
    hover_apply:
        mov edx, 0x3f800000
    hover_opacity:
        mov edi, ebx
        shl edi, 5
        mov ecx, dword ptr [g_outputStorage + 8 + edi + 12]
        test ecx, ecx
        jz hover_skip
        push edx
        mov eax, 0x55b3b0
        call eax
    hover_skip:
        inc ebx
        jmp hover_next
    hover_done:
        fxrstor [g_fpu]
        popad
        popfd
        sub esp, 0xbc
        push 0x5767a6
        ret

    }
}

// Pure public-input path calculation. Native b5f0d0 uses costs 2/3 and
// c52cc0 sets a speed*2 budget. Cells are full landing footprints, not anchors.
int ComputeProjectionRange(const unsigned char* blocked, int width, int height,
                           int startX, int startY, int size, int speed, bool flying,
                           int* cells) {
    if (blocked == nullptr || cells == nullptr || width < 8 || width > 32
        || height < 4 || height > 32 || size < 1 || size > 2 || speed < 0
        || startX < size + 1 || startX > width - 3 || startY < size || startY > height - 2) {
        return -1;
    }
    const int total = width * height;
    int distance[1024];
    unsigned char landed[1024]{};
    unsigned char visited[1024]{};
    unsigned char covered[1024]{};
    for (int index = 0; index < total; ++index) {
        distance[index] = (std::numeric_limits<int>::max)();
    }
    for (int y = size; y <= height - 2; ++y) {
        for (int x = size + 1; x <= width - 3; ++x) {
            bool free = true;
            for (int row = y - size + 1; row <= y; ++row) {
                for (int column = x - size + 1; column <= x; ++column) {
                    if (blocked[row * width + column]) free = false;
                }
            }
            landed[y * width + x] = static_cast<unsigned char>(free);
        }
    }
    const int origin = startY * width + startX;
    if (!landed[origin]) return 0;
    distance[origin] = 0;
    // A shortest simple path on this bounded grid never costs more than this.
    const int budget = speed > total * 3 ? total * 6 : speed * 2;
    for (int iteration = 0; iteration < total; ++iteration) {
        int current = -1;
        int nearest = (std::numeric_limits<int>::max)();
        for (int index = 0; index < total; ++index) {
            if (!visited[index] && distance[index] < nearest) {
                nearest = distance[index];
                current = index;
            }
        }
        if (current < 0 || nearest > budget) break;
        visited[current] = 1;
        const int x = current % width;
        const int y = current / width;
        if (landed[current]) {
            for (int row = y - size + 1; row <= y; ++row) {
                for (int column = x - size + 1; column <= x; ++column) {
                    covered[row * width + column] = 1;
                }
            }
        }
        for (int rowDelta = -1; rowDelta <= 1; ++rowDelta) {
            for (int columnDelta = -1; columnDelta <= 1; ++columnDelta) {
                if (rowDelta == 0 && columnDelta == 0) continue;
                const int nextX = x + columnDelta;
                const int nextY = y + rowDelta;
                if (nextX < size + 1 || nextX > width - 3 || nextY < size || nextY > height - 2) continue;
                const int next = nextY * width + nextX;
                if (!flying && !landed[next]) continue;
                const int cost = nearest + ((rowDelta != 0 && columnDelta != 0) ? 3 : 2);
                if (cost < distance[next] && cost <= budget) distance[next] = cost;
            }
        }
    }
    int count = 0;
    for (int index = 0; index < total; ++index) {
        if (covered[index]) {
            cells[count * 2] = index % width;
            cells[count * 2 + 1] = index / width;
            ++count;
        }
    }
    return count;
}

// Native highlight vectors own engine-allocated storage. The caller and
// 55cb20's copied frame both use 551010 to release their respective vectors.
void __stdcall UpdateProjectionRange(unsigned slot, uint32_t* highlight) {
    const auto* output = g_outputStorage + 8;
    const int width = *reinterpret_cast<const int*>(output + 384);
    const int height = *reinterpret_cast<const int*>(output + 388);
    const int count = *reinterpret_cast<const int*>(output + 496);
    const int stride = *reinterpret_cast<const int*>(output + 524);
    if (count < 1 || count > 7 || slot >= static_cast<unsigned>(count) || width < 8 || width > 32
        || height < 4 || height > 32 || stride < (width + 7) / 8 || stride > 1024 / height) return;
    uint32_t variants[3]{};
    const auto base = *reinterpret_cast<const uint32_t*>(output + 640 + slot * 4);
    const unsigned variantCount = PublicTooltipVariants(base, variants);
    const auto type = variants[g_tooltipChoice[slot] % variantCount];
    const auto* definition = reinterpret_cast<const unsigned char* (__fastcall*)(uint32_t)>(kCreatureDefinition)(type);
    if (definition == nullptr) return;
    unsigned char blocked[1024]{};
    for (int y = 0; y < height; ++y) {
        for (int x = 0; x < width; ++x) {
            blocked[y * width + x] = (output[2560 + y * stride + x / 8] >> (x % 8)) & 1;
        }
    }
    // This existing UI vector contains the visible player's occupied cells.
    // No army pointer, hidden count or defender combat object is followed.
    const auto* occupied = reinterpret_cast<const int*>(highlight[8]);
    const auto occupiedBytes = highlight[9] - highlight[8];
    if ((highlight[8] == 0 && occupiedBytes != 0) || occupiedBytes > 8192 || occupiedBytes % 8 != 0) return;
    for (unsigned index = 0; index < occupiedBytes / 8; ++index) {
        const int x = occupied[index * 2];
        const int y = occupied[index * 2 + 1];
        if (x >= 0 && x < width && y >= 0 && y < height) blocked[y * width + x] = 1;
    }
    for (int index = 0; index < count; ++index) {
        if (index == static_cast<int>(slot)) continue;
        const int size = *reinterpret_cast<const int*>(output + 600 + index * 4);
        if (size < 1 || size > 2) return;
        for (int y = g_cell[index * 2 + 1] - size + 1; y <= g_cell[index * 2 + 1]; ++y) {
            for (int x = g_cell[index * 2] - size + 1; x <= g_cell[index * 2]; ++x) {
                if (x >= 0 && x < width && y >= 0 && y < height) blocked[y * width + x] = 1;
            }
        }
    }
    struct RangeCache {
        LONG generation = -1;
        unsigned slot = 7;
        uint32_t type = 0;
        int count = 0;
        unsigned char blocked[1024]{};
        int cells[2048]{};
    };
    static RangeCache cache;
    if (cache.generation != g_placementGeneration || cache.slot != slot || cache.type != type
        || memcmp(cache.blocked, blocked, sizeof(blocked)) != 0) {
        cache.count = ComputeProjectionRange(blocked, width, height, g_cell[slot * 2], g_cell[slot * 2 + 1],
                                            *reinterpret_cast<const int*>(definition + 0xdc),
                                            *reinterpret_cast<const int*>(definition + 0x58), definition[0x60] != 0,
                                            cache.cells);
        memcpy(cache.blocked, blocked, sizeof(blocked));
        cache.generation = g_placementGeneration;
        cache.slot = slot;
        cache.type = type;
    }
    if (cache.count < 0) return;
    const unsigned rangeBytes = static_cast<unsigned>(cache.count) * 8;
    const unsigned bytes = occupiedBytes + rangeBytes;
    auto* replacement = bytes == 0 ? nullptr : reinterpret_cast<int* (__cdecl*)(unsigned)>(0x878fd0)(bytes);
    if (bytes != 0 && replacement == nullptr) return;
    // Keep the player's existing placement highlights as well as the range.
    if (occupiedBytes != 0) memcpy(replacement, occupied, occupiedBytes);
    if (rangeBytes != 0) memcpy(reinterpret_cast<unsigned char*>(replacement) + occupiedBytes, cache.cells, rangeBytes);
    if (highlight[8] != 0) reinterpret_cast<void (__cdecl*)(void*)>(0x8790b0)(reinterpret_cast<void*>(highlight[8]));
    highlight[8] = reinterpret_cast<uint32_t>(replacement);
    highlight[9] = highlight[8] + bytes;
    highlight[10] = highlight[9];
}

__declspec(naked) void ProjectionOutlineHook() {
    __asm {
        pushfd
        pushad
        cmp esi, dword ptr [g_placementOwner]
        jne outline_done
        fxsave [g_fpu]
        call UpdateProjectionGlows
        call ProcessProjectionDetails
        fxrstor [g_fpu]
        mov edx, dword ptr [g_outputStorage + 8 + 504]
        test edx, edx
        jz outline_done
        xor ebx, ebx
    outline_find:
        cmp ebx, dword ptr [g_outputStorage + 8 + 496]
        jae outline_done
        cmp edx, dword ptr [g_outputStorage + 8 + ebx * 4 + 640]
        jne outline_next
        mov ecx, dword ptr [g_outputStorage + 8 + ebx * 4 + 600]
        mov eax, dword ptr [g_cell + ebx * 8]
        sub eax, dword ptr [g_hoverX]
        cmp eax, ecx
        jae outline_next
        mov eax, dword ptr [g_cell + ebx * 8 + 4]
        sub eax, dword ptr [g_hoverY]
        cmp eax, ecx
        jb outline_selected
    outline_next:
        inc ebx
        jmp outline_find
    outline_selected:
        // Original highlight frame starts at esp+0x40; pushfd/pushad add 36.
        fxsave [g_fpu]
        lea eax, [esp + 0x64]
        push eax
        push ebx
        call UpdateProjectionRange
        fxrstor [g_fpu]
        mov ecx, dword ptr [g_outputStorage + 8 + ebx * 4 + 600]
        mov eax, dword ptr [g_cell + ebx * 8]
        mov edx, dword ptr [g_cell + ebx * 8 + 4]
        // Stock order: x-size, y, x, y-size. pushfd/pushad add 36.
        mov dword ptr [esp + 0xbc], eax
        mov dword ptr [esp + 0xb8], edx
        sub eax, ecx
        sub edx, ecx
        mov dword ptr [esp + 0xb4], eax
        mov dword ptr [esp + 0xc0], edx
    outline_done:
        popad
        popfd
        mov edx, dword ptr [esi + 0x40]
        mov eax, dword ptr [esi + 0x3c]
        push 0x57898c
        ret
    }
}

bool __fastcall ProjectionDetailsCanRotate(uint32_t* rotator, void*) {
    const unsigned models = *reinterpret_cast<const uint32_t*>(g_outputStorage + 8 + 496);
    if (rotator != g_detailsRotator || models > 7 || g_detailsProjectionSlot >= models
        || g_detailsRotatorGeneration != g_placementGeneration) return false;
    uint32_t variants[3]{};
    return PublicTooltipVariants(*reinterpret_cast<const uint32_t*>(g_outputStorage + 8 + 640
        + g_detailsProjectionSlot * 4), variants) > 1;
}

void RotateProjectionDetails(uint32_t* rotator, bool forward) {
    if (!ProjectionDetailsCanRotate(rotator, nullptr)) return;
    uint32_t variants[3]{};
    const unsigned count = PublicTooltipVariants(*reinterpret_cast<const uint32_t*>(
        g_outputStorage + 8 + 640 + g_detailsProjectionSlot * 4), variants);
    const unsigned choice = (g_tooltipChoice[g_detailsProjectionSlot] + (forward ? 1 : count - 1)) % count;
    uint32_t publicCreature[] = {variants[choice], 1};
    auto* creature = reinterpret_cast<uint32_t* (__thiscall*)(uint32_t*)>(0x4bd550)(publicCreature);
    if (creature == nullptr) return;
    auto* reference = reinterpret_cast<uint32_t*>(reinterpret_cast<uintptr_t>(creature)
        + reinterpret_cast<const uint32_t*>(creature[1])[1] + 4);
    ++reference[2];
    auto* previous = reinterpret_cast<uint32_t*>(rotator[2]);
    rotator[2] = reinterpret_cast<uint32_t>(creature);
    g_tooltipChoice[g_detailsProjectionSlot] = choice;
    if (previous != nullptr) {
        auto* oldReference = reinterpret_cast<uint32_t*>(reinterpret_cast<uintptr_t>(previous)
            + reinterpret_cast<const uint32_t*>(previous[1])[1] + 4);
        if (--oldReference[2] == 0) reinterpret_cast<void (__thiscall*)(void*)>(0x8c6150)(oldReference);
    }
}

void __fastcall ProjectionDetailsNext(uint32_t* rotator, void*) { RotateProjectionDetails(rotator, true); }
void __fastcall ProjectionDetailsPrevious(uint32_t* rotator, void*) { RotateProjectionDetails(rotator, false); }

void AttachProjectionDetailsRotator(uint32_t* rotator, unsigned slot) {
    if (*rotator != 0xe4046c) return;
    static uint32_t methods[16]{};
    if (methods[1] == 0) {
        memcpy(methods, reinterpret_cast<const void*>(0xe40468), sizeof(methods));
        methods[1] = reinterpret_cast<uint32_t>(ProjectionDetailsNext);
        methods[2] = reinterpret_cast<uint32_t>(ProjectionDetailsPrevious);
        methods[5] = reinterpret_cast<uint32_t>(ProjectionDetailsCanRotate);
    }
    // Keep native lifetime management: its destructor owns only rotator[2].
    *rotator = reinterpret_cast<uint32_t>(methods + 1);
    g_detailsRotator = rotator;
    g_detailsProjectionSlot = slot;
    g_detailsRotatorGeneration = g_placementGeneration;
}

void ProcessProjectionDetails() {
    const int slot = g_detailsSlot;
    g_detailsSlot = -1;
    auto* screen = g_projectionScreen;
    if (slot < 0 || screen == nullptr || g_detailsGeneration != g_placementGeneration
        || HoveredProjectionSlot() != slot || *screen != 0xe1da84
        || screen[0x488 / 4] != reinterpret_cast<uint32_t>(g_placementOwner)) return;
    if (!reinterpret_cast<bool (__thiscall*)(void*)>(0x669e10)(screen)) return;
    auto* root = reinterpret_cast<uint32_t*>(screen[0xa0 / 4]);
    auto* player = reinterpret_cast<uint32_t*>(screen[0x2b4 / 4]);
    if (root == nullptr || player == nullptr || player[3] == 0 || screen[0x2a8 / 4] == 0) return;
    auto* window = reinterpret_cast<uint32_t*>(reinterpret_cast<uintptr_t>(root)
        + reinterpret_cast<const uint32_t*>(root[1])[2] + 4);
    g_detailsHitTest = true;
    const bool blocked = reinterpret_cast<bool (__thiscall*)(void*, const int*)>(
        reinterpret_cast<const uint32_t*>(window[0])[0x34 / 4])(window, g_detailsPoint);
    g_detailsHitTest = false;
    if (blocked) return;

    uint32_t variants[3]{};
    const auto base = *reinterpret_cast<const uint32_t*>(g_outputStorage + 8 + 640 + slot * 4);
    const unsigned count = PublicTooltipVariants(base, variants);
    uint32_t publicCreature[] = {variants[g_tooltipChoice[slot] % count], 1};
    auto* creature = reinterpret_cast<uint32_t* (__thiscall*)(uint32_t*)>(0x4bd550)(publicCreature);
    if (creature == nullptr) return;
    auto* creatureReference = reinterpret_cast<uint32_t*>(reinterpret_cast<uintptr_t>(creature)
        + reinterpret_cast<const uint32_t*>(creature[1])[1] + 4);
    ++creatureReference[2];
    auto* rotator = reinterpret_cast<uint32_t* (__thiscall*)(void*)>(0x789010)(creature);
    if (rotator != nullptr) {
        auto* reference = reinterpret_cast<uint32_t*>(reinterpret_cast<uintptr_t>(rotator)
            + reinterpret_cast<const uint32_t*>(rotator[1])[1] + 4);
        ++reference[2];
        AttachProjectionDetailsRotator(rotator, static_cast<unsigned>(slot));
        // Native read-only creature screen with a single synthetic creature.
        // World/player are UI context only; no hero, army or combat stack is supplied.
        using CreateScreen = void* (__fastcall*)(uint32_t, uint32_t, void*, uint32_t, uint32_t,
            uint32_t, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t, uint32_t);
        void* command = reinterpret_cast<CreateScreen>(0x789600)(screen[0x2a8 / 4], player[3], rotator,
            0, 0, 1, 0, screen[0xf4 / 4], 0, 1, 0, 0);
        if (command != nullptr) reinterpret_cast<void (__thiscall*)(void*)>(0x838c10)(command);
        else g_detailsRotator = nullptr;
        if (--reference[2] == 0) reinterpret_cast<void (__thiscall*)(void*)>(0x8c6150)(reference);
    }
    if (--creatureReference[2] == 0) reinterpret_cast<void (__thiscall*)(void*)>(0x8c6150)(creatureReference);
}

int HoveredProjectionSlot() {
    const auto* output = g_outputStorage + 8;
    const unsigned count = *reinterpret_cast<const uint32_t*>(output + 496);
    const unsigned hovered = *reinterpret_cast<const uint32_t*>(output + 504);
    if (count > 7 || hovered == 0 || g_placementOwner == nullptr) return -1;
    for (unsigned index = 0; index < count; ++index) {
        const unsigned size = *reinterpret_cast<const uint32_t*>(output + 600 + index * 4);
        if (size >= 1 && size <= 2 && hovered == *reinterpret_cast<const uint32_t*>(output + 640 + index * 4)
            && static_cast<unsigned>(g_cell[index * 2]) - g_hoverX < size
            && static_cast<unsigned>(g_cell[index * 2 + 1]) - g_hoverY < size) return static_cast<int>(index);
    }
    return -1;
}

unsigned PublicTooltipVariants(uint32_t base, uint32_t* variants) {
    variants[0] = base;
    const auto* definition = reinterpret_cast<const uint32_t* (__fastcall*)(uint32_t)>(kCreatureDefinition)(base);
    if (definition == nullptr) return 1;
    const auto begin = definition[0x104 / 4];
    const auto end = definition[0x108 / 4];
    if (begin == 0 || end < begin || end - begin > 8 || (end - begin) % 4 != 0) return 1;
    unsigned count = 1;
    for (auto* current = reinterpret_cast<const uint32_t*>(begin); current != reinterpret_cast<const uint32_t*>(end); ++current) {
        if (*current == 0 || *current == base || (count > 1 && *current == variants[1])) continue;
        variants[count++] = *current;
    }
    // Explicit upgraded public portraits and creatures without Upgrades keep
    // stock behavior. Never derive a grade from an actual hidden defender stack.
    return count;
}

void ResetProjectionTooltipChoices() {
    memset(g_tooltipChoice, 0, sizeof(g_tooltipChoice));
    g_tooltipClickSlot = -1;
    g_tooltipController = nullptr;
    g_projectionScreen = nullptr;
    g_detailsSlot = -1;
    g_detailsRotator = nullptr;
}

uint32_t ProjectionTooltipDescriptor(uint32_t creatureType);

int UncertainProjectionProvider(uint32_t* provider, uint32_t* variants, unsigned* count) {
    const int slot = HoveredProjectionSlot();
    const auto cached = *reinterpret_cast<const uint32_t*>(g_outputStorage + 8 + 700);
    if (slot < 0 || provider == nullptr || cached == 0 || provider[3] != cached || provider[0x3c / 4] != 0) return -1;
    const auto base = *reinterpret_cast<const uint32_t*>(g_outputStorage + 8 + 640 + slot * 4);
    *count = PublicTooltipVariants(base, variants);
    const auto cachedType = *reinterpret_cast<const uint32_t*>(g_outputStorage + 8 + 716);
    if (cachedType != variants[g_tooltipChoice[slot] % *count]) return -1;
    return *count > 1 ? slot : -1;
}

uint32_t __fastcall ProjectionProviderWindow(uint32_t* provider, void*) {
    uint32_t variants[3]{};
    unsigned count = 0;
    if (UncertainProjectionProvider(provider, variants, &count) >= 0) provider[4] = 1;
    return reinterpret_cast<uint32_t (__thiscall*)(void*)>(0x6b7eb0)(provider);
}

void __fastcall ProjectionProviderRightClick(uint32_t* provider, void*) {
    uint32_t variants[3]{};
    unsigned count = 0;
    const int slot = UncertainProjectionProvider(provider, variants, &count);
    if (slot >= 0 && g_tooltipController != nullptr
        && g_tooltipController[0x44 / 4] == reinterpret_cast<uint32_t>(provider)) {
        const unsigned previous = g_tooltipChoice[slot];
        // Opening a card is not a request to advance its grade.
        g_tooltipChoice[slot] = g_tooltipClickSlot == slot ? (previous + 1) % count : 0;
        const uint32_t descriptor = ProjectionTooltipDescriptor(variants[g_tooltipChoice[slot]]);
        if (descriptor != 0) {
            // Keep the controller's source cache in sync with the provider.
            // Otherwise its next update detaches and destroys the open card.
            auto& current = g_tooltipController[0x24 / 4];
            const uint32_t old = current;
            ++*reinterpret_cast<uint32_t*>(descriptor + 8);
            current = descriptor;
            if (old != 0 && --*reinterpret_cast<uint32_t*>(old + 8) == 0) {
                reinterpret_cast<void (__thiscall*)(void*)>(0x8c6150)(reinterpret_cast<void*>(old));
            }
            reinterpret_cast<void (__thiscall*)(void*, uint32_t, const uint32_t*, uint32_t)>(0x6b7880)(
                provider, descriptor, provider + 6, provider[0x2c / 4]);
            provider[4] = 0;
            g_tooltipClickSlot = slot;
        } else {
            g_tooltipChoice[slot] = previous;
        }
    }
    reinterpret_cast<void (__thiscall*)(void*)>(0x6b7790)(provider);
}

void __stdcall AttachProjectionTooltipProvider(void* controller) {
    if (controller == nullptr) return;
    g_tooltipController = static_cast<uint32_t*>(controller);
    auto* provider = *reinterpret_cast<uint32_t**>(static_cast<unsigned char*>(controller) + 0x44);
    if (provider == nullptr || *provider != 0xe34b74) return;
    // Preserve the native provider's interface identity. Both callbacks guard
    // the owned projection descriptor and delegate all other cards unchanged.
    auto* methods = reinterpret_cast<uint32_t*>(0xe34b74);
    if (methods[0] != 0x6b7eb0 || methods[1] != 0x6b7790) return;
    DWORD protection{};
    if (!VirtualProtect(methods, 8, PAGE_READWRITE, &protection)) return;
    methods[0] = reinterpret_cast<uint32_t>(ProjectionProviderWindow);
    methods[1] = reinterpret_cast<uint32_t>(ProjectionProviderRightClick);
    DWORD ignored{};
    VirtualProtect(methods, 8, protection, &ignored);
}

// The deployment title is a CWindowFadedText with a large hit rectangle.
// Ignore that decoration only for tooltip hit testing over a live projection;
// keep checking every other window, including dialogs and interactive controls.
__declspec(naked) void ProjectionTooltipHitTestHook() {
    __asm {
        mov ecx, dword ptr [edi - 0x68]
        mov eax, dword ptr [ecx + esi * 4]
        pushfd
        cmp dword ptr [esp + 16], 0x6b8aad
        je tooltip_hit_caller
        cmp byte ptr [g_detailsHitTest], 0
        je original_hit_test
        jmp tooltip_hit_windows
    tooltip_hit_caller:
        cmp dword ptr [g_outputStorage + 8 + 496], 0
        je original_hit_test
        cmp dword ptr [g_outputStorage + 8 + 504], 0
        je original_hit_test
        pushad
        fxsave [g_fpu]
        // Original esp+4 is caller ESI (CScreenTooltipController).
        mov ecx, dword ptr [esp + 40]
        push ecx
        call AttachProjectionTooltipProvider
        fxrstor [g_fpu]
        popad
    tooltip_hit_windows:
        cmp dword ptr [eax], 0xe2ff58
        je skip_decoration
        cmp dword ptr [eax], 0xe73c70
        jne original_hit_test
        // CCommonGatheringWindow's IWindow is at +0x130. Only the
        // current controller's own tooltip may pass through itself.
        push edx
        cmp byte ptr [g_detailsHitTest], 0
        je tooltip_hit_controller
        mov edx, dword ptr [g_tooltipController]
        test edx, edx
        je other_window
        jmp tooltip_hit_provider
    tooltip_hit_controller:
        mov edx, dword ptr [esp + 12]
    tooltip_hit_provider:
        mov edx, dword ptr [edx + 0x44]
        test edx, edx
        je other_window
        mov edx, dword ptr [edx + 8]
        sub edx, 0x130
        cmp eax, edx
        pop edx
        jne original_hit_test
        jmp skip_decoration
    other_window:
        pop edx
        jmp original_hit_test
    skip_decoration:
        popfd
        push 0xa4eb2c
        ret
    original_hit_test:
        popfd
        push 0xa4eb16
        ret
    }
}

uint32_t ProjectionTooltipDescriptor(uint32_t creatureType) {
    auto& cached = *reinterpret_cast<uint32_t*>(g_outputStorage + 8 + 700);
    auto& cachedType = *reinterpret_cast<uint32_t*>(g_outputStorage + 8 + 716);
    if (cachedType != creatureType) {
        if (cached != 0 && --*reinterpret_cast<uint32_t*>(cached + 8) == 0) {
            reinterpret_cast<void (__thiscall*)(void*)>(0x8c6150)(reinterpret_cast<void*>(cached));
        }
        cached = 0;
        cachedType = 0;
        uint32_t publicCreature[] = {creatureType, 1};
        auto* creature = reinterpret_cast<uint32_t* (__thiscall*)(uint32_t*)>(0x4bd550)(publicCreature);
        if (creature != nullptr) {
            auto* reference = reinterpret_cast<uint32_t*>(reinterpret_cast<uintptr_t>(creature)
                + *reinterpret_cast<uint32_t*>(creature[1] + 4) + 4);
            ++reference[2];
            cached = reinterpret_cast<uint32_t (__thiscall*)(void*, uint32_t, uint32_t, uint32_t)>(0x4bd5d0)(creature, 0, 0, 0);
            if (cached != 0) {
                ++*reinterpret_cast<uint32_t*>(cached + 8);
                cachedType = creatureType;
            }
            if (--reference[2] == 0) {
                reinterpret_cast<void (__thiscall*)(void*)>(0x8c6150)(reference);
            }
        }
    }
    return cached;
}

// Supply only public definitions, preserving stock cards outside a projection.
uint32_t* __fastcall ScreenTooltipHook(void* owner, void*, uint32_t* result, const int* cursor) {
    const int slot = HoveredProjectionSlot();
    if (slot != g_tooltipClickSlot || cursor == nullptr) g_tooltipClickSlot = -1;
    if (slot < 0 || cursor == nullptr) {
        return reinterpret_cast<uint32_t* (__thiscall*)(void*, uint32_t*, const int*)>(g_originalTooltipSource)(owner, result, cursor);
    }
    uint32_t variants[3]{};
    const auto base = *reinterpret_cast<const uint32_t*>(g_outputStorage + 8 + 640 + slot * 4);
    const unsigned count = PublicTooltipVariants(base, variants);
    const uint32_t cached = ProjectionTooltipDescriptor(variants[g_tooltipChoice[slot] % count]);
    reinterpret_cast<uint32_t* (__thiscall*)(uint32_t*)>(0x54e440)(result);
    if (cached != 0) {
        result[3] = cached;
        ++*reinterpret_cast<uint32_t*>(cached + 8);
    }
    return result;
}

bool InstallRendererHook() {
    if (g_originalRenderer != nullptr) {
        return true;
    }
    constexpr unsigned char expectedAttack[] = {0x83, 0xec, 0x50, 0x53, 0x55};
    if (memcmp(reinterpret_cast<const void*>(kAttackEntry), expectedAttack, sizeof(expectedAttack)) != 0) {
        return false;
    }
    constexpr unsigned char expected[] = {0x55, 0x8b, 0xec, 0x83, 0xe4, 0xf8};
    if (memcmp(reinterpret_cast<const void*>(kRendererEntry), expected, sizeof(expected)) != 0) {
        return false;
    }
    constexpr unsigned char expectedHover[] = {0x81, 0xec, 0xbc, 0x00, 0x00, 0x00};
    constexpr unsigned char expectedTooltip[] = {0x81, 0xec, 0x14, 0x07, 0x00, 0x00};
    constexpr unsigned char expectedOutline[] = {0x8b, 0x56, 0x40, 0x8b, 0x46, 0x3c};
    constexpr unsigned char expectedTooltipHitTest[] = {0x8b, 0x4f, 0x98, 0x8b, 0x04, 0xb1};
    if (memcmp(reinterpret_cast<const void*>(0xa4eb10), expectedTooltipHitTest, sizeof(expectedTooltipHitTest)) != 0) {
        return false;
    }
    if (memcmp(reinterpret_cast<const void*>(0x578986), expectedOutline, sizeof(expectedOutline)) != 0) {
        return false;
    }
    if (memcmp(reinterpret_cast<const void*>(0x546f40), expectedTooltip, sizeof(expectedTooltip)) != 0) {
        return false;
    }
    if (memcmp(reinterpret_cast<const void*>(kHoverEntry), expectedHover, sizeof(expectedHover)) != 0) {
        return false;
    }
    constexpr unsigned char expectedPlacementConstructor[] = {0x53, 0x33, 0xdb, 0x56, 0x8b, 0xf1};
    if (memcmp(reinterpret_cast<const void*>(kPlacementConstructorEntry), expectedPlacementConstructor,
               sizeof(expectedPlacementConstructor)) != 0) {
        return false;
    }
    constexpr unsigned char expectedPlacementDestructor[] = {0x56, 0x8b, 0xf1, 0x8b, 0x86, 0x98, 0x00, 0x00, 0x00};
    if (memcmp(reinterpret_cast<const void*>(kPlacementDestructorEntry), expectedPlacementDestructor,
               sizeof(expectedPlacementDestructor)) != 0) {
        return false;
    }
    constexpr unsigned char expectedDeploymentEnd[] = {0x51, 0x53, 0x33, 0xdb, 0x56};
    if (memcmp(reinterpret_cast<const void*>(kDeploymentEndEntry), expectedDeploymentEnd,
               sizeof(expectedDeploymentEnd)) != 0) {
        return false;
    }
    auto* trampoline = static_cast<unsigned char*>(VirtualAlloc(nullptr, 16, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE));
    if (trampoline == nullptr) {
        return false;
    }
    memcpy(trampoline, expected, sizeof(expected));
    trampoline[6] = 0xe9;
    *reinterpret_cast<int32_t*>(trampoline + 7) = static_cast<int32_t>(kRendererResume - reinterpret_cast<uintptr_t>(trampoline + 11));
    auto* tooltipTrampoline = static_cast<unsigned char*>(VirtualAlloc(nullptr, 16, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE));
    if (tooltipTrampoline == nullptr) {
        VirtualFree(trampoline, 0, MEM_RELEASE);
        return false;
    }
    memcpy(tooltipTrampoline, expectedTooltip, sizeof(expectedTooltip));
    tooltipTrampoline[6] = 0xe9;
    *reinterpret_cast<int32_t*>(tooltipTrampoline + 7) = static_cast<int32_t>(0x546f46 - reinterpret_cast<uintptr_t>(tooltipTrampoline + 11));
    DWORD ignored{};
    if (!VirtualProtect(trampoline, 16, PAGE_EXECUTE_READ, &ignored)
        || !VirtualProtect(tooltipTrampoline, 16, PAGE_EXECUTE_READ, &ignored)
        || !FlushInstructionCache(GetCurrentProcess(), trampoline, 16)
        || !FlushInstructionCache(GetCurrentProcess(), tooltipTrampoline, 16)) {
        VirtualFree(trampoline, 0, MEM_RELEASE);
        VirtualFree(tooltipTrampoline, 0, MEM_RELEASE);
        return false;
    }

    const uintptr_t entries[] = {kAttackEntry, kPlacementConstructorEntry, kPlacementDestructorEntry,
        kDeploymentEndEntry, kRendererEntry, kHoverEntry, 0x546f40, 0x578986, 0xa4eb10};
    const uintptr_t targets[] = {reinterpret_cast<uintptr_t>(AttackHook), reinterpret_cast<uintptr_t>(PlacementConstructorHook),
        reinterpret_cast<uintptr_t>(PlacementDestructorHook), reinterpret_cast<uintptr_t>(DeploymentEndHook),
        reinterpret_cast<uintptr_t>(RendererHook), reinterpret_cast<uintptr_t>(HoverHook),
        reinterpret_cast<uintptr_t>(ScreenTooltipHook), reinterpret_cast<uintptr_t>(ProjectionOutlineHook),
        reinterpret_cast<uintptr_t>(ProjectionTooltipHitTestHook)};
    const size_t sizes[] = {5, 6, 9, 5, 6, 6, 6, 6, 6};
    DWORD protections[9]{};
    size_t prepared = 0;
    // Acquire every writable region before modifying any instruction. Several
    // entries share a page, so protection changes must unwind in reverse order.
    for (; prepared < 9; ++prepared) {
        if (!VirtualProtect(reinterpret_cast<void*>(entries[prepared]), sizes[prepared],
                            PAGE_EXECUTE_READWRITE, &protections[prepared])) {
            while (prepared != 0) {
                --prepared;
                VirtualProtect(reinterpret_cast<void*>(entries[prepared]), sizes[prepared], protections[prepared], &ignored);
            }
            VirtualFree(trampoline, 0, MEM_RELEASE);
            VirtualFree(tooltipTrampoline, 0, MEM_RELEASE);
            return false;
        }
    }
    // Publish both callable originals before any hook can reach them.
    g_originalRenderer = trampoline;
    g_originalTooltipSource = tooltipTrampoline;
    for (size_t index = 0; index < 9; ++index) {
        auto* bytes = reinterpret_cast<unsigned char*>(entries[index]);
        bytes[0] = 0xe9;
        *reinterpret_cast<uint32_t*>(bytes + 1) = static_cast<uint32_t>(targets[index] - entries[index] - 5);
        memset(bytes + 5, 0x90, sizes[index] - 5);
    }
    while (prepared != 0) {
        --prepared;
        FlushInstructionCache(GetCurrentProcess(), reinterpret_cast<void*>(entries[prepared]), sizes[prepared]);
        VirtualProtect(reinterpret_cast<void*>(entries[prepared]), sizes[prepared], protections[prepared], &ignored);
    }
    return true;
}

}

extern "C" __declspec(dllexport) unsigned long WorkshopDeploymentPreviewVersion() {
    if (g_publicCount == 0) {
        return 1;
    }
    return static_cast<unsigned long>((g_publicCount << 29) | (g_outputStorage[8 + 496] << 26)
                                      | (g_outputStorage[8 + 504] << 17)
                                      | ((g_hoverX & 0x1f) << 12) | ((g_hoverY & 0x1f) << 7)
                                      | (reinterpret_cast<uintptr_t>(g_outputStorage + 8) & 0x0f)) + 1;
}

extern "C" __declspec(dllexport) unsigned long WorkshopDeploymentPreviewInstall() {
    return InstallRendererHook() ? 1 : 0;
}

#pragma comment(linker, "/EXPORT:WorkshopDeploymentPreviewProjectionTrace=_WorkshopDeploymentPreviewProjectionTrace@4")
extern "C" unsigned long __stdcall WorkshopDeploymentPreviewProjectionTrace(void* destination) {
    if (destination != nullptr) {
        // 34 uint32 words: ABI, public count, model count, generation, width, height;
        // then seven (public type, x, y, footprint size) records.
        auto* snapshot = static_cast<uint32_t*>(destination);
        const auto* modelCount = reinterpret_cast<volatile uint32_t*>(g_outputStorage + 8 + 496);
        const uint32_t count = *modelCount;
        const uint32_t generation = g_placementGeneration;
        if (count > 7) {
            return 0;
        }
        memset(snapshot, 0, 34 * sizeof(uint32_t));
        snapshot[0] = 1;
        snapshot[1] = g_publicCount;
        snapshot[2] = count;
        snapshot[3] = generation;
        snapshot[4] = *reinterpret_cast<uint32_t*>(g_outputStorage + 8 + 384);
        snapshot[5] = *reinterpret_cast<uint32_t*>(g_outputStorage + 8 + 388);
        for (uint32_t index = 0; index < count; ++index) {
            snapshot[6 + index * 4] = *reinterpret_cast<uint32_t*>(g_outputStorage + 8 + 640 + index * 4);
            snapshot[7 + index * 4] = g_cell[index * 2];
            snapshot[8 + index * 4] = g_cell[index * 2 + 1];
            snapshot[9 + index * 4] = *reinterpret_cast<uint32_t*>(g_outputStorage + 8 + 600 + index * 4);
        }
        return count == *modelCount && generation == static_cast<uint32_t>(g_placementGeneration) ? 1 : 0;
    }
    // Retain the old null-argument diagnostic for older development loaders.
    const auto count = static_cast<uint32_t>(g_outputStorage[8 + 496]);
    const auto traceCount = count > 3 ? 3 : count;
    uint32_t trace = traceCount << 30;
    for (uint32_t index = 0; index < traceCount; ++index) {
        trace |= (static_cast<uint32_t>(g_cell[index * 2]) & 0x0f) << (index * 10);
        trace |= (static_cast<uint32_t>(g_cell[index * 2 + 1]) & 0x0f) << (index * 10 + 4);
        trace |= (static_cast<uint32_t>(g_outputStorage[8 + index * 4 + 600]) & 0x03) << (index * 10 + 8);
    }
    return trace;
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
