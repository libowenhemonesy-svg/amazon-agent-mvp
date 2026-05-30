"""战场地图分析模块 - 竞品分析"""
from __future__ import annotations

import re
from collections import Counter
from datetime import date
from typing import Any


class BattlefieldAnalyzer:
    """战场地图分析器"""

    def analyze(self, target_asin: str, competitors: list[dict]) -> dict:
        """
        分析竞品数据，生成战场地图

        参数：
            target_asin: 目标 ASIN
            competitors: 竞品数据列表

        返回：
            {
                "target_asin": str,
                "market_share": {...},  # 市场份额分布
                "price_band": {...},  # 价格带分析
                "keyword_analysis": {...},  # 关键词分析
                "review_insights": {...},  # 评论洞察
                "competitors": list,  # 竞品列表
            }
        """
        if not competitors:
            return {"error": "无竞品数据"}

        # 计算市场份额
        market_share = self.calculate_market_share(competitors)

        # 分析价格带
        price_band = self.analyze_price_band(competitors)

        # 提取关键词
        titles = [c.get("title", "") for c in competitors if c.get("title")]
        keywords = self.extract_keywords(titles)

        # 构建返回结果
        return {
            "target_asin": target_asin,
            "market_share": market_share,
            "price_band": price_band,
            "keyword_analysis": {
                "top_keywords": keywords[:20],
                "total_keywords": len(keywords),
            },
            "competitors": competitors,
        }

    def calculate_market_share(self, competitors: list[dict]) -> dict:
        """
        计算市场份额（基于 BSR 排名和评论数）

        返回：
            {
                "total_market_size": int,  # 总市场规模估算
                "shares": [
                    {"asin": str, "share": float, "bsr_rank": int, "review_count": int},
                    ...
                ],
            }
        """
        if not competitors:
            return {"total_market_size": 0, "shares": []}

        # 使用 BSR 排名的倒数作为市场份额的近似值
        # BSR 越小，市场份额越大
        shares = []
        total_weight = 0

        for comp in competitors:
            bsr = comp.get("bsr_rank", 1000)
            reviews = comp.get("review_count", 0)

            # 权重 = 评论数 / BSR 排名（简化模型）
            weight = (reviews + 1) / (bsr + 1) if bsr > 0 else reviews + 1
            total_weight += weight

            shares.append({
                "asin": comp.get("competitor_asin", comp.get("asin", "")),
                "title": comp.get("title", "")[:50],
                "weight": weight,
                "bsr_rank": bsr,
                "review_count": reviews,
                "price": comp.get("price", 0),
                "rating": comp.get("rating", 0),
            })

        # 计算百分比
        for share in shares:
            share["share"] = round(share["weight"] / total_weight * 100, 1) if total_weight > 0 else 0

        # 按份额排序
        shares.sort(key=lambda x: x["share"], reverse=True)

        return {
            "total_market_size": len(competitors),
            "shares": shares,
        }

    def analyze_price_band(self, competitors: list[dict]) -> dict:
        """
        分析价格带分布

        返回：
            {
                "min_price": float,
                "max_price": float,
                "avg_price": float,
                "bands": [
                    {"range": str, "count": int, "percentage": float},
                    ...
                ],
            }
        """
        prices = [c.get("price", 0) for c in competitors if c.get("price", 0) > 0]

        if not prices:
            return {"min_price": 0, "max_price": 0, "avg_price": 0, "bands": []}

        min_price = min(prices)
        max_price = max(prices)
        avg_price = sum(prices) / len(prices)

        # 划分价格带
        if max_price == min_price:
            bands = [{"range": f"${min_price:.2f}", "count": len(prices), "percentage": 100.0}]
        else:
            # 将价格分为 4-5 个区间
            step = (max_price - min_price) / 4
            bands = []

            for i in range(4):
                low = min_price + step * i
                high = min_price + step * (i + 1)
                count = sum(1 for p in prices if low <= p < high or (i == 3 and p == high))
                percentage = round(count / len(prices) * 100, 1)

                bands.append({
                    "range": f"${low:.2f} - ${high:.2f}",
                    "count": count,
                    "percentage": percentage,
                })

        return {
            "min_price": round(min_price, 2),
            "max_price": round(max_price, 2),
            "avg_price": round(avg_price, 2),
            "bands": bands,
        }

    def extract_keywords(self, titles: list[str]) -> list[dict]:
        """
        提取标题关键词

        返回：
            [{"keyword": str, "count": int}, ...]
        """
        if not titles:
            return []

        # 合并所有标题
        all_text = " ".join(titles).lower()

        # 移除特殊字符，保留字母、数字、空格
        all_text = re.sub(r'[^a-z0-9\s]', ' ', all_text)

        # 分词（简单按空格分割）
        words = all_text.split()

        # 移除停用词
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'is', 'are', 'was', 'were', 'be', 'been',
            'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
            'could', 'should', 'may', 'might', 'must', 'shall', 'can', 'need',
            'it', 'its', 'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she',
            'we', 'they', 'me', 'him', 'her', 'us', 'them', 'my', 'your', 'his',
            'our', 'their', 'mine', 'yours', 'hers', 'ours', 'theirs',
        }

        # 统计词频
        word_counts = Counter(w for w in words if len(w) > 2 and w not in stop_words)

        # 转换为列表
        keywords = [{"keyword": word, "count": count} for word, count in word_counts.most_common(50)]

        return keywords

    def generate_demo_data(self, target_asin: str) -> dict:
        """
        生成演示数据（用于测试）

        返回与 analyze 相同格式的数据
        """
        demo_competitors = [
            {
                "target_asin": target_asin,
                "competitor_asin": "B0COMPETITOR01",
                "title": "Premium Wireless Bluetooth Headphones with Active Noise Cancelling",
                "price": 79.99,
                "rating": 4.5,
                "review_count": 1250,
                "bsr_rank": 150,
                "marketplace": "US",
            },
            {
                "target_asin": target_asin,
                "competitor_asin": "B0COMPETITOR02",
                "title": "Wireless Earbuds with Charging Case IPX7 Waterproof",
                "price": 49.99,
                "rating": 4.3,
                "review_count": 890,
                "bsr_rank": 280,
                "marketplace": "US",
            },
            {
                "target_asin": target_asin,
                "competitor_asin": "B0COMPETITOR03",
                "title": "Over-Ear Headphones Hi-Fi Stereo Sound Deep Bass",
                "price": 59.99,
                "rating": 4.6,
                "review_count": 2100,
                "bsr_rank": 95,
                "marketplace": "US",
            },
            {
                "target_asin": target_asin,
                "competitor_asin": "B0COMPETITOR04",
                "title": "Bluetooth Headset with Microphone Noise Cancelling for Office",
                "price": 39.99,
                "rating": 4.1,
                "review_count": 450,
                "bsr_rank": 520,
                "marketplace": "US",
            },
            {
                "target_asin": target_asin,
                "competitor_asin": "B0COMPETITOR05",
                "title": "Gaming Headset 7.1 Surround Sound RGB Lighting",
                "price": 69.99,
                "rating": 4.4,
                "review_count": 1800,
                "bsr_rank": 120,
                "marketplace": "US",
            },
        ]

        return self.analyze(target_asin, demo_competitors)
