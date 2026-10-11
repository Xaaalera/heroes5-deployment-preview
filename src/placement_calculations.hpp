#ifndef H5_PREVIEW_PLACEMENT_CALCULATIONS_HPP
#define H5_PREVIEW_PLACEMENT_CALCULATIONS_HPP
#include <cstdint>
#include <cstring>
#include <limits>
#include "../game-api/include/h5/source_strength.hpp"
#include "../game-api/include/h5/actor_input.hpp"

namespace h5_preview {
inline constexpr uint32_t PlacementActorInputCapacity = 1024;
inline constexpr uint32_t PlacementAuxiliaryInputCapacity = 4096;
inline constexpr uint32_t PlacementHeroCorrectionCapacity = 256;
// Source-army strength is a different calculation from the combat aggregate.
// Inputs are primitive source statistics/definition deltas and loaded settings;
// this helper never queries engine decisions or final battle descriptors.
using SourceStrengthInput = h5::army::SourceStrengthInput;

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
    int32_t runicNumerator = 0, runicDenominator = 0;
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

// Defensive policy uses different totals from the spread denominator.
int CalculateDefensivePower(const PlacementAggregate& aggregate, const PlacementAggregate& opponent,
    float increase, float decrease, bool rangedOnly) {
    uint16_t original, truncation;
    int defence = 1, power = 0;
    float defenceValue = 1.0f, delta;
    __asm fnstcw original
    truncation = original | 0x0c00;
    if (rangedOnly) {
        const float value = opponent.eligibleDefence;
        __asm {
            fld value
            fldcw truncation
            fistp defence
            fldcw original
            fild defence
            fstp defenceValue
        }
    }
    const float attack = rangedOnly ? aggregate.shooterAttack : aggregate.attack;
    __asm {
        fld attack
        fsub defenceValue
        fstp delta
    }
    float coefficient = delta > 0 ? increase : decrease;
    if (!(coefficient > 0)) { coefficient = 0; }
    const float one = 1.0f, multiplier = aggregate.multiplier, rangedDamage = aggregate.shooterDamage;
    const int damage = aggregate.damage;
    const int fixedExtra = static_cast<int>(static_cast<uint32_t>(aggregate.extra0) + static_cast<uint32_t>(aggregate.extra2));
    __asm { fld coefficient }
    __asm { fmul delta }
    if (delta > 0) { __asm fadd one }
    else { __asm fsubr one __asm fdivr one }
    if (rangedOnly) { __asm fmul rangedDamage }
    else { __asm fimul damage }
    __asm { fmul multiplier }
    if (rangedOnly) { __asm fiadd fixedExtra }
    __asm {
        fldcw truncation
        fistp power
        fldcw original
    }
    if (rangedOnly) { return power; }
    int extra = 0;
    if (CalculatePlacementPower(aggregate, opponent, increase, decrease, true) >
        CalculatePlacementPower(opponent, aggregate, increase, decrease, true)) {
        const float flying = opponent.flyingDamage, ground = opponent.groundDamage, ranged = opponent.shooterDamage;
        const int extraPower = aggregate.unused;
        uint16_t status;
        __asm {
            fld flying
            fadd ground
            fadd ranged
            ftst
            fnstsw status
            fstp st(0)
        }
        if ((status & 0x4100) == 0) {
            __asm {
                fld flying
                fadd ground
                fadd ranged
                fdivr ground
                fimul extraPower
                fldcw truncation
                fistp extra
                fldcw original
            }
        }
    }
    const uint32_t subtotal = static_cast<uint32_t>(fixedExtra) + static_cast<uint32_t>(power) + static_cast<uint32_t>(extra);
    if (subtotal > 0x70000000u) { return 0; }
    return static_cast<int>(subtotal + static_cast<uint32_t>(aggregate.magicPower));
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
    if (input.runicDenominator > 0) {
        const int32_t numerator = input.runicNumerator, denominator = input.runicDenominator;
        float fraction;
        __asm {
            fild numerator
            fidiv denominator
            fstp fraction
            fld fraction
            fmul tenth
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

// Protection adds the greater of its reserve and the divided health estimate.
// Preserve the original signed comparison, x87 division and truncation.
int32_t TransformPlacementProtection(int32_t health, int32_t capacity, float fraction) {
    if (capacity <= 0) { return health; }
    int32_t extra = capacity;
    if (fraction <= 0.99f) {
        const float one = 1.0f;
        int32_t limit;
        uint16_t original, truncated;
        __asm {
            fild health
            fld one
            fsub fraction
            fdivp st(1), st(0)
            fnstcw original
            mov ax, original
            or ax, 0x0c00
            mov truncated, ax
            fldcw truncated
            fistp limit
            fldcw original
        }
        if (extra <= limit) { extra = limit; }
    }
    return static_cast<int32_t>(static_cast<uint32_t>(health) + static_cast<uint32_t>(extra));
}

// Actor aggregate reconstruction.
bool ReadFrozenRunicContribution(const h5::army::ActorInput& input, uint32_t inputCount,
    const h5::army::AuxiliaryPowerInput* auxiliary, uint32_t auxiliaryCount,
    int32_t& numerator, int32_t& denominator) {
    numerator = denominator = 0;
    int32_t expected = -1;
    uint32_t observed = 0;
    for (uint32_t index = 0; index < auxiliaryCount; ++index) {
        const auto& row = auxiliary[index];
        if (row.aggregateIdentity != input.aggregateIdentity || row.inputCount != inputCount ||
            row.attackGeneration != input.attackGeneration) { continue; }
        if (row.caller != h5::army::ActorRunicDescriptorCount && row.caller != h5::army::ActorRunicAvailability) { continue; }
        if (row.controlWord != input.controlWord) { return false; }
        if (row.caller == h5::army::ActorRunicDescriptorCount) {
            if (expected >= 0 || row.value < 0 || row.value > 256) { return false; }
            expected = row.value;
        } else {
            ++observed;
            if (observed > 256) { return false; }
            denominator += 3;
            numerator += row.value == 0 ? 3 : row.value == 1 || row.value == 2 ? 1 : 0;
        }
    }
    if (expected < 0) { return observed == 0 && !(input.unsupported & 32u); }
    return observed == static_cast<uint32_t>(expected) && (!(input.unsupported & 32u) || numerator > 0);
}
bool BuildFrozenPlacementCore(const h5::army::ActorInput* inputs, uint32_t count,
                              uint32_t world, uint32_t army, uint32_t generation,
                              PlacementAggregate& result, uint32_t& stackCount, uint32_t* inputEnd = nullptr,
                              uint32_t includedMask = UINT_MAX,
                              const h5::army::AuxiliaryPowerInput* auxiliary = nullptr, uint32_t auxiliaryCount = 0,
                              uint32_t inputOffset = 0) {
    stackCount = 0;
    if (inputEnd != nullptr) *inputEnd = 0;
    if (inputs == nullptr || count == 0 || count > PlacementActorInputCapacity || world == 0 || army == 0) return false;
    if (auxiliaryCount > PlacementAuxiliaryInputCapacity || (auxiliaryCount && !auxiliary) || inputOffset > UINT_MAX - count) return false;
    const auto matches = [&](const h5::army::ActorInput& input) {
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
        int32_t numerator = 0, denominator = 0;
        if ((input.unsupported & ~32u) || !ReadFrozenRunicContribution(input, inputOffset + index + 1,
                auxiliary, auxiliaryCount, numerator, denominator) || input.source == 0 || input.type == 0 || input.quantity == 0
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
        ReadFrozenRunicContribution(input, inputOffset + index + 1, auxiliary, auxiliaryCount,
            action.runicNumerator, action.runicDenominator);
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

bool ApplyCapturedPlacementCorrections(const h5::army::ActorInput* inputs, uint32_t count,
    uint32_t inputBegin, uint32_t inputEnd, uint32_t generation,
    const h5::army::AuxiliaryPowerInput* auxiliary, uint32_t auxiliaryCount,
    const h5::army::HeroCorrectionInput* corrections, uint32_t correctionCount,
    PlacementAggregate& aggregate, uint32_t& appliedMask, uint32_t includedMask = UINT_MAX) {
    appliedMask = 0;
    if (!inputs || !count || count > PlacementActorInputCapacity || inputBegin >= inputEnd || inputEnd > count ||
        inputEnd - inputBegin > 7 || auxiliaryCount > PlacementAuxiliaryInputCapacity || correctionCount > PlacementHeroCorrectionCapacity ||
        (auxiliaryCount && !auxiliary) || (correctionCount && !corrections)) { return false; }
    const auto& anchor = inputs[inputEnd - 1];
    if (!anchor.aggregateIdentity || anchor.attackGeneration != generation) { return false; }
    for (uint32_t index = inputBegin; index < inputEnd; ++index) {
        const auto& input = inputs[index];
        if (input.aggregateIdentity != anchor.aggregateIdentity || input.world != anchor.world ||
            input.army != anchor.army || input.attackGeneration != generation) { return false; }
    }
    for (uint32_t index = 0; index < auxiliaryCount; ++index) {
        const auto& extra = auxiliary[index];
        if (extra.aggregateIdentity == anchor.aggregateIdentity && extra.attackGeneration == generation &&
            extra.inputCount > count) { return false; }
    }
    for (uint32_t index = 0; index < correctionCount; ++index) {
        const auto& correction = corrections[index];
        if (correction.aggregateIdentity == anchor.aggregateIdentity && correction.attackGeneration == generation &&
            (correction.inputCount > count || correction.controlWord > 0xffff)) { return false; }
    }
    for (uint32_t index = 0; index < auxiliaryCount; ++index) {
        const auto& extra = auxiliary[index];
        if (extra.aggregateIdentity != anchor.aggregateIdentity || extra.attackGeneration != generation) { continue; }
        const bool physical = extra.caller == 0xbfbb90 || extra.caller == 0xbfbbc3;
        const bool hero = extra.caller == 0xbfc194 && extra.inputCount == inputEnd;
        const bool selected = physical && extra.inputCount > inputBegin && extra.inputCount <= inputEnd &&
            (includedMask & (1u << (extra.inputCount - inputBegin - 1)));
        if (hero || selected) {
            aggregate.extra2 = static_cast<int32_t>(static_cast<uint32_t>(aggregate.extra2) +
                static_cast<uint32_t>(extra.value));
            appliedMask |= 1;
        }
    }
    bool hasProtection = false;
    for (uint32_t index = inputBegin; index < inputEnd; ++index) {
        if (!(includedMask & (1u << (index - inputBegin)))) { continue; }
        const auto& input = inputs[index];
        const h5::army::AuxiliaryPowerInput* capacity = nullptr;
        const h5::army::AuxiliaryPowerInput* fraction = nullptr;
        for (uint32_t extraIndex = 0; extraIndex < auxiliaryCount; ++extraIndex) {
            const auto& extra = auxiliary[extraIndex];
            if (extra.aggregateIdentity != anchor.aggregateIdentity || extra.attackGeneration != generation ||
                extra.inputCount != index + 1) { continue; }
            if (extra.caller == h5::army::ActorProtectionCapacity) {
                if (capacity) { return false; }
                capacity = &extra;
            } else if (extra.caller == h5::army::ActorProtectionFraction) {
                if (fraction) { return false; }
                fraction = &extra;
            }
        }
        if ((capacity == nullptr) != (fraction == nullptr)) { return false; }
        if (!capacity) { continue; }
        float value;
        memcpy(&value, &fraction->value, sizeof(value));
        if (capacity->value <= 0 || !(value >= 0 && value <= 1) ||
            capacity->controlWord != input.controlWord || fraction->controlWord != input.controlWord) { return false; }
        hasProtection = true;
    }
    if (hasProtection) {
        PlacementAggregate healthAggregate;
        PlacementWeights healthWeights;
        InitializePlacementAggregate(healthAggregate, healthWeights);
        uint16_t originalControl;
        __asm fnstcw originalControl
        for (uint32_t index = inputBegin; index < inputEnd; ++index) {
            if (!(includedMask & (1u << (index - inputBegin)))) { continue; }
            const auto& input = inputs[index];
            const uint16_t control = static_cast<uint16_t>(input.controlWord);
            __asm fldcw control
            int32_t health = TransformPlacementHealth(input.health, input.healthTransformFlags, input.healthScaleBits);
            int32_t capacity = 0;
            float fraction = 0;
            for (uint32_t extraIndex = 0; extraIndex < auxiliaryCount; ++extraIndex) {
                const auto& extra = auxiliary[extraIndex];
                if (extra.aggregateIdentity != anchor.aggregateIdentity || extra.attackGeneration != generation ||
                    extra.inputCount != index + 1) { continue; }
                if (extra.caller == h5::army::ActorProtectionCapacity) { capacity = extra.value; }
                else if (extra.caller == h5::army::ActorProtectionFraction) {
                    memcpy(&fraction, &extra.value, sizeof(fraction));
                }
            }
            health = TransformPlacementProtection(health, capacity, fraction);
            AccumulatePlacementHealth(healthAggregate, healthWeights, health, input.defence,
                input.defence, input.eligible != 0);
        }
        NormalizePlacementAggregate(healthAggregate, healthWeights);
        __asm fldcw originalControl
        aggregate.health = healthAggregate.health;
        aggregate.defence = healthAggregate.defence;
        aggregate.eligibleHealth = healthAggregate.eligibleHealth;
        aggregate.eligibleDefence = healthAggregate.eligibleDefence;
        appliedMask |= 4;
    }
    for (uint32_t index = correctionCount; index != 0; --index) {
        const auto& correction = corrections[index - 1];
        if (correction.aggregateIdentity != anchor.aggregateIdentity || correction.inputCount != inputEnd ||
            correction.attackGeneration != generation) { continue; }
        uint16_t original, captured = static_cast<uint16_t>(correction.controlWord);
        __asm fnstcw original
        __asm fldcw captured
        aggregate.multiplier = ApplyHeroActionCorrection(aggregate.multiplier, correction.firstScalar, correction.secondScalar);
        __asm fldcw original
        appliedMask |= 2;
        break;
    }
    return true;
}


bool FrozenArmyRangedCapability(const h5::army::ActorInput* inputs, uint32_t inputEnd,
                               uint32_t stackCount, bool noRanged) {
    for (uint32_t index = inputEnd - stackCount; index < inputEnd; ++index) {
        if (inputs[index].rangedCapability & 2u) continue;
        if (noRanged && inputs[index].ignoreWhenNoRanged) continue;
        if (!(inputs[index].rangedCapability & 1u)) return false;
    }
    return true;
}

void WriteDefensiveStrategy(int enemyTotal, int enemyRanged, int ownRanged,
    bool enemyCapability, bool ownCapability, float shareThreshold, float advantageThreshold,
    uint32_t* trace) {
    const float share = enemyTotal > 0 ? PlacementRatio(enemyRanged, enemyTotal) : 0;
    const float advantage = ownRanged == 0 ? 100.0f : PlacementRatio(enemyRanged, ownRanged);
    const bool defensive = enemyTotal > 0 &&
        (enemyCapability || (share > shareThreshold && advantage > advantageThreshold)) && !ownCapability;
    trace[0] = 1;
    trace[1] = defensive;
    trace[2] = enemyRanged;
    trace[3] = enemyTotal;
    trace[4] = ownRanged;
    memcpy(trace + 5, &share, sizeof(share));
    memcpy(trace + 6, &advantage, sizeof(advantage));
    trace[7] = enemyCapability;
    trace[8] = ownCapability;
    trace[9] = 0;
}

}
#endif
