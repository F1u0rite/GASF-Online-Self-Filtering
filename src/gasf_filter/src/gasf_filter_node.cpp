#include "gasf_filter/core.hpp"

#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/imu.hpp>
#include <sensor_msgs/msg/point_cloud2.hpp>
#include <sensor_msgs/point_cloud2_iterator.hpp>
#include <std_msgs/msg/string.hpp>
#include <livox_ros_driver2/msg/custom_msg.hpp>
#include <livox_ros_driver2/msg/custom_point.hpp>

#include <atomic>
#include <chrono>
#include <condition_variable>
#include <deque>
#include <fstream>
#include <iomanip>
#include <memory>
#include <mutex>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <unordered_set>
#include <utility>
#include <vector>

using CustomMsg=livox_ros_driver2::msg::CustomMsg;
using CustomPoint=livox_ros_driver2::msg::CustomPoint;
using Cloud=sensor_msgs::msg::PointCloud2;

class GASFNode final:public rclcpp::Node {
public:
  GASFNode():Node("gasf_filter_node") {
    mode_=declare_parameter<std::string>("mode","online");
    if(mode_!="online" && mode_!="frozen")
      throw std::runtime_error("mode must be 'online' or 'frozen'");
    voxel_size_=declare_parameter<double>("voxel_size",0.06);
    min_range_=declare_parameter<double>("min_range",0.12);
    max_range_=declare_parameter<double>("max_range",0.45);
    if(voxel_size_<=0 || min_range_<0 || max_range_<=min_range_)
      throw std::runtime_error("invalid voxel_size/min_range/max_range");
    gyro_deadband_=declare_parameter<double>("gyro_deadband_rad_s",0.015);
    const int min_hits=declare_parameter<int>("min_hits",8);
    const int min_orientations=declare_parameter<int>("min_orientations",3);
    const int stale_frames=declare_parameter<int>("stale_frames",250);
    const double orient_step=declare_parameter<double>("orientation_step_deg",6.0);
    const int snapshot_every=declare_parameter<int>("snapshot_every_frames",5);
    snapshot_every_=std::max(1,snapshot_every);
    publish_visuals_=declare_parameter<bool>("publish_visuals",true);
    publish_custom_=declare_parameter<bool>("publish_filtered_custom",false);
    const int max_learning_queue = declare_parameter<int>("max_learning_queue", 5);
    max_queue_ = static_cast<size_t>(std::max(1, max_learning_queue));
    input_topic_=declare_parameter<std::string>("input_topic","/livox/lidar");
    imu_topic_=declare_parameter<std::string>("imu_topic","/livox/imu");
    const std::string frozen_path=declare_parameter<std::string>("frozen_mask_path","");
    learner_=std::make_unique<gasf::OnlineLearner>(
      gasf::LearnerConfig{min_hits,min_orientations,stale_frames,60,orient_step});

    rclcpp::QoS visual_qos=rclcpp::QoS(5).reliable();
    auto raw_pub=create_publisher<Cloud>("/gasf/raw_points",visual_qos);
    raw_pub_=raw_pub;
    retained_pub_=create_publisher<Cloud>("/gasf/filtered_points",visual_qos);
    removed_pub_=create_publisher<Cloud>("/gasf/removed_points",visual_qos);
    model_pub_=create_publisher<Cloud>("/gasf/model_points",visual_qos);
    custom_pub_=create_publisher<CustomMsg>("/gasf/filtered_custom",rclcpp::SensorDataQoS());
    stats_pub_=create_publisher<std_msgs::msg::String>("/gasf/stats",rclcpp::QoS(10));
    std::atomic_store(&mask_,std::shared_ptr<const gasf::Mask>(std::make_shared<gasf::Mask>()));

    if(mode_=="frozen") {
      auto loaded=load_mask(frozen_path);
      std::atomic_store(&mask_,std::shared_ptr<const gasf::Mask>(loaded));
      RCLCPP_WARN(get_logger(),"FROZEN DIAGNOSTIC MODE: %zu UNVERIFIED candidate voxels",loaded->size());
    } else {
      worker_=std::thread([this]{learning_loop();});
    }

    imu_sub_=create_subscription<sensor_msgs::msg::Imu>(imu_topic_,rclcpp::SensorDataQoS(),
        [this](sensor_msgs::msg::Imu::ConstSharedPtr msg){on_imu(msg);});
    lidar_sub_=create_subscription<CustomMsg>(input_topic_,rclcpp::SensorDataQoS(),
        [this](CustomMsg::ConstSharedPtr msg){on_lidar(msg);});
    timer_=create_wall_timer(std::chrono::seconds(1),[this]{publish_model();});
    RCLCPP_INFO(get_logger(),"GASF V1 mode=%s input=%s voxel=%.3fm learn_range=[%.2f,%.2f]m",
      mode_.c_str(),input_topic_.c_str(),voxel_size_,min_range_,max_range_);
  }
  ~GASFNode() override {
    {
      std::lock_guard<std::mutex> guard(queue_mutex_);stop_=true;
    }
    queue_cv_.notify_all();
    if(worker_.joinable())worker_.join();
  }
private:
  std::shared_ptr<gasf::Mask> load_mask(const std::string &path) {
    if(path.empty())throw std::runtime_error("frozen_mask_path required in frozen mode");
    std::ifstream in(path);
    if(!in)throw std::runtime_error("cannot read frozen mask: "+path);
    auto m=std::make_shared<gasf::Mask>();
    std::string line;
    while(std::getline(in,line)) {
      if(line.empty() || line[0]=='#')continue;
      std::istringstream ss(line);
      gasf::Voxel v;
      if(ss>>v.x>>v.y>>v.z)m->insert(v);
    }
    if(m->empty())throw std::runtime_error("frozen mask is empty: "+path);
    return m;
  }
  bool near_field(const CustomPoint& p)const {
    const double r2=double(p.x)*p.x+double(p.y)*p.y+double(p.z)*p.z;
    return std::isfinite(r2) && r2>=min_range_*min_range_ && r2<=max_range_*max_range_;
  }
  void on_imu(const sensor_msgs::msg::Imu::ConstSharedPtr &msg) {
    const int64_t now=rclcpp::Time(msg->header.stamp).nanoseconds();
    std::lock_guard<std::mutex> lk(orientation_mutex_);
    if(last_imu_ns_!=0){
      const double dt=(now-last_imu_ns_)*1e-9;
      if(dt>0 && dt<0.1) {
        const auto& w=msg->angular_velocity;
        if(std::isfinite(w.x) && std::isfinite(w.y) && std::isfinite(w.z)){
          const double omega=std::sqrt(w.x*w.x+w.y*w.y+w.z*w.z);
          if(omega>=gyro_deadband_){
            imu_q_=imu_q_*gasf::Quaternion::gyro_step(w.x,w.y,w.z,dt);
            imu_q_.normalize();
          }
          imu_ready_=true;
        }
      }else if(dt<0 || dt>1.0){
        // Bag time jumped or replay restarted: current pose is no longer continuous.
        imu_q_={};imu_ready_=false;imu_history_.clear();
      }
    }
    last_imu_ns_=now;
    if(imu_ready_){
      imu_history_.emplace_back(now,imu_q_);
      while(!imu_history_.empty() && now-imu_history_.front().first>2000000000LL)
        imu_history_.pop_front();
    }
  }
  Cloud make_cloud(const std_msgs::msg::Header& hdr,
                   const std::vector<CustomPoint>& points)const {
    Cloud cloud;
    cloud.header=hdr;
    cloud.is_dense=false;
    sensor_msgs::PointCloud2Modifier mod(cloud);
    mod.setPointCloud2Fields(5,
      "x",1,sensor_msgs::msg::PointField::FLOAT32,
      "y",1,sensor_msgs::msg::PointField::FLOAT32,
      "z",1,sensor_msgs::msg::PointField::FLOAT32,
      "intensity",1,sensor_msgs::msg::PointField::FLOAT32,
      "offset_time",1,sensor_msgs::msg::PointField::UINT32);
    mod.resize(points.size());
    sensor_msgs::PointCloud2Iterator<float> ix(cloud,"x"),iy(cloud,"y"),iz(cloud,"z"),ii(cloud,"intensity");
    sensor_msgs::PointCloud2Iterator<uint32_t> it(cloud,"offset_time");
    for(const auto& p:points){
      *ix=p.x;*iy=p.y;*iz=p.z;*ii=static_cast<float>(p.reflectivity);*it=p.offset_time;
      ++ix;++iy;++iz;++ii;++it;
    }
    return cloud;
  }
  void on_lidar(const CustomMsg::ConstSharedPtr &msg) {
    auto t0=std::chrono::steady_clock::now();
    ++received_frames_;
    const auto snapshot=std::atomic_load(&mask_); // Never wait for learning.
    const bool raw_requested=publish_visuals_ && raw_pub_->get_subscription_count()>0;
    const bool retained_requested=publish_visuals_ && retained_pub_->get_subscription_count()>0;
    const bool removed_requested=publish_visuals_ && removed_pub_->get_subscription_count()>0;
    const bool custom_requested=publish_custom_ && custom_pub_->get_subscription_count()>0;
    std::vector<CustomPoint> raw, kept, removed;
    if(raw_requested)raw.reserve(msg->points.size());
    if(retained_requested || custom_requested)kept.reserve(msg->points.size());
    if(removed_requested)removed.reserve(msg->points.size()/10);
    std::unordered_set<gasf::Voxel,gasf::VoxelHash> observed;
    if(mode_=="online")observed.reserve(512);
    size_t removed_count=0;
    for(const auto& p:msg->points){
      const bool valid=std::isfinite(p.x) && std::isfinite(p.y) && std::isfinite(p.z);
      bool is_candidate=false;
      if(valid && near_field(p)){
        const auto key=gasf::make_voxel(p.x,p.y,p.z,voxel_size_);
        is_candidate=(snapshot->find(key)!=snapshot->end());
        if(mode_=="online")observed.insert(key);
      }
      if(raw_requested)raw.push_back(p);
      if(is_candidate){
        ++removed_count;
        if(removed_requested)removed.push_back(p);
      }else{
        if(retained_requested || custom_requested)kept.push_back(p);
      }
    }
    const auto hdr=msg->header; // preserve original acquisition header and frame_id
    if(raw_requested)raw_pub_->publish(make_cloud(hdr,raw));
    if(retained_requested)retained_pub_->publish(make_cloud(hdr,kept));
    if(removed_requested)removed_pub_->publish(make_cloud(hdr,removed));
    if(custom_requested){
      CustomMsg out=*msg; // timebase, offsets, lidar_id and header unchanged
      out.points=std::move(kept);
      out.point_num=static_cast<uint32_t>(out.points.size());
      custom_pub_->publish(std::move(out));
    }
    if(mode_=="online"){
      gasf::Observation o;
      o.voxels.assign(observed.begin(),observed.end());
      {
        std::lock_guard<std::mutex> lk(orientation_mutex_);
        // Select the nearest PAST IMU attitude. Never wait for future IMU data.
        const int64_t stamp=rclcpp::Time(msg->header.stamp).nanoseconds();
        for(auto it=imu_history_.rbegin();it!=imu_history_.rend();++it){
          if(it->first<=stamp){
            const int64_t age_ns=stamp-it->first;
            if(age_ns>=0 && age_ns<=100000000LL){
              o.orientation=it->second;
              o.imu_ready=true;
            }
            break;
          }
        }
      }
      // Do not block the LiDAR callback if the learner is busy.
      if(queue_mutex_.try_lock()){
        if(queue_.size()>=max_queue_){queue_.pop_front();++dropped_learning_batches_;}
        queue_.push_back(std::move(o));
        queue_mutex_.unlock();
        queue_cv_.notify_one();
      }else ++dropped_learning_batches_;
    }
    const double elapsed_ms=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-t0).count();
    if(received_frames_%10==0){
      std_msgs::msg::String s;
      std::ostringstream os;
      os<<"mode="<<mode_<<" frame="<<received_frames_<<" raw="<<msg->points.size()
        <<" candidate_hits="<<removed_count<<" mask_voxels="<<snapshot->size()
        <<" callback_ms="<<std::fixed<<std::setprecision(3)<<elapsed_ms
        <<" learning_frames="<<learning_frames_.load()
        <<" orientation_bins="<<orientation_bins_.load()
        <<" candidate_voxels="<<candidate_voxels_.load()
        <<" dropped_learning_batches="<<dropped_learning_batches_.load();
      s.data=os.str(); stats_pub_->publish(std::move(s));
      RCLCPP_INFO(get_logger(),"%s",os.str().c_str());
    }
    last_header_=hdr;
  }
  void learning_loop(){
    while(true){
      gasf::Observation obs;
      {
        std::unique_lock<std::mutex> lk(queue_mutex_);
        queue_cv_.wait(lk,[this]{return stop_ || !queue_.empty();});
        if(stop_ && queue_.empty())return;
        obs=std::move(queue_.front());queue_.pop_front();
      }
      learner_->update(obs);
      learning_frames_.store(learner_->processed_frames());
      orientation_bins_.store(learner_->orientation_bins());
      candidate_voxels_.store(learner_->candidate_count());
      if(learner_->processed_frames()%static_cast<uint64_t>(snapshot_every_)==0){
        auto next=learner_->confirmed();
        std::atomic_store(&mask_,std::move(next));
      }
    }
  }
  void publish_model(){
    if(!publish_visuals_ || model_pub_->get_subscription_count()==0)return;
    const auto snapshot=std::atomic_load(&mask_);
    std::vector<CustomPoint> voxels;
    voxels.reserve(snapshot->size());
    for(const auto& v:*snapshot){
      CustomPoint p;
      p.x=static_cast<float>((v.x+0.5)*voxel_size_);
      p.y=static_cast<float>((v.y+0.5)*voxel_size_);
      p.z=static_cast<float>((v.z+0.5)*voxel_size_);
      p.reflectivity=255;p.offset_time=0;
      voxels.push_back(p);
    }
    auto hdr=last_header_;
    // Fallback before first LiDAR message; the user's RViz Fixed Frame must be LiDAR frame.
    if(hdr.frame_id.empty())hdr.frame_id="livox_frame";
    model_pub_->publish(make_cloud(hdr,voxels));
  }
  std::string mode_,input_topic_,imu_topic_;
  double voxel_size_,min_range_,max_range_,gyro_deadband_;
  int snapshot_every_;
  bool publish_visuals_,publish_custom_;
  size_t max_queue_;
  std::shared_ptr<const gasf::Mask> mask_;
  std::unique_ptr<gasf::OnlineLearner> learner_;
  std::mutex orientation_mutex_,queue_mutex_;
  gasf::Quaternion imu_q_;
  std::deque<std::pair<int64_t,gasf::Quaternion>> imu_history_;
  int64_t last_imu_ns_=0;
  bool imu_ready_=false;
  std::deque<gasf::Observation> queue_;
  std::condition_variable queue_cv_;
  std::thread worker_;
  bool stop_=false;
  uint64_t received_frames_=0;
  std::atomic<uint64_t> dropped_learning_batches_{0};
  std::atomic<uint64_t> learning_frames_{0};
  std::atomic<uint64_t> orientation_bins_{0};
  std::atomic<uint64_t> candidate_voxels_{0};
  std_msgs::msg::Header last_header_;
  rclcpp::Subscription<CustomMsg>::SharedPtr lidar_sub_;
  rclcpp::Subscription<sensor_msgs::msg::Imu>::SharedPtr imu_sub_;
  rclcpp::Publisher<Cloud>::SharedPtr raw_pub_,retained_pub_,removed_pub_,model_pub_;
  rclcpp::Publisher<CustomMsg>::SharedPtr custom_pub_;
  rclcpp::Publisher<std_msgs::msg::String>::SharedPtr stats_pub_;
  rclcpp::TimerBase::SharedPtr timer_;
};
int main(int argc,char**argv){
  rclcpp::init(argc,argv);
  try {rclcpp::spin(std::make_shared<GASFNode>());}
  catch(const std::exception& e){RCLCPP_FATAL(rclcpp::get_logger("gasf_filter"),"%s",e.what());rclcpp::shutdown();return 1;}
  rclcpp::shutdown();return 0;
}
