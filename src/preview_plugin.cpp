#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include "../game-api/include/h5/hooks.hpp"
#include <cstdint>
#include <cstring>
#include <limits>

namespace {

constexpr uintptr_t kRendererEntry = h5::hooks::PlacementRenderer.address;
constexpr uintptr_t kRendererResume = h5::hooks::PlacementRenderer.Resume();
constexpr uintptr_t kAttackEntry = h5::hooks::AdventureAttack.address;
constexpr uintptr_t kAttackResume = h5::hooks::AdventureAttack.Resume();
constexpr uintptr_t kScriptedSourceEntry = 0x5d434c;
constexpr uintptr_t kScriptedSourceResume = 0x5d4353;
constexpr uintptr_t kHoverEntry = h5::hooks::PlacementHover.address;
constexpr uintptr_t kHoverResume = h5::hooks::PlacementHover.Resume();
constexpr uintptr_t kPlacementConstructorEntry = 0x577e70;
constexpr uintptr_t kPlacementConstructorResume = 0x577e76;
constexpr uintptr_t kPlacementDestructorEntry = 0x579370;
constexpr uintptr_t kPlacementDestructorResume = 0x579379;
constexpr uintptr_t kDeploymentEndEntry = 0x541fa0;
constexpr uintptr_t kDeploymentEndResume = 0x541fa5;
constexpr uintptr_t kCreatureDefinition = 0x89fbf0;
constexpr uintptr_t kModelFactory = 0x4bdad0;
constexpr uintptr_t kActorInputEntry = 0xbfbb08;
constexpr uintptr_t kActorInputResume = 0xbfbb0f;
constexpr uintptr_t kHeroCorrectionEntry = 0xbfc12f;
constexpr uintptr_t kHeroCorrectionResume = 0xbfc135;
constexpr uintptr_t kAuxiliaryPowerEntry = 0xbfa4a5;
constexpr uintptr_t kAuxiliaryPowerResume = 0xbfa4aa;
constexpr uintptr_t kSourceStrengthEntry = 0x4e9c4d;
constexpr uintptr_t kSourceStrengthResume = 0x4e9c54;
constexpr uintptr_t kSplitSeedEntry = 0x855451;
constexpr uintptr_t kSplitSeedResume = 0x855457;
constexpr uintptr_t kOpacity = 0x55b3b0;
constexpr uintptr_t kFade = 0x55b370;

volatile LONG g_renderCalls = 0;
volatile LONG g_attackGeneration = 0;
volatile LONG g_renderedGeneration = 0;
volatile LONG g_placementGeneration = 0;
volatile LONG g_publicCount = 0;
uint32_t g_publicTypes[7]{};
uint32_t g_orderedPublicTypes[7]{};
uint32_t g_publicBands[7]{};
bool g_superadminEnabled = false;
bool g_useSpreadRows = false;
uint32_t g_estimatedSpreadDenominator = 0;
int32_t g_knownHeroAttack = -1;
bool g_knownHeroBattleFrenzy = false;
bool g_spreadFallback = false;
uint32_t g_superadminSourceTypes[7]{};
uint32_t g_superadminSourceCounts[7]{};
uint32_t g_superadminSourcePointers[7]{};
uint32_t g_superadminSourceKind = 0;
bool g_superadminSourceModifiersKnown = false;
int32_t g_superadminSourceSpeed[7]{};
uint32_t g_superadminSourceFlying[7]{};
uint32_t g_superadminSourceAggregate[18]{};
bool g_superadminTerrainKnown = false;
uint32_t g_superadminTerrainMask = 0;
uint32_t g_superadminTerrainType = 0;
bool g_superadminRngKnown = false;
uint32_t g_superadminRngState = 0;
int32_t g_publicSortSpeed[7]{};
uint32_t g_publicSortFlying[7]{};
int g_publicSortDistance = 0;
uint32_t g_predictionExcludedMask = 0;
int g_plannedProjectionCount = 0;
int g_publicPlacementScore[7]{};
bool g_projectionPlanning = false;
volatile LONG g_superadminSourceCount = 0;
volatile LONG g_superadminSourceGeneration = -1;
bool g_knownHeroLarge = false;
bool g_predictedDefensive = false;
int g_protectiveCells[120]{};
int g_protectiveCellCount = 0;
uint32_t g_candidateIdentity = 0;
uint32_t g_definitionMaximum = 0;
uint32_t g_groundRetryOrder[7]{};
void* g_originalRenderer = nullptr;
void* g_originalTooltipSource = nullptr;
void* g_placementOwner = nullptr;
void* g_root = nullptr;
void* g_grid = nullptr;
struct FrozenActorInput {
    uint32_t world, army, source, type, quantity, damage;
    int32_t attack, defence, health;
    float initiative, atb;
    int32_t morale, luck, speed;
    uint32_t category, eligible, skipSpeed, selected, retaliationBonus, controlWord;
    uint32_t aggregateIdentity, unsupported, specialCategory, attackGeneration;
    uint32_t rangedCapability, ignoreWhenNoRanged, armySize;
    int32_t counterMaximum[3], counterCurrent[3];
    uint32_t healthTransformFlags, healthScaleBits[2];
};
static_assert(sizeof(FrozenActorInput) == 144, "Primitive input trace layout");
constexpr uint32_t kActorInputCapacity = 256;
FrozenActorInput g_actorInputs[kActorInputCapacity]{};
volatile LONG g_actorInputSequence = 0;
volatile LONG g_actorInputCount = 0;
volatile LONG g_actorInputGeneration = 0;
volatile LONG g_actorInputOverflow = 0;
bool g_actorInputsFrozen = true;
bool g_actorInputBusy = false;
uint32_t g_actorInputWorld = 0;
uint32_t g_actorCoreMask = 0;
uint32_t g_actorCoreStackCounts[2]{};
uint32_t g_actorCoreWords[2][18]{};
uint32_t g_actorCoreInputEnds[2]{};
uint32_t g_strategyTrace[10]{};
struct FrozenHeroCorrection {
    uint32_t aggregateIdentity, inputCount;
    int32_t firstScalar, secondScalar;
    uint32_t controlWord, attackGeneration;
};
static_assert(sizeof(FrozenHeroCorrection) == 24, "Hero correction trace layout");
FrozenHeroCorrection g_heroCorrections[64]{};
uint32_t g_heroCorrectionCount = 0;
uint32_t g_heroCorrectionOverflow = 0;
uint32_t g_heroCorrectionMask = 0;
struct FrozenAuxiliaryPower {
    uint32_t aggregateIdentity, inputCount;
    int32_t value;
    uint32_t caller, controlWord, attackGeneration;
};
static_assert(sizeof(FrozenAuxiliaryPower) == 24, "Auxiliary input trace layout");
FrozenAuxiliaryPower g_auxiliaryInputs[256]{};
uint32_t g_auxiliaryInputCount = 0;
uint32_t g_auxiliaryInputOverflow = 0;
uint32_t g_auxiliaryMask = 0;
struct FrozenSourceStrength {
    uint32_t metadata[8], inputWords[30], ownWords[2];
};
static_assert(sizeof(FrozenSourceStrength) == 160, "Source strength trace row");
FrozenSourceStrength g_sourceStrengthInputs[256]{};
uint32_t g_sourceStrengthCount = 0, g_sourceStrengthOverflow = 0;
bool g_sourceStrengthBusy = false;
uint32_t g_sourceSplitSeed[4]{};
uint32_t g_sourceComposition[24]{};
bool g_sourceSimpleLayout = false;
int g_sourceSimpleColumns = 0;
bool g_sourceFallbackPrepared = false;
int g_sourceFallbackCells[4]{-1,-1,-1,-1};
struct FrozenAreaInput {
    uint32_t metadata[14], spellWords[32 * 9];
    uint32_t physicalWords[14];
};
static_assert(sizeof(FrozenAreaInput) == 316 * 4, "Area primitive trace row");
FrozenAreaInput g_areaInputs[128]{};
uint32_t g_areaInputCount = 0, g_areaInputOverflow = 0;
bool g_areaInputBusy = false;
uint32_t g_areaPolicyTrace[4]{};
uint32_t g_largePolicyTrace[4]{};
void ResetSuperadminInputCapture();
void FreezeSuperadminInputCapture();
void PrepareSuperadminAggregates();
void PrepareSuperadminStrategy();
void PrepareSourceComposition(const uint32_t* owner);
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
int PublicPlacementRole(uint32_t type);
bool __fastcall PublicPlacementPairBefore(const int* left, const int* right);
bool ExcludeWeakestProjection();
void ResetProjectionAttempt();
int ChooseLinkedGoblinCell();
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

// Source-army strength is a different calculation from the combat aggregate.
// Inputs are primitive source statistics/definition deltas and loaded settings;
// this helper never queries engine decisions or final battle descriptors.
struct SourceStrengthInput {
    int baseValue, quantity, deltas[6], modifierA, modifierB;
    uint32_t initiativeBits[3]; // Low 10 bytes are the getter's x87 value.
    int baseInitiative;
    bool shooterBonus, modifierPenalty;
    float coefficients[11];
    double baseScale, one;
};
static_assert(sizeof(SourceStrengthInput) == 120, "Source strength primitive layout");

int64_t CalculateSourceStrength(const SourceStrengthInput& input) {
    int64_t value;
    const int base = input.baseValue < 1 ? 1 : input.baseValue;
    const double scale = input.baseScale, one = input.one;
    unsigned short controlWord, conversionWord;
    __asm {
        fnstcw controlWord
        mov ax, controlWord
        or ax, 0x0c00
        mov conversionWord, ax
        fild base
        fmul scale
        fldcw conversionWord
        fistp value
        fldcw controlWord
    }
    if (input.shooterBonus) {
        const uint64_t product = static_cast<uint64_t>(value) * 140u;
        value = static_cast<int64_t>(product) / 100;
    }
    for (unsigned index = 0; index < 6; ++index) {
        const int delta = input.deltas[index];
        const float coefficient = input.coefficients[index];
        float storedDelta;
        if (index < 2) {
            __asm {
                fild delta
                fstp storedDelta
                fld storedDelta
            }
        } else {
            __asm { fild delta }
        }
        __asm {
            fmul coefficient
            fild value
            faddp st(1), st(0)
            fldcw conversionWord
            fistp value
            fldcw controlWord
        }
    }
    for (unsigned index = 0; index < 2; ++index) {
        const int modifier = index == 0 ? input.modifierA : static_cast<int>(
            static_cast<uint32_t>(input.modifierB) - (input.modifierPenalty ? 1u : 0u));
        const unsigned coefficientIndex = index == 0 ? (modifier >= 0 ? 7 : 8)
            : (modifier >= 0 ? 9 : 10);
        const double coefficient = input.coefficients[coefficientIndex];
        double storedWeight;
        __asm {
            fild modifier
            fmul coefficient
        }
        // 4e9e91 stores B's weighted modifier as a qword before adding one.
        if (index == 1) {
            __asm {
                fstp storedWeight
                fld storedWeight
            }
        }
        __asm {
            fadd one
            fild value
            fmulp st(1), st(0)
            fldcw conversionWord
            fistp value
            fldcw controlWord
        }
    }
    const void* initiative = input.initiativeBits;
    const float coefficient = input.coefficients[6];
    const int baseInitiative = input.baseInitiative;
    float storedInitiativeDelta;
    __asm {
        mov eax, initiative
        fld tbyte ptr [eax]
        fisub baseInitiative
        fstp storedInitiativeDelta
        fld storedInitiativeDelta
        fmul coefficient
        fadd one
        fild value
        fmulp st(1), st(0)
        fldcw conversionWord
        fistp value
        fldcw controlWord
    }
    return static_cast<int64_t>(static_cast<uint64_t>(value)
        * static_cast<uint64_t>(static_cast<int64_t>(input.quantity)));
}

uint32_t DrawSourceRandom(uint32_t& state, uint32_t bound) {
    if (bound == 0) return 0;
    const uint32_t first = state * 0x343fdu + 0x269ec3u;
    state = first * 0x343fdu + 0x269ec3u;
    const uint32_t mixed = static_cast<uint32_t>(static_cast<int32_t>(first) >> 7) ^ (state << 6);
    return mixed % bound;
}

bool CalculateSourceComposition(int64_t own, int64_t enemy, uint32_t seed, uint16_t selected,
                                uint32_t type, uint32_t quantity, int footprint,
                                const uint32_t* upgrades, uint32_t upgradeCount,
                                double halfThreshold, double oneThreshold, uint32_t* output) {
    if (output == nullptr || enemy == 0 || quantity == 0 || quantity > 0x7fffffffu
        || footprint <= 0 || upgradeCount > 32 || (upgradeCount && upgrades == nullptr)) return false;
    memset(output, 0, 24 * sizeof(uint32_t));
    memcpy(output + 1, &own, 8); memcpy(output + 3, &enemy, 8);
    const int maximum = footprint > 2 ? 2 : 4;
    int count = maximum == 2 ? 2 : 4;
    double ratio;
    unsigned short original;
    __asm {
        fnstcw original
        fldcw selected
        fild own
        fild enemy
        fdivp st(1), st(0)
        fst ratio
    }
    if (maximum == 4) {
        __asm {
            fcom halfThreshold
            fnstsw ax
            test ax, 0x0100
            jnz composition_threshold_done
            mov count, 3
            fcom oneThreshold
            fnstsw ax
            test ax, 0x0100
            jnz composition_threshold_done
            mov count, 2
        composition_threshold_done:
        }
    }
    __asm {
        fstp st(0)
        fldcw original
    }
    memcpy(output + 5, &ratio, 8);
    output[7] = maximum; output[8] = count;
    output[9] = DrawSourceRandom(seed, 100) + 1;
    if (output[9] <= 30) --count;
    else if (output[9] >= 70 && count < maximum) ++count;
    if (static_cast<uint32_t>(count) > quantity) count = static_cast<int>(quantity);
    if (count < 1) count = 1;
    uint32_t upgrade = 0;
    if (count > 2 && upgradeCount) {
        output[10] = DrawSourceRandom(seed, 100) + 1;
        if (output[10] < 50) {
            output[11] = DrawSourceRandom(seed, upgradeCount) + 1;
            upgrade = upgrades[output[11] - 1];
        }
    }
    output[12] = count; output[13] = seed; output[14] = selected;
    for (int index = 0; index < count; ++index) {
        output[16 + index * 2] = upgrade && index > 0 && index < count - 1 ? upgrade : type;
        output[17 + index * 2] = quantity / count + (static_cast<uint32_t>(index) < quantity % count ? 1 : 0);
    }
    output[0] = 1;
    return true;
}

struct PlacementAggregate {
    int extra0, unused, extra2, damage;
    float attack, multiplier;
    int health;
    float defence;
    int eligibleHealth;
    float eligibleDefence;
    float shooterDamage, shooterAttack;
    float flyingDamage, flyingAttack;
    float groundDamage, groundAttack;
    int magicPower;
    uintptr_t nativeHelper;
};
static_assert(sizeof(PlacementAggregate) == 0x48, "Native score aggregate layout");

struct BaselineActionFactorInput {
    int morale, luck, speed;
    float initiative, atb;
    bool skipSpeed, selected, retaliationBonus;
    int32_t counterMaximum[3]{}, counterCurrent[3]{};
    bool halfRangedFactor = false;
};

struct PlacementWeights {
    int attack;
    float action;
    int defence, eligibleDefence;
    int shooterDamage, flyingDamage, groundDamage;
};

void InitializePlacementAggregate(PlacementAggregate& aggregate, PlacementWeights& weights) {
    memset(&aggregate, 0, sizeof(aggregate));
    memset(&weights, 0, sizeof(weights));
    aggregate.multiplier = 1.0f;
    // bfbe50 seeds the action numerator, not just its final normalized field.
    weights.action = 1.0f;
}

float PlacementRatio(int numerator, int denominator) {
    float result;
    __asm {
        fild numerator
        fidiv denominator
        fstp result
    }
    return result;
}

float PlacementRatio(float numerator, int denominator) {
    float result;
    __asm {
        fild denominator
        fdivr numerator
        fstp result
    }
    return result;
}

int CalculatePlacementPower(const PlacementAggregate& aggregate, const PlacementAggregate& opponent,
                            float increase, float decrease, bool shootersOnly) {
    // A58D30 stores the attack delta as float, but returns an extended x87 factor.
    // BF9CC0/BFA1B0 truncate defence and the result without narrowing that factor.
    uint16_t original, truncation;
    int defence, power;
    float defenceValue, delta;
    __asm fnstcw original
    truncation = original | 0x0c00;
    const float opponentDefence = opponent.eligibleDefence;
    __asm {
        fld opponentDefence
        fldcw truncation
        fistp defence
        fldcw original
        fild defence
        fstp defenceValue
    }
    const float attack = shootersOnly ? aggregate.shooterAttack : aggregate.attack;
    __asm {
        fld attack
        fsub defenceValue
        fstp delta
    }
    float coefficient = delta > 0 ? increase : decrease;
    if (!(coefficient > 0)) coefficient = 0;
    const float one = 1.0f;
    const float multiplier = aggregate.multiplier;
    const int damage = aggregate.damage;
    const float shooterDamage = aggregate.shooterDamage;
    __asm {
        fld coefficient
        fmul delta
    }
    if (delta > 0) {
        __asm fadd one
    } else {
        __asm {
            fsubr one
            fdivr one
        }
    }
    if (shootersOnly) {
        __asm fmul shooterDamage
    } else {
        __asm fimul damage
    }
    __asm {
        fmul multiplier
        fldcw truncation
        fistp power
        fldcw original
    }
    if (shootersOnly) return power;
    int extra = 0;
    if (CalculatePlacementPower(aggregate, opponent, increase, decrease, true)
        > CalculatePlacementPower(opponent, aggregate, increase, decrease, true)) {
        const float flying = opponent.flyingDamage, shooter = opponent.shooterDamage;
        const float ground = opponent.groundDamage;
        const int extraPower = aggregate.unused;
        __asm {
            fld flying
            fadd shooter
            fadd ground
            fdivr ground
            fimul extraPower
            fldcw truncation
            fistp extra
            fldcw original
        }
    }
    return static_cast<int>(static_cast<uint32_t>(power) + static_cast<uint32_t>(extra)
        + static_cast<uint32_t>(aggregate.extra0) + static_cast<uint32_t>(aggregate.magicPower));
}

void NormalizePlacementAggregate(PlacementAggregate& aggregate, const PlacementWeights& weights) {
    if (aggregate.damage != 0) {
        aggregate.attack = PlacementRatio(weights.attack, aggregate.damage);
        aggregate.multiplier = PlacementRatio(weights.action, aggregate.damage);
    }
    if (aggregate.health != 0) {
        aggregate.defence = PlacementRatio(weights.defence, aggregate.health);
    }
    if (aggregate.eligibleHealth != 0) {
        aggregate.eligibleDefence = PlacementRatio(weights.eligibleDefence, aggregate.eligibleHealth);
    }
    if (weights.shooterDamage != 0) {
        aggregate.shooterAttack = PlacementRatio(aggregate.shooterAttack, weights.shooterDamage);
    }
    if (weights.flyingDamage != 0) {
        aggregate.flyingAttack = PlacementRatio(aggregate.flyingAttack, weights.flyingDamage);
    }
    if (weights.groundDamage != 0) {
        aggregate.groundAttack = PlacementRatio(aggregate.groundAttack, weights.groundDamage);
    }
}

struct AreaSpellInput {
    uint32_t identifier, usable, areaAllowed, damaging, excluded;
    int32_t damage;
    uint32_t limited;
    int32_t charges, cost;
};

int CalculateAreaSpellPower(int baseline, int resources, int horizon, bool areaOnly,
                           const AreaSpellInput* spells, uint32_t count) {
    // BFA360: the four-turn area estimate differs from the ten-turn aggregate.
    if (horizon <= 0) return baseline;
    int best = baseline;
    for (uint32_t index = 0; index < count; ++index) {
        const auto& spell = spells[index];
        if (!spell.usable || (areaOnly && !spell.areaAllowed) || !spell.damaging
            || spell.identifier == 0xa2 || spell.identifier == 0x13c || spell.excluded || spell.damage == 0) continue;
        int casts = spell.limited ? spell.charges : (spell.cost > 0 ? resources / spell.cost : 100);
        if (spell.limited || spell.cost > 0) {
            if (casts < 1) continue;
        }
        if (casts > horizon) casts = horizon;
        const int product = static_cast<int>(static_cast<uint32_t>(casts) * static_cast<uint32_t>(spell.damage));
        const int power = product / horizon;
        if (power > best) best = power;
    }
    return best;
}

int CalculateAreaPhysicalPower(int quantity, float damageSum, bool ranged, bool canShoot,
                               bool halfRanged, bool areaMelee) {
    const float half = 0.5f;
    int damage;
    uint16_t original, truncation;
    __asm fnstcw original
    truncation = original | 0x0c00;
    __asm {
        fild quantity
        fmul damageSum
        fmul half
        fldcw truncation
        fistp damage
        fldcw original
    }
    uint32_t total = 0;
    if (ranged && canShoot) total += static_cast<uint32_t>(halfRanged ? damage / 2 : damage);
    if (areaMelee) total += static_cast<uint32_t>(damage);
    return static_cast<int>(total);
}

// Initial-state arithmetic with resource ratios. Remaining status, ability and
// action corrections must be reconstructed before complete policy replay.
float BaselineActionFactor(const BaselineActionFactorInput& input) {
    const float one = 1.0f, tenth = 0.1f, twentieth = 0.05f, retaliation = 1.1f;
    const int morale = input.morale, luck = input.luck, speedDelta = input.speed - 5;
    const float initiative = input.initiative < 2 ? 2 : input.initiative > 30 ? 30 : input.initiative;
    const float atb = input.atb < 0 ? 0 : input.atb > 1 ? 1 : input.atb;
    float factor;
    // Match the native x87 intermediate precision and each float store.
    __asm {
        fild luck
        fmul tenth
        fadd one
        fild morale
        fmul tenth
        fadd one
        fmulp st(1), st(0)
        fstp factor
        fld initiative
        fmul factor
        fmul tenth
        fstp factor
    }
    if (input.halfRangedFactor) {
        const float half = 0.5f;
        __asm {
            fld factor
            fmul half
            fstp factor
        }
    }
    if (!input.skipSpeed) {
        __asm {
            fild speedDelta
            fmul twentieth
            fadd one
            fmul factor
            fstp factor
        }
    }
    if (!input.selected) {
        __asm {
            fld atb
            fmul tenth
            fadd one
            fsub twentieth
            fmul factor
            fstp factor
        }
    }
    for (uint32_t index = 0; index < 3; ++index) {
        const int maximum = input.counterMaximum[index], current = input.counterCurrent[index];
        if (maximum <= 0) continue;
        __asm {
            fild current
            fmul tenth
            fidiv maximum
            fadd one
            fmul factor
            fstp factor
        }
    }
    if (input.retaliationBonus) {
        __asm {
            fld factor
            fmul retaliation
            fstp factor
        }
    }
    return factor < 0 ? 0 : factor > 13 ? 13 : factor;
}

unsigned SelectPlacementDamageCategory(bool excluded, bool shooter, bool flying,
                                       bool special, bool ignoreWhenNoRanged) {
    if (excluded) return 3;
    if (shooter || (special && ignoreWhenNoRanged)) return 0;
    return flying ? 1 : 2;
}

// category: 0 shooter, 1 flying, 2 ground; other values omit category totals.
// Callers supply effective damage/attack and the already reconstructed factor.
void AccumulatePlacementDamage(PlacementAggregate& aggregate, PlacementWeights& weights,
                               int damage, int attack, float action, unsigned category) {
    aggregate.damage = static_cast<int32_t>(static_cast<uint32_t>(aggregate.damage) + static_cast<uint32_t>(damage));
    const int32_t attackContribution = static_cast<int32_t>(
        (static_cast<uint32_t>(attack) + 1u) * static_cast<uint32_t>(damage));
    weights.attack = static_cast<int32_t>(static_cast<uint32_t>(weights.attack)
        + static_cast<uint32_t>(attackContribution));
    float actionDamage;
    float* total = &weights.action;
    __asm {
        fild damage
        fmul action
        fstp actionDamage
        mov eax, total
        fld actionDamage
        fadd dword ptr [eax]
        fstp dword ptr [eax]
    }
    if (category > 2) return;
    float* categoryDamage = category == 0 ? &aggregate.shooterDamage
        : category == 1 ? &aggregate.flyingDamage : &aggregate.groundDamage;
    float* categoryAttack = category == 0 ? &aggregate.shooterAttack
        : category == 1 ? &aggregate.flyingAttack : &aggregate.groundAttack;
    int* denominator = category == 0 ? &weights.shooterDamage
        : category == 1 ? &weights.flyingDamage : &weights.groundDamage;
    *denominator = static_cast<int32_t>(static_cast<uint32_t>(*denominator) + static_cast<uint32_t>(damage));
    __asm {
        mov eax, categoryDamage
        mov edx, categoryAttack
        fld actionDamage
        fadd dword ptr [eax]
        fstp dword ptr [eax]
        fild attackContribution
        fadd dword ptr [edx]
        fstp dword ptr [edx]
    }
}

// Effective health/defence include earlier status transformations. The native
// eligible-health subset uses its own defence, which can differ from the total.
void AccumulatePlacementHealth(PlacementAggregate& aggregate, PlacementWeights& weights,
                               int health, int defence, int eligibleDefence, bool includeEligible) {
    aggregate.health = static_cast<int32_t>(static_cast<uint32_t>(aggregate.health) + static_cast<uint32_t>(health));
    const uint32_t contribution = (static_cast<uint32_t>(defence) + 1u) * static_cast<uint32_t>(health);
    weights.defence = static_cast<int32_t>(static_cast<uint32_t>(weights.defence) + contribution);
    if (!includeEligible) return;
    aggregate.eligibleHealth = static_cast<int32_t>(
        static_cast<uint32_t>(aggregate.eligibleHealth) + static_cast<uint32_t>(health));
    const uint32_t eligibleContribution = (static_cast<uint32_t>(eligibleDefence) + 1u)
        * static_cast<uint32_t>(health);
    weights.eligibleDefence = static_cast<int32_t>(
        static_cast<uint32_t>(weights.eligibleDefence) + eligibleContribution);
}

float ApplyHeroActionCorrection(float factor, int32_t firstScalar, int32_t secondScalar) {
    const int32_t sum = static_cast<int32_t>(static_cast<uint32_t>(firstScalar) + static_cast<uint32_t>(secondScalar));
    const float coefficient = 0.05f, one = 1.0f;
    float adjustment;
    __asm {
        fild sum
        fmul coefficient
        fstp adjustment
        fld adjustment
        fadd one
        fmul factor
        fstp factor
    }
    return factor;
}

int32_t TransformPlacementHealth(int32_t health, uint32_t flags, const uint32_t* scaleBits) {
    if ((flags & 1) == 0) return health;
    double scale;
    memcpy(&scale, scaleBits, sizeof(scale));
    int64_t transformed;
    uint16_t original, truncated;
    __asm {
        fild health
        fmul scale
        fnstcw original
        mov ax, original
        or ax, 0x0c00
        mov truncated, ax
        fldcw truncated
        fistp transformed
        fldcw original
    }
    return static_cast<int32_t>(static_cast<uint32_t>(static_cast<uint64_t>(transformed)));
}

void CaptureKnownHeroModifiers(const uint32_t* owner) {
    g_knownHeroAttack = -1;
    g_knownHeroBattleFrenzy = false;
    if (owner == nullptr || owner[0x98 / 4] == 0) return;
    const auto* holder = reinterpret_cast<const uint32_t*>(owner[0x98 / 4]);
    const uint32_t hero = holder[0x10 / 4];
    if (hero == 0) return;
    const uint32_t secondary = *reinterpret_cast<const uint32_t*>(hero + 4);
    if (secondary == 0) return;
    const int32_t offset = *reinterpret_cast<const int32_t*>(secondary);
    const uint32_t statObject = hero + 4 + static_cast<uint32_t>(offset);
    const int value = reinterpret_cast<int(__thiscall*)(const void*)>(0x5d4a40)(
        reinterpret_cast<const void*>(statObject));
    if (value >= 0 && value <= 1000) g_knownHeroAttack = value;
    const auto* methods = *reinterpret_cast<const uint32_t* const*>(hero);
    const auto mastery = reinterpret_cast<int(__thiscall*)(const void*, int)>(methods[0x174 / 4]);
    g_knownHeroBattleFrenzy = mastery(reinterpret_cast<const void*>(hero), 36) > 0;
    if (g_superadminEnabled) {
        InterlockedIncrement(&g_actorInputSequence);
        for (uint32_t index = 0; index < g_sourceStrengthCount; ++index) {
            auto& row = g_sourceStrengthInputs[index];
            row.metadata[7] = 0;
            if (row.metadata[2] != 0 || row.metadata[6] != 0) continue;
            if (row.metadata[1] == hero && owner[3] != 0 && owner[4] >= owner[3]
                && (owner[4] - owner[3]) % 36 == 0 && (owner[4] - owner[3]) / 36 <= 7) {
                const auto* begin = reinterpret_cast<const uint32_t*>(owner[3]);
                const auto* end = reinterpret_cast<const uint32_t*>(owner[4]);
                for (auto* record = begin; record != end; record += 9) {
                    if (record[2] != 0 && row.metadata[3] == record[7]
                        && row.inputWords[1] == record[2]) row.metadata[7] |= 1;
                }
            }
            if (row.metadata[1] != 0) continue;
            for (LONG source = 0; source < g_superadminSourceCount; ++source) {
                if (row.metadata[0] == g_superadminSourcePointers[source]
                    && row.metadata[3] == g_superadminSourceTypes[source]
                    && row.inputWords[1] == g_superadminSourceCounts[source]) row.metadata[7] |= 2;
            }
        }
        InterlockedIncrement(&g_actorInputSequence);
    }
}

// Only the visible player's CPlacementInfo records are traversed. Enemy army
// pointers, upgrades and splitting decisions are not inputs to this estimate.
void PrepareKnownHeroPolicy() {
    FreezeSuperadminInputCapture();
    PrepareSuperadminAggregates();
    g_knownHeroLarge = false;
    g_predictedDefensive = false;
    g_estimatedSpreadDenominator = 0;
    g_knownHeroAttack = -1;
    g_knownHeroBattleFrenzy = false;
    if (!g_superadminEnabled) g_useSpreadRows = false;
    const auto* owner = static_cast<const uint32_t*>(g_placementOwner);
    if (owner == nullptr || owner[3] == 0 || owner[4] < owner[3]
        || (owner[4] - owner[3]) % 36 != 0 || (owner[4] - owner[3]) / 36 > 7) return;
    using Definition = const int* (__fastcall*)(uint32_t);
    using Score = int (__thiscall*)(const PlacementAggregate*, const PlacementAggregate*);
    const auto definition = reinterpret_cast<Definition>(kCreatureDefinition);
    const auto evaluate = reinterpret_cast<Score>(0xbf9b80);
    const int* peasant = definition(1);
    if (peasant == nullptr) return;
    if (g_superadminEnabled) {
        g_superadminTerrainKnown = false;
        g_superadminTerrainMask = 0;
        g_superadminRngKnown = false;
        g_superadminRngState = 0;
        const auto* grid = static_cast<const uint32_t*>(g_grid);
        if (grid != nullptr && grid[0] == 0xe79d3c) {
            const auto* random = reinterpret_cast<const uint32_t*>(grid[0xd4 / 4]);
            if (random != nullptr && random[0] == 0xe51284) {
                g_superadminRngState = random[2];
                g_superadminRngKnown = true;
            }
            const auto* methods = reinterpret_cast<const uint32_t*>(grid[0]);
            if (methods[0x54 / 4] == 0xaf1380) {
                using NativeTerrain = bool (__thiscall*)(const void*, uint32_t);
                const auto native = reinterpret_cast<NativeTerrain>(methods[0x54 / 4]);
                g_superadminTerrainType = grid[0xb8 / 4];
                for (LONG index = 0; index < g_publicCount; ++index) {
                    const int* creature = definition(g_publicTypes[index]);
                    if (creature != nullptr && native(grid, creature[0x98 / 4])) {
                        g_superadminTerrainMask |= 1u << index;
                    }
                }
                g_superadminTerrainKnown = true;
            }
        }
    }
    CaptureKnownHeroModifiers(owner);
    PrepareSourceComposition(owner);
    PlacementAggregate reference{};
    reference.attack = static_cast<float>(peasant[0x44 / 4]);
    double total = 0;
    double large = 0;
    double knownDamage = 0;
    double knownAttackWeight = 0;
    double knownHealth = 0;
    double knownDefenceWeight = 0;
    double knownShooterDamage = 0;
    double knownShooterAttackWeight = 0;
    for (auto address = owner[3]; address < owner[4]; address += 36) {
        const auto* stack = reinterpret_cast<const int*>(address);
        const int quantity = stack[2];
        if (quantity <= 0) continue;
        const int* creature = definition(stack[7]);
        if (creature == nullptr) return;
        const int64_t damage = (static_cast<int64_t>(creature[0x50 / 4]) + creature[0x54 / 4]) * quantity / 2
            + (g_knownHeroBattleFrenzy ? quantity : 0);
        const int64_t health = static_cast<int64_t>(creature[0x64 / 4]) * quantity;
        if (damage < 0 || damage > INT_MAX || health < 0 || health > INT_MAX) return;
        knownDamage += static_cast<double>(damage);
        knownAttackWeight += static_cast<double>(damage) * creature[0x44 / 4];
        knownHealth += static_cast<double>(health);
        knownDefenceWeight += static_cast<double>(health) * creature[0x48 / 4];
        if (creature[0x4c / 4] > 0) {
            knownShooterDamage += static_cast<double>(damage);
            knownShooterAttackWeight += static_cast<double>(damage) * creature[0x44 / 4];
        }
        PlacementAggregate candidate{};
        candidate.damage = static_cast<int>(damage);
        candidate.attack = static_cast<float>(creature[0x44 / 4]);
        candidate.multiplier = 1.0f;
        candidate.health = static_cast<int>(health);
        candidate.defence = static_cast<float>(creature[0x48 / 4]);
        const int score = evaluate(&candidate, &reference);
        if (score <= 0) continue;
        total += score;
        if (creature[0xdc / 4] == 2) large += score;
    }
    const auto* settings = reinterpret_cast<const unsigned char* (__cdecl*)()>(0xbcb3f0)();
    if (settings != nullptr && total > 0) {
        const float threshold = *reinterpret_cast<const float*>(settings + 0xbf4);
        g_knownHeroLarge = large / total > threshold;
        if (!g_superadminEnabled && knownDamage > 0 && knownDamage < INT_MAX) {
            // Public row labels give only ranges, never source quantities.
            // Use their midpoints to estimate health-weighted enemy defence.
            const double midpoints[] = {0, 2.5, 7, 14.5, 34.5, 74.5, 174.5, 374.5, 749.5, 1000};
            const double lowerBounds[] = {0, 1, 5, 10, 20, 50, 100, 250, 500, 1000};
            double defenceWeight = 0;
            double healthWeight = 0;
            double enemyDamage = 0;
            double enemyShooterDamage = 0;
            double enemyShooterAttackWeight = 0;
            for (LONG index = 0; index < g_publicCount; ++index) {
                const unsigned band = g_publicBands[index];
                const int* creature = definition(g_publicTypes[index]);
                if (band < 1 || band > 9 || creature == nullptr || creature[0x64 / 4] <= 0) return;
                const double weight = midpoints[band] * creature[0x64 / 4];
                healthWeight += weight;
                defenceWeight += weight * creature[0x48 / 4];
                const double damage = midpoints[band] *
                    (static_cast<double>(creature[0x50 / 4]) + creature[0x54 / 4]) / 2;
                enemyDamage += damage;
                if (creature[0x4c / 4] > 0) {
                    const double shooterDamage = lowerBounds[band] *
                        (static_cast<double>(creature[0x50 / 4]) + creature[0x54 / 4]) / 2;
                    enemyShooterDamage += shooterDamage;
                    enemyShooterAttackWeight += shooterDamage * creature[0x44 / 4];
                }
            }
            if (healthWeight > 0) {
                const auto factorAgainst = [&](double attack, double defence) {
                    const double delta = attack - static_cast<int>(defence);
                    const double coefficient = delta > 0
                        ? *reinterpret_cast<const float*>(settings + 0x1d0)
                        : *reinterpret_cast<const float*>(settings + 0x1d8);
                    return delta > 0 ? 1 + coefficient * delta : 1 / (1 - coefficient * delta);
                };
                // First public-only estimate of the native 0xbfa1b0 ratio.
                // Hero bonuses and area power are still calibrated estimates.
                const double attack = knownAttackWeight / knownDamage
                    + (g_knownHeroAttack >= 0 ? g_knownHeroAttack : 1.0);
                const int denominator = static_cast<int>(knownDamage * 1.5 *
                    factorAgainst(attack, defenceWeight / healthWeight));
                g_estimatedSpreadDenominator = denominator > 0 ? static_cast<uint32_t>(denominator) : 0;
                const float spreadThreshold = *reinterpret_cast<const float*>(settings + 0xbf8);
                g_useSpreadRows = denominator > 0 && 24.0 / denominator > spreadThreshold;
                if (enemyDamage > 0 && enemyShooterDamage > 0 && knownHealth > 0) {
                    const double enemyShooterPower = enemyShooterDamage * factorAgainst(
                        enemyShooterAttackWeight / enemyShooterDamage, knownDefenceWeight / knownHealth);
                    // 0xa2fd40 compares their ranged damage to the opposing
                    // hero army's total power, not the neutral army's total.
                    const double knownTotalPower = knownDamage * 1.5 * factorAgainst(
                        attack, defenceWeight / healthWeight);
                    const double knownShooterPower = knownShooterDamage > 0
                        ? knownShooterDamage * 1.5 * factorAgainst(
                            knownShooterAttackWeight / knownShooterDamage
                                + (g_knownHeroAttack >= 0 ? g_knownHeroAttack : 1),
                            defenceWeight / healthWeight)
                        : 0;
                    const float shareThreshold = *reinterpret_cast<const float*>(settings + 0xbfc);
                    const float advantageThreshold = *reinterpret_cast<const float*>(settings + 0xc00);
                    g_predictedDefensive = knownTotalPower > 0
                        && enemyShooterPower / knownTotalPower > shareThreshold
                        && (knownShooterPower == 0 || enemyShooterPower / knownShooterPower > advantageThreshold);
                }
            }
        }
    }
    if (g_superadminEnabled) PrepareSuperadminStrategy();
}

void PrepareProtectiveCandidates() {
    g_protectiveCellCount = 0;
    const int width = *reinterpret_cast<const int*>(g_outputStorage + 8 + 384);
    const int height = *reinterpret_cast<const int*>(g_outputStorage + 8 + 388);
    const int stride = *reinterpret_cast<const int*>(g_outputStorage + 8 + 524);
    const int rows = height - 2;
    if (width < 8 || width > 32 || rows < 2 || rows > 30 || stride < (width + 7) / 8) return;
    const auto* occupied = g_outputStorage + 8 + 1536;
    const auto occupiedAt = [&](int localX, int localY) {
        const int x = width - 3 - localX;
        const int y = localY + 1;
        return (occupied[y * stride + x / 8] & (1 << (x & 7))) != 0;
    };
    // Native 0x857cc0 visits occupied deployment cells column first, then
    // inserts each free neighbour once in 0xb5f990's eight-offset order.
    constexpr int offsets[8][2] = {
        {0, -1}, {0, 1}, {-1, 0}, {1, 0},
        {1, -1}, {1, 1}, {-1, -1}, {-1, 1},
    };
    int candidateX[60]{};
    int candidateY[60]{};
    for (int localX = 0; localX < 2; ++localX) {
        for (int localY = 0; localY < rows; ++localY) {
            if (!occupiedAt(localX, localY)) continue;
            for (const auto& offset : offsets) {
                const int x = localX + offset[0];
                const int y = localY + offset[1];
                if (x < 0 || x >= 2 || y < 0 || y >= rows || occupiedAt(x, y)) continue;
                bool seen = false;
                for (int index = 0; index < g_protectiveCellCount; ++index) {
                    if (candidateX[index] == x && candidateY[index] == y) {
                        seen = true;
                        break;
                    }
                }
                if (!seen && g_protectiveCellCount < 60) {
                    candidateX[g_protectiveCellCount] = x;
                    candidateY[g_protectiveCellCount++] = y;
                }
            }
        }
    }
    if (g_protectiveCellCount == 0) return;
    const int window = *reinterpret_cast<const int*>(g_outputStorage + 8 + 784);
    const int windowLength = *reinterpret_cast<const int*>(g_outputStorage + 8 + 796);
    bool selected[30]{};
    if (window >= 0 && window < rows && windowLength > 0 && windowLength <= rows) {
        for (int index = 0; index < windowLength; ++index) selected[(window + index) % rows] = true;
    }
    int weight[30]{};
    for (int row = 0; row < rows; ++row) {
        weight[row] = selected[row] ? 2
            : ((row > 0 && selected[row - 1]) || (row + 1 < rows && selected[row + 1]) ? 1 : 0);
    }
    // 0x85a9b0 merges interleaved runs from the highest power of two down.
    // Its <= comparison chooses the right run on ties; a stable sort changes
    // the row sequence (recorded Polygon round 10: y9, y1, then y10).
    int original[60]{};
    int scratch[60]{};
    for (int index = 0; index < g_protectiveCellCount; ++index) original[index] = index;
    int* source = original;
    int* target = scratch;
    int step = 1;
    while (step < g_protectiveCellCount) step <<= 1;
    for (step >>= 1; step > 0; step >>= 1) {
        if (g_protectiveCellCount < step * 2) {
            for (int index = g_protectiveCellCount - step; index < g_protectiveCellCount; ++index) {
                target[index] = source[index];
            }
        }
        const int count = step < g_protectiveCellCount - step ? step : g_protectiveCellCount - step;
        for (int offset = 0; offset < count; ++offset) {
            int left = offset;
            int right = offset + step;
            int destination = offset;
            while (left < g_protectiveCellCount && right < g_protectiveCellCount) {
                const int leftWeight = weight[candidateY[source[left]]];
                const int rightWeight = weight[candidateY[source[right]]];
                target[destination] = source[leftWeight > rightWeight ? left : right];
                if (leftWeight > rightWeight) left += step * 2;
                else right += step * 2;
                destination += step;
            }
            while (left < g_protectiveCellCount) {
                target[destination] = source[left];
                left += step * 2;
                destination += step;
            }
            while (right < g_protectiveCellCount) {
                target[destination] = source[right];
                right += step * 2;
                destination += step;
            }
        }
        int* previous = source;
        source = target;
        target = previous;
    }
    for (int index = 0; index < g_protectiveCellCount; ++index) {
        const int candidate = source[index];
        g_protectiveCells[index * 2] = width - 3 - candidateX[candidate];
        g_protectiveCells[index * 2 + 1] = candidateY[candidate] + 1;
    }
}

int ChooseProtectiveCell() {
    const int width = *reinterpret_cast<const int*>(g_outputStorage + 8 + 384);
    const int height = *reinterpret_cast<const int*>(g_outputStorage + 8 + 388);
    const int stride = *reinterpret_cast<const int*>(g_outputStorage + 8 + 524);
    const int size = reinterpret_cast<intptr_t>(g_creatureDefinition);
    if (size < 1 || size > 2 || width < 8 || height < 4 || stride < (width + 7) / 8) return -1;
    const auto* occupied = g_outputStorage + 8 + 1536;
    for (int index = 0; index < g_protectiveCellCount; ++index) {
        const int originalColumn = g_protectiveCells[index * 2];
        const int originalRow = g_protectiveCells[index * 2 + 1];
        const int attempts = g_superadminEnabled && size == 2 ? 2 : 1;
        for (int columnAttempt = 0; columnAttempt < attempts; ++columnAttempt) {
          const int x = originalColumn + columnAttempt;
          for (int attempt = 0; attempt < attempts; ++attempt) {
            const int y = originalRow + attempt;
            if (x - size + 1 < width - 4 || (g_superadminEnabled && x > width - 3)
                || y - size + 1 < 1 || y >= height - 1) continue;
            bool free = true;
            for (int row = y - size + 1; row <= y; ++row) {
                for (int column = x - size + 1; column <= x; ++column) {
                    if (occupied[row * stride + column / 8] & (1 << (column & 7))) free = false;
                }
            }
            if (free) return (x << 8) | y;
          }
        }
    }
    return -1;
}

// Ordinary mode uses synthetic quantity=1; explicit Superadmin uses the map
// source quantities captured before Start. The native sort preserves its ties.
bool PlacementHasPhysicalShot(uint32_t type) {
    const auto* creature = reinterpret_cast<const int* (__fastcall*)(uint32_t)>(kCreatureDefinition)(type);
    if (creature == nullptr) return false;
    const bool defined = creature[0x4c / 4] > 0;
    if (!g_superadminEnabled || g_sourceSimpleLayout || !g_actorInputsFrozen || g_actorCoreMask != 3
        || g_actorInputGeneration != g_attackGeneration || g_superadminSourceGeneration != g_placementGeneration) return defined;
    const uint32_t end = g_actorCoreInputEnds[1], count = g_actorCoreStackCounts[1];
    if (!count || count > 7 || count != static_cast<uint32_t>(g_superadminSourceCount)
        || end < count || end > static_cast<uint32_t>(g_actorInputCount)) return defined;
    const uint32_t army = g_actorInputs[end - 1].army;
    bool found = false, shooter = false;
    for (uint32_t index = end - count; index < end; ++index) {
        const auto& input = g_actorInputs[index];
        if (input.type != type || input.world != g_actorInputWorld || input.army != army
            || input.attackGeneration != static_cast<uint32_t>(g_attackGeneration) || input.unsupported) continue;
        const bool physical = (input.skipSpeed & 4u) != 0;
        if (found && physical != shooter) return defined;
        shooter = physical;
        found = true;
    }
    return found ? shooter : defined;
}

bool PlacementHasShooterCategory(uint32_t type) {
    using Definition = const int* (__fastcall*)(uint32_t);
    using Ability = bool (__fastcall*)(uint32_t, uint32_t);
    const auto definition = reinterpret_cast<Definition>(kCreatureDefinition);
    const int* source = definition(type);
    if (source == nullptr) return false;
    // 4bb150 tests the source definition, independently of actor state.
    if (source[0x4c / 4] > 0) return true;
    if (!g_superadminEnabled || g_sourceSimpleLayout) return false;
    const auto ability = reinterpret_cast<Ability>(0xb61ba0);
    if (!ability(0x7a, type)) return false;
    // Native category4 also accepts a goblin thrower when a base-type117
    // source exists. This membership overlaps the earlier large-melee pass.
    for (LONG index = 0; index < g_publicCount; ++index) {
        const int* creature = definition(g_publicTypes[index]);
        if (creature != nullptr && static_cast<uint32_t>(creature[0x100 / 4] != 0
            ? creature[0x100 / 4] : g_publicTypes[index]) == 0x75) return true;
    }
    return false;
}

bool PreparePublicOrder() {
    using Aggregate = PlacementAggregate;
    struct Pair { int score; uint32_t sourceIndex; };
    using Definition = const int* (__fastcall*)(uint32_t);
    using Score = int (__thiscall*)(const Aggregate*, const Aggregate*);
    using Sort = void (__fastcall*)(Pair*, Pair*, uintptr_t);
    const auto definition = reinterpret_cast<Definition>(kCreatureDefinition);
    const auto evaluate = reinterpret_cast<Score>(0xbf9b80);
    const auto sort = reinterpret_cast<Sort>(0x85a700);
    memset(g_groundRetryOrder, 0xff, sizeof(g_groundRetryOrder));
    if (g_superadminEnabled && !g_sourceSimpleLayout) {
        if (g_superadminSourceGeneration != g_placementGeneration
            || g_superadminSourceCount < 1 || g_superadminSourceCount > 7
            || g_publicCount != g_superadminSourceCount) return false;
        for (LONG index = 0; index < g_superadminSourceCount; ++index) {
            if (g_superadminSourceCounts[index] == 0
                || definition(g_superadminSourceTypes[index]) == nullptr) return false;
        }
        // A public portrait may identify only the base creature or a shared
        // image. Admin ordering uses the original pre-Start source identities.
        memcpy(g_publicTypes, g_superadminSourceTypes, g_publicCount * sizeof(uint32_t));
    }
    if (g_superadminEnabled && g_sourceSimpleLayout) {
        if (g_sourceComposition[0] != 1 || g_sourceComposition[12] != static_cast<uint32_t>(g_publicCount)) return false;
        for (LONG index = 0; index < g_publicCount; ++index) {
            g_orderedPublicTypes[index] = g_publicTypes[index];
            reinterpret_cast<uint32_t*>(g_outputStorage + 8 + 832)[index] = g_sourceComposition[17 + index * 2];
            reinterpret_cast<uint32_t*>(g_outputStorage + 8 + 924)[index] = index;
        }
        g_plannedProjectionCount = g_publicCount;
        return true;
    }
    Aggregate reference{};
    const int* peasant = definition(1);
    if (!peasant || g_publicCount < 1 || g_publicCount > 7) return false;
    reference.attack = static_cast<float>(peasant[0x44 / 4]);
    uint32_t quantities[7]{};
    for (LONG index = 0; index < g_publicCount; ++index) {
        if (!g_superadminEnabled) continue;
        if (g_superadminSourceGeneration != g_placementGeneration) return false;
        LONG occurrence = 0;
        for (LONG previous = 0; previous < index; ++previous) {
            if (g_publicTypes[previous] == g_publicTypes[index]) ++occurrence;
        }
        for (LONG source = 0; source < g_superadminSourceCount; ++source) {
            if (g_superadminSourceTypes[source] != g_publicTypes[index]) continue;
            if (occurrence-- == 0) {
                quantities[index] = g_superadminSourceCounts[source];
                g_publicSortSpeed[index] = g_superadminSourceSpeed[source];
                g_publicSortFlying[index] = g_superadminSourceFlying[source];
                break;
            }
        }
        if (quantities[index] == 0) return false;
    }
    unsigned destination = 0;
    for (unsigned index = 0; index < 7; ++index) {
        reinterpret_cast<uint32_t*>(g_outputStorage + 8 + 924)[index] = UINT_MAX;
    }
    const int roleCount = g_superadminEnabled ? 6 : 3;
    for (int role = 0; role < roleCount; ++role) {
        Pair pairs[7]{};
        unsigned count = 0;
        for (LONG index = 0; index < g_publicCount; ++index) {
            if (g_superadminEnabled && (g_predictionExcludedMask & (1u << index))) continue;
            const int* creature = definition(g_publicTypes[index]);
            if (!creature) return false;
            const int creatureRole = PublicPlacementRole(g_publicTypes[index]);
            if (creatureRole != role) continue;
            const int quantity = g_superadminEnabled ? static_cast<int>(quantities[index]) : 1;
            const int64_t damage = (static_cast<int64_t>(creature[0x50 / 4]) + creature[0x54 / 4]) * quantity / 2;
            const int64_t health = static_cast<int64_t>(creature[0x64 / 4]) * quantity;
            if (quantity < 1 || damage < 0 || damage > INT_MAX || health < 0 || health > INT_MAX) return false;
            Aggregate candidate{};
            candidate.damage = static_cast<int>(damage);
            candidate.attack = static_cast<float>(creature[0x44 / 4]);
            candidate.multiplier = 1.0f;
            candidate.health = static_cast<int>(health);
            candidate.defence = static_cast<float>(creature[0x48 / 4]);
            g_publicPlacementScore[index] = evaluate(&candidate, &reference);
            pairs[count++] = {g_publicPlacementScore[index], static_cast<uint32_t>(index)};
        }
        // 859670 passes width-depth-6 to 85aba0 for non-shooter groups.
        // Neutral depth2 is the pinned Universe branch currently implemented;
        // other entry/depth paths still require independent reconstruction.
        g_publicSortDistance = *reinterpret_cast<const int*>(g_outputStorage + 8 + 384) - 2 - 6;
        const uintptr_t comparator = g_superadminEnabled && (!g_predictedDefensive || g_useSpreadRows) && role != 1
            ? reinterpret_cast<uintptr_t>(PublicPlacementPairBefore) : 0x85a4f0;
        sort(pairs, pairs + count, comparator);
        for (unsigned index = 0; index < count; ++index) {
            const uint32_t sourceIndex = pairs[index].sourceIndex;
            reinterpret_cast<uint32_t*>(g_outputStorage + 8 + 924)[sourceIndex] = destination;
            g_orderedPublicTypes[destination] = g_publicTypes[sourceIndex];
            *reinterpret_cast<uint32_t*>(g_outputStorage + 8 + 832 + destination * 4) = quantities[sourceIndex];
            ++destination;
        }
    }
    g_plannedProjectionCount = static_cast<int>(destination);
    if (g_superadminEnabled) {
        if (!g_predictedDefensive) {
            Pair ground[7]{};
            unsigned count = 0;
            for (LONG index = 0; index < g_publicCount; ++index) {
                if (g_predictionExcludedMask & (1u << index)) continue;
                const int* creature = definition(g_publicTypes[index]);
                // Category3 retries every small nonranged troop, including
                // supports and linked troops that failed an earlier phase.
                if (creature[0x4c / 4] <= 0 && creature[0xdc / 4] == 1) {
                    ground[count++] = {g_publicPlacementScore[index], static_cast<uint32_t>(index)};
                }
            }
            sort(ground, ground + count, reinterpret_cast<uintptr_t>(PublicPlacementPairBefore));
            for (unsigned index = 0; index < count; ++index) {
                g_groundRetryOrder[index] = reinterpret_cast<uint32_t*>(g_outputStorage + 8 + 924)[ground[index].sourceIndex];
            }
        }
        int shooters = 0;
        for (LONG index = 0; index < g_publicCount; ++index) {
            if (g_predictionExcludedMask & (1u << index)) continue;
            const int* creature = definition(g_publicTypes[index]);
            if (creature != nullptr && PlacementHasShooterCategory(g_publicTypes[index])) ++shooters;
        }
        *reinterpret_cast<int*>(g_outputStorage + 8 + 780) = shooters;
        return destination > 0;
    }
    return destination == static_cast<unsigned>(g_publicCount);
}

bool ExcludeWeakestProjection() {
    if (!g_superadminEnabled || g_sourceSimpleLayout) return false;
    struct Pair { int score; uint32_t sourceIndex; };
    Pair pairs[7]{};
    unsigned count = 0;
    for (LONG index = 0; index < g_publicCount; ++index) {
        if ((g_predictionExcludedMask & (1u << index)) == 0) {
            pairs[count++] = {g_publicPlacementScore[index], static_cast<uint32_t>(index)};
        }
    }
    if (count <= 1) return false;
    using Sort = void (__fastcall*)(Pair*, Pair*, uintptr_t);
    reinterpret_cast<Sort>(0x85a700)(pairs, pairs + count, 0x85a4f0);
    // 859b40 chooses the last globally score-sorted, non-excluded entry,
    // including an entry already placed during the failed attempt.
    g_predictionExcludedMask |= 1u << pairs[count - 1].sourceIndex;
    return PreparePublicOrder();
}

void ResetProjectionAttempt() {
    g_sourceFallbackPrepared = false;
    const int stride = *reinterpret_cast<const int*>(g_outputStorage + 8 + 524);
    const int height = *reinterpret_cast<const int*>(g_outputStorage + 8 + 528);
    if (stride > 0 && height > 0 && stride * height <= 1024) {
        memcpy(g_outputStorage + 8 + 1536, g_outputStorage + 8 + 2560, stride * height);
    }
    *reinterpret_cast<int*>(g_outputStorage + 8 + 496) = 0;
    g_protectiveCellCount = 0;
    g_definitionMaximum = 0;
    g_candidateIdentity = g_predictedDefensive ? 1 : 0;
    *reinterpret_cast<uint32_t*>(g_outputStorage + 8 + 908) = 0;
    *reinterpret_cast<uint32_t*>(g_outputStorage + 8 + 912) = 0;
    *reinterpret_cast<uint32_t*>(g_outputStorage + 8 + 952) = 0;
    *reinterpret_cast<uint32_t*>(g_outputStorage + 8 + 960) = 0;
    *reinterpret_cast<uint32_t*>(g_outputStorage + 8 + 964) = 0;
    *reinterpret_cast<uint32_t*>(g_outputStorage + 8 + 972) = 0;
}

bool CaptureSourceSimpleColumns() {
    g_sourceSimpleColumns = 0;
    __try {
        const auto* world = static_cast<const uint32_t*>(g_grid);
        if (!g_superadminEnabled || world == nullptr || world[0] != 0xe79d3c) return false;
        const auto* army = reinterpret_cast<const uint32_t*>(world[0x90 / 4]);
        if (army == nullptr || army[0] != 0xe17bcc) return false;
        const auto* methods = reinterpret_cast<const uint32_t*>(army[0]);
        int rectangle[4]{};
        reinterpret_cast<void (__thiscall*)(const void*, int*)>(methods[0xb0 / 4])(army, rectangle);
        const int width = *reinterpret_cast<const int*>(g_outputStorage + 8 + 384);
        const int height = *reinterpret_cast<const int*>(g_outputStorage + 8 + 388);
        const int columns = rectangle[2] - rectangle[0] + 1;
        if (columns < 2 || columns > 3 || rectangle[2] != width - 3
            || rectangle[1] != 1 || rectangle[3] != height - 2) return false;
        g_sourceSimpleColumns = columns;
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) { return false; }
}

bool ApplySourceComposition() {
    if (!g_superadminEnabled || g_sourceComposition[0] != 1) return true;
    const uint32_t count = g_sourceComposition[12];
    if (g_superadminSourceCount != 1 || count == 0 || count > 4) return false;
    uint32_t total = 0;
    for (uint32_t index = 0; index < count; ++index) {
        const uint32_t type = g_sourceComposition[16 + index * 2];
        const uint32_t quantity = g_sourceComposition[17 + index * 2];
        const auto* definition = reinterpret_cast<const uint32_t* (__fastcall*)(uint32_t)>(kCreatureDefinition)(type);
        if (!definition || quantity == 0 || definition[0xdc / 4] < 1 || definition[0xdc / 4] > 2) return false;
        total += quantity;
    }
    if (total != g_superadminSourceCounts[0]) return false;
    if (!CaptureSourceSimpleColumns()) return false;
    g_sourceFallbackPrepared = false;
    const uint32_t band = g_publicBands[0];
    for (uint32_t index = 0; index < count; ++index) {
        g_publicTypes[index] = g_sourceComposition[16 + index * 2];
        g_publicBands[index] = band;
    }
    g_publicCount = count;
    g_sourceSimpleLayout = true;
    return true;
}

bool CalculateSourceFallbackCells(int width, int height, int columns, const int* sizes,
                                 const bool* shooters, int count, uint32_t placed,
                                 const unsigned char* occupied, int stride, int* output) {
    if (width < 8 || width > 32 || height < 4 || height > 32 || columns < 2 || columns > 3
        || count < 1 || count > 7 || (placed >> count) != 0 || sizes == nullptr || shooters == nullptr
        || occupied == nullptr || output == nullptr || stride < (width + 7) / 8
        || stride > 1024 / height) return false;
    unsigned char scratch[1024]{};
    memcpy(scratch, occupied, stride * height);
    int cells[7];
    for (int index = 0; index < count; ++index) {
        if (sizes[index] < 1 || sizes[index] > 2) return false;
        cells[index] = -1;
    }
    // Native859930 pass order;858ba0 preserves source-record order.
    const int passes[7][3] = {{2,0,1},{1,0,1},{2,1,0},{1,2,0},{2,0,0},{1,1,0},{1,0,0}};
    for (int pass = 0; pass < 7; ++pass) {
        if ((pass == 2 || pass == 3) && columns == 2) continue;
        const int size = passes[pass][0], column = passes[pass][1];
        int row = size - 1;
        for (int index = 0; index < count; ++index) {
            if ((placed & (1u << index)) || sizes[index] != size || (passes[pass][2] && !shooters[index])) continue;
            bool found = false;
            for (; row < height - 2; ++row) {
                const int x = width - 3 - column, y = row + 1;
                if (column + size > columns || row < size - 1) break;
                bool free = true;
                for (int dy = 0; dy < size; ++dy) {
                    for (int dx = 0; dx < size; ++dx) {
                        const int line = y - dy, position = x - dx;
                        if (scratch[line * stride + position / 8] & (1u << (position & 7))) free = false;
                    }
                }
                if (!free) continue;
                for (int dy = 0; dy < size; ++dy) {
                    for (int dx = 0; dx < size; ++dx) {
                        const int line = y - dy, position = x - dx;
                        scratch[line * stride + position / 8] |= static_cast<unsigned char>(1u << (position & 7));
                    }
                }
                cells[index] = (x << 8) | y;
                placed |= 1u << index;
                found = true;
                break;
            }
            if (!found) break; // Native helper stops this pass at its first exhausted stack.
        }
    }
    memcpy(output, cells, count * sizeof(int));
    return true;
}

int ChooseSourceFallbackCell() {
    if (!g_sourceFallbackPrepared) {
        const int width = *reinterpret_cast<const int*>(g_outputStorage + 8 + 384);
        const int height = *reinterpret_cast<const int*>(g_outputStorage + 8 + 388);
        const int stride = *reinterpret_cast<const int*>(g_outputStorage + 8 + 524);
        int sizes[4]{}; bool shooters[4]{};
        if (g_plannedProjectionCount < 1 || g_plannedProjectionCount > 4) return -1;
        for (int slot = 0; slot < g_plannedProjectionCount; ++slot) {
            const auto* definition = reinterpret_cast<const int* (__fastcall*)(uint32_t)>(kCreatureDefinition)(g_orderedPublicTypes[slot]);
            if (definition == nullptr) return -1;
            sizes[slot] = definition[0xdc / 4];
            shooters[slot] = definition[0x4c / 4] > 0; // Native4d89f0, distinct from physical-shot capability.
        }
        const uint32_t placed = *reinterpret_cast<const uint32_t*>(g_outputStorage + 8 + 908);
        if (!CalculateSourceFallbackCells(width, height, g_sourceSimpleColumns, sizes, shooters,
                g_plannedProjectionCount, placed, g_outputStorage + 8 + 1536, stride, g_sourceFallbackCells)) return -1;
        g_sourceFallbackPrepared = true;
    }
    return g_definitionMaximum < static_cast<uint32_t>(g_plannedProjectionCount)
        ? g_sourceFallbackCells[g_definitionMaximum] : -1;
}

int ChooseSourceSimpleCell() {
    // Render the frozen successful anchors without recomputing rows after
    // compacting unplaced source records out of the render order.
    if (!g_projectionPlanning) {
        return g_definitionMaximum < static_cast<uint32_t>(g_plannedProjectionCount)
            ? g_sourceFallbackCells[g_definitionMaximum] : -1;
    }
    auto& failed = *reinterpret_cast<uint32_t*>(g_outputStorage + 8 + 972);
    if (failed) return ChooseSourceFallbackCell();
    failed = 1;
    const int width = *reinterpret_cast<const int*>(g_outputStorage + 8 + 384);
    const int height = *reinterpret_cast<const int*>(g_outputStorage + 8 + 388);
    const int stride = *reinterpret_cast<const int*>(g_outputStorage + 8 + 524);
    const int size = reinterpret_cast<intptr_t>(g_creatureDefinition);
    const int rows = height - 2;
    if (!g_sourceSimpleLayout || width < 8 || width > 32 || rows < 2 || rows > 30
        || stride < (width + 7) / 8 || size < 1 || size > 2) return -1;
    int total = 0;
    for (int index = 0; index < g_plannedProjectionCount; ++index) {
        const auto* definition = reinterpret_cast<const uint32_t* (__fastcall*)(uint32_t)>(kCreatureDefinition)(g_orderedPublicTypes[index]);
        if (!definition || definition[0xdc / 4] < 1 || definition[0xdc / 4] > 2) return -1;
        total += definition[0xdc / 4];
    }
    if (total > rows) return ChooseSourceFallbackCell();
    int row = *reinterpret_cast<const int*>(g_outputStorage + 8 + 960);
    const int cumulative = *reinterpret_cast<const int*>(g_outputStorage + 8 + 964);
    while (row < rows && ((2 * row - size + 3) * total <= (size + 2 * cumulative) * rows)) ++row;
    const auto* occupied = g_outputStorage + 8 + 1536;
    for (; row < rows; ++row) {
        for (int localColumn = 0; localColumn <= g_sourceSimpleColumns - size; ++localColumn) {
            const int x = width - 3 - localColumn, y = row + 1;
            if (y < size) continue;
            bool free = true;
            for (int dy = 0; dy < size; ++dy) {
                for (int dx = 0; dx < size; ++dx) {
                    const int column = x - dx, line = y - dy;
                    if (occupied[line * stride + column / 8] & (1 << (column & 7))) free = false;
                }
            }
            if (free) {
                failed = 0;
                *reinterpret_cast<int*>(g_outputStorage + 8 + 960) = row;
                *reinterpret_cast<int*>(g_outputStorage + 8 + 964) = cumulative + size;
                return (x << 8) | y;
            }
        }
    }
    return ChooseSourceFallbackCell();
}

bool FinalizeSourceSimplePlan() {
    if (!g_sourceSimpleLayout || g_publicCount < 1 || g_publicCount > 4) return false;
    const uint32_t placed = *reinterpret_cast<const uint32_t*>(g_outputStorage + 8 + 908);
    const uint32_t valid = (1u << g_publicCount) - 1;
    if ((placed & ~valid) != 0 || placed == 0) return false;
    unsigned count = 0;
    for (LONG index = 0; index < g_publicCount; ++index) count += (placed >> index) & 1u;
    if (count != *reinterpret_cast<const uint32_t*>(g_outputStorage + 8 + 496)) return false;
    // Simple85a110 returns after one fallback. Only placed records create
    // observed units; preserve their quantities and anchors, without a retry.
    unsigned destination = 0;
    for (LONG index = 0; index < g_publicCount; ++index) {
        if ((placed & (1u << index)) == 0) {
            reinterpret_cast<uint32_t*>(g_outputStorage + 8 + 924)[index] = UINT_MAX;
            continue;
        }
        g_orderedPublicTypes[destination] = g_orderedPublicTypes[index];
        reinterpret_cast<uint32_t*>(g_outputStorage + 8 + 832)[destination]
            = reinterpret_cast<const uint32_t*>(g_outputStorage + 8 + 832)[index];
        reinterpret_cast<uint32_t*>(g_outputStorage + 8 + 924)[index] = destination;
        g_sourceFallbackCells[destination] = (g_cell[destination * 2] << 8) | g_cell[destination * 2 + 1];
        ++destination;
    }
    g_predictionExcludedMask = valid & ~placed;
    g_plannedProjectionCount = static_cast<int>(count);
    return true;
}

bool __fastcall PublicPlacementPairBefore(const int* left, const int* right) {
    const uint32_t leftIndex = static_cast<uint32_t>(left[1]);
    const uint32_t rightIndex = static_cast<uint32_t>(right[1]);
    if (leftIndex >= 7 || rightIndex >= 7) return false;
    const uint32_t leftFlying = g_publicSortFlying[leftIndex];
    const uint32_t rightFlying = g_publicSortFlying[rightIndex];
    if (leftFlying != rightFlying) return leftFlying < rightFlying;
    const int leftSpeed = g_publicSortSpeed[leftIndex];
    const int rightSpeed = g_publicSortSpeed[rightIndex];
    if ((leftSpeed >= g_publicSortDistance || rightSpeed >= g_publicSortDistance)
        && leftSpeed != rightSpeed) return leftSpeed > rightSpeed;
    return left[0] > right[0];
}

int PublicPlacementRole(uint32_t type) {
    using Definition = const int* (__fastcall*)(uint32_t);
    using Ability = bool (__fastcall*)(uint32_t, uint32_t);
    const auto definition = reinterpret_cast<Definition>(kCreatureDefinition);
    const auto ability = reinterpret_cast<Ability>(0xb61ba0);
    const int* creature = definition(type);
    if (creature == nullptr) return -1;
    if (!g_superadminEnabled) {
        return PlacementHasPhysicalShot(type) ? 1 : (creature[0xdc / 4] == 2 ? 0 : 2);
    }
    if (g_predictedDefensive) {
        if (PlacementHasShooterCategory(type)) return 1;
        return creature[0xdc / 4] == 2 && !ability(0x2f, type) ? 0 : 2;
    }
    // Render each stack in its earliest ordinary phase: categories2,4,8/9,5,3.
    // Categories overlap: an earlier large/shooter carrier still contributes
    // its anchor to 858fb0's category8 neighbour lists.
    if (creature[0x4c / 4] <= 0 && creature[0xdc / 4] == 2 && !ability(0x2f, type)) return 0;
    if (PlacementHasShooterCategory(type)) return 1;
    if (ability(0x72, type) || ability(0x79, type) || ability(0x7a, type)) return 2;
    const uint32_t baseType = creature[0x100 / 4] != 0 ? creature[0x100 / 4] : type;
    if (baseType == 0x75) {
        for (LONG index = 0; index < g_publicCount; ++index) {
            if (g_predictionExcludedMask & (1u << index)) continue;
            const uint32_t carrier = g_publicTypes[index];
            const int* carrierDefinition = definition(carrier);
            if (carrierDefinition != nullptr
                && (ability(0x72, carrier) || ability(0x79, carrier) || ability(0x7a, carrier))) return 3;
        }
    }
    if (ability(0x2f, type) || ability(0x1b, type)) return 4;
    return 5;
}

int ChooseLinkedGoblinCell() {
    if (!g_superadminEnabled || g_definitionMaximum >= static_cast<uint32_t>(g_publicCount)) return -1;
    using Definition = const int* (__fastcall*)(uint32_t);
    using Ability = bool (__fastcall*)(uint32_t, uint32_t);
    const auto definition = reinterpret_cast<Definition>(kCreatureDefinition);
    const auto ability = reinterpret_cast<Ability>(0xb61ba0);
    const uint32_t type = g_orderedPublicTypes[g_definitionMaximum];
    const int* creature = definition(type);
    if (creature == nullptr || static_cast<uint32_t>(creature[0x100 / 4] != 0
        ? creature[0x100 / 4] : type) != 0x75) return -1;
    const int width = *reinterpret_cast<const int*>(g_outputStorage + 8 + 384);
    const int height = *reinterpret_cast<const int*>(g_outputStorage + 8 + 388);
    const int stride = *reinterpret_cast<const int*>(g_outputStorage + 8 + 524);
    const int count = *reinterpret_cast<const int*>(g_outputStorage + 8 + 496);
    if (width < 8 || width > 32 || height < 4 || height > 32
        || stride < (width + 7) / 8 || count < 0 || count > 7) return -1;
    int neighbours[7][12][2]{};
    int lengths[7]{};
    bool active[7]{};
    int carriers = 0;
    const auto* occupied = g_outputStorage + 8 + 1536;
    // b3d010's size1/radius1 ring starts at the right neighbour, then
    // traverses the upper, left and lower edges. Preserve this tie order.
    constexpr int offsets[8][2] = {
        {1, 0}, {1, 1}, {0, 1}, {-1, 1},
        {-1, 0}, {-1, -1}, {0, -1}, {1, -1},
    };
    constexpr int largeOffsets[12][2] = {
        {1, -1}, {1, 0}, {1, 1}, {0, 1}, {-1, 1}, {-2, 1},
        {-2, 0}, {-2, -1}, {-2, -2}, {-1, -2}, {0, -2}, {1, -2},
    };
    for (int index = 0; index < count; ++index) {
        const uint32_t type = *reinterpret_cast<const uint32_t*>(g_outputStorage + 8 + 640 + index * 4);
        if (!ability(0x72, type) && !ability(0x79, type) && !ability(0x7a, type)) continue;
        const int* carrierDefinition = definition(type);
        if (carrierDefinition == nullptr) continue;
        const int size = carrierDefinition[0xdc / 4];
        if (size < 1 || size > 2) continue;
        const int anchorX = g_cell[index * 2];
        const int anchorY = g_cell[index * 2 + 1];
        active[carriers] = true;
        const auto* ring = size == 2 ? largeOffsets : offsets;
        const int ringCount = size == 2 ? 12 : 8;
        for (int point = 0; point < ringCount; ++point) {
            const auto& offset = ring[point];
            const int x = anchorX + offset[0];
            const int y = anchorY + offset[1];
            if (x < width - 4 || x > width - 3 || y < 1 || y > height - 2) continue;
            // 858fb0 removes every carrier list covered by a previously
            // accepted goblin cell, not merely that one occupied candidate.
            for (int previous = 0; previous < count; ++previous) {
                const uint32_t previousType = *reinterpret_cast<const uint32_t*>(
                    g_outputStorage + 8 + 640 + previous * 4);
                const int* previousDefinition = definition(previousType);
                const uint32_t previousBase = previousDefinition != nullptr && previousDefinition[0x100 / 4] != 0
                    ? previousDefinition[0x100 / 4] : previousType;
                if (previousBase == 0x75 && g_cell[previous * 2] == x && g_cell[previous * 2 + 1] == y) {
                    active[carriers] = false;
                }
            }
            if ((occupied[y * stride + x / 8] & (1 << (x & 7))) != 0) continue;
            const int destination = lengths[carriers]++;
            neighbours[carriers][destination][0] = x;
            neighbours[carriers][destination][1] = y;
        }
        ++carriers;
    }
    for (int first = 0; first < carriers; ++first) {
        if (!active[first] || lengths[first] == 0) continue;
        int best = -1;
        int coverage = 0;
        for (int candidate = 0; candidate < lengths[first]; ++candidate) {
            const int x = neighbours[first][candidate][0];
            const int y = neighbours[first][candidate][1];
            int covered = 1;
            for (int other = first + 1; other < carriers; ++other) {
                if (!active[other]) continue;
                for (int point = 0; point < lengths[other]; ++point) {
                    if (neighbours[other][point][0] == x && neighbours[other][point][1] == y) {
                        ++covered;
                        break;
                    }
                }
            }
            if (covered > coverage) {
                coverage = covered;
                best = candidate;
            }
        }
        if (best >= 0) return (neighbours[first][best][0] << 8) | neighbours[first][best][1];
    }
    return -1;
}

bool __cdecl SpreadRowAllowed(int role, int row) {
    const int lastPrimaryRole = g_superadminEnabled ? 5 : 2;
    if (!g_useSpreadRows || g_spreadFallback || role < 0 || role > lastPrimaryRole) return true;
    // 0x858700 spaces rows by the complete placement-record vector length,
    // even when the current pass places only one role from that vector.
    const int count = g_publicCount;
    if (count < 2) return true;
    const int rows = *reinterpret_cast<const int*>(g_outputStorage + 8 + 388) - 2;
    if (rows < 2) return true;
    // 0x857160 maps every local row r to battlefield y=r+1. A 2x2 creature
    // cannot use y=1, but the remaining spread rows are not shifted.
    const int footprint = reinterpret_cast<intptr_t>(g_creatureDefinition);
    const int zeroBased = row - 1;
    const int step = (rows - 1) / (count - 1);
    // Local row zero itself fails the 2x2 footprint check; its first legal
    // anchor y=2 competes with the other spaced rows using row score first.
    // On an equal score its retained local-zero tie rank loses to later rows.
    bool selected = zeroBased == rows - 1 || (footprint == 2 && row == 2);
    for (int index = 0; index < count - 1; ++index) {
        if (zeroBased == index * step) selected = true;
    }
    if (!selected) return false;
    // Native 0x857930 drops a spread row when the front deployment lane is
    // occupied, provided at least one selected row remains clear. The current
    // predictor uses this proven 1x1 case; 2x2 filtering needs a separate trace.
    if (footprint != 1) return true;
    const int width = *reinterpret_cast<const int*>(g_outputStorage + 8 + 384);
    const int stride = *reinterpret_cast<const int*>(g_outputStorage + 8 + 524);
    if (width < 8 || stride < 1) return true;
    const int front = width - 3;
    const auto* occupied = g_outputStorage + 8 + 1536;
    const auto frontOccupied = [&](int candidate) {
        return (occupied[(candidate + 1) * stride + front / 8] & (1 << (front & 7))) != 0;
    };
    bool hasClear = !frontOccupied(rows - 1);
    for (int index = 0; index < count - 1; ++index) {
        if (!frontOccupied(index * step)) hasClear = true;
    }
    return !hasClear || !frontOccupied(zeroBased);
}

void ResetSuperadminInputCapture() {
    InterlockedIncrement(&g_actorInputSequence);
    g_actorInputCount = 0;
    g_actorInputOverflow = 0;
    g_actorInputGeneration = g_attackGeneration;
    g_actorInputWorld = 0;
    g_actorCoreMask = 0;
    memset(g_actorCoreInputEnds, 0, sizeof(g_actorCoreInputEnds));
    memset(g_strategyTrace, 0, sizeof(g_strategyTrace));
    g_heroCorrectionCount = 0;
    g_heroCorrectionOverflow = 0;
    g_heroCorrectionMask = 0;
    g_auxiliaryInputCount = 0;
    g_auxiliaryInputOverflow = 0;
    g_auxiliaryMask = 0;
    g_sourceStrengthCount = 0;
    g_sourceStrengthOverflow = 0;
    g_areaInputCount = 0;
    g_areaInputOverflow = 0;
    memset(g_areaPolicyTrace, 0, sizeof(g_areaPolicyTrace));
    memset(g_largePolicyTrace, 0, sizeof(g_largePolicyTrace));
    memset(g_sourceSplitSeed, 0, sizeof(g_sourceSplitSeed));
    memset(g_sourceComposition, 0, sizeof(g_sourceComposition));
    g_sourceSimpleLayout = false;
    g_sourceSimpleColumns = 0;
    g_sourceFallbackPrepared = false;
    memset(g_actorCoreStackCounts, 0, sizeof(g_actorCoreStackCounts));
    memset(g_actorCoreWords, 0, sizeof(g_actorCoreWords));
    g_actorInputsFrozen = !g_superadminEnabled;
    InterlockedIncrement(&g_actorInputSequence);
}

void FreezeSuperadminInputCapture() {
    if (!g_superadminEnabled) return;
    InterlockedIncrement(&g_actorInputSequence);
    g_actorInputsFrozen = true;
    g_actorInputWorld = reinterpret_cast<uint32_t>(g_grid);
    InterlockedIncrement(&g_actorInputSequence);
}

void __cdecl CaptureSuperadminActorInput(const uint32_t* actor, uint32_t aggregateIdentity,
                                        uint32_t damage, uint32_t selected, uint32_t specialCategory) {
    if (!g_superadminEnabled || g_actorInputsFrozen || g_actorInputBusy
        || g_actorInputGeneration != g_attackGeneration || g_attackGeneration == 0) return;
    if (static_cast<uint32_t>(g_actorInputCount) >= kActorInputCapacity) {
        g_actorInputOverflow = 1;
        return;
    }
    g_actorInputBusy = true;
    FrozenActorInput input{};
    input.damage = damage;
    input.aggregateIdentity = aggregateIdentity;
    input.specialCategory = specialCategory & 255;
    input.attackGeneration = g_attackGeneration;
    uint16_t controlWord;
    __asm fnstcw controlWord
    input.controlWord = controlWord;
    if (actor == nullptr || actor[0] != 0xe4fba4) {
        input.unsupported = 1;
    } else {
        const auto* methods = reinterpret_cast<const uint32_t*>(actor[0]);
        const auto integer = [&](uint32_t offset) {
            return reinterpret_cast<int32_t (__thiscall*)(const void*)>(methods[offset / 4])(actor);
        };
        const auto floating = [&](uint32_t offset) {
            return reinterpret_cast<float (__thiscall*)(const void*)>(methods[offset / 4])(actor);
        };
        const auto boolean = [&](uint32_t offset) {
            return reinterpret_cast<bool (__thiscall*)(const void*)>(methods[offset / 4])(actor);
        };
        const auto flag = [&](uint32_t value) {
            return reinterpret_cast<bool (__thiscall*)(const void*, uint32_t)>(methods[0x28c / 4])(actor, value);
        };
        const auto status = [&](uint32_t value) {
            return reinterpret_cast<uint32_t (__thiscall*)(const void*, uint32_t)>(methods[0x28 / 4])(actor, value);
        };
        input.world = integer(8);
        if (input.world == 0 || *reinterpret_cast<const uint32_t*>(input.world) != 0xe79d3c) input.unsupported |= 128;
        input.army = integer(0xc);
        input.attack = integer(0x198);
        input.defence = integer(0x19c);
        input.health = reinterpret_cast<int32_t (__thiscall*)(const void*, uint32_t)>(methods[0x1dc / 4])(
            actor, integer(0x20));
        input.initiative = floating(0x1bc);
        const auto* timer = reinterpret_cast<const float*>(integer(0x184));
        if (timer != nullptr) input.atb = timer[0x1c / 4];
        else input.unsupported |= 2;
        input.morale = integer(0x1ac);
        input.luck = integer(0x1b0);
        input.speed = integer(0x48);
        const bool shooter = boolean(0x1e0);
        input.rangedCapability = shooter || reinterpret_cast<int (__fastcall*)(const void*)>(0xbfa4f0)(actor) > 0;
        input.ignoreWhenNoRanged = flag(0x37) && flag(5);
        const auto* army = reinterpret_cast<const uint32_t*>(input.army);
        if (army != nullptr && army[0] == 0xe17bcc && army[0x2c / 4] >= army[0x28 / 4]
            && (army[0x2c / 4] - army[0x28 / 4]) % 4 == 0) {
            input.armySize = (army[0x2c / 4] - army[0x28 / 4]) / 4;
        } else input.unsupported |= 256;
        bool excludedCategory = false;
        const auto* role = reinterpret_cast<const uint32_t*>(integer(0x7c));
        if (role != nullptr) {
            const auto* roleMethods = reinterpret_cast<const uint32_t*>(role[0]);
            const auto* definition = reinterpret_cast<const uint32_t* (__thiscall*)(const void*)>(roleMethods[0])(role);
            excludedCategory = definition != nullptr && definition[0x1c / 4] == 2;
        }
        input.category = SelectPlacementDamageCategory(excludedCategory, shooter, !shooter && boolean(0x190),
                                                        input.specialCategory != 0, input.ignoreWhenNoRanged != 0);
        input.skipSpeed = (flag(1) ? 1u : 0u) | ((flag(4) && shooter) ? 2u : 0u) | (shooter ? 4u : 0u);
        input.selected = reinterpret_cast<uint32_t>(actor) == selected;
        input.retaliationBonus = boolean(0x1e4) && !flag(0x22);
        const auto* source = reinterpret_cast<const uint32_t*>(integer(0x6c));
        if (source != nullptr) {
            const auto* sourceMethods = reinterpret_cast<const uint32_t*>(source[0]);
            const auto* descriptor = reinterpret_cast<const uint32_t* (__thiscall*)(const void*)>(sourceMethods[0])(source);
            if (descriptor != nullptr) {
                input.source = reinterpret_cast<uint32_t>(descriptor);
                input.type = descriptor[0x1c / 4];
                input.quantity = descriptor[0x20 / 4];
                input.counterMaximum[1] = reinterpret_cast<int (__thiscall*)(const void*)>(0x4bab70)(descriptor);
                input.counterMaximum[2] = reinterpret_cast<int (__thiscall*)(const void*)>(0x4bab80)(descriptor);
                input.counterCurrent[1] = reinterpret_cast<int (__thiscall*)(const void*)>(sourceMethods[0x2c / 4])(source);
                input.counterCurrent[2] = reinterpret_cast<int (__thiscall*)(const void*)>(sourceMethods[0x34 / 4])(source);
            } else input.unsupported |= 4;
            if (integer(0) == 1) {
                const auto* secondary = reinterpret_cast<const int32_t*>(source[1]);
                const void* eligible = reinterpret_cast<const unsigned char*>(source) + 4 + secondary[2];
                const auto* eligibleMethods = *reinterpret_cast<const uint32_t* const*>(eligible);
                input.eligible = !reinterpret_cast<bool (__thiscall*)(const void*)>(eligibleMethods[0x58 / 4])(eligible);
            }
        } else input.unsupported |= 4;
        if ((input.skipSpeed & 1u) && !shooter) input.unsupported |= 8;
        input.counterMaximum[0] = integer(0x238);
        input.counterCurrent[0] = integer(0x234);
        if (reinterpret_cast<float (__fastcall*)(const void*)>(0xbfb3d0)(actor) != 0) input.unsupported |= 32;
        const uint32_t effects[] = {0x28u, 0x22u, 0x1du, 0x13du, 0x13u, 0xc9u, 0x14au, 0x150u, 0x9fu, 0x11u};
        for (const uint32_t effect : effects) {
            if (status(effect)) input.unsupported |= 64;
        }
        if (flag(0x28)) {
            const bool alternative = status(0x100) != 0;
            input.healthTransformFlags = alternative ? 3 : 1;
            const double scale = *reinterpret_cast<const double*>(alternative ? 0xe72bf8 : 0xe87cf8);
            memcpy(input.healthScaleBits, &scale, sizeof(scale));
        }
    }
    if (!g_actorInputsFrozen && input.attackGeneration == static_cast<uint32_t>(g_actorInputGeneration)) {
        InterlockedIncrement(&g_actorInputSequence);
        g_actorInputs[g_actorInputCount] = input;
        ++g_actorInputCount;
        InterlockedIncrement(&g_actorInputSequence);
    }
    g_actorInputBusy = false;
}

__declspec(naked) void ActorInputHook() {
    __asm {
        pushfd
        pushad
        mov ebx, esp
        sub esp, 528
        and esp, -16
        fxsave [esp]
        push dword ptr [ebx + 84]
        push dword ptr [ebx + 76]
        push dword ptr [ebx + 8]
        push dword ptr [ebx]
        push dword ptr [ebx + 4]
        call CaptureSuperadminActorInput
        add esp, 20
        fxrstor [esp]
        mov esp, ebx
        popad
        popfd
        fld dword ptr [esp + 0x24]
        fadd dword ptr [ebx + 4]
        jmp kActorInputResume
    }
}

void __cdecl CaptureSourceStrengthInput(const uint32_t* source, const uint32_t* context, uint32_t phase) {
    if (!g_superadminEnabled || g_actorInputsFrozen || g_sourceStrengthBusy
        || g_actorInputGeneration != g_attackGeneration) return;
    SourceStrengthInput input{};
    memset(&input, 0, sizeof(input));
    uint32_t controlWord = 0, unsupported = 0, type = 0;
    g_sourceStrengthBusy = true;
    __try {
        __asm { fnstcw word ptr controlWord }
        type = source[0x1c / 4];
        const auto* definition = reinterpret_cast<const int* (__fastcall*)(uint32_t)>(kCreatureDefinition)(type);
        if (definition == nullptr || static_cast<int>(source[0x20 / 4]) <= 0
            || *reinterpret_cast<const unsigned char*>(0x10c5178) == 0) {
            unsupported = 1;
        } else {
            input.baseValue = definition[0x84 / 4];
            input.quantity = static_cast<int>(source[0x20 / 4]);
            using Stat = int (__thiscall*)(const void*, const void*, uint32_t);
            const auto health = reinterpret_cast<Stat>(0x4bc470);
            const auto maximum = reinterpret_cast<Stat>(0x4bbfb0);
            const auto minimum = reinterpret_cast<Stat>(0x4bc020);
            const auto attack = reinterpret_cast<Stat>(0x4bb170);
            const auto defence = reinterpret_cast<Stat>(0x4bb2a0);
            input.deltas[0] = static_cast<int>(static_cast<uint32_t>(health(source, context, phase))
                - static_cast<uint32_t>(definition[0x64 / 4]));
            input.deltas[1] = static_cast<int>(static_cast<uint32_t>(maximum(source, context, phase))
                + static_cast<uint32_t>(minimum(source, context, phase))
                - static_cast<uint32_t>(definition[0x54 / 4]) - static_cast<uint32_t>(definition[0x50 / 4]));
            input.deltas[2] = static_cast<int>(static_cast<uint32_t>(attack(source, nullptr, phase))
                + static_cast<uint32_t>(defence(source, nullptr, phase))
                - static_cast<uint32_t>(definition[0x44 / 4]) - static_cast<uint32_t>(definition[0x48 / 4]));
            const auto* extras = reinterpret_cast<const signed char*>(source) + 0x38;
            input.deltas[3] = extras[8]; input.deltas[4] = extras[9]; input.deltas[5] = extras[12];
            input.modifierA = reinterpret_cast<int (__thiscall*)(const void*, uint32_t)>(0x4bb3c0)(source, phase);
            input.modifierB = reinterpret_cast<Stat>(0x4bb3f0)(source, context, phase);
            if (context != nullptr) {
                const auto* methods = reinterpret_cast<const uint32_t*>(context[0]);
                if (definition[0x4c / 4] > 0) {
                    input.shooterBonus = reinterpret_cast<int (__thiscall*)(const void*)>(methods[0x324 / 4])(context) > 0;
                }
                const auto owner = reinterpret_cast<const uint32_t* (__thiscall*)(const void*)>(methods[0x54 / 4])(context);
                if (owner != nullptr) {
                    const auto* ownerMethods = reinterpret_cast<const uint32_t*>(owner[0]);
                    input.modifierPenalty = reinterpret_cast<int (__thiscall*)(const void*, int)>(ownerMethods[0x34 / 4])(owner, 4) > 0;
                }
            }
            input.baseInitiative = definition[0x5c / 4];
            void* initiative = input.initiativeBits;
            const uintptr_t getter = 0x4bc190;
            __asm {
                push phase
                push context
                mov ecx, source
                call getter
                mov eax, initiative
                fstp tbyte ptr [eax]
            }
            memcpy(input.coefficients, reinterpret_cast<const void*>(0x10c5480 + 0x250), sizeof(input.coefficients));
            memcpy(&input.baseScale, reinterpret_cast<const void*>(0xe0d608), sizeof(double));
            memcpy(&input.one, reinterpret_cast<const void*>(0xe12e00), sizeof(double));
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) { unsupported = 2; }
    for (uint32_t index = 0; index < g_sourceStrengthCount; ++index) {
        const auto& previous = g_sourceStrengthInputs[index];
        if (previous.metadata[0] == reinterpret_cast<uint32_t>(source)
            && previous.metadata[1] == reinterpret_cast<uint32_t>(context)
            && previous.metadata[2] == phase && previous.metadata[3] == type
            && previous.metadata[4] == controlWord && previous.metadata[5] == g_actorInputGeneration
            && previous.metadata[6] == unsupported && memcmp(previous.inputWords, &input, sizeof(input)) == 0) {
            g_sourceStrengthBusy = false;
            return;
        }
    }
    if (g_sourceStrengthCount >= 256) {
        g_sourceStrengthOverflow = 1;
        g_sourceStrengthBusy = false;
        return;
    }
    int64_t value = 0;
    if (unsupported == 0) {
        unsigned short selected = static_cast<unsigned short>(controlWord);
        __asm { fldcw selected }
        value = CalculateSourceStrength(input);
    }
    InterlockedIncrement(&g_actorInputSequence);
    auto& row = g_sourceStrengthInputs[g_sourceStrengthCount++];
    memset(&row, 0, sizeof(row));
    row.metadata[0] = reinterpret_cast<uint32_t>(source);
    row.metadata[1] = reinterpret_cast<uint32_t>(context);
    row.metadata[2] = phase; row.metadata[3] = type;
    row.metadata[4] = controlWord; row.metadata[5] = g_actorInputGeneration;
    row.metadata[6] = unsupported;
    memcpy(row.inputWords, &input, sizeof(input));
    memcpy(row.ownWords, &value, sizeof(value));
    InterlockedIncrement(&g_actorInputSequence);
    g_sourceStrengthBusy = false;
}

__declspec(naked) void SourceStrengthHook() {
    __asm {
        pushfd
        pushad
        mov ebx, esp
        sub esp, 528
        and esp, -16
        fxsave [esp]
        push dword ptr [ebp + 8]
        push dword ptr [ebx + 48]
        push esi
        call CaptureSourceStrengthInput
        add esp, 12
        fxrstor [esp]
        mov esp, ebx
        popad
        popfd
        mov edi, dword ptr [ebp + 8]
        mov edx, dword ptr [esp + 0xc]
        jmp kSourceStrengthResume
    }
}

void __cdecl CaptureSourceSplitSeed(const uint32_t* random) {
    if (!g_superadminEnabled || g_actorInputsFrozen || g_actorInputGeneration != g_attackGeneration) return;
    __try {
        if (random == nullptr || random[0] != 0xe51284) return;
        uint32_t control = 0;
        __asm { fnstcw word ptr control }
        InterlockedIncrement(&g_actorInputSequence);
        g_sourceSplitSeed[0] = reinterpret_cast<uint32_t>(random);
        g_sourceSplitSeed[1] = random[2];
        g_sourceSplitSeed[2] = g_actorInputGeneration;
        g_sourceSplitSeed[3] = control;
        InterlockedIncrement(&g_actorInputSequence);
    } __except (EXCEPTION_EXECUTE_HANDLER) { }
}

__declspec(naked) void SplitSeedHook() {
    __asm {
        pushfd
        pushad
        mov ebx, esp
        sub esp, 528
        and esp, -16
        fxsave [esp]
        push eax
        call CaptureSourceSplitSeed
        add esp, 4
        fxrstor [esp]
        mov esp, ebx
        popad
        popfd
        mov edx, dword ptr [eax]
        push 100
        push 1
        jmp kSplitSeedResume
    }
}

void PrepareSourceComposition(const uint32_t* owner) {
    if (!g_superadminEnabled) return;
    uint32_t result[24]{};
    result[15] = 1;
    if (g_actorInputsFrozen && g_sourceStrengthOverflow == 0 && g_superadminSourceCount == 1
        && g_sourceSplitSeed[0] && g_sourceSplitSeed[2] == static_cast<uint32_t>(g_actorInputGeneration)
        && owner && owner[3] && owner[4] >= owner[3] && (owner[4] - owner[3]) % 36 == 0
        && (owner[4] - owner[3]) / 36 <= 7) {
        uint32_t required = 0;
        const auto* begin = reinterpret_cast<const uint32_t*>(owner[3]);
        const auto* end = reinterpret_cast<const uint32_t*>(owner[4]);
        for (auto* record = begin; record != end; record += 9) if (record[2]) ++required;
        uint64_t totals[2]{};
        uint32_t counts[2]{};
        bool valid = required > 0;
        for (uint32_t index = 0; index < g_sourceStrengthCount && valid; ++index) {
            const auto& row = g_sourceStrengthInputs[index];
            if (!row.metadata[7]) continue;
            if (row.metadata[6] || row.metadata[5] != static_cast<uint32_t>(g_actorInputGeneration)
                || row.metadata[4] != g_sourceSplitSeed[3]) { valid = false; break; }
            for (uint32_t earlier = 0; earlier < index; ++earlier) {
                const auto& previous = g_sourceStrengthInputs[earlier];
                if (previous.metadata[7] == row.metadata[7] && previous.metadata[0] == row.metadata[0]) valid = false;
            }
            uint64_t value;
            memcpy(&value, row.ownWords, sizeof(value));
            const uint32_t side = row.metadata[7] == 1 ? 0 : 1;
            if (row.metadata[7] != 1 && row.metadata[7] != 2) valid = false;
            totals[side] += value;
            ++counts[side];
        }
        if (valid && counts[0] == required && counts[1] == 1) {
            const auto type = g_superadminSourceTypes[0], quantity = g_superadminSourceCounts[0];
            const auto* definition = reinterpret_cast<const uint32_t* (__fastcall*)(uint32_t)>(kCreatureDefinition)(type);
            if (definition) {
                const auto first = definition[0x104 / 4], last = definition[0x108 / 4];
                if (last >= first && (last - first) % 4 == 0 && (last - first) / 4 <= 32) {
                    double half, one;
                    memcpy(&half, reinterpret_cast<const void*>(0xf43e80), 8);
                    memcpy(&one, reinterpret_cast<const void*>(0xf43e78), 8);
                    CalculateSourceComposition(static_cast<int64_t>(totals[0]), static_cast<int64_t>(totals[1]),
                        g_sourceSplitSeed[1], static_cast<uint16_t>(g_sourceSplitSeed[3]), type, quantity,
                        static_cast<int>(definition[0xdc / 4]), reinterpret_cast<const uint32_t*>(first),
                        (last - first) / 4, half, one, result);
                }
            }
        }
    }
    InterlockedIncrement(&g_actorInputSequence);
    memcpy(g_sourceComposition, result, sizeof(result));
    InterlockedIncrement(&g_actorInputSequence);
}

bool BuildFrozenPlacementCore(const FrozenActorInput* inputs, uint32_t count,
                              uint32_t world, uint32_t army, uint32_t generation,
                              PlacementAggregate& result, uint32_t& stackCount, uint32_t* inputEnd = nullptr,
                              uint32_t includedMask = UINT_MAX) {
    stackCount = 0;
    if (inputEnd != nullptr) *inputEnd = 0;
    if (inputs == nullptr || count == 0 || count > kActorInputCapacity || world == 0 || army == 0) return false;
    const auto matches = [&](const FrozenActorInput& input) {
        return input.world == world && input.army == army && input.attackGeneration == generation;
    };
    uint32_t last = count;
    while (last != 0 && !matches(inputs[last - 1])) --last;
    if (last == 0) return false;
    const uint32_t identity = inputs[last - 1].aggregateIdentity;
    if (identity == 0) return false;
    uint32_t first = last - 1;
    while (first != 0 && matches(inputs[first - 1]) && inputs[first - 1].aggregateIdentity == identity) --first;
    if (last - first > 7) return false;
    for (uint32_t index = first; index < last; ++index) {
        const auto& input = inputs[index];
        if (input.unsupported || input.source == 0 || input.type == 0 || input.quantity == 0
            || input.controlWord > 0xffff || input.category > 3) return false;
        for (uint32_t earlier = first; earlier < index; ++earlier) {
            // A repeated source can mark an unobserved aggregate reset. Do not
            // merge distinct passes merely because a scratch address repeats.
            if (inputs[earlier].source == input.source) return false;
        }
    }
    PlacementAggregate aggregate;
    PlacementWeights weights;
    InitializePlacementAggregate(aggregate, weights);
    uint16_t originalControl;
    __asm fnstcw originalControl
    uint32_t includedCount = 0;
    for (uint32_t index = first; index < last; ++index) {
        if (!(includedMask & (1u << (index - first)))) continue;
        ++includedCount;
        const auto& input = inputs[index];
        const uint16_t control = static_cast<uint16_t>(input.controlWord);
        __asm fldcw control
        BaselineActionFactorInput action{input.morale, input.luck, input.speed, input.initiative, input.atb,
            (input.skipSpeed & 1u) != 0, input.selected != 0, input.retaliationBonus != 0};
        action.halfRangedFactor = (input.skipSpeed & 2u) != 0;
        memcpy(action.counterMaximum, input.counterMaximum, sizeof(action.counterMaximum));
        memcpy(action.counterCurrent, input.counterCurrent, sizeof(action.counterCurrent));
        AccumulatePlacementDamage(aggregate, weights, static_cast<int32_t>(input.damage), input.attack,
                                  BaselineActionFactor(action), input.category);
        const int32_t health = TransformPlacementHealth(input.health, input.healthTransformFlags, input.healthScaleBits);
        AccumulatePlacementHealth(aggregate, weights, health, input.defence, input.defence, input.eligible != 0);
    }
    NormalizePlacementAggregate(aggregate, weights);
    __asm fldcw originalControl
    result = aggregate;
    stackCount = includedCount;
    if (inputEnd != nullptr) *inputEnd = last;
    return true;
}

void PrepareSuperadminAggregates() {
    InterlockedIncrement(&g_actorInputSequence);
    g_actorCoreMask = 0;
    memset(g_actorCoreInputEnds, 0, sizeof(g_actorCoreInputEnds));
    g_heroCorrectionMask = 0;
    g_auxiliaryMask = 0;
    memset(g_actorCoreStackCounts, 0, sizeof(g_actorCoreStackCounts));
    memset(g_actorCoreWords, 0, sizeof(g_actorCoreWords));
    if (!g_superadminEnabled || !g_actorInputsFrozen || g_actorInputOverflow || g_auxiliaryInputOverflow || g_heroCorrectionOverflow
        || g_actorInputGeneration != g_attackGeneration || g_actorInputWorld != reinterpret_cast<uint32_t>(g_grid)) {
        InterlockedIncrement(&g_actorInputSequence);
        return;
    }
    const auto* world = static_cast<const uint32_t*>(g_grid);
    if (world == nullptr || world[0] != 0xe79d3c) {
        InterlockedIncrement(&g_actorInputSequence);
        return;
    }
    for (uint32_t side = 0; side < 2; ++side) {
        const uint32_t army = world[(0x8c + side * 4) / 4];
        if (army == 0 || *reinterpret_cast<const uint32_t*>(army) != 0xe17bcc) continue;
        PlacementAggregate aggregate;
        uint32_t inputEnd = 0;
        if (BuildFrozenPlacementCore(g_actorInputs, g_actorInputCount, g_actorInputWorld, army,
                g_actorInputGeneration, aggregate, g_actorCoreStackCounts[side], &inputEnd)) {
            const uint32_t inputBegin = inputEnd - g_actorCoreStackCounts[side];
            for (uint32_t index = 0; index < g_auxiliaryInputCount; ++index) {
                const auto& extra = g_auxiliaryInputs[index];
                if (extra.aggregateIdentity != g_actorInputs[inputEnd - 1].aggregateIdentity
                    || extra.attackGeneration != static_cast<uint32_t>(g_actorInputGeneration)) continue;
                const bool physical = extra.caller == 0xbfbb90 || extra.caller == 0xbfbbc3;
                const bool hero = extra.caller == 0xbfc194;
                if ((physical && extra.inputCount > inputBegin && extra.inputCount <= inputEnd)
                    || (hero && extra.inputCount == inputEnd)) {
                    aggregate.extra2 = static_cast<int32_t>(static_cast<uint32_t>(aggregate.extra2)
                        + static_cast<uint32_t>(extra.value));
                    g_auxiliaryMask |= 1u << side;
                }
            }
            for (uint32_t index = g_heroCorrectionCount; index != 0; --index) {
                const auto& correction = g_heroCorrections[index - 1];
                if (correction.aggregateIdentity != g_actorInputs[inputEnd - 1].aggregateIdentity
                    || correction.inputCount != inputEnd || correction.attackGeneration != static_cast<uint32_t>(g_actorInputGeneration)) continue;
                uint16_t original, captured = static_cast<uint16_t>(correction.controlWord);
                __asm fnstcw original
                __asm fldcw captured
                aggregate.multiplier = ApplyHeroActionCorrection(aggregate.multiplier, correction.firstScalar, correction.secondScalar);
                __asm fldcw original
                g_heroCorrectionMask |= 1u << side;
                break;
            }
            memcpy(g_actorCoreWords[side], &aggregate, sizeof(aggregate));
            g_actorCoreInputEnds[side] = inputEnd;
            g_actorCoreMask |= 1u << side;
        }
    }
    InterlockedIncrement(&g_actorInputSequence);
}

void __cdecl CaptureSuperadminHeroCorrection(uint32_t aggregateIdentity, int32_t firstScalar, int32_t secondScalar) {
    if (!g_superadminEnabled || g_actorInputsFrozen || g_actorInputGeneration != g_attackGeneration) return;
    if (g_heroCorrectionCount >= 64) {
        g_heroCorrectionOverflow = 1;
        return;
    }
    FrozenHeroCorrection correction{};
    correction.aggregateIdentity = aggregateIdentity;
    correction.inputCount = g_actorInputCount;
    correction.firstScalar = firstScalar;
    correction.secondScalar = secondScalar;
    correction.attackGeneration = g_attackGeneration;
    uint16_t control;
    __asm fnstcw control
    correction.controlWord = control;
    InterlockedIncrement(&g_actorInputSequence);
    g_heroCorrections[g_heroCorrectionCount++] = correction;
    InterlockedIncrement(&g_actorInputSequence);
}

__declspec(naked) void HeroCorrectionHook() {
    __asm {
        pushfd
        pushad
        mov ebx, esp
        sub esp, 528
        and esp, -16
        fxsave [esp]
        push dword ptr [ebx + 28]
        push dword ptr [ebx + 16]
        push dword ptr [ebx]
        call CaptureSuperadminHeroCorrection
        add esp, 12
        fxrstor [esp]
        mov esp, ebx
        popad
        popfd
        add ebx, eax
        mov eax, dword ptr [esp + 0x28]
        jmp kHeroCorrectionResume
    }
}

void __cdecl CaptureAreaSpellInput(const uint32_t* actor, uint32_t horizon, uint32_t areaOnly) {
    if (!g_superadminEnabled || g_actorInputsFrozen || g_areaInputBusy
        || g_actorInputGeneration != g_attackGeneration || g_attackGeneration == 0) return;
    g_areaInputBusy = true;
    FrozenAreaInput input{};
    input.metadata[0] = reinterpret_cast<uint32_t>(actor);
    input.metadata[3] = g_actorInputGeneration;
    uint16_t control;
    __asm fnstcw control
    input.metadata[4] = control;
    input.metadata[9] = g_actorInputCount;
    input.metadata[10] = horizon;
    input.metadata[11] = areaOnly & 255;
    __try {
        if (actor == nullptr || actor[0] == 0 || (horizon != 4 && horizon != 10)) {
            input.metadata[5] = 1;
        } else {
            const auto* methods = reinterpret_cast<const uintptr_t*>(actor[0]);
            const uint32_t world = reinterpret_cast<uint32_t (__thiscall*)(const void*)>(methods[8 / 4])(actor);
            input.metadata[1] = world;
            input.metadata[2] = reinterpret_cast<uint32_t (__thiscall*)(const void*)>(methods[0xc / 4])(actor);
            auto* physical = input.physicalWords;
            physical[0] = reinterpret_cast<int (__thiscall*)(const void*)>(methods[0])(actor);
            if (physical[0] == 1) {
                const auto* source = reinterpret_cast<const uint32_t* (__thiscall*)(const void*)>(methods[0x6c / 4])(actor);
                if (source == nullptr || source[0] == 0) input.metadata[5] |= 32;
                else {
                    const auto* sourceMethods = reinterpret_cast<const uintptr_t*>(source[0]);
                    const auto* descriptor = reinterpret_cast<const uint32_t* (__thiscall*)(const void*)>(sourceMethods[0])(source);
                    if (descriptor == nullptr) input.metadata[5] |= 32;
                    else {
                        physical[1] = reinterpret_cast<uint32_t>(descriptor);
                        physical[2] = descriptor[0x1c / 4];
                    }
                }
                physical[3] = reinterpret_cast<int (__thiscall*)(const void*)>(methods[0x1d8 / 4])(actor);
                physical[4] = reinterpret_cast<int (__thiscall*)(const void*)>(methods[0x1a0 / 4])(actor);
                if (static_cast<int>(physical[4]) > 0) {
                    physical[5] = reinterpret_cast<int (__thiscall*)(const void*, int, int, int)>(methods[0xb8 / 4])(actor, 1, 0, 0) != 0;
                }
                physical[7] = reinterpret_cast<bool (__thiscall*)(const void*, uint32_t)>(methods[0x28c / 4])(actor, 4);
                physical[8] = reinterpret_cast<bool (__thiscall*)(const void*, uint32_t)>(methods[0x28c / 4])(actor, 101)
                    || reinterpret_cast<bool (__thiscall*)(const void*, uint32_t)>(methods[0x28c / 4])(actor, 43);
                if ((static_cast<int>(physical[4]) > 0 && physical[5]) || physical[8]) {
                    float minimum, sum;
                    const uintptr_t minGetter = methods[0x1ec / 4], maxGetter = methods[0x1f0 / 4];
                    unsigned char maximum[10];
                    __asm {
                        mov ecx, actor
                        call minGetter
                        fstp minimum
                        mov ecx, actor
                        call maxGetter
                        fstp tbyte ptr maximum
                        fld tbyte ptr maximum
                        fadd minimum
                        fstp sum
                    }
                    memcpy(physical + 6, &sum, 4);
                    memcpy(physical + 10, &minimum, 4);
                    memcpy(physical + 11, maximum, sizeof(maximum));
                    physical[9] = CalculateAreaPhysicalPower(static_cast<int>(physical[3]), sum,
                        static_cast<int>(physical[4]) > 0, physical[5] != 0, physical[7] != 0, physical[8] != 0);
                }
            }
            const auto* caster = reinterpret_cast<const uint32_t* (__thiscall*)(const void*)>(methods[0x78 / 4])(actor);
            if (caster != nullptr) {
                const auto* casterMethods = reinterpret_cast<const uintptr_t*>(caster[0]);
                input.metadata[6] = reinterpret_cast<int (__thiscall*)(const void*, int, int)>(casterMethods[8 / 4])(caster, 0, 0);
            }
            input.metadata[7] = reinterpret_cast<int (__thiscall*)(const void*)>(methods[0x234 / 4])(actor);
            const auto* vector = reinterpret_cast<const uint32_t* (__thiscall*)(const void*)>(methods[0x248 / 4])(actor);
            if (vector == nullptr || vector[1] < vector[0] || (vector[1] - vector[0]) % 20 != 0) {
                input.metadata[5] |= 4;
            } else {
                const uint32_t count = (vector[1] - vector[0]) / 20;
                if (count > 32) input.metadata[5] |= 8;
                else {
                    input.metadata[8] = count;
                    auto* spells = reinterpret_cast<AreaSpellInput*>(input.spellWords);
                    for (uint32_t index = 0; index < count; ++index) {
                        const auto* descriptor = reinterpret_cast<const uint32_t*>(vector[0] + index * 20);
                        auto& spell = spells[index];
                        spell.identifier = descriptor[1];
                        spell.usable = reinterpret_cast<bool (__thiscall*)(const void*, const void*)>(methods[0x220 / 4])(actor, descriptor);
                        if (!spell.usable) continue;
                        spell.areaAllowed = reinterpret_cast<bool (__fastcall*)(uint32_t)>(0xa34670)(spell.identifier);
                        spell.damaging = reinterpret_cast<bool (__fastcall*)(uint32_t, const void*, const void*)>(0x982be0)(world, actor, descriptor);
                        if (!spell.damaging || spell.identifier == 0xa2 || spell.identifier == 0x13c) continue;
                        spell.excluded = reinterpret_cast<bool (__fastcall*)(const void*, const void*)>(0x9785e0)(descriptor, actor);
                        if (spell.excluded) continue;
                        spell.damage = reinterpret_cast<int (__fastcall*)(const void*, const void*, int)>(0x977c80)(descriptor, actor, 0);
                        if (spell.damage == 0) continue;
                        spell.limited = reinterpret_cast<bool (__fastcall*)(const void*)>(0xa34470)(descriptor);
                        if (spell.limited) {
                            const auto* charges = reinterpret_cast<const int* (__fastcall*)(const void*)>(0xa34490)(descriptor);
                            if (charges == nullptr) { input.metadata[5] |= 16; continue; }
                            spell.charges = charges[0x20 / 4];
                        } else {
                            spell.cost = reinterpret_cast<int (__fastcall*)(const void*, const void*, int)>(0x9781e0)(descriptor, actor, 0);
                        }
                    }
                }
            }
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) { input.metadata[5] |= 2; }
    if (input.metadata[5] == 0) {
        input.metadata[12] = CalculateAreaSpellPower(static_cast<int>(input.metadata[6]), static_cast<int>(input.metadata[7]),
            4, true, reinterpret_cast<const AreaSpellInput*>(input.spellWords), input.metadata[8]);
        input.metadata[13] = CalculateAreaSpellPower(static_cast<int>(input.metadata[6]), static_cast<int>(input.metadata[7]),
            10, false, reinterpret_cast<const AreaSpellInput*>(input.spellWords), input.metadata[8]);
    }
    bool duplicate = false;
    for (uint32_t index = 0; index < g_areaInputCount; ++index) {
        const auto& previous = g_areaInputs[index];
        if (memcmp(previous.metadata, input.metadata, 9 * 4) == 0
            && memcmp(previous.metadata + 10, input.metadata + 10, 4 * 4) == 0
            && memcmp(previous.spellWords, input.spellWords, sizeof(input.spellWords)) == 0
            && memcmp(previous.physicalWords, input.physicalWords, sizeof(input.physicalWords)) == 0) { duplicate = true; break; }
    }
    if (!duplicate) {
        InterlockedIncrement(&g_actorInputSequence);
        if (g_areaInputCount >= 128) g_areaInputOverflow = 1;
        else g_areaInputs[g_areaInputCount++] = input;
        InterlockedIncrement(&g_actorInputSequence);
    }
    g_areaInputBusy = false;
}

void __cdecl CaptureSuperadminAuxiliaryPower(uint32_t aggregateIdentity, int32_t value, uint32_t caller) {
    if (!g_superadminEnabled || g_actorInputsFrozen || g_areaInputBusy || g_actorInputGeneration != g_attackGeneration
        || (caller != 0xbfbb90 && caller != 0xbfbbc3 && caller != 0xbfc194)) return;
    if (g_auxiliaryInputCount >= 256) {
        g_auxiliaryInputOverflow = 1;
        return;
    }
    FrozenAuxiliaryPower input{};
    input.aggregateIdentity = aggregateIdentity;
    input.inputCount = g_actorInputCount;
    input.value = value;
    input.caller = caller;
    input.attackGeneration = g_attackGeneration;
    uint16_t control;
    __asm fnstcw control
    input.controlWord = control;
    InterlockedIncrement(&g_actorInputSequence);
    g_auxiliaryInputs[g_auxiliaryInputCount++] = input;
    InterlockedIncrement(&g_actorInputSequence);
}

__declspec(naked) void AuxiliaryPowerHook() {
    __asm {
        pushfd
        pushad
        mov ebx, esp
        sub esp, 528
        and esp, -16
        fxsave [esp]
        push dword ptr [ebx + 64]
        push dword ptr [ebx + 48]
        push dword ptr [ebx + 36]
        call CaptureSuperadminAuxiliaryPower
        add esp, 12
        fxrstor [esp]
        push dword ptr [ebx + 72]
        push dword ptr [ebx + 68]
        push dword ptr [ebx + 4]
        call CaptureAreaSpellInput
        add esp, 12
        fxrstor [esp]
        mov esp, ebx
        popad
        popfd
        mov eax, dword ptr [esp + 0xc]
        pop edi
        jmp kAuxiliaryPowerResume
    }
}

bool BuildFrozenOwnSubset(uint32_t mask, PlacementAggregate& result) {
    const uint32_t end = g_actorCoreInputEnds[0], count = g_actorCoreStackCounts[0];
    if (!count || end < count || end > static_cast<uint32_t>(g_actorInputCount)) return false;
    const uint32_t begin = end - count;
    const auto& anchor = g_actorInputs[end - 1];
    uint32_t selectedCount;
    if (!BuildFrozenPlacementCore(g_actorInputs + begin, count, g_actorInputWorld, anchor.army,
                                  g_actorInputGeneration, result, selectedCount, nullptr, mask)) return false;
    const auto* complete = reinterpret_cast<const PlacementAggregate*>(g_actorCoreWords[0]);
    result.extra0 = complete->extra0;
    result.unused = complete->unused;
    result.magicPower = complete->magicPower;
    for (uint32_t index = 0; index < g_auxiliaryInputCount; ++index) {
        const auto& extra = g_auxiliaryInputs[index];
        if (extra.aggregateIdentity != anchor.aggregateIdentity || extra.attackGeneration != anchor.attackGeneration) continue;
        const bool hero = extra.caller == 0xbfc194 && extra.inputCount == end;
        const bool selected = (extra.caller == 0xbfbb90 || extra.caller == 0xbfbbc3)
            && extra.inputCount > begin && extra.inputCount <= end
            && (mask & (1u << (extra.inputCount - begin - 1)));
        if (hero || selected) result.extra2 = static_cast<int32_t>(static_cast<uint32_t>(result.extra2)
                                                                 + static_cast<uint32_t>(extra.value));
    }
    for (uint32_t index = g_heroCorrectionCount; index; --index) {
        const auto& correction = g_heroCorrections[index - 1];
        if (correction.aggregateIdentity == anchor.aggregateIdentity && correction.inputCount == end
            && correction.attackGeneration == anchor.attackGeneration) {
            uint16_t original, captured = static_cast<uint16_t>(correction.controlWord);
            __asm fnstcw original
            __asm fldcw captured
            result.multiplier = ApplyHeroActionCorrection(result.multiplier, correction.firstScalar, correction.secondScalar);
            __asm fldcw original
            break;
        }
    }
    return true;
}

bool CalculateFrozenAreaNumerator(int& numerator) {
    if (!g_superadminEnabled || !g_actorInputsFrozen || g_actorInputOverflow || g_areaInputOverflow
        || g_actorCoreMask != 3 || g_actorInputGeneration != g_attackGeneration) return false;
    const uint32_t end = g_actorCoreInputEnds[0], count = g_actorCoreStackCounts[0];
    if (count == 0 || end < count || end > static_cast<uint32_t>(g_actorInputCount)) return false;
    const auto& anchor = g_actorInputs[end - 1];
    const auto sameState = [](const FrozenAreaInput& first, const FrozenAreaInput& second) {
        return memcmp(first.metadata + 6, second.metadata + 6, 3 * 4) == 0
            && memcmp(first.spellWords, second.spellWords, sizeof(first.spellWords)) == 0
            && memcmp(first.physicalWords, second.physicalWords, sizeof(first.physicalWords)) == 0;
    };
    uint32_t total = 0;
    for (uint32_t index = end - count; index < end; ++index) {
        const auto& actor = g_actorInputs[index];
        const FrozenAreaInput* selected = nullptr;
        for (uint32_t candidate = 0; candidate < g_areaInputCount; ++candidate) {
            const auto& row = g_areaInputs[candidate];
            if (row.metadata[1] != g_actorInputWorld || row.metadata[2] != anchor.army
                || row.metadata[3] != static_cast<uint32_t>(g_actorInputGeneration)
                || row.metadata[4] != anchor.controlWord || row.physicalWords[0] != 1
                || row.physicalWords[1] != actor.source || row.physicalWords[2] != actor.type
                || row.physicalWords[3] != actor.quantity) continue;
            if (row.metadata[5] != 0 || row.metadata[8] > 32 || (selected != nullptr && !sameState(*selected, row))) return false;
            selected = &row;
        }
        if (selected == nullptr) return false;
        const int spell = CalculateAreaSpellPower(static_cast<int>(selected->metadata[6]), static_cast<int>(selected->metadata[7]),
            4, true, reinterpret_cast<const AreaSpellInput*>(selected->spellWords), selected->metadata[8]);
        if (spell > 0) total += static_cast<uint32_t>(spell);
        float damageSum;
        memcpy(&damageSum, selected->physicalWords + 6, 4);
        total += static_cast<uint32_t>(CalculateAreaPhysicalPower(static_cast<int>(selected->physicalWords[3]), damageSum,
            static_cast<int>(selected->physicalWords[4]) > 0, selected->physicalWords[5] != 0,
            selected->physicalWords[7] != 0, selected->physicalWords[8] != 0));
    }
    const FrozenAreaInput* hero = nullptr;
    for (uint32_t candidate = 0; candidate < g_areaInputCount; ++candidate) {
        const auto& row = g_areaInputs[candidate];
        if (row.metadata[1] != g_actorInputWorld || row.metadata[2] != anchor.army
            || row.metadata[3] != static_cast<uint32_t>(g_actorInputGeneration)
            || row.metadata[4] != anchor.controlWord || row.physicalWords[0] != 2) continue;
        if (row.metadata[5] != 0 || row.metadata[8] > 32
            || (hero != nullptr && (hero->metadata[0] != row.metadata[0] || !sameState(*hero, row)))) return false;
        hero = &row;
    }
    if (hero == nullptr) return false;
    total += static_cast<uint32_t>(CalculateAreaSpellPower(static_cast<int>(hero->metadata[6]), static_cast<int>(hero->metadata[7]),
        4, true, reinterpret_cast<const AreaSpellInput*>(hero->spellWords), hero->metadata[8]));
    numerator = static_cast<int>(total);
    return true;
}

bool FrozenArmyRangedCapability(const FrozenActorInput* inputs, uint32_t inputEnd,
                               uint32_t stackCount, bool noRanged) {
    for (uint32_t index = inputEnd - stackCount; index < inputEnd; ++index) {
        if (noRanged && inputs[index].ignoreWhenNoRanged) continue;
        if (!inputs[index].rangedCapability) return false;
    }
    return true;
}

void PrepareSuperadminStrategy() {
    InterlockedIncrement(&g_actorInputSequence);
    memset(g_strategyTrace, 0, sizeof(g_strategyTrace));
    memset(g_areaPolicyTrace, 0, sizeof(g_areaPolicyTrace));
    memset(g_largePolicyTrace, 0, sizeof(g_largePolicyTrace));
    if (g_superadminEnabled) { g_predictedDefensive = false; g_useSpreadRows = false; }
    bool valid = g_actorCoreMask == 3 && g_actorInputsFrozen && !g_actorInputOverflow
        && g_actorInputGeneration == g_attackGeneration
        && g_superadminSourceGeneration == g_placementGeneration;
    bool used[7]{};
    const uint32_t enemyEnd = g_actorCoreInputEnds[1];
    const uint32_t enemyCount = g_actorCoreStackCounts[1];
    valid = valid && enemyCount == static_cast<uint32_t>(g_superadminSourceCount) && enemyCount > 0 && enemyCount <= 7;
    for (uint32_t side = 0; valid && side < 2; ++side) {
        const uint32_t end = g_actorCoreInputEnds[side], count = g_actorCoreStackCounts[side];
        valid = count > 0 && end >= count && end <= static_cast<uint32_t>(g_actorInputCount);
        for (uint32_t index = end - count; valid && index < end; ++index) {
            valid = g_actorInputs[index].armySize == count;
        }
    }
    for (uint32_t index = enemyEnd - enemyCount; valid && index < enemyEnd; ++index) {
        const auto& input = g_actorInputs[index];
        bool matched = false;
        for (uint32_t source = 0; source < enemyCount; ++source) {
            if (!used[source] && input.type == g_superadminSourceTypes[source] && input.quantity == g_superadminSourceCounts[source]) {
                used[source] = true;
                matched = true;
                break;
            }
        }
        valid = matched;
    }
    if (valid) {
        const auto* own = reinterpret_cast<const PlacementAggregate*>(g_actorCoreWords[0]);
        const auto* enemy = reinterpret_cast<const PlacementAggregate*>(g_actorCoreWords[1]);
        using Power = int (__thiscall*)(const PlacementAggregate*, const PlacementAggregate*);
        const auto total = reinterpret_cast<Power>(0xbfc4a0);
        const auto ranged = reinterpret_cast<Power>(0xbf9d30);
        uint16_t original, captured = static_cast<uint16_t>(g_actorInputs[enemyEnd - 1].controlWord);
        __asm fnstcw original
        __asm fldcw captured
        const int enemyTotal = total(enemy, own);
        const int enemyRanged = ranged(enemy, own);
        const int ownRanged = ranged(own, enemy);
        const float share = enemyTotal > 0 ? PlacementRatio(enemyRanged, enemyTotal) : 0;
        const float advantage = ownRanged == 0 ? 100.0f : PlacementRatio(enemyRanged, ownRanged);
        const bool enemyCapability = FrozenArmyRangedCapability(g_actorInputs, enemyEnd, enemyCount, ownRanged == 0);
        const bool ownCapability = FrozenArmyRangedCapability(g_actorInputs, g_actorCoreInputEnds[0],
                                                            g_actorCoreStackCounts[0], enemyRanged == 0);
        const auto* settings = reinterpret_cast<const unsigned char* (__cdecl*)()>(0xbcb3f0)();
        const float shareThreshold = *reinterpret_cast<const float*>(settings + 0xbfc);
        const float advantageThreshold = *reinterpret_cast<const float*>(settings + 0xc00);
        uint32_t meleeMask = 0, largeMask = 0;
        bool largeInputsValid = !g_areaInputOverflow;
        const uint32_t ownEnd = g_actorCoreInputEnds[0], ownCount = g_actorCoreStackCounts[0];
        for (uint32_t index = ownEnd - ownCount; largeInputsValid && index < ownEnd; ++index) {
            const auto& actor = g_actorInputs[index];
            const int* creature = reinterpret_cast<const int* (__fastcall*)(uint32_t)>(kCreatureDefinition)(actor.type);
            if (creature == nullptr || creature[0xdc / 4] < 1 || creature[0xdc / 4] > 2) { largeInputsValid = false; break; }
            const FrozenAreaInput* selected = nullptr;
            for (uint32_t candidate = 0; candidate < g_areaInputCount; ++candidate) {
                const auto& row = g_areaInputs[candidate];
                if (row.metadata[1] != actor.world || row.metadata[2] != actor.army
                    || row.metadata[3] != actor.attackGeneration || row.metadata[4] != actor.controlWord
                    || row.physicalWords[0] != 1 || row.physicalWords[1] != actor.source
                    || row.physicalWords[2] != actor.type || row.physicalWords[3] != actor.quantity) continue;
                if (row.metadata[5] || (selected && selected->physicalWords[4] != row.physicalWords[4])) { largeInputsValid = false; break; }
                selected = &row;
            }
            if (!selected) { largeInputsValid = false; break; }
            if (static_cast<int>(selected->physicalWords[4]) <= 0) {
                meleeMask |= 1u << (index - (ownEnd - ownCount));
                if (creature[0xdc / 4] == 2) largeMask |= 1u << (index - (ownEnd - ownCount));
            }
        }
        PlacementAggregate melee, large;
        if (largeInputsValid && BuildFrozenOwnSubset(meleeMask, melee) && BuildFrozenOwnSubset(largeMask, large)) {
            const auto evaluate = reinterpret_cast<Power>(0xbf9b80);
            const int denominator = evaluate(&melee, enemy), numerator = evaluate(&large, enemy);
            const float ratio = denominator ? PlacementRatio(numerator, denominator) : 0;
            g_knownHeroLarge = ratio > *reinterpret_cast<const float*>(settings + 0xbf4);
            g_largePolicyTrace[0] = 1;
            g_largePolicyTrace[1] = numerator;
            g_largePolicyTrace[2] = denominator;
            memcpy(g_largePolicyTrace + 3, &ratio, 4);
        }
        const int spreadDenominator = CalculatePlacementPower(*own, *enemy,
            *reinterpret_cast<const float*>(settings + 0x1d0),
            *reinterpret_cast<const float*>(settings + 0x1d8), false);
        g_estimatedSpreadDenominator = spreadDenominator > 0 ? static_cast<uint32_t>(spreadDenominator) : 0;
        int areaNumerator;
        if (spreadDenominator > 0 && CalculateFrozenAreaNumerator(areaNumerator)) {
            const float ratio = PlacementRatio(areaNumerator, spreadDenominator);
            g_useSpreadRows = ratio > *reinterpret_cast<const float*>(settings + 0xbf8);
            g_areaPolicyTrace[0] = 1;
            g_areaPolicyTrace[1] = static_cast<uint32_t>(areaNumerator);
            g_areaPolicyTrace[2] = static_cast<uint32_t>(spreadDenominator);
            memcpy(g_areaPolicyTrace + 3, &ratio, 4);
        }
        const bool defensive = enemyTotal > 0 && (enemyCapability || (share > shareThreshold && advantage > advantageThreshold))
            && !ownCapability;
        __asm fldcw original
        g_strategyTrace[0] = 1;
        g_strategyTrace[1] = defensive;
        g_strategyTrace[2] = enemyRanged;
        g_strategyTrace[3] = enemyTotal;
        g_strategyTrace[4] = ownRanged;
        memcpy(g_strategyTrace + 5, &share, 4);
        memcpy(g_strategyTrace + 6, &advantage, 4);
        g_strategyTrace[7] = enemyCapability;
        g_strategyTrace[8] = ownCapability;
        g_predictedDefensive = defensive;
    }
    InterlockedIncrement(&g_actorInputSequence);
}

void __cdecl CaptureScriptedSource(const uint32_t* vector) {
    if (!g_superadminEnabled) return;
    ++g_attackGeneration;
    ResetSuperadminInputCapture();
    g_superadminSourceCount = 0;
    g_superadminSourceKind = 2;
    g_superadminSourceModifiersKnown = false;
    g_superadminTerrainKnown = false;
    g_superadminRngKnown = false;
    g_superadminTerrainMask = 0;
    g_superadminTerrainType = 0;
    g_superadminRngState = 0;
    g_publicCount = 0;
    memset(g_publicTypes, 0, sizeof(g_publicTypes));
    memset(g_superadminSourcePointers, 0, sizeof(g_superadminSourcePointers));
    memset(g_superadminSourceSpeed, 0, sizeof(g_superadminSourceSpeed));
    memset(g_superadminSourceFlying, 0, sizeof(g_superadminSourceFlying));
    memset(g_superadminSourceAggregate, 0, sizeof(g_superadminSourceAggregate));
    // Original parsed StartCombat arguments, before any combat construction.
    // Descriptor modifiers are absent here; do not invent them from definitions.
    __try {
        if (vector == nullptr || vector[0] == 0 || vector[1] < vector[0]
            || vector[2] < vector[1] || (vector[1] - vector[0]) % 8 != 0) return;
        const uint32_t count = (vector[1] - vector[0]) / 8;
        if (count == 0 || count > 7) return;
        const auto* stacks = reinterpret_cast<const uint32_t*>(vector[0]);
        for (uint32_t index = 0; index < count; ++index) {
            if (stacks[index * 2] == 0 || stacks[index * 2 + 1] == 0) return;
        }
        for (uint32_t index = 0; index < count; ++index) {
            g_superadminSourceTypes[index] = stacks[index * 2];
            g_superadminSourceCounts[index] = stacks[index * 2 + 1];
        }
        g_superadminSourceGeneration = g_placementGeneration;
        g_superadminSourceCount = static_cast<LONG>(count);
    } __except (EXCEPTION_EXECUTE_HANDLER) { }
}

__declspec(naked) void ScriptedSourceHook() {
    __asm {
        pushfd
        pushad
        mov ebx, esp
        sub esp, 528
        and esp, -16
        fxsave [esp]
        lea eax, [ebx + 36 + 0x54]
        push eax
        call CaptureScriptedSource
        add esp, 4
        fxrstor [esp]
        mov esp, ebx
        popad
        popfd
        lea ecx, [esp + 0x84]
        jmp kScriptedSourceResume
    }
}

bool PrepareScriptedPreviewSource() {
    if (!g_superadminEnabled || g_superadminSourceKind != 2 || g_publicCount != 0
        || g_superadminSourceCount < 1 || g_superadminSourceCount > 7
        || g_superadminSourceGeneration != g_placementGeneration
        || g_actorInputGeneration != g_attackGeneration || g_attackGeneration == 0
        || g_actorInputOverflow || g_actorInputCount < 1 || g_actorInputCount > 256) return false;
    uint32_t pointers[7]{};
    int32_t speeds[7]{};
    uint32_t flying[7]{};
    __try {
        const uint32_t worldAddress = g_actorInputs[g_actorInputCount - 1].world;
        const auto* world = reinterpret_cast<const uint32_t*>(worldAddress);
        if (world == nullptr || world[0] != 0xe79d3c || world[0x90 / 4] == 0) return false;
        for (LONG slot = 0; slot < g_superadminSourceCount; ++slot) {
            for (LONG previous = 0; previous < slot; ++previous) {
                if (g_superadminSourceTypes[previous] == g_superadminSourceTypes[slot]
                    && g_superadminSourceCounts[previous] == g_superadminSourceCounts[slot]) return false;
            }
            for (LONG index = 0; index < g_actorInputCount; ++index) {
                const auto& row = g_actorInputs[index];
                if (row.world != worldAddress || row.army != world[0x90 / 4]
                    || row.attackGeneration != static_cast<uint32_t>(g_attackGeneration)
                    || row.type != g_superadminSourceTypes[slot]
                    || row.quantity != g_superadminSourceCounts[slot]) continue;
                if (row.unsupported || row.source == 0 || (pointers[slot] && pointers[slot] != row.source)) return false;
                pointers[slot] = row.source;
            }
            const auto* descriptor = reinterpret_cast<const uint32_t*>(pointers[slot]);
            if (descriptor == nullptr || descriptor[0x1c / 4] != g_superadminSourceTypes[slot]
                || descriptor[0x20 / 4] != g_superadminSourceCounts[slot]) return false;
            speeds[slot] = reinterpret_cast<int (__thiscall*)(const void*, const void*)>(0x4bc0b0)(descriptor, nullptr);
            flying[slot] = reinterpret_cast<bool (__thiscall*)(const void*)>(0x4ba950)(descriptor);
        }
        const uint32_t vector[] = {reinterpret_cast<uint32_t>(pointers),
            reinterpret_cast<uint32_t>(pointers + g_superadminSourceCount),
            reinterpret_cast<uint32_t>(pointers + g_superadminSourceCount)};
        uint32_t aggregate[18]{};
        using Builder = void (__stdcall*)(void*, const void*, const void*, const void*);
        reinterpret_cast<Builder>(0xbfaa70)(aggregate, vector, nullptr, nullptr);
        memcpy(g_superadminSourcePointers, pointers, sizeof(pointers));
        memcpy(g_superadminSourceSpeed, speeds, sizeof(speeds));
        memcpy(g_superadminSourceFlying, flying, sizeof(flying));
        memcpy(g_superadminSourceAggregate, aggregate, sizeof(aggregate));
        memcpy(g_publicTypes, g_superadminSourceTypes, g_superadminSourceCount * sizeof(uint32_t));
        memset(g_publicBands, 0, sizeof(g_publicBands));
        g_superadminSourceModifiersKnown = true;
        g_publicCount = g_superadminSourceCount;
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) { return false; }
}

void CaptureSuperadminSource(const uint32_t* object) {
    g_superadminSourceCount = 0;
    g_superadminSourceKind = 0;
    g_superadminSourceModifiersKnown = false;
    memset(g_superadminSourcePointers, 0, sizeof(g_superadminSourcePointers));
    g_superadminTerrainKnown = false;
    g_superadminTerrainMask = 0;
    g_superadminTerrainType = 0;
    g_superadminRngKnown = false;
    g_superadminRngState = 0;
    if (!g_superadminEnabled || object == nullptr) return;
    const auto* vector = reinterpret_cast<uint32_t* const*>(object + 0xe0 / 4);
    const auto* begin = vector[0];
    const auto* end = vector[1];
    if (begin == nullptr || end < begin || end - begin > 7) return;
    memset(g_superadminSourceAggregate, 0, sizeof(g_superadminSourceAggregate));
    using AggregateBuilder = void (__stdcall*)(void*, const void*, const void*, const void*);
    reinterpret_cast<AggregateBuilder>(0xbfaa70)(g_superadminSourceAggregate, vector, nullptr, nullptr);
    LONG count = 0;
    for (auto entry = begin; entry != end; ++entry) {
        const auto* descriptor = reinterpret_cast<const uint32_t*>(*entry);
        if (descriptor == nullptr || descriptor[0x20 / 4] == 0) continue;
        g_superadminSourceTypes[count] = descriptor[0x1c / 4];
        g_superadminSourceCounts[count] = descriptor[0x20 / 4];
        g_superadminSourcePointers[count] = reinterpret_cast<uint32_t>(descriptor);
        // Freeze source modifiers while the map descriptor is still alive.
        // These getters do not consult final enemy placement records.
        g_superadminSourceSpeed[count] = reinterpret_cast<int (__thiscall*)(const void*, const void*)>(
            0x4bc0b0)(descriptor, nullptr);
        g_superadminSourceFlying[count] = reinterpret_cast<bool (__thiscall*)(const void*)>(0x4ba950)(descriptor);
        ++count;
    }
    g_superadminSourceGeneration = g_placementGeneration;
    g_superadminSourceCount = count;
    g_superadminSourceKind = 1;
    g_superadminSourceModifiersKnown = true;
}

// The stock public model contains qualitative count text for each portrait.
// Compare it with labels built by the same game function for representative
// public ranges. No monster quantity or combat stack is read here.
void __cdecl CapturePublicBands(const uint32_t* model) {
    memset(g_publicBands, 0, sizeof(g_publicBands));
    if (model == nullptr) return;
    const uintptr_t begin = model[0x50 / 4];
    const uintptr_t end = model[0x54 / 4];
    if (end < begin || (end - begin) % 24 != 0 || (end - begin) / 24 > 7) return;
    const int representatives[] = {1, 5, 10, 20, 50, 100, 250, 500, 1000};
    for (uintptr_t rowAddress = begin, index = 0; rowAddress < end; rowAddress += 24, ++index) {
        const auto* row = reinterpret_cast<const uint32_t*>(rowAddress);
        const uintptr_t labelBegin = row[0xc / 4];
        const uintptr_t labelEnd = row[0x10 / 4];
        if (labelEnd <= labelBegin || labelEnd - labelBegin > 128 || (labelEnd - labelBegin) % 2 != 0) continue;
        for (unsigned band = 0; band < 9; ++band) {
            uint32_t reference[3]{};
            reinterpret_cast<uint32_t* (__fastcall*)(uint32_t*, int)>(0x4bc930)(reference, representatives[band]);
            const uintptr_t textBegin = reference[0];
            const uintptr_t textEnd = reference[1];
            const bool equal = textEnd >= textBegin && textEnd - textBegin == labelEnd - labelBegin
                && memcmp(reinterpret_cast<const void*>(textBegin),
                          reinterpret_cast<const void*>(labelBegin), labelEnd - labelBegin) == 0;
            if (textBegin != 0) reinterpret_cast<void (__cdecl*)(void*)>(0x879240)(reinterpret_cast<void*>(textBegin));
            if (equal) {
                g_publicBands[index] = band + 1;
                break;
            }
        }
    }
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
        mov dword ptr [g_predictionExcludedMask], 0
        mov dword ptr [g_plannedProjectionCount], 0
        mov dword ptr [g_publicTypes], 0
        test eax, eax
        jz capture_done
        cmp dword ptr [eax], 0xe18f7c
        jne capture_done
        sub eax, 0x158
        pushad
        push eax
        call CaptureSuperadminSource
        add esp, 4
        popad
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
        pushad
        push ebp
        call CapturePublicBands
        add esp, 4
        popad
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
        pushfd
        pushad
        inc dword ptr [g_attackGeneration]
        call ResetSuperadminInputCapture
        popad
        popfd
        fxrstor [g_fpu]
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
        mov dword ptr [g_predictionExcludedMask], 0
        mov dword ptr [g_plannedProjectionCount], 0
        mov byte ptr [g_projectionPlanning], 0
        mov dword ptr [g_placementOwner], ecx
        cmp dword ptr [g_superadminSourceCount], 0
        je admin_generation_ready
        mov eax, dword ptr [g_placementGeneration]
        mov dword ptr [g_superadminSourceGeneration], eax
    admin_generation_ready:
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
        mov dword ptr [g_superadminSourceCount], 0
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
        call FreezeSuperadminInputCapture
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
        // Scripted admin inputs are original arguments plus captured descriptors.
        // Keep the trusted caller and placement-owner checks above this binding.
        cmp dword ptr [g_publicCount], 0
        jne source_ready
        fxsave [g_fpu]
        call PrepareScriptedPreviewSource
        fxrstor [g_fpu]
    source_ready:
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
        call PrepareKnownHeroPolicy
        cmp byte ptr [g_superadminEnabled], 0
        je strategy_order_ready
        call ApplySourceComposition
        test al, al
        jz restore
        call PreparePublicOrder
        test al, al
        jz restore
    strategy_order_ready:
        mov al, byte ptr [g_superadminEnabled]
        mov byte ptr [g_projectionPlanning], al
        mov dword ptr [g_candidateIdentity], 0
        cmp byte ptr [g_predictedDefensive], 0
        je first_candidate_ready
        mov dword ptr [g_candidateIdentity], 1
    first_candidate_ready:
        mov dword ptr [g_outputStorage + 8 + 960], 0
        mov dword ptr [g_outputStorage + 8 + 964], 0
        mov dword ptr [g_outputStorage + 8 + 972], 0
        mov byte ptr [g_sourceFallbackPrepared], 0
        mov dword ptr [g_outputStorage + 8 + 908], 0
        mov dword ptr [g_outputStorage + 8 + 912], 0
        mov dword ptr [g_definitionMaximum], 0
        mov dword ptr [g_outputStorage + 8 + 496], 0
        mov dword ptr [g_outputStorage + 8 + 952], 0
    model_loop:
        cmp dword ptr [g_candidateIdentity], 6
        jl primary_model_index
        mov esi, dword ptr [g_outputStorage + 8 + 952]
        cmp esi, dword ptr [g_publicCount]
        jae residual_pass_done
        mov esi, dword ptr [g_outputStorage + 8 + esi * 4 + 924]
        cmp esi, -1
        je next_model
        mov dword ptr [g_definitionMaximum], esi
        bt dword ptr [g_outputStorage + 8 + 908], esi
        jc next_model
    primary_model_index:
        cmp dword ptr [g_candidateIdentity], 6
        jge selected_model_index
        mov esi, dword ptr [g_outputStorage + 8 + 952]
        cmp esi, dword ptr [g_plannedProjectionCount]
        jae restore
        cmp byte ptr [g_superadminEnabled], 0
        je selected_model_index
        cmp byte ptr [g_predictedDefensive], 0
        jne selected_model_index
        cmp dword ptr [g_candidateIdentity], 5
        jne selected_model_index
        mov esi, dword ptr [g_groundRetryOrder + esi * 4]
        cmp esi, -1
        je next_model
    selected_model_index:
        cmp esi, dword ptr [g_plannedProjectionCount]
        jae restore
        mov dword ptr [g_definitionMaximum], esi
        cmp byte ptr [g_superadminEnabled], 0
        je unplaced_model_index
        bt dword ptr [g_outputStorage + 8 + 908], esi
        jc next_model
    unplaced_model_index:
        mov ecx, dword ptr [g_orderedPublicTypes + esi * 4]
        mov eax, 0x89fbf0
        call eax
        test eax, eax
        jz next_model
        mov edx, dword ptr [eax + 0xdc]
        mov dword ptr [g_creatureDefinition], edx
        push eax
        mov ecx, dword ptr [g_definitionMaximum]
        push dword ptr [g_orderedPublicTypes + ecx * 4]
        call PublicPlacementRole
        add esp, 4
        mov ecx, eax
        pop eax
        xor edx, edx
        cmp ecx, 1
        sete dl
        mov dword ptr [g_outputStorage + 8 + 740], edx
    role_ready:
        cmp byte ptr [g_sourceSimpleLayout], 0
        jne model_role_accepted
        cmp dword ptr [g_candidateIdentity], 6
        jge residual_role
        cmp byte ptr [g_superadminEnabled], 0
        je primary_role_match
        cmp byte ptr [g_predictedDefensive], 0
        jne primary_role_match
        cmp dword ptr [g_candidateIdentity], 5
        je model_role_accepted
    primary_role_match:
        cmp ecx, dword ptr [g_candidateIdentity]
        jne next_model
        cmp byte ptr [g_superadminEnabled], 0
        je model_role_accepted
        cmp byte ptr [g_predictedDefensive], 0
        jne model_role_accepted
        cmp byte ptr [g_useSpreadRows], 0
        jne model_role_accepted
        cmp ecx, 4
        jne model_role_accepted
        // 8580e0 keeps world shooter neighbours, then tests local depth2
        // bounds. Defender anchors on this supported field are outside them.
        // No support candidate survives; small melee joins category3 next.
        jmp next_model
    residual_role:
        mov ecx, dword ptr [g_creatureDefinition]
        cmp dword ptr [g_candidateIdentity], 6
        jne residual_small_role
        cmp ecx, 2
        jne next_model
        jmp model_role_accepted
    residual_small_role:
        cmp ecx, 1
        jne next_model
    model_role_accepted:
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
        mov ecx, dword ptr [g_definitionMaximum]
        mov ecx, dword ptr [g_outputStorage + 8 + ecx * 4 + 832]
        mov dword ptr [g_outputStorage + 8 + esi * 4 + 864], ecx
        mov eax, dword ptr [g_creatureDefinition]
        mov dword ptr [g_outputStorage + 8 + esi * 4 + 600], eax
        cmp byte ptr [g_sourceSimpleLayout], 0
        je simple_layout_unavailable
        call ChooseSourceSimpleCell
        test eax, eax
        js next_model
        mov edi, eax
        and edi, 0xff
        mov esi, eax
        shr esi, 8
        mov eax, dword ptr [g_outputStorage + 8 + 496]
        lea edx, [g_cell + eax * 8]
        jmp cell_selected
    simple_layout_unavailable:
        cmp dword ptr [g_candidateIdentity], 6
        jge residual_cell
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
        call ChooseLinkedGoblinCell
        cmp eax, 0
        jl linked_cell_unavailable
        mov edi, eax
        and edi, 0xff
        mov esi, eax
        shr esi, 8
        mov eax, dword ptr [g_outputStorage + 8 + 496]
        lea edx, [g_cell + eax * 8]
        jmp cell_selected
    residual_cell:
        mov esi, dword ptr [g_outputStorage + 8 + 384]
        sub esi, 3
        sub esi, dword ptr [g_outputStorage + 8 + 912]
        mov edi, dword ptr [g_outputStorage + 8 + 916]
        cmp dword ptr [g_candidateIdentity], 6
        je residual_row
        mov edi, dword ptr [g_outputStorage + 8 + 920]
    residual_row:
        mov eax, dword ptr [g_outputStorage + 8 + 388]
        sub eax, 2
        cmp edi, eax
        jg residual_pass_done
        cmp dword ptr [g_creatureDefinition], 2
        jne residual_footprint
        cmp dword ptr [g_outputStorage + 8 + 912], 0
        jne residual_pass_done
    residual_footprint:
        call footprint_free
        test eax, eax
        jnz residual_selected
        inc edi
        jmp residual_row
    residual_selected:
        cmp dword ptr [g_candidateIdentity], 6
        jne residual_save_small_row
        mov dword ptr [g_outputStorage + 8 + 916], edi
        jmp residual_save_cell
    residual_save_small_row:
        mov dword ptr [g_outputStorage + 8 + 920], edi
    residual_save_cell:
        mov eax, dword ptr [g_outputStorage + 8 + 496]
        lea edx, [g_cell + eax * 8]
        jmp cell_selected
    linked_cell_unavailable:
        cmp byte ptr [g_predictedDefensive], 0
        je ordinary_rank_row
        // 0x8593c0 uses 0x858700 for the defensive+spread combination;
        // shooter-adjacent guard placement applies only without spread.
        cmp byte ptr [g_useSpreadRows], 0
        jne ordinary_rank_row
        cmp dword ptr [g_candidateIdentity], 1
        je ordinary_rank_row
        call ChooseProtectiveCell
        cmp eax, 0
        jl next_model
        mov edi, eax
        and edi, 0xff
        mov esi, eax
        shr esi, 8
        mov eax, dword ptr [g_outputStorage + 8 + 496]
        lea edx, [g_cell + eax * 8]
        jmp cell_selected
    ordinary_rank_row:
        mov byte ptr [g_spreadFallback], 0
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
        // 0x857e60 uses the two-row approach vector when the known hero army
        // is predominantly large. Row 1 retains its single-row score.
        cmp byte ptr [g_knownHeroLarge], 0
        je window_lane_clear
        mov edx, edi
        add edx, esi
        mov eax, dword ptr [g_outputStorage + 8 + 388]
        sub eax, 2
        cmp edx, eax
        jl window_previous_row
        sub edx, eax
    window_previous_row:
        test edx, edx
        jz window_lane_clear
        push ebx
        sub ebx, dword ptr [g_outputStorage + 8 + 524]
        mov eax, ecx
        shr eax, 3
        movzx edx, byte ptr [ebx + eax]
        mov eax, ecx
        and eax, 7
        pop ebx
        bt edx, eax
        jc window_lane_done
    window_lane_clear:
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
        push edi
        push dword ptr [g_candidateIdentity]
        call SpreadRowAllowed
        add esp, 8
        test al, al
        jz rank_advance
        mov esi, dword ptr [g_outputStorage + 8 + 384]
        sub esi, 4
        cmp dword ptr [g_creatureDefinition], 2
        je rank_rear_anchor
        cmp dword ptr [g_outputStorage + 8 + 740], 0
        jle rank_column
    rank_rear_anchor:
        inc esi
    rank_column:
        mov dword ptr [g_outputStorage + 8 + 904], edi
        call footprint_free
        test eax, eax
        jnz rank_lane
        cmp byte ptr [g_superadminEnabled], 0
        je rank_advance
        cmp dword ptr [g_creatureDefinition], 2
        jne rank_advance
        // 857160 tries candidate local row r, then r+1 for a large unit.
        // Keep r's score/tie priority even when the accepted anchor is shifted.
        inc edi
        call footprint_free
        dec edi
        test eax, eax
        jz rank_advance
        lea eax, [edi + 1]
        mov dword ptr [g_outputStorage + 8 + 904], eax
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
        cmp byte ptr [g_superadminEnabled], 0
        je large_lane_previous_row
        cmp edi, 1
        je lane_clear
    large_lane_previous_row:
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
        // The first window row can be y=1, which cannot hold a 2x2 shooter.
        // In that one case the native first usable anchor is y=2. Keep every
        // other window index unchanged: shifting them broke obstacle arenas.
        cmp dword ptr [g_creatureDefinition], 2
        jne shooter_window_footprint_ready
        cmp dword ptr [g_outputStorage + 8 + 784], 0
        jne shooter_window_footprint_ready
        cmp edi, 2
        jne shooter_window_footprint_ready
        xor eax, eax
    shooter_window_footprint_ready:
        xor ebp, ebp
        cmp eax, dword ptr [g_outputStorage + 8 + 796]
        jge rank_compare
        inc ebp
    rank_compare:
        // Equal-score row tie: reverse five bits of y-1 and take the largest.
        // On a 12-row field this visits y=8,4,6,10,2,7,3,5,9,1.
        // PanUI's top labels are these visit ranks read at y=10..1:
        // 4,9,1,6,3,8,2,7,5,10. Score and strategy still take precedence.
        mov eax, edi
        dec eax
        // A 2x2 spread stack can occupy y=2 when local row zero (y=1) is
        // illegal. Keep row zero's tie rank; do not promote it to row one's.
        cmp byte ptr [g_useSpreadRows], 0
        je priority_row_ready
        cmp byte ptr [g_spreadFallback], 0
        jne priority_row_ready
        cmp dword ptr [g_creatureDefinition], 2
        jne priority_row_ready
        cmp edi, 2
        jne priority_row_ready
        xor eax, eax
    priority_row_ready:
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
        cmp byte ptr [g_superadminEnabled], 0
        je rank_save_score
        cmp dword ptr [g_creatureDefinition], 2
        jne rank_save_score
        mov eax, dword ptr [g_outputStorage + 8 + 904]
        mov dword ptr [g_outputStorage + 8 + 744], eax
    rank_save_score:
        mov dword ptr [g_outputStorage + 8 + 748], ebp
        mov dword ptr [g_outputStorage + 8 + 752], edx
    rank_advance:
        inc edi
        jmp rank_next
    rank_done:
        mov edx, dword ptr [g_outputStorage + 8 + 744]
        cmp edx, -1
        jne rank_selected
        cmp byte ptr [g_useSpreadRows], 0
        je next_model
        cmp byte ptr [g_spreadFallback], 0
        jne next_model
        // Native spread keeps an ordinary candidate list if its restricted
        // list cannot place a stack on this arena.
        mov byte ptr [g_spreadFallback], 1
        mov dword ptr [g_outputStorage + 8 + 744], -1
        mov dword ptr [g_outputStorage + 8 + 748], -1
        mov edi, 1
        jmp rank_next
    rank_selected:
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
        mov eax, dword ptr [g_definitionMaximum]
        bts dword ptr [g_outputStorage + 8 + 908], eax
        cmp byte ptr [g_projectionPlanning], 0
        je render_planned_model
        inc dword ptr [g_outputStorage + 8 + 496]
        jmp next_model
    render_planned_model:
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
        cmp dword ptr [g_candidateIdentity], 6
        jl primary_next_model
        inc dword ptr [g_outputStorage + 8 + 952]
        jmp model_loop
    primary_next_model:
        inc dword ptr [g_outputStorage + 8 + 952]
        mov eax, dword ptr [g_outputStorage + 8 + 952]
        cmp eax, dword ptr [g_plannedProjectionCount]
        jb model_loop
        cmp byte ptr [g_sourceSimpleLayout], 0
        jne restore
        cmp byte ptr [g_predictedDefensive], 0
        je ordinary_next_identity
        cmp dword ptr [g_candidateIdentity], 1
        jne protective_after_large
        mov dword ptr [g_candidateIdentity], 0
        call PrepareProtectiveCandidates
        jmp next_identity_ready
    protective_after_large:
        cmp dword ptr [g_candidateIdentity], 0
        jne primary_passes_done
        mov dword ptr [g_candidateIdentity], 2
        call PrepareProtectiveCandidates
        jmp next_identity_ready
    ordinary_next_identity:
        inc dword ptr [g_candidateIdentity]
    next_identity_ready:
        cmp byte ptr [g_superadminEnabled], 0
        je ordinary_phase_limit
        cmp dword ptr [g_candidateIdentity], 6
        jae primary_passes_done
        jmp phase_continue
    ordinary_phase_limit:
        cmp dword ptr [g_candidateIdentity], 3
        jae restore
    phase_continue:
        mov dword ptr [g_definitionMaximum], 0
        mov dword ptr [g_outputStorage + 8 + 952], 0
        jmp model_loop
    primary_passes_done:
        cmp byte ptr [g_superadminEnabled], 0
        je restore
        mov dword ptr [g_candidateIdentity], 6
        jmp residual_column_ready
    residual_pass_done:
        cmp dword ptr [g_candidateIdentity], 6
        jne residual_column_done
        mov dword ptr [g_candidateIdentity], 7
        mov dword ptr [g_outputStorage + 8 + 952], 0
        jmp model_loop
    residual_column_done:
        inc dword ptr [g_outputStorage + 8 + 912]
        cmp dword ptr [g_outputStorage + 8 + 912], 2
        jae restore
        mov dword ptr [g_candidateIdentity], 6
    residual_column_ready:
        mov dword ptr [g_outputStorage + 8 + 916], 2
        mov dword ptr [g_outputStorage + 8 + 920], 1
        mov dword ptr [g_outputStorage + 8 + 952], 0
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
        cmp byte ptr [g_projectionPlanning], 0
        je planning_finished
        cmp byte ptr [g_sourceSimpleLayout], 0
        je check_complete_plan
        call FinalizeSourceSimplePlan
        test al, al
        jz plan_failed
        jmp plan_succeeded
    check_complete_plan:
        mov eax, dword ptr [g_outputStorage + 8 + 496]
        cmp eax, dword ptr [g_plannedProjectionCount]
        je plan_succeeded
        call ExcludeWeakestProjection
        test al, al
        jz plan_failed
        call ResetProjectionAttempt
        jmp model_loop
    plan_succeeded:
        mov byte ptr [g_projectionPlanning], 0
        call ResetProjectionAttempt
        jmp model_loop
    plan_failed:
        mov byte ptr [g_projectionPlanning], 0
        mov dword ptr [g_outputStorage + 8 + 496], 0
    planning_finished:
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
    constexpr const auto& expectedAttack = h5::hooks::AdventureAttack.expected;
    if (memcmp(reinterpret_cast<const void*>(kAttackEntry), expectedAttack, sizeof(expectedAttack)) != 0) {
        return false;
    }
    constexpr const auto& expected = h5::hooks::PlacementRenderer.expected;
    if (memcmp(reinterpret_cast<const void*>(kRendererEntry), expected, sizeof(expected)) != 0) {
        return false;
    }
    constexpr const auto& expectedHover = h5::hooks::PlacementHover.expected;
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
    constexpr unsigned char expectedActorInput[] = {0xd9, 0x44, 0x24, 0x24, 0xd8, 0x43, 0x04};
    if (g_superadminEnabled && memcmp(reinterpret_cast<const void*>(kActorInputEntry),
                                    expectedActorInput, sizeof(expectedActorInput)) != 0) return false;
    constexpr unsigned char expectedHeroCorrection[] = {0x03, 0xd8, 0x8b, 0x44, 0x24, 0x28};
    if (g_superadminEnabled && memcmp(reinterpret_cast<const void*>(kHeroCorrectionEntry),
                                    expectedHeroCorrection, sizeof(expectedHeroCorrection)) != 0) return false;
    constexpr unsigned char expectedAuxiliary[] = {0x8b, 0x44, 0x24, 0x0c, 0x5f};
    if (g_superadminEnabled && memcmp(reinterpret_cast<const void*>(kAuxiliaryPowerEntry),
                                    expectedAuxiliary, sizeof(expectedAuxiliary)) != 0) return false;
    constexpr unsigned char expectedSourceStrength[] = {0x8b, 0x7d, 0x08, 0x8b, 0x54, 0x24, 0x0c};
    if (g_superadminEnabled && memcmp(reinterpret_cast<const void*>(kSourceStrengthEntry),
                                    expectedSourceStrength, sizeof(expectedSourceStrength)) != 0) return false;
    constexpr unsigned char expectedSplitSeed[] = {0x8b, 0x10, 0x6a, 0x64, 0x6a, 0x01};
    if (g_superadminEnabled && memcmp(reinterpret_cast<const void*>(kSplitSeedEntry),
                                    expectedSplitSeed, sizeof(expectedSplitSeed)) != 0) return false;
    constexpr unsigned char expectedScriptedSource[] = {0x8d, 0x8c, 0x24, 0x84, 0x00, 0x00, 0x00};
    if (g_superadminEnabled && memcmp(reinterpret_cast<const void*>(kScriptedSourceEntry),
                                    expectedScriptedSource, sizeof(expectedScriptedSource)) != 0) return false;
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
        kDeploymentEndEntry, kRendererEntry, kHoverEntry, 0x546f40, 0x578986, 0xa4eb10, kActorInputEntry, kHeroCorrectionEntry, kAuxiliaryPowerEntry, kSourceStrengthEntry, kSplitSeedEntry, kScriptedSourceEntry};
    const uintptr_t targets[] = {reinterpret_cast<uintptr_t>(AttackHook), reinterpret_cast<uintptr_t>(PlacementConstructorHook),
        reinterpret_cast<uintptr_t>(PlacementDestructorHook), reinterpret_cast<uintptr_t>(DeploymentEndHook),
        reinterpret_cast<uintptr_t>(RendererHook), reinterpret_cast<uintptr_t>(HoverHook),
        reinterpret_cast<uintptr_t>(ScreenTooltipHook), reinterpret_cast<uintptr_t>(ProjectionOutlineHook),
        reinterpret_cast<uintptr_t>(ProjectionTooltipHitTestHook), reinterpret_cast<uintptr_t>(ActorInputHook),
        reinterpret_cast<uintptr_t>(HeroCorrectionHook), reinterpret_cast<uintptr_t>(AuxiliaryPowerHook), reinterpret_cast<uintptr_t>(SourceStrengthHook), reinterpret_cast<uintptr_t>(SplitSeedHook), reinterpret_cast<uintptr_t>(ScriptedSourceHook)};
    const size_t sizes[] = {5, 6, 9, 5, 6, 6, 6, 6, 6, 7, 6, 5, 7, 6, 7};
    const size_t patchCount = g_superadminEnabled ? 15 : 9;
    DWORD protections[15]{};
    size_t prepared = 0;
    // Acquire every writable region before modifying any instruction. Several
    // entries share a page, so protection changes must unwind in reverse order.
    for (; prepared < patchCount; ++prepared) {
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
    for (size_t index = 0; index < patchCount; ++index) {
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
    if (g_publicCount == 0 || g_projectionPlanning) {
        return 1;
    }
    return static_cast<unsigned long>((g_publicCount << 29) | (g_outputStorage[8 + 496] << 26)
                                      | (g_outputStorage[8 + 504] << 17)
                                      | ((g_hoverX & 0x1f) << 12) | ((g_hoverY & 0x1f) << 7)
                                      | (reinterpret_cast<uintptr_t>(g_outputStorage + 8) & 0x0f)) + 1;
}

extern "C" __declspec(dllexport) unsigned long WorkshopDeploymentPreviewInstall() {
    wchar_t mode[8]{};
    g_superadminEnabled = GetEnvironmentVariableW(L"H5_PREVIEW_SUPERADMIN", mode, 8) == 1 && mode[0] == L'1';
    wchar_t spread[8]{};
    g_useSpreadRows = g_superadminEnabled
        && GetEnvironmentVariableW(L"H5_PREVIEW_SUPERADMIN_SPREAD", spread, 8) == 1 && spread[0] == L'1';
    return InstallRendererHook() ? 1 : 0;
}

#pragma comment(linker, "/EXPORT:WorkshopDeploymentPreviewSuperadminSourceTrace=_WorkshopDeploymentPreviewSuperadminSourceTrace@4")
extern "C" __declspec(dllexport) unsigned long __stdcall WorkshopDeploymentPreviewSuperadminSourceTrace(void* destination) {
    if (destination == nullptr) return 0;
    auto* snapshot = static_cast<uint32_t*>(destination);
    memset(snapshot, 0, 58 * sizeof(uint32_t));
    snapshot[0] = 7;
    snapshot[1] = g_superadminEnabled ? 1 : 0;
    if (!g_superadminEnabled || g_superadminSourceGeneration != g_placementGeneration) return 1;
    const auto count = static_cast<uint32_t>(g_superadminSourceCount);
    if (count > 7) return 0;
    snapshot[2] = g_placementGeneration;
    snapshot[3] = count;
    snapshot[56] = g_superadminSourceKind;
    snapshot[57] = g_superadminSourceModifiersKnown ? 1 : 0;
    for (uint32_t index = 0; index < count; ++index) {
        snapshot[4 + index * 2] = g_superadminSourceTypes[index];
        snapshot[5 + index * 2] = g_superadminSourceCounts[index];
        snapshot[18 + index] = static_cast<uint32_t>(g_superadminSourceSpeed[index]);
        snapshot[25 + index] = g_superadminSourceFlying[index];
    }
    memcpy(snapshot + 32, g_superadminSourceAggregate, sizeof(g_superadminSourceAggregate));
    snapshot[50] = g_superadminTerrainKnown ? 1 : 0;
    snapshot[51] = g_superadminTerrainMask;
    snapshot[52] = g_superadminTerrainType;
    snapshot[53] = g_superadminRngKnown ? 1 : 0;
    snapshot[54] = g_superadminRngState;
    snapshot[55] = g_superadminTerrainKnown ? reinterpret_cast<uint32_t>(g_grid) : 0;
    return g_superadminSourceGeneration == g_placementGeneration
        && count == static_cast<uint32_t>(g_superadminSourceCount) ? 1 : 0;
}

#pragma comment(linker, "/EXPORT:WorkshopDeploymentPreviewProjectionTrace=_WorkshopDeploymentPreviewProjectionTrace@4")
extern "C" unsigned long __stdcall WorkshopDeploymentPreviewProjectionTrace(void* destination) {
    if (destination != nullptr) {
        // 54 words: ABI7 fields followed by the pre-Start exclusion mask.
        // Ordinary quantities remain zero/unknown; explicit Superadmin owns them.
        auto* snapshot = static_cast<uint32_t*>(destination);
        const auto* modelCount = reinterpret_cast<volatile uint32_t*>(g_outputStorage + 8 + 496);
        const uint32_t count = *modelCount;
        const uint32_t generation = g_placementGeneration;
        if (count > 7) {
            return 0;
        }
        if (g_projectionPlanning) {
            // No speculative model records are observable while a dry pass
            // changes count/coordinates/exclusions on its owned scratch state.
            memset(snapshot, 0, 54 * sizeof(uint32_t));
            snapshot[0] = 8;
            snapshot[1] = g_publicCount;
            snapshot[3] = generation;
            return 1;
        }
        memset(snapshot, 0, 54 * sizeof(uint32_t));
        snapshot[0] = 8;
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
            snapshot[46 + index] = *reinterpret_cast<uint32_t*>(g_outputStorage + 8 + 864 + index * 4);
        }
        for (uint32_t index = 0; index < static_cast<uint32_t>(g_publicCount) && index < 7; ++index) {
            snapshot[34 + index] = g_publicBands[index];
        }
        snapshot[41] = g_useSpreadRows ? 1 : 0;
        snapshot[42] = g_predictedDefensive ? 1 : 0;
        snapshot[43] = g_estimatedSpreadDenominator;
        snapshot[44] = static_cast<uint32_t>(g_knownHeroAttack);
        snapshot[45] = g_knownHeroBattleFrenzy ? 1 : 0;
        snapshot[53] = g_predictionExcludedMask;
        return count == *modelCount && generation == static_cast<uint32_t>(g_placementGeneration)
            && snapshot[1] == static_cast<uint32_t>(g_publicCount)
            && snapshot[53] == g_predictionExcludedMask && !g_projectionPlanning ? 1 : 0;
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

#pragma comment(linker, "/EXPORT:WorkshopDeploymentPreviewSuperadminInputTrace=_WorkshopDeploymentPreviewSuperadminInputTrace@4")
extern "C" __declspec(dllexport) unsigned long __stdcall WorkshopDeploymentPreviewSuperadminInputTrace(void* destination) {
    if (destination == nullptr) return 0;
    auto* snapshot = static_cast<uint32_t*>(destination);
    constexpr uint32_t rowWords = sizeof(FrozenActorInput) / sizeof(uint32_t);
    constexpr uint32_t metadata = 8 + kActorInputCapacity * rowWords;
    constexpr uint32_t auxiliary = metadata + 39 + 3 + 64 * 6;
    constexpr uint32_t strategy = auxiliary + 3 + 256 * 6;
    constexpr uint32_t strengths = strategy + 10;
    constexpr uint32_t area = strengths + 2 + 256 * 40 + 4 + 24;
    memset(snapshot, 0, (area + 2 + 128 * 316 + 8) * sizeof(uint32_t));
    snapshot[0] = 15;
    snapshot[1] = g_superadminEnabled ? 1 : 0;
    snapshot[7] = rowWords;
    if (!g_superadminEnabled) return 1;
    const LONG sequence = g_actorInputSequence;
    if (sequence & 1) return 2;
    const uint32_t count = g_actorInputCount;
    if (count > kActorInputCapacity) return 0;
    snapshot[2] = g_actorInputGeneration;
    snapshot[3] = count;
    snapshot[4] = g_actorInputOverflow;
    snapshot[5] = g_actorInputsFrozen ? 1 : 0;
    snapshot[6] = g_actorInputWorld;
    memcpy(snapshot + 8, g_actorInputs, count * sizeof(FrozenActorInput));
    snapshot[metadata] = g_actorCoreMask;
    snapshot[metadata + 1] = g_actorCoreStackCounts[0];
    snapshot[metadata + 2] = g_actorCoreStackCounts[1];
    memcpy(snapshot + metadata + 3, g_actorCoreWords, sizeof(g_actorCoreWords));
    snapshot[metadata + 39] = g_heroCorrectionCount;
    snapshot[metadata + 40] = g_heroCorrectionOverflow;
    snapshot[metadata + 41] = g_heroCorrectionMask;
    memcpy(snapshot + metadata + 42, g_heroCorrections, g_heroCorrectionCount * sizeof(FrozenHeroCorrection));
    snapshot[auxiliary] = g_auxiliaryInputCount;
    snapshot[auxiliary + 1] = g_auxiliaryInputOverflow;
    snapshot[auxiliary + 2] = g_auxiliaryMask;
    memcpy(snapshot + auxiliary + 3, g_auxiliaryInputs, g_auxiliaryInputCount * sizeof(FrozenAuxiliaryPower));
    memcpy(snapshot + strategy, g_strategyTrace, sizeof(g_strategyTrace));
    if (g_sourceStrengthCount > 256) return 0;
    snapshot[strengths] = g_sourceStrengthCount;
    snapshot[strengths + 1] = g_sourceStrengthOverflow;
    memcpy(snapshot + strengths + 2, g_sourceStrengthInputs,
           g_sourceStrengthCount * sizeof(FrozenSourceStrength));
    memcpy(snapshot + strengths + 2 + 256 * 40, g_sourceSplitSeed, sizeof(g_sourceSplitSeed));
    memcpy(snapshot + strengths + 2 + 256 * 40 + 4, g_sourceComposition, sizeof(g_sourceComposition));
    if (g_areaInputCount > 128) return 0;
    snapshot[area] = g_areaInputCount;
    snapshot[area + 1] = g_areaInputOverflow;
    memcpy(snapshot + area + 2, g_areaInputs, g_areaInputCount * sizeof(FrozenAreaInput));
    memcpy(snapshot + area + 2 + 128 * 316, g_areaPolicyTrace, sizeof(g_areaPolicyTrace));
    memcpy(snapshot + area + 2 + 128 * 316 + 4, g_largePolicyTrace, sizeof(g_largePolicyTrace));
    return sequence == g_actorInputSequence ? 1 : 2;
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
