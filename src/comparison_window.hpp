#pragma once
#include <windows.h>
#include <algorithm>
#include <array>
#include "deployment_comparison.hpp"
#include "../game-api/include/h5/camera_input.hpp"

#pragma comment(lib, "gdi32.lib")

namespace h5_preview {
// Mod-owned UI prototype. No SDK or game-memory dependency; sample data is
// deliberately labelled and must never be mistaken for a captured battle.
class ComparisonWindow {
    struct Strings {
        const wchar_t* defensiveExplanation = L"\u0417\u0430\u0449\u0438\u0442\u043d\u044b\u0439 \u0441\u0442\u0440\u043e\u0439: \u043f\u0435\u0440\u0435\u0434 \u043e\u0431\u0449\u0438\u043c \u043f\u0440\u043e\u0445\u043e\u0434\u043e\u043c \u0438\u0449\u0443\u0442\u0441\u044f \u043f\u043e\u0437\u0438\u0446\u0438\u0438 \u043f\u0440\u0438\u043a\u0440\u044b\u0442\u0438\u044f \u0441\u0442\u0440\u0435\u043b\u043a\u043e\u0432.";
        const wchar_t* spreadExplanation = L"\u0420\u0430\u0437\u0440\u0435\u0436\u0435\u043d\u0438\u0435: \u0441\u043d\u0430\u0447\u0430\u043b\u0430 \u043f\u0440\u043e\u0432\u0435\u0440\u044f\u044e\u0442\u0441\u044f \u0440\u0430\u0437\u043d\u0435\u0441\u0451\u043d\u043d\u044b\u0435 \u0440\u044f\u0434\u044b.";
        const wchar_t* decisionPhases[8] = {
            L"\u042d\u0442\u0430\u043f: \u043a\u0440\u0443\u043f\u043d\u044b\u0435 \u043d\u0435\u0441\u0442\u0440\u0435\u043b\u044f\u044e\u0449\u0438\u0435 \u043e\u0442\u0440\u044f\u0434\u044b.", L"\u042d\u0442\u0430\u043f: \u0441\u0442\u0440\u0435\u043b\u043a\u0438.",
            L"\u042d\u0442\u0430\u043f: \u043e\u0441\u043d\u043e\u0432\u043d\u0430\u044f \u0433\u0440\u0443\u043f\u043f\u0430 \u0441\u0432\u044f\u0437\u0430\u043d\u043d\u044b\u0445 \u043e\u0442\u0440\u044f\u0434\u043e\u0432.", L"\u042d\u0442\u0430\u043f: \u0441\u0432\u044f\u0437\u0430\u043d\u043d\u044b\u0435 \u0433\u043e\u0431\u043b\u0438\u043d\u044b.",
            L"\u042d\u0442\u0430\u043f: \u043e\u0442\u0440\u044f\u0434\u044b \u0441 \u0437\u0430\u0449\u0438\u0442\u043d\u044b\u043c\u0438 \u0441\u043f\u043e\u0441\u043e\u0431\u043d\u043e\u0441\u0442\u044f\u043c\u0438.", L"\u042d\u0442\u0430\u043f: \u043e\u0431\u0449\u0438\u0439 \u043f\u0440\u043e\u0445\u043e\u0434 \u043e\u0441\u0442\u0430\u0432\u0448\u0438\u0445\u0441\u044f \u043e\u0442\u0440\u044f\u0434\u043e\u0432.",
            L"\u042d\u0442\u0430\u043f: \u0437\u0430\u043f\u0430\u0441\u043d\u044b\u0435 \u043c\u0435\u0441\u0442\u0430 \u0434\u043b\u044f \u043a\u0440\u0443\u043f\u043d\u044b\u0445 \u043e\u0442\u0440\u044f\u0434\u043e\u0432.", L"\u042d\u0442\u0430\u043f: \u0437\u0430\u043f\u0430\u0441\u043d\u044b\u0435 \u043c\u0435\u0441\u0442\u0430 \u0434\u043b\u044f \u043c\u0430\u043b\u044b\u0445 \u043e\u0442\u0440\u044f\u0434\u043e\u0432."
        };
        const wchar_t* defensiveRemainder = L"\u042d\u0442\u0430\u043f: \u043e\u0441\u0442\u0430\u043b\u044c\u043d\u044b\u0435 \u043e\u0442\u0440\u044f\u0434\u044b \u043f\u0440\u0438\u043a\u0440\u044b\u0442\u0438\u044f.";
        const wchar_t* unknownCreature = L"\u0421\u0443\u0449\u0435\u0441\u0442\u0432\u043e";
        const wchar_t* noForecastStatus = L"\u041f\u0440\u043e\u0433\u043d\u043e\u0437 \u0434\u043e Start \u0431\u044b\u043b \u043d\u0435\u0434\u043e\u0441\u0442\u0443\u043f\u0435\u043d. \u041f\u043e\u043a\u0430\u0437\u0430\u043d\u0430 \u0444\u0430\u043a\u0442\u0438\u0447\u0435\u0441\u043a\u0430\u044f \u0440\u0430\u0441\u0441\u0442\u0430\u043d\u043e\u0432\u043a\u0430.";
        const wchar_t* factEntryFormat = L"%s \u00b7 %u\n%s\n\u041f\u0440\u043e\u0433\u043d\u043e\u0437 \u0434\u043e Start \u043d\u0435\u0434\u043e\u0441\u0442\u0443\u043f\u0435\u043d.\n\u0424\u0430\u043a\u0442: %s \u2014 %s.";
        const wchar_t* smallRowFormat = L"\u0420\u0430\u0437\u043c\u0435\u0440: 1 \u043a\u043b\u0435\u0442\u043a\u0430. \u0420\u044f\u0434 %u \u043d\u0430 \u0441\u0445\u0435\u043c\u0435.";
        const wchar_t* largeRowsFormat = L"\u0420\u0430\u0437\u043c\u0435\u0440: 2\u00d72 \u043a\u043b\u0435\u0442\u043a\u0438. \u0420\u044f\u0434\u044b %u \u0438 %u \u043d\u0430 \u0441\u0445\u0435\u043c\u0435.";
        const wchar_t* shooterWindowFormat = L"\u0427\u0438\u0441\u043b\u043e \u0440\u044f\u0434\u043e\u0432 \u0434\u043b\u044f \u0441\u0442\u0440\u0435\u043b\u043a\u043e\u0432: %u.";
        const wchar_t* namedEntryFormat = L"%s \u00b7 %u\n%s\n\u041f\u0440\u043e\u0433\u043d\u043e\u0437: %s \u2014 %s. \u0424\u0430\u043a\u0442: %s \u2014 %s.\n%s";
        const wchar_t* referenceUnavailable = L"\u0414\u0430\u043d\u043d\u044b\u0445 \u0434\u043b\u044f \u043e\u0431\u044a\u044f\u0441\u043d\u0435\u043d\u0438\u044f \u0432\u044b\u0431\u043e\u0440\u0430 \u043a\u043b\u0435\u0442\u043a\u0438 \u043f\u043e\u043a\u0430 \u043d\u0435\u0434\u043e\u0441\u0442\u0430\u0442\u043e\u0447\u043d\u043e.";
        const wchar_t* referenceMismatch = L"\u041f\u0440\u0438\u0447\u0438\u043d\u0430 \u0432\u044b\u0431\u043e\u0440\u0430 \u043a\u043b\u0435\u0442\u043a\u0438 \u043f\u043e\u043a\u0430 \u043d\u0435 \u043f\u043e\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043d\u0430.";
        const wchar_t* decisionFormat = L"%s\n\u041f\u043e\u0440\u044f\u0434\u043e\u043a \u0440\u0430\u0437\u043c\u0435\u0449\u0435\u043d\u0438\u044f: %u. %s\n%s";
        const wchar_t* decisionRules[7] = {
            L"\u041f\u0440\u0430\u0432\u0438\u043b\u043e \u0432\u044b\u0431\u043e\u0440\u0430 \u043a\u043b\u0435\u0442\u043a\u0438 \u043d\u0435 \u0437\u0430\u043f\u0438\u0441\u0430\u043d\u043e.",
            L"\u041a\u043b\u0435\u0442\u043a\u0430 \u0432\u044b\u0431\u0440\u0430\u043d\u0430 \u043f\u043e \u043f\u0440\u0438\u043e\u0440\u0438\u0442\u0435\u0442\u0430\u043c \u0440\u044f\u0434\u043e\u0432 \u0441\u0440\u0435\u0434\u0438 \u0434\u043e\u0441\u0442\u0443\u043f\u043d\u044b\u0445 \u043c\u0435\u0441\u0442.",
            L"\u0418\u0441\u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u043d\u0430 \u043f\u0440\u043e\u0441\u0442\u0430\u044f \u0441\u0445\u0435\u043c\u0430 \u0440\u0430\u0441\u0441\u0442\u0430\u043d\u043e\u0432\u043a\u0438 \u0434\u043b\u044f \u044d\u0442\u043e\u0433\u043e \u0441\u043e\u0441\u0442\u0430\u0432\u0430.",
            L"\u041a\u043b\u0435\u0442\u043a\u0430 \u0432\u044b\u0431\u0440\u0430\u043d\u0430 \u0437\u0430\u0449\u0438\u0442\u043d\u043e\u0439 \u0432\u0435\u0442\u043a\u043e\u0439 \u0440\u0430\u0441\u0441\u0442\u0430\u043d\u043e\u0432\u043a\u0438 \u0441 \u043f\u0440\u043e\u0432\u0435\u0440\u043a\u043e\u0439 \u0441\u0432\u043e\u0431\u043e\u0434\u043d\u043e\u0433\u043e \u043c\u0435\u0441\u0442\u0430.",
            L"\u041e\u0442\u0440\u044f\u0434 \u0440\u0430\u0437\u043c\u0435\u0449\u0451\u043d \u043d\u0430 \u044d\u0442\u0430\u043f\u0435 \u043e\u0441\u0442\u0430\u0432\u0448\u0438\u0445\u0441\u044f \u043e\u0442\u0440\u044f\u0434\u043e\u0432, \u0441 \u043f\u0435\u0440\u0435\u0431\u043e\u0440\u043e\u043c \u0434\u043e\u043f\u043e\u043b\u043d\u0438\u0442\u0435\u043b\u044c\u043d\u044b\u0445 \u043a\u043e\u043b\u043e\u043d\u043e\u043a.",
            L"\u041a\u043b\u0435\u0442\u043a\u0430 \u0432\u044b\u0431\u0440\u0430\u043d\u0430 \u0441\u043f\u0435\u0446\u0438\u0430\u043b\u044c\u043d\u044b\u043c \u043f\u0440\u0430\u0432\u0438\u043b\u043e\u043c \u0441\u0432\u044f\u0437\u0430\u043d\u043d\u043e\u0433\u043e \u0432\u0441\u043f\u043e\u043c\u043e\u0433\u0430\u0442\u0435\u043b\u044c\u043d\u043e\u0433\u043e \u043e\u0442\u0440\u044f\u0434\u0430.",
            L"\u0418\u0441\u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u043d\u043e \u043f\u0440\u0430\u0432\u0438\u043b\u043e \u0440\u0430\u0437\u043c\u0435\u0449\u0435\u043d\u0438\u044f \u0435\u0434\u0438\u043d\u0441\u0442\u0432\u0435\u043d\u043d\u043e\u0433\u043e \u043e\u0442\u0440\u044f\u0434\u0430."
        };
        const wchar_t* decisionRoles[2] = {L"\u0411\u043b\u0438\u0436\u043d\u0438\u0439 \u0431\u043e\u0439.", L"\u0421\u0442\u0440\u0435\u043b\u043e\u043a."};
        const wchar_t* title = L"\u041f\u0440\u0435\u0434\u0438\u043a\u0442\u043e\u0440 \u2014 \u043f\u043e\u0447\u0435\u043c\u0443 \u043d\u0435 \u0441\u043e\u0432\u043f\u0430\u043b\u043e? [\u0414\u0435\u043c\u043e\u043d\u0441\u0442\u0440\u0430\u0446\u0438\u044f]";
        const wchar_t* heading = L"\u0420\u0430\u0437\u0431\u043e\u0440 \u0440\u0430\u0441\u0441\u0442\u0430\u043d\u043e\u0432\u043a\u0438";
        const wchar_t* sample = L"\u0414\u0415\u041c\u041e\u041d\u0421\u0422\u0420\u0410\u0426\u0418\u042f \u0418\u041d\u0422\u0415\u0420\u0424\u0415\u0419\u0421\u0410 \u00b7 \u0443\u0441\u043b\u043e\u0432\u043d\u044b\u0439 \u0431\u043e\u0439, \u043d\u0435 \u0442\u0435\u043a\u0443\u0449\u0430\u044f \u0440\u0430\u0441\u0441\u0442\u0430\u043d\u043e\u0432\u043a\u0430";
        const wchar_t* forecast = L"\u041f\u0420\u041e\u0413\u041d\u041e\u0417 \u0414\u041e \u0411\u041e\u042f";
        const wchar_t* actual = L"\u0424\u0410\u041a\u0422 \u0412 \u041d\u0410\u0427\u0410\u041b\u0415 \u0411\u041e\u042f";
        const wchar_t* hint = L"\u041f\u043e\u0437\u0438\u0446\u0438\u0438 \u0434\u043e \u043f\u0435\u0440\u0432\u043e\u0433\u043e \u0445\u043e\u0434\u0430. \u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u043e\u0442\u0440\u044f\u0434 \u0434\u043b\u044f \u043f\u043e\u044f\u0441\u043d\u0435\u043d\u0438\u044f.";
        const wchar_t* ownArmy = L"\u0417\u0415\u041b\u0401\u041d\u042b\u0419 \u2014 \u0430\u0440\u043c\u0438\u044f \u0433\u0435\u0440\u043e\u044f";
        const wchar_t* realBattle = L"\u0420\u0435\u0430\u043b\u044c\u043d\u044b\u0439 \u0431\u043e\u0439: \u043f\u0440\u043e\u0433\u043d\u043e\u0437 \u0441\u043e\u0445\u0440\u0430\u043d\u0451\u043d \u0434\u043e Start, \u0444\u0430\u043a\u0442 \u0441\u043d\u044f\u0442 \u043f\u0440\u0438 \u043f\u0440\u0438\u043d\u044f\u0442\u0438\u0438 \u0440\u0430\u0441\u0441\u0442\u0430\u043d\u043e\u0432\u043a\u0438";
        const wchar_t* realTitle = L"\u041f\u0440\u0435\u0434\u0438\u043a\u0442\u043e\u0440 \u2014 \u0440\u0430\u0437\u0431\u043e\u0440 \u0440\u0430\u0441\u0441\u0442\u0430\u043d\u043e\u0432\u043a\u0438";
        const wchar_t* button = L"\u0420\u0430\u0441\u0441\u0442\u0430\u043d\u043e\u0432\u043a\u0430";
        const wchar_t* ownDescription = L"\u0410\u0440\u043c\u0438\u044f \u0433\u0435\u0440\u043e\u044f. \u041f\u043e\u043a\u0430\u0437\u0430\u043d\u044b \u043d\u0430\u0447\u0430\u043b\u044c\u043d\u044b\u0435 \u043f\u043e\u043b\u043e\u0436\u0435\u043d\u0438\u0435 \u0438 \u0447\u0438\u0441\u043b\u0435\u043d\u043d\u043e\u0441\u0442\u044c.";
        const wchar_t* statusFormat = L"\u041f\u0440\u043e\u0433\u043d\u043e\u0437: %u \u043e\u0442\u0440\u044f\u0434\u043e\u0432. \u0424\u0430\u043a\u0442: %u. \u0421\u043e\u0432\u043f\u0430\u043b\u043e \u043f\u043e \u043a\u043b\u0435\u0442\u043a\u0430\u043c: %u. \u041f\u0440\u043e\u0433\u043d\u043e\u0437 \u0441\u043e\u0445\u0440\u0430\u043d\u0451\u043d \u0434\u043e Start.";
        const wchar_t* unknownQuantity = L"\u043d\u0435\u0438\u0437\u0432\u0435\u0441\u0442\u043d\u043e";
        const wchar_t* missingStack = L"\u043d\u0435\u0442 \u043e\u0442\u0440\u044f\u0434\u0430";
        const wchar_t* splitDifference = L"\u0420\u0430\u0437\u0434\u0435\u043b\u0435\u043d\u0438\u0435 \u043d\u0430 \u043e\u0442\u0440\u044f\u0434\u044b \u043e\u0442\u043b\u0438\u0447\u0430\u0435\u0442\u0441\u044f. \u0415\u0433\u043e \u0432\u043b\u0438\u044f\u043d\u0438\u0435 \u043d\u0430 \u043a\u043b\u0435\u0442\u043a\u0438 \u0435\u0449\u0451 \u043d\u0435 \u043f\u043e\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043d\u043e \u043f\u0435\u0440\u0435\u0441\u0447\u0451\u0442\u043e\u043c.";
        const wchar_t* differences[6] = {
            L"\u0422\u0438\u043f, \u0447\u0438\u0441\u043b\u0435\u043d\u043d\u043e\u0441\u0442\u044c \u0438 \u043a\u043b\u0435\u0442\u043a\u0430 \u0441\u043e\u0432\u043f\u0430\u043b\u0438.",
            L"\u041a\u043b\u0435\u0442\u043a\u0430 \u0441\u043e\u0432\u043f\u0430\u043b\u0430. \u0422\u043e\u0447\u043d\u0430\u044f \u0447\u0438\u0441\u043b\u0435\u043d\u043d\u043e\u0441\u0442\u044c \u0434\u043e \u043d\u0430\u0447\u0430\u043b\u0430 \u0431\u043e\u044f \u043d\u0435 \u0431\u044b\u043b\u0430 \u0438\u0437\u0432\u0435\u0441\u0442\u043d\u0430.",
            L"\u041e\u0442\u0440\u044f\u0434 \u0437\u0430\u043d\u044f\u043b \u0434\u0440\u0443\u0433\u0443\u044e \u043a\u043b\u0435\u0442\u043a\u0443, \u0447\u0435\u043c \u0432 \u043f\u0440\u043e\u0433\u043d\u043e\u0437\u0435.",
            L"\u0427\u0438\u0441\u043b\u0435\u043d\u043d\u043e\u0441\u0442\u044c \u043e\u0442\u0440\u044f\u0434\u0430 \u043e\u0442\u043b\u0438\u0447\u0430\u0435\u0442\u0441\u044f \u043e\u0442 \u043f\u0440\u043e\u0433\u043d\u043e\u0437\u0430. \u042d\u0442\u043e \u043d\u0430\u0431\u043b\u044e\u0434\u0435\u043d\u0438\u0435, \u0430 \u043d\u0435 \u0434\u043e\u043a\u0430\u0437\u0430\u043d\u043d\u0430\u044f \u043f\u0440\u0438\u0447\u0438\u043d\u0430 \u0432\u044b\u0431\u043e\u0440\u0430 \u043a\u043b\u0435\u0442\u043a\u0438.",
            L"\u0422\u0430\u043a\u043e\u0433\u043e \u043e\u0442\u0440\u044f\u0434\u0430 \u043d\u0435 \u0431\u044b\u043b\u043e \u0432 \u043f\u0440\u043e\u0433\u043d\u043e\u0437\u0435. \u0412\u043e\u0437\u043c\u043e\u0436\u043d\u043e\u0435 \u0438\u0437\u043c\u0435\u043d\u0435\u043d\u0438\u0435 \u0441\u043e\u0441\u0442\u0430\u0432\u0430 \u0438\u043b\u0438 \u0440\u0430\u0437\u0434\u0435\u043b\u0435\u043d\u0438\u044f \u0435\u0449\u0451 \u043d\u0443\u0436\u043d\u043e \u043f\u0440\u043e\u0432\u0435\u0440\u0438\u0442\u044c.",
            L"\u041f\u0440\u0435\u0434\u0441\u043a\u0430\u0437\u0430\u043d\u043d\u043e\u0433\u043e \u043e\u0442\u0440\u044f\u0434\u0430 \u043d\u0435\u0442 \u0432 \u0444\u0430\u043a\u0442\u0438\u0447\u0435\u0441\u043a\u043e\u0439 \u0440\u0430\u0441\u0441\u0442\u0430\u043d\u043e\u0432\u043a\u0435. \u0412\u043e\u0437\u043c\u043e\u0436\u043d\u043e\u0435 \u0438\u0437\u043c\u0435\u043d\u0435\u043d\u0438\u0435 \u0441\u043e\u0441\u0442\u0430\u0432\u0430 \u0438\u043b\u0438 \u0440\u0430\u0437\u0434\u0435\u043b\u0435\u043d\u0438\u044f \u0435\u0449\u0451 \u043d\u0443\u0436\u043d\u043e \u043f\u0440\u043e\u0432\u0435\u0440\u0438\u0442\u044c."
        };
        const wchar_t* close = L"\u0417\u0430\u043a\u0440\u044b\u0442\u044c: Esc \u0438\u043b\u0438 \u043a\u0440\u0435\u0441\u0442\u0438\u043a. \u041c\u043e\u0436\u043d\u043e \u043c\u0435\u043d\u044f\u0442\u044c \u0440\u0430\u0437\u043c\u0435\u0440 \u043e\u043a\u043d\u0430.";
        const wchar_t* symbols[6] = {L"\u041b", L"\u041a", L"\u0413", L"\u041b", L"\u041e", L"\u0410"};
        const wchar_t* details[6] = {
            L"\u041b\u0443\u0447\u043d\u0438\u043a\u0438 \u00b7 40\n\u041f\u0440\u043e\u0433\u043d\u043e\u0437 \u0438 \u0444\u0430\u043a\u0442\u0438\u0447\u0435\u0441\u043a\u0430\u044f \u043a\u043b\u0435\u0442\u043a\u0430 \u043e\u0442\u043b\u0438\u0447\u0430\u044e\u0442\u0441\u044f.\n\u041f\u0440\u0438\u043c\u0435\u0440 \u043f\u043e\u044f\u0441\u043d\u0435\u043d\u0438\u044f: \u0434\u0440\u0443\u0433\u043e\u0435 \u0440\u0430\u0437\u0434\u0435\u043b\u0435\u043d\u0438\u0435 \u043d\u0435\u0439\u0442\u0440\u0430\u043b\u043e\u0432 \u0438\u0437\u043c\u0435\u043d\u0438\u043b\u043e \u043f\u043e\u0441\u0442\u0440\u043e\u0435\u043d\u0438\u0435. \u0412 \u0433\u043e\u0442\u043e\u0432\u043e\u043c \u0440\u0430\u0437\u0431\u043e\u0440\u0435 \u044d\u0442\u0430 \u043f\u0440\u0438\u0447\u0438\u043d\u0430 \u043f\u043e\u044f\u0432\u0438\u0442\u0441\u044f \u0442\u043e\u043b\u044c\u043a\u043e \u043f\u043e\u0441\u043b\u0435 \u043f\u0440\u043e\u0432\u0435\u0440\u043a\u0438 \u043f\u0435\u0440\u0435\u0441\u0447\u0451\u0442\u043e\u043c.",
            L"\u041a\u0440\u0435\u0441\u0442\u044c\u044f\u043d\u0435 \u00b7 80\n\u041f\u043e\u0437\u0438\u0446\u0438\u044f \u0441\u043e\u0432\u043f\u0430\u043b\u0430: \u0441\u0438\u043d\u0438\u0439 \u0438 \u043e\u0440\u0430\u043d\u0436\u0435\u0432\u044b\u0439 \u043e\u0431\u043e\u0437\u043d\u0430\u0447\u0430\u044e\u0442 \u043e\u0434\u043d\u0443 \u043a\u043b\u0435\u0442\u043a\u0443.\n\u0412 \u0433\u043e\u0442\u043e\u0432\u043e\u043c \u0440\u0430\u0437\u0431\u043e\u0440\u0435 \u0437\u0434\u0435\u0441\u044c \u0431\u0443\u0434\u0443\u0442 \u0438\u0441\u0445\u043e\u0434\u043d\u044b\u0435 \u0434\u043e\u043f\u0443\u0449\u0435\u043d\u0438\u044f \u043f\u0440\u043e\u0433\u043d\u043e\u0437\u0430 \u0438 \u043f\u0440\u0430\u0432\u0438\u043b\u043e \u0432\u044b\u0431\u043e\u0440\u0430 \u043a\u043b\u0435\u0442\u043a\u0438.",
            L"\u0413\u0440\u0438\u0444\u043e\u043d\u044b \u00b7 12\n\u041a\u0440\u0443\u043f\u043d\u044b\u0439 \u043e\u0442\u0440\u044f\u0434 \u0437\u0430\u043d\u0438\u043c\u0430\u0435\u0442 \u0447\u0435\u0442\u044b\u0440\u0435 \u043a\u043b\u0435\u0442\u043a\u0438. \u041f\u0440\u043e\u0433\u043d\u043e\u0437 \u0438 \u0444\u0430\u043a\u0442 \u043e\u0442\u043b\u0438\u0447\u0430\u044e\u0442\u0441\u044f.\n\u041f\u0440\u0438\u043c\u0435\u0440 \u043d\u0435\u0438\u0437\u0432\u0435\u0441\u0442\u043d\u043e\u0439 \u043f\u0440\u0438\u0447\u0438\u043d\u044b: \u043e\u0442\u043b\u0438\u0447\u0438\u0435 \u043d\u0430\u0439\u0434\u0435\u043d\u043e, \u043d\u043e \u043f\u043e\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0451\u043d\u043d\u043e\u0433\u043e \u043e\u0431\u044a\u044f\u0441\u043d\u0435\u043d\u0438\u044f \u043f\u043e\u043a\u0430 \u043d\u0435\u0442.",
            L"\u0410\u0440\u043c\u0438\u044f \u0433\u0435\u0440\u043e\u044f: \u043b\u0443\u0447\u043d\u0438\u043a\u0438 \u00b7 100\n\u0421\u043e\u0441\u0442\u0430\u0432 \u0438 \u043a\u043e\u043b\u0438\u0447\u0435\u0441\u0442\u0432\u043e \u0441\u043e\u0431\u0441\u0442\u0432\u0435\u043d\u043d\u043e\u0439 \u0430\u0440\u043c\u0438\u0438 \u0438\u0437\u0432\u0435\u0441\u0442\u043d\u044b \u0438\u0433\u0440\u043e\u043a\u0443. \u0417\u0435\u043b\u0451\u043d\u044b\u043c \u043f\u043e\u043a\u0430\u0437\u0430\u043d\u043e \u0435\u0451 \u043f\u043e\u043b\u043e\u0436\u0435\u043d\u0438\u0435 \u0432 \u0443\u0441\u043b\u043e\u0432\u043d\u043e\u043c \u043f\u0440\u0438\u043c\u0435\u0440\u0435.",
            L"\u0410\u0440\u043c\u0438\u044f \u0433\u0435\u0440\u043e\u044f: \u043e\u0440\u0443\u0436\u0435\u043d\u043e\u0441\u0446\u044b \u00b7 55\n\u0417\u0435\u043b\u0451\u043d\u044b\u043c \u043f\u043e\u043a\u0430\u0437\u0430\u043d\u0430 \u0441\u043e\u0431\u0441\u0442\u0432\u0435\u043d\u043d\u0430\u044f \u0430\u0440\u043c\u0438\u044f. \u0415\u0451 \u043f\u043e\u043b\u043e\u0436\u0435\u043d\u0438\u0435 \u043d\u0430 \u0441\u0445\u0435\u043c\u0435 \u043d\u0435 \u043e\u0437\u043d\u0430\u0447\u0430\u0435\u0442, \u0447\u0442\u043e \u043c\u044b \u0438\u0441\u043f\u043e\u043b\u044c\u0437\u0443\u0435\u043c \u0432\u044b\u0431\u0440\u0430\u043d\u043d\u0443\u044e \u0438\u0433\u0440\u043e\u043a\u043e\u043c \u0440\u0430\u0441\u0441\u0442\u0430\u043d\u043e\u0432\u043a\u0443 \u0434\u043b\u044f \u043f\u0440\u043e\u0433\u043d\u043e\u0437\u0430.",
            L"\u0410\u0440\u043c\u0438\u044f \u0433\u0435\u0440\u043e\u044f: \u0430\u043d\u0433\u0435\u043b\u044b \u00b7 3\n\u041a\u0440\u0443\u043f\u043d\u044b\u0439 \u043e\u0442\u0440\u044f\u0434 \u0437\u0430\u043d\u0438\u043c\u0430\u0435\u0442 \u0447\u0435\u0442\u044b\u0440\u0435 \u043a\u043b\u0435\u0442\u043a\u0438. \u0414\u0430\u043d\u043d\u044b\u0435 \u0434\u0435\u043c\u043e\u043d\u0441\u0442\u0440\u0430\u0446\u0438\u043e\u043d\u043d\u044b\u0435; \u0440\u0435\u0430\u043b\u044c\u043d\u0430\u044f \u0430\u0440\u043c\u0438\u044f \u043f\u043e\u043a\u0430 \u043d\u0435 \u043f\u043e\u0434\u043a\u043b\u044e\u0447\u0435\u043d\u0430."
        };
    };
    inline static const Strings text{};
    inline static HWND window = nullptr;
    inline static HWND launcher = nullptr;
    inline static bool closePressed = false;
    inline static HINSTANCE instance = nullptr;
    inline static int selected = 0;
    inline static bool demonstration = true, realBattleAvailable = false;
    inline static uint32_t realNeutralCount = 0, realEntryCount = 0;
    inline static int realPositions[21][5]{};
    inline static uint32_t realQuantities[21][2]{};
    inline static bool realVisible[21][2]{};
    inline static wchar_t realDetails[21][1536]{};
    inline static wchar_t realStatus[192]{};
    inline static DeploymentComparison realComparison{};
    inline static RECT battlefields[2]{};
    inline static RECT closeButton{};
    inline static int cellSize = 24;
    inline static uint32_t currentBattleId = 0;
    inline static int lastOwnerWidth = 0;
    inline static constexpr const wchar_t* layoutProperties[5] = {
        L"H5DeploymentComparison.Left.v1", L"H5DeploymentComparison.Top.v1",
        L"H5DeploymentComparison.Width.v1", L"H5DeploymentComparison.Height.v1",
        L"H5DeploymentComparison.Selection.v1"
    };
    static int SavedLayoutValue(HWND owner, int index, int fallback) {
        const auto value = reinterpret_cast<uintptr_t>(GetPropW(owner, layoutProperties[index]));
        return value && value <= 32768 ? static_cast<int>(value - 1) : fallback;
    }
    static void SaveLayout(HWND handle) {
        const auto owner = GetParent(handle);
        RECT bounds{};
        if (!owner || !GetWindowRect(handle, &bounds)) { return; }
        MapWindowPoints(nullptr, owner, reinterpret_cast<POINT*>(&bounds), 2);
        const int values[]{(std::max)(0L, bounds.left), (std::max)(0L, bounds.top),
            bounds.right - bounds.left, bounds.bottom - bounds.top, selected};
        for (int index = 0; index < 5; ++index) {
            if (values[index] >= 0 && values[index] < 32768) {
                SetPropW(owner, layoutProperties[index], reinterpret_cast<HANDLE>(static_cast<uintptr_t>(values[index] + 1)));
            }
        }
    }
    static constexpr COLORREF Background = RGB(23, 35, 27);
    static constexpr COLORREF Gold = RGB(199, 166, 102);
    static constexpr COLORREF Forecast = RGB(94, 178, 255);
    static constexpr COLORREF Actual = RGB(255, 170, 80);
    static constexpr int DefaultColumns = 12, DefaultRows = 10;
    inline static int Columns = DefaultColumns, Rows = DefaultRows;
    // PanUI reference, native rows y=10..1. These are row priorities, not
    // sequential square IDs and not the complete placement algorithm.
    inline static constexpr int rowLabels[DefaultRows] = {4, 9, 1, 6, 3, 8, 2, 7, 5, 10};
    // x/y are local schematic coordinates, not native actor identities.
    inline static constexpr int positions[6][5] = {
        {9, 2, 11, 3, 1}, {10, 7, 10, 7, 1}, {8, 4, 10, 4, 2},
        {0, 2, 0, 2, 1}, {0, 7, 0, 7, 1}, {0, 4, 0, 4, 2}
    };
    inline static constexpr int quantities[6] = {40, 80, 12, 100, 55, 3};

