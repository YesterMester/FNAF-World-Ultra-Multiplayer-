#pragma once
#include <windows.h>
#include <winhttp.h>
#include <atomic>
#include <condition_variable>
#include <deque>
#include <memory>
#include <mutex>
#include <thread>
#include <vector>
#include <nlohmann/json.hpp>
#include "snapshot.hpp"

namespace fwum {
using Json = nlohmann::json;
inline std::wstring widen(const std::string& s) {
    int n = MultiByteToWideChar(CP_UTF8, 0, s.data(), int(s.size()), nullptr, 0);
    std::wstring out(n, L'\0');
    if (n) MultiByteToWideChar(CP_UTF8, 0, s.data(), int(s.size()), out.data(), n);
    return out;
}
inline std::string narrow(const std::wstring& s) {
    int n = WideCharToMultiByte(CP_UTF8, 0, s.data(), int(s.size()), nullptr, 0, nullptr, nullptr);
    std::string out(n, '\0');
    if (n) WideCharToMultiByte(CP_UTF8, 0, s.data(), int(s.size()), out.data(), n, nullptr, nullptr);
    return out;
}

// Network I/O stays on worker threads; the Fusion event loop only exchanges queues.
class Connection : public std::enable_shared_from_this<Connection> {
    std::atomic<HINTERNET> socket{nullptr};
    std::atomic<bool> stopped{false};
    std::atomic<bool> notified_disconnect{false};
    std::mutex mutex;
    std::condition_variable wake;
    std::deque<std::string> outgoing;
    std::deque<Json> incoming;
    std::vector<uint8_t> world_in, world_out;
    void notice(Json msg) {
        std::lock_guard lock(mutex);
        if (incoming.size() >= 128) {
            auto audio = std::find_if(incoming.begin(), incoming.end(), [](const auto& m) { return m.value("type", "") == "audio"; });
            if (audio != incoming.end()) incoming.erase(audio); else incoming.pop_front();
        }
        incoming.push_back(std::move(msg));
    }
    void disconnected() {
        if (!notified_disconnect.exchange(true)) notice({{"type", "disconnected"}});
    }
    void transmit() {
        while (!stopped) {
            std::string message; std::vector<uint8_t> world;
            {
                std::unique_lock lock(mutex);
                wake.wait(lock, [&] { return stopped || !outgoing.empty() || !world_out.empty(); });
                if (stopped) break;
                if (!outgoing.empty()) { message = std::move(outgoing.front()); outgoing.pop_front(); }
                else world.swap(world_out);
            }
            const auto handle = socket.load();
            DWORD error = !message.empty()
                ? WinHttpWebSocketSend(handle, WINHTTP_WEB_SOCKET_UTF8_MESSAGE_BUFFER_TYPE, message.data(), DWORD(message.size()))
                : WinHttpWebSocketSend(handle, WINHTTP_WEB_SOCKET_BINARY_MESSAGE_BUFFER_TYPE, world.data(), DWORD(world.size()));
            // Some WinHTTP implementations can keep Receive blocked while a
            // failed Send closes the handle. Notify the game before closing,
            // so it can release controls and reconnect on either failure path.
            if (error) { disconnected(); stop(); break; }
        }
    }
    void run(std::wstring endpoint, Json hello) {
        HINTERNET session = nullptr, connect = nullptr, request = nullptr;
        try {
            // WinHTTP parses http(s) URLs; the on-disk setting uses familiar ws(s).
            if (endpoint.rfind(L"wss://", 0) == 0) endpoint.replace(0, 6, L"https://");
            else if (endpoint.rfind(L"ws://", 0) == 0) endpoint.replace(0, 5, L"http://");
            else throw std::runtime_error("The online service address is invalid.");
            URL_COMPONENTS u{}; u.dwStructSize = sizeof u;
            u.dwHostNameLength = u.dwUrlPathLength = u.dwExtraInfoLength = DWORD(-1);
            if (!WinHttpCrackUrl(endpoint.c_str(), 0, 0, &u)) throw std::runtime_error("The online service address is invalid.");
            std::wstring host(u.lpszHostName, u.dwHostNameLength);
            std::wstring path(u.lpszUrlPath, u.dwUrlPathLength);
            if (path.empty() || path == L"/") path = L"/lobbies";
            session = WinHttpOpen(L"FWUM/1.2", WINHTTP_ACCESS_TYPE_AUTOMATIC_PROXY, nullptr, nullptr, 0);
            if (!session) throw std::runtime_error("Couldn't open the online connection.");
            // Older WinHTTP/Wine defaults can still select obsolete TLS versions.
            DWORD protocols = WINHTTP_FLAG_SECURE_PROTOCOL_TLS1_2 | 0x00002000; // TLS 1.3
            if (!WinHttpSetOption(session, WINHTTP_OPTION_SECURE_PROTOCOLS, &protocols, sizeof protocols)) {
                protocols = WINHTTP_FLAG_SECURE_PROTOCOL_TLS1_2;
                WinHttpSetOption(session, WINHTTP_OPTION_SECURE_PROTOCOLS, &protocols, sizeof protocols);
            }
            WinHttpSetTimeouts(session, 5000, 5000, 5000, 5000);
            connect = WinHttpConnect(session, host.c_str(), u.nPort, 0);
            request = WinHttpOpenRequest(connect, L"GET", path.c_str(), nullptr, nullptr, nullptr,
                u.nScheme == INTERNET_SCHEME_HTTPS ? WINHTTP_FLAG_SECURE : 0);
            if (!request || !WinHttpSetOption(request, WINHTTP_OPTION_UPGRADE_TO_WEB_SOCKET, nullptr, 0) ||
                !WinHttpSendRequest(request, nullptr, 0, nullptr, 0, 0, 0) || !WinHttpReceiveResponse(request, nullptr)) {
                throw std::runtime_error("Can't reach the online service. Check your connection and try again.");
            }
            auto ws = WinHttpWebSocketCompleteUpgrade(request, 0);
            if (!ws) throw std::runtime_error("The online service refused the connection.");
            socket = ws;
            if (stopped) { stop(); throw std::runtime_error("Connection cancelled."); }
            auto text = hello.dump();
            if (WinHttpWebSocketSend(ws, WINHTTP_WEB_SOCKET_UTF8_MESSAGE_BUFFER_TYPE, text.data(), DWORD(text.size()))) {
                throw std::runtime_error("Couldn't sign in to the lobby.");
            }
            std::thread([self = shared_from_this()] { self->transmit(); }).detach();
            std::vector<uint8_t> buffer(65536), message;
            while (!stopped) {
                DWORD size = 0; WINHTTP_WEB_SOCKET_BUFFER_TYPE type;
                if (WinHttpWebSocketReceive(ws, buffer.data(), DWORD(buffer.size()), &size, &type) ||
                    type == WINHTTP_WEB_SOCKET_CLOSE_BUFFER_TYPE) break;
                if (message.size() + size > max_packet) throw std::runtime_error("The online service sent too much data.");
                message.insert(message.end(), buffer.begin(), buffer.begin() + size);
                if (type == WINHTTP_WEB_SOCKET_BINARY_MESSAGE_BUFFER_TYPE) {
                    std::lock_guard lock(mutex); world_in.swap(message); message.clear();
                } else if (type == WINHTTP_WEB_SOCKET_UTF8_MESSAGE_BUFFER_TYPE) {
                    if (message.size() > 65536) throw std::runtime_error("Invalid lobby response.");
                    notice(Json::parse(message)); message.clear();
                }
            }
        } catch (const std::exception& e) { notice({{"type", "connection-error"}, {"message", e.what()}}); }
        disconnected(); stop();
        if (request) WinHttpCloseHandle(request);
        if (connect) WinHttpCloseHandle(connect);
        if (session) WinHttpCloseHandle(session);
    }
public:
    static std::shared_ptr<Connection> open(const std::wstring& url, Json hello) {
        auto c = std::make_shared<Connection>();
        std::thread([c, url, hello] { c->run(url, hello); }).detach(); return c;
    }
    void stop() {
        stopped = true; wake.notify_all();
        if (auto handle = socket.exchange(nullptr)) WinHttpCloseHandle(handle);
    }
    void send(const Json& message) {
        std::lock_guard lock(mutex);
        if (outgoing.size() < 128) outgoing.push_back(message.dump());
        wake.notify_one();
    }
    void send_world(std::vector<uint8_t> state) {
        std::lock_guard lock(mutex); world_out = std::move(state); wake.notify_one();
    }
    std::deque<Json> messages() { std::lock_guard lock(mutex); std::deque<Json> result; result.swap(incoming); return result; }
    std::vector<uint8_t> world() { std::lock_guard lock(mutex); std::vector<uint8_t> result; result.swap(world_in); return result; }
};
}
