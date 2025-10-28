import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

import streamlit as st

from config_loader import load_json
from utils.i18n import (
    SKILL_MARKET_AVAILABILITY_METRIC_LABEL,
    SKILL_MARKET_FALLBACK_CAPTION,
    SKILL_MARKET_METRIC_CAPTION,
    SKILL_MARKET_SALARY_METRIC_LABEL,
    SKILL_MARKET_SELECT_SKILL_LABEL,
    tr,
)


def _unique_normalized(values: Iterable[str]) -> list[str]:
    from wizard._logic import unique_normalized as _unique_normalized_impl

    return _unique_normalized_impl(values)


@dataclass
class SkillMarketRecord:
    """Prepared data point for the visualization."""

    skill: str
    normalized_skill: str
    salary_delta_pct: float
    availability_index: float
    has_benchmark: bool
    region_label: str | None = None
    radius_km: float | None = None


_DEFAULT_SKILL_MARKET_DATA: dict[str, dict[str, object]] = {
    "python": {
        "aliases": ["python"],
        "salary_delta_pct": 6.5,
        "availability_index": 42.0,
        "regions": {
            "berlin de": [
                {"max_radius": 25, "salary_delta_pct": 7.4, "availability_index": 38.0},
                {"max_radius": 80, "salary_delta_pct": 7.0, "availability_index": 41.0},
            ],
            "de": [
                {"max_radius": 50, "salary_delta_pct": 6.8, "availability_index": 43.0},
                {"salary_delta_pct": 6.2, "availability_index": 46.0},
            ],
        },
    },
    "java": {
        "aliases": ["java"],
        "salary_delta_pct": 5.0,
        "availability_index": 48.0,
        "regions": {
            "munich de": [
                {"max_radius": 30, "salary_delta_pct": 6.1, "availability_index": 37.0},
                {"salary_delta_pct": 5.4, "availability_index": 40.0},
            ]
        },
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
        "regions": {
            "berlin de": [
                {"max_radius": 25, "salary_delta_pct": 0.2, "availability_index": 78.0},
                {"salary_delta_pct": 0.1, "availability_index": 80.0},
            ],
            "de": [{"salary_delta_pct": 0.0, "availability_index": 82.0}],
        },
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
_LOCATION_SANITIZE_PATTERN = re.compile(r"[^a-z0-9]+", re.IGNORECASE)


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


def _normalize_location_key(value: str) -> str:
    cleaned = value.lower()
    cleaned = cleaned.replace("/", " ")
    cleaned = cleaned.replace("-", " ")
    cleaned = _LOCATION_SANITIZE_PATTERN.sub(" ", cleaned)
    return " ".join(cleaned.split())


def _prepare_region_bands(raw_regions: object) -> dict[str, list[dict[str, float | None]]]:
    if not isinstance(raw_regions, Mapping):
        return {}
    prepared: dict[str, list[dict[str, float | None]]] = {}
    for region_key, raw_bands in raw_regions.items():
        normalized_region = _normalize_location_key(str(region_key))
        if not normalized_region:
            continue
        bands: list[dict[str, float | None]] = []
        if isinstance(raw_bands, Mapping):
            iterable = [raw_bands]
        elif isinstance(raw_bands, Sequence) and not isinstance(raw_bands, (str, bytes)):
            iterable = list(raw_bands)
        else:
            iterable = [raw_bands]
        for band in iterable:
            if not isinstance(band, Mapping):
                continue
            try:
                salary_delta = float(band.get("salary_delta_pct", 0.0) or 0.0)
            except (TypeError, ValueError):
                salary_delta = 0.0
            try:
                availability = float(band.get("availability_index", 50.0) or 50.0)
            except (TypeError, ValueError):
                availability = 50.0
            radius_raw = band.get("max_radius")
            radius_value: float | None
            if radius_raw is None:
                radius_value = None
            else:
                try:
                    radius_value = float(radius_raw)
                except (TypeError, ValueError):
                    radius_value = None
            bands.append(
                {
                    "max_radius": radius_value,
                    "salary_delta_pct": float(round(salary_delta, 2)),
                    "availability_index": float(min(100.0, max(0.0, availability))),
                }
            )
        if not bands:
            continue
        bands.sort(key=lambda item: float("inf") if item["max_radius"] is None else float(item["max_radius"]))
        prepared[normalized_region] = bands
    return prepared


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
            "regions": _prepare_region_bands(value.get("regions")),
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


def _derive_location_keys(location: Mapping[str, object] | None) -> list[str]:
    if not isinstance(location, Mapping):
        return []
    keys: list[str] = []
    city = str(location.get("primary_city", "") or "").strip()
    country = str(location.get("country", "") or "").strip()
    region = str(location.get("region") or location.get("state") or location.get("province") or "").strip()
    if city and country:
        keys.append(f"{city} {country}")
    if region and country:
        keys.append(f"{region} {country}")
    if city:
        keys.append(city)
    if region:
        keys.append(region)
    if country:
        keys.append(country)
    return keys


def _select_region_band(
    entry: Mapping[str, object],
    *,
    location_keys: Sequence[str],
    radius_km: float | None,
) -> tuple[float, float, str | None]:
    regions = entry.get("regions")
    if isinstance(regions, Mapping):
        for key in location_keys:
            normalized_key = _normalize_location_key(key)
            bands = regions.get(normalized_key)
            if not bands:
                continue
            band = None
            if radius_km is None:
                band = bands[0]
            else:
                for candidate in bands:
                    max_radius = candidate.get("max_radius")
                    if max_radius is None or radius_km <= max_radius:
                        band = candidate
                        break
                if band is None:
                    band = bands[-1]
            if band:
                salary = float(band.get("salary_delta_pct", 0.0) or 0.0)
                availability = float(band.get("availability_index", 50.0) or 50.0)
                return salary, min(100.0, max(0.0, availability)), key
    salary = float(entry.get("salary_delta_pct", 0.0) or 0.0)
    availability = float(entry.get("availability_index", 50.0) or 50.0)
    return salary, min(100.0, max(0.0, availability)), None


def _compose_location_label(location: Mapping[str, object] | None) -> str:
    if not isinstance(location, Mapping):
        return ""
    city = str(location.get("primary_city", "") or "").strip()
    region = str(location.get("region") or location.get("state") or location.get("province") or "").strip()
    country = str(location.get("country", "") or "").strip()
    parts = [part for part in (city, region, country) if part]
    return ", ".join(dict.fromkeys(parts))


def prepare_skill_market_records(
    skills: Sequence[str],
    *,
    dataset: Mapping[str, dict[str, object]] | None = None,
    location: Mapping[str, object] | None = None,
    radius_km: float | None = None,
) -> list[SkillMarketRecord]:
    """Normalize selected skills and enrich them with market data."""

    dataset = dataset or _load_skill_market_data()
    seen: set[str] = set()
    location_keys = _derive_location_keys(location)
    normalized_radius = float(radius_km) if radius_km is not None else None
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
                    region_label=_compose_location_label(location) or None,
                    radius_km=normalized_radius,
                )
            )
            continue
        salary_delta, availability, region_label = _select_region_band(
            entry,
            location_keys=location_keys,
            radius_km=normalized_radius,
        )
        records.append(
            SkillMarketRecord(
                skill=cleaned,
                normalized_skill=normalized,
                salary_delta_pct=float(round(salary_delta, 2)),
                availability_index=float(round(availability, 2)),
                has_benchmark=True,
                region_label=region_label or (_compose_location_label(location) or None),
                radius_km=normalized_radius,
            )
        )
    records.sort(
        key=lambda record: (
            record.has_benchmark,
            record.salary_delta_pct,
            -record.availability_index,
        ),
        reverse=True,
    )
    return records


