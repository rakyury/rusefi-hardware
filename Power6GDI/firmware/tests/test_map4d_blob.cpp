#include "map4d_blob.h"
#include <cassert>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <vector>

using power8gdi::Map4DBlob;
static void u16(std::vector<std::uint8_t>& a, std::size_t offset, std::uint16_t n) {
    a.at(offset)=n&255;
    a.at(offset+1)=(n>>8)&255;
}
static void u32(std::vector<std::uint8_t>& a, std::size_t offset, std::uint32_t n) {
    u16(a, offset, n&65535);u16(a, offset+2, (n>>16)&65535);
}
static void f32(std::vector<std::uint8_t>& a, std::size_t off,float v) {
    std::uint32_t n;
    std::memcpy(&n,&v,4);u32(a,off,n);
}
static std::uint32_t crc32(const std::uint8_t* p, std::size_t size) {
    std::uint32_t crc=0xffffffff;
    for (std::size_t i=0;i<size;++i) {
        crc ^= p[i];
        for(int b=0;b<8;++b) crc = (crc>>1) ^ ((crc & 1) ? 0xedb88320u : 0u);
    }
    return ~crc;
}
static std::vector<std::uint8_t> good() {
    const int cells=8;
    std::vector<std::uint8_t> a(48+24+cells*2,0);
    a[0]='P';a[1]='4';a[2]='D';a[3]='M';
    u16(a,4,1);u16(a,6,48);u16(a,8,2);u16(a,10,2);u16(a,12,2);
    f32(a,16,0.01f);f32(a,20,0.f);f32(a,24,-20.f);f32(a,28,40.f);
    u32(a,32,24+cells*2);
    const float bins[]={0.f,100.f,1000.f,3000.f,0.f,85.f};
    for(int i=0;i<6;++i) f32(a,48+i*4,bins[i]);
    const int16_t v[]={100,1100,300,1300,2100,3100,2300,3300};
    for(int i=0;i<cells;++i)u16(a,72+i*2,static_cast<std::uint16_t>(v[i]));
    u32(a,36,crc32(a.data()+48, a.size()-48));
    return a;
}
int main(){
    Map4DBlob b;
    float result=1234.f;
    auto a=good();
    assert(b.load(a.data(),a.size()));
    assert(b.ready()&&b.cellCount()==8);
    assert(b.evaluate(50,2000,42.5f,result));
    assert(std::fabs(result-17.f)<1e-4f);
    assert(b.evaluate(-1,1000,-1,result)&&std::fabs(result-1.f)<1e-5f);
    assert(b.evaluate(999,9999,999,result)&&std::fabs(result-33.f)<1e-4f);
    result=1234.f;
    assert(!b.evaluate(NAN,2000,2,result) && result==1234.f);
    for(std::size_t pos: {0u,4u,14u,40u,72u,87u}){
        auto broken=a;broken[pos]^=0x80;
        assert(!b.load(broken.data(),broken.size()));
        assert(!b.ready());
        assert(!b.evaluate(50,2000,50,result));
    }
    auto broken=a;broken.pop_back();assert(!b.load(broken.data(),broken.size()));
    broken=a;broken.push_back(0);assert(!b.load(broken.data(),broken.size()));
    broken=a;u16(broken,10,0);assert(!b.load(broken.data(),broken.size()));
    // Valid CRC but invalid monotonic axis
    broken=a;f32(broken,52,0.f);u32(broken,36,crc32(broken.data()+48,broken.size()-48));
    assert(!b.load(broken.data(),broken.size()));
    // Physical bounds invalid after CRC updated
    broken=a;u16(broken,72,32000);u32(broken,36,crc32(broken.data()+48,broken.size()-48));
    assert(!b.load(broken.data(),broken.size()));
}
