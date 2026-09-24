#include <windows.h>
#include <tlhelp32.h>
#include <bcrypt.h>

#include <filesystem>
#include <fstream>
#include <array>
#include <cstring>
#include <iostream>
#include <string>
#include <vector>

namespace {

HANDLE startedProcess = nullptr;

struct Arguments {
    DWORD processId{};
    std::filesystem::path libraryPath;
    std::filesystem::path gamePath;
    bool projectionTrace{};
    bool prepareStdin{};
};

void Fail(const std::wstring& message) {
    std::wcerr << message << L" (Win32 error " << GetLastError() << L")\n";
    if (startedProcess != nullptr) {
        TerminateProcess(startedProcess, 1);
        WaitForSingleObject(startedProcess, 5000);
    }
    ExitProcess(1);
}

void VerifyGame(const std::filesystem::path& executable) {
    if (_wcsicmp(executable.filename().c_str(), L"H5_Game.exe") != 0) {
        Fail(L"Expected H5_Game.exe");
    }
    const std::pair<const wchar_t*, const char*> binaries[] = {
        {L"H5_Game.exe", "88c9dc6107b9bced0649924a86360f1c56397ee00de0413f6f2b08f865ed5519"},
        {L"uni.dll", "aa5211151d9e9a8c135e180ff8832908d128ccae08a5145162bcdae4946c18ee"},
        {L"um.dll", "1956c00b371d22a3e1a644394ff3e7159b6ec36d660d5ffa36628fcf63fd0fc6"},
        {L"d3d9.dll", "5eb152357f99d53397b764384d5cf9a0f6aece733ced30a34186ac57fb15be25"},
    };
    BCRYPT_ALG_HANDLE algorithm{};
    if (BCryptOpenAlgorithmProvider(&algorithm, BCRYPT_SHA256_ALGORITHM, nullptr, 0) != 0) {
        Fail(L"Cannot initialize SHA-256");
    }
    for (const auto& [name, expected] : binaries) {
        std::ifstream file(executable.parent_path() / name, std::ios::binary);
        if (!file) {
            Fail(std::wstring(L"Cannot read Universe binary: ") + name);
        }
        BCRYPT_HASH_HANDLE hash{};
        if (BCryptCreateHash(algorithm, &hash, nullptr, 0, nullptr, 0, 0) != 0) {
            Fail(L"Cannot create SHA-256 hash");
        }
        std::array<unsigned char, 65536> buffer{};
        while (file) {
            file.read(reinterpret_cast<char*>(buffer.data()), buffer.size());
            if (file.gcount() != 0 && BCryptHashData(hash, buffer.data(), static_cast<ULONG>(file.gcount()), 0) != 0) {
                Fail(L"Cannot hash Universe binary");
            }
        }
        if (!file.eof()) {
            Fail(std::wstring(L"Failed reading Universe binary: ") + name);
        }
        std::array<unsigned char, 32> digest{};
        if (BCryptFinishHash(hash, digest.data(), digest.size(), 0) != 0) {
            Fail(L"Cannot finish SHA-256 hash");
        }
        BCryptDestroyHash(hash);
        std::string actual;
        for (const auto byte : digest) {
            actual += "0123456789abcdef"[byte >> 4];
            actual += "0123456789abcdef"[byte & 15];
        }
        if (actual != expected) {
            Fail(std::wstring(L"Unsupported Universe binary: ") + name);
        }
    }
    BCryptCloseAlgorithmProvider(algorithm, 0);
}

Arguments ParseArguments(int count, wchar_t* values[]) {
    Arguments arguments;
    for (int index = 1; index < count; ++index) {
        const std::wstring argument = values[index];
        if (argument == L"--pid" && index + 1 < count) {
            arguments.processId = std::wcstoul(values[++index], nullptr, 10);
        } else if (argument == L"--dll" && index + 1 < count) {
            arguments.libraryPath = std::filesystem::absolute(values[++index]);
        } else if (argument == L"--game" && index + 1 < count) {
            arguments.gamePath = std::filesystem::absolute(values[++index]);
        } else if (argument == L"--projection-trace") {
            arguments.projectionTrace = true;
        } else if (argument == L"--prepare-stdin") {
            arguments.prepareStdin = true;
        } else {
            std::wcerr << L"Usage: workshop_preview_loader (--game <H5_Game.exe> | --pid <PID>) [--dll <DLL>] [--projection-trace]\n";
            ExitProcess(2);
        }
    }
    if (arguments.libraryPath.empty()) {
        std::array<wchar_t, 32768> path{};
        const DWORD length = GetModuleFileNameW(nullptr, path.data(), path.size());
        if (length == 0 || length >= path.size()) {
            Fail(L"Cannot resolve launcher directory");
        }
        arguments.libraryPath = std::filesystem::path(path.data()).parent_path() / L"WorkshopDeploymentPreview.dll";
    }
    if ((arguments.processId == 0) == arguments.gamePath.empty()
        || (arguments.projectionTrace && arguments.processId == 0)
        || (arguments.prepareStdin && arguments.gamePath.empty())
        || !std::filesystem::is_regular_file(arguments.libraryPath)) {
        std::wcerr << L"Specify exactly one game executable or PID, and an existing plugin DLL. Trace requires a PID.\n";
        ExitProcess(2);
    }
    return arguments;
}

uintptr_t FindModuleBase(DWORD processId, const wchar_t* moduleName) {
    HANDLE snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, processId);
    if (snapshot == INVALID_HANDLE_VALUE) {
        Fail(L"Cannot enumerate target modules");
    }
    MODULEENTRY32W entry{.dwSize = sizeof(entry)};
    uintptr_t result = 0;
    if (Module32FirstW(snapshot, &entry)) {
        do {
            if (_wcsicmp(entry.szModule, moduleName) == 0) {
                result = reinterpret_cast<uintptr_t>(entry.modBaseAddr);
                break;
            }
        } while (Module32NextW(snapshot, &entry));
    }
    CloseHandle(snapshot);
    if (result == 0) {
        Fail(std::wstring(L"Target does not contain ") + moduleName);
    }
    return result;
}