def _translate_pair(pair: tuple[str, str], *, lang: str) -> str:
    """Return the translated string for ``pair`` in ``lang``."""

    return tr(pair[0], pair[1], lang=lang)


def build_salary_chart_spec(
    records: Sequence[SkillMarketRecord],
    *,
    lang: str,
) -> dict[str, object]:
    """Create a Vega-Lite spec showing salary deltas per skill."""

    values: list[dict[str, object]] = []
    for record in records:
        values.append(
            {
                "skill": record.skill,
                "value": round(record.salary_delta_pct, 2),
                "source": tr("Benchmark", "Benchmark", lang=lang)
                if record.has_benchmark
                else tr("Fallback", "Fallback", lang=lang),
                "region": record.region_label or tr("Global", "Global", lang=lang),
            }
        )
    base_label = _translate_pair(SKILL_MARKET_SALARY_METRIC_LABEL, lang=lang)
    title = f"{base_label} (%)"
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "data": {"values": values},
        "mark": {"type": "bar", "cornerRadiusEnd": 4},
        "encoding": {
            "x": {
                "field": "value",
                "type": "quantitative",
                "axis": {"title": title},
                "scale": {"zero": True},
            },
            "y": {
                "field": "skill",
                "type": "nominal",
                "sort": "-x",
            },
            "color": {
                "field": "source",
                "type": "nominal",
                "legend": {"title": tr("Datenbasis", "Data source", lang=lang)},
                "scale": {
                    "domain": [
                        tr("Benchmark", "Benchmark", lang=lang),
                        tr("Fallback", "Fallback", lang=lang),
                    ],
                    "range": ["#2563eb", "#9ca3af"],
                },
            },
            "tooltip": [
                {"field": "skill", "type": "nominal"},
                {
                    "field": "value",
                    "type": "quantitative",
                    "title": base_label,
                    "format": "+.1f",
                },
                {"field": "region", "type": "nominal"},
                {"field": "source", "type": "nominal"},
            ],
        },
    }