    static int RowLabel(int row) { return Rows == DefaultRows ? rowLabels[row] : Rows - row; }
    static void Label(HDC canvas, RECT area, const wchar_t* value, COLORREF color,
        UINT flags = DT_LEFT | DT_TOP | DT_WORDBREAK) {
        SetTextColor(canvas, color);
        DrawTextW(canvas, value, -1, &area, flags | DT_NOPREFIX);
    }
    static RECT Token(int index, bool actual) {
        const auto& position = demonstration ? positions[index] : realPositions[index];
        const int offset = actual ? 2 : 0;
        const auto& field = battlefields[actual ? 1 : 0];
        const int x = field.left + position[offset] * cellSize;
        const int y = field.top + position[offset + 1] * cellSize;
        return {x + 2, y + 2, x + position[4] * cellSize - 2, y + position[4] * cellSize - 2};
    }
    static void Panel(HDC canvas, RECT area, COLORREF fill, COLORREF border) {
        auto brush = CreateSolidBrush(fill); FillRect(canvas, &area, brush); DeleteObject(brush);
        brush = CreateSolidBrush(border); FrameRect(canvas, &area, brush); DeleteObject(brush);
    }
    static void Paint(HDC canvas, const RECT& client) {
        Panel(canvas, client, RGB(38, 28, 19), RGB(75, 51, 28));
        RECT inset = client; InflateRect(&inset, -3, -3);
        Panel(canvas, inset, RGB(85, 64, 37), Gold);
        InflateRect(&inset, -4, -4);
        Panel(canvas, inset, Background, RGB(116, 92, 52));
        // Quiet horizontal grain gives the panel depth without a repaint loop,
        // external assets, or dependence on SDK rendering internals.
        auto grain = CreatePen(PS_SOLID, 1, RGB(26, 39, 30));
        auto oldPen = SelectObject(canvas, grain);
        for (int y = 12; y < client.bottom - 12; y += 4) {
            MoveToEx(canvas, 12, y, nullptr); LineTo(canvas, client.right - 12, y);
        }
        SelectObject(canvas, oldPen); DeleteObject(grain);
        Panel(canvas, {12, 12, client.right - 12, 62}, RGB(41, 43, 28), RGB(116, 92, 52));
        closeButton = {client.right - 55, 22, client.right - 25, 49};
        Panel(canvas, closeButton, RGB(91, 44, 30), Gold);
        SetBkMode(canvas, TRANSPARENT);
        auto font = CreateFontW(-16, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE,
            DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS, CLEARTYPE_QUALITY,
            DEFAULT_PITCH, L"Segoe UI");
        const auto previousFont = SelectObject(canvas, font);
        auto titleFont = CreateFontW(-23, 0, 0, 0, FW_BOLD, FALSE, FALSE, FALSE,
            DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS, CLEARTYPE_QUALITY,
            DEFAULT_PITCH, L"Georgia");
        SelectObject(canvas, titleFont);
        Label(canvas, {26, 22, client.right - 68, 55}, text.heading, RGB(234, 216, 173), DT_CENTER | DT_VCENTER | DT_SINGLELINE);
        Label(canvas, closeButton, L"\u00d7", RGB(243, 223, 178), DT_CENTER | DT_VCENTER | DT_SINGLELINE);
        SelectObject(canvas, font); DeleteObject(titleFont);
        Label(canvas, {26, 74, client.right - 26, 99}, demonstration ? text.sample : realStatus, RGB(204, 183, 126));
        Label(canvas, {26, 141, client.right / 3, 174}, text.ownArmy, RGB(138, 213, 145));
        Label(canvas, {client.right / 3, 141, client.right - 26, 174}, text.hint, RGB(195, 205, 177));
        RECT descriptionBounds{0, 0, client.right - 72, 0};
        DrawTextW(canvas, demonstration ? text.details[selected] : realDetails[selected], -1,
            &descriptionBounds, DT_LEFT | DT_WORDBREAK | DT_NOPREFIX | DT_CALCRECT);
        constexpr int fieldGap = 64, outsideSpace = 96;
        cellSize = (std::max)(12L, (std::min)((client.right - fieldGap - outsideSpace) / (2 * Columns),
            (client.bottom - 285 - descriptionBounds.bottom) / Rows));
        const int fieldWidth = cellSize * Columns;
        const int firstLeft = (client.right - (2 * fieldWidth + fieldGap + 48)) / 2;
        for (int phase = 0; phase < 2; ++phase) {
            auto& field = battlefields[phase];
            field = {firstLeft + phase * (fieldWidth + fieldGap), 183, 0, 0};
            field.right = field.left + fieldWidth;
            field.bottom = field.top + cellSize * Rows;
            Label(canvas, {field.left, 109, field.right, 135}, phase ? text.actual : text.forecast,
                phase ? Actual : Forecast, DT_CENTER | DT_VCENTER | DT_SINGLELINE);
            RECT frame = field; InflateRect(&frame, 5, 5);
            Panel(canvas, frame, RGB(17, 28, 21), RGB(116, 92, 52));
            auto gridPen = CreatePen(PS_SOLID, 1, RGB(59, 83, 66));
            auto previousPen = SelectObject(canvas, gridPen);
            for (int column = 0; column <= Columns; ++column) {
                MoveToEx(canvas, field.left + column * cellSize, field.top, nullptr);
                LineTo(canvas, field.left + column * cellSize, field.bottom);
            }
            for (int row = 0; row <= Rows; ++row) {
                MoveToEx(canvas, field.left, field.top + row * cellSize, nullptr);
                LineTo(canvas, field.right, field.top + row * cellSize);
            }
            SelectObject(canvas, previousPen); DeleteObject(gridPen);
            auto rowFont = CreateFontW(-22, 0, 0, 0, FW_BOLD, FALSE, FALSE, FALSE,
                DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS, CLEARTYPE_QUALITY,
                DEFAULT_PITCH, L"Georgia");
            SelectObject(canvas, rowFont);
            for (int row = 0; row < Rows; ++row) {
                wchar_t number[12]{}; swprintf_s(number, L"%d", RowLabel(row));
                const int top = field.top + row * cellSize;
                Label(canvas, {field.right + 14, top + 2, field.right + 49, top + cellSize + 2},
                    number, RGB(9, 18, 12), DT_CENTER | DT_VCENTER | DT_SINGLELINE);
                Label(canvas, {field.right + 12, top, field.right + 47, top + cellSize},
                    number, RGB(237, 218, 162), DT_CENTER | DT_VCENTER | DT_SINGLELINE);
            }
            SelectObject(canvas, font); DeleteObject(rowFont);
        }
        auto tokenFont = CreateFontW(-(std::max)(10, (std::min)(14, (cellSize - 4) * 2 / 3)), 0, 0, 0,
            FW_SEMIBOLD, FALSE, FALSE, FALSE, DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
            CLEARTYPE_QUALITY, DEFAULT_PITCH, L"Segoe UI");
        SelectObject(canvas, tokenFont);
        const uint32_t neutralCount = demonstration ? 3u : realNeutralCount;
        const uint32_t entryCount = demonstration ? 6u : realEntryCount;
        for (uint32_t index = 0; index < entryCount; ++index) {
            const bool ownArmy = index >= neutralCount;
            for (int phase = 0; phase < 2; ++phase) {
                if (!demonstration && !realVisible[index][phase]) { continue; }
                RECT token = Token(index, phase != 0);
                const COLORREF color = ownArmy ? RGB(138, 213, 145) : phase ? Actual : Forecast;
                const COLORREF fillColor = ownArmy ? RGB(44, 81, 52) : phase ? RGB(65, 46, 24) : RGB(26, 49, 69);
                Panel(canvas, token, fillColor, color);
                wchar_t caption[32]{};
                if (demonstration) { swprintf_s(caption, L"%s%d", text.symbols[index], quantities[index]); }
                else if (realQuantities[index][phase]) { swprintf_s(caption, L"%u", realQuantities[index][phase]); }
                else { wcscpy_s(caption, L"?"); }
                Label(canvas, token, caption, color, DT_CENTER | DT_VCENTER | DT_SINGLELINE);
                if (index == selected) {
                    InflateRect(&token, 2, 2);
                    auto outline = CreateSolidBrush(RGB(245, 244, 240));
                    FrameRect(canvas, &token, outline); DeleteObject(outline);
                }
            }
        }
        SelectObject(canvas, font); DeleteObject(tokenFont);
        Panel(canvas, {22, battlefields[0].bottom + 18, client.right - 22, client.bottom - 48},
            RGB(202, 188, 145), RGB(135, 104, 56));
        Label(canvas, {36, battlefields[0].bottom + 30, client.right - 36, client.bottom - 56},
            demonstration ? text.details[selected] : realDetails[selected], RGB(46, 40, 26));
        Label(canvas, {26, client.bottom - 35, client.right - 26, client.bottom - 12}, text.close, RGB(190, 176, 140));
        SelectObject(canvas, previousFont);
        DeleteObject(font);
    }
    static void PaintWindow(HWND handle, HDC canvas, const RECT& client) {
        if (handle != launcher) {
            const auto previousPaint = reinterpret_cast<uintptr_t>(GetPropW(handle, L"H5Comparison.PaintEpoch.v1"));
            RemovePropW(handle, L"H5Comparison.LayoutReady.v1");
            Paint(canvas, client);
            // Scalar window properties expose the layout actually used by Paint
            // and Token. They hold no pointers into an unloadable payload.
            constexpr const wchar_t* names[] = {
                L"H5Comparison.Columns.v1", L"H5Comparison.Rows.v1", L"H5Comparison.CellSize.v1",
                L"H5Comparison.ForecastLeft.v1", L"H5Comparison.ForecastTop.v1",
                L"H5Comparison.ForecastRight.v1", L"H5Comparison.ForecastBottom.v1",
                L"H5Comparison.ActualLeft.v1", L"H5Comparison.ActualTop.v1",
                L"H5Comparison.ActualRight.v1", L"H5Comparison.ActualBottom.v1",
                L"H5Comparison.Selection.v1", L"H5Comparison.Entries.v1", L"H5Comparison.Battle.v1",
                L"H5Comparison.ClientWidth.v1", L"H5Comparison.ClientHeight.v1"
            };
            int activeColumns = 0, activeRows = 0;
            uint32_t activeBattleId = 0;
            ReadBattleGeometry(activeColumns, activeRows, activeBattleId);
            const int values[] = {activeColumns, activeRows, cellSize,
                battlefields[0].left, battlefields[0].top, battlefields[0].right, battlefields[0].bottom,
                battlefields[1].left, battlefields[1].top, battlefields[1].right, battlefields[1].bottom,
                selected, static_cast<int>(demonstration ? 6u : realEntryCount), static_cast<int>(activeBattleId),
                client.right, client.bottom};
            bool complete = true;
            for (size_t index = 0; index < std::size(names); ++index) {
                complete = SetPropW(handle, names[index],
                    reinterpret_cast<HANDLE>(static_cast<intptr_t>(values[index]) + 1)) && complete;
            }
            complete = SetPropW(handle, L"H5Comparison.PaintEpoch.v1",
                reinterpret_cast<HANDLE>(previousPaint < UINT32_MAX ? previousPaint + 1 : 1)) && complete;
            SetPropW(handle, L"H5Comparison.LayoutReady.v1", reinterpret_cast<HANDLE>(complete ? 1 : 0));
            return;
        }
        Panel(canvas, client, RGB(41, 43, 28), Gold);
        auto font = CreateFontW(-16, 0, 0, 0, FW_BOLD, FALSE, FALSE, FALSE,
            DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS, CLEARTYPE_QUALITY, DEFAULT_PITCH, L"Georgia");
        auto previousFont = SelectObject(canvas, font); SetBkMode(canvas, TRANSPARENT);
        Label(canvas, client, text.button, RGB(234, 216, 173), DT_CENTER | DT_VCENTER | DT_SINGLELINE);
        SelectObject(canvas, previousFont); DeleteObject(font);
    }
    static LRESULT CALLBACK Procedure(HWND handle, UINT message, WPARAM word, LPARAM value) {
        if (message == WM_CLOSE && handle == window) {
            RemovePropW(GetParent(handle), L"H5DeploymentComparison.OpenBattle.v1");
            SetFocus(GetParent(handle)); DestroyWindow(handle); return 0;
        }
        // Standard Win32 client painting. Programmatic layout verification
        // uses the scalar diagnostics above rather than capturing an image.
        if (message == WM_PRINTCLIENT) {
            RECT client{}; GetClientRect(handle, &client);
            PaintWindow(handle, reinterpret_cast<HDC>(word), client); return 0;
        }
        if (handle == launcher && (message == WM_LBUTTONDOWN ||
            (message == WM_KEYDOWN && (word == VK_RETURN || word == VK_SPACE)))) {
            ShowBattle(); return 0;
        }
        if (message == WM_NCCALCSIZE) { return 0; }
        if (message == WM_NCPAINT) { return 0; }
        if (message == WM_NCACTIVATE) { return TRUE; }
        if (message == WM_NCHITTEST) {
            if (handle == launcher) { return HTCLIENT; }
            RECT bounds{}; GetWindowRect(handle, &bounds);
            const POINT local{static_cast<short>(LOWORD(value)) - bounds.left,
                static_cast<short>(HIWORD(value)) - bounds.top};
            const bool left = local.x < 8, right = local.x >= bounds.right - bounds.left - 8;
            const bool top = local.y < 8, bottom = local.y >= bounds.bottom - bounds.top - 8;
            if (top) { return left ? HTTOPLEFT : right ? HTTOPRIGHT : HTTOP; }
            if (bottom) { return left ? HTBOTTOMLEFT : right ? HTBOTTOMRIGHT : HTBOTTOM; }
            if (left || right) { return left ? HTLEFT : HTRIGHT; }
            if (local.y < 62 && !PtInRect(&closeButton, local)) { return HTCAPTION; }
            return HTCLIENT;
        }
        if (message == WM_ERASEBKGND) { return 1; }
        if (message == WM_GETMINMAXINFO) {
            reinterpret_cast<MINMAXINFO*>(value)->ptMinTrackSize = {680, 700};
            return 0;
        }
        if (message == WM_SETCURSOR && LOWORD(value) == HTCLIENT) {
            SetCursor(LoadCursorW(nullptr, MAKEINTRESOURCEW(32512))); return TRUE;
        }
        if (message == WM_MOUSEWHEEL || message == WM_MOUSEHWHEEL) { return 0; }
        if (message == WM_LBUTTONDOWN) {
            SetFocus(handle);
            const POINT point{static_cast<short>(LOWORD(value)), static_cast<short>(HIWORD(value))};
            if (PtInRect(&closeButton, point)) {
                closePressed = true; SetCapture(handle); return 0;
            }
            const uint32_t entryCount = demonstration ? 6u : realEntryCount;
            for (int phase = 1; phase >= 0; --phase) {
                for (uint32_t index = 0; index < entryCount; ++index) {
                    const auto token = Token(index, phase != 0);
                    if ((demonstration || realVisible[index][phase]) && PtInRect(&token, point)) {
                        selected = index; SaveLayout(handle); InvalidateRect(handle, nullptr, FALSE); return 0;
                    }
                }
            }
            return 0;
        }
        if (message == WM_LBUTTONUP && closePressed) {
            const POINT point{static_cast<short>(LOWORD(value)), static_cast<short>(HIWORD(value))};
            closePressed = false;
            if (GetCapture() == handle) { ReleaseCapture(); }
            if (PtInRect(&closeButton, point)) { SendMessageW(handle, WM_CLOSE, 0, 0); }
            return 0;
        }
        if (message == WM_CAPTURECHANGED) { closePressed = false; }
        if (message == WM_KEYDOWN && word == VK_ESCAPE) { return 0; }
        if (message == WM_KEYUP && word == VK_ESCAPE) { SendMessageW(handle, WM_CLOSE, 0, 0); return 0; }
        if (message == WM_SIZE) {
            if (handle == window) { SaveLayout(handle); }
            InvalidateRect(handle, nullptr, FALSE); return 0;
        }
        if (message == WM_MOVE && handle == window) { SaveLayout(handle); }
        if (message == WM_NCDESTROY) {
            if (handle == window) {
                window = nullptr; closePressed = false;
            }
            if (handle == launcher) { launcher = nullptr; }
        }
        if (message == WM_PAINT) {
            PAINTSTRUCT paint{};
            auto destination = BeginPaint(handle, &paint);
            RECT client{}; GetClientRect(handle, &client);
            auto buffer = CreateCompatibleDC(destination);
            auto bitmap = CreateCompatibleBitmap(destination, (std::max)(1L, client.right), (std::max)(1L, client.bottom));
            auto previousBitmap = SelectObject(buffer, bitmap);
            PaintWindow(handle, buffer, client);
            BitBlt(destination, 0, 0, client.right, client.bottom, buffer, 0, 0, SRCCOPY);
            SelectObject(buffer, previousBitmap); DeleteObject(bitmap); DeleteDC(buffer);
            EndPaint(handle, &paint);
            return 0;
        }
        return DefWindowProcW(handle, message, word, value);
    }
    static BOOL CALLBACK FindOwner(HWND candidate, LPARAM parameter) {
        DWORD process = 0;
        const auto thread = GetWindowThreadProcessId(candidate, &process);
        if (process == GetCurrentProcessId() && thread == GetCurrentThreadId() &&
            IsWindowVisible(candidate) && !GetWindow(candidate, GW_OWNER)) {
            *reinterpret_cast<HWND*>(parameter) = candidate;
            return FALSE;
        }
        return TRUE;
    }
    static bool Register() {
        if (instance) { return true; }
        if (!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
            reinterpret_cast<LPCWSTR>(&Procedure), &instance)) { return false; }
        WNDCLASSW definition{};
        definition.lpfnWndProc = Procedure; definition.hInstance = instance;
        definition.hCursor = LoadCursorW(nullptr, MAKEINTRESOURCEW(32512));
        definition.lpszClassName = L"H5DeploymentComparison";
        if (!RegisterClassW(&definition)) { instance = nullptr; return false; }
        return true;
    }
public:
    // UI-owned value query for native diagnostics; it does not create a window
    // or access the game, and rejected SetBattle calls preserve these values.
    static void ReadBattleGeometry(int& columns, int& rows, uint32_t& battleId) {
        columns = Columns; rows = Rows; battleId = currentBattleId;
    }
    static bool SetBattle(const ComparisonStack* forecast, uint32_t forecastCount,
        const ComparisonStack* actual, uint32_t actualCount, const ComparisonStack* own, uint32_t ownCount,
        const PlacementDecisionTrace* decisions = nullptr, const wchar_t (*quantityLabels)[32] = nullptr,
        bool (*resolveName)(uint32_t, wchar_t*, uint32_t) = nullptr,
        uint32_t nativeWidth = 16, uint32_t nativeHeight = 12, uint32_t battleId = 0) {
        if (nativeWidth < 8 || nativeWidth > 32 || nativeHeight < 4 || nativeHeight > 32) { return false; }
        const auto comparison = CompareDeployments(forecast, forecastCount, actual, actualCount);
        if (!comparison.valid || !own || ownCount > 7 || !ownCount) { return false; }
        for (uint32_t index = 0; index < ownCount; ++index) {
            if (!ValidComparisonStack(own[index], true)) { return false; }
        }
        Columns = static_cast<int>(nativeWidth) - 4; Rows = static_cast<int>(nativeHeight) - 2;
        currentBattleId = battleId;
        const auto referenceComparison = decisions ? CompareReferenceDecisions(*decisions, actual, actualCount) : ReferenceDecisionComparison{};
        realComparison = comparison; realNeutralCount = comparison.entryCount;
        realEntryCount = realNeutralCount + ownCount;
        if (forecastCount) { swprintf_s(realStatus, text.statusFormat, forecastCount, actualCount, comparison.positionMatchCount); }
        else { wcscpy_s(realStatus, text.noForecastStatus); }
        for (uint32_t index = 0; index < realEntryCount; ++index) {
            const bool ownArmy = index >= realNeutralCount;
            const auto& entry = comparison.entries[ownArmy ? 0 : index];
            const ComparisonStack* expected = !ownArmy && entry.forecastIndex >= 0 ? forecast + entry.forecastIndex : nullptr;
            const ComparisonStack* observed = ownArmy ? own + index - realNeutralCount :
                entry.actualIndex >= 0 ? actual + entry.actualIndex : nullptr;
            const auto* reference = observed ? observed : expected;
            if (!reference || !ValidComparisonStack(*reference, observed != nullptr)) { return false; }
            int32_t forecastForDetails = entry.forecastIndex;
            if (!ownArmy && observed && forecastForDetails < 0) {
                for (uint32_t candidate = 0; candidate < forecastCount; ++candidate) {
                    if (forecast[candidate].x == observed->x && forecast[candidate].y == observed->y &&
                        forecast[candidate].footprint == observed->footprint) {
                        forecastForDetails = candidate; break;
                    }
                }
            }
            const auto* expectedForDetails = ownArmy ? observed : forecastForDetails >= 0 ? forecast + forecastForDetails : nullptr;
            for (uint32_t phase = 0; phase < 2; ++phase) {
                const auto* stack = ownArmy ? observed : phase ? observed : expected;
                realVisible[index][phase] = stack != nullptr;
                realQuantities[index][phase] = stack ? stack->quantity : 0;
                realPositions[index][phase * 2] = stack ? stack->x - static_cast<int32_t>(stack->footprint) - 1 : 0;
                realPositions[index][phase * 2 + 1] = stack ? Rows - stack->y : 0;
            }
            realPositions[index][4] = reference->footprint;
            wchar_t names[2][96]{};
            for (uint32_t phase = 0; phase < 2; ++phase) {
                const auto* stack = phase ? observed : expectedForDetails;
                if (!stack) { wcscpy_s(names[phase], text.missingStack); }
                else if (!resolveName || !resolveName(stack->type, names[phase], 96)) {
                    wcscpy_s(names[phase], text.unknownCreature);
                }
            }
            const wchar_t* visibleComparison = ownArmy ? text.ownDescription : text.differences[static_cast<uint32_t>(entry.difference)];
            const wchar_t* explanation = visibleComparison;
            wchar_t decisionExplanation[768]{};
            if (!ownArmy && observed) {
                if (referenceComparison.status == ReferenceDecisionStatus::MatchesFact) {
                    const auto& decision = decisions->records[referenceComparison.decisionForActual[entry.actualIndex]];
                    swprintf_s(decisionExplanation, text.decisionFormat, visibleComparison, decision.order,
                        text.decisionRoles[decision.shooter], text.decisionRules[static_cast<uint32_t>(decision.rule)]);
                    const bool complexPlacement = decision.rule != PlacementDecisionRule::Simple &&
                        decision.rule != PlacementDecisionRule::Solo && decision.rule != PlacementDecisionRule::Unknown;
                    if (complexPlacement) {
                        wcscat_s(decisionExplanation, L"\n");
                        wcscat_s(decisionExplanation, decision.defensive && decision.phase == 2
                            ? text.defensiveRemainder : text.decisionPhases[decision.phase]);
                    }
                    if (complexPlacement && decision.defensive) {
                        wcscat_s(decisionExplanation, L"\n");
                        wcscat_s(decisionExplanation, text.defensiveExplanation);
                    }
                    if (complexPlacement && decision.spread) {
                        wcscat_s(decisionExplanation, L"\n");
                        wcscat_s(decisionExplanation, text.spreadExplanation);
                    }
                    if (decision.y >= static_cast<int32_t>(decision.footprint) && decision.y <= Rows) {
                        wchar_t geometry[160]{};
                        const int row = Rows - decision.y;
                        if (decision.footprint == 2) {
                            swprintf_s(geometry, text.largeRowsFormat, RowLabel(row), RowLabel(row + 1));
                        } else { swprintf_s(geometry, text.smallRowFormat, RowLabel(row)); }
                        wcscat_s(decisionExplanation, L"\n"); wcscat_s(decisionExplanation, geometry);
                    }
                    if (decision.shooter && decision.windowLength > 0 && decision.windowLength <= Rows &&
                        (decision.rule == PlacementDecisionRule::RankedRow || decision.rule == PlacementDecisionRule::Protective)) {
                        wchar_t shelter[128]{}; swprintf_s(shelter, text.shooterWindowFormat, decision.windowLength);
                        wcscat_s(decisionExplanation, L"\n"); wcscat_s(decisionExplanation, shelter);
                    }
                    explanation = decisionExplanation;
                } else {
                    swprintf_s(decisionExplanation, L"%s\n%s", visibleComparison,
                        referenceComparison.status == ReferenceDecisionStatus::DisagreesWithFact
                            ? text.referenceMismatch : text.referenceUnavailable);
                    explanation = decisionExplanation;
                }
            }
            wchar_t counts[2][32]{};
            for (uint32_t phase = 0; phase < 2; ++phase) {
                const auto* stack = phase ? observed : expectedForDetails;
                if (!stack) { wcscpy_s(counts[phase], text.missingStack); }
                else if (!stack->quantity) {
                    if (!phase && quantityLabels && forecastForDetails >= 0 && quantityLabels[forecastForDetails][0]) {
                        wcsncpy_s(counts[phase], quantityLabels[forecastForDetails], 31);
                    } else { wcscpy_s(counts[phase], text.unknownQuantity); }
                }
                else { swprintf_s(counts[phase], L"%u", stack->quantity); }
            }
            swprintf_s(realDetails[index], text.namedEntryFormat,
                observed ? names[1] : names[0], ownArmy ? index - realNeutralCount + 1 : index + 1,
                explanation, names[0], counts[0], names[1], counts[1],
                !ownArmy && comparison.splitChanged ? text.splitDifference : L"");
            if (!ownArmy && !forecastCount) {
                swprintf_s(realDetails[index], text.factEntryFormat, names[1], index + 1, explanation, names[1], counts[1]);
            }
        }
        realBattleAvailable = true;
        return true;
    }
    static bool ShowBattle() {
        if (!realBattleAvailable) { return false; }
        demonstration = false; selected = 0;
        for (uint32_t index = 0; index < realComparison.entryCount; ++index) {
            const auto difference = realComparison.entries[index].difference;
            if (difference != DeploymentDifference::Exact && difference != DeploymentDifference::PositionOnlyKnown) {
                selected = index; break;
            }
        }
        const auto owner = launcher ? GetParent(launcher) : nullptr;
        if (owner && reinterpret_cast<uintptr_t>(GetPropW(owner, L"H5DeploymentComparison.OpenBattle.v1")) == currentBattleId) {
            const int saved = SavedLayoutValue(owner, 4, selected);
            if (saved >= 0 && static_cast<uint32_t>(saved) < realEntryCount) { selected = saved; }
        }
        const bool shown = Show();
        if (shown && currentBattleId) {
            SetPropW(GetParent(window), L"H5DeploymentComparison.OpenBattle.v1", reinterpret_cast<HANDLE>(static_cast<uintptr_t>(currentBattleId)));
        }
        if (shown) { InvalidateRect(window, nullptr, FALSE); }
        return shown;
    }
    static bool ShowDemo() {
        demonstration = true; selected = 0; Columns = DefaultColumns; Rows = DefaultRows;
        const bool shown = Show();
        if (shown) { InvalidateRect(window, nullptr, FALSE); }
        return shown;
    }
    static bool HasBattle() { return realBattleAvailable; }
    static bool HasDifferences() {
        for (uint32_t index = 0; index < realComparison.entryCount; ++index) {
            const auto difference = realComparison.entries[index].difference;
            if (difference != DeploymentDifference::Exact && difference != DeploymentDifference::PositionOnlyKnown) { return true; }
        }
        return false;
    }
    static bool ShowLauncher(HWND owner) {
        if (!realBattleAvailable || !owner || !Register()) { return false; }
        if (!launcher) {
            RECT area{}; GetClientRect(owner, &area);
            SetWindowLongPtrW(owner, GWL_STYLE, GetWindowLongPtrW(owner, GWL_STYLE) | WS_CLIPCHILDREN);
            launcher = CreateWindowExW(0, L"H5DeploymentComparison", text.button, WS_CHILD | WS_CLIPSIBLINGS,
                (area.right - 230) / 2, 68, 230, 36, owner, nullptr, instance, nullptr);
        }
        if (!launcher) { return false; }
        if (!h5::ui::RegisterInputPanel(launcher)) { DestroyWindow(launcher); return false; }
        ShowWindow(launcher, SW_SHOW); BringWindowToTop(launcher);
        InvalidateRect(launcher, nullptr, FALSE);
        RefreshOwnerLayout(owner);
        if (!window && currentBattleId && reinterpret_cast<uintptr_t>(GetPropW(owner,
            L"H5DeploymentComparison.OpenBattle.v1")) == currentBattleId) { ShowBattle(); }
        return true;
    }
    static void RefreshOwnerLayout(HWND owner) {
        if (!launcher || !owner || GetParent(launcher) != owner) { return; }
        RECT area{}; if (!GetClientRect(owner, &area) || area.right == lastOwnerWidth) { return; }
        lastOwnerWidth = area.right;
        SetWindowPos(launcher, nullptr, (std::max)(0L, (area.right - 230) / 2), 68, 230, 36,
            SWP_NOACTIVATE | SWP_NOZORDER);
    }
    static bool Show() {
        HWND owner = nullptr;
        EnumWindows(FindOwner, reinterpret_cast<LPARAM>(&owner));
        if (!owner) { return false; }
        if (!Register()) { return false; }
        if (!window) {
            RECT area{}; GetClientRect(owner, &area);
            const int width = (std::min)(SavedLayoutValue(owner, 2, 1180), static_cast<int>(area.right) - 24);
            const int height = (std::min)(SavedLayoutValue(owner, 3, 760), static_cast<int>(area.bottom) - 24);
            const int left = (std::max)(0, (std::min)(SavedLayoutValue(owner, 0, (area.right - width) / 2), static_cast<int>(area.right) - width));
            const int top = (std::max)(0, (std::min)(SavedLayoutValue(owner, 1, (area.bottom - height) / 2), static_cast<int>(area.bottom) - height));
            window = CreateWindowExW(0, L"H5DeploymentComparison", text.title,
                WS_CHILD | WS_THICKFRAME | WS_CLIPSIBLINGS | WS_CLIPCHILDREN,
                left, top, width, height,
                owner, nullptr, instance, nullptr);
        }
        if (!window) { return false; }
        if (!h5::ui::RegisterInputPanel(window)) { DestroyWindow(window); return false; }
        SetWindowTextW(window, demonstration ? text.title : text.realTitle);
        ShowWindow(window, SW_SHOW); BringWindowToTop(window); SetFocus(window);
        SaveLayout(window);
        return true;
    }
    static void Close() {
        if (window) { DestroyWindow(window); }
        if (launcher) { DestroyWindow(launcher); }
        realBattleAvailable = false;
        if (instance && UnregisterClassW(L"H5DeploymentComparison", instance)) { instance = nullptr; }
    }
};
}
