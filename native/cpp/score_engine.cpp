#include "score_engine.h"
#include <algorithm>
#include <atomic>
#include <chrono>
#include <cmath>
#include <thread>
#include <vector>
namespace {
constexpr int F=8, K=3;
void score(const double* x,const double* mean,const double* scale,const double* weights,double* out) {
  double logits[K];
  for(int k=0;k<K;++k) {
    logits[k]=weights[F*K+k];
    for(int j=0;j<F;++j) logits[k]+=std::clamp((x[j]-mean[j])/scale[j],-12.0,12.0)*weights[j*K+k];
  }
  const double top=*std::max_element(logits,logits+K);
  double sum=0;
  for(int k=0;k<K;++k) {out[k]=std::exp(logits[k]-top);sum+=out[k];}
  for(int k=0;k<K;++k) out[k]/=sum;
}
}
extern "C" int extract_features(const double* p,const double* b,const double* v,int n,double sent,double present,double* out) {
  if(n<25 || !p || !b || !v || !out) return -1;
  std::vector<double> r(n-1),br(n-1);
  double mu=0,bmu=0;
  for(int i=0;i<n;++i) if(!std::isfinite(p[i]) || !std::isfinite(b[i]) || !std::isfinite(v[i]) || p[i]<=0 || b[i]<=0 || v[i]<0) return -2;
  for(int i=1;i<n;++i) {r[i-1]=std::log(p[i]/p[i-1]);br[i-1]=std::log(b[i]/b[i-1]);mu+=r[i-1];bmu+=br[i-1];}
  mu/=n-1; bmu/=n-1;
  double var=0,bvar=0,cov=0,mom=0,bmom=0,shortvar=0,vm=0,vvar=0;
  for(int i=0;i<n-1;++i) {var+=(r[i]-mu)*(r[i]-mu);bvar+=(br[i]-bmu)*(br[i]-bmu);cov+=(r[i]-mu)*(br[i]-bmu);}
  for(int i=n-4;i<n-1;++i) {mom+=r[i];bmom+=br[i];shortvar+=r[i]*r[i];}
  for(int i=0;i<n-1;++i) vm+=v[i]; vm/=n-1;
  for(int i=0;i<n-1;++i) vvar+=(v[i]-vm)*(v[i]-vm);
  const double vol=std::sqrt(var/(n-2));
  out[0]=sent;out[1]=present;out[2]=(var*bvar>1e-24)?cov/std::sqrt(var*bvar):0;
  out[3]=vol;out[4]=mom;out[5]=mom-bmom;
  out[6]=std::clamp((v[n-1]-vm)/std::max(std::sqrt(vvar/(n-2)),1e-9),-10.0,10.0);
  out[7]=std::min(10.0,std::sqrt(shortvar/3)/std::max(vol,1e-9));
  return 0;
}
extern "C" int score_batch(const double* x,int rows,const double* mean,const double* scale,const double* weights,double* out) {
  if(rows<1) return -1;
  for(int i=0;i<rows;++i) score(x+i*F,mean,scale,weights,out+i*K);
  return 0;
}
extern "C" int work_index_lock_free() {std::atomic<int> index{0};return index.is_lock_free();}
extern "C" double replay_windows(const double* x,int rows,const double* mean,const double* scale,const double* weights,int threads,int repeats,double* checksum) {
  if(rows<1 || threads<1 || threads>64 || repeats<1) return -1;
  const auto start=std::chrono::steady_clock::now();
  // Fixed workers claim disjoint row blocks with an atomic index: no queue mutex.
  std::atomic<int> next{0};
  std::vector<double> sums(rows,0.0);
  std::vector<std::thread> pool;
  for(int t=0;t<std::min(threads,rows);++t) pool.emplace_back([&]() {
    for(;;) {
      const int begin=next.fetch_add(32,std::memory_order_relaxed);
      if(begin>=rows) break;
      for(int i=begin;i<std::min(begin+32,rows);++i) {
        double sum=0, out[K];
        for(int r=0;r<repeats;++r) {score(x+((i+r)%rows)*F,mean,scale,weights,out);sum+=out[1]+2*out[2];}
        sums[i]=sum;
      }
    }
  });
  for(auto& worker:pool) worker.join();
  *checksum=0; for(double value:sums) *checksum+=value;
  return std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-start).count();
}
