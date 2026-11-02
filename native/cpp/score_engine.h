#pragma once
extern "C" {
int extract_features(const double*, const double*, const double*, int, double, double, double*);
int score_batch(const double*, int, const double*, const double*, const double*, double*);
double replay_windows(const double*, int, const double*, const double*, const double*, int, int, double*);
int work_index_lock_free();
}
