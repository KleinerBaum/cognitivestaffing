"""Visual market insights for selected requirements."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping, Sequence

import streamlit as st

from config_loader import load_json
from utils.i18n import tr


@dataclass
class SkillMarketRecord:
    """Prepared data point for the visualization."""

    skill: str
    normalized_skill: str
    salary_delta_pct: float
    availability_index: float
    has_benchmark: bool


_DEFAULT_SKILL_MARKET_DATA: dict[str, dict[str, object]] = {
    "python": {
        "aliases": ["python"],
        "salary_delta_pct": 6.5,
        "availability_index": 42.0,
    },
    "java": {
        "aliases": ["java"],
        "salary_delta_pct": 5.0,
        "availability_index": 48.0,
    },
    "go": {
        "aliases": ["go", "golang"],
        "salary_delta_pct": 9.0,
        "availability_index": 30.0,
    },
    "aws": {
        "aliases": ["aws", "amazon web services"],
        "salary_delta_pct": 8.0,
        "availability_index": 34.0,
    },
    "azure": {
        "aliases": ["azure", "microsoft azure"],
        "salary_delta_pct": 7.0,
        "availability_index": 40.0,
    },
    "kubernetes": {
        "aliases": ["kubernetes", "k8s"],
        "salary_delta_pct": 7.5,
        "availability_index": 32.0,
    },
    "react": {
        "aliases": ["react", "react.js"],
        "salary_delta_pct": 4.0,
        "availability_index": 55.0,
    },
    "communication": {
        "aliases": ["communication", "kommunikation"],
        "salary_delta_pct": 1.0,
        "availability_index": 70.0,
    },
    "leadership": {
        "aliases": ["leadership", "fuehrung"],
        "salary_delta_pct": 2.0,
        "availability_index": 60.0,
    },
    "project management": {
        "aliases": ["project management", "projektmanagement"],
        "salary_delta_pct": 3.0,
        "availability_index": 65.0,
    },
    "machine learning": {
        "aliases": ["machine learning", "ml"],
        "salary_delta_pct": 10.0,
        "availability_index": 28.0,
    },
    "data engineering": {
        "aliases": ["data engineering", "data pipelines"],
        "salary_delta_pct": 7.5,
        "availability_index": 38.0,
    },
    "english": {
        "aliases": ["english", "englisch"],
        "salary_delta_pct": 0.0,
        "availability_index": 82.0,
    },
    "german": {
        "aliases": ["german", "deutsch"],
        "salary_delta_pct": 3.5,
        "availability_index": 55.0,
    },
    "french": {
        "aliases": ["french", "franzoesisch"],
        "salary_delta_pct": 2.0,
        "availability_index": 52.0,
    },
    "spanish": {
        "aliases": ["spanish", "spanisch"],
        "salary_delta_pct": 1.5,
        "availability_index": 58.0,
    },
}


_SKILL_SANITIZE_PATTERN = re.compile(r"[^a-z0-9äöüß\+]+", re.IGNORECASE)


def _as_list(value: object) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if isinstance(item, str) and item.strip()]
    if isinstance(value, str) and value.strip():
        return [value]
    return []


def _normalize_skill_label(value: str) -> str:
    cleaned = value.lower().replace("&", " ")
    cleaned = cleaned.replace("/", " ")
    cleaned = cleaned.replace("-", " ")
    cleaned = cleaned.replace("+", " plus ")
    cleaned = _SKILL_SANITIZE_PATTERN.sub(" ", cleaned)
    return " ".join(cleaned.split())


def _load_skill_market_data() -> dict[str, dict[str, object]]:
    raw_data = load_json("skill_market_insights.json", fallback=_DEFAULT_SKILL_MARKET_DATA)
    if not isinstance(raw_data, Mapping):
        return dict(_DEFAULT_SKILL_MARKET_DATA)
    prepared: dict[str, dict[str, object]] = {}
    for key, value in raw_data.items():
        if not isinstance(key, str) or not isinstance(value, Mapping):
            continue
        normalized_key = _normalize_skill_label(key)
        if not normalized_key:
            continue
        aliases = [_normalize_skill_label(item) for item in _as_list(value.get("aliases"))]
        salary_delta = value.get("salary_delta_pct", 0)
        availability = value.get("availability_index", 50)
        try:
            salary_delta_float = float(salary_delta)
        except (TypeError, ValueError):
            salary_delta_float = 0.0
        try:
            availability_float = float(availability)
        except (TypeError, ValueError):
            availability_float = 50.0
        prepared[normalized_key] = {
            "aliases": [alias for alias in aliases if alias],
            "salary_delta_pct": float(round(salary_delta_float, 2)),
            "availability_index": float(min(100.0, max(0.0, availability_float))),
        }
    return prepared or dict(_DEFAULT_SKILL_MARKET_DATA)


def _resolve_entry(
    normalized_skill: str,
    dataset: Mapping[str, dict[str, object]],
) -> dict[str, object] | None:
    if normalized_skill in dataset:
        return dataset[normalized_skill]
    for key, entry in dataset.items():
        aliases = entry.get("aliases", [])
        if not isinstance(aliases, list):
            continue
        alias_matches = [alias for alias in aliases if alias]
        if normalized_skill in alias_matches:
            return entry
        for alias in alias_matches:
            if alias and (normalized_skill.startswith(alias) or alias in normalized_skill):
                return entry
    return None


def prepare_skill_market_records(
    skills: Sequence[str],
    *,
    dataset: Mapping[str, dict[str, object]] | None = None,
) -> list[SkillMarketRecord]:
    """Normalize selected skills and enrich them with market data."""

    dataset = dataset or _load_skill_market_data()
    seen: set[str] = set()
    records: list[SkillMarketRecord] = []
    for raw_skill in skills:
        if not isinstance(raw_skill, str):
            continue
        cleaned = raw_skill.strip()
        if not cleaned:
            continue
        normalized = _normalize_skill_label(cleaned)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        entry = _resolve_entry(normalized, dataset)
        if entry is None:
            records.append(
                SkillMarketRecord(
                    skill=cleaned,
                    normalized_skill=normalized,
                    salary_delta_pct=0.0,
                    availability_index=50.0,
                    has_benchmark=False,
                )
            )
            continue
        salary_delta = float(entry.get("salary_delta_pct", 0.0) or 0.0)
        availability = float(entry.get("availability_index", 50.0) or 50.0)
        records.append(
            SkillMarketRecord(
                skill=cleaned,
                normalized_skill=normalized,
                salary_delta_pct=salary_delta,
                availability_index=min(100.0, max(0.0, availability)),
                has_benchmark=True,
            )
        )
    records.sort(key=lambda record: (record.has_benchmark, record.salary_delta_pct), reverse=True)
    return records


def build_skill_market_chart_spec(
    records: Sequence[SkillMarketRecord],
    *,
    lang: str,
) -> dict[str, object]:
    """Create a Vega-Lite spec visualising salary and availability impact."""

    benchmark_label = tr("Benchmark", "Benchmark", lang=lang)
    fallback_label = tr("Fallback", "Fallback", lang=lang)
    values: list[dict[str, object]] = []
    for record in records:
        bubble_size = 80.0 - record.availability_index * 0.4
        bubble_size = max(24.0, bubble_size)
        values.append(
            {
                "skill": record.skill,
                "salary_delta_pct": round(record.salary_delta_pct, 2),
                "availability_index": round(record.availability_index, 2),
                "source": benchmark_label if record.has_benchmark else fallback_label,
                "bubble_size": round(bubble_size, 2),
                "salary_text": f"{record.salary_delta_pct:+.1f}%",
                "availability_text": f"{record.availability_index:.0f}/100",
            }
        )
    x_title = tr(
        "Verfügbarkeit (100 = großer Talentpool)",
        "Availability (100 = large talent pool)",
        lang=lang,
    )
    y_title = tr(
        "Gehaltsimpact vs. Basis (%)",
        "Salary impact vs. baseline (%)",
        lang=lang,
    )
    legend_title = tr("Datenbasis", "Data source", lang=lang)
    tooltip_salary = tr("Gehaltsimpact", "Salary impact", lang=lang)
    tooltip_availability = tr("Verfügbarkeit", "Availability", lang=lang)

    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "data": {"values": values},
        "mark": {"type": "circle", "tooltip": True},
        "encoding": {
            "x": {
                "field": "availability_index",
                "type": "quantitative",
                "scale": {"domain": [0, 100]},
                "axis": {"title": x_title},
            },
            "y": {
                "field": "salary_delta_pct",
                "type": "quantitative",
                "axis": {"title": y_title},
            },
            "size": {
                "field": "bubble_size",
                "type": "quantitative",
                "legend": None,
            },
            "color": {
                "field": "source",
                "type": "nominal",
                "title": legend_title,
                "scale": {
                    "domain": [benchmark_label, fallback_label],
                    "range": ["#2563eb", "#9ca3af"],
                },
            },
            "tooltip": [
                {"field": "skill", "type": "nominal"},
                {"field": "salary_text", "type": "nominal", "title": tooltip_salary},
                {"field": "availability_text", "type": "nominal", "title": tooltip_availability},
                {"field": "source", "type": "nominal"},
            ],
        },
    }


def _render_summary(records: Sequence[SkillMarketRecord], *, segment_label: str, lang: str) -> None:
    benchmarks = [record for record in records if record.has_benchmark]
    if benchmarks:
        avg_salary = sum(record.salary_delta_pct for record in benchmarks) / len(benchmarks)
        avg_availability = sum(record.availability_index for record in benchmarks) / len(benchmarks)
        st.caption(
            tr(
                "{segment}: Ø Gehaltsimpact {salary:+.1f}% · Ø Verfügbarkeit {availability:.0f}/100",
                "{segment}: Avg. salary impact {salary:+.1f}% · Avg. availability {availability:.0f}/100",
                lang=lang,
            ).format(
                segment=segment_label,
                salary=avg_salary,
                availability=avg_availability,
            )
        )
    else:
        st.caption(
            tr(
                "{segment}: Keine Benchmarks gefunden – neutrale Platzhalter (0%, 50/100).",
                "{segment}: No benchmarks found – using neutral placeholders (0%, 50/100).",
                lang=lang,
            ).format(segment=segment_label)
        )
    fallback_skills = [record.skill for record in records if not record.has_benchmark]
    if fallback_skills:
        st.caption(
            tr(
                "Fallback-Daten für: {skills}",
                "Fallback data for: {skills}",
                lang=lang,
            ).format(skills=", ".join(fallback_skills))
        )


def render_skill_market_insights(
    skills: Sequence[str],
    *,
    segment_label: str,
    empty_message: str | None = None,
    lang: str | None = None,
) -> None:
    """Render the skill market insights component in Streamlit."""

    lang_code = lang or st.session_state.get("lang", "de")
    cleaned_skills = [skill for skill in skills if isinstance(skill, str) and skill.strip()]
    if not cleaned_skills:
        st.info(
            empty_message
            or tr(
                "Keine Auswahl – bitte Skills hinzufügen, um Markt-Insights zu sehen.",
                "No selection – add skills to view market insights.",
                lang=lang_code,
            )
        )
        return
    records = prepare_skill_market_records(cleaned_skills)
    if not records:
        st.info(
            empty_message
            or tr(
                "Keine Auswahl – bitte Skills hinzufügen, um Markt-Insights zu sehen.",
                "No selection – add skills to view market insights.",
                lang=lang_code,
            )
        )
        return
    spec = build_skill_market_chart_spec(records, lang=lang_code)
    st.vega_lite_chart(spec=spec, use_container_width=True)
    _render_summary(records, segment_label=segment_label, lang=lang_code)