def build_availability_chart_spec(
    records: Sequence[SkillMarketRecord],
    *,
    lang: str,
) -> dict[str, object]:
    """Create a Vega-Lite spec showing availability index per skill."""

    values: list[dict[str, object]] = []
    for record in records:
        values.append(
            {
                "skill": record.skill,
                "value": round(record.availability_index, 2),
                "source": tr("Benchmark", "Benchmark", lang=lang)
                if record.has_benchmark
                else tr("Fallback", "Fallback", lang=lang),
                "region": record.region_label or tr("Global", "Global", lang=lang),
            }
        )
    base_label = _translate_pair(SKILL_MARKET_AVAILABILITY_METRIC_LABEL, lang=lang)
    title = f"{base_label} (0–100)"
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "data": {"values": values},
        "mark": {"type": "bar", "cornerRadiusEnd": 4},
        "encoding": {
            "x": {
                "field": "value",
                "type": "quantitative",
                "axis": {"title": title},
                "scale": {"domain": [0, 100]},
            },
            "y": {
                "field": "skill",
                "type": "nominal",
                "sort": "-x",
            },
            "color": {
                "field": "source",
                "type": "nominal",
                "legend": {"title": tr("Datenbasis", "Data source", lang=lang)},
                "scale": {
                    "domain": [
                        tr("Benchmark", "Benchmark", lang=lang),
                        tr("Fallback", "Fallback", lang=lang),
                    ],
                    "range": ["#0ea5e9", "#9ca3af"],
                },
            },
            "tooltip": [
                {"field": "skill", "type": "nominal"},
                {
                    "field": "value",
                    "type": "quantitative",
                    "title": base_label,
                    "format": ".0f",
                },
                {"field": "region", "type": "nominal"},
                {"field": "source", "type": "nominal"},
            ],
        },
    }


