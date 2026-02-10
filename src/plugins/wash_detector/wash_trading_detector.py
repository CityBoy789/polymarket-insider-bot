import math
from statistics import mean
from typing import Any


class WashTradingDetector:
    """
    Polymarket 洗盘交易检测器 (8维度版)
    基于：哥伦比亚大学《Network-Based Detection of Wash-Trading》研究及量化反欺诈算法
    """

    def __init__(self, thresholds: dict[str, float] = None):
        # 默认阈值设置（可根据市场波动率调整）
        self.thresholds = thresholds or {
            "min_pl_volume_ratio": 0.005,  # P&L/成交量比例低于 0.5% 视为可疑
            "max_holding_time_sec": 300,  # 平均持仓时间少于 5 分钟
            "extreme_price_threshold": 0.05,  # 价格低于 $0.05 或高于 $0.95 的交易比例
            "win_rate_suspicious": 0.90,  # 胜率过高 (可能是极低价对倒)
            "entropy_low_limit": 1.5,  # 时间间隔熵过低 (极度规律的机器人)
            "concentration_limit": 0.85,  # 资金集中在单一市场的比例
        }

    def detect(self, address: str, trades: list[dict[str, Any]]) -> dict[str, Any]:
        """
        执行多维度扫描
        trades 格式要求: [{ "price": float, "size": float, "timestamp": int, "pnl": float, "market": str }]
        """
        if not trades or len(trades) < 5:
            return {"is_suspicious": False, "score": 0, "reason": "数据样本不足"}

        results = {
            "pl_vol_ratio": self._check_pl_volume_ratio(trades),
            "holding_time": self._check_average_holding_time(trades),
            "extreme_prices": self._check_extreme_price_ratio(trades),
            "win_rate": self._check_win_rate(trades),
            "cycle_patterns": self._check_round_trip_patterns(trades),
            "entropy": self._check_temporal_entropy(trades),
            "market_concentration": self._check_market_concentration(trades),
            "price_impact_reversal": self._check_price_impact_reversal(trades),
        }

        # 计算综合评分 (0-100)
        suspicious_count = sum(1 for v in results.values() if v.get("flagged"))
        score = (suspicious_count / len(results)) * 100

        return {
            "address": address,
            "is_suspicious": score >= 60,  # 综合得分 60 以上标记为可疑
            "score": round(score, 2),
            "details": results,
        }

    def _check_pl_volume_ratio(self, trades):
        """1. P&L / Volume 比例: 洗盘者通常成交额巨大但利润极低"""
        total_vol = sum(t["size"] * t["price"] for t in trades)
        total_pnl = abs(sum(t.get("pnl", 0) for t in trades))
        ratio = total_pnl / total_vol if total_vol > 0 else 1
        return {"value": round(ratio, 4), "flagged": ratio < self.thresholds["min_pl_volume_ratio"]}

    def _check_average_holding_time(self, trades):
        """2. 平均持仓时间: 洗盘交易通常在数秒或数分钟内对冲完成"""
        # 简化版：计算连续两笔相同市场交易的间隔
        intervals = []
        for i in range(1, len(trades)):
            if trades[i]["market"] == trades[i - 1]["market"]:
                intervals.append(trades[i]["timestamp"] - trades[i - 1]["timestamp"])

        avg_time = mean(intervals) if intervals else 9999
        return {
            "value": f"{round(avg_time, 1)}s",
            "flagged": avg_time < self.thresholds["max_holding_time_sec"],
        }

    def _check_extreme_price_ratio(self, trades):
        """3. 极端价格占比: 利用 $0.01 或 $0.99 刷量以降低磨损"""
        extreme_count = sum(1 for t in trades if t["price"] < 0.05 or t["price"] > 0.95)
        ratio = extreme_count / len(trades)
        return {
            "value": round(ratio, 2),
            "flagged": ratio > self.thresholds["extreme_price_threshold"],
        }

    def _check_win_rate(self, trades):
        """4. 胜率异常: 90%+ 的胜率通常通过对倒刷小额利润获得"""
        wins = sum(1 for t in trades if t.get("pnl", 0) > 0)
        rate = wins / len(trades)
        return {"value": round(rate, 2), "flagged": rate > self.thresholds["win_rate_suspicious"]}

    def _check_round_trip_patterns(self, trades):
        """5. 往返交易识别: 短时间内在同一市场进行买入后立即卖出同等规模"""
        # 实现逻辑：检测 15 分钟内是否存在 Size 差异 < 5% 的反向操作
        matches = 0
        for i in range(len(trades)):
            for j in range(i + 1, min(i + 5, len(trades))):
                if trades[i]["market"] == trades[j]["market"]:
                    time_diff = trades[j]["timestamp"] - trades[i]["timestamp"]
                    size_diff = abs(trades[i]["size"] - trades[j]["size"]) / trades[i]["size"]
                    if time_diff < 900 and size_diff < 0.05:
                        matches += 1
        return {"count": matches, "flagged": matches > len(trades) * 0.3}

    def _check_temporal_entropy(self, trades):
        """6. 时间熵: 机器人交易的时间间隔通常具有规律性 (低熵值)"""
        intervals = [
            trades[i]["timestamp"] - trades[i - 1]["timestamp"] for i in range(1, len(trades))
        ]
        if not intervals:
            return {"value": 0, "flagged": False}

        # 简易 Shannon 熵计算
        counts = {}
        for iv in [round(i / 10) for i in intervals]:  # 以10秒为桶
            counts[iv] = counts.get(iv, 0) + 1

        entropy = -sum(
            (c / len(intervals)) * math.log2(c / len(intervals)) for c in counts.values()
        )
        return {
            "value": round(entropy, 2),
            "flagged": entropy < self.thresholds["entropy_low_limit"],
        }

    def _check_market_concentration(self, trades):
        """7. 市场集中度: 只在极个别低流动性市场活动"""
        markets = [t["market"] for t in trades]
        top_market_share = markets.count(max(set(markets), key=markets.count)) / len(trades)
        return {
            "value": round(top_market_share, 2),
            "flagged": top_market_share > self.thresholds["concentration_limit"],
        }

    def _check_price_impact_reversal(self, trades):
        """8. 价格操纵回撤: 推高价格后立即由同一地址或关联地址接盘"""
        # 简化版：连续成交中价格变动 > 10% 后立即反转
        suspicious_moves = 0
        for i in range(2, len(trades)):
            p1, p2, p3 = trades[i - 2]["price"], trades[i - 1]["price"], trades[i]["price"]
            if abs(p2 - p1) / p1 > 0.1 and (p3 - p2) * (p2 - p1) < 0:  # 价格方向反转
                suspicious_moves += 1
        return {"value": suspicious_moves, "flagged": suspicious_moves > 2}
