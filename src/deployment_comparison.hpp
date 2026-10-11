#pragma once
#include <array>
#include <cstdint>

namespace h5_preview {
enum class PlacementDecisionRule : uint32_t {
    Unknown, RankedRow, Simple, Protective, Residual, LinkedSupport, Solo
};
struct PlacementDecisionRecord {
    uint32_t type, quantity, footprint, order, phase, shooter;
    int32_t x, y, windowStart, windowLength;
    PlacementDecisionRule rule;
    uint32_t defensive, spread;
};
struct PlacementDecisionTrace {
    uint32_t version, placementGeneration, count, complete;
    PlacementDecisionRecord records[7];
};
static_assert(sizeof(PlacementDecisionRecord) == 52);
static_assert(sizeof(PlacementDecisionTrace) == 380);
// Player-domain values only: no actor identities, hooks, or SDK transport.
struct ComparisonStack {
    uint32_t type, quantity, footprint;
    int32_t x, y;
};

// A copied initial field, shared by the planner and its explanatory UI.
// Rows retain native coordinates; no actor, process or SDK pointers survive.
struct PlacementFieldSnapshot {
    uint32_t version, generation, width, height;
    uint32_t blockedRows[32];
};

inline bool CopyPlacementField(const unsigned char* blocked, uint32_t stride,
    uint32_t width, uint32_t height, uint32_t generation, PlacementFieldSnapshot& result) {
    result = {};
    if (!blocked || !generation || width < 8 || width > 32 || height < 4 || height > 32 ||
        stride < (width + 7) / 8 || stride > 1024 / height) { return false; }
    result.version = 1; result.generation = generation; result.width = width; result.height = height;
    for (uint32_t y = 0; y < height; ++y) {
        for (uint32_t x = 0; x < width; ++x) {
            if (blocked[y * stride + x / 8] & (1u << (x % 8))) { result.blockedRows[y] |= 1u << x; }
        }
    }
    return true;
}
enum class DeploymentDifference : uint32_t {
    Exact, PositionOnlyKnown, Moved, QuantityChanged, Unpredicted, Missing
};
struct DeploymentComparisonEntry {
    int32_t forecastIndex = -1, actualIndex = -1;
    DeploymentDifference difference = DeploymentDifference::Unpredicted;
};
struct DeploymentComparison {
    bool valid = false, quantitiesKnown = false, splitChanged = false;
    bool totalsChanged = false, typesChanged = false;
    uint32_t entryCount = 0, exactCount = 0, positionMatchCount = 0;
    std::array<DeploymentComparisonEntry, 14> entries{};
};
inline bool ValidComparisonStack(const ComparisonStack& stack, bool actual) {
    return stack.type && (!actual || stack.quantity) && stack.quantity <= INT32_MAX &&
        stack.footprint >= 1 && stack.footprint <= 2 &&
        stack.x >= 0 && stack.x < 32 && stack.y >= 0 && stack.y < 32;
}
inline DeploymentComparison CompareDeployments(const ComparisonStack* forecast, uint32_t forecastCount,
    const ComparisonStack* actual, uint32_t actualCount) {
    DeploymentComparison result{};
    if (forecastCount > 7 || !actualCount || actualCount > 7 ||
        (forecastCount && !forecast) || !actual) { return result; }
    result.quantitiesKnown = forecastCount != 0;
    for (uint32_t index = 0; index < forecastCount; ++index) {
        if (!ValidComparisonStack(forecast[index], false)) { return result; }
        result.quantitiesKnown = result.quantitiesKnown && forecast[index].quantity != 0;
    }
    for (uint32_t index = 0; index < actualCount; ++index) {
        if (!ValidComparisonStack(actual[index], true)) { return result; }
    }
    // At most seven stacks: bounded assignment avoids greedy mispairing of
    // duplicates. Exact tuples dominate all weaker pairings combined.
    constexpr int32_t Unreachable = -100000000;
    std::array<std::array<int32_t, 128>, 8> scores{};
    std::array<std::array<int32_t, 128>, 8> choices{};
    for (auto& row : scores) { row.fill(Unreachable); }
    for (auto& row : choices) { row.fill(-2); }
    scores[0][0] = 0;
    const uint32_t maskCount = 1u << actualCount;
    for (uint32_t forecastIndex = 0; forecastIndex < forecastCount; ++forecastIndex) {
        const auto& predicted = forecast[forecastIndex];
        for (uint32_t mask = 0; mask < maskCount; ++mask) {
            const int32_t previous = scores[forecastIndex][mask];
            if (previous == Unreachable) { continue; }
            if (previous > scores[forecastIndex + 1][mask]) {
                scores[forecastIndex + 1][mask] = previous;
                choices[forecastIndex + 1][mask] = -1;
            }
            for (uint32_t actualIndex = 0; actualIndex < actualCount; ++actualIndex) {
                if ((mask & (1u << actualIndex)) || predicted.type != actual[actualIndex].type) { continue; }
                const auto& observed = actual[actualIndex];
                const bool samePosition = predicted.x == observed.x && predicted.y == observed.y &&
                    predicted.footprint == observed.footprint;
                const bool sameQuantity = predicted.quantity && predicted.quantity == observed.quantity;
                const int32_t horizontal = predicted.x > observed.x ? predicted.x - observed.x : observed.x - predicted.x;
                const int32_t vertical = predicted.y > observed.y ? predicted.y - observed.y : observed.y - predicted.y;
                const int32_t score = previous + 100 - horizontal - vertical +
                    (sameQuantity ? 10000 : 0) + (samePosition ? 1000 : 0) +
                    (samePosition && sameQuantity ? 1000000 : 0);
                const uint32_t nextMask = mask | (1u << actualIndex);
                if (score > scores[forecastIndex + 1][nextMask]) {
                    scores[forecastIndex + 1][nextMask] = score;
                    choices[forecastIndex + 1][nextMask] = actualIndex;
                }
            }
        }
    }
    uint32_t bestMask = 0;
    for (uint32_t mask = 1; mask < maskCount; ++mask) {
        if (scores[forecastCount][mask] > scores[forecastCount][bestMask]) { bestMask = mask; }
    }
    const uint32_t usedActual = bestMask;
    for (uint32_t remaining = forecastCount; remaining > 0; --remaining) {
        const uint32_t forecastIndex = remaining - 1;
        auto& entry = result.entries[forecastIndex];
        entry.forecastIndex = forecastIndex;
        entry.actualIndex = choices[remaining][bestMask];
        if (entry.actualIndex < 0) { entry.difference = DeploymentDifference::Missing; continue; }
        bestMask ^= 1u << entry.actualIndex;
        const auto& predicted = forecast[forecastIndex];
        const auto& observed = actual[entry.actualIndex];
        const bool samePosition = predicted.x == observed.x && predicted.y == observed.y &&
            predicted.footprint == observed.footprint;
        if (samePosition) { ++result.positionMatchCount; }
        if (predicted.quantity && predicted.quantity != observed.quantity) {
            entry.difference = DeploymentDifference::QuantityChanged;
        } else if (!samePosition) { entry.difference = DeploymentDifference::Moved; }
        else if (!predicted.quantity) { entry.difference = DeploymentDifference::PositionOnlyKnown; }
        else { entry.difference = DeploymentDifference::Exact; ++result.exactCount; }
    }
    result.entryCount = forecastCount;
    for (uint32_t index = 0; index < actualCount; ++index) {
        if (!(usedActual & (1u << index))) {
            result.entries[result.entryCount++] = {-1, static_cast<int32_t>(index), DeploymentDifference::Unpredicted};
        }
    }
    // Describe observed input differences. These flags do NOT establish why
    // any cell changed; causal wording requires a separate verified replay.
    for (uint32_t side = 0; side < 2; ++side) {
        const ComparisonStack* source = side ? actual : forecast;
        const uint32_t sourceCount = side ? actualCount : forecastCount;
        const ComparisonStack* other = side ? forecast : actual;
        const uint32_t otherCount = side ? forecastCount : actualCount;
        for (uint32_t index = 0; index < sourceCount; ++index) {
            uint64_t sourceTotal = 0, otherTotal = 0;
            uint32_t sourceStacks = 0, otherStacks = 0, sameQuantityHere = 0, sameQuantityThere = 0;
            for (uint32_t candidate = 0; candidate < sourceCount; ++candidate) {
                if (source[candidate].type != source[index].type) { continue; }
                sourceTotal += source[candidate].quantity; ++sourceStacks;
                if (source[candidate].quantity == source[index].quantity) { ++sameQuantityHere; }
            }
            for (uint32_t candidate = 0; candidate < otherCount; ++candidate) {
                if (other[candidate].type != source[index].type) { continue; }
                otherTotal += other[candidate].quantity; ++otherStacks;
                if (other[candidate].quantity == source[index].quantity) { ++sameQuantityThere; }
            }
            if (!otherStacks) { result.typesChanged = true; }
            if (result.quantitiesKnown) {
                if (sourceTotal != otherTotal) { result.totalsChanged = true; }
                else if (sourceStacks != otherStacks || sameQuantityHere != sameQuantityThere) { result.splitChanged = true; }
            }
        }
    }
    result.valid = true;
    return result;
}
enum class ReferenceDecisionStatus : uint32_t { Unavailable, MatchesFact, DisagreesWithFact };
struct ReferenceDecisionComparison {
    ReferenceDecisionStatus status = ReferenceDecisionStatus::Unavailable;
    std::array<int32_t, 7> decisionForActual{{-1, -1, -1, -1, -1, -1, -1}};
};
inline ReferenceDecisionComparison CompareReferenceDecisions(const PlacementDecisionTrace& reference,
    const ComparisonStack* actual, uint32_t actualCount) {
    ReferenceDecisionComparison result{};
    if (reference.version != 1 || reference.complete != 1 || !reference.placementGeneration ||
        !reference.count || reference.count > 7) { return result; }
    ComparisonStack prediction[7]{};
    for (uint32_t index = 0; index < reference.count; ++index) {
        const auto& decision = reference.records[index];
        if (decision.order != index + 1 || decision.phase > 7 || decision.shooter > 1 || decision.defensive > 1 ||
            decision.spread > 1 || static_cast<uint32_t>(decision.rule) > 6) { return result; }
        prediction[index] = {decision.type, decision.quantity, decision.footprint, decision.x, decision.y};
        if (!ValidComparisonStack(prediction[index], true)) { return result; }
    }
    const auto comparison = CompareDeployments(prediction, reference.count, actual, actualCount);
    if (!comparison.valid) { return result; }
    result.status = ReferenceDecisionStatus::DisagreesWithFact;
    if (reference.count != actualCount || comparison.exactCount != actualCount) { return result; }
    for (uint32_t index = 0; index < comparison.entryCount; ++index) {
        const auto& entry = comparison.entries[index];
        if (entry.actualIndex >= 0) { result.decisionForActual[entry.actualIndex] = entry.forecastIndex; }
    }
    result.status = ReferenceDecisionStatus::MatchesFact;
    return result;
}
}
