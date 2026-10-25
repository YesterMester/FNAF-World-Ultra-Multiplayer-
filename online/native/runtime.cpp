#define WIN32
#define COXSDK
#define IN_EXT_VERSION2
#define UNICODE
#define _UNICODE
#define NOMINMAX
#define HWABETA
#include "ccxhdr.h"
#undef __segment
#include <xinput.h>
#include <array>
#include <fstream>
#include <map>
#include <set>
#include "transport.hpp"
#include "input.hpp"
#include "images.hpp"

using fwum::Json;
static_assert(sizeof(void*) == 4, "Build FWUMOnline with a 32-bit x86 compiler.");
namespace {
constexpr int authority = 16, needs_frame = 17, create_pending = 18, text_pending = 19, show_pending = 20;
struct Data { headerObject rHo; int frame; };
struct Pad { uint16_t buttons = 0; int16_t lx = 0, ly = 0; ULONGLONG seen = 0; };
struct BusyScope {
    bool& flag;
    explicit BusyScope(bool& value) : flag(value) { flag = true; }
    ~BusyScope() { flag = false; }
};
struct Context {
    Data* data = nullptr;
    std::shared_ptr<fwum::Connection> connection;
    HWND window = nullptr, badge = nullptr, game = nullptr, status = nullptr, list = nullptr;
    std::wstring ini, endpoint, build, player_name, state_file;
    std::wstring message = L"Choose Host or select a lobby to join.";
    Json rooms = Json::array(), members = Json::array();
    Json seat = Json::object(), host_options = Json::object();
    Json request_pending = Json::object();
    std::vector<std::string> shown_rooms;
    bool connected = false, hosting = false, joined = false, playing = false, exit_session = false;
    bool exit_queued = false;
    bool connection_failed = false;
    bool reconnecting = false, leaving = false, resume_pending = false, force_state = false;
    bool engine_busy = false, network_busy = false;
    bool key_down = false;
    int slot = 0, players = 1, frame = -1;
    std::array<Pad, 4> pads{};
    ULONGLONG input_at = 0, state_at = 0, retry_at = 0, reconnect_until = 0, resume_at = 0;
    ULONGLONG diagnostics_at = 0;
    Pad sent_pad;
    uint32_t sequence = 0;
    uint32_t applied_sequence = uint32_t(-1);
    std::unique_ptr<fwum::Snapshot> snapshot;
    LPHO target = nullptr, created = nullptr;
    const fwum::Entity* entity = nullptr;
    int creating = -1;
    double counter_value = 0;
    bool counter_read = false;
    std::map<uint32_t, uint32_t> mapping;
    std::deque<Json> audio;
    int audio_pending = -1;
    Json audio_out = Json::array();
    struct Music { int callback = -1, sample = -1, volume = -1; bool paused = false; };
    std::array<Music, 65> music{};
    int audio_channel = 0, audio_value = 0, audio_opcode = -1;
    struct Effect { int shader = -1; std::map<int, float> params; };
    std::map<uint32_t, Effect> effects, applied_effects;
    int shader_pending = -1, shader_param = -1;
    float shader_value = 0;
    int render_alpha = 0, render_rgb = 0xffffff;
};
Context& ctx() { static auto* c = new Context(); return *c; }
HINSTANCE instance = nullptr;
WNDPROC badge_proc_original = nullptr;
void menu();
void connect(bool automatic = false);
LRESULT CALLBACK badge_proc(HWND h, UINT m, WPARAM w, LPARAM l) {
    if (m == BM_CLICK) { menu(); return 0; }
    auto result = CallWindowProcW(badge_proc_original, h, m, w, l);
    if (m == WM_LBUTTONUP) menu();
    return result;
}
std::wstring setting(const wchar_t* key, const wchar_t* fallback) {
    wchar_t buf[2048]; GetPrivateProfileStringW(L"online", key, fallback, buf, 2048, ctx().ini.c_str()); return buf;
}
void log(const std::string& message) {
    wchar_t path[2048]{}; GetEnvironmentVariableW(L"FWUM_TEST_LOG", path, 2048);
    if (!*path && !ctx().ini.empty()) GetPrivateProfileStringW(L"online", L"diagnostics", L"", path, 2048, ctx().ini.c_str());
    if (!*path) return;
    std::ofstream f(fwum::narrow(path), std::ios::app); f << message << '\n';
}
bool readable(const void* p, size_t length) {
    MEMORY_BASIC_INFORMATION m{};
    return p && VirtualQuery(p, &m, sizeof m) && m.State == MEM_COMMIT && !(m.Protect & (PAGE_NOACCESS | PAGE_GUARD)) &&
        uintptr_t(p) + length <= uintptr_t(m.BaseAddress) + m.RegionSize;
}
LPRH header() { return ctx().data ? ctx().data->rHo.hoAdRunHeader : nullptr; }
fwum::ImageMap image_map() {
    auto app = header()->rhApp;
    const auto memory_count = app->m_nbEltMemToDisk[IMG_TAB], disk_count = app->m_nbEltOff[IMG_TAB];
    if (!readable(app->m_EltMemToDisk[IMG_TAB], size_t(memory_count) * sizeof(WORD)) ||
        !readable(app->m_EltDiskToMem[IMG_TAB], size_t(disk_count) * sizeof(WORD)))
        throw std::runtime_error("The game image bank is unavailable.");
    return {app->m_EltMemToDisk[IMG_TAB], app->m_EltDiskToMem[IMG_TAB], memory_count, disk_count};
}
std::vector<LPHO> objects() {
    std::vector<LPHO> result; auto rh = header();
    if (!rh || rh->rhMaxObjects < 0 || rh->rhMaxObjects > 30000 ||
        !readable(rh->rhObjectList, size_t(rh->rhMaxObjects) * sizeof(objectsList))) return result;
    for (int i = 0; i < rh->rhMaxObjects; ++i) {
        auto ho = rh->rhObjectList[i].oblOffset;
        if (readable(ho, sizeof(headerObject)) && ho->hoNumber == i && !(ho->hoFlags & HOF_DESTROYED)) result.push_back(ho);
    }
    return result;
}
uint32_t fixed(LPHO ho) { return (uint32_t(ho->hoCreationId) << 16) | uint16_t(ho->hoNumber); }
rCom* common(LPHO ho) { return reinterpret_cast<rCom*>(reinterpret_cast<char*>(ho) + sizeof(headerObject)); }
rSpr* sprite(LPHO ho) {
    if (ho->hoType == 2) return &reinterpret_cast<LPRO>(ho)->ros;
    return &reinterpret_cast<LPRS>(ho)->rss;
}
LPRS system_fields(LPHO ho) {
    // Fusion 2.5+ gives strings/counters alterable values. Its rVal is inserted
    // after the sprite header, before the fields described by the older SDK's
    // rs struct. Active objects already include rVal in their own SDK layout.
    size_t extra = 0;
    if ((ho->hoOEFlags & OEFLAG_VALUES) && ho->hoOffsetValue == offsetof(rs, rsPlayer)) extra = sizeof(rVal);
    return reinterpret_cast<LPRS>(reinterpret_cast<char*>(ho) + extra);
}
bool renderable(LPHO ho) { return ho->hoType == 2 || ho->hoType == 3 || ho->hoType == 7; }
void redraw(LPHO ho) {
    common(ho)->rcChanged = TRUE;
    if (ho->hoModifRoutine) ho->hoModifRoutine(ho);
}
void no_move(LPHO) {}
bool select_target() {
    auto& c = ctx();
    if (!c.target || !c.entity) return false;
    auto oi = c.target->hoOiList;
    oi->oilEventCount = header()->rh2.rh2EventCount;
    oi->oilListSelected = c.target->hoNumber; oi->oilNumOfSelected = 1; c.target->hoNextSelected = -1;
    return true;
}
void generate(unsigned event) { callRunTimeFunction(ctx().data, RFUNCTION_GENERATEEVENT, event, 0); }
double counter_value(LPHO target, const fwum::Entity& e) {
    auto& c = ctx(); const auto previous_target = c.target; const auto previous_entity = c.entity;
    c.target = target; c.entity = &e; c.counter_read = false;
    // The counter's cached display fields can differ from its numeric value.
    // Read through Fusion's own expression, including negative integers.
    generate(26);
    const auto value = c.counter_value; const bool read = c.counter_read;
    c.target = previous_target; c.entity = previous_entity;
    if (!read) throw std::runtime_error("Couldn't read a game counter.");
    return value;
}
void release_session() {
    auto& c = ctx();
    if (c.joined && !c.hosting) c.exit_session = true;
    c.joined = c.hosting = c.playing = false; c.players = 1; c.slot = 0;
    c.pads = {}; c.mapping.clear(); c.snapshot.reset();
    c.audio.clear(); c.audio_out = Json::array();
    c.seat = Json::object(); c.host_options = Json::object();
    c.request_pending = Json::object();
    c.reconnecting = c.leaving = c.resume_pending = false;
    c.retry_at = c.reconnect_until = c.resume_at = 0;
}
Pad physical_pad() {
    Pad pad;
    auto fg = GetForegroundWindow(); auto& c = ctx();
    if ((c.window && IsWindowVisible(c.window)) || (fg != c.game && !IsChild(c.game, fg))) return pad;
    static auto get = [] {
        for (auto dll : {L"xinput1_4.dll", L"xinput1_3.dll", L"xinput9_1_0.dll"}) {
            auto module = LoadLibraryW(dll);
            if (module) if (auto fn = GetProcAddress(module, "XInputGetState")) return reinterpret_cast<DWORD(WINAPI*)(DWORD, XINPUT_STATE*)>(fn);
        }
        return static_cast<DWORD(WINAPI*)(DWORD, XINPUT_STATE*)>(nullptr);
    }();
    XINPUT_STATE state{};
    if (get && get(0, &state) == ERROR_SUCCESS) {
        pad.buttons = state.Gamepad.wButtons;
        pad.lx = fwum::normalize_axis(state.Gamepad.sThumbLX); pad.ly = fwum::normalize_axis(state.Gamepad.sThumbLY);
    }
    auto key = [](int k) { return (GetAsyncKeyState(k) & 0x8000) != 0; };
    if (key('W') || key(VK_UP)) pad.buttons |= XINPUT_GAMEPAD_DPAD_UP;
    if (key('S') || key(VK_DOWN)) pad.buttons |= XINPUT_GAMEPAD_DPAD_DOWN;
    if (key('A') || key(VK_LEFT)) pad.buttons |= XINPUT_GAMEPAD_DPAD_LEFT;
    if (key('D') || key(VK_RIGHT)) pad.buttons |= XINPUT_GAMEPAD_DPAD_RIGHT;
    if (key('Z') || key(VK_RETURN) || key(VK_SPACE)) pad.buttons |= XINPUT_GAMEPAD_A;
    if (key('R')) pad.buttons |= XINPUT_GAMEPAD_B;
    if (key('X') || key(VK_SHIFT)) pad.buttons |= XINPUT_GAMEPAD_X;
    if (key(VK_TAB)) pad.buttons |= XINPUT_GAMEPAD_BACK;
    if (key('E')) pad.buttons |= XINPUT_GAMEPAD_RIGHT_SHOULDER;
    return pad;
}
void refresh_ui();
void network() {
    auto& c = ctx();
    const auto now = GetTickCount64();
    if (c.reconnecting && now >= c.reconnect_until) {
        release_session();
        if (c.connection) c.connection->stop();
        c.connected = false; c.message = L"Couldn't restore the connection. Please join again.";
        if (c.window) ShowWindow(c.window, SW_SHOW);
        refresh_ui();
    }
    if (c.reconnecting && !c.connection && now >= c.retry_at) connect(true);
    if (!c.connection) return;
    const auto pending = c.connection->messages();
    for (const auto& m : pending) {
        const auto type = m.value("type", "");
        if (type == "welcome") {
            c.connected = true; c.connection_failed = false;
            c.message = c.reconnecting ? L"Restoring the co-op session..." : L"Connected. Host a game or choose a lobby.";
            if (c.reconnecting) c.resume_at = now;
            else if (!c.request_pending.empty()) {
                c.connection->send(c.request_pending); c.request_pending = Json::object();
            }
        }
        else if (type == "rooms") c.rooms = m.at("rooms");
        else if (type == "hosted" || type == "joined" || type == "resumed") {
            c.joined = true;
            if (type != "resumed") c.hosting = type == "hosted";
            c.slot = m.at("slot");
            c.seat = {{"room", m.at("room").at("id")}, {"member", m.at("member")}, {"token", m.at("token")}};
            if (c.hosting) c.seat["host"] = c.host_options;
            c.reconnecting = c.leaving = c.resume_pending = false;
            c.retry_at = c.reconnect_until = c.resume_at = 0;
            c.state_at = c.input_at = 0; c.sent_pad = {}; c.force_state = true;
            c.message = c.hosting ? L"Lobby is visible. Press Start co-op when ready." : L"Joined! Waiting for the host to start.";
            if (c.playing) c.message = L"Connection restored. Co-op is running.";
            log(type + " slot=" + std::to_string(c.slot));
        } else if (type == "members") {
            c.members = m.at("members"); c.players = int(c.members.size()); c.slot = m.at("slot"); c.pads = {};
        } else if (type == "started") {
            c.playing = true; c.message = L"Co-op is running. F10 opens this menu.";
            if (c.hosting) { c.host_options["playing"] = true; c.seat["host"] = c.host_options; }
            if (c.window) ShowWindow(c.window, SW_HIDE);
            log("started");
        } else if (type == "input" && c.hosting) {
            const int slot = m.at("slot");
            if (slot > 0 && slot < 4) {
                const Pad next{m.at("buttons").get<uint16_t>(), m.at("lx").get<int16_t>(), m.at("ly").get<int16_t>(), now};
                const auto& old = c.pads[slot];
                if (next.buttons != old.buttons || next.lx != old.lx || next.ly != old.ly) c.force_state = true;
                c.pads[slot] = next;
            }
        } else if (type == "audio") { if (c.audio.size() < 128) c.audio.push_back(m); }
        else if (type == "need-state") c.force_state = true;
        else if (type == "notice") c.message = fwum::widen(m.value("message", ""));
        else if (type == "reset-inputs") c.pads = {};
        else if (type == "error" || type == "connection-error") {
            c.message = fwum::widen(m.value("message", "Couldn't connect."));
            if (type == "connection-error") { c.connection_failed = true; c.request_pending = Json::object(); }
            else if (c.reconnecting) {
                if (m.value("code", "") == "resume_wait") { c.resume_pending = false; c.resume_at = now + 750; }
                else { release_session(); if (c.window) ShowWindow(c.window, SW_SHOW); }
            }
        }
        else if (type == "disconnected") {
            c.connected = false; c.connection.reset(); c.pads = {}; c.audio_out = Json::array();
            if (c.joined && !c.leaving && !c.seat.empty()) {
                if (!c.reconnecting) c.reconnect_until = now + 25000;
                c.reconnecting = true; c.resume_pending = false; c.retry_at = now + 1000;
                c.message = L"Connection lost. Reconnecting automatically..."; log("reconnecting");
            } else {
                release_session();
                if (!c.connection_failed) c.message = L"Disconnected. Press Connect to try again.";
                if (c.window) ShowWindow(c.window, SW_SHOW);
            }
        }
        else if (type == "closed" || type == "left") {
            release_session();
            if (!c.connection_failed) c.message = type == "closed" ? L"The host ended the session." : L"Session ended.";
            if (c.window) ShowWindow(c.window, SW_SHOW);
        }
        refresh_ui();
    }
    if (c.reconnecting && c.connected && !c.resume_pending && now >= c.resume_at) {
        Json request = c.seat; request["type"] = "resume";
        c.connection->send(request); c.resume_pending = true;
    }
    if (!c.playing) return;
    if (c.hosting) {
        c.pads[0] = physical_pad();
        for (int i = 1; i < 4; ++i) if (now - c.pads[i].seen > 1000) c.pads[i] = {};
    } else {
        const auto pad = physical_pad();
        const bool changed = pad.buttons != c.sent_pad.buttons || pad.lx != c.sent_pad.lx || pad.ly != c.sent_pad.ly;
        if (c.connected && !c.reconnecting && now - c.input_at >= 33 && (changed || now - c.input_at >= 500)) {
            c.input_at = now; c.sent_pad = pad;
            c.connection->send({{"type", "input"}, {"buttons", pad.buttons}, {"lx", pad.lx}, {"ly", pad.ly}});
        }
        auto packet = c.connection ? c.connection->world() : std::vector<uint8_t>();
        if (!packet.empty()) {
            try {
                auto snapshot = std::make_unique<fwum::Snapshot>(fwum::decode(packet));
                if (snapshot->frame >= header()->rhApp->m_hdr.gaNbFrames) throw std::runtime_error("Invalid game area.");
                c.snapshot = std::move(snapshot);
            }
            catch (const std::exception& e) { c.message = fwum::widen(e.what()); c.connection->stop(); release_session(); }
        }
    }
}
void safe_network() {
    auto& c = ctx();
    if (c.network_busy) return;
    BusyScope guard(c.network_busy);
    try { network(); }
    catch (const std::exception& e) {
        c.message = L"The lobby sent an invalid response. Please reconnect.";
        log(e.what()); c.connected = false; c.connection_failed = true;
        if (c.connection) c.connection->stop();
        release_session(); refresh_ui();
    }
}
fwum::Snapshot capture() {
    auto& c = ctx(); auto rh = header(); fwum::Snapshot state;
    state.frame = c.frame; state.sequence = ++c.sequence;
    state.camera_x = rh->rhWindowX; state.camera_y = rh->rhWindowY;
    state.width = uint16_t(rh->rh3.rh3WindowSx); state.height = uint16_t(rh->rh3.rh3WindowSy);
    auto frame = rh->rhFrame;
    state.background = frame->m_hdr.leBackground;
    for (size_t i = 1; i < c.music.size(); ++i) {
        const auto& m = c.music[i];
        if (m.callback >= 32768) state.music.push_back({uint8_t(i), uint16_t(m.callback), int16_t(m.volume), m.paused});
    }
    if (frame->m_nLayers >= 0 && frame->m_nLayers <= 128 &&
        readable(frame->m_pLayers, frame->m_nLayers * sizeof(RunFrameLayer))) {
        for (int i = 0; i < frame->m_nLayers; ++i) {
            const auto& l = frame->m_pLayers[i];
            state.layers.push_back({l.x, l.y, l.dwOptions & 0x7ffffu});
        }
    }
    const auto live_objects = objects();
    std::set<uint32_t> live_ids;
    for (auto ho : live_objects) live_ids.insert(fixed(ho));
    for (auto ho : live_objects) {
        if (!renderable(ho) || !readable(ho, ho->hoType == 2 ? sizeof(RunObject) : sizeof(rs))) continue;
        auto rc = common(ho); auto sp = sprite(ho);
        if (sp->rsFlags & RSFLAG_HIDDEN) continue;
        if (ho->hoX + ho->hoImgWidth < state.camera_x - 128 || ho->hoY + ho->hoImgHeight < state.camera_y - 128 ||
            ho->hoX > state.camera_x + state.width + 128 || ho->hoY > state.camera_y + state.height + 128) continue;
        fwum::Entity e;
        e.id = fixed(ho); e.oi = ho->hoOi; e.type = ho->hoType; e.layer = ho->hoLayer;
        e.z = sp->rsZOrder;
        e.sprite_layer = rc->rcSprite ? GetSpriteLayer(rh->rhIdEditWin, rc->rcSprite) : ho->hoLayer;
        if (rc->rcSprite && ho->hoType == 2 && (sp->rsEffect & 0xfff) == 13) {
            e.hotspot_x = rc->rcSprite->sprHotSpotX; e.hotspot_y = rc->rcSprite->sprHotSpotY;
            e.display_width = rc->rcSprite->sprWidth; e.display_height = rc->rcSprite->sprHeight;
        }
        e.x = ho->hoX; e.y = ho->hoY;
        e.image = ho->hoType == 2 ? image_map().to_disk(rc->rcImage) : 0;
        e.animation = rc->rcAnim; e.direction = uint8_t(rc->rcDir & 31);
        e.scale_x = rc->rcScaleX; e.scale_y = rc->rcScaleY; e.angle = rc->rcAngle;
        // The runtime adds private high flags even to ordinary RGBA effects.
        // Only BOP_EFFECTEX (13) stores a shader pointer in the parameter.
        e.effect = sp->rsEffect & 0x10ff; e.effect_param = uint32_t(sp->rsEffectParam);
        if ((sp->rsEffect & 0xfff) == 13) {
            const auto previous_target = c.target; const auto previous_entity = c.entity;
            c.target = ho; c.entity = &e; generate(30);
            e.effect = 13; e.effect_param = (uint32_t(255 - c.render_alpha) << 24) | uint32_t(c.render_rgb);
            c.target = previous_target; c.entity = previous_entity;
        } else if ((sp->rsEffect & 0xfff) > 12) { e.effect = 0; e.effect_param = 0; }
        if (auto effect = c.effects.find(e.id); (sp->rsEffect & 0xfff) == 13 && effect != c.effects.end()) {
            e.shader = int16_t(effect->second.shader);
            for (const auto& p : effect->second.params) e.shader_params.emplace_back(uint16_t(p.first), p.second);
        }
        if (ho->hoType == 3) {
            auto text = system_fields(ho);
            e.colour = text->rsTextColor;
            if (text->rsTextBuffer && readable(text->rsTextBuffer, size_t(std::max(0, std::min(text->rsLBuffer, 8192))))) {
                size_t len = 0;
                while (len < size_t(std::max(0, std::min(text->rsLBuffer / 2, 4096))) && text->rsTextBuffer[len]) ++len;
                e.text.assign(reinterpret_cast<const char16_t*>(text->rsTextBuffer), len);
            }
        } else if (ho->hoType == 7) {
            auto counter = system_fields(ho);
            e.floating = counter->rsValue.m_type == TYPE_DOUBLE;
            e.value = counter_value(ho, e);
            e.minimum = e.floating ? counter->rsMiniDouble : counter->rsMini;
            e.maximum = e.floating ? counter->rsMaxiDouble : counter->rsMaxi;
            e.colour = counter->rsColor1; e.colour2 = counter->rsColor2;
        }
        state.entities.push_back(std::move(e));
    }
    for (auto i = c.effects.begin(); i != c.effects.end();) {
        if (!live_ids.count(i->first)) i = c.effects.erase(i); else ++i;
    }
    return state;
}
void audio_control(int opcode, int channel, int value = 0) {
    auto& c = ctx(); c.audio_opcode = opcode; c.audio_channel = channel; c.audio_value = value;
    generate(27); c.audio_opcode = -1;
}
void apply_music() {
    auto& c = ctx();
    for (int channel = 1; channel <= 64; ++channel) {
        const auto remote = std::find_if(c.snapshot->music.begin(), c.snapshot->music.end(),
            [channel](const auto& m) { return m.channel == channel; });
        auto& local = c.music[channel];
        if (remote == c.snapshot->music.end()) {
            if (local.callback >= 0) audio_control(15, channel);
            continue;
        }
        if (local.callback != remote->callback) {
            c.audio_pending = remote->callback; generate(23); c.audio_pending = -1;
        }
        if (remote->volume >= 0 && local.volume != remote->volume) audio_control(17, channel, remote->volume);
        if (local.paused != remote->paused) audio_control(remote->paused ? 13 : 14, channel);
    }
}
void apply_effect(LPHO target, const fwum::Entity& e) {
    auto& c = ctx(); auto& applied = c.applied_effects[e.id];
    if (e.shader >= 0 && applied.shader != e.shader) {
        c.shader_pending = e.shader; generate(28); applied.shader = e.shader; applied.params.clear();
    }
    for (const auto& p : e.shader_params) {
        const auto old = applied.params.find(p.first);
        if (old == applied.params.end() || old->second != p.second) {
            c.shader_param = p.first; c.shader_value = p.second; generate(29); applied.params[p.first] = p.second;
        }
    }
    if ((e.effect & 0xff) == 13) generate(31);
    else if ((sprite(target)->rsEffect & 0xfff) == 13) {
        c.shader_pending = -1; generate(28); applied.shader = -1; applied.params.clear();
    }
}
void apply() {
    auto& c = ctx();
    if (!c.snapshot || c.snapshot->frame != c.frame) return;
    if (c.applied_sequence == c.snapshot->sequence) return;
    c.applied_sequence = c.snapshot->sequence;
    auto frame = header()->rhFrame;
    if (frame->m_hdr.leBackground != c.snapshot->background) {
        frame->m_hdr.leBackground = c.snapshot->background;
        header()->rh3.rh3Scrolling |= RH3SCROLLING_REDRAWALL;
    }
    if (c.snapshot->layers.size() == size_t(frame->m_nLayers)) {
        for (int i = 0; i < frame->m_nLayers; ++i) {
            auto& l = frame->m_pLayers[i]; const auto& remote = c.snapshot->layers[i];
            l.dx = remote.x - l.x; l.dy = remote.y - l.y;
            if ((l.dwOptions ^ remote.flags) & FLOPT_VISIBLE) l.dwOptions |= (remote.flags & FLOPT_VISIBLE) ? FLOPT_TOSHOW : FLOPT_TOHIDE;
        }
    }
    auto all = objects(); std::set<uint32_t> used, reserved;
    int missing = 0, made = 0, text_mismatch = 0, counter_mismatch = 0;
    std::vector<std::pair<int32_t, LPHO>> order;
    for (const auto& e : c.snapshot->entities) {
        if (e.layer >= frame->m_nLayers || e.sprite_layer >= frame->m_nLayers) continue;
        auto mapped = c.mapping.find(e.id);
        if (mapped != c.mapping.end()) reserved.insert(mapped->second);
    }
    for (const auto& e : c.snapshot->entities) {
        if (e.layer >= frame->m_nLayers || e.sprite_layer >= frame->m_nLayers) { ++missing; continue; }
        LPHO target = nullptr;
        auto found = c.mapping.find(e.id);
        if (found != c.mapping.end()) for (auto ho : all) if (fixed(ho) == found->second && ho->hoOi == e.oi) { target = ho; break; }
        if (!target) for (auto ho : all) if (ho->hoOi == e.oi && ho->hoType == e.type &&
            !used.count(fixed(ho)) && !reserved.count(fixed(ho))) { target = ho; break; }
        if (!target) {
            c.creating = e.oi; c.created = nullptr; generate(create_pending); c.creating = -1;
            target = c.created; if (target) { all.push_back(target); ++made; }
        }
        if (!target || !renderable(target) || target->hoType != e.type) { ++missing; continue; }
        used.insert(fixed(target)); c.mapping[e.id] = fixed(target);
        order.emplace_back(e.z, target);
        c.target = target; c.entity = &e;
        apply_effect(target, e);
        auto rc = common(target); auto sp = sprite(target);
        target->hoX = e.x; target->hoY = e.y; target->hoCalculX = target->hoCalculY = 0;
        target->hoLayer = e.layer;
        if (rc->rcSprite) SetSpriteLayer(header()->rhIdEditWin, rc->rcSprite, e.sprite_layer);
        rc->rcRoutineMove = no_move; rc->rcRoutineAnimation = no_move;
        rc->rcImage = target->hoType == 2 ? image_map().to_memory(e.image) : 0;
        rc->rcAnim = e.animation; rc->rcDir = e.direction;
        rc->rcScaleX = e.scale_x; rc->rcScaleY = e.scale_y; rc->rcAngle = e.angle;
        // Preserve any locally-owned shader resources and only apply ordinary effects.
        if ((e.effect & 0xff) != 13 && (sp->rsEffect & 0xfff) <= 12) {
            const DWORD effect = (sp->rsEffect & ~0x10ffu) | e.effect;
            if (sp->rsEffect != effect || uint32_t(sp->rsEffectParam) != e.effect_param) {
                sp->rsEffect = effect; sp->rsEffectParam = e.effect_param;
                if (rc->rcSprite) ModifSpriteEffect(header()->rhIdEditWin, rc->rcSprite, effect, sp->rsEffectParam);
            }
        } else if ((e.effect & 0xff) == 13 && (sp->rsEffect & 0xfff) == 13 && rc->rcSprite) {
            // Animation is frozen on guests, so commit the locally-created
            // shader to the display sprite explicitly, using its local pointer.
            ModifSpriteEffect(header()->rhIdEditWin, rc->rcSprite, sp->rsEffect, sp->rsEffectParam);
        }
        if (target->hoType == 3) {
            system_fields(target)->rsTextColor = e.colour;
            generate(text_pending);
            const auto text = system_fields(target);
            if (!readable(text->rsTextBuffer, (e.text.size() + 1) * sizeof(wchar_t)) ||
                std::char_traits<char16_t>::compare(reinterpret_cast<const char16_t*>(text->rsTextBuffer), e.text.c_str(), e.text.size() + 1)) ++text_mismatch;
        }
        else if (target->hoType == 7) {
            auto counter = system_fields(target);
            counter->rsMini = long(std::clamp(e.minimum, double(INT32_MIN), double(INT32_MAX)));
            counter->rsMaxi = long(std::clamp(e.maximum, double(INT32_MIN), double(INT32_MAX)));
            counter->rsMiniDouble = e.minimum; counter->rsMaxiDouble = e.maximum;
            counter->rsColor1 = e.colour; counter->rsColor2 = e.colour2;
            generate(24);
            const double value = counter_value(target, e);
            if (std::abs(value - e.value) > std::max(0.00001, std::abs(e.value) * 0.000001)) {
                ++counter_mismatch;
                if (c.snapshot->sequence % 60 == 0) log("counter oi=" + std::to_string(e.oi) +
                    " expected=" + std::to_string(e.value) + " actual=" + std::to_string(value) +
                    " min=" + std::to_string(e.minimum) + " max=" + std::to_string(e.maximum));
            }
        }
        generate(show_pending); redraw(target);
        if (rc->rcSprite && target->hoType == 2 && (e.effect & 0xff) == 13) {
            // Postprocessing shaders expand their original bitmap to a viewport
            // quad. ModifSprite otherwise restores the bitmap's small geometry.
            // All fields here are scalar display geometry, never pixel pointers.
            auto s = rc->rcSprite;
            s->sprHotSpotX = s->sprHotSpotXnew = e.hotspot_x;
            s->sprHotSpotY = s->sprHotSpotYnew = e.hotspot_y;
            s->sprWidth = s->sprWidthNew = e.display_width;
            s->sprHeight = s->sprHeightNew = e.display_height;
            s->sprX1 = s->sprX - e.hotspot_x; s->sprY1 = s->sprY - e.hotspot_y;
            s->sprX2 = s->sprX1 + e.display_width; s->sprY2 = s->sprY1 + e.display_height;
            s->sprX1new = s->sprXnew - e.hotspot_x; s->sprY1new = s->sprYnew - e.hotspot_y;
            s->sprX2new = s->sprX1new + e.display_width; s->sprY2new = s->sprY1new + e.display_height;
            s->sprFlags |= SF_REAF;
        }
    }
    for (auto ho : all) if (renderable(ho) && !used.count(fixed(ho))) {
        ho->hoX = ho->hoY = -900000;
        common(ho)->rcRoutineMove = no_move; common(ho)->rcRoutineAnimation = no_move;
        sprite(ho)->rsFlags |= RSFLAG_HIDDEN;
        if (common(ho)->rcSprite) ShowSprite(header()->rhIdEditWin, common(ho)->rcSprite, 0);
        redraw(ho);
    }
    c.target = nullptr; c.entity = nullptr;
    std::stable_sort(order.begin(), order.end(), [](const auto& a, const auto& b) { return a.first < b.first; });
    for (auto [z, ho] : order) if (common(ho)->rcSprite) MoveSpriteToFront(header()->rhIdEditWin, common(ho)->rcSprite);
    std::set<uint32_t> alive;
    for (const auto& e : c.snapshot->entities) alive.insert(e.id);
    for (auto i = c.mapping.begin(); i != c.mapping.end();) { if (!alive.count(i->first)) i = c.mapping.erase(i); else ++i; }
    for (auto i = c.applied_effects.begin(); i != c.applied_effects.end();) {
        if (!alive.count(i->first)) i = c.applied_effects.erase(i); else ++i;
    }
    static uint32_t logged = 0;
    if (c.snapshot->sequence % 60 == 0 && c.snapshot->sequence != logged) {
        logged = c.snapshot->sequence; log("applied " + std::to_string(c.snapshot->entities.size()) +
            " objects; created=" + std::to_string(made) + "; missing=" + std::to_string(missing) + "; text mismatches=" + std::to_string(text_mismatch) +
            "; counter mismatches=" + std::to_string(counter_mismatch));
    }
    for (auto i = c.audio.begin(); i != c.audio.end();) {
        if (i->at("frame").get<int>() != c.frame) { ++i; continue; }
        auto m = std::move(*i); i = c.audio.erase(i);
        for (const auto& id : m.at("ids")) { c.audio_pending = id; generate(23); }
        c.audio_pending = -1;
    }
    apply_music();
}

std::wstring field(int id) { wchar_t b[2048]; GetDlgItemTextW(ctx().window, id, b, 2048); return b; }
void send(Json message) { if (ctx().connection) ctx().connection->send(message); }
void lobby_request(Json message) {
    auto& c = ctx();
    if (field(101) != c.player_name) {
        c.request_pending = std::move(message); connect();
    } else send(std::move(message));
}
void refresh_ui() {
    auto& c = ctx();
    if (!c.window) return;
    SetWindowTextW(c.status, c.message.c_str());
    const auto selected = SendMessageW(c.list, LB_GETCURSEL, 0, 0);
    const std::string selection = selected >= 0 && size_t(selected) < c.shown_rooms.size() ? c.shown_rooms[size_t(selected)] : "";
    SendMessageW(c.list, LB_RESETCONTENT, 0, 0);
    c.shown_rooms.clear();
    if (c.joined) {
        for (const auto& m : c.members) {
            auto text = L"P" + std::to_wstring(m.at("slot").get<int>() + 1) + L"  " + fwum::widen(m.at("name").get<std::string>());
            SendMessageW(c.list, LB_ADDSTRING, 0, LPARAM(text.c_str()));
        }
    } else for (const auto& r : c.rooms) {
        auto text = fwum::widen(r.at("name").get<std::string>()) + L"   " + std::to_wstring(r.at("players").get<int>()) + L"/4" +
            (r.at("locked").get<bool>() ? L"   [code]" : L"   [open]");
        SendMessageW(c.list, LB_ADDSTRING, 0, LPARAM(text.c_str()));
        c.shown_rooms.push_back(r.at("id").get<std::string>());
    }
    if (!c.joined && !c.shown_rooms.empty()) {
        const auto found = std::find(c.shown_rooms.begin(), c.shown_rooms.end(), selection);
        SendMessageW(c.list, LB_SETCURSEL, found == c.shown_rooms.end() ? 0 : found - c.shown_rooms.begin(), 0);
    }
    EnableWindow(GetDlgItem(c.window, 104), c.connected && !c.joined);
    EnableWindow(GetDlgItem(c.window, 105), c.connected && !c.joined && !c.rooms.empty());
    EnableWindow(GetDlgItem(c.window, 106), c.connected && !c.reconnecting && c.hosting && !c.playing);
    EnableWindow(GetDlgItem(c.window, 107), c.joined);
    EnableWindow(GetDlgItem(c.window, 100), !c.joined);
    if (c.badge) SetWindowTextW(c.badge, c.reconnecting ? L"Reconnecting [F10]" :
        c.joined ? (L"P" + std::to_wstring(c.slot + 1) + L" | Co-op " + std::to_wstring(c.players) + L"/4 [F10]").c_str() : L"Online co-op [F10]");
}
void connect(bool automatic) {
    auto& c = ctx();
    if (c.endpoint.empty()) { c.message = L"The online service hasn't been configured for this build yet."; refresh_ui(); return; }
    if (c.connection) c.connection->stop();
    c.connected = false; c.message = automatic ? L"Reconnecting automatically..." : L"Connecting..."; refresh_ui();
    if (!automatic) {
        c.player_name = field(101);
        WritePrivateProfileStringW(L"online", L"name", c.player_name.c_str(), c.ini.c_str());
    }
    c.connection = fwum::Connection::open(c.endpoint, {{"type", "hello"}, {"protocol", 2},
        {"build", fwum::narrow(c.build)}, {"name", fwum::narrow(c.player_name)}});
}
LRESULT CALLBACK menu_proc(HWND window, UINT message, WPARAM w, LPARAM l) {
    auto& c = ctx();
    if (message == WM_TIMER && w == 1) { if (header() && !c.engine_busy) safe_network(); return 0; }
    if (message == WM_CLOSE) { ShowWindow(window, SW_HIDE); return 0; }
    if (message == WM_COMMAND) {
        const int id = LOWORD(w);
        if (id == 100) connect();
        if (id == 104) {
            auto room_name = field(102);
            if (room_name == L"Freddy's co-op") {
                room_name = field(101) + L"'s co-op"; SetDlgItemTextW(c.window, 102, room_name.c_str());
            }
            c.host_options = {{"name", fwum::narrow(room_name)}, {"pin", fwum::narrow(field(103))}, {"playing", false}};
            Json request = c.host_options; request["type"] = "host"; lobby_request(request);
        }
        if (id == 105 || (id == 110 && HIWORD(w) == LBN_DBLCLK)) {
            auto selected = SendMessageW(c.list, LB_GETCURSEL, 0, 0);
            if (!c.joined && selected >= 0 && size_t(selected) < c.rooms.size()) lobby_request({{"type", "join"},
                {"id", c.rooms[size_t(selected)].at("id")}, {"pin", fwum::narrow(field(103))}});
        }
        if (id == 106) send({{"type", "start"}});
        if (id == 107) {
            c.leaving = true;
            if (c.connected && !c.reconnecting) send({{"type", "leave"}});
            else { release_session(); if (c.connection) c.connection->stop(); refresh_ui(); }
        }
        if (id == 108) { ShowWindow(window, SW_HIDE); SetForegroundWindow(c.game); }
        if (id == 109) send({{"type", "browse"}});
        return 0;
    }
    return DefWindowProcW(window, message, w, l);
}
void menu() {
    auto& c = ctx();
    if (c.window && !IsWindow(c.window)) c.window = c.list = c.status = nullptr;
    if (!c.window) {
        WNDCLASSW wc{}; wc.lpfnWndProc = menu_proc; wc.hInstance = instance; wc.hbrBackground = HBRUSH(COLOR_BTNFACE + 1);
        wc.lpszClassName = L"FWUMOnlineMenu"; wc.hCursor = LoadCursor(nullptr, IDC_ARROW); RegisterClassW(&wc);
        RECT r{}; GetWindowRect(c.game, &r);
        c.window = CreateWindowExW(WS_EX_CONTROLPARENT, wc.lpszClassName, L"FNaF World Ultra - Online co-op",
            WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU, r.left + 20, r.top + 30, 590, 510, c.game, nullptr, instance, nullptr);
        auto control = [&](const wchar_t* type, const wchar_t* text, int id, int x, int y, int width, int height, DWORD style = 0) {
            auto h = CreateWindowExW(0, type, text, WS_CHILD | WS_VISIBLE | style, x, y, width, height,
                c.window, HMENU(INT_PTR(id)), instance, nullptr);
            SendMessageW(h, WM_SETFONT, WPARAM(GetStockObject(DEFAULT_GUI_FONT)), TRUE); return h;
        };
        control(L"STATIC", L"Your name", 0, 16, 18, 85, 22);
        control(L"EDIT", setting(L"name", L"Player").c_str(), 101, 105, 16, 275, 25, WS_BORDER | ES_AUTOHSCROLL | WS_TABSTOP);
        control(L"BUTTON", L"Connect", 100, 397, 14, 155, 30, WS_TABSTOP);
        control(L"STATIC", L"Lobby name", 0, 16, 56, 85, 22);
        control(L"EDIT", L"Freddy's co-op", 102, 105, 53, 447, 25, WS_BORDER | ES_AUTOHSCROLL | WS_TABSTOP);
        control(L"STATIC", L"Code (optional)", 0, 16, 93, 110, 22);
        auto pin = control(L"EDIT", L"", 103, 132, 89, 90, 25, WS_BORDER | ES_NUMBER | ES_PASSWORD | WS_TABSTOP);
        SendMessageW(pin, EM_SETLIMITTEXT, 4, 0);
        control(L"STATIC", L"Leave empty for an open lobby", 0, 240, 93, 310, 22);
        c.list = control(L"LISTBOX", L"", 110, 16, 130, 536, 188, WS_BORDER | WS_VSCROLL | LBS_NOTIFY | WS_TABSTOP);
        control(L"BUTTON", L"Host game", 104, 16, 330, 125, 32, WS_TABSTOP);
        control(L"BUTTON", L"Join selected", 105, 153, 330, 125, 32, WS_TABSTOP);
        control(L"BUTTON", L"Refresh", 109, 290, 330, 125, 32, WS_TABSTOP);
        control(L"BUTTON", L"Start co-op", 106, 427, 330, 125, 32, WS_TABSTOP);
        c.status = control(L"STATIC", c.message.c_str(), 0, 16, 376, 536, 42);
        control(L"BUTTON", L"Leave session", 107, 16, 428, 162, 30, WS_TABSTOP);
        control(L"BUTTON", L"Back to game", 108, 390, 428, 162, 30, WS_TABSTOP);
        SendDlgItemMessageW(c.window, 101, EM_SETLIMITTEXT, 24, 0);
        SendDlgItemMessageW(c.window, 102, EM_SETLIMITTEXT, 40, 0);
    }
    refresh_ui(); ShowWindow(c.window, SW_SHOW); SetForegroundWindow(c.window);
    // The engine can pause its frame events while an owned menu has focus.
    // Keep the lobby responsive on the UI thread during that pause as well.
    SetTimer(c.window, 1, 50, nullptr);
    if (!c.connection) connect();
}
}

