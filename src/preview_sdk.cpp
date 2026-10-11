#include "plugin_runtime.hpp"
#include "diagnostic_bus.hpp"
#include "placement_calculations.hpp"
#include "comparison_window.hpp"
#include "../game-api/include/h5/hooks.hpp"
#include "../game-api/include/h5/actor_input.hpp"
#include <cstdint>
// Reuse the existing planner/model renderer during migration. Managed builds
// exclude its independent hook installer, legacy exports and DllMain.
#ifndef H5_PREVIEW_MANAGED_SDK
#define H5_PREVIEW_MANAGED_SDK 1
#endif
#include "preview_plugin.cpp"

namespace {
struct PreviewSessionState {
    uint32_t version;
    uint32_t acceptedCalls;
    uint32_t adminCapture;
    uint32_t placementOwner;
};

struct PreviewSourceRecord {
    uint32_t source, context;
    h5::army::SourceStrengthSample sample;
};

struct PreviewInputCapture {
    uint32_t version, generation, count, overflow, frozen, observations;
    volatile LONG sequence;
    PreviewSourceRecord records[256];
    uint32_t actorCount, actorOverflow;
    h5::army::ActorInput actors[h5_preview::PlacementActorInputCapacity];
    uint32_t heroCorrectionCount, heroCorrectionOverflow;
    h5::army::HeroCorrectionInput heroCorrections[h5_preview::PlacementHeroCorrectionCapacity];
    uint32_t auxiliaryCount, auxiliaryOverflow, auxiliaryFrameFailures;
    h5::army::AuxiliaryPowerInput auxiliaryInputs[h5_preview::PlacementAuxiliaryInputCapacity];
    uint32_t worldIdentity, armyIdentities[2], sideReadFailures, sideConflict;
    uint32_t coreMask, coreErrors, coreStackCounts[2], coreInputEnds[2], coreCorrectionMasks[2];
    h5_preview::PlacementAggregate coreAggregates[2];
    uint32_t strategyMask, strategyTrace[2][10];

    void Begin() {
        InterlockedIncrement(&sequence);
        ++generation;
        count = overflow = observations = frozen = 0;
        actorCount = actorOverflow = 0;
        heroCorrectionCount = heroCorrectionOverflow = 0;
        auxiliaryCount = auxiliaryOverflow = auxiliaryFrameFailures = 0;
        worldIdentity = armyIdentities[0] = armyIdentities[1] = sideReadFailures = sideConflict = 0;
        coreMask = coreErrors = strategyMask = 0;
        memset(strategyTrace, 0, sizeof(strategyTrace));
        memset(coreStackCounts, 0, sizeof(coreStackCounts));
        memset(coreInputEnds, 0, sizeof(coreInputEnds));
        memset(coreCorrectionMasks, 0, sizeof(coreCorrectionMasks));
        memset(coreAggregates, 0, sizeof(coreAggregates));
        InterlockedIncrement(&sequence);
    }

    void Append(uint32_t source, uint32_t context, const h5::army::SourceStrengthSample& sample) {
        if (frozen || overflow) { return; }
        InterlockedIncrement(&sequence);
        ++observations;
        for (uint32_t index = 0; index < count; ++index) {
            const auto& previous = records[index];
            if (previous.source == source && previous.context == context &&
                previous.sample.type == sample.type && previous.sample.phase == sample.phase &&
                previous.sample.controlWord == sample.controlWord &&
                previous.sample.unsupported == sample.unsupported &&
                memcmp(&previous.sample.input, &sample.input, sizeof(sample.input)) == 0 &&
                previous.sample.calculated == sample.calculated) {
                InterlockedIncrement(&sequence);
                return;
            }
        }
        if (count == 256) {
            overflow = 1;
            InterlockedIncrement(&sequence);
            return;
        }
        records[count] = {source, context, sample};
        ++count;
        InterlockedIncrement(&sequence);
    }