void InjectLibrary(const Arguments& arguments) {
    const std::wstring absolutePath = arguments.libraryPath.wstring();
    const SIZE_T bytes = (absolutePath.size() + 1) * sizeof(wchar_t);
    HANDLE process = OpenProcess(PROCESS_CREATE_THREAD | PROCESS_QUERY_INFORMATION | PROCESS_VM_OPERATION | PROCESS_VM_WRITE | PROCESS_VM_READ, FALSE, arguments.processId);
    if (process == nullptr) {
        Fail(L"Cannot open target process");
    }
    std::array<wchar_t, 32768> executable{};
    DWORD executableLength = executable.size();
    if (!QueryFullProcessImageNameW(process, 0, executable.data(), &executableLength)) {
        Fail(L"Cannot identify target executable");
    }
    VerifyGame(std::filesystem::path(executable.data()));
    if (arguments.projectionTrace) {
        const HMODULE localPlugin = LoadLibraryExW(absolutePath.c_str(), nullptr, DONT_RESOLVE_DLL_REFERENCES);
        const FARPROC localTrace = localPlugin == nullptr ? nullptr : GetProcAddress(localPlugin, "WorkshopDeploymentPreviewProjectionTrace");
        if (localTrace == nullptr) {
            Fail(L"Cannot resolve the plugin projection-trace export");
        }
        const uintptr_t remotePlugin = FindModuleBase(arguments.processId, arguments.libraryPath.filename().c_str());
        const uintptr_t remoteTrace = remotePlugin + (reinterpret_cast<uintptr_t>(localTrace) - reinterpret_cast<uintptr_t>(localPlugin));
        void* remoteSnapshot = VirtualAllocEx(process, nullptr, 136, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
        if (remoteSnapshot == nullptr) {
            Fail(L"Cannot allocate projection snapshot");
        }
        HANDLE traceThread = CreateRemoteThread(process, nullptr, 0, reinterpret_cast<LPTHREAD_START_ROUTINE>(remoteTrace), remoteSnapshot, 0, nullptr);
        if (traceThread == nullptr) {
            VirtualFreeEx(process, remoteSnapshot, 0, MEM_RELEASE);
            Fail(L"Cannot execute the plugin projection-trace export");
        }
        if (WaitForSingleObject(traceThread, 10000) != WAIT_OBJECT_0) {
            // The remote thread may still use its buffer; retain it until exit.
            Fail(L"Projection snapshot timed out");
        }
        DWORD trace{};
        GetExitCodeThread(traceThread, &trace);
        CloseHandle(traceThread);
        std::array<uint32_t, 34> snapshot{};
        SIZE_T received{};
        const bool captured = trace == 1 && ReadProcessMemory(process, remoteSnapshot, snapshot.data(),
            sizeof(snapshot), &received) && received == sizeof(snapshot);
        VirtualFreeEx(process, remoteSnapshot, 0, MEM_RELEASE);
        FreeLibrary(localPlugin);
        if (!captured || snapshot[0] != 1 || snapshot[1] > 7 || snapshot[2] > 7) {
            Fail(L"Projection snapshot changed during capture or has an unsupported ABI");
        }
        CloseHandle(process);
        std::wcout << L"{\"abi\":1,\"public\":" << snapshot[1] << L",\"models\":" << snapshot[2]
                   << L",\"generation\":" << snapshot[3] << L",\"grid\":[" << snapshot[4] << L"," << snapshot[5] << L"],\"slots\":[";
        for (uint32_t index = 0; index < snapshot[2]; ++index) {
            if (index != 0) {
                std::wcout << L",";
            }
            std::wcout << L"{\"type\":" << snapshot[6 + index * 4]
                       << L",\"cell\":[" << snapshot[7 + index * 4] << L"," << snapshot[8 + index * 4]
                       << L"],\"size\":" << snapshot[9 + index * 4] << L"}";
        }
        std::wcout << L"]}\n";
        return;
    }
    const HMODULE localKernel = GetModuleHandleW(L"kernel32.dll");
    const FARPROC localLoadLibrary = GetProcAddress(localKernel, "LoadLibraryW");
    if (localKernel == nullptr || localLoadLibrary == nullptr) {
        Fail(L"Cannot resolve LoadLibraryW");
    }
    const uintptr_t remoteKernel = FindModuleBase(arguments.processId, L"kernel32.dll");
    const uintptr_t remoteLoadLibrary = remoteKernel + (reinterpret_cast<uintptr_t>(localLoadLibrary) - reinterpret_cast<uintptr_t>(localKernel));
    void* remotePath = VirtualAllocEx(process, nullptr, bytes, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
    if (remotePath == nullptr) {
        Fail(L"Cannot allocate DLL path in target");
    }
    SIZE_T written{};
    if (!WriteProcessMemory(process, remotePath, absolutePath.c_str(), bytes, &written) || written != bytes) {
        VirtualFreeEx(process, remotePath, 0, MEM_RELEASE);
        Fail(L"Cannot write DLL path to target");
    }
    HANDLE thread = CreateRemoteThread(process, nullptr, 0, reinterpret_cast<LPTHREAD_START_ROUTINE>(remoteLoadLibrary), remotePath, 0, nullptr);
    if (thread == nullptr) {
        VirtualFreeEx(process, remotePath, 0, MEM_RELEASE);
        Fail(L"Cannot start target loader thread");
    }
    WaitForSingleObject(thread, INFINITE);
    DWORD moduleHandle{};
    GetExitCodeThread(thread, &moduleHandle);
    CloseHandle(thread);
    VirtualFreeEx(process, remotePath, 0, MEM_RELEASE);
    if (moduleHandle == 0) {
        Fail(L"Target LoadLibraryW rejected the DLL");
    }
    const HMODULE localPlugin = LoadLibraryExW(absolutePath.c_str(), nullptr, DONT_RESOLVE_DLL_REFERENCES);
    const FARPROC localVersion = localPlugin == nullptr ? nullptr : GetProcAddress(localPlugin, "WorkshopDeploymentPreviewVersion");
    const FARPROC localInstall = localPlugin == nullptr ? nullptr : GetProcAddress(localPlugin, "WorkshopDeploymentPreviewInstall");
    if (localVersion == nullptr || localInstall == nullptr) {
        Fail(L"Cannot resolve the plugin exports");
    }
    const uintptr_t remotePlugin = FindModuleBase(arguments.processId, arguments.libraryPath.filename().c_str());
    const uintptr_t remoteVersion = remotePlugin + (reinterpret_cast<uintptr_t>(localVersion) - reinterpret_cast<uintptr_t>(localPlugin));
    HANDLE versionThread = CreateRemoteThread(process, nullptr, 0, reinterpret_cast<LPTHREAD_START_ROUTINE>(remoteVersion), nullptr, 0, nullptr);
    if (versionThread == nullptr) {
        Fail(L"Cannot execute the plugin version export");
    }
    WaitForSingleObject(versionThread, INFINITE);
    DWORD version{};
    GetExitCodeThread(versionThread, &version);
    CloseHandle(versionThread);
    if (version != 1) {
        const DWORD diagnostic = version - 1;
        std::wcerr << L"Plugin diagnostics: public portraits=" << (diagnostic >> 29)
                   << L", model outputs=" << ((diagnostic >> 26) & 0x07)
                   << L", hovered creature=" << ((diagnostic >> 17) & 0x1ff)
                   << L", cursor cell=" << ((diagnostic >> 12) & 0x1f) << L"," << ((diagnostic >> 7) & 0x1f)
                   << L", output alignment=" << (diagnostic & 0x0f) << L"\n";
        Fail(L"Unexpected plugin version");
    }
    const uintptr_t remoteInstall = remotePlugin + (reinterpret_cast<uintptr_t>(localInstall) - reinterpret_cast<uintptr_t>(localPlugin));
    HANDLE installThread = CreateRemoteThread(process, nullptr, 0, reinterpret_cast<LPTHREAD_START_ROUTINE>(remoteInstall), nullptr, 0, nullptr);
    if (installThread == nullptr) {
        Fail(L"Cannot execute the plugin install export");
    }
    WaitForSingleObject(installThread, INFINITE);
    DWORD installed{};
    GetExitCodeThread(installThread, &installed);
    CloseHandle(installThread);
    FreeLibrary(localPlugin);
    if (installed != 1) {
        Fail(L"Plugin refused to install its renderer hook");
    }
    CloseHandle(process);
    std::wcout << L"Loaded, executed, and installed " << arguments.libraryPath.wstring() << L" in PID " << arguments.processId << L".\n";
}

}

int wmain(int count, wchar_t* values[]) {
    auto arguments = ParseArguments(count, values);
    PROCESS_INFORMATION child{};
    if (!arguments.gamePath.empty()) {
        VerifyGame(arguments.gamePath);
        STARTUPINFOW startup{.cb = sizeof(startup)};
        std::wstring command = L"\"" + arguments.gamePath.wstring() + L"\"";
        if (!CreateProcessW(arguments.gamePath.c_str(), command.data(), nullptr, nullptr, FALSE,
                            CREATE_SUSPENDED, nullptr, arguments.gamePath.parent_path().c_str(), &startup, &child)) {
            Fail(L"Cannot start Universe");
        }
        startedProcess = child.hProcess;
        arguments.processId = child.dwProcessId;
        if (arguments.prepareStdin) {
            // Explicit dev handshake: the test may install its map/control
            // instrumentation while this owned child has never been resumed.
            std::wcout << L"PREPARED " << child.dwProcessId << L" " << child.dwThreadId << std::endl;
            std::wstring instruction;
            if (!std::getline(std::wcin, instruction) || instruction != L"resume") {
                Fail(L"Test preparation cancelled before game startup");
            }
        }
        CONTEXT context{};
        context.ContextFlags = CONTEXT_INTEGER;
        if (!GetThreadContext(child.hThread, &context) || context.Eax != 0xd11e1c) {
            Fail(L"Unexpected suspended Universe entry point");
        }
        // The Windows loader resolves this pinned EXE's IAT before invoking
        // EAX as its main-thread entry. Install there, before game code starts.
        // EBX points to RW data; all initial registers/flags are preserved.
        unsigned char startupCode[] = {
            0x9c, 0x60,                         // pushfd; pushad
            0xbb, 0, 0, 0, 0,                 // mov ebx, remoteData
            0x8d, 0x43, 0x30, 0x50,           // LoadLibraryA("kernel32.dll")
            0xff, 0x15, 0xd4, 0xa0, 0xe0, 0,
            0x85, 0xc0, 0x74, 0x5c,
            0x8d, 0x4b, 0x10, 0x51, 0x50,     // GetProcAddress(LoadLibraryW)
            0xff, 0x15, 0x44, 0xa0, 0xe0, 0,
            0x85, 0xc0, 0x74, 0x4d,
            0x8d, 0x8b, 0, 0x01, 0, 0, 0x51, // LoadLibraryW(plugin path)
            0xff, 0xd0, 0x85, 0xc0, 0x74, 0x40,
            0x89, 0xc6,                       // preserve plugin HMODULE
            0x8d, 0x8b, 0x80, 0, 0, 0, 0x51, 0x56,
            0xff, 0x15, 0x44, 0xa0, 0xe0, 0, // GetProcAddress(Version)
            0x85, 0xc0, 0x74, 0x2c,
            0xff, 0xd0, 0x83, 0xf8, 0x01, 0x75, 0x25,
            0x8d, 0x4b, 0x50, 0x51, 0x56,
            0xff, 0x15, 0x44, 0xa0, 0xe0, 0, // GetProcAddress(Install)
            0x85, 0xc0, 0x74, 0x16,
            0xff, 0xd0, 0x83, 0xf8, 0x01, 0x75, 0x0f,
            0xc7, 0x03, 0x02, 0, 0, 0,       // status = installed
            0x61, 0x9d,                       // popad; popfd
            0xb8, 0x1c, 0x1e, 0xd1, 0, 0xff, 0xe0, // original EAX/entry
            0xc7, 0x03, 0xff, 0xff, 0xff, 0xff,     // failure status
            0x6a, 0x01, 0xff, 0x15, 0x60, 0xa1, 0xe0, 0, // ExitProcess(1)
            0xcc
        };
        const auto path = arguments.libraryPath.wstring();
        std::vector<unsigned char> startupData(256 + (path.size() + 1) * sizeof(wchar_t));
        memcpy(startupData.data() + 16, "LoadLibraryW", sizeof("LoadLibraryW"));
        memcpy(startupData.data() + 48, "kernel32.dll", sizeof("kernel32.dll"));
        memcpy(startupData.data() + 80, "WorkshopDeploymentPreviewInstall", sizeof("WorkshopDeploymentPreviewInstall"));
        memcpy(startupData.data() + 128, "WorkshopDeploymentPreviewVersion", sizeof("WorkshopDeploymentPreviewVersion"));
        memcpy(startupData.data() + 256, path.c_str(), (path.size() + 1) * sizeof(wchar_t));
        auto* startupMemory = static_cast<unsigned char*>(VirtualAllocEx(child.hProcess, nullptr,
            4096 + startupData.size(), MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE));
        if (startupMemory == nullptr) {
            Fail(L"Cannot allocate main-thread plugin bootstrap");
        }
        *reinterpret_cast<uint32_t*>(startupCode + 3) = reinterpret_cast<uint32_t>(startupMemory + 4096);
        SIZE_T written{};
        DWORD protection{};
        if (!WriteProcessMemory(child.hProcess, startupMemory, startupCode, sizeof(startupCode), &written)
            || written != sizeof(startupCode)
            || !WriteProcessMemory(child.hProcess, startupMemory + 4096, startupData.data(), startupData.size(), &written)
            || written != startupData.size()
            || !VirtualProtectEx(child.hProcess, startupMemory, 4096, PAGE_EXECUTE_READ, &protection)
            || !FlushInstructionCache(child.hProcess, startupMemory, sizeof(startupCode))) {
            Fail(L"Cannot prepare main-thread plugin bootstrap");
        }
        context.Eax = reinterpret_cast<DWORD>(startupMemory);
        if (!SetThreadContext(child.hThread, &context)) {
            Fail(L"Cannot select main-thread plugin bootstrap");
        }
        if (ResumeThread(child.hThread) == static_cast<DWORD>(-1)) {
            Fail(L"Cannot resume Universe");
        }
        const auto deadline = GetTickCount64() + 30000;
        DWORD status{};
        while (status != 2) {
            SIZE_T received{};
            if (!ReadProcessMemory(child.hProcess, startupMemory + 4096, &status, sizeof(status), &received)
                || received != sizeof(status) || status == 0xffffffff
                || WaitForSingleObject(child.hProcess, 0) != WAIT_TIMEOUT) {
                Fail(L"Universe plugin bootstrap failed before game entry");
            }
            if (GetTickCount64() >= deadline) {
                Fail(L"Universe plugin bootstrap timed out");
            }
            if (status != 2) {
                Sleep(10);
            }
        }
        if (WaitForInputIdle(child.hProcess, 30000) != 0) {
            Fail(L"Universe did not reach UI initialization within 30 seconds");
        }
        std::wcout << L"Installed " << arguments.libraryPath.wstring()
                   << L" on the main thread before game entry in PID " << arguments.processId << L".\n";
    } else {
        InjectLibrary(arguments);
    }
    if (child.hProcess != nullptr) {
        startedProcess = nullptr;
        CloseHandle(child.hThread);
        CloseHandle(child.hProcess);
    }
}
