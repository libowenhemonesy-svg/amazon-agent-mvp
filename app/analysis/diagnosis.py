"""运营天眼诊断模块 - 产品健康度分析"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any


class DiagnosisAnalyzer:
    """运营天眼诊断器"""

    # 行业基准值（可配置）
    BENCHMARKS = {
        "ctr": 0.02,  # 点击率基准 2%
        "cvr": 0.10,  # 转化率基准 10%
        "acos": 0.30,  # ACoS 基准 30%
        "rating": 4.3,  # 评分基准
        "return_rate": 0.05,  # 退货率基准 5%
        "inventory_days": 30,  # 库存天数基准
        "organic_traffic_ratio": 0.60,  # 自然流量占比基准 60%
    }

    def diagnose(self, asin: str, metrics: dict, competitors: list[dict] = None) -> dict:
        """
        生成产品诊断报告

        参数：
            asin: 目标 ASIN
            metrics: 产品指标数据
            competitors: 竞品数据（可选）

        返回：
            {
                "asin": str,
                "health_score": float,  # 总体健康度 0-100
                "health_level": str,  # green/yellow/red
                "six_factors": {...},  # 六大分析因子
                "top_keywords": [...],  # 出单词 TOP 分析
                "sales_trend": {...},  # 销量趋势
                "recommendations": [...],  # 优化建议
                "priority": str,  # 紧急/重要/优化
            }
        """
        if not metrics:
            return {"error": "无指标数据"}

        # 评估六大因子
        sales_trend = self.evaluate_sales_trend(metrics)
        traffic = self.evaluate_traffic_health(metrics)
        conversion = self.evaluate_conversion(metrics)
        competitive = self.evaluate_competitive(metrics, competitors or [])
        review = self.evaluate_review_risk(metrics)
        ad_performance = self.evaluate_ad_performance(metrics)

        # 六大因子
        six_factors = {
            "sales_trend": sales_trend,
            "traffic_health": traffic,
            "conversion_efficiency": conversion,
            "competitive_landscape": competitive,
            "review_risk": review,
            "ad_performance": ad_performance,
        }

        # 计算总体健康度（加权平均）
        weights = {
            "sales_trend": 0.20,
            "traffic_health": 0.20,
            "conversion_efficiency": 0.20,
            "competitive_landscape": 0.15,
            "review_risk": 0.15,
            "ad_performance": 0.10,
        }

        health_score = sum(
            six_factors[key]["score"] * weights[key] for key in weights
        )

        # 健康等级（绿/黄/红）
        if health_score >= 80:
            health_level = "green"
        elif health_score >= 60:
            health_level = "yellow"
        else:
            health_level = "red"

        # 确定优先级
        priority = self._determine_priority(health_score, six_factors)

        # 出单词 TOP 分析
        top_keywords = self.analyze_top_keywords(metrics)

        # 销量趋势数据
        sales_trend_data = self.get_sales_trend_data(metrics)

        # 生成优化建议
        recommendations = self.generate_recommendations(six_factors)

        return {
            "asin": asin,
            "health_score": round(health_score, 1),
            "health_level": health_level,
            "six_factors": six_factors,
            "top_keywords": top_keywords,
            "sales_trend": sales_trend_data,
            "recommendations": recommendations,
            "priority": priority,
        }

    def evaluate_traffic_health(self, metrics: dict) -> dict:
        """
        评估流量健康度

        返回：
            {
                "score": float,  # 0-100
                "status": str,  # 良好/警告/危险
                "details": {...},
            }
        """
        impressions = metrics.get("impressions", 0)
        clicks = metrics.get("clicks", 0)
        ctr = metrics.get("ctr", 0)

        # 计算得分
        if impressions == 0:
            score = 0
            status = "危险"
            details = {"impressions": 0, "clicks": 0, "ctr": 0, "issue": "无曝光数据"}
        else:
            # CTR 得分（50分）
            ctr_score = min(50, (ctr / self.BENCHMARKS["ctr"]) * 50) if self.BENCHMARKS["ctr"] > 0 else 50

            # 曝光量得分（50分）
            # 假设日均 1000 曝光为基准
            impression_score = min(50, (impressions / 1000) * 50)

            score = ctr_score + impression_score

            if score >= 80:
                status = "良好"
            elif score >= 50:
                status = "警告"
            else:
                status = "危险"

            details = {
                "impressions": impressions,
                "clicks": clicks,
                "ctr": round(ctr * 100, 2),
                "ctr_status": "良好" if ctr >= self.BENCHMARKS["ctr"] else "偏低",
            }

        return {
            "score": round(score, 1),
            "status": status,
            "details": details,
        }

    def evaluate_conversion(self, metrics: dict) -> dict:
        """
        评估转化效率

        返回：
            {
                "score": float,  # 0-100
                "status": str,  # 良好/警告/危险
                "details": {...},
            }
        """
        clicks = metrics.get("clicks", 0)
        orders = metrics.get("ad_orders", 0) or metrics.get("units_sold", 0)
        cvr = metrics.get("cvr", 0)
        acos = metrics.get("acos", 0)

        if clicks == 0:
            score = 0
            status = "危险"
            details = {"cvr": 0, "acos": 0, "issue": "无点击数据"}
        else:
            # CVR 得分（50分）
            cvr_score = min(50, (cvr / self.BENCHMARKS["cvr"]) * 50) if self.BENCHMARKS["cvr"] > 0 else 50

            # ACoS 得分（50分）- ACoS 越低越好
            if acos > 0:
                acos_score = max(0, 50 - (acos - self.BENCHMARKS["acos"]) * 100)
            else:
                acos_score = 50

            score = cvr_score + acos_score

            if score >= 80:
                status = "良好"
            elif score >= 50:
                status = "警告"
            else:
                status = "危险"

            details = {
                "cvr": round(cvr * 100, 2),
                "cvr_status": "良好" if cvr >= self.BENCHMARKS["cvr"] else "偏低",
                "acos": round(acos * 100, 2),
                "acos_status": "良好" if acos <= self.BENCHMARKS["acos"] else "偏高",
            }

        return {
            "score": round(score, 1),
            "status": status,
            "details": details,
        }

    def evaluate_competitive(self, metrics: dict, competitors: list[dict]) -> dict:
        """
        评估竞争态势

        返回：
            {
                "score": float,  # 0-100
                "status": str,  # 良好/警告/危险
                "details": {...},
            }
        """
        price = metrics.get("price", 0)
        rating = metrics.get("rating", 0)
        review_count = metrics.get("review_count", 0)

        if not competitors:
            # 无竞品数据时，基于自身指标评分
            score = 50
            status = "警告"
            details = {"issue": "无竞品数据，无法对比分析"}
        else:
            # 计算竞品平均值
            avg_price = sum(c.get("price", 0) for c in competitors) / len(competitors)
            avg_rating = sum(c.get("rating", 0) for c in competitors) / len(competitors)
            avg_reviews = sum(c.get("review_count", 0) for c in competitors) / len(competitors)

            # 价格竞争力得分（30分）
            if avg_price > 0:
                price_ratio = price / avg_price
                if price_ratio <= 1:
                    price_score = 30  # 价格有优势
                else:
                    price_score = max(0, 30 - (price_ratio - 1) * 50)
            else:
                price_score = 15

            # 评分竞争力得分（40分）
            if avg_rating > 0:
                rating_ratio = rating / avg_rating
                rating_score = min(40, rating_ratio * 40)
            else:
                rating_score = 20

            # 评论数量得分（30分）
            if avg_reviews > 0:
                review_ratio = review_count / avg_reviews
                review_score = min(30, review_ratio * 30)
            else:
                review_score = 15

            score = price_score + rating_score + review_score

            if score >= 80:
                status = "良好"
            elif score >= 50:
                status = "警告"
            else:
                status = "危险"

            details = {
                "price": price,
                "avg_competitor_price": round(avg_price, 2),
                "price_status": "有优势" if price <= avg_price else "偏高",
                "rating": rating,
                "avg_competitor_rating": round(avg_rating, 2),
                "rating_status": "良好" if rating >= avg_rating else "偏低",
                "review_count": review_count,
                "avg_competitor_reviews": round(avg_reviews),
            }

        return {
            "score": round(score, 1),
            "status": status,
            "details": details,
        }

    def evaluate_review_risk(self, metrics: dict) -> dict:
        """
        评估评论风险

        返回：
            {
                "score": float,  # 0-100
                "status": str,  # 良好/警告/危险
                "details": {...},
            }
        """
        rating = metrics.get("rating", 0)
        negative_reviews = metrics.get("negative_reviews", 0)
        return_count = metrics.get("return_count", 0)
        units_sold = metrics.get("units_sold", 1)

        # 评分得分（40分）
        if rating >= self.BENCHMARKS["rating"]:
            rating_score = 40
        elif rating >= 4.0:
            rating_score = 30
        elif rating >= 3.5:
            rating_score = 20
        else:
            rating_score = 10

        # 差评率得分（30分）
        total_reviews = metrics.get("review_count", 100)  # 假设 100
        negative_rate = negative_reviews / total_reviews if total_reviews > 0 else 0
        if negative_rate <= 0.05:
            negative_score = 30
        elif negative_rate <= 0.10:
            negative_score = 20
        elif negative_rate <= 0.20:
            negative_score = 10
        else:
            negative_score = 0

        # 退货率得分（30分）
        return_rate = return_count / units_sold if units_sold > 0 else 0
        if return_rate <= self.BENCHMARKS["return_rate"]:
            return_score = 30
        elif return_rate <= 0.10:
            return_score = 20
        elif return_rate <= 0.15:
            return_score = 10
        else:
            return_score = 0

        score = rating_score + negative_score + return_score

        if score >= 80:
            status = "良好"
        elif score >= 50:
            status = "警告"
        else:
            status = "危险"

        return {
            "score": round(score, 1),
            "status": status,
            "details": {
                "rating": rating,
                "rating_status": "良好" if rating >= self.BENCHMARKS["rating"] else "偏低",
                "negative_reviews": negative_reviews,
                "negative_rate": round(negative_rate * 100, 2),
                "return_count": return_count,
                "return_rate": round(return_rate * 100, 2),
            },
        }

    def _determine_priority(self, health_score: float, traffic: dict, conversion: dict, competitive: dict, review: dict) -> str:
        """确定优化优先级"""
        # 如果有危险项，优先级为紧急
        if any(d["status"] == "危险" for d in [traffic, conversion, competitive, review]):
            return "紧急"

        # 如果健康度低于 60，优先级为重要
        if health_score < 60:
            return "重要"

        # 否则为优化
        return "优化"

    def generate_recommendations(self, analysis: dict) -> list[dict]:
        """
        生成优化建议

        返回：
            [
                {
                    "priority": "紧急/重要/优化",
                    "category": "流量/转化/竞争/评论",
                    "issue": "问题描述",
                    "suggestion": "优化建议",
                },
                ...
            ]
        """
        recommendations = []

        # 流量建议
        traffic = analysis.get("traffic", {})
        if traffic.get("status") == "危险":
            recommendations.append({
                "priority": "紧急",
                "category": "流量",
                "issue": "曝光量严重不足",
                "suggestion": "建议增加广告预算，优化关键词投放，提升 Listing 曝光",
            })
        elif traffic.get("status") == "警告":
            details = traffic.get("details", {})
            if details.get("ctr_status") == "偏低":
                recommendations.append({
                    "priority": "重要",
                    "category": "流量",
                    "issue": "点击率低于行业基准",
                    "suggestion": "优化主图和标题，提升点击率",
                })

        # 转化建议
        conversion = analysis.get("conversion", {})
        if conversion.get("status") == "危险":
            recommendations.append({
                "priority": "紧急",
                "category": "转化",
                "issue": "转化率严重偏低",
                "suggestion": "检查 Listing 详情页，优化五点描述和 A+ 内容",
            })
        elif conversion.get("status") == "警告":
            details = conversion.get("details", {})
            if details.get("acos_status") == "偏高":
                recommendations.append({
                    "priority": "重要",
                    "category": "转化",
                    "issue": f"ACoS 高于基准 {self.BENCHMARKS['acos']*100}%",
                    "suggestion": "优化否定关键词，调整出价策略",
                })

        # 竞争建议
        competitive = analysis.get("competitive", {})
        if competitive.get("status") == "危险":
            recommendations.append({
                "priority": "紧急",
                "category": "竞争",
                "issue": "竞争力不足",
                "suggestion": "分析竞品优势，优化价格策略和产品差异化",
            })

        # 评论建议
        review = analysis.get("review", {})
        if review.get("status") == "危险":
            recommendations.append({
                "priority": "紧急",
                "category": "评论",
                "issue": "评论风险较高",
                "suggestion": "关注差评原因，改善产品质量，积极处理客户投诉",
            })
        elif review.get("status") == "警告":
            details = review.get("details", {})
            if details.get("rating", 5) < self.BENCHMARKS["rating"]:
                recommendations.append({
                    "priority": "重要",
                    "category": "评论",
                    "issue": f"评分低于基准 {self.BENCHMARKS['rating']}",
                    "suggestion": "分析差评原因，提升产品和服务质量",
                })

        # 如果没有建议，添加默认建议
        if not recommendations:
            recommendations.append({
                "priority": "优化",
                "category": "综合",
                "issue": "产品状态良好",
                "suggestion": "继续保持，关注竞品动态，持续优化",
            })

        return recommendations

    def evaluate_sales_trend(self, metrics: dict) -> dict:
        """
        评估销量趋势

        返回：
            {
                "score": float,  # 0-100
                "status": str,  # 良好/警告/危险
                "details": {...},
            }
        """
        units_sold = metrics.get("units_sold", 0)
        sales_amount = metrics.get("sales_amount", 0)
        avg_units_7d = metrics.get("avg_units_7d", 0)
        sales_trend_7d = metrics.get("sales_trend_7d", 0)
        three_day_decline = metrics.get("three_day_sales_decline", False)

        # 销量得分（40分）
        if units_sold > 0:
            if avg_units_7d > 0:
                sales_ratio = units_sold / avg_units_7d
                sales_score = min(40, sales_ratio * 40)
            else:
                sales_score = 20
        else:
            sales_score = 0

        # 趋势得分（40分）
        if sales_trend_7d > 0:
            trend_score = 40  # 上升趋势
        elif sales_trend_7d == 0:
            trend_score = 25  # 平稳
        else:
            trend_score = max(0, 20 + sales_trend_7d * 10)  # 下降趋势

        # 连续下降扣分（20分）
        decline_score = 0 if three_day_decline else 20

        score = sales_score + trend_score + decline_score

        if score >= 80:
            status = "良好"
        elif score >= 50:
            status = "警告"
        else:
            status = "危险"

        return {
            "score": round(score, 1),
            "status": status,
            "details": {
                "units_sold": units_sold,
                "sales_amount": sales_amount,
                "avg_units_7d": avg_units_7d,
                "trend_7d": sales_trend_7d,
                "trend_status": "上升" if sales_trend_7d > 0 else ("平稳" if sales_trend_7d == 0 else "下降"),
                "three_day_decline": three_day_decline,
            },
        }

    def evaluate_ad_performance(self, metrics: dict) -> dict:
        """
        评估广告表现

        返回：
            {
                "score": float,  # 0-100
                "status": str,  # 良好/警告/危险
                "details": {...},
            }
        """
        impressions = metrics.get("impressions", 0)
        clicks = metrics.get("clicks", 0)
        spend = metrics.get("spend", 0)
        ad_sales = metrics.get("ad_sales", 0)
        acos = metrics.get("acos", 0)
        ad_orders = metrics.get("ad_orders", 0)

        if spend == 0:
            score = 50
            status = "警告"
            details = {"issue": "无广告花费数据"}
        else:
            # ACoS 得分（50分）
            if acos <= self.BENCHMARKS["acos"]:
                acos_score = 50
            elif acos <= self.BENCHMARKS["acos"] * 1.5:
                acos_score = 30
            else:
                acos_score = max(0, 50 - (acos - self.BENCHMARKS["acos"]) * 100)

            # ROAS 得分（50分）
            roas = ad_sales / spend if spend > 0 else 0
            if roas >= 3:
                roas_score = 50
            elif roas >= 2:
                roas_score = 35
            elif roas >= 1:
                roas_score = 20
            else:
                roas_score = 10

            score = acos_score + roas_score

            if score >= 80:
                status = "良好"
            elif score >= 50:
                status = "警告"
            else:
                status = "危险"

            details = {
                "impressions": impressions,
                "clicks": clicks,
                "spend": spend,
                "ad_sales": ad_sales,
                "acos": round(acos * 100, 2),
                "acos_status": "良好" if acos <= self.BENCHMARKS["acos"] else "偏高",
                "roas": round(roas, 2),
                "ad_orders": ad_orders,
            }

        return {
            "score": round(score, 1),
            "status": status,
            "details": details,
        }

    def analyze_top_keywords(self, metrics: dict) -> list[dict]:
        """
        出单词 TOP 分析

        返回：
            [
                {
                    "keyword": str,
                    "aba_rank": int,  # ABA 排名
                    "click_share": float,  # 点击共享
                    "conversion_share": float,  # 转化共享
                    "top3_click_share": float,  # 前三 ASIN 点击总占比
                },
                ...
            ]
        """
        # 模拟数据（实际应从亚马逊 API 获取）
        return [
            {
                "keyword": "wireless headphones",
                "aba_rank": 1500,
                "click_share": 0.08,
                "conversion_share": 0.12,
                "top3_click_share": 0.45,
            },
            {
                "keyword": "bluetooth earbuds",
                "aba_rank": 3200,
                "click_share": 0.05,
                "conversion_share": 0.08,
                "top3_click_share": 0.38,
            },
            {
                "keyword": "noise cancelling headphones",
                "aba_rank": 5800,
                "click_share": 0.03,
                "conversion_share": 0.06,
                "top3_click_share": 0.52,
            },
        ]

    def get_sales_trend_data(self, metrics: dict) -> dict:
        """
        获取销量趋势数据

        返回：
            {
                "dates": [...],
                "sales": [...],
                "revenue": [...],
            }
        """
        # 模拟数据（实际应从数据库获取）
        today = date.today()
        dates = [(today - timedelta(days=i)).isoformat() for i in range(29, -1, -1)]

        # 模拟销量数据
        import random
        random.seed(42)  # 固定随机种子，保证数据一致
        base_sales = metrics.get("units_sold", 20)
        sales = [max(0, base_sales + random.randint(-10, 10)) for _ in range(30)]
        revenue = [s * metrics.get("price", 49.99) for s in sales]

        return {
            "dates": dates,
            "sales": sales,
            "revenue": [round(r, 2) for r in revenue],
        }

    def _determine_priority(self, health_score: float, six_factors: dict) -> str:
        """确定优化优先级"""
        # 如果有危险项，优先级为紧急
        if any(f.get("status") == "危险" for f in six_factors.values()):
            return "紧急"

        # 如果健康度低于 60，优先级为重要
        if health_score < 60:
            return "重要"

        # 否则为优化
        return "优化"

    def generate_demo_data(self, asin: str) -> dict:
        """
        生成演示数据（用于测试）

        返回与 diagnose 相同格式的数据
        """
        demo_metrics = {
            "asin": asin,
            "impressions": 5000,
            "clicks": 150,
            "units_sold": 25,
            "ad_orders": 20,
            "spend": 75.0,
            "ad_sales": 500.0,
            "ctr": 0.03,
            "cvr": 0.13,
            "acos": 0.15,
            "price": 49.99,
            "rating": 4.5,
            "review_count": 850,
            "negative_reviews": 12,
            "return_count": 5,
            "available_inventory": 200,
            "inventory_days": 45,
        }

        demo_competitors = [
            {"price": 59.99, "rating": 4.6, "review_count": 1200},
            {"price": 39.99, "rating": 4.2, "review_count": 600},
            {"price": 54.99, "rating": 4.4, "review_count": 950},
        ]

        return self.diagnose(asin, demo_metrics, demo_competitors)
