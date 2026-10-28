#pragma once
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <limits>
#include <memory>
#include <unordered_map>
#include <unordered_set>
#include <vector>

namespace gasf {
constexpr double PI = 3.1415926535897932384626433832795;
struct Voxel {
  int32_t x=0, y=0, z=0;
  bool operator==(const Voxel& b) const noexcept {return x==b.x && y==b.y && z==b.z;}
};
struct VoxelHash {
  size_t operator()(const Voxel& v) const noexcept {
    uint64_t h=1469598103934665603ULL;
    for (int32_t n: {v.x,v.y,v.z}) {
      h ^= static_cast<uint32_t>(n);
      h *= 1099511628211ULL;
    }
    return static_cast<size_t>(h);
  }
};
inline Voxel make_voxel(float x, float y, float z, double size) {
  return {static_cast<int32_t>(std::floor(x / size)),
          static_cast<int32_t>(std::floor(y / size)),
          static_cast<int32_t>(std::floor(z / size))};
}
using Mask = std::unordered_set<Voxel, VoxelHash>;
struct Quaternion {
  double w=1, x=0, y=0, z=0;
  void normalize() {
    const double n=std::sqrt(w*w+x*x+y*y+z*z);
    if(n>1e-15){w/=n;x/=n;y/=n;z/=n;}
  }
  Quaternion operator*(const Quaternion& b) const {
    return {w*b.w-x*b.x-y*b.y-z*b.z,
            w*b.x+x*b.w+y*b.z-z*b.y,
            w*b.y-x*b.z+y*b.w+z*b.x,
            w*b.z+x*b.y-y*b.x+z*b.w};
  }
  static Quaternion gyro_step(double wx, double wy, double wz, double dt) {
    const double rate=std::sqrt(wx*wx+wy*wy+wz*wz);
    if(rate<1e-12 || dt<=0) return {};
    const double a=rate*dt/2;
    const double s=std::sin(a)/rate;
    return {std::cos(a),wx*s,wy*s,wz*s};
  }
  static double distance(const Quaternion& a, const Quaternion& b) {
    double dot=std::abs(a.w*b.w+a.x*b.x+a.y*b.y+a.z*b.z);
    return 2*std::acos(std::clamp(dot,0.0,1.0));
  }
};
struct Observation {
  std::vector<Voxel> voxels;
  Quaternion orientation;
  bool imu_ready=false;
};
struct LearnerConfig {
  int min_hits=8;
  int min_orientations=3;
  int stale_frames=250;
  int max_bins=60;
  double orientation_step_deg=6.0;
};
class OnlineLearner {
public:
  explicit OnlineLearner(LearnerConfig c):c_(c){}
  void update(const Observation& obs) {
    ++frame_;
    const int bin=obs.imu_ready? get_orientation_bin(obs.orientation) : -1;
    for(const auto &v: obs.voxels){
      auto &s=counts_[v];
      if(s.last_seen_frame==frame_) continue;
      s.hits=std::min(s.hits+1,1000000);
      s.last_seen_frame=frame_;
      if(bin>=0) s.bins |= (1ULL << bin);
    }
    if(frame_%25 == 0){
      for(auto it=counts_.begin();it!=counts_.end();){
        if(frame_-it->second.last_seen_frame > static_cast<uint64_t>(c_.stale_frames)) it=counts_.erase(it);
        else ++it;
      }
    }
  }
  std::shared_ptr<const Mask> confirmed() const {
    auto m=std::make_shared<Mask>();
    for(const auto &kv: counts_){
      const auto &s=kv.second;
      if(s.hits>=c_.min_hits && popcount(s.bins)>=c_.min_orientations &&
         frame_-s.last_seen_frame <= static_cast<uint64_t>(c_.stale_frames))
        m->insert(kv.first);
    }
    return m;
  }
  size_t candidate_count() const {return counts_.size();}
  uint64_t processed_frames() const{return frame_;}
  size_t orientation_bins() const{return orientations_.size();}
  void reset(){counts_.clear();orientations_.clear();frame_=0;}
private:
  struct Accum {int hits=0;uint64_t bins=0;uint64_t last_seen_frame=0;};
  static int popcount(uint64_t v){
    int n=0;while(v){v &= v-1; ++n;}return n;
  }
  int get_orientation_bin(const Quaternion &q){
    const double max_angle=c_.orientation_step_deg*PI/180.0;
    int nearest=-1; double dist=std::numeric_limits<double>::infinity();
    for(size_t i=0;i<orientations_.size();++i){
      const double d=Quaternion::distance(orientations_[i],q);
      if(d<dist){dist=d;nearest=static_cast<int>(i);}
    }
    if(dist>=max_angle && static_cast<int>(orientations_.size())<c_.max_bins &&
       orientations_.size()<64){
      orientations_.push_back(q);
      return static_cast<int>(orientations_.size()-1);
    }
    if(nearest==-1){orientations_.push_back(q); return 0;}
    return nearest;
  }
  LearnerConfig c_;
  std::unordered_map<Voxel,Accum,VoxelHash> counts_;
  std::vector<Quaternion> orientations_;
  uint64_t frame_=0;
};
} // namespace gasf
