"""Tests for backfill_stance_from_claims helpers (Wave7 / Issue #312)."""

from __future__ import annotations


class TestExtractAnalystName:
    """_extract_analyst_name() のテスト."""

    def test_正常系_アナリスト名を抽出できる(self) -> None:
        from scripts.backfill_stance_from_claims import _extract_analyst_name

        content = "JP Morgan rates Telkom Buy with TP 5000"
        assert _extract_analyst_name(content) == "JP Morgan"

    def test_正常系_複合名を抽出できる(self) -> None:
        from scripts.backfill_stance_from_claims import _extract_analyst_name

        content = "Goldman Sachs rates ISAT Overweight with TP 10000"
        assert _extract_analyst_name(content) == "Goldman Sachs"

    def test_正常系_パターン不一致はNoneを返す(self) -> None:
        from scripts.backfill_stance_from_claims import _extract_analyst_name

        assert _extract_analyst_name("some other content") is None
        assert _extract_analyst_name("") is None

    def test_正常系_小文字始まりはパターン不一致(self) -> None:
        # パターンは大文字始まりを要求する
        from scripts.backfill_stance_from_claims import _extract_analyst_name

        assert _extract_analyst_name("morgan rates ISAT Buy") is None


class TestRatingToSentiment:
    """_rating_to_sentiment() のテスト."""

    def test_正常系_Buyはbullish(self) -> None:
        from scripts.backfill_stance_from_claims import _rating_to_sentiment

        assert _rating_to_sentiment("Buy") == "bullish"
        assert _rating_to_sentiment("Overweight") == "bullish"
        assert _rating_to_sentiment("Outperform") == "bullish"

    def test_正常系_Holdはneutral(self) -> None:
        from scripts.backfill_stance_from_claims import _rating_to_sentiment

        assert _rating_to_sentiment("Hold") == "neutral"
        assert _rating_to_sentiment("Neutral") == "neutral"
        assert _rating_to_sentiment("Equal-weight") == "neutral"

    def test_正常系_Sellはbearish(self) -> None:
        from scripts.backfill_stance_from_claims import _rating_to_sentiment

        assert _rating_to_sentiment("Sell") == "bearish"
        assert _rating_to_sentiment("Underweight") == "bearish"
        assert _rating_to_sentiment("Underperform") == "bearish"

    def test_正常系_未知のratingはneutralにフォールバック(self) -> None:
        from scripts.backfill_stance_from_claims import _rating_to_sentiment

        assert _rating_to_sentiment("Unknown") == "neutral"
        assert _rating_to_sentiment("") == "neutral"


class TestBuildBackfillData:
    """_build_backfill_data() のテスト."""

    def _make_claim(
        self,
        content: str = "JP Morgan rates Telkom Buy with TP 5000",
        rating: str = "Buy",
        target_price: float | None = 5000.0,
        entity_name: str = "Telkom Indonesia",
        entity_id: str = "ent-001",
        claim_id: str = "claim-001",
        source_id: str = "src-001",
    ) -> dict:
        return {
            "content": content,
            "rating": rating,
            "target_price": target_price,
            "entity_name": entity_name,
            "entity_id": entity_id,
            "claim_id": claim_id,
            "source_id": source_id,
        }

    def test_正常系_有効なclaimからStancetとAuthorを生成できる(self) -> None:
        from scripts.backfill_stance_from_claims import _build_backfill_data

        claims = [self._make_claim()]
        result = _build_backfill_data(claims)

        assert len(result["authors"]) == 1
        assert result["authors"][0]["name"] == "JP Morgan"
        assert result["authors"][0]["author_type"] == "sell_side"

        assert len(result["stances"]) == 1
        assert result["stances"][0]["rating"] == "Buy"
        assert result["stances"][0]["sentiment"] == "bullish"
        assert result["stances"][0]["target_price"] == 5000.0

    def test_正常系_リレーションが正しく生成される(self) -> None:
        from scripts.backfill_stance_from_claims import _build_backfill_data

        claims = [self._make_claim()]
        result = _build_backfill_data(claims)

        assert len(result["holds_stance"]) == 1
        assert result["holds_stance"][0]["type"] == "HOLDS_STANCE"
        assert len(result["on_entity"]) == 1
        assert result["on_entity"][0]["type"] == "ON_ENTITY"
        assert len(result["based_on"]) == 1
        assert result["based_on"][0]["type"] == "BASED_ON"
        assert len(result["authored_by"]) == 1
        assert result["authored_by"][0]["type"] == "AUTHORED_BY"

    def test_正常系_entity_nameなしのclaimはスキップされる(self) -> None:
        from scripts.backfill_stance_from_claims import _build_backfill_data

        claims = [self._make_claim(entity_name="", entity_id="")]
        result = _build_backfill_data(claims)

        assert result["authors"] == []
        assert result["stances"] == []

    def test_正常系_アナリスト抽出できないclaimはスキップされる(self) -> None:
        from scripts.backfill_stance_from_claims import _build_backfill_data

        claims = [self._make_claim(content="no analyst here")]
        result = _build_backfill_data(claims)

        assert result["stances"] == []

    def test_正常系_authored_byが重複排除される(self) -> None:
        from scripts.backfill_stance_from_claims import _build_backfill_data

        # 同じ source_id + author の組み合わせが2件
        claims = [
            self._make_claim(claim_id="claim-001"),
            self._make_claim(
                claim_id="claim-002",
                content="JP Morgan rates Indosat Buy with TP 2000",
                entity_name="Indosat",
                entity_id="ent-002",
            ),
        ]
        result = _build_backfill_data(claims)

        # authored_by は src-001→JP Morgan のペアが1件のみ
        assert len(result["authored_by"]) == 1

    def test_正常系_空のclaimsは空の結果を返す(self) -> None:
        from scripts.backfill_stance_from_claims import _build_backfill_data

        result = _build_backfill_data([])

        assert result["authors"] == []
        assert result["stances"] == []
        assert result["holds_stance"] == []
        assert result["on_entity"] == []
        assert result["based_on"] == []
        assert result["authored_by"] == []

    def test_正常系_複数アナリストが独立して生成される(self) -> None:
        from scripts.backfill_stance_from_claims import _build_backfill_data

        claims = [
            self._make_claim(
                content="JP Morgan rates Telkom Buy with TP 5000",
                entity_name="Telkom",
                entity_id="ent-001",
                claim_id="c1",
                source_id="src-1",
            ),
            self._make_claim(
                content="Morgan Stanley rates Telkom Hold with TP 4500",
                rating="Hold",
                target_price=4500.0,
                entity_name="Telkom",
                entity_id="ent-001",
                claim_id="c2",
                source_id="src-2",
            ),
        ]
        result = _build_backfill_data(claims)

        assert len(result["authors"]) == 2
        author_names = {a["name"] for a in result["authors"]}
        assert "JP Morgan" in author_names
        assert "Morgan Stanley" in author_names
