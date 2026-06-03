"""Amazon Listing 优化规则生成器。"""
from __future__ import annotations

import re
from typing import Any


class ListingOptimizer:
    """基于产品信息和关键词生成 Listing 内容与质量评分。"""

    _INTENT_TERMS = [
        "portable",
        "handheld",
        "mini",
        "usb",
        "rechargeable",
        "travel",
        "quiet",
        "battery",
        "office",
        "outdoor",
        "personal",
        "lightweight",
        "durable",
        "easy clean",
        "space saving",
    ]

    _BANNED_CLAIMS = [
        "best",
        "#1",
        "guaranteed",
        "cure",
        "medical",
        "free shipping",
        "limited time",
    ]

    def optimize(
        self,
        *,
        product_description: str,
        keywords: str | list[str] | None = None,
        marketplace: str = "US",
        competitor_asin: str = "",
    ) -> dict[str, Any]:
        description = self._clean_text(product_description)
        if not description:
            raise ValueError("产品信息不能为空")

        normalized_keywords = self._normalize_keywords(keywords)
        signals = self._extract_signals(description, normalized_keywords)
        listing = self._build_listing(description, normalized_keywords, signals)
        keyword_coverage = self._build_keyword_coverage(normalized_keywords, listing)
        quality_score = self._build_quality_score(listing, keyword_coverage, description)

        return {
            "marketplace": (marketplace or "US").upper(),
            "competitor_asin": competitor_asin.strip(),
            "listing": listing,
            "quality_score": quality_score,
            "keyword_coverage": keyword_coverage,
            "generated_by_ai": False,
        }

    def _normalize_keywords(self, keywords: str | list[str] | None) -> list[str]:
        if isinstance(keywords, list):
            raw_items = keywords
        else:
            raw_items = re.split(r"[,，\n;；]+", keywords or "")

        seen: set[str] = set()
        normalized = []
        for item in raw_items:
            keyword = self._clean_text(str(item)).lower()
            if keyword and keyword not in seen:
                seen.add(keyword)
                normalized.append(keyword)
        return normalized[:18]

    def _extract_signals(self, description: str, keywords: list[str]) -> dict[str, list[str] | str]:
        lower_description = description.lower()
        terms = []
        for term in self._INTENT_TERMS:
            if term in lower_description:
                terms.append(term)

        if not terms:
            terms = self._description_terms(description)[:5] or ["daily use", "easy to use", "reliable"]

        product_name = self._infer_product_name(description, keywords)
        return {
            "product_name": product_name,
            "terms": terms[:8],
            "benefits": self._build_benefit_terms(description, terms),
        }

    def _build_listing(
        self,
        description: str,
        keywords: list[str],
        signals: dict[str, list[str] | str],
    ) -> dict[str, Any]:
        product_name = str(signals["product_name"])
        terms = [str(term) for term in signals["terms"]]
        benefits = [str(benefit) for benefit in signals["benefits"]]
        relevant_keywords = [
            keyword for keyword in keywords if self._keyword_relevance(keyword, description, terms) >= 0.5
        ]

        title_parts = []
        for item in [*relevant_keywords[:3], product_name, *terms[:4]]:
            label = self._title_case(item)
            if label and label.lower() not in {part.lower() for part in title_parts}:
                title_parts.append(label)
        title = self._limit_text(", ".join(title_parts), 200)

        bullets = [
            self._limit_text(
                f"{self._lead('Powerful Performance', terms)} - Designed for {benefits[0]}, "
                f"this {product_name} delivers dependable everyday performance.",
                240,
            ),
            self._limit_text(
                f"{self._lead('Portable Design', terms)} - Compact construction makes it easy "
                f"to carry, store, and use for {benefits[1]}.",
                240,
            ),
            self._limit_text(
                f"{self._lead('Easy Everyday Use', terms)} - Simple operation supports fast setup "
                f"and consistent results at home, work, or on the go.",
                240,
            ),
            self._limit_text(
                f"{self._lead('Built for Comfort', terms)} - Thoughtful details help reduce hassle "
                f"while keeping the product practical for repeated use.",
                240,
            ),
            self._limit_text(
                f"{self._lead('Versatile Application', terms)} - A useful choice for {benefits[2]}, "
                f"with balanced value for daily Amazon shoppers.",
                240,
            ),
        ]

        description_body = self._limit_text(
            f"Upgrade your routine with this {product_name}. {description} "
            f"It is built for {', '.join(benefits[:3])} and optimized around shopper search intent "
            f"including {', '.join(relevant_keywords[:5] or terms[:5])}.",
            1900,
        )
        backend_terms = self._build_backend_terms(relevant_keywords, terms, product_name)

        return {
            "title": title,
            "bullets": bullets,
            "description": description_body,
            "search_terms": " ".join(backend_terms),
            "backend_terms": backend_terms,
        }

    def _build_keyword_coverage(self, keywords: list[str], listing: dict[str, Any]) -> dict[str, Any]:
        if not keywords:
            return {"coverage_rate": 0, "items": []}

        title = listing["title"].lower()
        bullets = " ".join(listing["bullets"]).lower()
        description = listing["description"].lower()
        search_terms = listing["search_terms"].lower()

        items = []
        covered_score = 0.0
        for keyword in keywords:
            locations = []
            if keyword in title:
                locations.append("标题")
            if keyword in bullets:
                locations.append("卖点")
            if keyword in description:
                locations.append("描述")
            if keyword in search_terms:
                locations.append("后台词")

            if locations:
                status = "已覆盖"
                covered_score += 1
            else:
                tokens = self._keyword_tokens(keyword)
                combined = f"{title} {bullets} {description} {search_terms}"
                matched_tokens = sum(1 for token in tokens if token in combined)
                if tokens and matched_tokens / len(tokens) >= 0.5:
                    status = "部分覆盖"
                    covered_score += 0.5
                    locations = ["分词覆盖"]
                else:
                    status = "未覆盖"

            items.append({"keyword": keyword, "status": status, "locations": locations})

        return {
            "coverage_rate": round(covered_score / len(keywords) * 100),
            "items": items,
        }

    def _build_quality_score(
        self,
        listing: dict[str, Any],
        keyword_coverage: dict[str, Any],
        source_description: str,
    ) -> dict[str, Any]:
        title_length = len(listing["title"])
        bullet_count = len(listing["bullets"])
        description_length = len(listing["description"])
        combined = " ".join([listing["title"], *listing["bullets"], listing["description"]]).lower()
        banned_hits = sum(1 for claim in self._BANNED_CLAIMS if claim in combined)

        dimensions = [
            {"key": "keyword_coverage", "label": "关键词覆盖", "score": keyword_coverage["coverage_rate"]},
            {
                "key": "title_quality",
                "label": "标题质量",
                "score": self._bounded_score(100 - abs(145 - title_length) * 0.45),
            },
            {
                "key": "readability",
                "label": "可读性",
                "score": self._bounded_score(92 - max(0, self._avg_sentence_length(listing) - 28) * 1.4),
            },
            {
                "key": "benefit_clarity",
                "label": "卖点清晰",
                "score": self._bounded_score(70 + min(20, bullet_count * 4) + self._feature_density(source_description)),
            },
            {
                "key": "differentiation",
                "label": "竞争差异化",
                "score": self._bounded_score(68 + self._feature_density(combined) * 1.5),
            },
            {
                "key": "seo_compliance",
                "label": "SEO 合规",
                "score": self._bounded_score(96 - banned_hits * 18 - (10 if title_length > 200 else 0)),
            },
            {
                "key": "structure",
                "label": "结构完整性",
                "score": self._bounded_score(40 + bullet_count * 8 + min(20, description_length / 70)),
            },
            {
                "key": "search_terms",
                "label": "后台词质量",
                "score": self._bounded_score(85 if len(listing["search_terms"]) <= 249 else 68),
            },
        ]
        overall_score = round(sum(item["score"] for item in dimensions) / len(dimensions))
        return {
            "overall_score": overall_score,
            "grade": self._grade(overall_score),
            "dimensions": dimensions,
        }

    def _build_backend_terms(self, keywords: list[str], terms: list[str], product_name: str) -> list[str]:
        candidates = [*keywords, *terms, *self._keywords_to_terms([product_name])]
        output = []
        seen: set[str] = set()
        total_length = 0
        for candidate in candidates:
            phrase = self._clean_text(candidate).lower()
            if not phrase or phrase in seen:
                continue
            next_length = total_length + len(phrase) + (1 if output else 0)
            if next_length > 249:
                continue
            seen.add(phrase)
            output.append(phrase)
            total_length = next_length
        return output

    def _build_benefit_terms(self, description: str, terms: list[str]) -> list[str]:
        benefits = []
        mapping = {
            "travel": "travel and commuting",
            "portable": "bags, desks, and compact spaces",
            "quiet": "quiet work areas",
            "rechargeable": "longer use between charges",
            "usb": "simple USB-powered convenience",
            "mini": "small-space storage",
            "handheld": "handheld daily use",
            "battery": "cordless use cases",
        }
        for term in terms:
            if term in mapping:
                benefits.append(mapping[term])
        if not benefits:
            benefits = self._split_feature_phrases(description)[:3]
        return (benefits + ["home use", "office use", "gift-ready daily needs"])[:3]

    def _infer_product_name(self, description: str, keywords: list[str]) -> str:
        if keywords:
            description_lower = description.lower()
            relevant_keywords = [
                keyword
                for keyword in keywords
                if len(keyword.split()) >= 2
                and all(token in description_lower for token in self._keyword_tokens(keyword))
            ]
            if relevant_keywords:
                return min(relevant_keywords, key=len)

        words = re.findall(r"[A-Za-z][A-Za-z0-9+-]*", description)
        if len(words) >= 3:
            return " ".join(words[:4]).lower()
        return "amazon product"

    def _keywords_to_terms(self, keywords: list[str]) -> list[str]:
        terms = []
        for keyword in keywords:
            terms.extend(self._keyword_tokens(keyword))
        return terms

    def _description_terms(self, description: str) -> list[str]:
        stop_words = {"with", "made", "from", "that", "this", "and", "the", "for", "use"}
        terms = []
        for token in re.findall(r"[a-z0-9]+", description.lower()):
            if len(token) > 2 and token not in stop_words and token not in terms:
                terms.append(token)
        return terms

    def _keyword_relevance(self, keyword: str, description: str, terms: list[str]) -> float:
        tokens = self._keyword_tokens(keyword)
        if not tokens:
            return 0
        search_space = f"{description.lower()} {' '.join(terms).lower()}"
        matched = sum(1 for token in tokens if token in search_space)
        return matched / len(tokens)

    def _keyword_tokens(self, keyword: str) -> list[str]:
        return [token for token in re.findall(r"[a-z0-9]+", keyword.lower()) if len(token) > 2]

    def _feature_density(self, text: str) -> int:
        lower_text = text.lower()
        return min(20, sum(4 for term in self._INTENT_TERMS if term in lower_text))

    def _avg_sentence_length(self, listing: dict[str, Any]) -> float:
        text = ". ".join([listing["title"], *listing["bullets"], listing["description"]])
        sentences = [sentence for sentence in re.split(r"[.!?。！？]+", text) if sentence.strip()]
        if not sentences:
            return 0
        return sum(len(sentence.split()) for sentence in sentences) / len(sentences)

    def _lead(self, fallback: str, terms: list[str]) -> str:
        if "quiet" in terms:
            return "QUIET & COMFORTABLE"
        if "rechargeable" in terms or "usb" in terms:
            return "USB RECHARGEABLE"
        if "portable" in terms or "mini" in terms:
            return "LIGHTWEIGHT & PORTABLE"
        return fallback.upper()

    def _split_feature_phrases(self, text: str) -> list[str]:
        phrases = [self._clean_text(part).lower() for part in re.split(r"[,，.;；。]+", text)]
        return [phrase for phrase in phrases if phrase][:6]

    def _title_case(self, text: str) -> str:
        small_words = {"and", "or", "for", "with", "of", "the", "to"}
        words = []
        for word in self._clean_text(text).split():
            lower = word.lower()
            words.append(lower if lower in small_words else word[:1].upper() + word[1:])
        return " ".join(words)

    def _limit_text(self, text: str, max_length: int) -> str:
        cleaned = self._clean_text(text)
        if len(cleaned) <= max_length:
            return cleaned
        return cleaned[: max_length - 1].rstrip(" ,.;-") + "..."

    def _clean_text(self, value: str) -> str:
        return re.sub(r"\s+", " ", str(value or "")).strip()

    def _bounded_score(self, value: float) -> int:
        return max(0, min(100, round(value)))

    def _grade(self, score: int) -> str:
        if score >= 90:
            return "A"
        if score >= 80:
            return "B"
        if score >= 70:
            return "C"
        if score >= 60:
            return "D"
        return "E"
