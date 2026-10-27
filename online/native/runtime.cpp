#define WIN32
#define COXSDK
#define IN_EXT_VERSION2
#define UNICODE
#define _UNICODE
#define NOMINMAX
#define HWABETA
#include "ccxhdr.h"
#include "Surface.h"
#undef __segment
#include <xinput.h>
#include <array>
#include <fstream>
#include <map>
#include <set>
#include "transport.hpp"
#include "input.hpp"
#include "images.hpp"
#include "ownership.hpp"
#include "navigation.hpp"

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
    struct LobbyNavigation {
        WORD previous = 0, direction = 0;
        ULONGLONG repeat_at = 0;
        int focus = 0, digit = 0;
        bool pin = false, connected = false, joined = false, start_down = false;
    } lobby_navigation;
    int slot = 0, players = 1, frame = -1;
    std::array<Pad, 4> pads{};
    std::array<Pad, 4> previous_pads{};
    std::array<fwum::ActionLatch, 5> input_latches{};
    bool input_focused = false;
    unsigned sent_epoch = 0;
    struct UI {
        int attack = -1, icon = -1, swap = -1, done = -1, reset = -1;
        int category = -1, previous = -1, following = -1, cards = -1;
        std::array<int, 4> avatars{};
    } ui;
    int co_op_players = 1, co_op_owner = 0, co_op_keyboard = 0, battle_slot = 0;
    Pad keyboard_pad, previous_keyboard_pad;
    bool in_battle = false, individual_battle = false;
    bool remote_battle = false;
    unsigned battle_teams = 0;
    fwum::BattleOwners battle_owners;
    fwum::BattleHealth battle_health;
    ULONGLONG battle_started_at = 0;
    uint32_t switch_object = 0;
    int switch_checked_loop = -1;
    struct Pose { float scale = 1; int x = 0, y = 0; } pose;
    std::map<int, RECT> image_bounds;
    std::map<std::string, std::map<int, int>> cosmetics;
    struct Party {
        int slot = 0, owner = 0, players = 1, keyboard = 0, preferred = 0;
        int previous_slot = -1, cursor = 0, page = 0, page_count = 1;
        int command = 0, chosen_slot = 0, chosen_character = 0;
        int cursor_x = 0, cursor_y = 0, cursor_character = 0;
        std::array<WORD, 4> previous{};
        std::array<int, 8> characters{};
        std::array<int, 4> selected{};
        bool valid = false;
        WORD repeating = 0;
        ULONGLONG repeat_at = 0;
        std::map<uint32_t, std::pair<POINT, bool>> original;
        Json view = Json::object(), catalog = Json::object();
        std::set<int> personal;
        std::array<unsigned, 8> versions{};
        std::deque<Json> requests;
        unsigned epoch = 0, sequence = 0, received = unsigned(-1), pending = 0;
        ULONGLONG pending_at = 0;
        std::wstring feedback;
        int pending_base = 0, pending_skin = 0;
        std::set<int> restored;
        std::map<uint32_t, unsigned> filters;
    } party;
    struct Controls {
        std::set<int> targets;
        std::array<int, 4> markers{{-1,-1,-1,-1}};
        std::array<uint32_t, 4> focus{}, clicks{};
        std::array<uint32_t, 4> last_preferred{};
        std::array<bool, 4> moved{};
        std::vector<int> preferences;
        std::vector<std::array<int, 3>> bound_buttons;
        std::array<WORD, 4> bound_previous{};
        std::array<WORD, 4> previous{}, repeating{};
        std::array<ULONGLONG, 4> repeat_at{};
        int back = -1, preferred = -1, keyboard_global = -1, players_global = -1;
        bool automatic = true, host_only = false;
        std::array<bool, 4> connected{};
        std::array<bool, 4> open{};
        bool world = false;
        uint32_t pending_click = 0;
        int slider_knob = -1, slider_track = -1, hint = -1, slider_x = 0;
        uint32_t editing = 0;
        bool mouse_overridden = false;
        POINT saved_mouse{};
    } controls;
    ULONGLONG input_at = 0, state_at = 0, retry_at = 0, reconnect_until = 0, resume_at = 0;
    ULONGLONG diagnostics_at = 0;
    Pad sent_pad;
    uint32_t sequence = 0;
    uint32_t applied_sequence = uint32_t(-1);
    std::unique_ptr<fwum::Snapshot> snapshot;
    std::unique_ptr<fwum::Snapshot> previous_snapshot;
    ULONGLONG snapshot_at = 0, snapshot_interval = 50;
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
bool spatial_frame() {
    const int frame = ctx().frame;
    return (frame >= 4 && frame <= 8) || frame == 20 || frame == 24 || frame == 25 || frame == 26;
}
HINSTANCE instance = nullptr;
WNDPROC badge_proc_original = nullptr;
void menu();
void connect(bool automatic = false);
void save_skin(int base, int appearance, int player = 0);
void party_text(LPHO ho, const std::wstring& text, unsigned colour);
Pad controls_pad(Pad pad, int player);
void controls_tick();
void bound_buttons_tick();
bool controls_active();
unsigned controls_consumed_mask();
long clicked_control(int oi);
bool personal_control(int oi) {
    const auto& markers = ctx().controls.markers;
    return std::find(markers.begin(), markers.end(), oi) != markers.end();
}
std::string shared_party();
bool personal_party(int oi) {
    auto& c = ctx(); return c.playing && c.frame == 3 && c.party.personal.count(oi);
}
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
        // This is Fusion's own object table, read on its game thread. Valid
        // entries remain allocated throughout the event tick.
        if (ho && ho->hoNumber == i && !(ho->hoFlags & HOF_DESTROYED)) result.push_back(ho);
    }
    return result;
}
uint32_t fixed(LPHO ho) { return (uint32_t(ho->hoCreationId) << 16) | uint16_t(ho->hoNumber); }
rVal* values(LPHO ho) {
    auto value = reinterpret_cast<rVal*>(reinterpret_cast<char*>(ho) + ho->hoOffsetValue);
    return ho->hoOffsetValue && readable(value, sizeof(rVal)) ? value : nullptr;
}
int integer_value(LPHO ho, int index) {
    auto v = values(ho);
    if (!v || index < 0 || index >= 26 || !readable(v->rvpValues, (index + 1) * sizeof(CValue))) return 0;
    const auto& number = v->rvpValues[index];
    return number.m_type == TYPE_DOUBLE ? int(number.m_double) : int(number.m_long);
}
LPHO mouse_object(const Pad& pad) {
    if (!(pad.buttons & fwum::mouse_target_button)) return nullptr;
    const auto id = fwum::mouse_target(pad.lx, pad.ly);
    auto rh = header();
    const auto number = uint16_t(id);
    if (!rh || number >= rh->rhMaxObjects) return nullptr;
    const auto ho = rh->rhObjectList[number].oblOffset;
    return readable(ho, sizeof(headerObject)) && !(ho->hoFlags & HOF_DESTROYED) && fixed(ho) == id ? ho : nullptr;
}
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
    c.pads = {}; c.mapping.clear(); c.snapshot.reset(); c.previous_snapshot.reset(); c.snapshot_at = 0;
    c.audio.clear(); c.audio_out = Json::array();
    c.seat = Json::object(); c.host_options = Json::object();
    c.request_pending = Json::object();
    c.reconnecting = c.leaving = c.resume_pending = false;
    c.retry_at = c.reconnect_until = c.resume_at = 0;
}
bool game_focused() {
    const auto game = header() ? header()->rhHMainWin : ctx().game;
    const auto foreground = GetForegroundWindow();
    return game && foreground && GetAncestor(game, GA_ROOTOWNER) == GetAncestor(foreground, GA_ROOTOWNER);
}
bool game_input_focused() {
    return game_focused() && !(ctx().window && IsWindowVisible(ctx().window));
}
Pad controller_pad(int controller) {
    static auto get = [] {
        for (auto dll : {L"xinput1_4.dll", L"xinput1_3.dll", L"xinput9_1_0.dll"}) {
            auto module = LoadLibraryW(dll);
            if (module) if (auto fn = GetProcAddress(module, "XInputGetState")) return reinterpret_cast<DWORD(WINAPI*)(DWORD, XINPUT_STATE*)>(fn);
        }
        return static_cast<DWORD(WINAPI*)(DWORD, XINPUT_STATE*)>(nullptr);
    }();
    Pad pad; XINPUT_STATE state{};
    if (controller >= 0 && get && get(DWORD(controller), &state) == ERROR_SUCCESS) {
        pad.seen = GetTickCount64();
        pad.buttons = state.Gamepad.wButtons & ~fwum::mouse_target_button;
        pad.lx = fwum::normalize_axis(state.Gamepad.sThumbLX); pad.ly = fwum::normalize_axis(state.Gamepad.sThumbLY);
    }
    return pad;
}
Pad physical_pad(int controller = 0, bool keyboard = true) {
    Pad pad;
    auto& context = ctx(); const bool focused = game_input_focused();
    if (focused != context.input_focused) for (auto& latch : context.input_latches) latch.arm();
    context.input_focused = focused;
    if (!focused) return pad;
    pad = controller_pad(controller);
    auto key = [keyboard](int k) { return keyboard && (GetAsyncKeyState(k) & 0x8000) != 0; };
    if (key('W') || key(VK_UP)) pad.buttons |= XINPUT_GAMEPAD_DPAD_UP;
    if (key('S') || key(VK_DOWN)) pad.buttons |= XINPUT_GAMEPAD_DPAD_DOWN;
    if (key('A') || key(VK_LEFT)) pad.buttons |= XINPUT_GAMEPAD_DPAD_LEFT;
    if (key('D') || key(VK_RIGHT)) pad.buttons |= XINPUT_GAMEPAD_DPAD_RIGHT;
    if (key('Z') || key(VK_RETURN) || key(VK_SPACE)) pad.buttons |= XINPUT_GAMEPAD_A;
    if (key('R')) pad.buttons |= XINPUT_GAMEPAD_B;
    if (key('X') || key(VK_SHIFT)) pad.buttons |= XINPUT_GAMEPAD_X;
    if (key(VK_TAB)) pad.buttons |= XINPUT_GAMEPAD_BACK;
    if (key('E')) pad.buttons |= XINPUT_GAMEPAD_RIGHT_SHOULDER;
    if (key('Q')) pad.buttons |= XINPUT_GAMEPAD_LEFT_SHOULDER;
    if (ctx().frame == 3 && key('C')) pad.buttons |= XINPUT_GAMEPAD_Y;
    if (keyboard && key(VK_LBUTTON) && (ctx().frame == 3 || ctx().frame == 4 || !ctx().controls.targets.empty())) {
        auto& c = ctx(); const auto point = header()->rh2.rh2Mouse;
        uint32_t selected = 0; int selected_layer = INT_MIN, selected_z = INT_MIN;
        for (auto ho : objects()) {
            if ((ho->hoType != 2 && ho->hoType != 3) || (sprite(ho)->rsFlags & RSFLAG_HIDDEN)) continue;
            const bool interactive = c.frame == 3 ? (ho->hoOi == c.ui.icon || ho->hoOi == c.ui.done || ho->hoOi == c.ui.reset ||
                ho->hoOi == c.ui.previous || ho->hoOi == c.ui.following ||
                ho->hoOi == c.party.view.value("skin", -1) ||
                ho->hoOi == c.party.view.value("back", -1) ||
                (ho->hoOi >= c.ui.cards && ho->hoOi < c.ui.cards + 8)) :
                c.frame == 4 ? (ho->hoOi == c.ui.attack || ho->hoOi == c.ui.swap ||
                    c.controls.targets.count(ho->hoOi)) : c.controls.targets.count(ho->hoOi);
            // The hardware renderer leaves hoRect empty for these UI sprites.
            // Their image size and hotspot still describe the clickable bounds.
            const bool card = c.frame == 3 && ho->hoOi >= c.ui.cards && ho->hoOi < c.ui.cards + 8;
            const int left = ho->hoX - ho->hoImgXSpot - (card ? 38 : 0), top = ho->hoY - ho->hoImgYSpot;
            if (!interactive || point.x < left || point.x >= left + ho->hoImgWidth + (card ? 38 : 0) ||
                point.y < top || point.y >= top + ho->hoImgHeight) continue;
            uint32_t id = fixed(ho);
            if (c.playing && !c.hosting && c.frame != 3) {
                const auto match = std::find_if(c.mapping.begin(), c.mapping.end(),
                    [id](const auto& entry) { return entry.second == id; });
                if (match == c.mapping.end()) continue;
                id = match->first;
            }
            const auto sp = sprite(ho); const auto render = common(ho)->rcSprite;
            const int layer = render ? GetSpriteLayer(header()->rhIdEditWin, render) : ho->hoLayer;
            const int z = render ? render->sprZOrder : sp->rsZOrder;
            if (!selected || layer > selected_layer || (layer == selected_layer && z >= selected_z)) {
                selected = id; selected_layer = layer; selected_z = z;
            }
        }
        if (selected) {
            pad.buttons |= fwum::mouse_target_button;
            pad.lx = fwum::mouse_target_low(selected); pad.ly = fwum::mouse_target_high(selected);
        }
    }
    const bool mouse = pad.buttons & fwum::mouse_target_button;
    pad.buttons = context.input_latches[controller < 0 ? 4 : std::clamp(controller, 0, 3)].filter(pad.buttons);
    if (mouse && !(pad.buttons & fwum::mouse_target_button)) pad.lx = pad.ly = 0;
    return pad;
}
int mouse_attack_choice(int mask) {
    auto& c = ctx();
    if (!c.playing) return -1;
    for (int i = 0; i < c.players; ++i) if (mask & (1 << i)) {
        const auto target = mouse_object(c.pads[i]);
        if (target && target->hoOi == c.ui.attack) return integer_value(target, 20);
    }
    return -1;
}
int visible_battle_slot() {
    auto& c = ctx();
    for (auto ho : objects()) if (ho->hoOi == c.ui.attack && !(sprite(ho)->rsFlags & RSFLAG_HIDDEN) &&
        ho->hoX >= header()->rhWindowX && ho->hoX < header()->rhWindowX + header()->rh3.rh3WindowSx * 3 / 4 &&
        ho->hoY >= header()->rhWindowY && ho->hoY < header()->rhWindowY + header()->rh3.rh3WindowSy) {
        const auto slot = integer_value(ho, 0);
        if (slot >= 1 && slot <= 4) return slot;
    }
    return 0;
}
bool swap_requested(int mask) {
    auto& c = ctx();
    if (!c.playing && c.co_op_keyboard && c.co_op_owner == 0 &&
        (c.keyboard_pad.buttons & XINPUT_GAMEPAD_RIGHT_SHOULDER) && !(c.previous_keyboard_pad.buttons & XINPUT_GAMEPAD_RIGHT_SHOULDER)) return true;
    for (int i = 0; i < (c.playing ? c.players : c.co_op_players); ++i) if (mask & (1 << i)) {
        const auto& p = c.pads[i]; const auto& previous = c.previous_pads[i];
        if ((p.buttons & XINPUT_GAMEPAD_RIGHT_SHOULDER) && !(previous.buttons & XINPUT_GAMEPAD_RIGHT_SHOULDER)) return true;
        const auto target = mouse_object(p);
        if (target && target->hoOi == c.ui.swap && !(previous.buttons & fwum::mouse_target_button)) return true;
    }
    return false;
}
int slot_team(int slot) {
    auto& c = ctx();
    if (c.individual_battle) return (c.battle_teams >> std::clamp(slot - 1, 0, 3)) & 1;
    auto rh = header();
    auto resolve = [&]() -> LPHO {
        const unsigned number = uint16_t(c.switch_object);
        if (!c.switch_object || number >= unsigned(rh->rhMaxObjects)) return nullptr;
        auto ho = rh->rhObjectList[number].oblOffset;
        return ho && !(ho->hoFlags & HOF_DESTROYED) && fixed(ho) == c.switch_object ? ho : nullptr;
    };
    auto ho = resolve();
    if (!ho && c.switch_checked_loop != rh->rhLoopCount) {
        c.switch_checked_loop = rh->rhLoopCount;
        for (auto object : objects()) if (object->hoOi == c.ui.swap) { c.switch_object = fixed(object); ho = object; break; }
    }
    if (ho) { auto v = values(ho); return v && (v->rvValueFlags & 1); }
    return 0;
}
std::vector<std::string> member_ids() {
    std::vector<std::string> result;
    for (size_t i = 0; i < ctx().members.size(); ++i) result.push_back(ctx().members[i].value("id", std::to_string(i)));
    return result;
}
std::string cosmetic_member(int player) {
    auto& c = ctx();
    if (c.playing && player >= 0 && size_t(player) < c.members.size()) return c.members[player].value("id", "");
    return "local-" + std::to_string(player);
}
int appearance(int player, int base) {
    const auto& choices = ctx().cosmetics;
    const auto member = choices.find(cosmetic_member(player));
    if (member == choices.end()) return base;
    const auto selected = member->second.find(base); return selected == member->second.end() ? base : selected->second;
}
std::wstring cosmetic_file() {
    const auto& ini = ctx().ini; return ini.substr(0, ini.find_last_of(L"\\/") + 1) + L"FWUM-skins.ini";
}
void save_skin(int base, int selected, int player) {
    const auto key = std::to_wstring(base), value = std::to_wstring(selected), path = cosmetic_file();
    const auto section = player ? L"local-" + std::to_wstring(player + 1) : std::wstring(L"skins");
    WritePrivateProfileStringW(section.c_str(), key.c_str(), value.c_str(), path.c_str());
}
int saved_skin(int base, int player = 0) {
    const auto key = std::to_wstring(base), path = cosmetic_file();
    const auto section = player ? L"local-" + std::to_wstring(player + 1) : std::wstring(L"skins");
    return GetPrivateProfileIntW(section.c_str(), key.c_str(), base, path.c_str());
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
            const auto previous_members = member_ids(); const auto previous_slot = c.slot;
            c.members = m.at("members"); c.players = int(c.members.size()); c.slot = m.at("slot"); c.pads = {};
            if (previous_slot != c.slot || previous_members != member_ids()) {
                for (auto& latch : c.input_latches) latch.arm();
                c.sent_pad = {}; c.input_at = 0; c.sent_epoch = 0; c.previous_pads = {};
                c.party.previous.fill(0); c.controls.previous.fill(0); c.controls.repeating.fill(0);
                c.controls.bound_previous.fill(0); c.controls.pending_click = 0; c.controls.clicks.fill(0);
            }
        } else if (type == "started") {
            c.playing = true; c.message = L"Co-op is running. F10 opens this menu.";
            if (c.hosting) { c.host_options["playing"] = true; c.seat["host"] = c.host_options; }
            if (c.window) ShowWindow(c.window, SW_HIDE);
            log("started");
        } else if (type == "input" && c.hosting) {
            const int slot = m.at("slot");
            if (slot > 0 && slot < 4 && m.value("frame", -1) == c.frame && m.value("epoch", 0u) == c.party.epoch) {
                const Pad next{m.at("buttons").get<uint16_t>(), m.at("lx").get<int16_t>(), m.at("ly").get<int16_t>(), now};
                const auto& old = c.pads[slot];
                if (next.buttons != old.buttons || next.lx != old.lx || next.ly != old.ly) c.force_state = true;
                c.pads[slot] = next;
            }
        } else if (type == "party-edit" && c.hosting) {
            if (c.frame != 3) c.connection->send({{"type", "party-result"}, {"member", m.at("member")},
                {"seq", m.at("seq")}, {"accepted", false}, {"message", "That party screen has closed."}});
            else if (c.party.requests.size() < 32) c.party.requests.push_back(m);
        } else if (type == "party-result" && !c.hosting) {
            if (m.value("seq", 0u) == c.party.pending) {
                if (m.value("accepted", false) && c.party.pending_base > 0) save_skin(c.party.pending_base, c.party.pending_skin);
                c.party.pending = 0; c.party.feedback = fwum::widen(m.value("message", ""));
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
        const auto pad = c.frame == 3 ? Pad{} : controls_pad(physical_pad(), c.slot);
        const unsigned epoch = c.snapshot && c.snapshot->frame == c.frame ? c.snapshot->epoch : 0;
        const bool changed = pad.buttons != c.sent_pad.buttons || pad.lx != c.sent_pad.lx || pad.ly != c.sent_pad.ly || epoch != c.sent_epoch;
        if (c.connected && !c.reconnecting && now - c.input_at >= 33 && (changed || now - c.input_at >= 500)) {
            c.input_at = now; c.sent_pad = pad; c.sent_epoch = epoch;
            c.connection->send({{"type", "input"}, {"buttons", pad.buttons}, {"lx", pad.lx}, {"ly", pad.ly}, {"frame", c.frame}, {"epoch", epoch}});
            if (pad.buttons & fwum::mouse_target_button) c.controls.pending_click = 0;
        }
        auto packet = c.connection ? c.connection->world() : std::vector<uint8_t>();
        if (!packet.empty()) {
            try {
                auto snapshot = std::make_unique<fwum::Snapshot>(fwum::decode(packet));
                c.remote_battle = !snapshot->party.empty() && Json::parse(snapshot->party).value("phase", "") == "battle";
                if (!c.snapshot || snapshot->epoch != c.snapshot->epoch) for (auto& latch : c.input_latches) latch.arm();
                if (!c.snapshot || snapshot->epoch != c.snapshot->epoch) c.controls.pending_click = 0;
                if (snapshot->frame >= header()->rhApp->m_hdr.gaNbFrames) throw std::runtime_error("Invalid game area.");
                const auto received = GetTickCount64();
                if (c.snapshot_at) c.snapshot_interval = std::clamp<ULONGLONG>(received - c.snapshot_at, 30, 120);
                c.snapshot_at = received;
                c.previous_snapshot = std::move(c.snapshot); c.snapshot = std::move(snapshot);
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
fwum::Snapshot capture(bool include_personal = false) {
    auto& c = ctx(); auto rh = header(); fwum::Snapshot state;
    state.frame = c.frame; state.sequence = ++c.sequence;
    state.epoch = c.party.epoch;
    state.camera_x = rh->rhWindowX; state.camera_y = rh->rhWindowY;
    state.width = uint16_t(rh->rh3.rh3WindowSx); state.height = uint16_t(rh->rh3.rh3WindowSy);
    state.party = shared_party();
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
    int left = state.camera_x, top = state.camera_y;
    int right = left + state.width, bottom = top + state.height;
    if (c.playing && spatial_frame() && !c.in_battle) {
        for (auto ho : live_objects) if (std::find(c.ui.avatars.begin(), c.ui.avatars.end(), ho->hoOi) != c.ui.avatars.end() &&
                !(sprite(ho)->rsFlags & RSFLAG_HIDDEN)) {
            left = std::min(left, ho->hoX - state.width / 2); right = std::max(right, ho->hoX + state.width / 2);
            top = std::min(top, ho->hoY - state.height / 2); bottom = std::max(bottom, ho->hoY + state.height / 2);
        }
    }
    std::set<uint32_t> live_ids;
    for (auto ho : live_objects) live_ids.insert(fixed(ho));
    for (auto ho : live_objects) {
        if (!renderable(ho) || !readable(ho, ho->hoType == 2 ? sizeof(RunObject) : sizeof(rs))) continue;
        if (!include_personal && (personal_party(ho->hoOi) || personal_control(ho->hoOi))) continue;
        auto rc = common(ho); auto sp = sprite(ho);
        if (sp->rsFlags & RSFLAG_HIDDEN) continue;
        if (ho->hoX + ho->hoImgWidth < left - 128 || ho->hoY + ho->hoImgHeight < top - 128 ||
            ho->hoX > right + 128 || ho->hoY > bottom + 128) continue;
        fwum::Entity e;
        e.id = fixed(ho); e.oi = ho->hoOi; e.type = ho->hoType; e.layer = ho->hoLayer;
        e.z = rc->rcSprite ? rc->rcSprite->sprZOrder : sp->rsZOrder;
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
POINT interpolated_position(const fwum::Entity& entity) {
    auto& c = ctx();
    POINT result{entity.x, entity.y};
    if (!spatial_frame() || !c.previous_snapshot || c.previous_snapshot->frame != c.frame) return result;
    const auto& previous = c.previous_snapshot->entities;
    const auto old = std::find_if(previous.begin(), previous.end(), [&](const auto& item) { return item.id == entity.id && item.oi == entity.oi; });
    if (old == previous.end() || std::abs(entity.x - old->x) > 256 || std::abs(entity.y - old->y) > 256) return result;
    const double progress = std::min(1.0, double(GetTickCount64() - c.snapshot_at) / double(c.snapshot_interval));
    result.x = old->x + long(std::lround((entity.x - old->x) * progress));
    result.y = old->y + long(std::lround((entity.y - old->y) * progress));
    return result;
}
POINT guest_camera_center() {
    auto& c = ctx();
    if (!c.snapshot) return {};
    const auto& s = *c.snapshot;
    POINT result{s.camera_x + s.width / 2, s.camera_y + s.height / 2};
    if (spatial_frame() && c.slot > 0 && c.slot < 4) {
        const auto player = std::find_if(s.entities.begin(), s.entities.end(), [&](const auto& e) { return e.oi == c.ui.avatars[c.slot]; });
        if (player != s.entities.end()) {
            result = interpolated_position(*player);
            result.x = std::clamp(result.x, LONG(s.width / 2), std::max(LONG(s.width / 2), header()->rhFrame->m_hdr.leWidth - s.width / 2));
            result.y = std::clamp(result.y, LONG(s.height / 2), std::max(LONG(s.height / 2), header()->rhFrame->m_hdr.leHeight - s.height / 2));
        }
    }
    return result;
}
void restore_shader_geometry(LPHO target, const fwum::Entity& e) {
    auto rc = common(target);
    if (!rc->rcSprite || target->hoType != 2 || (e.effect & 0xff) != 13) return;
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
void apply_positions() {
    auto& c = ctx(); auto rh = header();
    if (c.hosting || !c.playing || !c.snapshot || c.snapshot->frame != c.frame || !spatial_frame()) return;
    for (const auto& e : c.snapshot->entities) {
        const auto mapping = c.mapping.find(e.id);
        if (mapping == c.mapping.end()) continue;
        const unsigned number = uint16_t(mapping->second);
        if (number >= unsigned(rh->rhMaxObjects)) continue;
        auto ho = rh->rhObjectList[number].oblOffset;
        if (!ho || fixed(ho) != mapping->second || (ho->hoFlags & HOF_DESTROYED)) continue;
        auto position = interpolated_position(e);
        if (ho->hoOEFlags & OEFLAG_SCROLLINGINDEPENDANT) {
            position.x = e.x + rh->rhWindowX - c.snapshot->camera_x;
            position.y = e.y + rh->rhWindowY - c.snapshot->camera_y;
        }
        if (ho->hoX != position.x || ho->hoY != position.y) {
            ho->hoX = position.x; ho->hoY = position.y; redraw(ho);
            restore_shader_geometry(ho, e);
        }
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
        if (personal_party(e.oi)) continue;
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
        if (target->hoOEFlags & OEFLAG_SCROLLINGINDEPENDANT) {
            target->hoX += header()->rhWindowX - c.snapshot->camera_x;
            target->hoY += header()->rhWindowY - c.snapshot->camera_y;
        }
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
            restore_shader_geometry(target, e);
        }
    }
    for (auto ho : all) if (renderable(ho) && !used.count(fixed(ho)) && !personal_party(ho->hoOi) && !personal_control(ho->hoOi)) {
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
void lobby_controller() {
    auto& c = ctx(); auto& nav = c.lobby_navigation;
    if (!c.window || !IsWindowVisible(c.window) ||
            !(GetForegroundWindow() == c.window || IsChild(c.window, GetForegroundWindow()))) return;
    auto pad = controller_pad(0); WORD down = pad.buttons;
    if (pad.lx < -7000) down |= XINPUT_GAMEPAD_DPAD_LEFT;
    if (pad.lx > 7000) down |= XINPUT_GAMEPAD_DPAD_RIGHT;
    if (pad.ly > 7000) down |= XINPUT_GAMEPAD_DPAD_UP;
    if (pad.ly < -7000) down |= XINPUT_GAMEPAD_DPAD_DOWN;
    const WORD pressed = down & ~nav.previous, direction = down & 15;
    const auto now = GetTickCount64();
    const bool navigate = direction && ((pressed & 15) || direction != nav.direction || now >= nav.repeat_at);
    nav.previous = down;
    if (!direction) nav.direction = 0;
    if (!pressed && !navigate) return;
    if (navigate) { nav.repeat_at = now + (direction == nav.direction ? 150 : 400); nav.direction = direction; }
    if (nav.pin) {
        auto pin = field(103); pin.resize(4, L'0');
        if (navigate) {
            if (direction & XINPUT_GAMEPAD_DPAD_LEFT) nav.digit = (nav.digit + 3) % 4;
            if (direction & XINPUT_GAMEPAD_DPAD_RIGHT) nav.digit = (nav.digit + 1) % 4;
            if (direction & (XINPUT_GAMEPAD_DPAD_UP | XINPUT_GAMEPAD_DPAD_DOWN)) {
                const int delta = direction & XINPUT_GAMEPAD_DPAD_UP ? 1 : 9;
                pin[nav.digit] = wchar_t(L'0' + (pin[nav.digit] - L'0' + delta) % 10);
                SetDlgItemTextW(c.window, 103, pin.c_str());
            }
            SendDlgItemMessageW(c.window, 103, EM_SETSEL, nav.digit, nav.digit + 1);
        }
        if (pressed & (XINPUT_GAMEPAD_A | XINPUT_GAMEPAD_B)) {
            if (pressed & XINPUT_GAMEPAD_B) SetDlgItemTextW(c.window, 103, L"");
            nav.pin = false; SendDlgItemMessageW(c.window, 103, EM_SETPASSWORDCHAR, L'*', 0);
            InvalidateRect(GetDlgItem(c.window, 103), nullptr, TRUE);
        }
        return;
    }
    const std::vector<int> order{100,110,103,104,105,109,106,107,108};
    auto enabled = [&](int id) { auto h = GetDlgItem(c.window, id); return h && IsWindowEnabled(h) && IsWindowVisible(h); };
    if (!nav.focus || !enabled(nav.focus) || nav.connected != c.connected || nav.joined != c.joined) {
        nav.focus = c.joined ? (c.hosting && !c.playing ? 106 : 108) : !c.rooms.empty() ? 110 : c.connected ? 104 : 100;
        if (!enabled(nav.focus)) nav.focus = 108;
        nav.connected = c.connected; nav.joined = c.joined;
    }
    if (navigate) {
        if (nav.focus == 110 && (direction & (XINPUT_GAMEPAD_DPAD_UP | XINPUT_GAMEPAD_DPAD_DOWN))) {
            const int count = int(SendMessageW(c.list, LB_GETCOUNT, 0, 0));
            const int selected = int(SendMessageW(c.list, LB_GETCURSEL, 0, 0));
            if (count) SendMessageW(c.list, LB_SETCURSEL, std::clamp(selected + (direction & XINPUT_GAMEPAD_DPAD_UP ? -1 : 1), 0, count - 1), 0);
        } else {
            int position = int(std::find(order.begin(), order.end(), nav.focus) - order.begin());
            const int delta = direction & (XINPUT_GAMEPAD_DPAD_UP | XINPUT_GAMEPAD_DPAD_LEFT) ? -1 : 1;
            do { position = (position + delta + int(order.size())) % int(order.size()); } while (!enabled(order[position]));
            nav.focus = order[position];
        }
    }
    SetFocus(GetDlgItem(c.window, nav.focus));
    SendMessageW(c.window, WM_CHANGEUISTATE, MAKEWPARAM(UIS_CLEAR, UISF_HIDEFOCUS), 0);
    if (pressed & XINPUT_GAMEPAD_B) { ShowWindow(c.window, SW_HIDE); SetForegroundWindow(c.game); return; }
    if (pressed & XINPUT_GAMEPAD_A) {
        if (nav.focus == 103) {
            auto pin = field(103); if (pin.size() != 4) SetDlgItemTextW(c.window, 103, L"0000");
            nav.pin = true; nav.digit = 0;
            SendDlgItemMessageW(c.window, 103, EM_SETPASSWORDCHAR, 0, 0);
            SendDlgItemMessageW(c.window, 103, EM_SETSEL, 0, 1);
            InvalidateRect(GetDlgItem(c.window, 103), nullptr, TRUE);
        } else if (nav.focus == 110 && !c.joined) SendMessageW(c.window, WM_COMMAND, MAKEWPARAM(105, BN_CLICKED), 0);
        else if (nav.focus != 110) SendMessageW(c.window, WM_COMMAND, MAKEWPARAM(nav.focus, BN_CLICKED), 0);
    }
}

LRESULT CALLBACK menu_proc(HWND window, UINT message, WPARAM w, LPARAM l) {
    auto& c = ctx();
    if (message == WM_TIMER && w == 1) {
        if (header() && !c.engine_busy) { safe_network(); lobby_controller(); }
        return 0;
    }
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
            WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU, r.left + 20, r.top + 30, 590, 540, c.game, nullptr, instance, nullptr);
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
        control(L"STATIC", L"D-pad: focus   A: select   B: back   Code: A edits, arrows change digits", 0, 16, 470, 536, 24);
        SendDlgItemMessageW(c.window, 101, EM_SETLIMITTEXT, 24, 0);
        SendDlgItemMessageW(c.window, 102, EM_SETLIMITTEXT, 40, 0);
    }
    c.lobby_navigation.focus = 0; c.lobby_navigation.pin = false;
    c.lobby_navigation.previous = controller_pad(0).buttons;
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
    if constexpr (N == create_pending || N == text_pending || N == show_pending || N == 33 || (N >= 23 && N <= 31 && N != 25)) return TRUE;
    if constexpr (N == 21) return c.exit_session && !c.exit_queued;
    if constexpr (N == 22) return c.playing;
    if constexpr (N == 25) return select_target();
    if constexpr (N == 32) return !c.playing || (p1 & (1 << c.slot));
    if constexpr (N < 16) {
        if constexpr (N == 1 || N == 2 || N >= 12) {
            p1 &= ~long(controls_consumed_mask());
            if (!p1) return FALSE;
        }
        if (!c.playing) {
            auto original = offline_object();
            return original && offline_conditions[N] ? offline_conditions[N](original, p1, p2) : FALSE;
        }
        if constexpr (N == 0) return p1 >= 0 && p1 < c.players;
        const WORD bits[] = {0, XINPUT_GAMEPAD_A, XINPUT_GAMEPAD_B, XINPUT_GAMEPAD_X, XINPUT_GAMEPAD_Y,
            XINPUT_GAMEPAD_BACK, XINPUT_GAMEPAD_LEFT_THUMB, XINPUT_GAMEPAD_LEFT_SHOULDER, XINPUT_GAMEPAD_RIGHT_THUMB,
            XINPUT_GAMEPAD_RIGHT_SHOULDER, 0, XINPUT_GAMEPAD_START, XINPUT_GAMEPAD_DPAD_UP,
            XINPUT_GAMEPAD_DPAD_DOWN, XINPUT_GAMEPAD_DPAD_LEFT, XINPUT_GAMEPAD_DPAD_RIGHT};
        for (int i = 0; i < c.players; ++i) if (p1 & (1 << i)) {
            if (c.pads[i].buttons & bits[N]) return TRUE;
            if constexpr (N == 1) {
                const auto target = mouse_object(c.pads[i]);
                if (target && target->hoOi == c.ui.attack) return TRUE;
            }
        }
    }
    return FALSE;
}
template<int N> long WINAPI expression(LPHO ho, long param) {
    auto& c = ctx();
    ho->hoFlags &= ~(HOF_STRING | HOF_FLOAT);
    if constexpr (N < 2) {
        const int mask = CNC_GetFirstExpressionParameter(reinterpret_cast<Data*>(ho), param, TYPE_LONG) & ~int(controls_consumed_mask());
        if (!c.playing && !game_input_focused()) return 0;
        for (int i = 0; i < (c.playing ? c.players : 4); ++i) if (mask & (1 << i)) {
            const auto pad = c.playing ? c.pads[i] : controller_pad(i);
            if (pad.buttons & fwum::mouse_target_button) continue;
            const int v = N == 0 ? pad.lx : -int(pad.ly);
            if (std::abs(v) > 7000) return v * 100 / 32768;
        }
        return 0;
    }
    if constexpr (N == 2) return c.snapshot ? c.snapshot->frame + 1 : c.frame + 1;
    if constexpr (N == 3) return guest_camera_center().x;
    if constexpr (N == 4) return guest_camera_center().y;
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
    if constexpr (N == 18) return !(c.joined && !c.hosting) && !c.exit_session;
    // Use expressions for guards so Fusion keeps the parent's object selection
    // when evaluating child events. Input belongs to the focused network slot.
    if constexpr (N == 19) return !c.playing && game_input_focused() && !controls_active();
    if constexpr (N == 20) {
        const auto key = CNC_GetFirstExpressionParameter(reinterpret_cast<Data*>(ho), param, TYPE_INT);
        return c.playing || !game_input_focused() || !(GetAsyncKeyState(int(key)) & 0x8000);
    }
    if constexpr (N == 21) {
        const auto mask = CNC_GetFirstExpressionParameter(reinterpret_cast<Data*>(ho), param, TYPE_INT);
        return !c.playing || (mask & (1 << c.slot));
    }
    if constexpr (N == 22) return slot_team(CNC_GetFirstExpressionParameter(reinterpret_cast<Data*>(ho), param, TYPE_INT));
    if constexpr (N == 23) return c.individual_battle;
    if constexpr (N == 24) return mouse_attack_choice(CNC_GetFirstExpressionParameter(reinterpret_cast<Data*>(ho), param, TYPE_INT));
    if constexpr (N == 25) return swap_requested(CNC_GetFirstExpressionParameter(reinterpret_cast<Data*>(ho), param, TYPE_INT));
    if constexpr (N == 26) return visible_battle_slot();
    if constexpr (N == 27) return c.party.chosen_slot;
    if constexpr (N == 28) return c.party.chosen_character;
    if constexpr (N == 29) return c.party.command;
    if constexpr (N == 30) return c.party.cursor_x;
    if constexpr (N == 31) return c.party.cursor_y;
    if constexpr (N == 32) return c.party.page + 1;
    if constexpr (N == 33) return c.party.page_count;
    if constexpr (N == 34) return c.party.cursor_character;
    if constexpr (N == 35) return c.party.valid;
    if constexpr (N == 36) {
        const auto slot = CNC_GetFirstExpressionParameter(reinterpret_cast<Data*>(ho), param, TYPE_INT);
        if (c.playing && c.frame == 4 && c.in_battle) return c.battle_owners.owner(slot, member_ids());
        return (std::max(int(slot), 1) - 1) % std::max(c.playing ? c.players : c.co_op_players, 1);
    }
    if constexpr (N == 37) return c.in_battle && GetTickCount64() - c.battle_started_at > 500 ? c.battle_health.living() : -1;
    if constexpr (N == 38) return c.in_battle && GetTickCount64() - c.battle_started_at > 500 ? c.battle_health.replacement(c.battle_teams) : 0;
    if constexpr (N == 39) {
        ho->hoFlags |= HOF_FLOAT;
        long bits; std::memcpy(&bits, &c.pose.scale, sizeof bits); return bits;
    }
    if constexpr (N == 40) return c.pose.x;
    if constexpr (N == 41) return c.pose.y;
    if constexpr (N == 42) {
        const int player = CNC_GetFirstExpressionParameter(reinterpret_cast<Data*>(ho), param, TYPE_INT) - 1;
        const int base = CNC_GetNextExpressionParameter(reinterpret_cast<Data*>(ho), param, TYPE_INT);
        return appearance(player, base);
    }
    if constexpr (N == 43) return clicked_control(CNC_GetFirstExpressionParameter(reinterpret_cast<Data*>(ho), param, TYPE_INT));
    return 0;
}
short WINAPI begin(LPHO ho, long, long) {
    auto& c = ctx(); c.data = reinterpret_cast<Data*>(ho);
    const int frame = CNC_GetIntParameter(c.data);
    c.ui.attack = CNC_GetIntParameter(c.data); c.ui.icon = CNC_GetIntParameter(c.data);
    c.ui.swap = CNC_GetIntParameter(c.data); c.ui.done = CNC_GetIntParameter(c.data); c.ui.reset = CNC_GetIntParameter(c.data);
    c.ui.category = CNC_GetIntParameter(c.data); c.ui.previous = CNC_GetIntParameter(c.data); c.ui.following = CNC_GetIntParameter(c.data);
    c.ui.cards = CNC_GetIntParameter(c.data);
    for (auto& avatar : c.ui.avatars) avatar = CNC_GetIntParameter(c.data);
    const auto view_text = reinterpret_cast<const wchar_t*>(CNC_GetStringParameter(c.data));
    if (c.frame != frame || c.data->frame != frame) {
        c.data->frame = frame;
        if (frame == 0) c.music.fill(Context::Music{}); // Fusion stops sounds when restarting the application.
        c.mapping.clear(); c.applied_effects.clear(); c.applied_sequence = uint32_t(-1); c.frame = int(frame); c.force_state = true;
        c.party.original.clear(); c.party.previous_slot = -1; c.party.previous.fill(0);
        c.party.selected.fill(0); c.party.characters.fill(0); c.party.valid = false;
        c.party.catalog = Json::object(); c.party.personal.clear(); c.party.requests.clear();
        c.party.versions.fill(0); c.party.pending = 0; c.party.feedback.clear(); c.party.received = unsigned(-1);
        c.party.restored.clear(); c.party.filters.clear();
        c.pads = {}; c.previous_pads = {}; c.sent_pad = {}; c.input_at = 0; c.sent_epoch = 0;
        for (auto& latch : c.input_latches) latch.arm();
        ++c.party.epoch;
        c.party.view = Json::parse(fwum::narrow(view_text ? std::wstring(view_text) : L"{}"));
        c.controls = Context::Controls{};
        c.controls.bound_buttons = c.party.view.value("bound_buttons", std::vector<std::array<int, 3>>{});
        c.controls.keyboard_global = c.party.view.value("keyboard_global", -1);
        c.controls.players_global = c.party.view.value("players_global", -1);
        if (c.party.view.contains("controls")) {
            for (const auto& id : c.party.view.at("controls")) c.controls.targets.insert(id.get<int>());
            c.controls.markers = c.party.view.at("markers").get<std::array<int, 4>>();
            c.controls.back = c.party.view.value("back_control", -1);
            c.controls.preferred = c.party.view.value("preferred", -1);
            c.controls.preferences = c.party.view.value("preferences", std::vector<int>{});
            c.controls.automatic = c.party.view.value("auto_focus", true);
            c.controls.host_only = c.party.view.value("host_only", false);
            c.controls.world = c.party.view.value("world", false);
            c.controls.keyboard_global = c.party.view.value("keyboard_global", -1);
            c.controls.players_global = c.party.view.value("players_global", -1);
            c.controls.slider_knob = c.party.view.value("slider_knob", -1);
            c.controls.slider_track = c.party.view.value("slider_track", -1);
            c.controls.hint = c.party.view.value("control_hint", -1);
        }
        if (frame == 3) {
            for (auto key : {"icon", "done", "reset", "category", "previous", "following", "focus", "skin", "back"})
                c.party.personal.insert(c.party.view.value(key, -1));
            for (auto key : {"labels", "portraits", "borders"})
                for (const auto& id : c.party.view.value(key, Json::array())) c.party.personal.insert(id.get<int>());
        }
        c.image_bounds.clear();
        c.switch_object = 0; c.switch_checked_loop = -1;
        if (frame != 4) c.in_battle = false;
        c.audio_out = Json::array();
        c.audio.erase(std::remove_if(c.audio.begin(), c.audio.end(),
            [frame](const auto& m) { return m.at("frame").template get<int>() != frame; }), c.audio.end());
        log("frame " + std::to_string(frame) + " objects=" + std::to_string(objects().size()));
    }
    safe_network();
    bound_buttons_tick();
    controls_tick();
    return 0;
}
short WINAPI configure_combat(LPHO ho, long, long) {
    auto& c = ctx(); auto d = reinterpret_cast<Data*>(ho);
    c.co_op_players = std::clamp(int(CNC_GetIntParameter(d)), 1, 4);
    c.battle_slot = CNC_GetIntParameter(d);
    const bool battle = CNC_GetIntParameter(d) != 0;
    c.co_op_keyboard = CNC_GetIntParameter(d); c.co_op_owner = CNC_GetIntParameter(d);
    if (!c.playing) {
        for (int i = 0; i < 4; ++i) c.pads[i] = physical_pad(i, i == 0 && !c.co_op_keyboard);
        c.keyboard_pad = physical_pad(-1, true);
    }
    c.battle_health.begin_tick();
    if (battle != c.in_battle) {
        ++c.party.epoch; c.pads = {}; c.previous_pads = {};
        c.controls.open.fill(false); c.controls.focus.fill(0); c.controls.clicks.fill(0); c.controls.pending_click = 0;
        for (auto& latch : c.input_latches) latch.arm();
    }
    if (battle && !c.in_battle) {
        c.battle_started_at = GetTickCount64();
        if (c.playing) c.battle_owners.begin(member_ids());
    }
    if (!battle) { c.individual_battle = false; c.battle_teams = 0; c.battle_owners.clear(); }
    else if (c.co_op_players > 1 && !c.individual_battle) {
        const auto current = slot_team(1);
        c.battle_teams = current ? 15 : 0; c.individual_battle = true;
    }
    c.in_battle = battle;
    return 0;
}
short WINAPI configure_health(LPHO ho, long, long) {
    auto d = reinterpret_cast<Data*>(ho);
    const int slot = CNC_GetIntParameter(d);
    double hp[4]{};
    for (auto& value : hp) {
        const auto bits = CNC_GetFloatParameter(d); float number; std::memcpy(&number, &bits, sizeof number);
        if (!std::isfinite(number)) return 0;
        value = number;
    }
    ctx().battle_health.set(slot, hp[0], hp[1], hp[2], hp[3]);
    return 0;
}
short WINAPI switch_character(LPHO, long slot, long) {
    auto& c = ctx();
    if (c.individual_battle && c.in_battle && slot >= 1 && slot <= 4) c.battle_teams ^= 1u << (slot - 1);
    return 0;
}
short WINAPI fit_character(LPHO ho, long, long) {
    auto d = reinterpret_cast<Data*>(ho); auto& c = ctx();
    const int oi = CNC_GetIntParameter(d), center = CNC_GetIntParameter(d), feet = CNC_GetIntParameter(d);
    const int width = std::max(1, int(CNC_GetIntParameter(d))), height = std::max(1, int(CNC_GetIntParameter(d)));
    for (auto target : objects()) if (target->hoOi == oi) {
        const auto image = common(target)->rcImage;
        Img info{}; GetImageInfoEx(header()->rhIdAppli, image, 0, 1, 1, &info);
        RECT bounds{0, 0, std::max(1, int(info.imgWidth)), std::max(1, int(info.imgHeight))};
        auto cached = c.image_bounds.find(image);
        if (cached != c.image_bounds.end()) bounds = cached->second;
        else {
            auto mask = GetImageMask(header()->rhIdAppli, image, GCMF_OBSTACLE);
            if (readable(mask, sizeof(sMask)) && mask->mkWidth > 0 && mask->mkWidth <= 8192 &&
                    mask->mkHeight > 0 && mask->mkHeight <= 8192 && mask->mkWidthBytes >= (mask->mkWidth + 15) / 16 * 2 &&
                    mask->mkWidthBytes <= 4096 && readable(mask, sizeof(sMask) + size_t(mask->mkWidthBytes) * mask->mkHeight)) {
                const auto bits = reinterpret_cast<const BYTE*>(mask) + sizeof(sMask);
                RECT opaque{mask->mkWidth, mask->mkHeight, 0, 0};
                for (int y = 0; y < mask->mkHeight; ++y) {
                    auto row = reinterpret_cast<const WORD*>(bits + size_t(y) * mask->mkWidthBytes);
                    for (int x = 0; x < mask->mkWidth; ++x) if (row[x / 16] & (0x8000u >> (x & 15))) {
                        opaque.left = std::min(opaque.left, LONG(x)); opaque.right = std::max(opaque.right, LONG(x + 1));
                        opaque.top = std::min(opaque.top, LONG(y)); opaque.bottom = std::max(opaque.bottom, LONG(y + 1));
                    }
                }
                if (opaque.right > opaque.left && opaque.bottom > opaque.top) bounds = opaque;
            }
            c.image_bounds.emplace(image, bounds);
            if (!c.state_file.empty()) log("character bounds image=" + std::to_string(image) + " canvas=" +
                std::to_string(info.imgWidth) + "x" + std::to_string(info.imgHeight) + " visible=" +
                std::to_string(bounds.left) + "," + std::to_string(bounds.top) + "," +
                std::to_string(bounds.right) + "," + std::to_string(bounds.bottom));
        }
        c.pose.scale = std::clamp(std::min(float(width) / (bounds.right - bounds.left),
            float(height) / (bounds.bottom - bounds.top)), .01f, 8.f);
        c.pose.x = center - int(std::lround(c.pose.scale * ((bounds.left + bounds.right) / 2.f - info.imgXSpot)));
        c.pose.y = feet - int(std::lround(c.pose.scale * (bounds.bottom - info.imgYSpot)));
        break;
    }
    return 0;
}
short WINAPI configure_party(LPHO ho, long, long) {
    auto& p = ctx().party; auto d = reinterpret_cast<Data*>(ho);
    const int row = CNC_GetIntParameter(d), character = CNC_GetIntParameter(d);
    p.players = std::clamp(int(CNC_GetIntParameter(d)), 1, 4); p.keyboard = CNC_GetIntParameter(d);
    CNC_GetIntParameter(d); // card object, also supplied to guests by Begin
    p.slot = CNC_GetIntParameter(d);
    if (row >= 1 && row <= 8 && p.characters[row - 1] != character) {
        p.characters[row - 1] = character; ++p.versions[row - 1];
    }
    p.owner = std::clamp(((p.slot - 1) % 4) % p.players, 0, p.players - 1);
    p.preferred = p.slot >= 1 && p.slot <= 8 ? p.characters[p.slot - 1] : 0;
    return 0;
}
void party_tick_legacy() {
    auto& c = ctx(); auto& p = c.party;
    if (c.frame != 3 || (c.joined && !c.hosting)) return;
    const auto all = objects();
    auto visible = [&](LPHO ho, bool show) {
        if (show) sprite(ho)->rsFlags &= ~RSFLAG_HIDDEN;
        else sprite(ho)->rsFlags |= RSFLAG_HIDDEN;
        if (common(ho)->rcSprite) ShowSprite(header()->rhIdEditWin, common(ho)->rcSprite, show);
        redraw(ho);
    };
    if (p.players <= 1 || p.slot <= 0) {
        if (!p.original.empty()) {
            for (auto ho : all) {
                const auto old = p.original.find(fixed(ho));
                if (old == p.original.end()) continue;
                ho->hoX = old->second.first.x; ho->hoY = old->second.first.y;
                visible(ho, !old->second.second);
            }
            p.original.clear(); p.previous_slot = -1;
        }
        return;
    }
    std::vector<LPHO> icons, headings;
    for (auto ho : all) if (ho->hoOi == c.ui.icon || ho->hoOi == c.ui.category) {
        p.original.emplace(fixed(ho), std::make_pair(POINT{ho->hoX, ho->hoY}, bool(sprite(ho)->rsFlags & RSFLAG_HIDDEN)));
        if (ho->hoOi == c.ui.category) { headings.push_back(ho); continue; }
        const auto character = integer_value(ho, 1);
        // Ultra reserves 257-264 for empty/dead party slots, with RIP art.
        if (character > 0 && (character < 257 || character > 264)) icons.push_back(ho);
        else { ho->hoX = ho->hoY = -400; visible(ho, false); }
    }
    auto original = [&](LPHO ho) { return p.original.at(fixed(ho)).first; };
    auto order = [&](LPHO a, LPHO b) {
        const auto x = original(a), y = original(b);
        return x.y == y.y ? x.x < y.x : x.y < y.y;
    };
    std::sort(icons.begin(), icons.end(), order);
    // Source portraits in the same row can differ by one or two pixels.
    for (size_t first = 0; first < icons.size();) {
        size_t last = first + 1;
        while (last < icons.size() && original(icons[last]).y - original(icons[first]).y <= 8) ++last;
        std::sort(icons.begin() + first, icons.begin() + last, [&](auto a, auto b) { return original(a).x < original(b).x; });
        first = last;
    }
    std::sort(headings.begin(), headings.end(), order);
    if (icons.empty()) return;
    struct Page { int begin, end; LPHO heading; };
    std::vector<Page> pages;
    int start = 0;
    while (start < int(icons.size())) {
        auto category = [&](LPHO icon) {
            LPHO result = nullptr;
            for (auto heading : headings) if (original(heading).y <= original(icon).y) result = heading;
            return result;
        };
        auto heading = category(icons[start]);
        int end = start + 1;
        while (end < int(icons.size()) && end - start < 32 && category(icons[end]) == heading) ++end;
        pages.push_back({start, end, heading}); start = end;
    }
    if (p.previous_slot != p.slot) {
        const auto desired = std::find_if(icons.begin(), icons.end(), [&](auto ho) { return integer_value(ho, 1) == p.preferred; });
        p.cursor = desired == icons.end() ? 0 : int(desired - icons.begin());
        p.previous_slot = p.slot; p.repeating = 0; p.repeat_at = 0;
    }
    p.cursor = std::clamp(p.cursor, 0, int(icons.size()) - 1);
    std::array<Pad, 4> inputs{};
    for (int player = 0; player < p.players; ++player) {
        inputs[player] = c.playing ? c.pads[player] : physical_pad(player - p.keyboard, player == 0);
        if (!c.playing && p.keyboard && player == 0) inputs[player] = physical_pad(-1, true);
    }
    auto row_owner = [&](int row) { return ((row - 1) % 4) % p.players; };
    auto unlocked = [&](int character) {
        return std::any_of(icons.begin(), icons.end(), [&](auto icon) {
            const auto v = values(icon);
            return integer_value(icon, 1) == character && v && (v->rvValueFlags & 1);
        });
    };
    auto valid = [&] { return std::all_of(p.characters.begin(), p.characters.end(), unlocked); };
    auto callback = [&](int command, int row, int character = 0) {
        p.command = command; p.chosen_slot = row; p.chosen_character = character;
        generate(33); p.command = -1;
    };
    auto activate = [&](int player, bool follow) {
        p.slot = p.selected[player]; p.owner = player; p.previous_slot = p.slot;
        callback(4, p.slot);
        if (follow) {
            auto desired = std::find_if(icons.begin(), icons.end(), [&](auto icon) { return integer_value(icon, 1) == p.characters[p.slot - 1]; });
            if (desired != icons.end()) p.cursor = int(desired - icons.begin());
        }
    };
    bool direction_held = false;
    for (int player = 0; player < p.players; ++player) {
        if (p.selected[player] < 1 || row_owner(p.selected[player]) != player) p.selected[player] = player + 1;
        auto down = inputs[player].buttons;
        if (!(down & fwum::mouse_target_button)) {
            if (inputs[player].lx < -7000) down |= XINPUT_GAMEPAD_DPAD_LEFT;
            if (inputs[player].lx > 7000) down |= XINPUT_GAMEPAD_DPAD_RIGHT;
            if (inputs[player].ly > 7000) down |= XINPUT_GAMEPAD_DPAD_UP;
            if (inputs[player].ly < -7000) down |= XINPUT_GAMEPAD_DPAD_DOWN;
        }
        const WORD pressed = down & ~p.previous[player];
        const auto target = mouse_object(inputs[player]);
        const bool mouse_pressed = (down & fwum::mouse_target_button) && !(p.previous[player] & fwum::mouse_target_button);
        const WORD direction = down & (XINPUT_GAMEPAD_DPAD_UP | XINPUT_GAMEPAD_DPAD_DOWN | XINPUT_GAMEPAD_DPAD_LEFT | XINPUT_GAMEPAD_DPAD_RIGHT);
        if (mouse_pressed && target && target->hoOi >= c.ui.cards && target->hoOi < c.ui.cards + 8) {
            const int row = target->hoOi - c.ui.cards + 1;
            if (row_owner(row) == player) { p.selected[player] = row; activate(player, true); }
        }
        if (pressed & XINPUT_GAMEPAD_B) {
            int row = p.selected[player];
            do { row = row % 8 + 1; } while (row_owner(row) != player);
            p.selected[player] = row; activate(player, true);
        }
        const auto now = GetTickCount64();
        if (direction) {
            direction_held = true;
            if (direction != p.repeating || now >= p.repeat_at) {
                activate(player, false);
                const int delta = direction & XINPUT_GAMEPAD_DPAD_UP ? -8 : direction & XINPUT_GAMEPAD_DPAD_DOWN ? 8 :
                    direction & XINPUT_GAMEPAD_DPAD_LEFT ? -1 : 1;
                p.cursor = std::clamp(p.cursor + delta, 0, int(icons.size()) - 1);
                p.repeat_at = now + (direction == p.repeating ? 140 : 350); p.repeating = direction;
            }
        }
        p.page = 0;
        for (size_t page = 0; page < pages.size(); ++page) if (p.cursor >= pages[page].begin) p.page = int(page);
        int delta = 0;
        if ((pressed & XINPUT_GAMEPAD_LEFT_SHOULDER) || (mouse_pressed && target && target->hoOi == c.ui.previous)) delta = -1;
        if ((pressed & XINPUT_GAMEPAD_RIGHT_SHOULDER) || (mouse_pressed && target && target->hoOi == c.ui.following)) delta = 1;
        if (delta) {
            activate(player, false);
            p.page = std::clamp(p.page + delta, 0, int(pages.size()) - 1); p.cursor = pages[p.page].begin;
        }
        int character = (pressed & XINPUT_GAMEPAD_A) ? integer_value(icons[p.cursor], 1) : 0;
        if (mouse_pressed && target && target->hoOi == c.ui.icon) {
            character = integer_value(target, 1);
            const auto selected = std::find(icons.begin(), icons.end(), target);
            if (selected != icons.end()) p.cursor = int(selected - icons.begin());
        }
        if (character) {
            activate(player, false);
            if (unlocked(character)) {
                p.characters[p.selected[player] - 1] = character;
                callback(0, p.selected[player], character);
            }
        }
        if (player == 0 && ((pressed & XINPUT_GAMEPAD_START) ||
                (mouse_pressed && target && target->hoOi == c.ui.done)) && valid()) callback(1, p.slot);
        if (player == 0 && ((pressed & XINPUT_GAMEPAD_BACK) ||
                (mouse_pressed && target && target->hoOi == p.view.value("back", -1)))) callback(6, p.slot);
        if ((pressed & XINPUT_GAMEPAD_X) || (mouse_pressed && target && target->hoOi == c.ui.reset)) {
            for (int row = 1; row <= 8; ++row) if (row_owner(row) == player) {
                p.characters[row - 1] = 0; callback(5, row);
            }
            activate(player, false);
        }
        const int base = p.characters[p.selected[player] - 1];
        const auto families = p.view.value("skins", Json::object()); const auto key = std::to_string(base);
        if (families.contains(key)) {
            std::vector<int> choices;
            for (const auto& option : families.at(key)) if (unlocked(option)) choices.push_back(option.get<int>());
            if (p.restored.insert(player * 10000 + base).second) {
                const auto preferred = saved_skin(base, player);
                if (std::find(choices.begin(), choices.end(), preferred) != choices.end()) c.cosmetics[cosmetic_member(player)][base] = preferred;
            }
            if (choices.size() > 1 && ((pressed & XINPUT_GAMEPAD_Y) ||
                    (mouse_pressed && target && target->hoOi == p.view.value("skin", -1)))) {
                activate(player, false);
                const auto at = std::find(choices.begin(), choices.end(), appearance(player, base));
                const auto selected = choices[(at == choices.end() ? 0 : size_t(at - choices.begin()) + 1) % choices.size()];
                c.cosmetics[cosmetic_member(player)][base] = selected; save_skin(base, selected, player);
            }
        }
        p.previous[player] = down;
    }
    if (!direction_held) p.repeating = 0;
    p.valid = valid();
    p.page_count = int(pages.size());
    p.page = 0;
    for (size_t index = 0; index < pages.size(); ++index) if (p.cursor >= pages[index].begin) p.page = int(index);
    const auto& page = pages[p.page];
    for (auto heading : headings) {
        const bool show = heading == page.heading;
        heading->hoX = show ? 102 : -400; heading->hoY = show ? 35 : -400;
        visible(heading, show);
    }
    for (size_t i = 0; i < icons.size(); ++i) {
        auto ho = icons[i]; const bool show = int(i) >= page.begin && int(i) < page.end;
        const int local = int(i) - page.begin;
        ho->hoX = show ? 22 + (local % 8) * 73 : -400;
        ho->hoY = show ? 64 + (local / 8) * 72 : -400;
        visible(ho, show);
    }
    p.cursor_character = integer_value(icons[p.cursor], 1);
    p.cursor_x = icons[p.cursor]->hoX + 24; p.cursor_y = icons[p.cursor]->hoY - 22;
    const int owner = row_owner(p.slot), base = p.characters[p.slot - 1];
    for (auto ho : all) if (ho->hoOi == p.view.value("skin", -1)) {
        const auto families = p.view.value("skins", Json::object());
        if (families.contains(std::to_string(base))) party_text(ho,
            L"P" + std::to_wstring(owner + 1) + L"  Y / C: skin", 0x5ad4ff);
        else visible(ho, false);
    }
}
void party_visible(LPHO ho, bool show) {
    if (show) sprite(ho)->rsFlags &= ~RSFLAG_HIDDEN;
    else sprite(ho)->rsFlags |= RSFLAG_HIDDEN;
    if (common(ho)->rcSprite) {
        ShowSprite(header()->rhIdEditWin, common(ho)->rcSprite, show);
        if (show) MoveSpriteToFront(header()->rhIdEditWin, common(ho)->rcSprite);
    }
    redraw(ho);
}
void party_text(LPHO ho, const std::wstring& text, unsigned colour = 0xffffff) {
    auto& c = ctx(); fwum::Entity entity; entity.oi = ho->hoOi; entity.type = 3;
    entity.text.assign(reinterpret_cast<const char16_t*>(text.data()), text.size());
    const auto saved_target = c.target; const auto saved_entity = c.entity;
    c.target = ho; c.entity = &entity; generate(text_pending);
    system_fields(ho)->rsTextColor = colour; party_visible(ho, true);
    c.target = saved_target; c.entity = saved_entity;
}
void party_filter(LPHO ho, unsigned rgb = 0xffffff, unsigned alpha = 0) {
    auto& c = ctx(); const unsigned rgba = ((255u - alpha) << 24) | rgb;
    const auto old = c.party.filters.find(fixed(ho));
    if (old != c.party.filters.end() && old->second == rgba) return;
    c.party.filters[fixed(ho)] = rgba;
    fwum::Entity entity; entity.oi = ho->hoOi; entity.type = ho->hoType; entity.effect_param = rgba;
    const auto saved_target = c.target; const auto saved_entity = c.entity;
    c.target = ho; c.entity = &entity; generate(31);
    c.target = saved_target; c.entity = saved_entity;
}
void party_image(LPHO ho, int image, int x, int y, float scale_x = 1, float scale_y = 1) {
    auto rc = common(ho); rc->rcImage = image_map().to_memory(image);
    rc->rcScaleX = scale_x; rc->rcScaleY = scale_y;
    if (ctx().joined && !ctx().hosting) rc->rcRoutineAnimation = no_move;
    Img info{}; GetImageInfoEx(header()->rhIdAppli, rc->rcImage, 0, scale_x, scale_y, &info);
    ho->hoImgWidth = info.imgWidth; ho->hoImgHeight = info.imgHeight;
    ho->hoImgXSpot = info.imgXSpot; ho->hoImgYSpot = info.imgYSpot;
    ho->hoX = x; ho->hoY = y; party_visible(ho, true);
}
std::string shared_party() {
    auto& c = ctx(); auto& p = c.party;
    if (!c.playing || !c.hosting) return {};
    if (c.frame != 3 || p.catalog.empty()) return Json{{"epoch", p.epoch},
        {"phase", c.in_battle ? "battle" : c.frame >= 4 && c.frame <= 8 ? "world" : "scene"}}.dump();
    Json state = p.catalog;
    state["epoch"] = p.epoch; state["characters"] = p.characters; state["versions"] = p.versions;
    state["skins"] = Json::array();
    for (int player = 0; player < c.players; ++player) {
        Json choices = Json::object();
        for (const auto& choice : c.cosmetics[cosmetic_member(player)]) choices[std::to_string(choice.first)] = choice.second;
        state["skins"].push_back(std::move(choices));
    }
    return state.dump();
}
void party_online_tick() {
    auto& c = ctx(); auto& p = c.party;
    if (c.frame != 3 || p.view.empty()) return;
    const auto all = objects();
    std::map<int, LPHO> by_oi, by_source;
    for (auto ho : all) { by_oi.emplace(ho->hoOi, ho); by_source.emplace(ho->hoHFII, ho); }
    auto find = [&](int oi) -> LPHO { auto at = by_oi.find(oi); return at == by_oi.end() ? nullptr : at->second; };
    auto source = [&](int id) -> LPHO { auto at = by_source.find(id); return at == by_source.end() ? nullptr : at->second; };
    auto text = [&](const char* key, const std::wstring& value, unsigned colour = 0xffffff) {
        if (auto ho = find(p.view.value(key, -1))) party_text(ho, value, colour);
    };
    p.players = c.players;
    if (c.hosting && p.catalog.empty()) {
        std::vector<LPHO> icons, headings;
        for (auto ho : all) if (ho->hoOi == c.ui.icon || ho->hoOi == c.ui.category) {
            p.original.emplace(fixed(ho), std::make_pair(POINT{ho->hoX, ho->hoY}, bool(sprite(ho)->rsFlags & RSFLAG_HIDDEN)));
            if (ho->hoOi == c.ui.category) headings.push_back(ho);
            else if (const auto id = integer_value(ho, 1); id > 0 && (id < 257 || id > 264)) icons.push_back(ho);
        }
        auto position = [&](LPHO ho) { return p.original.at(fixed(ho)).first; };
        auto order = [&](LPHO a, LPHO b) { auto x = position(a), y = position(b); return x.y == y.y ? x.x < y.x : x.y < y.y; };
        std::sort(icons.begin(), icons.end(), order); std::sort(headings.begin(), headings.end(), order);
        for (size_t first = 0; first < icons.size();) {
            size_t end = first + 1;
            while (end < icons.size() && position(icons[end]).y - position(icons[first]).y <= 8) ++end;
            std::sort(icons.begin() + first, icons.begin() + end, [&](auto a, auto b) { return position(a).x < position(b).x; });
            first = end;
        }
        if (icons.size() < 32 || headings.empty()) return; // Source initialization has not finished yet.
        p.catalog = {{"icons", Json::array()}, {"headings", Json::array()}};
        for (auto ho : headings) { auto at = position(ho); p.catalog["headings"].push_back({ho->hoHFII, image_map().to_disk(common(ho)->rcImage), at.x, at.y}); }
        for (auto ho : icons) {
            auto at = position(ho); int category = 0;
            for (size_t i = 0; i < headings.size(); ++i) if (position(headings[i]).y <= at.y) category = int(i);
            p.catalog["icons"].push_back({ho->hoHFII, integer_value(ho, 1), image_map().to_disk(common(ho)->rcImage),
                at.x, at.y, integer_value(ho, 2), bool(values(ho)->rvValueFlags & 1), category});
        }
    }
    if (!c.hosting && c.snapshot && c.snapshot->frame == 3 && p.received != c.snapshot->sequence && !c.snapshot->party.empty()) {
        auto state = Json::parse(c.snapshot->party);
        if (state.at("characters").size() != 8 || state.at("versions").size() != 8 ||
                state.at("icons").size() > 4096 || state.at("headings").size() > 128) throw std::runtime_error("Invalid party data.");
        p.epoch = state.at("epoch"); p.characters = state.at("characters").get<std::array<int, 8>>();
        p.versions = state.at("versions").get<std::array<unsigned, 8>>(); p.catalog = std::move(state);
        if (p.catalog.contains("skins")) for (size_t player = 0; player < p.catalog["skins"].size() && player < 4; ++player)
            for (auto item = p.catalog["skins"][player].begin(); item != p.catalog["skins"][player].end(); ++item)
                c.cosmetics[cosmetic_member(int(player))][std::stoi(item.key())] = item.value().get<int>();
        p.received = c.snapshot->sequence;
    }
    if (p.catalog.empty()) return;
    const auto& icons = p.catalog.at("icons"); const auto& headings = p.catalog.at("headings");
    auto unlocked = [&icons](int character) {
        return character > 0 && std::any_of(icons.begin(), icons.end(), [character](const Json& item) {
            return item[1].get<int>() == character && item[6].get<bool>();
        });
    };
    auto owner = [&](int row) { return ((row - 1) % 4) % std::max(1, c.players); };
    auto callback = [&](int command, int row, int character = 0) {
        p.command = command; p.chosen_slot = row; p.chosen_character = character;
        generate(33); p.command = -1;
    };
    auto apply = [&](int player, const Json& request) -> std::wstring {
        const int row = request.at("row"), character = request.at("character");
        if (request.at("epoch").get<unsigned>() != p.epoch || row < 1 || row > 8) return L"That party screen has closed.";
        if (owner(row) != player) return L"Choose one of your own player slots.";
        if (request.at("revision").get<unsigned>() != p.versions[row - 1]) return L"That slot changed. Please choose again.";
        const auto command = request.at("command").get<std::string>();
        if (command == "pick") {
            if (!unlocked(character)) return L"That character is locked.";
            p.characters[row - 1] = character; ++p.versions[row - 1]; callback(0, row, character);
        } else if (command == "reset") {
            for (int i = 1; i <= 8; ++i) if (owner(i) == player) {
                p.characters[i - 1] = 0; ++p.versions[i - 1]; callback(5, i);
            }
        } else if (command == "skin") {
            const int base = p.characters[row - 1]; const auto key = std::to_string(base);
            const auto skins = p.view.value("skins", Json::object());
            if (!skins.contains(key) || std::find(skins.at(key).begin(), skins.at(key).end(), character) == skins.at(key).end() ||
                    !unlocked(character)) return L"Unlock that skin before choosing it.";
            c.cosmetics[cosmetic_member(player)][base] = character; ++p.versions[row - 1];
            if (player == 0) save_skin(base, character);
        } else return L"That choice is unavailable.";
        callback(4, p.selected[0]); // A remote edit must not move the host's selected slot.
        c.force_state = true; return {};
    };
    const int player = std::clamp(c.slot, 0, c.players - 1);
    if (p.selected[player] < 1 || p.selected[player] > 8 || owner(p.selected[player]) != player) p.selected[player] = player + 1;
    p.slot = p.selected[player];
    while (c.hosting && !p.requests.empty()) {
        auto request = std::move(p.requests.front()); p.requests.pop_front();
        const int seat = request.value("slot", -1); const auto members = member_ids();
        std::wstring error = L"Your player slot has changed. Please choose again.";
        if (seat > 0 && size_t(seat) < members.size() && request.value("member", "") == members[seat]) error = apply(seat, request);
        send({{"type", "party-result"}, {"member", request.at("member")}, {"seq", request.at("seq")},
              {"accepted", error.empty()}, {"message", fwum::narrow(error)}});
    }
    auto submit = [&](const std::string& command, int character) {
        if (p.pending) { p.feedback = L"Waiting for the host to confirm your choice..."; return; }
        Json request{{"type", "party-edit"}, {"version", 1}, {"seq", ++p.sequence}, {"epoch", p.epoch},
            {"revision", p.versions[p.slot - 1]}, {"row", p.slot}, {"command", command}, {"character", character}};
        p.pending_base = command == "skin" ? p.characters[p.slot - 1] : 0; p.pending_skin = character;
        if (c.hosting) p.feedback = apply(player, request);
        else { p.pending = p.sequence; p.pending_at = GetTickCount64(); send(request); p.feedback = L"Applying your choice..."; }
    };
    struct Page { int begin, end, category; };
    std::vector<Page> pages;
    for (int start = 0; start < int(icons.size());) {
        int end = start + 1; const int category = icons[start][7];
        while (end < int(icons.size()) && end - start < 32 && icons[end][7].template get<int>() == category) ++end;
        pages.push_back({start, end, category}); start = end;
    }
    auto follow = [&] {
        const int character = p.characters[p.slot - 1];
        auto at = std::find_if(icons.begin(), icons.end(), [character](const Json& icon) { return icon[1].get<int>() == character; });
        if (at != icons.end()) p.cursor = int(at - icons.begin());
    };
    if (p.previous_slot != p.slot) { follow(); p.previous_slot = p.slot; p.repeating = 0; }
    p.cursor = std::clamp(p.cursor, 0, int(icons.size()) - 1);
    auto pad = physical_pad(); WORD down = pad.buttons;
    if (!(down & fwum::mouse_target_button)) {
        if (pad.lx < -7000) down |= XINPUT_GAMEPAD_DPAD_LEFT;
        if (pad.lx > 7000) down |= XINPUT_GAMEPAD_DPAD_RIGHT;
        if (pad.ly > 7000) down |= XINPUT_GAMEPAD_DPAD_UP;
        if (pad.ly < -7000) down |= XINPUT_GAMEPAD_DPAD_DOWN;
    }
    const WORD pressed = down & ~p.previous[player];
    const auto target = mouse_object(pad);
    const bool click = (down & fwum::mouse_target_button) && !(p.previous[player] & fwum::mouse_target_button);
    if (click && target && target->hoOi >= c.ui.cards && target->hoOi < c.ui.cards + 8) {
        const int row = target->hoOi - c.ui.cards + 1;
        if (owner(row) == player) { p.selected[player] = p.slot = row; p.previous_slot = row; follow(); p.feedback.clear(); }
        else p.feedback = L"P" + std::to_wstring(owner(row) + 1) + L" owns that slot.";
    }
    if (pressed & XINPUT_GAMEPAD_B) {
        int row = p.slot; do { row = row % 8 + 1; } while (owner(row) != player);
        p.selected[player] = p.slot = row; p.previous_slot = row; follow(); p.feedback.clear();
    }
    const WORD direction = down & 15;
    const auto now = GetTickCount64();
    if (direction && (direction != p.repeating || now >= p.repeat_at)) {
        const int delta = direction & XINPUT_GAMEPAD_DPAD_UP ? -8 : direction & XINPUT_GAMEPAD_DPAD_DOWN ? 8 :
            direction & XINPUT_GAMEPAD_DPAD_LEFT ? -1 : 1;
        p.cursor = std::clamp(p.cursor + delta, 0, int(icons.size()) - 1);
        p.repeat_at = now + (direction == p.repeating ? 140 : 350); p.repeating = direction;
    }
    if (!direction) p.repeating = 0;
    p.page = 0;
    for (size_t i = 0; i < pages.size(); ++i) if (p.cursor >= pages[i].begin) p.page = int(i);
    int page_delta = 0;
    if ((pressed & XINPUT_GAMEPAD_LEFT_SHOULDER) || (click && target && target->hoOi == c.ui.previous)) page_delta = -1;
    if ((pressed & XINPUT_GAMEPAD_RIGHT_SHOULDER) || (click && target && target->hoOi == c.ui.following)) page_delta = 1;
    if (page_delta) { p.page = std::clamp(p.page + page_delta, 0, int(pages.size()) - 1); p.cursor = pages[p.page].begin; }
    int character = (pressed & XINPUT_GAMEPAD_A) ? icons[p.cursor][1].get<int>() : 0;
    if (click && target && target->hoOi == c.ui.icon) {
        const int instance = target->hoHFII;
        auto at = std::find_if(icons.begin(), icons.end(), [instance](const Json& icon) { return icon[0].get<int>() == instance; });
        if (at != icons.end()) { p.cursor = int(at - icons.begin()); character = (*at)[1]; }
    }
    if (character) submit("pick", character);
    const int base = p.characters[p.slot - 1]; const auto skin_key = std::to_string(base);
    const auto families = p.view.value("skins", Json::object());
    if (families.contains(skin_key)) {
        std::vector<int> choices;
        for (const auto& option : families.at(skin_key)) if (unlocked(option)) choices.push_back(option.get<int>());
        if ((pressed & XINPUT_GAMEPAD_Y) || (click && target && target->hoOi == p.view.value("skin", -1))) {
            if (choices.size() > 1) {
                const auto current = std::find(choices.begin(), choices.end(), appearance(player, base));
                submit("skin", choices[(current == choices.end() ? 0 : size_t(current - choices.begin()) + 1) % choices.size()]);
            } else p.feedback = L"Unlock another skin for this character first.";
        }
        if (!p.pending && p.restored.insert(base).second) {
            const int preferred = saved_skin(base);
            if (preferred != appearance(player, base) && std::find(choices.begin(), choices.end(), preferred) != choices.end()) submit("skin", preferred);
        }
    }
    if ((pressed & XINPUT_GAMEPAD_X) || (click && target && target->hoOi == c.ui.reset)) submit("reset", 0);
    p.valid = std::all_of(p.characters.begin(), p.characters.end(), unlocked);
    if (player == 0 && ((pressed & XINPUT_GAMEPAD_START) || (click && target && target->hoOi == c.ui.done))) {
        if (p.valid && !p.pending) callback(1, p.slot); else p.feedback = L"Fill all eight slots with unlocked characters first.";
    }
    if (player == 0 && (pressed & XINPUT_GAMEPAD_BACK)) callback(6, p.slot);
    if (player == 0 && click && target && target->hoOi == p.view.value("back", -1)) callback(6, p.slot);
    if (p.pending && now - p.pending_at > 3000) { p.pending = 0; p.feedback = L"No confirmation yet. Please try again."; }
    p.previous[player] = down;
    p.page = 0; p.page_count = int(pages.size());
    for (size_t i = 0; i < pages.size(); ++i) if (p.cursor >= pages[i].begin) p.page = int(i);
    const auto page = pages[p.page];
    for (auto ho : all) if (ho->hoOi == c.ui.icon || ho->hoOi == c.ui.category) party_visible(ho, false);
    for (size_t i = 0; i < headings.size(); ++i) if (auto ho = source(headings[i][0])) {
        if (int(i) == page.category) party_image(ho, headings[i][1], 102, 35);
    }
    for (int i = page.begin; i < page.end; ++i) if (auto ho = source(icons[i][0])) {
        const int local = i - page.begin; party_image(ho, icons[i][2], 22 + local % 8 * 73, 64 + local / 8 * 72);
        party_filter(ho, icons[i][6].get<bool>() ? 0xffffff : 0x505050);
    }
    auto name = [&](int id) {
        const auto& names = p.view.at("names");
        return id > 0 && size_t(id) <= names.size() ? fwum::widen(names[id - 1].get<std::string>()) : std::wstring(L"Choose character");
    };
    text("title_a", L"TEAM A"); text("title_b", L"RESERVES");
    text("title", L"P" + std::to_wstring(player + 1) + L": EDIT YOUR SELECTED SLOT");
    text("pages", L"Roster page " + std::to_wstring(p.page + 1) + L" / " + std::to_wstring(p.page_count));
    const int focused = icons[p.cursor][1];
    text("preview", name(focused) + (unlocked(focused) ? L"   Lv. " + std::to_wstring(icons[p.cursor][5].get<int>()) : L"   LOCKED"), unlocked(focused) ? 0xffffff : 0xa0a0a0);
    if (families.contains(skin_key)) text("skin", L"C / Y  Skin: " + (appearance(player, base) == base ? std::wstring(L"Default") : name(appearance(player, base))), 0x5ad4ff);
    else if (auto ho = find(p.view.value("skin", -1))) party_visible(ho, false);
    text("prompt", p.feedback.empty() ? L"Click your P# slot, then a portrait. D-pad + A selects.\nB / R: your next slot. Q / E or LB / RB: category.\nReset clears YOUR slots. P1: Done / Start to play." : p.feedback, p.feedback.empty() ? 0xffffff : 0x5ad4ff);
    if (auto ho = find(p.view.value("cursor", -1))) party_visible(ho, false);
    for (int row = 1; row <= 8; ++row) {
        if (auto ho = find(c.ui.cards + row - 1)) party_text(ho,
            L"P" + std::to_wstring(owner(row) + 1) + L"  Slot " + std::to_wstring((row - 1) % 4 + 1) + L"\n" + name(p.characters[row - 1]),
            row == p.slot ? 0x5ad4ff : owner(row) == player ? 0xffffff : 0xb0b0b0);
        auto portrait = find(p.view.at("portraits")[row - 1]);
        const int character = p.characters[row - 1];
        auto icon = std::find_if(icons.begin(), icons.end(), [character](const Json& item) { return item[1].get<int>() == character; });
        if (portrait && icon != icons.end()) { party_image(portrait, (*icon)[2], 634, 44 + (row - 1) % 4 * 35 + (row > 4 ? 168 : 0), .42f, .42f); party_filter(portrait); }
        else if (portrait) party_visible(portrait, false);
        const int y = 42 + (row - 1) % 4 * 35 + (row > 4 ? 168 : 0);
        const int dimensions[4][4] = {{630,y,152,1},{630,y+33,152,1},{630,y,1,34},{781,y,1,34}};
        for (int edge = 0; edge < 4; ++edge) if (auto ho = find(p.view.at("borders")[(row - 1) * 4 + edge])) {
            const auto image = image_map().to_disk(common(ho)->rcImage);
            Img info{}; GetImageInfoEx(header()->rhIdAppli, common(ho)->rcImage, 0, 1, 1, &info);
            const auto& d = dimensions[edge];
            party_image(ho, image, d[0], d[1], float(d[2]) / std::max(1, int(info.imgWidth)), float(d[3]) / std::max(1, int(info.imgHeight)));
        }
    }
    p.cursor_character = focused;
    const int local = p.cursor - page.begin; p.cursor_x = 22 + local % 8 * 73 + 24; p.cursor_y = 64 + local / 8 * 72 - 22;
    if (auto ho = find(p.view.value("focus", -1))) { ho->hoX = p.cursor_x - 24; ho->hoY = p.cursor_y + 22; party_visible(ho, true); party_filter(ho); }
    if (auto ho = find(c.ui.previous)) { ho->hoX = 548; ho->hoY = 363; common(ho)->rcAngle = 90; party_visible(ho, true); party_filter(ho); }
    if (auto ho = find(c.ui.following)) { ho->hoX = 590; ho->hoY = 363; common(ho)->rcAngle = 90; party_visible(ho, true); party_filter(ho); }
    if (auto ho = find(c.ui.done)) party_visible(ho, player == 0);
    if (auto ho = find(c.ui.reset)) party_visible(ho, true);
    if (auto ho = find(p.view.value("back", -1))) party_visible(ho, player == 0);
}
void party_tick() {
    try { if (ctx().playing) party_online_tick(); else party_tick_legacy(); }
    catch (const std::exception& error) {
        log(std::string("party: ") + error.what());
        ctx().party.feedback = L"The party list could not be refreshed. Please reopen it.";
    }
}

bool cooperative_party() {
    auto& c = ctx(); if (c.frame != 3) return false;
    if (c.playing) return true;
    const int index = c.controls.players_global; auto app = header()->rhApp;
    if (index < 0 || index >= app->m_nGlobalValues) return false;
    const auto& value = app->m_pGlobalValues[index];
    return (value.m_type == TYPE_DOUBLE ? value.m_double : value.m_long) > 1;
}
std::vector<LPHO> control_objects() {
    std::vector<LPHO> result; auto& c = ctx(); auto rh = header();
    for (auto ho : objects()) if (c.controls.targets.count(ho->hoOi) && renderable(ho) &&
            !(sprite(ho)->rsFlags & RSFLAG_HIDDEN) && ho->hoImgWidth > 0 && ho->hoImgHeight > 0 &&
            ho->hoX - ho->hoImgXSpot >= rh->rhWindowX - 8 && ho->hoY - ho->hoImgYSpot >= rh->rhWindowY - 8 &&
            ho->hoX - ho->hoImgXSpot < rh->rhWindowX + rh->rh3.rh3WindowSx &&
            ho->hoY - ho->hoImgYSpot < rh->rhWindowY + rh->rh3.rh3WindowSy) result.push_back(ho);
    std::sort(result.begin(), result.end(), [](auto a, auto b) {
        return a->hoY == b->hoY ? a->hoX < b->hoX : a->hoY < b->hoY;
    });
    return result;
}
bool controls_active() {
    auto& c = ctx();
    const int player = c.playing ? c.slot : 0;
    return !cooperative_party() && !c.controls.targets.empty() && c.controls.focus[player] &&
        (!c.controls.world || (c.controls.open[player] && !(c.hosting || !c.playing ? c.in_battle : c.remote_battle)));
}
unsigned controls_consumed_mask() {
    auto& c = ctx(); auto& ui = c.controls;
    if (cooperative_party() || ui.targets.empty() || (ui.world && (c.hosting || !c.playing ? c.in_battle : c.remote_battle))) return 0;
    int keyboard = 0; auto app = header()->rhApp;
    if (!c.playing && ui.keyboard_global >= 0 && ui.keyboard_global < app->m_nGlobalValues)
        keyboard = int(app->m_pGlobalValues[ui.keyboard_global].m_long);
    unsigned result = 0;
    for (int player = 0; player < 4; ++player) if (ui.focus[player] && (!ui.world || ui.open[player])) {
        const int controller = c.playing ? player : player - keyboard;
        if (controller >= 0 && controller < 4) result |= 1u << controller;
    }
    return result;
}
Pad controls_pad(Pad pad, int player) {
    auto& c = ctx(); auto& ui = c.controls;
    if (cooperative_party() || ui.targets.empty() || player < 0 || player > 3) return pad;
    if (ui.world) {
        const bool battle = c.hosting || !c.playing ? c.in_battle : c.remote_battle;
        if (battle) { ui.focus[player] = 0; ui.open[player] = false; return pad; }
        const WORD pressed = pad.buttons & ~ui.previous[player];
        if (pressed & XINPUT_GAMEPAD_START) {
            ui.open[player] = !ui.open[player]; ui.focus[player] = 0;
            if (ui.open[player]) {
                const auto choices = control_objects();
                auto at = std::find_if(choices.begin(), choices.end(), [&](auto ho) { return ho->hoOi == ui.preferred; });
                if (!choices.empty()) ui.focus[player] = fixed(at == choices.end() ? choices.front() : *at);
            }
        }
        if (pressed & XINPUT_GAMEPAD_B) { ui.open[player] = false; ui.focus[player] = 0; }
        if (!ui.open[player] && !(pad.buttons & fwum::mouse_target_button)) { ui.previous[player] = pad.buttons; return pad; }
    }
    const auto targets = control_objects();
    auto target = [&](uint32_t id) -> LPHO { for (auto ho : targets) if (fixed(ho) == id) return ho; return nullptr; };
    LPHO preferred = nullptr;
    for (const auto oi : ui.preferences) {
        const auto at = std::find_if(targets.begin(), targets.end(), [oi](auto ho) { return ho->hoOi == oi; });
        if (at != targets.end()) { preferred = *at; break; }
    }
    if (ui.automatic && preferred && fixed(preferred) != ui.last_preferred[player] &&
            (!ui.moved[player] || !target(ui.focus[player]))) ui.focus[player] = fixed(preferred);
    ui.last_preferred[player] = preferred ? fixed(preferred) : 0;
    if (!target(ui.focus[player])) {
        ui.focus[player] = 0;
        ui.moved[player] = false;
        if (ui.automatic && !targets.empty() && (preferred || ui.preferences.empty())) {
            auto at = preferred ? std::find(targets.begin(), targets.end(), preferred) :
                std::find_if(targets.begin(), targets.end(), [&](auto ho) { return ho->hoOi == ui.preferred; });
            if (at == targets.end()) at = std::find_if(targets.begin(), targets.end(), [&](auto ho) { return ho->hoOi != ui.back; });
            ui.focus[player] = fixed(at == targets.end() ? targets.front() : *at);
        }
    }
    WORD down = pad.buttons;
    if (!(down & fwum::mouse_target_button)) {
        if (pad.lx < -7000) down |= XINPUT_GAMEPAD_DPAD_LEFT;
        if (pad.lx > 7000) down |= XINPUT_GAMEPAD_DPAD_RIGHT;
        if (pad.ly > 7000) down |= XINPUT_GAMEPAD_DPAD_UP;
        if (pad.ly < -7000) down |= XINPUT_GAMEPAD_DPAD_DOWN;
    }
    const WORD pressed = down & ~ui.previous[player], direction = down & 15;
    const auto now = GetTickCount64();
    if ((!ui.host_only || player == 0) && ui.editing && !(down & fwum::mouse_target_button)) {
        auto knob = target(ui.editing);
        if (!knob || (pressed & (XINPUT_GAMEPAD_A | XINPUT_GAMEPAD_B))) ui.editing = 0;
        else if (direction && (direction != ui.repeating[player] || now >= ui.repeat_at[player])) {
            ui.slider_x = knob->hoX + (direction & XINPUT_GAMEPAD_DPAD_LEFT ? -2 :
                direction & XINPUT_GAMEPAD_DPAD_RIGHT ? 2 : 0);
            ui.repeat_at[player] = now + 40; ui.repeating[player] = direction;
        }
        if (!direction) ui.repeating[player] = 0;
        ui.previous[player] = down;
        return pad;
    }
    if (down & fwum::mouse_target_button) ui.editing = 0;
    if ((!ui.host_only || player == 0) && (pressed & XINPUT_GAMEPAD_A)) {
        auto focused = target(ui.focus[player]);
        if (focused && (focused->hoOi == ui.slider_knob || focused->hoOi == ui.slider_track)) {
            auto knob = focused;
            if (focused->hoOi == ui.slider_track) {
                knob = nullptr;
                for (auto candidate : targets) if (candidate->hoOi == ui.slider_knob &&
                    (!knob || std::abs(candidate->hoY - focused->hoY) < std::abs(knob->hoY - focused->hoY))) knob = candidate;
            }
            if (knob) {
                ui.editing = ui.focus[player] = fixed(knob); ui.slider_x = knob->hoX;
                ui.previous[player] = down; ui.repeating[player] = 0; return pad;
            }
        }
    }
    if (direction && (direction != ui.repeating[player] || now >= ui.repeat_at[player])) {
        ui.moved[player] = true;
        std::vector<fwum::FocusTarget> points;
        for (auto ho : targets) points.push_back({fixed(ho), float(ho->hoX - ho->hoImgXSpot + ho->hoImgWidth / 2),
            float(ho->hoY - ho->hoImgYSpot + ho->hoImgHeight / 2)});
        const int dx = direction & XINPUT_GAMEPAD_DPAD_LEFT ? -1 : direction & XINPUT_GAMEPAD_DPAD_RIGHT ? 1 : 0;
        const int dy = direction & XINPUT_GAMEPAD_DPAD_UP ? -1 : direction & XINPUT_GAMEPAD_DPAD_DOWN ? 1 : 0;
        ui.focus[player] = fwum::move_focus(points, ui.focus[player], dx, dy);
        ui.repeat_at[player] = now + (direction == ui.repeating[player] ? 140 : 350); ui.repeating[player] = direction;
    }
    if (!direction) ui.repeating[player] = 0;
    uint32_t clicked = 0;
    if (ui.focus[player] && (pressed & XINPUT_GAMEPAD_A)) clicked = ui.focus[player];
    if (pressed & XINPUT_GAMEPAD_B) {
        auto back = std::find_if(targets.begin(), targets.end(), [&](auto ho) { return ho->hoOi == ui.back; });
        if (back != targets.end()) clicked = fixed(*back);
        else if (!ui.automatic) ui.focus[player] = 0;
    }
    if ((down & fwum::mouse_target_button) && !(ui.previous[player] & fwum::mouse_target_button)) {
        if (c.playing && !c.hosting) {
            const auto mapped = c.mapping.find(fwum::mouse_target(pad.lx, pad.ly));
            if (mapped != c.mapping.end()) for (auto local : targets) if (fixed(local) == mapped->second) { clicked = fixed(local); break; }
        } else if (auto ho = mouse_object(pad); ho && ui.targets.count(ho->hoOi)) clicked = fixed(ho);
        if (clicked) { ui.focus[player] = clicked; ui.moved[player] = true; }
    }
    ui.previous[player] = down;
    if (!c.playing || c.hosting) {
        ui.clicks[player] = clicked;
        return pad;
    }
    if (clicked && (!ui.host_only || player == 0)) {
        const auto mapped = std::find_if(c.mapping.begin(), c.mapping.end(), [clicked](const auto& item) { return item.second == clicked; });
        if (mapped != c.mapping.end()) ui.pending_click = mapped->first;
    }
    if (!ui.focus[player]) return pad; // NPC confirm remains available until D-pad focus is requested.
    pad.buttons = 0; pad.lx = pad.ly = 0;
    if (ui.pending_click) {
        pad.buttons = fwum::mouse_target_button; pad.lx = fwum::mouse_target_low(ui.pending_click); pad.ly = fwum::mouse_target_high(ui.pending_click);
    }
    return pad;
}
void bound_buttons_tick() {
    auto& c = ctx(); auto& ui = c.controls;
    if (ui.bound_buttons.empty() || (c.playing && !c.hosting)) return;
    int keyboard = 0;
    const auto app = header()->rhApp;
    if (!c.playing && ui.keyboard_global >= 0 && ui.keyboard_global < app->m_nGlobalValues) {
        const auto& value = app->m_pGlobalValues[ui.keyboard_global];
        keyboard = value.m_type == TYPE_DOUBLE ? int(value.m_double) : int(value.m_long);
    }
    std::array<Pad, 4> pads{};
    for (int player = 0; player < 4; ++player) pads[player] = c.playing ? c.pads[player] : physical_pad(player - keyboard, player == 0);
    for (auto& pad : pads) if (!(pad.buttons & fwum::mouse_target_button)) {
        if (pad.lx < -7000) pad.buttons |= XINPUT_GAMEPAD_DPAD_LEFT;
        if (pad.lx > 7000) pad.buttons |= XINPUT_GAMEPAD_DPAD_RIGHT;
        if (pad.ly > 7000) pad.buttons |= XINPUT_GAMEPAD_DPAD_UP;
        if (pad.ly < -7000) pad.buttons |= XINPUT_GAMEPAD_DPAD_DOWN;
    }
    for (auto ho : objects()) for (const auto& binding : ui.bound_buttons) if (ho->hoOi == binding[0]) {
        const int player = binding[1]; if (player < 0 || player > 3) continue;
        auto state = values(ho); if (!state) continue;
        const WORD bit = WORD(binding[2]);
        const bool held = pads[player].buttons & bit;
        const bool pressed = held && !(ui.bound_previous[player] & bit);
        state->rvValueFlags = (state->rvValueFlags & ~3u) | unsigned(held) | (unsigned(pressed) << 1);
    }
    for (int player = 0; player < 4; ++player) ui.bound_previous[player] = pads[player].buttons;
}
void controls_tick() {
    auto& c = ctx(); auto& ui = c.controls; ui.clicks.fill(0); ui.connected.fill(false);
    if (cooperative_party() || ui.targets.empty()) return;
    if (c.playing) {
        ui.connected[c.slot] = true;
        if (!c.hosting) return;
        controls_pad(c.pads[0], 0);
        for (int player = 1; player < c.players; ++player) {
            const auto& input = c.pads[player];
            if ((input.buttons & fwum::mouse_target_button) && !(c.previous_pads[player].buttons & fwum::mouse_target_button)) {
                auto ho = mouse_object(input);
                if (ho && ui.targets.count(ho->hoOi)) ui.clicks[player] = fixed(ho);
            }
        }
    } else {
        int keyboard = 0; const int index = ui.keyboard_global; auto app = header()->rhApp;
        if (index >= 0 && index < app->m_nGlobalValues) {
            const auto& value = app->m_pGlobalValues[index]; keyboard = value.m_type == TYPE_DOUBLE ? int(value.m_double) : int(value.m_long);
        }
        for (int player = 0; player < 4; ++player) {
            const auto input = physical_pad(player - keyboard, player == 0);
            if (player && !input.seen) { ui.focus[player] = 0; continue; }
            ui.connected[player] = true; controls_pad(input, player);
        }
    }
    if (ui.editing) for (auto knob : objects()) if (fixed(knob) == ui.editing && knob->hoOi == ui.slider_knob) {
        auto state = values(knob);
        if (!state || !readable(state->rvpValues, sizeof(CValue))) break;
        state->rvpValues[0].m_type = TYPE_INT; state->rvpValues[0].m_long = knob->hoX;
        state->rvValueFlags |= 1;
        ui.saved_mouse = header()->rh2.rh2Mouse; ui.mouse_overridden = true;
        header()->rh2.rh2Mouse.x = ui.slider_x;
        break;
    }
}
long clicked_control(int oi) {
    auto& c = ctx(); auto& ui = c.controls;
    if (!ui.targets.count(oi)) return 0;
    for (int player = 0; player < 4; ++player) if (!ui.host_only || player == 0) {
        const auto id = ui.clicks[player]; const unsigned number = uint16_t(id);
        if (!id || number >= unsigned(header()->rhMaxObjects)) continue;
        auto ho = header()->rhObjectList[number].oblOffset;
        if (ho && !(ho->hoFlags & HOF_DESTROYED) && fixed(ho) == id && ho->hoOi == oi) return long(id);
    }
    return 0;
}
void controls_draw() {
    auto& c = ctx(); auto& ui = c.controls;
    if (ui.targets.empty()) return;
    const auto all = objects(); const unsigned colours[] = {0x5ad4ff, 0xffb56b, 0x8fffa0, 0xd290ff};
    for (auto ho : all) {
        if (ho->hoOi == ui.hint) party_text(ho, ui.editing ? L"Left / Right: adjust    A / B: done" :
            fwum::widen(c.party.view.value("hint_text", "D-pad: choose    A: select / edit    B: back")), 0xffffff);
        if (ho->hoOi == c.party.view.value("night_back", -1)) party_text(ho, L"Back to world", 0xffffff);
    }
    for (int player = 0; player < 4; ++player) {
        auto marker = std::find_if(all.begin(), all.end(), [&](auto ho) { return ho->hoOi == ui.markers[player]; });
        if (marker == all.end()) continue;
        auto target = std::find_if(all.begin(), all.end(), [&](auto ho) { return ui.focus[player] && fixed(ho) == ui.focus[player]; });
        if (!ui.connected[player] || (ui.world && !ui.open[player]) || target == all.end() || (sprite(*target)->rsFlags & RSFLAG_HIDDEN)) { party_visible(*marker, false); continue; }
        (*marker)->hoX = std::max(header()->rhWindowX, (*target)->hoX - (*target)->hoImgXSpot - 27);
        (*marker)->hoY = (*target)->hoY - (*target)->hoImgYSpot + (*target)->hoImgHeight / 2 - 12;
        party_text(*marker, std::to_wstring(player + 1) + L">", colours[player]);
    }
}

short WINAPI finish(LPHO, long, long) {
    auto& c = ctx();
    BusyScope guard(c.engine_busy);
    if (c.controls.mouse_overridden) {
        header()->rh2.rh2Mouse = c.controls.saved_mouse; c.controls.mouse_overridden = false;
    }
    if (c.hosting || !c.playing) { party_tick(); controls_draw(); }
    c.previous_pads = c.pads; c.previous_keyboard_pad = c.keyboard_pad;
    if (!c.state_file.empty() && GetTickCount64() - c.diagnostics_at >= 250) {
        c.diagnostics_at = GetTickCount64();
        try {
            const auto packet = fwum::encode(capture(true));
            const auto temporary = c.state_file + L".tmp";
            std::ofstream out(fwum::narrow(temporary), std::ios::binary | std::ios::trunc);
            out.write(reinterpret_cast<const char*>(packet.data()), packet.size()); out.close();
            if (out) MoveFileExW(temporary.c_str(), c.state_file.c_str(), MOVEFILE_REPLACE_EXISTING);
            const auto metadata = c.state_file + L".diagnostics";
            const auto pending = metadata + L".tmp";
            std::ofstream detail(fwum::narrow(pending), std::ios::trunc);
            detail << Json{{"frame", c.frame}, {"playing", c.playing}, {"hosting", c.hosting},
                {"connected", c.connected}, {"reconnecting", c.reconnecting},
                {"players", c.players}, {"co_op_players", c.co_op_players}, {"in_battle", c.in_battle},
                {"individual_battle", c.individual_battle}, {"teams", c.battle_teams},
                {"turn_slot", c.battle_slot}, {"turn_owner", c.co_op_owner},
                {"party_page", c.party.page + 1}, {"party_cursor", c.party.cursor}, {"party_slot", c.party.slot},
                {"party_pending", c.party.pending}, {"party_feedback", fwum::narrow(c.party.feedback)},
                {"menu_focus", c.controls.focus}, {"menu_open", c.controls.open},
                {"menu_preferences", c.controls.preferences}, {"menu_previous", c.controls.previous},
                {"menu_moved", c.controls.moved}, {"menu_preferred", c.controls.last_preferred},
                {"sent_buttons", c.sent_pad.buttons}, {"sent_epoch", c.sent_epoch}, {"epoch", c.party.epoch},
                {"input_focused", c.input_focused}, {"waiting_for_release", c.input_latches[0].waiting},
                {"input_buttons", {c.pads[0].buttons,c.pads[1].buttons,c.pads[2].buttons,c.pads[3].buttons}},
                {"health_ready", c.battle_health.ready()}, {"health", c.battle_health.values()},
                {"living", c.battle_health.living()}, {"replacement", c.battle_health.replacement(c.battle_teams)}}.dump();
            detail.close();
            if (detail) MoveFileExW(pending.c_str(), metadata.c_str(), MOVEFILE_REPLACE_EXISTING);
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
        const ULONGLONG interval = c.frame == 3 ? 100 : active_input || battle ? 50 : 100;
        if (c.hosting && c.connected && !c.reconnecting && c.players > 1 && (c.force_state || GetTickCount64() - c.state_at >= interval)) {
            c.force_state = false;
            c.state_at = GetTickCount64(); auto state = capture();
            if (state.sequence % 60 == 0) log("captured " + std::to_string(state.entities.size()) + " objects");
            c.connection->send_world(fwum::encode(state));
        } else if (!c.hosting) { apply(); apply_positions(); party_tick(); controls_draw(); }
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
    condition<15>, condition<16>, condition<17>, condition<18>, condition<19>, condition<20>, condition<21>, condition<22>, condition<23>, condition<24>, condition<25>, condition<26>, condition<27>, condition<28>, condition<29>, condition<30>, condition<31>, condition<32>, condition<33>};
ActFn actions[] = {begin, finish, created, clear_exit, report_audio, report_counter, report_shader, report_shader_param, report_colour,
    configure_combat, switch_character, configure_party, configure_health, fit_character};
ExpFn expressions[] = {expression<0>, expression<1>, expression<2>, expression<3>, expression<4>, expression<5>, expression<6>, expression<7>, expression<8>, expression<9>, expression<10>, expression<11>, expression<12>, expression<13>, expression<14>, expression<15>, expression<16>, expression<17>, expression<18>, expression<19>, expression<20>, expression<21>, expression<22>, expression<23>, expression<24>, expression<25>, expression<26>, expression<27>, expression<28>, expression<29>, expression<30>, expression<31>, expression<32>, expression<33>, expression<34>, expression<35>, expression<36>, expression<37>, expression<38>, expression<39>, expression<40>, expression<41>, expression<42>, expression<43>};
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
        (game_focused() || GetForegroundWindow() == c.window || IsChild(c.window, GetForegroundWindow()));
    if (down && !c.key_down) {
        if (c.window && IsWindowVisible(c.window)) ShowWindow(c.window, SW_HIDE); else menu();
    }
    c.key_down = down;
    const bool controller_start = (controller_pad(0).buttons & XINPUT_GAMEPAD_START) != 0;
    const bool online_chord = (controller_pad(0).buttons & XINPUT_GAMEPAD_BACK) != 0;
    if (controller_start && !c.lobby_navigation.start_down && (online_chord || (c.frame != 3 && !c.controls.world)) && game_focused() &&
            !(c.window && IsWindowVisible(c.window))) menu();
    c.lobby_navigation.start_down = controller_start;
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
    info->numOfConditions = 34; info->numOfActions = 14; info->numOfExpressions = 44;
    info->editFlags = OEFLAG_NEVERSLEEP | OEFLAG_NEVERKILL; info->identifier = 0x4e4d5746; return TRUE;
}
}