    void CalculateCores(const float* strategySettings = nullptr) {
        coreMask = coreErrors = strategyMask = 0;
        memset(strategyTrace, 0, sizeof(strategyTrace));
        memset(coreStackCounts, 0, sizeof(coreStackCounts));
        memset(coreInputEnds, 0, sizeof(coreInputEnds));
        memset(coreCorrectionMasks, 0, sizeof(coreCorrectionMasks));
        memset(coreAggregates, 0, sizeof(coreAggregates));
        if (!frozen || !generation || !worldIdentity || !armyIdentities[0] || !armyIdentities[1] ||
            sideConflict || sideReadFailures || actorOverflow || heroCorrectionOverflow ||
            auxiliaryOverflow || auxiliaryFrameFailures) { coreErrors = 1; return; }
        alignas(16) unsigned char floatingState[512];
        __asm {
            lea eax, floatingState
            fxsave [eax]
            fninit
        }
        for (uint32_t side = 0; side < 2; ++side) {
            h5_preview::PlacementAggregate aggregate{};
            uint32_t count = 0, end = 0, applied = 0;
            if (!h5_preview::BuildFrozenPlacementCore(actors, actorCount, worldIdentity, armyIdentities[side],
                    generation, aggregate, count, &end, UINT_MAX, auxiliaryInputs, auxiliaryCount) || !count || end < count ||
                !h5_preview::ApplyCapturedPlacementCorrections(actors, actorCount, end - count, end,
                    generation, auxiliaryInputs, auxiliaryCount, heroCorrections, heroCorrectionCount,
                    aggregate, applied)) {
                coreErrors |= 2u << side;
                continue;
            }
            coreAggregates[side] = aggregate;
            coreStackCounts[side] = count;
            coreInputEnds[side] = end;
            coreCorrectionMasks[side] = applied;
            coreMask |= 1u << side;
        }
        bool completeArmies = coreMask == 3;
        for (uint32_t side = 0; completeArmies && side < 2; ++side) {
            for (uint32_t index = coreInputEnds[side] - coreStackCounts[side]; index < coreInputEnds[side]; ++index) {
                if (actors[index].armySize != coreStackCounts[side]) { completeArmies = false; break; }
            }
        }
        if (completeArmies && strategySettings) {
            for (uint32_t side = 0; side < 2; ++side) {
                const uint32_t opponent = 1 - side;
                const auto& own = coreAggregates[opponent];
                const auto& enemy = coreAggregates[side];
                const uint16_t capturedControl = static_cast<uint16_t>(actors[coreInputEnds[side] - 1].controlWord);
                __asm { fldcw capturedControl }
                const int enemyTotal = h5_preview::CalculateDefensivePower(enemy, own,
                    strategySettings[0], strategySettings[1], false);
                const int enemyRanged = h5_preview::CalculateDefensivePower(enemy, own,
                    strategySettings[0], strategySettings[1], true);
                const int ownRanged = h5_preview::CalculateDefensivePower(own, enemy,
                    strategySettings[0], strategySettings[1], true);
                const bool enemyCapability = h5_preview::FrozenArmyRangedCapability(actors,
                    coreInputEnds[side], coreStackCounts[side], ownRanged == 0);
                const bool ownCapability = h5_preview::FrozenArmyRangedCapability(actors,
                    coreInputEnds[opponent], coreStackCounts[opponent], enemyRanged == 0);
                h5_preview::WriteDefensiveStrategy(enemyTotal, enemyRanged, ownRanged,
                    enemyCapability, ownCapability, strategySettings[2], strategySettings[3], strategyTrace[side]);
                strategyMask |= 1u << side;
            }
        }
        __asm {
            lea eax, floatingState
            fxrstor [eax]
        }
    }
};
static_assert(sizeof(PreviewSourceRecord) == 152);
static_assert(offsetof(PreviewInputCapture, records) == 32);
static_assert(8192 + sizeof(PreviewInputCapture) <= heroes5_sdk::ContextCapacity);
constexpr uint32_t PolicyObservationCapacity = 64;
constexpr uint32_t CapabilityCallCapacity = PolicyObservationCapacity * 5;
struct PolicyVerification {
    uint32_t version, generation, count, failures, overflow;
    h5::army::NativePolicyAggregates observations[PolicyObservationCapacity];
    uint32_t capabilityContexts[PolicyObservationCapacity][8];
    uint32_t capabilityArmyCounts[PolicyObservationCapacity][3];
    uint32_t capabilityCallCount, capabilityCallFailures, capabilityCallOverflow;
    uint32_t capabilityCalls[CapabilityCallCapacity][5];
    uint32_t policyCallContexts[PolicyObservationCapacity][2];
    uint32_t intervalVersion, intervalGeneration;
    // Prefix ends before verification getters: actors, auxiliary inputs, corrections.
    uint32_t capturedInputCounts[PolicyObservationCapacity][3];
};
constexpr uint32_t PolicyVerificationOffset = 304 * 1024;
constexpr uint32_t PostStartVerificationOffset = 336 * 1024;
constexpr uint32_t PublicProjectionOffset = 352 * 1024;
static_assert(8192 + sizeof(PreviewInputCapture) <= PolicyVerificationOffset);
static_assert(PolicyVerificationOffset + sizeof(PolicyVerification) <= heroes5_sdk::ContextCapacity);

struct PostStartVerification {
    uint32_t version, generation, armed, positionCount, quantityCount, failures, overflow;
    volatile LONG sequence;
    h5::army::CombatUnitSample positions[7], quantities[7];
    uint32_t rosterObserved, defenderCount, rosterFailures, rosterReserved;
    // Appended player comparison record; preserve the research-v2 prefix.
    uint32_t playerVersion, playerGeneration, playerFrozen, playerForecastCount;
    uint32_t playerWidth, playerHeight, playerCommitted, playerCaptureFailures;
    h5::army::DeploymentStackSample playerForecast[7];
    h5::army::CommittedDeploymentSample playerActual;
    uint32_t playerOracleCountsAtCapture[3];
    uint32_t referenceAttackGeneration;
    h5_preview::PlacementDecisionTrace referenceTrace;
    wchar_t playerQuantityLabels[7][32];
    h5_preview::PlacementFieldSnapshot playerField;
    void Reset() {
        InterlockedIncrement(&sequence);
        version = 2;generation = armed = positionCount = quantityCount = failures = overflow = 0;
        rosterObserved = defenderCount = rosterFailures = rosterReserved = 0;
        memset(positions, 0, sizeof(positions));memset(quantities, 0, sizeof(quantities));
        playerVersion = 1; playerGeneration = playerFrozen = playerForecastCount = 0;
        playerWidth = playerHeight = playerCommitted = playerCaptureFailures = 0;
        memset(playerForecast, 0, sizeof(playerForecast)); playerActual = {};
        memset(playerOracleCountsAtCapture, 0, sizeof(playerOracleCountsAtCapture));
        referenceAttackGeneration = 0; referenceTrace = {};
        memset(playerQuantityLabels, 0, sizeof(playerQuantityLabels));
        playerField = {};
        InterlockedIncrement(&sequence);
    }
};
static_assert(PolicyVerificationOffset + sizeof(PolicyVerification) <= PostStartVerificationOffset);
static_assert(PostStartVerificationOffset + sizeof(PostStartVerification) <= PublicProjectionOffset);
static_assert(offsetof(PostStartVerification, playerVersion) == 1616);
static_assert(offsetof(PostStartVerification, playerActual) == 1816);
static_assert(offsetof(PostStartVerification, playerField) == 3024);
static_assert(sizeof(PostStartVerification) == 3168);

bool RestorePlayerComparisonUI(const PostStartVerification& state, HWND window) {
    if (state.playerVersion != 1 || !state.playerFrozen || state.playerCommitted != 1 ||
        state.playerCaptureFailures || !state.playerGeneration || state.playerForecastCount > 7 ||
        state.playerActual.failures || state.playerActual.overflow ||
        state.playerActual.counts[0] > 7 || state.playerActual.counts[1] > 7) { return false; }
    h5_preview::ComparisonStack forecast[7]{}, actual[7]{}, own[7]{};
    const auto copy = [](const h5::army::DeploymentStackSample& source) {
        return h5_preview::ComparisonStack{source.type, source.quantity, source.footprint, source.x, source.y};
    };
    for (uint32_t index = 0; index < state.playerForecastCount; ++index) { forecast[index] = copy(state.playerForecast[index]); }
    for (uint32_t index = 0; index < state.playerActual.counts[1]; ++index) { actual[index] = copy(state.playerActual.stacks[1][index]); }
    for (uint32_t index = 0; index < state.playerActual.counts[0]; ++index) { own[index] = copy(state.playerActual.stacks[0][index]); }
    if (!h5_preview::ComparisonWindow::SetBattle(forecast, state.playerForecastCount,
        actual, state.playerActual.counts[1], own, state.playerActual.counts[0],
        state.referenceAttackGeneration == state.playerGeneration ? &state.referenceTrace : nullptr,
        state.playerQuantityLabels, h5::army::ReadCreatureDisplayName,
        state.playerWidth, state.playerHeight, state.playerGeneration,
        state.playerField.version == 1 ? &state.playerField : nullptr)) { return false; }
    h5_preview::ComparisonWindow::ShowLauncher(window);
    return true;
}

void ObservePostStartResult(uint32_t command, const heroes5_sdk::EngineContext& context,
    PostStartVerification& verification) {
    if (!verification.armed || !verification.generation) { return; }
    if (command == 33) {
        h5::army::CombatRosterSample roster{};
        const bool valid = h5::army::ReadCombatRosterCount(context.registers, roster);
        InterlockedIncrement(&verification.sequence);
        if (!valid) { ++verification.rosterFailures; }
        else if (roster.side == 1 && roster.kind == 1) {
            if (verification.rosterObserved && verification.defenderCount != roster.count) {
                ++verification.rosterFailures;
            }
            verification.rosterObserved = 1;verification.defenderCount = roster.count;
        }
        InterlockedIncrement(&verification.sequence);
        return;
    }
    h5::army::CombatUnitSample sample{};
    const bool position = command == 31;
    const bool valid = position ? h5::army::ReadCombatPositionResult(context.registers, sample) :
        h5::army::ReadCombatQuantityResult(context.registers, sample);
    InterlockedIncrement(&verification.sequence);
    auto& count = position ? verification.positionCount : verification.quantityCount;
    auto* records = position ? verification.positions : verification.quantities;
    if (!valid) { ++verification.failures; }
    else if (count >= 7) { verification.overflow = 1; }
    else { records[count++] = sample; }
    InterlockedIncrement(&verification.sequence);
}

bool PolicyVerificationAvailable() {
    static const bool available = [] {
        const auto loader = GetModuleHandleW(L"dinput8.dll");
        return loader && GetProcAddress(loader, "Heroes5ModsEngineHookV2");
    }();
    return available;
}
bool InterceptionAvailable() {
    static const bool available=[] {
        const auto loader=GetModuleHandleW(L"dinput8.dll");
        return loader && GetProcAddress(loader,"Heroes5ModsEngineHookV3");
    }();
    return available;
}
void ObserveNativeCapabilityCall(uint32_t command, const heroes5_sdk::EngineContext& context,
    PreviewInputCapture& capture, PolicyVerification& verification, bool authorized) {
    if (!authorized || !capture.generation || verification.generation!=capture.generation ||
        verification.capabilityCallCount>CapabilityCallCapacity) { return; }
    h5::army::NativeCapabilityInput input{};
    const bool resultEvent=command>=27 && command<=29;
    const uint32_t nativeResult=context.registers.eax & 255u;
    const bool valid=resultEvent ? nativeResult<=1 : h5::army::ReadNativeCapabilityCall(context.registers,input);
    InterlockedIncrement(&capture.sequence);
    if (!valid) { ++verification.capabilityCallFailures; }
    else if (verification.capabilityCallCount==CapabilityCallCapacity) { verification.capabilityCallOverflow=1; }
    else {
        auto* row=verification.capabilityCalls[verification.capabilityCallCount++];
        row[0]=command;row[1]=resultEvent ? nativeResult : input.army;
        row[2]=resultEvent ? context.registers.ebp : input.rawUnitCount;
        row[3]=input.noRanged;row[4]=input.classRejected;
    }
    InterlockedIncrement(&capture.sequence);
}

void ObserveNativePolicy(const heroes5_sdk::EngineContext& context, PreviewInputCapture& capture,
    PolicyVerification& verification, bool authorized) {
    if (!authorized || !capture.generation ||
        verification.generation != capture.generation) { return; }
    h5::army::NativePolicyAggregates observed{};
    const bool valid = h5::army::ReadNativePolicyAggregates(context.registers, observed);
    const uint32_t inputCounts[]{capture.actorCount, capture.auxiliaryCount, capture.heroCorrectionCount};
    uint32_t capabilityContext[8]{};
    uint32_t armyCounts[3]{};
    if (valid && verification.count < PolicyObservationCapacity) {
        alignas(16) unsigned char floatingState[512];
        uint16_t originalControl;
        __asm { fnstcw originalControl }
        __asm { lea eax, floatingState }
        __asm { fxsave [eax] }
        __asm { fninit }
        __asm { fldcw originalControl }
        capabilityContext[7] = h5::army::ReadNativePolicyCapabilities(
            context.registers, capabilityContext, armyCounts) ? 0 : 1;
        capabilityContext[6] = capture.actorCount;
        __asm { lea eax, floatingState }
        __asm { fxrstor [eax] }
    }
    InterlockedIncrement(&capture.sequence);
    if (!valid) { ++verification.failures; }
    else if (verification.count == PolicyObservationCapacity) { verification.overflow = 1; }
    else {
        verification.observations[verification.count] = observed;
        verification.policyCallContexts[verification.count][0]=context.registers.ecx;
        verification.policyCallContexts[verification.count][1]=verification.capabilityCallCount;
        verification.intervalVersion = 1;
        verification.intervalGeneration = capture.generation;
        memcpy(verification.capturedInputCounts[verification.count], inputCounts, sizeof(inputCounts));
        memcpy(verification.capabilityContexts[verification.count], capabilityContext, sizeof(capabilityContext));
        memcpy(verification.capabilityArmyCounts[verification.count], armyCounts, sizeof(armyCounts));
        ++verification.count;
    }
    InterlockedIncrement(&capture.sequence);
}

// Game-owned models and public inputs survive payload HMR in the SDK buffer.
// No payload function/window-procedure address is stored here.
struct PublicProjectionState {
    uint32_t version;
    LONG attackGeneration, placementGeneration, renderedGeneration, publicCount;
    uint32_t publicTypes[7], publicBands[7];
    uint32_t placementOwner, root, grid, rendererRoot, rendererFactory;
    int cells[14], positions[28];
    alignas(16) unsigned char models[sizeof(g_outputStorage)];
    uint32_t hoverX, hoverY;
    unsigned tooltipChoice[7];
    ProjectionGlow glows[7];
    uint32_t uiVersion, projectionScreen;
    int tooltipClickSlot;
    uint32_t tooltipController;
    int detailsSlot;
    LONG detailsGeneration;
    int detailsPoint[2];
    uint32_t detailsRotator;
    unsigned detailsProjectionSlot;
    LONG detailsRotatorGeneration;
    uint32_t detailsRotatorOwned;
    // Appended mod-owned state; the existing public/UI prefix stays unchanged.
    // A zero version is the ordinary mode of pre-migration sessions.
    PreciseResearchState research;
    uint32_t publicPolicyVersion;
    PublicPlannerState publicPolicy;