def _render_summary(
    records: Sequence[SkillMarketRecord],
    *,
    segment_label: str,
    lang: str,
    location: Mapping[str, object] | None,
) -> None:
    benchmarks = [record for record in records if record.has_benchmark]
    if benchmarks:
        avg_salary = sum(record.salary_delta_pct for record in benchmarks) / len(benchmarks)
        avg_availability = sum(record.availability_index for record in benchmarks) / len(benchmarks)
        st.caption(
            _translate_pair(SKILL_MARKET_METRIC_CAPTION, lang=lang).format(
                skill=segment_label,
                salary=avg_salary,
                availability=avg_availability,
            )
        )
    else:
        st.caption(_translate_pair(SKILL_MARKET_FALLBACK_CAPTION, lang=lang).format(skill=segment_label))
    fallback_skills = [record.skill for record in records if not record.has_benchmark]
    if fallback_skills:
        st.caption(
            tr(
                "Fallback-Daten für: {skills}",
                "Fallback data for: {skills}",
                lang=lang,
            ).format(skills=", ".join(fallback_skills))
        )
    regions = {record.region_label for record in records if record.region_label}
    if regions or any(record.radius_km is not None for record in records):
        location_label = _compose_location_label(location)
        region_label = ", ".join(sorted(region for region in regions if region)) or location_label
        radius_values = {record.radius_km for record in records if record.radius_km is not None}
        radius_text: str | None = None
        if radius_values:
            radius = sorted(radius_values)[-1]
            radius_text = tr("Radius: {radius:.0f} km", "Radius: {radius:.0f} km", lang=lang).format(radius=radius)
        if region_label or radius_text:
            if region_label and radius_text:
                combined = f"{region_label} · {radius_text}"
            else:
                combined = region_label or radius_text or ""
            st.caption(
                tr(
                    "Berechnet für {details}.",
                    "Calculated for {details}.",
                    lang=lang,
                ).format(details=combined)
            )


def render_skill_market_insights(
    skills: Mapping[str, Sequence[str]] | Sequence[str],
    *,
    segment_label: str,
    empty_message: str | None = None,
    lang: str | None = None,
    location: Mapping[str, object] | None = None,
    radius_km: float | None = None,
) -> None:
    """Render the skill market insights component in Streamlit."""

    lang_code = lang or st.session_state.get("lang", "de")

    cleaned_skills: list[str] = []
    skill_segments: dict[str, set[str]] = {}
    if isinstance(skills, Mapping):
        for segment, group in skills.items():
            for skill in group:
                if not isinstance(skill, str):
                    continue
                cleaned = skill.strip()
                if not cleaned:
                    continue
                cleaned_skills.append(cleaned)
                skill_segments.setdefault(cleaned, set()).add(segment)
    else:
        for skill in skills:
            if not isinstance(skill, str):
                continue
            cleaned = skill.strip()
            if cleaned:
                cleaned_skills.append(cleaned)

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

    unique_skills = _unique_normalized(cleaned_skills)

    option_map: dict[str, str] = {}
    options: list[str] = []
    for skill in unique_skills:
        segments = sorted(skill_segments.get(skill, []))
        if segments:
            label = f"{skill} ({', '.join(segments)})"
        else:
            label = skill
        option_map[label] = skill
        options.append(label)

    multiselect_label = _translate_pair(SKILL_MARKET_SELECT_SKILL_LABEL, lang=lang_code)
    selected_labels = st.multiselect(
        multiselect_label,
        options,
        default=options,
        help=tr(
            "Blende Skills aus, um Gehalts- und Verfügbarkeitskarten ohne diese Anforderungen zu berechnen.",
            "Hide skills to recalculate salary and availability charts without them.",
            lang=lang_code,
        ),
    )

    selected_skills = [option_map[label] for label in selected_labels if label in option_map]
    if not selected_skills:
        st.info(
            tr(
                "Wähle mindestens einen Skill aus, um Markt-Insights zu berechnen.",
                "Select at least one skill to calculate market insights.",
                lang=lang_code,
            )
        )
        return

    records = prepare_skill_market_records(
        selected_skills,
        location=location,
        radius_km=radius_km,
    )
    if not records:
        st.info(
            tr(
                "Keine Auswahl – bitte Skills hinzufügen, um Markt-Insights zu sehen.",
                "No selection – add skills to view market insights.",
                lang=lang_code,
            )
        )
        return

    st.caption(
        tr(
            "Wir aktualisieren die Karten live basierend auf deiner Skill-Auswahl und dem gewählten Radius.",
            "The charts update instantly based on your skill selection and chosen radius.",
            lang=lang_code,
        )
    )

    salary_spec = build_salary_chart_spec(records, lang=lang_code)
    availability_spec = build_availability_chart_spec(records, lang=lang_code)
    col_salary, col_availability = st.columns(2, gap="large")
    with col_salary:
        st.vega_lite_chart(spec=salary_spec, width="stretch")
    with col_availability:
        st.vega_lite_chart(spec=availability_spec, width="stretch")

    _render_summary(
        records,
        segment_label=segment_label,
        lang=lang_code,
        location=location,
    )
