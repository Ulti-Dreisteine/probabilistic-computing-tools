from scipy.signal import find_peaks
from itertools import permutations
from typing import Tuple
from typing import List
import numpy as np


# ---- 时延传递熵峰值解析 ----------------------------------------------------------------------------

def parse_peaks(tau_x: int, td_lags: np.ndarray, td_te_info: List[tuple], ci_bg_ub: float, 
                    thres: float = None, distance: int = None, prominence: float = None):
    """
    从时延TE结果中寻找是否有高于阈值的一个或多个峰值, 如果没有则默认峰在0时延处
    
    Params:
    -------
    tau_x: 因变量的特征时间参数, 以样本为单位计
    td_lags: 检测用的作用时延序列
    td_te_info: 包含了各作用时延td_lag上的te均值和方差的列表, 形如 [(te_mean@td_lag_1, te_std@td_lag_1), ...]
    ci_bg_ub: 从te背景值结果中解析获得的CI上界
    distance: 相邻两个峰的最小间距, 见scipy.signal.find_peaks()
    prominence: 在wlen范围内至少超过最低值的程度, 见scipy.signal.find_peaks()
    """
    
    if thres is None:
        thres = ci_bg_ub
        
    if distance is None:
        distance = 2 * tau_x
        
    if prominence is None:
        prominence = 0.01
    
    td_te_means = [p[0] for p in td_te_info]
    td_te_stds = [p[1] for p in td_te_info]
    
    peak_idxs, _ = find_peaks(
        td_te_means, height=thres, distance=distance, prominence=prominence, 
        wlen=max([2, len(td_lags) // 2]))

    peak_signifs = []
    
    if len(peak_idxs) == 0:
        peak_taus = []
        peak_strengths = []
        peak_stds = []
    else:
        # 获得对应峰时延、强度和显著性信息
        peak_taus = [td_lags[p] for p in peak_idxs]
        peak_strengths = [td_te_means[p] for p in peak_idxs]
        peak_stds = [td_te_stds[p] for p in peak_idxs]

        for idx in peak_idxs:
            _n = len(td_lags) // 10
            _series = np.append(td_te_means[: _n], td_te_means[-_n :])
            _mean, _std = np.mean(_series), np.std(_series)
            signif = (td_te_means[idx] > ci_bg_ub) & (td_te_means[idx] > _mean + 3 * _std)  # 99% CI
            peak_signifs.append(signif)

    return peak_idxs, peak_taus, peak_strengths, peak_stds, peak_signifs


# ---- 序列符号化 -----------------------------------------------------------------------------------

def _build_embed_series(x: np.ndarray, idxs: np.ndarray, m: int, tau: int) -> np.ndarray:
    """
    构造一维序列x的m维嵌入序列
    
    Params:
    -------
    x: 一维序列
    idxs: 首尾截断(避免空值)后的连续索引序列
    m: 嵌入维度
    tau: 嵌入延迟(以样本为单位计), 应等于序列自身的特征时间参数
    """
    
    X_embed = x[idxs]
    
    for i in range(1, m):
        X_embed = np.c_[x[idxs - i * tau], X_embed]
        
    return X_embed.reshape(len(X_embed), -1)


def continuously_symbolize(x: np.ndarray, y: np.ndarray, m: int, tau_x: int, tau_y: int) -> \
    Tuple[np.ndarray, np.ndarray]:
    """
    生成具有连续索引的符号样本
    
    Params:
    -------
    x: X序列
    y: Y序列
    m: 嵌入维度
    tau_x: X序列的嵌入延迟(以样本为单位计), 应等于序列自身的特征时间参数
    tau_y: Y序列的嵌入延迟(以样本为单位计), 应等于序列自身的特征时间参数
    """
    
    # 提取所有可能的离散模式
    patterns = list(permutations(np.arange(m) + 1))
    dict_pattern_index = {patterns[i]: i for i in range(len(patterns))}
    
    # 构造嵌入序列
    idxs = np.arange((m - 1) * max(tau_x, tau_y), len(x))       # 连续索引
    X_embed = _build_embed_series(x, idxs, m, tau_x)
    Y_embed = _build_embed_series(y, idxs, m, tau_y)
    
    # 获得对应的索引
    X = np.argsort(X_embed) + 1                                 # 滚动形成m维时延嵌入样本  一个时刻成为一个标签
    X = np.array([dict_pattern_index[tuple(p)] for p in X])     # 对应映射到符号上
    
    Y = np.argsort(Y_embed) + 1
    Y = np.array([dict_pattern_index[tuple(p)] for p in Y])
    
    return X.flatten(), Y.flatten()