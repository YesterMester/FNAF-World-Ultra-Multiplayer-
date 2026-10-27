#include "snapshot.hpp"
#include <cassert>
#include <limits>
#include <iostream>
int main() {
    fwum::Snapshot s; s.frame = 4; s.sequence = 52; s.camera_x = 700;
    s.epoch = 17;
    s.layers.push_back({100, 200, 16});
    fwum::Entity freddy; freddy.id = 123; freddy.oi = 317; freddy.x = 800; freddy.y = 250;
    freddy.image = 901; freddy.scale_x = .75f; freddy.value = 9.5; freddy.text = u"P2: Freddy \u2605";
    freddy.z = 42; freddy.sprite_layer = 3;
    freddy.minimum = -10; freddy.maximum = 200; freddy.floating = true; freddy.colour = 0x123456;
    freddy.shader = 3; freddy.shader_params.push_back({2, 700.5f});
    freddy.hotspot_x = 375; freddy.hotspot_y = 225; freddy.display_width = 800; freddy.display_height = 480;
    s.entities.push_back(freddy);
    s.music.push_back({48, 32771, 75, true});
    s.party = R"({"epoch":12,"characters":[1,1,3,4,5,6,7,8],"versions":[2,3,0,0,0,0,0,0]})";
    auto data = fwum::encode(s); auto result = fwum::decode(data);
    auto old_format = data; old_format[1] = 5;
    bool old_rejected = false;
    try { fwum::decode(old_format); } catch (const std::runtime_error&) { old_rejected = true; }
    assert(old_rejected);
    assert(result.frame == 4 && result.sequence == 52 && result.camera_x == 700);
    assert(result.party == s.party && result.epoch == 17);
    assert(result.entities[0].image == 901 && result.entities[0].value == 9.5 && result.entities[0].text == freddy.text);
    assert(result.layers[0].x == 100 && result.layers[0].flags == 16);
    assert(result.entities[0].z == 42 && result.entities[0].sprite_layer == 3);
    assert(result.entities[0].minimum == -10 && result.entities[0].maximum == 200 && result.entities[0].floating);
    assert(result.entities[0].colour == 0x123456);
    assert(result.entities[0].shader == 3 && result.entities[0].shader_params[0].second == 700.5f);
    assert(result.entities[0].hotspot_x == 375 && result.entities[0].display_width == 800);
    assert(result.music[0].channel == 48 && result.music[0].callback == 32771 &&
        result.music[0].volume == 75 && result.music[0].paused);
    for (size_t i = 0; i < data.size(); ++i) {
        bool rejected = false;
        try { fwum::decode(std::vector<uint8_t>(data.begin(), data.begin() + i)); }
        catch (const std::runtime_error&) { rejected = true; }
        assert(rejected);
    }
    s.entities[0].scale_x = std::numeric_limits<float>::quiet_NaN();
    bool rejected = false;
    try { fwum::decode(fwum::encode(s)); } catch (const std::runtime_error&) { rejected = true; }
    assert(rejected);
    s.entities[0].scale_x = 1;
    s.entities[0].effect = 0x200d; // Only an effect kind and scalar RGBA may be received.
    rejected = false;
    try { fwum::decode(fwum::encode(s)); } catch (const std::runtime_error&) { rejected = true; }
    assert(rejected);
    s.entities[0].effect = 0x1009; s.entities[0].effect_param = 0x00ffffff; // Transparent HWA overlay.
    assert(fwum::decode(fwum::encode(s)).entities[0].effect_param == 0x00ffffff);
    s.music.push_back(s.music[0]);
    rejected = false;
    try { fwum::decode(fwum::encode(s)); } catch (const std::runtime_error&) { rejected = true; }
    assert(rejected);
    std::cout << "snapshot round trip, UTF-16 text, all truncated packets, and invalid numbers passed\n";
}
