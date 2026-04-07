"""みつき占術エンジン — Venus星座 × 数秘術LP の144パターン分析.

入力: 生年月日（YYYY-MM-DD）+ MBTI（任意）
出力: LP, Personal Year, Venus星座, 144タイプ名, 恋愛パターン解説

Decision refs:
  - dec-2026-04-07-venus-only-engine
  - dec-2026-04-07-numerology-input-plan-a
  - dec-2026-04-07-hide-divination-systems
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import swisseph as swe

from utils_core.logging.config import get_logger

logger = get_logger(__name__)

# --- 定数 ---

ZODIAC_SIGNS = [
    "牡羊座", "牡牛座", "双子座", "蟹座", "獅子座", "乙女座",
    "天秤座", "蠍座", "射手座", "山羊座", "水瓶座", "魚座",
]

ZODIAC_EN = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]

LP_NUMBERS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 22, 33]


# --- Venus計算 ---

def calc_venus_sign(birth_date: date) -> dict:
    """生年月日からVenus星座を計算する."""
    swe.set_ephe_path("")
    jd = swe.julday(birth_date.year, birth_date.month, birth_date.day, 12.0)
    pos = swe.calc_ut(jd, swe.VENUS)
    degree = pos[0][0]
    sign_idx = int(degree // 30)
    return {
        "venus_degree": round(degree, 2),
        "venus_sign_idx": sign_idx,
        "venus_sign_ja": ZODIAC_SIGNS[sign_idx],
        "venus_sign_en": ZODIAC_EN[sign_idx],
    }


# --- 数秘術 ---

def _reduce_to_single(n: int) -> int:
    """マスターナンバー(11,22,33)を保持しつつ一桁に縮約."""
    while n > 9 and n not in (11, 22, 33):
        n = sum(int(d) for d in str(n))
    return n


def calc_life_path(birth_date: date) -> int:
    """生年月日からライフパスナンバーを計算する."""
    digits = f"{birth_date.year:04d}{birth_date.month:02d}{birth_date.day:02d}"
    total = sum(int(d) for d in digits)
    return _reduce_to_single(total)


def calc_personal_year(birth_date: date, target_year: int | None = None) -> int:
    """パーソナルイヤーナンバーを計算する."""
    if target_year is None:
        target_year = date.today().year
    digits = f"{target_year:04d}{birth_date.month:02d}{birth_date.day:02d}"
    total = sum(int(d) for d in digits)
    return _reduce_to_single(total)


# --- 144タイプ命名体系 ---

# LP × Venus の「愛のタイプ名」
# 表面に占術名を出さず、恋愛パターン名として提示する
# dec-2026-04-07-hide-divination-systems に準拠

TYPE_NAMES: dict[tuple[int, int], str] = {}

# LP別の恋愛コアテーマ
LP_LOVE_THEMES = {
    1:  {"theme": "先駆者の愛", "keyword": "リード", "shadow": "支配"},
    2:  {"theme": "調和の愛", "keyword": "共感", "shadow": "依存"},
    3:  {"theme": "表現者の愛", "keyword": "言葉", "shadow": "散漫"},
    4:  {"theme": "堅実な愛", "keyword": "安定", "shadow": "束縛"},
    5:  {"theme": "自由な愛", "keyword": "冒険", "shadow": "逃避"},
    6:  {"theme": "献身の愛", "keyword": "世話", "shadow": "犠牲"},
    7:  {"theme": "探求者の愛", "keyword": "内省", "shadow": "孤立"},
    8:  {"theme": "情熱の愛", "keyword": "力", "shadow": "支配"},
    9:  {"theme": "博愛の愛", "keyword": "慈悲", "shadow": "理想化"},
    11: {"theme": "直感の愛", "keyword": "霊感", "shadow": "過敏"},
    22: {"theme": "創造者の愛", "keyword": "構築", "shadow": "完璧主義"},
    33: {"theme": "癒し手の愛", "keyword": "奉仕", "shadow": "自己犠牲"},
}

# Venus星座別の愛し方スタイル
VENUS_LOVE_STYLES = {
    0:  {"style": "情熱直球", "desire": "征服する恋", "fear": "退屈"},
    1:  {"style": "じっくり溺愛", "desire": "感覚の安心", "fear": "変化"},
    2:  {"style": "言葉で繋がる", "desire": "知的な刺激", "fear": "沈黙"},
    3:  {"style": "包み込む愛", "desire": "心の居場所", "fear": "拒絶"},
    4:  {"style": "ドラマティック", "desire": "特別扱い", "fear": "無関心"},
    5:  {"style": "尽くす愛", "desire": "完璧な関係", "fear": "不完全"},
    6:  {"style": "対等なパートナー", "desire": "美しい調和", "fear": "対立"},
    7:  {"style": "深く溶け合う", "desire": "魂の融合", "fear": "裏切り"},
    8:  {"style": "自由な冒険愛", "desire": "成長する関係", "fear": "束縛"},
    9:  {"style": "静かな献身", "desire": "信頼の証明", "fear": "軽薄さ"},
    10: {"style": "ユニークな繋がり", "desire": "知性の共有", "fear": "平凡"},
    11: {"style": "夢見る愛", "desire": "理想の融合", "fear": "現実"},
}


def _build_type_name(lp: int, venus_idx: int) -> str:
    """LP×Venusから144タイプ名を生成する."""
    lp_theme = LP_LOVE_THEMES[lp]
    venus_style = VENUS_LOVE_STYLES[venus_idx]
    return f"{lp_theme['keyword']}×{venus_style['desire']}"


def _build_type_description(lp: int, venus_idx: int) -> str:
    """タイプの恋愛パターン解説を生成する."""
    lt = LP_LOVE_THEMES[lp]
    vs = VENUS_LOVE_STYLES[venus_idx]
    return (
        f"あなたの恋愛パターンは「{lt['theme']}」×「{vs['style']}」。"
        f"愛し方の軸は「{lt['keyword']}」で、相手に求めるのは「{vs['desire']}」。"
        f"うまくいかない時のパターンは「{lt['shadow']}」と「{vs['fear']}」が重なるとき。"
    )


def build_all_144_types() -> list[dict]:
    """144タイプ全パターンを生成する."""
    types = []
    for lp in LP_NUMBERS:
        for v_idx in range(12):
            type_name = _build_type_name(lp, v_idx)
            types.append({
                "lp": lp,
                "venus_sign_idx": v_idx,
                "venus_sign_ja": ZODIAC_SIGNS[v_idx],
                "type_name": type_name,
                "description": _build_type_description(lp, v_idx),
                "lp_theme": LP_LOVE_THEMES[lp],
                "venus_style": VENUS_LOVE_STYLES[v_idx],
            })
    return types


# --- 統合分析 ---

def analyze(birth_date: date, mbti: str | None = None) -> dict:
    """生年月日から恋愛パターン分析を実行する."""
    venus = calc_venus_sign(birth_date)
    lp = calc_life_path(birth_date)
    py = calc_personal_year(birth_date)

    type_name = _build_type_name(lp, venus["venus_sign_idx"])
    description = _build_type_description(lp, venus["venus_sign_idx"])

    result = {
        "birth_date": birth_date.isoformat(),
        "type_name": type_name,
        "description": description,
        "numerology": {
            "life_path": lp,
            "personal_year": py,
            "lp_theme": LP_LOVE_THEMES[lp],
        },
        "venus": venus,
        "venus_style": VENUS_LOVE_STYLES[venus["venus_sign_idx"]],
    }

    if mbti:
        result["mbti"] = mbti.upper()

    logger.info(
        "Analysis complete",
        birth_date=birth_date.isoformat(),
        lp=lp,
        venus=venus["venus_sign_ja"],
        type_name=type_name,
    )
    return result


# --- CLI ---

def main() -> None:
    parser = argparse.ArgumentParser(description="みつき占術エンジン")
    sub = parser.add_subparsers(dest="command")

    # analyze
    p_analyze = sub.add_parser("analyze", help="生年月日から恋愛パターン分析")
    p_analyze.add_argument("birth_date", help="生年月日 (YYYY-MM-DD)")
    p_analyze.add_argument("--mbti", help="MBTIタイプ (任意)")

    # types
    p_types = sub.add_parser("types", help="144タイプ全パターンを出力")
    p_types.add_argument("--output", "-o", help="出力先JSONファイル")

    args = parser.parse_args()

    if args.command == "analyze":
        bd = date.fromisoformat(args.birth_date)
        result = analyze(bd, mbti=args.mbti)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.command == "types":
        types = build_all_144_types()
        output = json.dumps(types, ensure_ascii=False, indent=2)
        if args.output:
            Path(args.output).write_text(output)
            print(f"144 types written to {args.output}")
        else:
            print(output[:2000])
            print(f"\n... ({len(types)} types total)")

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
