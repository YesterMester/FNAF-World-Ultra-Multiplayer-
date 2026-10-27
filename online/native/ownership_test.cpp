#include "ownership.hpp"
#include <cassert>
#include <iostream>

int main() {
    fwum::BattleOwners owners;
    const std::vector<std::string> two{"host", "guest"};
    owners.begin(two);
    assert(owners.owner(1, two) == 0 && owners.owner(2, two) == 1);
    assert(owners.owner(3, two) == 0 && owners.owner(4, two) == 1);
    const std::vector<std::string> joined{"host", "guest", "newcomer"};
    assert(owners.owner(3, joined) == 0 && owners.owner(4, joined) == 1);
    owners.begin(joined);
    const std::vector<std::string> left{"host", "newcomer"};
    assert(owners.owner(2, left) == 0); // host takes an abandoned turn
    assert(owners.owner(3, left) == 1); // remaining member still owns their actor
    assert(owners.owner(4, left) == 0);
    assert(owners.owner(2, joined) == 1); // the same identity can resume
    owners.begin({"host", "b", "c", "d"});
    assert(owners.owner(4, {"host", "d"}) == 1);
    assert(owners.owner(0, joined) == 0 && owners.owner(5, joined) == 0);
    owners.clear();
    assert(owners.owner(1, joined) == 0);
    fwum::BattleHealth hp;
    assert(hp.living() == -1 && hp.replacement(0) == 0);
    for (int slot = 1; slot <= 4; ++slot) hp.set(slot, 0, 20, 100, 100);
    assert(hp.living() == 4 && hp.replacement(0) == 1);
    assert(hp.replacement(1) == 2 && hp.replacement(15) == 0);
    hp.set(1, 5, -2, 100, 100);
    assert(hp.replacement(15) == 1);
    hp.begin_tick();
    hp.set(1, 0, 0, 100, 100);
    assert(hp.living() == -1); // a partial tick cannot declare defeat
    for (int slot = 2; slot <= 4; ++slot) hp.set(slot, -1, 0, 100, 100);
    assert(hp.living() == 0);
    hp.set(1, .5, 0, 100, 100);
    assert(hp.living() == 1 && hp.replacement(0) == 0);
    std::cout << "battle ownership: joins, departures and resumed identities passed\n";
}
