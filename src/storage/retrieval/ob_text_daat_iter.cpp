/*
 * Copyright (c) 2025 OceanBase.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

#define USING_LOG_PREFIX STORAGE

#include "ob_text_daat_iter.h"

namespace oceanbase
{
namespace storage
{
int ObTextDaaTIter::init(const ObTextDaaTParam &param)
{
  int ret = OB_SUCCESS;
  if (OB_ISNULL(param.base_param_) || OB_ISNULL(param.dim_iters_) || OB_ISNULL(param.allocator_)
      || OB_ISNULL(param.relevance_collector_)) {
    ret = OB_INVALID_ARGUMENT;
  } else if (OB_FAIL(ObSRDaaTIterImpl::init(*param.base_param_, *param.dim_iters_,
                                            *param.allocator_, *param.relevance_collector_))) {
  } else if (OB_FAIL(bm25_param_estimator_.init(param.bm25_param_est_ctx_))) {
  } else {
    mode_flag_ = param.mode_flag_;
    function_lookup_mode_ = param.function_lookup_mode_;
  }
  return ret;
}

// For up to three natural-language terms, keep one head per posting list.
// Equal document IDs are still collected in ascending term-index order, exactly
// as ObSimpleRowsMerger does. Boolean and larger queries use the existing path.
int ObTextDaaTIter::do_one_merge_round(int64_t &count)
{
  int ret = OB_SUCCESS;
  const int64_t dim_count = dim_iters_->count();
  if (dim_count > 3 || mode_flag_ != sql::ObMatchAgainstMode::NATURAL_LANGUAGE_MODE) {
    ret = ObSRDaaTIterImpl::do_one_merge_round(count);
  } else {
    for (int64_t i = 0; OB_SUCC(ret) && i < next_round_cnt_; ++i) {
      const int64_t idx = next_round_iter_idxes_[i];
      ObISRDaaTDimIter *iter = dim_iters_->at(idx);
      small_active_[idx] = false;
      if (OB_ISNULL(iter)) {
        ret = OB_ERR_UNEXPECTED;
      } else if (OB_FAIL(iter->get_next_row())) {
        if (OB_ITER_END == ret) {
          ret = OB_SUCCESS;
        }
      } else if (OB_FAIL(iter->get_curr_score(small_scores_[idx]))) {
      } else if (OB_FAIL(iter->get_curr_id(iter_domain_ids_[idx]))) {
      } else {
        if (OB_NOT_NULL(iter_param_->dim_weights_)) {
          small_scores_[idx] = small_scores_[idx] * iter_param_->field_boost_
                              * iter_param_->dim_weights_->at(idx);
        }
        small_active_[idx] = true;
      }
    }
    next_round_cnt_ = 0;
    int64_t winner = -1;
    uint64_t matched = 0;
    for (int64_t i = 0; OB_SUCC(ret) && i < dim_count; ++i) {
      if (!small_active_[i]) {
      } else if (winner < 0) {
        winner = i;
        matched = 1ULL << i;
      } else {
        ObSRMergeItem left;
        ObSRMergeItem right;
        left.iter_idx_ = i;
        right.iter_idx_ = winner;
        int64_t cmp = 0;
        if (OB_FAIL(merge_cmp_.cmp(left, right, cmp))) {
        } else if (cmp < 0) {
          winner = i;
          matched = 1ULL << i;
        } else if (cmp == 0) {
          matched |= 1ULL << i;
        }
      }
    }
    const ObDatum *id = nullptr;
    double relevance = 0.0;
    bool need_project = false;
    if (OB_SUCC(ret) && winner < 0) {
      ret = OB_ITER_END;
    }
    for (int64_t i = 0; OB_SUCC(ret) && i < dim_count; ++i) {
      if (matched & (1ULL << i)) {
        if (OB_FAIL(relevance_collector_->collect_one_dim(i, small_scores_[i]))) {
        } else {
          id = iter_domain_ids_[i];
          next_round_iter_idxes_[next_round_cnt_++] = i;
        }
      }
    }
    if (OB_FAIL(ret)) {
    } else if (OB_ISNULL(id)) {
      ret = OB_ERR_UNEXPECTED;
    } else if (OB_FAIL(relevance_collector_->get_result(relevance, need_project))) {
    } else if (need_project && OB_FAIL(process_collected_row(*id, relevance))) {
    } else if (need_project && OB_FAIL(filter_on_demand(count, relevance, need_project))) {
    } else if (need_project && OB_FAIL(cache_result(count, *id, relevance))) {
    }
  }
  return ret;
}

void ObTextDaaTIter::reset()
{
  MEMSET(small_active_, 0, sizeof(small_active_));
  bm25_param_estimator_.reset();
  // this class can know the type of dim_iters_, but ObSRDaaTIterImpl maybe not
  if (OB_NOT_NULL(dim_iters_)) {
    for (int64_t i = 0; i < dim_iters_->count(); ++i) {
      static_cast<ObTextRetrievalDaaTTokenIter *>(dim_iters_->at(i))->reset();
    }
  }
  ObSRDaaTIterImpl::reset();
}

void ObTextDaaTIter::reuse(const bool switch_tablet)
{
  MEMSET(small_active_, 0, sizeof(small_active_));
  if ((OB_NOT_NULL(dim_iters_) && 0 == dim_iters_->count())) {
    // do nothing
  } else {
    bm25_param_estimator_.reuse(switch_tablet);
  }
  if (OB_NOT_NULL(dim_iters_)) {
    for (int64_t i = 0; i < dim_iters_->count(); ++i) {
      static_cast<ObTextRetrievalDaaTTokenIter *>(dim_iters_->at(i))->reuse();
    }
  }
  ObSRDaaTIterImpl::reuse(switch_tablet);
}

int ObTextDaaTIter::pre_process()
{
  int ret = OB_SUCCESS;
  if (dim_iters_->count() == 0) {
    ret = OB_ITER_END;
  } else if (iter_param_->need_project_relevance()) {
    if (OB_FAIL(bm25_param_estimator_.do_estimation(*iter_param_->eval_ctx_))) {
    }
  }
  return ret;
}

ObTextBMWIter::ObTextBMWIter()
  : ObSRBMWIterImpl(),
    bm25_param_estimator_() {}

void ObTextBMWIter::reuse(const bool switch_tablet)
{
  bm25_param_estimator_.reuse(switch_tablet);
  if (OB_NOT_NULL(dim_iters_)) {
    for (int64_t i = 0; i < dim_iters_->count(); ++i) {
      static_cast<ObTextRetrievalBlockMaxIter *>(dim_iters_->at(i))->reuse();
    }
  }
  ObSRBMWIterImpl::reuse(switch_tablet);
}

void ObTextBMWIter::reset()
{
  bm25_param_estimator_.reset();
  if (OB_NOT_NULL(dim_iters_)) {
    for (int64_t i = 0; i < dim_iters_->count(); ++i) {
      static_cast<ObTextRetrievalBlockMaxIter *>(dim_iters_->at(i))->reset();
    }
  }
  ObSRBMWIterImpl::reset();
}

int ObTextBMWIter::init(const ObTextDaaTParam &param)
{
  int ret = OB_SUCCESS;
  if (OB_ISNULL(param.base_param_) || OB_ISNULL(param.dim_iters_) || OB_ISNULL(param.allocator_)
      || OB_ISNULL(param.relevance_collector_)) {
    ret = OB_INVALID_ARGUMENT;
  } else if (OB_FAIL(ObSRBMWIterImpl::init(*param.base_param_, *param.dim_iters_,
                                           *param.allocator_, *param.relevance_collector_))) {
  } else if (OB_FAIL(bm25_param_estimator_.init(param.bm25_param_est_ctx_))) {
  }
  return ret;
}

int ObTextBMWIter::get_next_rows(const int64_t capacity, int64_t &count)
{
  int ret = OB_SUCCESS;
  if (IS_NOT_INIT) {
    ret = OB_NOT_INIT;
  } else if (dim_iters_->count() == 0) {
    ret = OB_ITER_END;
  } else if (OB_FAIL(bm25_param_estimator_.do_estimation(*iter_param_->eval_ctx_))) {
  }

  if (FAILEDx(ObSRBMWIterImpl::get_next_rows(capacity, count))) {
    if (OB_UNLIKELY(OB_ITER_END != ret)) {
    }
  }
  return ret;
}

int ObTextBMWIter::init_before_wand_process()
{
  int ret = OB_SUCCESS;
  if (OB_UNLIKELY(!bm25_param_estimator_.is_estimated())) {
    ret = OB_ERR_UNEXPECTED;
  }

  for (int64_t i = 0; OB_SUCC(ret) && i < dim_iters_->count(); ++i) {
    ObTextRetrievalBlockMaxIter *block_max_iter = static_cast<ObTextRetrievalBlockMaxIter *>(dim_iters_->at(i));
    if (OB_FAIL(block_max_iter->init_block_max_iter(
        bm25_param_estimator_.get_total_doc_cnt(), bm25_param_estimator_.get_avg_doc_token_cnt()))) {
    }
  }
  return ret;
}

} // namespace storage
} // namespace oceanbase