// Fusion calls conditions using a single long mask parameter. Offline calls are
// forwarded to XBOXGamepad; online calls read the assigned local/remote slots.
namespace {
using CondFn = BOOL(WINAPI*)(LPHO, long, long);
using ExpFn = long(WINAPI*)(LPHO, long);
using ActFn = short(WINAPI*)(LPHO, long, long);
CondFn offline_conditions[16]{};
ExpFn offline_expressions[2]{};
LPHO offline_object() {
    for (auto ho : objects()) if (ho->hoIdentifier == 0x5842584a) return ho;
    return nullptr;
}
template<int N> BOOL WINAPI condition(LPHO ho, long p1, long p2) {
    auto& c = ctx();
    if constexpr (N == authority) {
        return !(c.joined && !c.hosting) && !c.exit_session;
    }
    if constexpr (N == needs_frame) return c.playing && !c.hosting && c.snapshot && c.snapshot->frame != c.frame;
    if constexpr (N == create_pending || N == text_pending || N == show_pending || (N >= 23 && N <= 31 && N != 25)) return TRUE;
    if constexpr (N == 21) return c.exit_session && !c.exit_queued;
    if constexpr (N == 22) return c.playing;
    if constexpr (N == 25) return select_target();
    if constexpr (N == 32) return !c.playing || (p1 & (1 << c.slot));
    if constexpr (N < 16) {
        if (!c.playing) {
            auto original = offline_object();
            return original && offline_conditions[N] ? offline_conditions[N](original, p1, p2) : FALSE;
        }
        if constexpr (N == 0) return p1 >= 0 && p1 < c.players;
        const WORD bits[] = {0, XINPUT_GAMEPAD_A, XINPUT_GAMEPAD_B, XINPUT_GAMEPAD_X, XINPUT_GAMEPAD_Y,
            XINPUT_GAMEPAD_BACK, XINPUT_GAMEPAD_LEFT_THUMB, XINPUT_GAMEPAD_LEFT_SHOULDER, XINPUT_GAMEPAD_RIGHT_THUMB,
            XINPUT_GAMEPAD_RIGHT_SHOULDER, 0, XINPUT_GAMEPAD_START, XINPUT_GAMEPAD_DPAD_UP,
            XINPUT_GAMEPAD_DPAD_DOWN, XINPUT_GAMEPAD_DPAD_LEFT, XINPUT_GAMEPAD_DPAD_RIGHT};
        for (int i = 0; i < c.players; ++i) if ((p1 & (1 << i)) && (c.pads[i].buttons & bits[N])) return TRUE;
    }
    return FALSE;
}
template<int N> long WINAPI expression(LPHO ho, long param) {
    auto& c = ctx();
    ho->hoFlags &= ~(HOF_STRING | HOF_FLOAT);
    if constexpr (N < 2) {
        if (!c.playing) {
            auto original = offline_object();
            return original && offline_expressions[N] ? offline_expressions[N](original, param) : 0;
        }
        const int mask = CNC_GetFirstExpressionParameter(reinterpret_cast<Data*>(ho), param, TYPE_LONG);
        for (int i = 0; i < c.players; ++i) if (mask & (1 << i)) {
            const int v = N == 0 ? c.pads[i].lx : -int(c.pads[i].ly);
            if (std::abs(v) > 7000) return v * 100 / 32768;
        }
        return 0;
    }
    if constexpr (N == 2) return c.snapshot ? c.snapshot->frame + 1 : c.frame + 1;
    if constexpr (N == 3) return c.snapshot ? c.snapshot->camera_x + c.snapshot->width / 2 : 0;
    if constexpr (N == 4) return c.snapshot ? c.snapshot->camera_y + c.snapshot->height / 2 : 0;
    if constexpr (N == 5) {
        ho->hoFlags |= HOF_STRING;
        const auto& text = c.entity ? c.entity->text : std::u16string();
        auto result = reinterpret_cast<wchar_t*>(callRunTimeFunction(reinterpret_cast<Data*>(ho),
            RFUNCTION_GETSTRINGSPACE_EX, 0, (text.size() + 1) * sizeof(wchar_t)));
        if (result) { std::memcpy(result, text.data(), text.size() * sizeof(wchar_t)); result[text.size()] = 0; }
        return long(result);
    }
    if constexpr (N == 6) {
        if (!c.entity) return 0;
        if (c.entity->floating) {
            const float value = float(c.entity->value); long bits; std::memcpy(&bits, &value, sizeof bits);
            ho->hoFlags |= HOF_FLOAT; return bits;
        }
        return long(std::clamp(c.entity->value, double(INT32_MIN), double(INT32_MAX)));
    }
    if constexpr (N == 7) return c.creating;
    if constexpr (N == 8) {
        return c.entity ? c.entity->oi : -1;
    }
    if constexpr (N == 9) return c.audio_pending;
    if constexpr (N == 10) return c.audio_channel;
    if constexpr (N == 11) return c.audio_value;
    if constexpr (N == 12) return c.audio_opcode;
    if constexpr (N == 13) return c.shader_pending;
    if constexpr (N == 14) return c.shader_param;
    if constexpr (N == 15) {
        // Ultra's perspective/orientation shader uniforms are integer values.
        // Supplying a float expression makes Fusion upload its IEEE bits to an
        // integer uniform (1 becomes 1065353216), corrupting the perspective.
        return long(c.shader_value);
    }
    if constexpr (N == 16) return c.entity ? 255 - int(c.entity->effect_param >> 24) : 0;
    if constexpr (N == 17) return c.entity ? long(c.entity->effect_param & 0xffffff) : 0xffffff;
    return 0;
}
short WINAPI begin(LPHO ho, long frame, long) {
    auto& c = ctx(); c.data = reinterpret_cast<Data*>(ho);
    if (c.frame != frame) {
        if (frame == 0) c.music.fill(Context::Music{}); // Fusion stops sounds when restarting the application.
        c.mapping.clear(); c.applied_effects.clear(); c.applied_sequence = uint32_t(-1); c.frame = int(frame); c.force_state = true;
        c.audio_out = Json::array();
        c.audio.erase(std::remove_if(c.audio.begin(), c.audio.end(),
            [frame](const auto& m) { return m.at("frame").template get<int>() != frame; }), c.audio.end());
        log("frame " + std::to_string(frame) + " objects=" + std::to_string(objects().size()));
    }
    safe_network();
    return 0;
}
short WINAPI finish(LPHO, long, long) {
    auto& c = ctx();
    BusyScope guard(c.engine_busy);
    if (!c.state_file.empty() && GetTickCount64() - c.diagnostics_at >= 250) {
        c.diagnostics_at = GetTickCount64();
        try {
            const auto packet = fwum::encode(capture());
            const auto temporary = c.state_file + L".tmp";
            std::ofstream out(fwum::narrow(temporary), std::ios::binary | std::ios::trunc);
            out.write(reinterpret_cast<const char*>(packet.data()), packet.size()); out.close();
            if (out) MoveFileExW(temporary.c_str(), c.state_file.c_str(), MOVEFILE_REPLACE_EXISTING);
        } catch (const std::exception& e) { log(e.what()); }
    }
    if (!c.playing) return 0;
    try {
        if (c.hosting && c.connected && !c.reconnecting && c.players > 1 && !c.audio_out.empty()) {
            send({{"type", "audio"}, {"frame", c.frame}, {"ids", c.audio_out}}); c.audio_out = Json::array();
        }
        if (c.hosting && (!c.connected || c.reconnecting || c.players <= 1)) c.audio_out = Json::array();
        const bool active_input = std::any_of(c.pads.begin(), c.pads.end(), [](const Pad& p) { return p.buttons || p.lx || p.ly; });
        const bool battle = c.frame == 4 && header()->rhWindowX < 64 && header()->rhWindowY < 64;
        const ULONGLONG interval = active_input || battle ? 50 : 100;
        if (c.hosting && c.connected && !c.reconnecting && c.players > 1 && (c.force_state || GetTickCount64() - c.state_at >= interval)) {
            c.force_state = false;
            c.state_at = GetTickCount64(); auto state = capture();
            if (state.sequence % 60 == 0) log("captured " + std::to_string(state.entities.size()) + " objects");
            c.connection->send_world(fwum::encode(state));
        } else if (!c.hosting) apply();
    } catch (const std::exception& e) { c.message = fwum::widen(e.what()); refresh_ui(); }
    return 0;
}
short WINAPI created(LPHO, long, long) {
    auto& c = ctx(); auto all = objects();
    for (auto ho : all) if (ho->hoOi == c.creating && ho->hoCreationId == header()->rh2.rh2CreationCount) c.created = ho;
    return 0;
}
short WINAPI clear_exit(LPHO, long, long) { ctx().exit_queued = true; return 0; }
short WINAPI report_audio(LPHO ho, long, long) {
    auto& c = ctx();
    auto d = reinterpret_cast<Data*>(ho);
    const int id = CNC_GetIntParameter(d), opcode = CNC_GetIntParameter(d), channel = CNC_GetIntParameter(d);
    const int sample = CNC_GetIntParameter(d), value = CNC_GetIntParameter(d);
    auto update = [&](Context::Music& m) {
        if (opcode == 12) {
            m.callback = id >= 32768 ? id : -1; m.sample = sample; m.paused = false;
        } else if (opcode == 1 || opcode == 6 || opcode == 11 || opcode == 15) {
            m.callback = m.sample = -1; m.paused = false;
        } else if (opcode == 7 || opcode == 13 || opcode == 24) m.paused = true;
        else if (opcode == 8 || opcode == 14 || opcode == 25) m.paused = false;
        else if (opcode == 17) m.volume = std::clamp(value, 0, 100);
    };
    if (opcode == 1 || opcode == 24 || opcode == 25) {
        for (auto& m : c.music) update(m);
    } else if (opcode == 6 || opcode == 7 || opcode == 8) {
        for (auto& m : c.music) if (m.sample == sample) update(m);
    } else if (channel > 0 && channel <= 64) update(c.music[channel]);
    if (opcode == 12 && id >= 32768) log("music callback=" + std::to_string(id) + " channel=" + std::to_string(channel));
    if (id >= 0 && id < 32768 && c.playing && c.hosting && c.audio_out.size() < 128) c.audio_out.push_back(id);
    return 0;
}
short WINAPI report_counter(LPHO ho, long value, long) {
    auto& c = ctx();
    c.counter_read = true;
    if (c.entity && c.entity->floating) {
        const long bits = CNC_GetFloatValue(reinterpret_cast<Data*>(ho), 0);
        float result; std::memcpy(&result, &bits, sizeof result); c.counter_value = result;
    } else c.counter_value = value;
    return 0;
}
std::vector<LPHO> selected_objects(int oi) {
    auto all = objects();
    auto first = std::find_if(all.begin(), all.end(), [oi](LPHO ho) { return ho->hoOi == oi; });
    if (first == all.end()) return {};
    const auto list = (*first)->hoOiList;
    if (list->oilEventCount != header()->rh2.rh2EventCount) {
        all.erase(std::remove_if(all.begin(), all.end(), [oi](LPHO ho) { return ho->hoOi != oi; }), all.end()); return all;
    }
    std::vector<LPHO> selected;
    for (int number = list->oilListSelected; number >= 0 && number < header()->rhMaxObjects && selected.size() < all.size();) {
        auto ho = header()->rhObjectList[number].oblOffset;
        if (!ho || ho->hoOi != oi) break;
        selected.push_back(ho); number = ho->hoNextSelected;
    }
    return selected;
}
short WINAPI report_shader(LPHO, long oi, long shader) {
    for (auto ho : selected_objects(int(oi))) {
        auto& effect = ctx().effects[fixed(ho)]; effect.shader = int(shader); effect.params.clear();
    }
    return 0;
}
short WINAPI report_shader_param(LPHO ho, long, long) {
    auto d = reinterpret_cast<Data*>(ho);
    const int oi = CNC_GetIntParameter(d), id = CNC_GetIntParameter(d);
    const long bits = CNC_GetFloatParameter(d); float value; std::memcpy(&value, &bits, sizeof value);
    if (std::isfinite(value)) for (auto target : selected_objects(oi)) ctx().effects[fixed(target)].params[id] = value;
    return 0;
}
short WINAPI report_colour(LPHO, long alpha, long rgb) {
    ctx().render_alpha = std::clamp(int(alpha), 0, 255); ctx().render_rgb = int(rgb & 0xffffff); return 0;
}
CondFn conditions[] = {condition<0>, condition<1>, condition<2>, condition<3>, condition<4>, condition<5>, condition<6>,
    condition<7>, condition<8>, condition<9>, condition<10>, condition<11>, condition<12>, condition<13>, condition<14>,
    condition<15>, condition<16>, condition<17>, condition<18>, condition<19>, condition<20>, condition<21>, condition<22>, condition<23>, condition<24>, condition<25>, condition<26>, condition<27>, condition<28>, condition<29>, condition<30>, condition<31>, condition<32>};
ActFn actions[] = {begin, finish, created, clear_exit, report_audio, report_counter, report_shader, report_shader_param, report_colour};
ExpFn expressions[] = {expression<0>, expression<1>, expression<2>, expression<3>, expression<4>, expression<5>, expression<6>, expression<7>, expression<8>, expression<9>, expression<10>, expression<11>, expression<12>, expression<13>, expression<14>, expression<15>, expression<16>, expression<17>};
}
extern "C" {
BOOL WINAPI DllMain(HINSTANCE h, DWORD reason, LPVOID) { if (reason == DLL_PROCESS_ATTACH) instance = h; return TRUE; }
DWORD WINAPI GetInfos(int i) {
    switch (i) { case KGI_VERSION: return EXT_VERSION2; case KGI_PLUGIN: return EXT_PLUGIN_VERSION1;
        case KGI_PRODUCT: return PRODUCT_VERSION_STANDARD; case KGI_BUILD: return 295; case KGI_UNICODE: return TRUE; default: return 0; }
}
short WINAPI Initialize(mv*, int) { return 0; }
short WINAPI Free(mv*) { if (ctx().connection) ctx().connection->stop(); return 0; }
ushort WINAPI GetRunObjectDataSize(fprh, void*) { return sizeof(Data); }
short WINAPI CreateRunObject(Data* d, void*, fpcob) {
    auto& c = ctx(); c.data = d; d->frame = -1;
    c.effects.clear(); c.applied_effects.clear();
    HMODULE pinned = nullptr;
    GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_PIN,
        reinterpret_cast<LPCWSTR>(&CreateRunObject), &pinned);
    if (c.exit_queued) { c.exit_queued = c.exit_session = false; c.frame = -1; }
    // Online hosts keep serving peers when another window is focused.
    d->rHo.hoAdRunHeader->rhApp->m_hdr.gaNewFlags |= GANF_RUNWHENMINIMIZED;
    if (c.ini.empty()) {
        wchar_t path[2048]; GetModuleFileNameW(nullptr, path, 2048);
        c.ini = path; c.ini = c.ini.substr(0, c.ini.find_last_of(L"\\/") + 1) + L"FWUM-online.ini";
        c.endpoint = setting(L"server", L""); c.build = setting(L"build", L"");
        c.state_file = setting(L"state_file", L"");
        auto module_path = c.ini.substr(0, c.ini.find_last_of(L"\\/") + 1) + L"Modules\\XBOXGamepad.mfx";
        auto module = LoadLibraryW(module_path.c_str());
        if (module) {
            using Info = short(WINAPI*)(mv*, fpKpxRunInfos);
            auto get = reinterpret_cast<Info>(GetProcAddress(module, "GetRunObjectInfos"));
            if (get) { kpxRunInfos info{}; get(nullptr, &info);
                for (int i = 0; i < 16 && i < info.numOfConditions; ++i) offline_conditions[i] = reinterpret_cast<CondFn*>(info.conditions)[i];
                for (int i = 0; i < 2 && i < info.numOfExpressions; ++i) offline_expressions[i] = reinterpret_cast<ExpFn*>(info.expressions)[i]; }
        }
    }
    log("native extension created; " + std::to_string(objects().size()) + " runtime objects");
    return 0;
}
short WINAPI DestroyRunObject(Data* d, long) { if (ctx().data == d) ctx().data = nullptr; return 0; }
short WINAPI HandleRunObject(Data* d) {
    auto& c = ctx(); c.data = d; c.game = d->rHo.hoAdRunHeader->rhHMainWin;
    if (c.badge && IsWindow(c.badge) && GetWindow(c.badge, GW_OWNER) != c.game) {
        DestroyWindow(c.badge); c.badge = nullptr;
    }
    if (c.window && IsWindow(c.window)) SetWindowLongPtrW(c.window, GWLP_HWNDPARENT, LONG_PTR(c.game));
    if (!c.badge || !IsWindow(c.badge)) {
        POINT p{8, 8}; ClientToScreen(c.game, &p);
        c.badge = CreateWindowExW(WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE, L"BUTTON", L"Online co-op [F10]", WS_POPUP | WS_VISIBLE | BS_PUSHBUTTON,
            p.x, p.y, 150, 25, c.game, nullptr, instance, nullptr);
        badge_proc_original = reinterpret_cast<WNDPROC>(SetWindowLongPtrW(c.badge, GWLP_WNDPROC, LONG_PTR(badge_proc)));
    }
    if (c.badge) {
        POINT p{8, 8}; ClientToScreen(c.game, &p);
        SetWindowPos(c.badge, nullptr, p.x, p.y, 0, 0, SWP_NOSIZE | SWP_NOACTIVATE | SWP_NOZORDER);
    }
    const bool down = (GetAsyncKeyState(VK_F10) & 0x8000) &&
        (GetForegroundWindow() == c.game || GetForegroundWindow() == c.window);
    if (down && !c.key_down) {
        if (c.window && IsWindowVisible(c.window)) ShowWindow(c.window, SW_HIDE); else menu();
    }
    c.key_down = down;
    static int calls = 0;
    if (++calls == 60) log("handle alive frame=" + std::to_string(c.frame) + " objects=" + std::to_string(objects().size()));
    return 0;
}
short WINAPI DisplayRunObject(Data*) { return 0; }
short WINAPI PauseRunObject(Data*) { return 0; }
short WINAPI ContinueRunObject(Data*) { return 0; }
short WINAPI GetRunObjectInfos(mv*, fpKpxRunInfos info) {
    memset(info, 0, sizeof(*info)); info->conditions = reinterpret_cast<EXTCONDROUTINE*>(conditions);
    info->actions = reinterpret_cast<EXTACTROUTINE*>(actions); info->expressions = reinterpret_cast<EXTEXPROUTINE*>(expressions);
    info->numOfConditions = 33; info->numOfActions = 9; info->numOfExpressions = 18;
    info->editFlags = OEFLAG_NEVERSLEEP | OEFLAG_NEVERKILL; info->identifier = 0x4e4d5746; return TRUE;
}
}
