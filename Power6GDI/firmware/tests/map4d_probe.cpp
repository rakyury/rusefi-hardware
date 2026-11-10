// Host-only cross-language fixture writer and production-reader probe.
// The writer is deliberately independent of the Python serializer.
#include "map4d_blob.h"
#include <cstring>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <iterator>
#include <string>
#include <vector>

using Bytes = std::vector<std::uint8_t>;
static void append16(Bytes& b, std::uint16_t v) {
    b.push_back(v & 255); b.push_back((v >> 8) & 255);
}
static void append32(Bytes& b, std::uint32_t v) {
    append16(b, v & 65535); append16(b, (v >> 16) & 65535);
}
static void appendFloat(Bytes& b, float v) {
    std::uint32_t u; std::memcpy(&u, &v, 4); append32(b, u);
}
static Bytes fixture() {
    Bytes payload;
    for (float f : {-100.f, 0.f, 250.f, 1000.f, 3000.f, -20.f, 80.f}) appendFloat(payload, f);
    for (int v : {-20, 0, 12, 24, 44, 60, 80, 100, 120, 140, 160, 200})
        append16(payload, static_cast<std::uint16_t>(v));
    std::uint32_t crc = 0xffffffffu;
    for (auto byte : payload) {
        crc ^= byte;
        for (int bit = 0; bit < 8; ++bit)
            crc = (crc >> 1) ^ ((crc & 1) ? 0xedb88320u : 0u);
    }
    Bytes bytes{'P','4','D','M'};
    for (int v : {1, 48, 3, 2, 2, 0}) append16(bytes, v);
    for (float v : {.25f, -3.5f, -10.f, 50.f}) appendFloat(bytes, v);
    append32(bytes, static_cast<std::uint32_t>(payload.size())); append32(bytes, ~crc);
    append32(bytes, 0); append32(bytes, 0);
    bytes.insert(bytes.end(), payload.begin(), payload.end());
    return bytes;
}

int main(int argc, char** argv) {
    if (argc == 2 && std::string(argv[1]) == "fixture") {
        for (auto byte : fixture()) std::cout << std::hex << std::setfill('0') << std::setw(2) << unsigned(byte);
        std::cout << '\n'; return 0;
    }
    if (argc != 5) return 2;
    std::ifstream file(argv[1], std::ios::binary);
    if (!file) return 3;
    Bytes bytes((std::istreambuf_iterator<char>(file)), {});
    power8gdi::Map4DBlob map;
    if (!map.load(bytes.data(), bytes.size())) {
        float result = 1234.f;
        if (map.ready() || map.cellCount() || map.evaluate(0,0,0,result) || result != 1234.f) return 4;
        std::cout << "REJECT\n"; return 0;
    }
    float output = 1234.f;
    if (!map.evaluate(std::stof(argv[2]), std::stof(argv[3]), std::stof(argv[4]), output)) {
        if (output != 1234.f) return 5;
        std::cout << "INVALID_INPUT\n"; return 0;
    }
    std::cout << "OK " << map.cellCount() << ' ' << std::setprecision(9) << output << '\n';
}
