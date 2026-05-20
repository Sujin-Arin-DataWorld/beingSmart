"""ML 기반 regime classifier — KMeans unsupervised clustering + 매핑.

scikit-learn 필요. 없으면 None 반환 (rule-based가 fallback).

Features (daily):
- VIX 수준
- VIX 5일 변화율
- SP500 5일 수익률
- SP500 20일 수익률
- SP500 / SMA200 ratio

cluster centroids로 BULL/CHOPPY/BEAR/RISK_OFF 매핑 (rule-based와 동일 기준).
이는 supervised label 없이 historical 분포에서 자연스러운 grouping 찾는 방식.
"""
from __future__ import annotations
from typing import Dict, Optional

import numpy as np
import pandas as pd

from src.regime.classifier import Regime


def _build_features(macro_history: Dict[str, pd.DataFrame]) -> Optional[pd.DataFrame]:
    vix_df = macro_history.get("^VIX")
    sp_df = macro_history.get("^GSPC")
    if vix_df is None or sp_df is None:
        return None

    common = vix_df.index.intersection(sp_df.index)
    if len(common) < 250:
        return None

    vix = vix_df.loc[common, "Close"]
    sp = sp_df.loc[common, "Close"]

    features = pd.DataFrame(index=common)
    features["vix"] = vix
    features["vix_5d_change"] = vix.pct_change(5) * 100
    features["sp_5d_return"] = sp.pct_change(5) * 100
    features["sp_20d_return"] = sp.pct_change(20) * 100
    features["sp_vs_sma200"] = (sp / sp.rolling(200).mean() - 1) * 100
    features = features.dropna()
    return features


def _assign_regime(centroid: Dict[str, float]) -> Regime:
    """centroid 특성으로 regime 할당 (rule-based와 동일 기준)."""
    if centroid["vix"] > 28 or centroid["sp_5d_return"] < -6:
        return Regime.RISK_OFF
    if centroid["sp_vs_sma200"] < -5:
        return Regime.BEAR
    if centroid["vix"] > 19:
        return Regime.CHOPPY
    return Regime.BULL


def fit_and_predict(
    macro_history: Dict[str, pd.DataFrame],
    n_clusters: int = 4,
    random_state: int = 42,
) -> Optional[Dict]:
    """historical macro에 KMeans fit 후 최신 시점 regime 예측.

    Returns:
        {
          "regime": Regime,
          "cluster_id": int,
          "cluster_info": [{id, vix, vix_5d_change, sp_5d_return, sp_20d_return, sp_vs_sma200, size, regime}, ...],
          "n_samples": int,
          "latest_features": {...},
          "method": "kmeans-4cluster",
        }
        sklearn 미설치 또는 데이터 부족 시 None.
    """
    try:
        from sklearn.cluster import KMeans
        from sklearn.preprocessing import StandardScaler
    except ImportError:
        return None

    features = _build_features(macro_history)
    if features is None or len(features) < 250:
        return None

    X = features.values
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    km = KMeans(n_clusters=n_clusters, random_state=random_state, n_init=10)
    labels = km.fit_predict(X_scaled)

    centroids_scaled = km.cluster_centers_
    centroids = scaler.inverse_transform(centroids_scaled)

    cluster_info = []
    for i, c in enumerate(centroids):
        info = {
            "id": int(i),
            "vix": float(c[0]),
            "vix_5d_change": float(c[1]),
            "sp_5d_return": float(c[2]),
            "sp_20d_return": float(c[3]),
            "sp_vs_sma200": float(c[4]),
            "size": int((labels == i).sum()),
        }
        info["regime"] = _assign_regime(info).value
        cluster_info.append(info)

    latest_label = int(labels[-1])
    latest_centroid = next(c for c in cluster_info if c["id"] == latest_label)
    latest_regime = Regime(latest_centroid["regime"])

    return {
        "regime": latest_regime,
        "cluster_id": latest_label,
        "cluster_info": cluster_info,
        "n_samples": int(len(features)),
        "latest_features": {
            col: float(features.iloc[-1][col]) for col in features.columns
        },
        "method": f"kmeans-{n_clusters}cluster",
    }


def compare_with_rule_based(
    ml_result: Optional[Dict],
    rule_regime: Regime,
) -> Dict:
    """ML 예측과 rule-based 결과 비교."""
    if ml_result is None:
        return {"available": False, "agreement": None}
    return {
        "available": True,
        "ml_regime": ml_result["regime"].value,
        "rule_regime": rule_regime.value,
        "agreement": ml_result["regime"] == rule_regime,
        "method": ml_result["method"],
        "n_samples": ml_result["n_samples"],
    }