    void Load() const {
        g_superadminEnabled = false;
        if (research.version == 3 && research.enabled) { research.Load(); }
        else if (publicPolicyVersion == 0xf0505303u) { publicPolicy.Load(); }
        else if (publicPolicyVersion == 0xf0505302u) {
            publicPolicy.Load(); g_neutralTypesUnknown = false;
        }
        else { PublicPlannerState{}.Load(); }
        g_attackGeneration = attackGeneration;
        g_placementGeneration = placementGeneration;
        g_renderedGeneration = renderedGeneration;
        g_publicCount = publicCount;
        memcpy(g_publicTypes, publicTypes, sizeof(publicTypes));
        memcpy(g_publicBands, publicBands, sizeof(publicBands));
        g_placementOwner = reinterpret_cast<void*>(placementOwner);
        g_root = reinterpret_cast<void*>(root);g_grid = reinterpret_cast<void*>(grid);
        g_rendererRootArgument = rendererRoot;g_rendererFactoryArgument = rendererFactory;
        memcpy(g_cell, cells, sizeof(cells));memcpy(g_position, positions, sizeof(positions));
        memcpy(g_outputStorage, models, sizeof(models));
        g_originalRenderer = reinterpret_cast<void*>(kRendererEntry);
        g_hoverX = hoverX;g_hoverY = hoverY;
        memcpy(g_tooltipChoice, tooltipChoice, sizeof(tooltipChoice));
        memcpy(g_glows, glows, sizeof(glows));
        g_projectionScreen=uiVersion>=1 ? reinterpret_cast<uint32_t*>(projectionScreen) : nullptr;
        g_tooltipClickSlot=uiVersion>=1 ? tooltipClickSlot : -1;
        g_tooltipController=uiVersion>=2 ? reinterpret_cast<uint32_t*>(tooltipController) : nullptr;
        g_detailsSlot=uiVersion>=3 ? detailsSlot : -1;
        g_detailsGeneration=uiVersion>=3 ? detailsGeneration : -1;
        g_detailsPoint[0]=uiVersion>=3 ? detailsPoint[0] : 0;g_detailsPoint[1]=uiVersion>=3 ? detailsPoint[1] : 0;
        g_detailsRotator=uiVersion>=3 ? reinterpret_cast<uint32_t*>(detailsRotator) : nullptr;
        g_detailsProjectionSlot=uiVersion>=3 ? detailsProjectionSlot : 7;
        g_detailsRotatorGeneration=uiVersion>=3 ? detailsRotatorGeneration : -1;
        g_detailsRotatorOwned=uiVersion>=4 && detailsRotatorOwned==1;
    }
    void Save() {
        version = 1;
        attackGeneration = g_attackGeneration;
        placementGeneration = g_placementGeneration;
        renderedGeneration = g_renderedGeneration;
        publicCount = g_publicCount;
        memcpy(publicTypes, g_publicTypes, sizeof(publicTypes));
        memcpy(publicBands, g_publicBands, sizeof(publicBands));
        placementOwner = reinterpret_cast<uint32_t>(g_placementOwner);
        root = reinterpret_cast<uint32_t>(g_root);grid = reinterpret_cast<uint32_t>(g_grid);
        rendererRoot = g_rendererRootArgument;rendererFactory = g_rendererFactoryArgument;
        memcpy(cells, g_cell, sizeof(cells));memcpy(positions, g_position, sizeof(positions));
        memcpy(models, g_outputStorage, sizeof(models));
        hoverX = g_hoverX;hoverY = g_hoverY;
        memcpy(tooltipChoice, g_tooltipChoice, sizeof(tooltipChoice));
        memcpy(glows, g_glows, sizeof(glows));
        uiVersion=4;projectionScreen=reinterpret_cast<uint32_t>(g_projectionScreen);tooltipClickSlot=g_tooltipClickSlot;
        tooltipController=reinterpret_cast<uint32_t>(g_tooltipController);
        detailsSlot=g_detailsSlot;detailsGeneration=g_detailsGeneration;
        detailsPoint[0]=g_detailsPoint[0];detailsPoint[1]=g_detailsPoint[1];
        detailsRotator=reinterpret_cast<uint32_t>(g_detailsRotator);
        detailsProjectionSlot=g_detailsProjectionSlot;detailsRotatorGeneration=g_detailsRotatorGeneration;
        detailsRotatorOwned=g_detailsRotatorOwned ? 1u : 0u;
        // Ordinary rendering never snapshots hidden inputs. Once initialized,
        // the research snapshot also retains an explicit disabled mode.
        if (g_superadminEnabled) { research.Save(); }
        else {
            publicPolicy.Save(); publicPolicyVersion = 0xf0505303u;
            if (research.version == 3) { research.enabled = false; }
        }
        // This scratch cell pointer is used only during planning and can point
        // into the payload. It is recalculated before every model creation.
        *reinterpret_cast<uint32_t*>(models + 8 + 736) = 0;
    }
    void Release() {
        if (*reinterpret_cast<uint32_t*>(g_outputStorage + 8 + 728) != 0) {
            ReleaseProjectionModels();
        }
        ResetProjectionTooltipChoices();
        g_publicCount = 0;g_placementOwner = nullptr;g_root = nullptr;g_grid = nullptr;
        g_rendererRootArgument = g_rendererFactoryArgument = 0;
    }
};
static_assert(PolicyVerificationOffset + sizeof(PolicyVerification) <= PublicProjectionOffset);
static_assert(PublicProjectionOffset + sizeof(PublicProjectionState) <= heroes5_sdk::ContextCapacity);
// Permanent host-owned immutable native data, outside every migrated/reset state.
// Native UI may retain this address beyond a synchronous payload lease. It holds
// no payload function/data pointers, is never cleared/reused, and is restored out
// of an owned rotator before releasing that rotator's retained reference.
constexpr uint32_t DetailsNativeMethodsOffset = heroes5_sdk::ContextCapacity - 64;
static_assert(PublicProjectionOffset + sizeof(PublicProjectionState) <= DetailsNativeMethodsOffset);
static_assert(DetailsNativeMethodsOffset + sizeof(h5::hooks::DetailsRotatorMethods) == heroes5_sdk::ContextCapacity);

bool EnsurePreviewStorage(const heroes5_sdk::EngineContext& context) {
    if (context.residentSchema != 6 || context.residentBytes != heroes5_sdk::ContextCapacity ||
        !context.residentData) { return false; }
    uint32_t expectedMethods[16];
    memcpy(expectedMethods,h5::hooks::DetailsRotatorMethods,sizeof(expectedMethods));
    expectedMethods[5]=h5::hooks::DetailsRotationAvailable.address;
    const auto* nativeMethods=reinterpret_cast<const uint32_t*>(context.residentData+DetailsNativeMethodsOffset);
    g_detailsNativeMethods=memcmp(nativeMethods,expectedMethods,sizeof(expectedMethods))==0 ? nativeMethods+1 : nullptr;
    auto& capture = *reinterpret_cast<PreviewInputCapture*>(context.residentData + 8192);
    if (capture.version != 5 && capture.version != 6) { return capture.version == 0 || capture.version == 7; }
    constexpr uint32_t previousPublicOffset = 192 * 1024;
    const auto& previous = *reinterpret_cast<const PublicProjectionState*>(context.residentData + previousPublicOffset);
    if (previous.version > 1 || previous.publicCount < 0 || previous.publicCount > 7 || previous.uiVersion > 4 ||
        (previous.uiVersion >= 4 && previous.detailsRotatorOwned > 1)) { return false; }
    const uint32_t generation = capture.generation;
    alignas(16) unsigned char prefix[offsetof(PublicProjectionState, research)];
    memcpy(prefix, &previous, sizeof(prefix));
    // The enlarged input journal overlaps the old public location. Preserve
    // resource ownership first, and publish the new format only after migration.
    capture.version = UINT32_MAX;
    auto& state = *reinterpret_cast<PublicProjectionState*>(context.residentData + PublicProjectionOffset);
    memset(&state, 0, sizeof(state));
    memcpy(&state, prefix, sizeof(prefix));
    memset(reinterpret_cast<unsigned char*>(&capture) + sizeof(capture.version), 0,
        sizeof(capture) - sizeof(capture.version));
    capture.generation = generation;
    capture.sequence = 2;
    auto& verification = *reinterpret_cast<PolicyVerification*>(context.residentData + PolicyVerificationOffset);
    memset(&verification, 0, sizeof(verification));
    verification.version = 2;verification.generation = generation;
    auto& postStart = *reinterpret_cast<PostStartVerification*>(context.residentData + PostStartVerificationOffset);
    memset(&postStart, 0, sizeof(postStart));postStart.version = 2;
    MemoryBarrier();
    capture.version = 7;
    return true;
}

void UpdatePreciseInputs(uint32_t command, const heroes5_sdk::EngineContext& context) {
    if (command < 9 || command > 14) { return; }
    if (g_referenceCalculationActive) { return; }
    if (!EnsurePreviewStorage(context)) { return; }
    auto& state = *reinterpret_cast<PublicProjectionState*>(context.residentData + PublicProjectionOffset);
    if (state.version > 1 || state.publicCount < 0 || state.publicCount > 7) { return; }
    if (command != 14 && state.research.version != 3) { return; }
    // All ordinary capture primitives already refuse frozen inputs. Avoid
    // loading/copying their large journals for these late no-op callbacks.
    // A scripted-source event can start another attack and must still pass.
    if (command != 14 && state.research.actorInputsFrozen) { return; }
    // Domain captures use the same public generation/owner snapshot as rendering.
    state.Load();
    // Scripted combat may be the first attack in the session.
    if (command == 14) { ConfigureResearchMode(); }
    const bool displayFull = g_superadminEnabled;
    if (state.research.version == 3 && !state.research.Load()) { return; }
    g_superadminEnabled = true;
    alignas(16) unsigned char floatingState[512];
    __asm { lea eax, floatingState }
    __asm { fxsave [eax] }
    __try {
        const auto& frame = context.registers;
        const auto* stack = reinterpret_cast<const uint32_t*>(frame.savedEsp + 4);
        if (command == 9) {
            CaptureSuperadminActorInput(reinterpret_cast<const uint32_t*>(frame.esi), frame.edi,
                frame.ebp, stack[10], stack[12]);
        } else if (command == 10) {
            CaptureSuperadminHeroCorrection(frame.edi, static_cast<int32_t>(frame.ebx), static_cast<int32_t>(frame.eax));
        } else if (command == 11) {
            CaptureSuperadminAuxiliaryPower(stack[0], static_cast<int32_t>(stack[3]), stack[7]);
            // The original hook restores the caller's FPU before the second capture.
            __asm { lea eax, floatingState }
            __asm { fxrstor [eax] }
            CaptureAreaSpellInput(reinterpret_cast<const uint32_t*>(frame.esi), stack[8], stack[9]);
        } else if (command == 12) {
            const auto phase = *reinterpret_cast<const uint32_t*>(frame.ebp + 8);
            CaptureSourceStrengthInput(reinterpret_cast<const uint32_t*>(frame.esi),
                reinterpret_cast<const uint32_t*>(stack[3]), phase);
        } else if (command == 13) {
            CaptureSourceSplitSeed(reinterpret_cast<const uint32_t*>(frame.eax));
        } else if (command == 14) {
            CaptureScriptedSource(reinterpret_cast<const uint32_t*>(frame.savedEsp + 4 + 0x54));
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        // Refuse a precise calculation after an incomplete source frame.
        g_actorInputOverflow = 1;
        g_sourceStrengthOverflow = g_areaInputOverflow = 1;
        g_actorInputBusy = g_sourceStrengthBusy = g_areaInputBusy = false;
    }
    if (displayFull) { state.Save(); }
    else {
        state.research.Save(); state.research.enabled = false;
        if (command == 14) {
            // The scripted event owns a new attack, but its hidden army vector
            // is not an ordinary portrait. Retain only the new lifetime here.
            state.attackGeneration = g_attackGeneration;
            state.publicCount = 0; state.renderedGeneration = -1;
            memset(state.publicTypes, 0, sizeof(state.publicTypes));
            memset(state.publicBands, 0, sizeof(state.publicBands));
            state.publicPolicy = {}; state.publicPolicyVersion = 0xf0505303u;
            state.publicPolicy.neutralTypesUnknown = g_neutralTypesUnknown;
        }
        state.Load();
    }
    __asm { lea eax, floatingState }
    __asm { fxrstor [eax] }
}

void UpdatePublicProjections(uint32_t command, const heroes5_sdk::EngineContext& context) {
    // Native model creation reenters the renderer hook. Do not reload globals
    // from the previous resident snapshot while the outer renderer is active.
    static thread_local bool active = false;
    if (active || (command != 3 && command != 4 && command != 5 && command != 6 && command != 7 && command != 8 && command != 16)) { return; }
    if (!EnsurePreviewStorage(context)) { return; }
    auto& state = *reinterpret_cast<PublicProjectionState*>(context.residentData + PublicProjectionOffset);
    if (state.version > 1 || state.publicCount < 0 || state.publicCount > 7) { return; }
    if (state.version == 0) {
        const int initialCells[14]{13,5,12,6,12,4,12,8,11,3,11,9,10,5};
        memcpy(state.cells, initialCells, sizeof(initialCells));
        state.renderedGeneration = -1;
        state.version = 1;
    }
    active = true;
    state.Load();
    alignas(16) unsigned char floatingState[512];
    __asm { lea eax, floatingState }
    __asm { fxsave [eax] }
    auto& verification = *reinterpret_cast<PostStartVerification*>(context.residentData + PostStartVerificationOffset);
    bool published = false;
    // Publish the private reference, ordinary renderer and saved public bytes
    // as one transaction. A reference alone does not mean the forecast is ready;
    // an unavailable ordinary forecast is still a valid completed publication.
    InterlockedIncrement(&verification.sequence);
    __try {
        if (command == 3) {
            state.Release();
            ++g_attackGeneration;
            ConfigureResearchMode();
            const bool displayFull = g_superadminEnabled;
            g_superadminEnabled = true;
            ResetSuperadminInputCapture();
            CaptureSuperadminSource(nullptr);
            const uint32_t source = context.registers.eax;
            bool publicMonster = false;
            __try {
                publicMonster = source != 0 && *reinterpret_cast<const uint32_t*>(source) == 0xe18f7c;
            } __except (EXCEPTION_EXECUTE_HANDLER) { publicMonster = false; }
            if (publicMonster) {
                __asm { mov eax, source }
                __asm { call CapturePublicPortraits }
            }
            state.research.Save(); state.research.enabled = displayFull;
            if (!displayFull) {
                PublicPlannerState publicCapture{};
                publicCapture.neutralTypesUnknown = g_neutralTypesUnknown;
                memcpy(publicCapture.publicKnownCounts, g_publicKnownCounts, sizeof(g_publicKnownCounts));
                memcpy(publicCapture.publicQuantityLabels, g_publicQuantityLabels, sizeof(g_publicQuantityLabels));
                publicCapture.Load();
            }
        } else if (command == 6) {
            state.Release();
            // Public portraits were captured at attack, before placement exists.
            g_publicCount = state.publicCount;
            memcpy(g_publicTypes, state.publicTypes, sizeof(g_publicTypes));
            memcpy(g_publicBands, state.publicBands, sizeof(g_publicBands));
            ++g_placementGeneration;
            if (g_superadminSourceCount > 0) { g_superadminSourceGeneration = g_placementGeneration; }
            if (state.research.version == 3 && state.research.superadminSourceCount > 0) {
                state.research.superadminSourceGeneration = g_placementGeneration;
            }
            g_predictionExcludedMask = 0;g_plannedProjectionCount = 0;g_projectionPlanning = false;
            g_renderedGeneration = -1;
            g_placementOwner = reinterpret_cast<void*>(context.registers.ecx);
        } else if (command == 4 && context.registers.edi == reinterpret_cast<uint32_t>(g_placementOwner)) {
            uint32_t arguments[10]{};
            bool valid = false;
            __try {
                memcpy(arguments, reinterpret_cast<const void*>(context.registers.savedEsp + 4), sizeof(arguments));
                valid = arguments[0] == h5::hooks::PlacementRendererCaller;
            } __except (EXCEPTION_EXECUTE_HANDLER) { valid = false; }
            if (valid) {
                if (!g_superadminEnabled && !g_neutralTypesUnknown) {
                    ApplyScoutedSource(state.research, static_cast<const uint32_t*>(g_placementOwner));
                }
                if (!g_superadminEnabled && g_renderedGeneration != g_placementGeneration &&
                    (verification.referenceAttackGeneration != static_cast<uint32_t>(g_attackGeneration) ||
                     verification.referenceTrace.placementGeneration != static_cast<uint32_t>(g_placementGeneration))) {
                    h5_preview::PlacementDecisionTrace decisions{};
                    h5_preview::PlacementFieldSnapshot field{};
                    const bool complete = PlanReferencePlacement(state.research, context.registers.edi,
                        arguments[5], arguments[9], arguments[7], decisions, &field);
                    verification.referenceAttackGeneration = g_attackGeneration;
                    verification.referenceTrace = complete ? decisions : h5_preview::PlacementDecisionTrace{};
                    verification.referenceTrace.placementGeneration = g_placementGeneration;
                    verification.playerField = complete ? field : h5_preview::PlacementFieldSnapshot{};
                    state.research.actorInputsFrozen = true;
                }
                RenderPlacementPreview(context.registers.edi, arguments[0], arguments[5], arguments[9], arguments[7]);
                if (!g_superadminEnabled) {
                    CopyRenderedQuantityLabels(verification.playerQuantityLabels);
                }
            }
        } else if (command == 5) {
            __try {
                const auto* stack=reinterpret_cast<const uint32_t*>(context.registers.savedEsp+4);
                auto* screen=reinterpret_cast<uint32_t*>(context.registers.esi);
                if (stack[0]==0x54589e && screen && *screen==0xe1da84 &&
                    screen[0x488/4]==reinterpret_cast<uint32_t>(g_placementOwner)) { g_projectionScreen=screen; }
            } __except (EXCEPTION_EXECUTE_HANDLER) { }
            int coordinates[2]{};
            bool valid = false;
            __try {
                const auto* cell = *reinterpret_cast<const int* const*>(context.registers.savedEsp + 12);
                if (cell) {
                    coordinates[0] = cell[0];coordinates[1] = cell[1];
                    valid = coordinates[0] >= 0 && coordinates[0] < 32 && coordinates[1] >= 0 && coordinates[1] < 32;
                }
            } __except (EXCEPTION_EXECUTE_HANDLER) { valid = false; }
            // The original hover handler clears selection even without a valid cell.
            UpdatePlacementHover(context.registers.edx, valid ? coordinates : nullptr);
        } else if (command == 16 && context.registers.esi == reinterpret_cast<uint32_t>(g_placementOwner)) {
            if (g_detailsSlot>=0 && !g_detailsNativeMethods) {
                __try {
                    MEMORY_BASIC_INFORMATION methodsRegion{},codeRegion{};
                    auto* methods=reinterpret_cast<uint32_t*>(context.residentData+DetailsNativeMethodsOffset);
                    const uint32_t emptyMethods[16]{};
                    const auto& available=h5::hooks::DetailsRotationAvailable;
                    const auto image=GetModuleHandleW(nullptr);
                    DWORD process=0;
                    if (GetWindowThreadProcessId(context.window,&process)==GetCurrentThreadId() && process==GetCurrentProcessId() &&
                        VirtualQuery(reinterpret_cast<const void*>(0xe40468),&methodsRegion,sizeof(methodsRegion)) &&
                        methodsRegion.AllocationBase==image && methodsRegion.Type==MEM_IMAGE && methodsRegion.State==MEM_COMMIT &&
                        VirtualQuery(reinterpret_cast<const void*>(available.address),&codeRegion,sizeof(codeRegion)) &&
                        codeRegion.AllocationBase==image && codeRegion.Type==MEM_IMAGE && codeRegion.State==MEM_COMMIT &&
                        !(codeRegion.Protect&PAGE_GUARD) &&
                        (codeRegion.Protect&(PAGE_EXECUTE_READ|PAGE_EXECUTE_READWRITE|PAGE_EXECUTE_WRITECOPY)) &&
                        memcmp(reinterpret_cast<const void*>(available.address),available.expected,sizeof(available.expected))==0 &&
                        memcmp(reinterpret_cast<const void*>(0xe40468),h5::hooks::DetailsRotatorMethods,sizeof(emptyMethods))==0 &&
                        memcmp(methods,emptyMethods,sizeof(emptyMethods))==0) {
                        memcpy(methods,h5::hooks::DetailsRotatorMethods,sizeof(emptyMethods));
                        methods[5]=available.address;MemoryBarrier();g_detailsNativeMethods=methods+1;
                    }
                } __except (EXCEPTION_EXECUTE_HANDLER) { g_detailsNativeMethods=nullptr; }
            }
            ProcessProjectionDetails(false);
            const auto stack = context.registers.savedEsp + 4;
            ApplyProjectionOutline(context.registers.esi, reinterpret_cast<uint32_t*>(stack + 0x40),
                reinterpret_cast<int*>(stack + 0x90), false);
        } else if (command == 8 || (command == 7 && context.registers.ecx == reinterpret_cast<uint32_t>(g_placementOwner))) {
            if (command == 8) { FreezeSuperadminInputCapture(); }
            state.Release();
        }
        state.Save();
        published = true;
    } __finally {
        if (!published) {
            verification.referenceAttackGeneration = 0;
            verification.referenceTrace = {};
            verification.playerField = {};
        }
        __asm { lea eax, floatingState }
        __asm { fxrstor [eax] }
        active = false;
        InterlockedIncrement(&verification.sequence);
    }

}

bool HandlePreviewInterception(uint32_t command, heroes5_sdk::EngineInterceptionContext& borrowed) {
    if (borrowed.size!=sizeof(borrowed) || borrowed.version!=1 || borrowed.readOnly>1 ||
        (borrowed.readOnly && command!=17 && command!=22)) { return false; }
    auto& context=borrowed.engine;
    if (!EnsurePreviewStorage(context)) { return false; }
    auto& state=*reinterpret_cast<PublicProjectionState*>(context.residentData+PublicProjectionOffset);
    if (state.version>1 || state.publicCount<0 || state.publicCount>7 || state.uiVersion>4 ||
        (state.uiVersion>=4 && state.detailsRotatorOwned>1)) { return false; }
    if (!borrowed.readOnly) { state.Load(); }
    if (command==15 && HoveredProjectionSlot()>=0) {
        uint32_t* output=nullptr;const int* cursor=nullptr;
        bool ownScreen=false;
        __try {
            // The pinned source entry receives the screen's embedded tooltip
            // interface; its native prologue recovers the screen by subtracting 0x18c.
            auto* owner=g_projectionScreen;
            ownScreen=owner && context.registers.ecx==reinterpret_cast<uint32_t>(owner)+0x18c &&
                *owner==0xe1da84 && owner[0x488/4]==reinterpret_cast<uint32_t>(g_placementOwner);
            const auto* stack=reinterpret_cast<const uint32_t*>(context.registers.savedEsp+4);
            output=reinterpret_cast<uint32_t*>(stack[1]);cursor=reinterpret_cast<const int*>(stack[2]);
        } __except (EXCEPTION_EXECUTE_HANDLER) { ownScreen=false; }
        if (ownScreen && output && cursor) {
            alignas(16) unsigned char floatingState[512];uint16_t originalControl;
            __asm { fnstcw originalControl }
            __asm { lea eax,floatingState }
            __asm { fxsave [eax] }
            __asm { fninit }
            __asm { fldcw originalControl }
            const auto result=ScreenTooltipHook(reinterpret_cast<void*>(context.registers.ecx),nullptr,output,cursor);
            __asm { lea eax,floatingState }
            __asm { fxrstor [eax] }
            borrowed.result=reinterpret_cast<uint32_t>(result);borrowed.action=heroes5_sdk::EngineCallAction::ReturnEax;
        }
    } else if (command==17) {
        __try {
            const auto* stack=reinterpret_cast<const uint32_t*>(context.registers.savedEsp+4);
            const bool caller=stack[3]==0x6b8aad;
            const auto models=*reinterpret_cast<const uint32_t*>(g_outputStorage+8+496);
            const auto hovered=*reinterpret_cast<const uint32_t*>(g_outputStorage+8+504);
            if ((caller && models && hovered) || (!caller && g_detailsHitTest)) {
                const auto table=*reinterpret_cast<const uint32_t*>(context.registers.edi-0x68);
                const auto window=*reinterpret_cast<const uint32_t*>(table+context.registers.esi*4);
                auto* controller=reinterpret_cast<uint32_t*>(stack[1]);
                if (!borrowed.readOnly && caller && g_projectionScreen && controller &&
                    controller[0x10/4]==reinterpret_cast<uint32_t>(g_projectionScreen)+0x18c) {
                    const auto* provider=reinterpret_cast<const uint32_t*>(controller[0x44/4]);
                    if (provider && *provider==0xe34b74) { g_tooltipController=controller; }
                }
                if (ProjectionTooltipWindowIsDecoration(reinterpret_cast<const uint32_t*>(window),controller)) {
                    borrowed.engine.registers.ecx=table;borrowed.engine.registers.eax=window;
                    borrowed.action=heroes5_sdk::EngineCallAction::Branch;
                }
            }
        } __except (EXCEPTION_EXECUTE_HANDLER) { borrowed.action=heroes5_sdk::EngineCallAction::Continue; }
    } else if (command>=22 && command<=24) {
        const auto expectedSite=command==22 ? h5::hooks::ProjectionDetailsCanRotate.address :
            command==23 ? h5::hooks::ProjectionDetailsNext.address : h5::hooks::ProjectionDetailsPrevious.address;
        if (context.callSite!=expectedSite) { return true; }
        __try {
            auto* rotator=command==22 ? reinterpret_cast<uint32_t*>(context.registers.esi) :
                *reinterpret_cast<uint32_t**>(context.registers.esi+0x2c);
            const bool owned=g_detailsRotatorOwned && rotator && rotator==g_detailsRotator &&
                (*rotator==0xe4046c || (g_detailsNativeMethods && *rotator==reinterpret_cast<uint32_t>(g_detailsNativeMethods)));
            const bool canRotate=owned && ProjectionDetailsCanRotate(rotator,nullptr);
            if (command==22) {
                heroes5_sdk::Trace(heroes5_sdk::LogLevel::Debug,"deployment-preview",
                    canRotate ? "Public details grade switch available" :
                    owned ? "Public details has one grade" : "Details query belongs to another rotator");
            }
            if (canRotate) {
                context.registers.ecx=reinterpret_cast<uint32_t>(rotator);
                if (command==22) { context.registers.eax=1; }
                else {
                    alignas(16) unsigned char floatingState[512];uint16_t originalControl;
                    __asm { fnstcw originalControl }
                    __asm { lea eax,floatingState }
                    __asm { fxsave [eax] }
                    __asm { fninit }
                    __asm { fldcw originalControl }
                    RotateProjectionDetails(rotator,context.callSite==h5::hooks::ProjectionDetailsNext.address);
                    __asm { lea eax,floatingState }
                    __asm { fxrstor [eax] }
                    if (command==23) { context.registers.eax=*rotator; }
                    else { context.registers.edx=*rotator; }
                }
                borrowed.action=heroes5_sdk::EngineCallAction::Branch;
            }
        } __except (EXCEPTION_EXECUTE_HANDLER) { borrowed.action=heroes5_sdk::EngineCallAction::Continue; }
    } else if (command==20 || command==21) {
        __try {
            auto* provider=reinterpret_cast<uint32_t*>(context.registers.ecx);
            if (provider && *provider==0xe34b74 && g_tooltipController &&
                g_projectionScreen && *g_projectionScreen==0xe1da84 &&
                g_projectionScreen[0x488/4]==reinterpret_cast<uint32_t>(g_placementOwner) &&
                g_tooltipController[0x10/4]==reinterpret_cast<uint32_t>(g_projectionScreen)+0x18c &&
                g_tooltipController[0x44/4]==reinterpret_cast<uint32_t>(provider)) {
                alignas(16) unsigned char floatingState[512];uint16_t originalControl;
                __asm { fnstcw originalControl }
                __asm { lea eax,floatingState }
                __asm { fxsave [eax] }
                __asm { fninit }
                __asm { fldcw originalControl }
                if (command==20) { PrepareProjectionProviderWindow(provider); }
                else { AdvanceProjectionProviderGrade(provider); }
                __asm { lea eax,floatingState }
                __asm { fxrstor [eax] }
            }
        } __except (EXCEPTION_EXECUTE_HANDLER) { borrowed.action=heroes5_sdk::EngineCallAction::Continue; }
    }
    if (!borrowed.readOnly) { state.Save(); }
    return true;
}

uint32_t __cdecl DispatchPreview(uint32_t command, uint32_t argument,
    void* memory, uint32_t bytes, uint32_t* result) {
    if (!memory || bytes != sizeof(PreviewSessionState) || !result) { return 0; }
    if (command > 37 || (command == 19 && !PolicyVerificationAvailable())) { return 0; }
    // Explicit developer preview; no combat data is inferred or fabricated.
    // The main-thread bridge queues this call on the owning window thread.
    if (command == 34) {
        if (argument != 1) { return 0; }
        SetLastError(0);
        const bool shown = h5_preview::ComparisonWindow::ShowDemo();
        *result = shown ? 1 : 1000 + GetLastError(); return 1;
    }
    if (command == 36) {
        if (argument != 1) { return 0; }
        *result = h5_preview::ComparisonWindow::ShowBattle() ? 1u : 0u; return 1;
    }
    if (((command>=20 && command<=29) || (command>=31 && command<=36)) && !InterceptionAvailable()) { return 0; }
    auto& state = *static_cast<PreviewSessionState*>(memory);
    if (state.version != 0 && state.version != 3) { return 0; }
    if (command == 37) {
        if (argument > 1 || !SetNeutralTypeKnowledge(argument == 1)) { return 0; }
        state.version = 3; ++state.acceptedCalls;
        *result = argument; return 1;
    }
    if (command == 30) {
        if (argument > 1 || !SetResearchMode(argument == 1)) { return 0; }
        state.version = 3;++state.acceptedCalls;
        *result = argument;return 1;
    }
    if (command == 18) {
        if (argument > 1) { return 0; }
        state.adminCapture = argument;
    }
    if ((command >= 2 && command <= 17) || command >= 19) {
        const auto* context = reinterpret_cast<const heroes5_sdk::EngineContext*>(argument);
        if (!context || context->size != sizeof(heroes5_sdk::EngineContext) || context->version != 2 ||
            context->residentSchema != 6 || context->residentBytes != heroes5_sdk::ContextCapacity ||
            !context->residentData) { return 0; }
        if (command >= 3 && context->hasRegisters != 1) { return 0; }
        if (!EnsurePreviewStorage(*context)) { return 0; }
        auto& capture = *reinterpret_cast<PreviewInputCapture*>(context->residentData + 8192);
        if ((capture.version != 0 && capture.version != 7) || capture.count > 256 ||
            capture.actorCount > h5_preview::PlacementActorInputCapacity || capture.heroCorrectionCount > h5_preview::PlacementHeroCorrectionCapacity ||
            capture.auxiliaryCount > h5_preview::PlacementAuxiliaryInputCapacity) { return 0; }
        auto& verification = *reinterpret_cast<PolicyVerification*>(context->residentData + PolicyVerificationOffset);
        if ((verification.version != 0 && verification.version != 2) || verification.count > PolicyObservationCapacity) { return 0; }
        auto& postStart = *reinterpret_cast<PostStartVerification*>(context->residentData + PostStartVerificationOffset);
        if (postStart.version > 2 || postStart.positionCount > 7 || postStart.quantityCount > 7) { return 0; }
        if (command == 14) {
            h5_preview::ComparisonWindow::Close(); postStart.Reset(); capture.Begin();
            verification = {}; verification.version = 2; verification.generation = capture.generation;
        }
        if (command == 2) {
            h5_preview::ComparisonWindow::RefreshOwnerLayout(context->window);
            if (!h5_preview::ComparisonWindow::HasBattle()) { RestorePlayerComparisonUI(postStart, context->window); }
        }
        if (command == 35) {
            auto& borrowed = *reinterpret_cast<heroes5_sdk::EngineInterceptionContext*>(argument);
            if (borrowed.size != sizeof(borrowed) || borrowed.version != 1 || borrowed.readOnly ||
                context->callSite != h5::hooks::DeploymentCommitted.address) { return 0; }
            borrowed.action = heroes5_sdk::EngineCallAction::Continue;
            if (postStart.playerVersion == 1 && postStart.playerFrozen && !postStart.playerCommitted) {
                h5::army::CommittedDeploymentSample actual{};
                uint32_t fieldWidth = 0, fieldHeight = 0;
                const bool complete = h5::army::ReadCommittedDeployment(context->registers, actual) &&
                    h5::army::ReadCombatFieldDimensions(actual.world, fieldWidth, fieldHeight);
                InterlockedIncrement(&postStart.sequence);
                if (complete) {
                    postStart.playerActual = actual; postStart.playerCommitted = 1;
                    postStart.playerWidth = fieldWidth; postStart.playerHeight = fieldHeight;
                    postStart.playerOracleCountsAtCapture[0] = postStart.positionCount;
                    postStart.playerOracleCountsAtCapture[1] = postStart.quantityCount;
                    postStart.playerOracleCountsAtCapture[2] = postStart.rosterObserved;
                }
                else { postStart.playerActual = actual; ++postStart.playerCaptureFailures; }
                InterlockedIncrement(&postStart.sequence);
                if (complete) { RestorePlayerComparisonUI(postStart, context->window); }
            }
            state.version = 3; ++state.acceptedCalls; *result = 0; return 1;
        }
        if (command == 31 || command == 32 || command == 33) {
            auto& borrowed = *reinterpret_cast<heroes5_sdk::EngineInterceptionContext*>(argument);
            const auto site = command == 31 ? h5::hooks::CombatPositionResult.address : command == 32
                ? h5::hooks::CombatQuantityResult.address : h5::hooks::CombatRosterCount.address;
            if (borrowed.size != sizeof(borrowed) || borrowed.version != 1 || borrowed.readOnly || context->callSite != site) { return 0; }
            borrowed.action = heroes5_sdk::EngineCallAction::Continue;
            ObservePostStartResult(command, *context, postStart);
            state.version = 3;++state.acceptedCalls;*result = 0;return 1;
        }
        // Precise captures receive the original FPU state before diagnostic
        // readers run. Their inputs/results never come from verification data.
        if (command >= 9 && command <= 14) { UpdatePreciseInputs(command, *context); }
        if (command>=25 && command<=29) {
            auto& borrowed=*reinterpret_cast<heroes5_sdk::EngineInterceptionContext*>(argument);
            const uint32_t sites[]{h5::hooks::DefensiveCapabilityFirst.address,h5::hooks::DefensiveCapabilitySecond.address,
                h5::hooks::DefensiveCapabilityFirstResult.address,h5::hooks::DefensiveCapabilitySecondResult.address,
                h5::hooks::DefensiveDecisionStore.address};
            const auto site=sites[command-25];
            if (borrowed.size!=sizeof(borrowed) || borrowed.version!=1 || borrowed.readOnly ||
                context->callSite!=site || verification.capabilityCallCount>CapabilityCallCapacity) { return 0; }
            borrowed.action=heroes5_sdk::EngineCallAction::Continue;
            ObserveNativeCapabilityCall(command,*context,capture,verification,state.adminCapture==1);
            state.version=3;++state.acceptedCalls;*result=0;return 1;
        }
        if ((command==15 || command==17 || command>=20) && InterceptionAvailable()) {
            auto& borrowed=*reinterpret_cast<heroes5_sdk::EngineInterceptionContext*>(argument);
            if (!HandlePreviewInterception(command,borrowed)) { return 0; }
            state.version=3;++state.acceptedCalls;*result=0;return 1;
        }
        // SDK-owned event marker only; forecasting remains unavailable.
        ++*reinterpret_cast<uint32_t*>(context->residentData);
        if (command >= 3) {
            ++reinterpret_cast<uint32_t*>(context->residentData)[command - 2];
        }
        capture.version = 7;
        if (command == 3) {
            h5_preview::ComparisonWindow::Close();
            capture.Begin(); state.placementOwner = 0;
            postStart.Reset();
            InterlockedIncrement(&capture.sequence);
            verification = {}; verification.version = 2; verification.generation = capture.generation;
            InterlockedIncrement(&capture.sequence);
        }
        if (command == 19) { ObserveNativePolicy(*context, capture, verification, state.adminCapture == 1); }
        if (command == 6) { state.placementOwner = context->registers.ecx; }
        if (command == 7 && context->registers.ecx == state.placementOwner) { state.placementOwner = 0; }
        if (command == 8) {
            auto& projections = *reinterpret_cast<PublicProjectionState*>(context->residentData + PublicProjectionOffset);
            if (projections.attackGeneration <= 0) {
                // Loading a player module during placement can miss attack
                // discovery. Start still creates a fresh facts-only lifetime.
                capture.Begin(); projections.attackGeneration = capture.generation;
            }
            InterlockedIncrement(&postStart.sequence);
            const auto* planned = reinterpret_cast<const uint32_t*>(projections.models + 8);
            postStart.playerVersion = 1;
            postStart.playerGeneration = projections.attackGeneration;
            const bool forecastReady = projections.renderedGeneration == projections.placementGeneration &&
                planned[496 / 4] > 0 && planned[496 / 4] <= 7;
            postStart.playerForecastCount = forecastReady ? planned[496 / 4] : 0;
            postStart.playerWidth = forecastReady ? planned[384 / 4] : 0;
            postStart.playerHeight = forecastReady ? planned[388 / 4] : 0;
            // An unavailable forecast is also an immutable snapshot. Actual
            // deployment capture must not depend on a successful prediction.
            postStart.playerFrozen = postStart.playerGeneration ? 1u : 0u;
            postStart.playerCommitted = postStart.playerCaptureFailures = 0;
            postStart.playerActual = {};
            memset(postStart.playerForecast, 0, sizeof(postStart.playerForecast));
            for (uint32_t index = 0; index < postStart.playerForecastCount; ++index) {
                const uint32_t type = planned[640 / 4 + index];
                const auto* definition = reinterpret_cast<const uint32_t* (__fastcall*)(uint32_t)>(kCreatureDefinition)(type);
                postStart.playerForecast[index] = {0, type, planned[864 / 4 + index],
                    definition ? definition[0xdc / 4] : 0,
                    projections.cells[index * 2], projections.cells[index * 2 + 1]};
            }
            const auto& decisions = *reinterpret_cast<const h5_preview::PlacementDecisionTrace*>(projections.models + 8 + 976);
            if (decisions.version == 1 && decisions.complete == 1 && decisions.count <= 7 &&
                decisions.placementGeneration == static_cast<uint32_t>(projections.placementGeneration)) {
                postStart.referenceAttackGeneration = postStart.playerGeneration;
                postStart.referenceTrace = decisions;
                if (postStart.playerField.version != 1 || postStart.playerField.generation != postStart.playerGeneration) {
                    const auto* output = projections.models + 8;
                    h5_preview::CopyPlacementField(output + 2560, planned[524 / 4], planned[384 / 4],
                        planned[388 / 4], postStart.playerGeneration, postStart.playerField);
                }
            } else if (postStart.referenceAttackGeneration != postStart.playerGeneration) {
                postStart.referenceAttackGeneration = 0; postStart.referenceTrace = {};
            }
            postStart.version = 2;postStart.generation = projections.attackGeneration;
            postStart.armed = (state.adminCapture == 1 || (projections.research.version == 3 && projections.research.enabled)) ? 1u : 0u;
            postStart.positionCount = postStart.quantityCount = postStart.failures = postStart.overflow = 0;
            postStart.rosterObserved = postStart.defenderCount = postStart.rosterFailures = postStart.rosterReserved = 0;
            InterlockedIncrement(&postStart.sequence);
        }
        bool renderReady = false;
        if (command == 4 && state.adminCapture == 1 && !capture.frozen && capture.generation &&
            state.placementOwner && context->registers.edi == state.placementOwner) {
            __try {
                renderReady = *reinterpret_cast<const uint32_t*>(context->registers.savedEsp + 4) ==
                    h5::hooks::PlacementRendererCaller;
            } __except (EXCEPTION_EXECUTE_HANDLER) { renderReady = false; }
        }
        if ((renderReady || command == 8) && !capture.frozen) {
            InterlockedIncrement(&capture.sequence);
            capture.frozen = 1;
            if (state.adminCapture == 1) {
                float strategySettings[4]{};
                const bool hasSettings = h5::army::ReadPlacementStrategySettings(strategySettings);
                capture.CalculateCores(hasSettings ? strategySettings : nullptr);
            }
            InterlockedIncrement(&capture.sequence);
        }
        if (command == 9 && state.adminCapture == 1 && !capture.frozen && capture.generation != 0) {
            if (capture.actorCount == h5_preview::PlacementActorInputCapacity) {
                InterlockedIncrement(&capture.sequence);
                capture.actorOverflow = 1;
                InterlockedIncrement(&capture.sequence);
            } else {
                h5::army::ActorInput input{};
                h5::army::ReadActorInputFrame(context->registers, capture.generation,
                    input, h5_preview::SelectPlacementDamageCategory);
                h5::army::AuxiliaryPowerInput protection[2]{};
                h5::army::AuxiliaryPowerInput runic[h5::army::ActorRunicInputCapacity]{};
                uint32_t runicCount = 0;
                if (!h5::army::ReadActorRunicInputs(
                    reinterpret_cast<const uint32_t*>(context->registers.esi), input,
                    capture.actorCount + 1, runic, runicCount)) { input.unsupported |= 1024; }
                uint32_t protectionCount = 0;
                if (!h5::army::ReadActorProtectionInputs(
                    reinterpret_cast<const uint32_t*>(context->registers.esi), input,
                    capture.actorCount + 1, protection, protectionCount)) { input.unsupported |= 512; }
                uint32_t sides[2]{};
                const bool readSides = h5::army::ReadActorArmySides(input.world, sides);
                InterlockedIncrement(&capture.sequence);
                if (!readSides) { ++capture.sideReadFailures; }
                else if (capture.worldIdentity && (capture.worldIdentity != input.world ||
                    capture.armyIdentities[0] != sides[0] || capture.armyIdentities[1] != sides[1])) {
                    capture.sideConflict = 1;
                } else {
                    capture.worldIdentity = input.world;
                    capture.armyIdentities[0] = sides[0];
                    capture.armyIdentities[1] = sides[1];
                }
                capture.actors[capture.actorCount] = input;
                ++capture.actorCount;
                if (capture.auxiliaryCount + protectionCount + runicCount > h5_preview::PlacementAuxiliaryInputCapacity) { capture.auxiliaryOverflow = 1; }
                else {
                    for (uint32_t index = 0; index < protectionCount; ++index) {
                        capture.auxiliaryInputs[capture.auxiliaryCount++] = protection[index];
                    }
                    for (uint32_t index = 0; index < runicCount; ++index) {
                        capture.auxiliaryInputs[capture.auxiliaryCount++] = runic[index];
                    }
                }
                InterlockedIncrement(&capture.sequence);
            }
        }
        if (command == 10 && state.adminCapture == 1 && !capture.frozen && capture.generation != 0) {
            InterlockedIncrement(&capture.sequence);
            if (capture.heroCorrectionCount == h5_preview::PlacementHeroCorrectionCapacity) { capture.heroCorrectionOverflow = 1; }
            else {
                h5::army::ReadHeroCorrectionFrame(context->registers, capture.actorCount,
                    capture.generation, capture.heroCorrections[capture.heroCorrectionCount]);
                ++capture.heroCorrectionCount;
            }
            InterlockedIncrement(&capture.sequence);
        }
        if (command == 11 && state.adminCapture == 1 && !capture.frozen && capture.generation != 0) {
            h5::army::AuxiliaryPowerInput input{};
            const auto read = h5::army::ReadAuxiliaryPowerFrame(context->registers,
                capture.actorCount, capture.generation, input);
            if (read != h5::army::AuxiliaryReadResult::UnrelatedCaller) {
                InterlockedIncrement(&capture.sequence);
                if (read == h5::army::AuxiliaryReadResult::InvalidFrame) { ++capture.auxiliaryFrameFailures; }
                else if (capture.auxiliaryCount == h5_preview::PlacementAuxiliaryInputCapacity) { capture.auxiliaryOverflow = 1; }
                else {
                    capture.auxiliaryInputs[capture.auxiliaryCount] = input;
                    ++capture.auxiliaryCount;
                }
                InterlockedIncrement(&capture.sequence);
            }
        }
        if (command == 12 && state.adminCapture == 1 && !capture.frozen) {
            auto& sample = *reinterpret_cast<h5::army::SourceStrengthSample*>(context->residentData + 4096);
            h5::army::ReadSourceStrengthFrame(context->registers, sample);
            if (!sample.unsupported) {
                unsigned short originalControl = 0;
                const auto capturedControl = static_cast<unsigned short>(sample.controlWord);
                __asm { fnstcw originalControl }
                __asm { fldcw capturedControl }
                sample.calculated = h5_preview::CalculateSourceStrength(sample.input);
                __asm { fldcw originalControl }
            }
            uint32_t sourceContext = 0;
            __try {
                sourceContext = *reinterpret_cast<const uint32_t*>(context->registers.savedEsp + 16);
            } __except (EXCEPTION_EXECUTE_HANDLER) { sample.unsupported = 2; }
            capture.Append(context->registers.esi, sourceContext, sample);
        }
    }
    if ((command >= 3 && command <= 8) || command == 16) {
        const auto* context = reinterpret_cast<const heroes5_sdk::EngineContext*>(argument);
        UpdatePublicProjections(command, *context);
    }
    state.version = 3;
    ++state.acceptedCalls;
    // Status/admin admission; public model rendering is driven by owned game events.
    *result = command == 0 ? 1 : (command == 18 ? state.adminCapture : 0);
    return 1;
}

const heroes5_sdk::HookPluginApi previewApi{
    {{sizeof(heroes5_sdk::HookPluginApi), heroes5_sdk::HookPluginAbi, 3,
     sizeof(PreviewSessionState), DispatchPreview, 0, 0, 0,
     static_cast<uint32_t>(h5::hooks::ScriptDispatchCall.address),
     static_cast<uint32_t>(h5::hooks::ScriptDispatchTarget), 2},
    6, heroes5_sdk::ContextCapacity},
    {15, {{{static_cast<uint32_t>(h5::hooks::AdventureAttack.address), 3},
        {static_cast<uint32_t>(h5::hooks::PlacementRenderer.address), 4},
        {static_cast<uint32_t>(h5::hooks::PlacementHover.address), 5},
        {static_cast<uint32_t>(h5::hooks::PlacementConstructor.address), 6},
        {static_cast<uint32_t>(h5::hooks::PlacementDestructor.address), 7},
        {static_cast<uint32_t>(h5::hooks::DeploymentEnd.address), 8},
        {static_cast<uint32_t>(h5::hooks::ActorInput.address), 9},
        {static_cast<uint32_t>(h5::hooks::HeroCorrection.address), 10},
        {static_cast<uint32_t>(h5::hooks::AuxiliaryPower.address), 11},
        {static_cast<uint32_t>(h5::hooks::SourceStrength.address), 12},
        {static_cast<uint32_t>(h5::hooks::SourceSplitSeed.address), 13},
        {static_cast<uint32_t>(h5::hooks::ScriptedSource.address), 14},
        {static_cast<uint32_t>(h5::hooks::PlacementTooltip.address), 15},
        {static_cast<uint32_t>(h5::hooks::ProjectionOutline.address), 16},
        {static_cast<uint32_t>(h5::hooks::ProjectionTooltipHitTest.address), 17}}}}};
const heroes5_sdk::HookPluginApi previewVerificationApi = [] {
    auto api = previewApi;
    api.hooks.count = 16;
    api.hooks.entries[15] = {static_cast<uint32_t>(h5::hooks::PlacementPolicyInitialize.address), 19};
    return api;
}();
const heroes5_sdk::InterceptionPluginApi previewInterceptionApi=[] {
    heroes5_sdk::InterceptionPluginApi api{};
    api.base=previewVerificationApi;
    api.base.base.base.size=sizeof(api);api.base.base.base.abi=heroes5_sdk::InterceptionPluginAbi;
    const auto old=api.base.hooks;api.base.hooks={};
    for (uint32_t index=0;index<old.count;++index) {
        if (old.entries[index].command!=15 && old.entries[index].command!=17) {
            api.base.hooks.entries[api.base.hooks.count++]=old.entries[index];
        }
    }
    api.interceptions.count=16;
    auto& tooltip=api.interceptions.entries[0];tooltip.site=h5::hooks::PlacementTooltip.address;tooltip.command=15;
    tooltip.sourceBytes=sizeof(h5::hooks::PlacementTooltip.expected);
    memcpy(tooltip.sourceExpected,h5::hooks::PlacementTooltip.expected,tooltip.sourceBytes);
    tooltip.policy.allowReturn=1;tooltip.policy.stackPopBytes=8;
    auto& hit=api.interceptions.entries[1];hit.site=h5::hooks::ProjectionTooltipHitTest.address;hit.command=17;
    hit.sourceBytes=sizeof(h5::hooks::ProjectionTooltipHitTest.expected);
    memcpy(hit.sourceExpected,h5::hooks::ProjectionTooltipHitTest.expected,hit.sourceBytes);
    hit.policy.branch=h5::hooks::ProjectionTooltipSkip.address;
    hit.branchBytes=sizeof(h5::hooks::ProjectionTooltipSkip.expected);
    memcpy(hit.branchExpected,h5::hooks::ProjectionTooltipSkip.expected,hit.branchBytes);hit.readOnlyReentry=1;
    const auto& window=h5::hooks::ProjectionProviderWindow;
    auto& providerWindow=api.interceptions.entries[2];providerWindow.site=window.address;providerWindow.command=20;
    providerWindow.sourceBytes=sizeof(window.expected);memcpy(providerWindow.sourceExpected,window.expected,providerWindow.sourceBytes);
    const auto& click=h5::hooks::ProjectionProviderClick;
    auto& providerClick=api.interceptions.entries[3];providerClick.site=click.address;providerClick.command=21;
    providerClick.sourceBytes=sizeof(click.expected);memcpy(providerClick.sourceExpected,click.expected,providerClick.sourceBytes);
    const auto bindBranch=[&](uint32_t index,uint32_t command,const auto& source,const auto& continuation,bool pure) {
        auto& entry=api.interceptions.entries[index];entry.site=source.address;entry.command=command;
        entry.sourceBytes=sizeof(source.expected);memcpy(entry.sourceExpected,source.expected,entry.sourceBytes);
        entry.policy.branch=continuation.address;entry.branchBytes=sizeof(continuation.expected);
        memcpy(entry.branchExpected,continuation.expected,entry.branchBytes);entry.readOnlyReentry=pure ? 1u : 0u;
    };
    bindBranch(4,22,h5::hooks::ProjectionDetailsCanRotate,h5::hooks::ProjectionDetailsCanRotateContinue,true);
    bindBranch(5,23,h5::hooks::ProjectionDetailsNext,h5::hooks::ProjectionDetailsNextContinue,false);
    bindBranch(6,24,h5::hooks::ProjectionDetailsPrevious,h5::hooks::ProjectionDetailsPreviousContinue,false);
    const auto& firstCapability=h5::hooks::DefensiveCapabilityFirst;
    auto& firstCall=api.interceptions.entries[7];firstCall.site=firstCapability.address;firstCall.command=25;
    firstCall.sourceBytes=sizeof(firstCapability.expected);
    memcpy(firstCall.sourceExpected,firstCapability.expected,firstCall.sourceBytes);
    const auto& secondCapability=h5::hooks::DefensiveCapabilitySecond;
    auto& secondCall=api.interceptions.entries[8];secondCall.site=secondCapability.address;secondCall.command=26;
    secondCall.sourceBytes=sizeof(secondCapability.expected);
    memcpy(secondCall.sourceExpected,secondCapability.expected,secondCall.sourceBytes);
    const auto& firstResult=h5::hooks::DefensiveCapabilityFirstResult;
    auto& firstReturn=api.interceptions.entries[9];firstReturn.site=firstResult.address;firstReturn.command=27;
    firstReturn.sourceBytes=sizeof(firstResult.expected);
    memcpy(firstReturn.sourceExpected,firstResult.expected,firstReturn.sourceBytes);
    const auto& secondResult=h5::hooks::DefensiveCapabilitySecondResult;
    auto& secondReturn=api.interceptions.entries[10];secondReturn.site=secondResult.address;secondReturn.command=28;
    secondReturn.sourceBytes=sizeof(secondResult.expected);
    memcpy(secondReturn.sourceExpected,secondResult.expected,secondReturn.sourceBytes);
    const auto& decision=h5::hooks::DefensiveDecisionStore;
    auto& decisionStore=api.interceptions.entries[11];decisionStore.site=decision.address;decisionStore.command=29;
    decisionStore.sourceBytes=sizeof(decision.expected);
    memcpy(decisionStore.sourceExpected,decision.expected,decisionStore.sourceBytes);
    const auto bindObserver = [&](uint32_t index, uint32_t command, const auto& source) {
        auto& entry = api.interceptions.entries[index];entry.site = source.address;entry.command = command;
        entry.sourceBytes = sizeof(source.expected);memcpy(entry.sourceExpected, source.expected, entry.sourceBytes);
    };
    bindObserver(12,31,h5::hooks::CombatPositionResult);
    bindObserver(13,32,h5::hooks::CombatQuantityResult);
    bindObserver(14,33,h5::hooks::CombatRosterCount);
    bindObserver(15,35,h5::hooks::DeploymentCommitted);
    return api;
}();

}

uint32_t RetirePreviewUI(const heroes5_sdk::EngineContext* context, bool replacing) {
    if (!context || context->size!=sizeof(*context) || context->version!=2 || context->residentSchema!=6 ||
        context->residentBytes!=heroes5_sdk::ContextCapacity || !context->residentData) { return 0; }
    DWORD process=0;
    if (GetWindowThreadProcessId(context->window,&process)!=GetCurrentThreadId() || process!=GetCurrentProcessId()) { return 0; }
    h5_preview::ComparisonWindow::Close();
    if (!EnsurePreviewStorage(*context)) { return 0; }
    auto& state=*reinterpret_cast<PublicProjectionState*>(context->residentData+PublicProjectionOffset);
    if (state.version>1 || state.publicCount<0 || state.publicCount>7 || state.uiVersion>4 ||
        (state.uiVersion>=4 && state.detailsRotatorOwned>1)) { return 0; }
    alignas(16) unsigned char floatingState[512];uint16_t originalControl;
    __asm { fnstcw originalControl }
    __asm { lea eax,floatingState }
    __asm { fxsave [eax] }
    __asm { fninit }
    __asm { fldcw originalControl }
    state.Load();
    if (replacing) {
        // Placement and its models survive payload HMR. Retire transient cards
        // and the retained details rotator, but preserve the owned screen binding.
        auto* screen=g_projectionScreen;
        ResetProjectionTooltipChoices();
        if (screen && *screen==0xe1da84 &&
            screen[0x488/4]==reinterpret_cast<uint32_t>(g_placementOwner)) { g_projectionScreen=screen; }
    }
    else { state.Release(); }
    state.Save();
    __asm { lea eax,floatingState }
    __asm { fxrstor [eax] }
    return 1;
}
extern "C" uint32_t __cdecl Heroes5PluginFinalize(const heroes5_sdk::EngineContext* context) {
    return RetirePreviewUI(context, false);
}
extern "C" uint32_t __cdecl Heroes5PluginPrepareReplace(const heroes5_sdk::EngineContext* context) {
    return RetirePreviewUI(context, true);
}
#pragma comment(linker,"/EXPORT:Heroes5PluginFinalize=_Heroes5PluginFinalize")
#pragma comment(linker,"/EXPORT:Heroes5PluginPrepareReplace=_Heroes5PluginPrepareReplace")
extern "C" uint32_t __cdecl Heroes5PluginWindowInput(const heroes5_sdk::WindowInputContext* input) {
    if (!input || input->size!=sizeof(*input) || input->version!=1 || input->message!=WM_LBUTTONDBLCLK) { return 0; }
    const auto& context=input->engine;DWORD process=0;
    if (context.size!=sizeof(context) || context.version!=2 || context.residentSchema!=6 ||
        context.residentBytes!=heroes5_sdk::ContextCapacity || !context.residentData ||
        GetWindowThreadProcessId(context.window,&process)!=GetCurrentThreadId() || process!=GetCurrentProcessId()) { return 0; }
    if (!EnsurePreviewStorage(context)) { return 0; }
    auto& state=*reinterpret_cast<PublicProjectionState*>(context.residentData+PublicProjectionOffset);
    if (state.version>1 || state.publicCount<0 || state.publicCount>7 || state.uiVersion>4 ||
        (state.uiVersion>=4 && state.detailsRotatorOwned>1)) { return 0; }
    state.Load();
    if (g_projectionScreen && (*g_projectionScreen!=0xe1da84 ||
        g_projectionScreen[0x488/4]!=reinterpret_cast<uint32_t>(g_placementOwner))) { return 0; }
    ObserveProjectionWindowInput(input->message,input->lparam);state.Save();return 1;
}
#pragma comment(linker,"/EXPORT:Heroes5PluginWindowInput=_Heroes5PluginWindowInput")
extern "C" const heroes5_sdk::PluginApi* __cdecl Heroes5PluginQuery() {
    if (InterceptionAvailable()) { return &previewInterceptionApi.base.base.base; }
    return PolicyVerificationAvailable() ? &previewVerificationApi.base.base : &previewApi.base.base;
}
#pragma comment(linker, "/EXPORT:Heroes5PluginQuery=_Heroes5PluginQuery")
