#include "navigation.hpp"
#include <cassert>
#include <iostream>
int main() {
    const std::vector<fwum::FocusTarget> grid{{1,10,10},{2,100,10},{3,10,80},{4,100,80},{5,10,150},{6,100,150}};
    assert(fwum::move_focus(grid,1,1,0)==2);
    assert(fwum::move_focus(grid,1,0,1)==3);
    assert(fwum::move_focus(grid,3,0,1)==5);
    assert(fwum::move_focus(grid,1,-1,0)==2);
    assert(fwum::move_focus(grid,1,0,-1)==5);
    assert(fwum::move_focus(grid,999,0,1)==1);
    assert(fwum::move_focus({},1,1,0)==0);
    assert(fwum::move_focus({{7,20,30}},7,1,0)==7);
    assert(fwum::move_focus({{1,0,0},{2,2,60},{3,80,1}},1,0,1)==2);
    std::cout << "menu navigation: rows, columns, wrapping, removed controls and empty screens passed\n";
}
