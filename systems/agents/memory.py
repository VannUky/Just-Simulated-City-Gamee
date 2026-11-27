"""Bounded, personal episodic memory for simulation agents."""
from dataclasses import dataclass
import math
from typing import Optional


EPISODE_CAPACITY = 64
SUMMARY_CAPACITY = 16
SUMMARY_THRESHOLD = 3
SOURCE_REFERENCE_CAPACITY = 32


@dataclass
class MemoryEpisode:
    id: int
    day: int
    domain: str
    action: str
    context: dict
    outcome: str
    success: Optional[bool]
    impact: float
    value: float

    @property
    def source_count(self):
        return 1

    @property
    def source_ids(self):
        return (self.id,)

    @property
    def first_day(self):
        return self.day

    @property
    def last_day(self):
        return self.day

    @property
    def mean_value(self):
        return self.value

    @property
    def mean_impact(self):
        return self.impact

    @property
    def importance(self):
        failure_weight = 0.25 if self.success is False else 0.0
        return min(1.0, self.impact + failure_weight)


@dataclass
class MemorySummary:
    domain: str
    action: str
    context: dict
    first_day: int
    last_day: int
    source_count: int
    source_ids: list
    success_count: int
    failure_count: int
    unknown_count: int
    mean_value: float
    mean_impact: float
    last_outcome: str

    @property
    def id(self):
        return self.source_ids[-1] if self.source_ids else 0

    @property
    def success_rate(self):
        resolved = self.success_count + self.failure_count
        if not resolved:
            return None
        return self.success_count / resolved

    @property
    def importance(self):
        failure_weight = (
            0.25 * self.failure_count / self.source_count
            if self.source_count else 0.0
        )
        return min(1.0, self.mean_impact + failure_weight)


class EpisodicMemory:
    """Keep recent experiences and bounded summaries of repeated episodes."""

    def __init__(self):
        self.episodes = []
        self.summaries = []
        self.next_episode_id = 1

    @staticmethod
    def _text(value, label, maximum):
        if not isinstance(value, str) or not value.strip() or len(value) > maximum:
            raise ValueError(f"{label} memori tidak valid.")
        return value.strip()

    @staticmethod
    def _context(context):
        if context is None:
            return {}
        if not isinstance(context, dict):
            raise ValueError("Konteks memori harus berupa dictionary.")
        if len(context) > 16:
            raise ValueError("Konteks memori melebihi batas atribut.")
        normalized = {}
        for key, value in context.items():
            if not isinstance(key, str) or not key or len(key) > 64:
                raise ValueError("Kunci konteks memori tidak valid.")
            if isinstance(value, str):
                if len(value) > 120:
                    raise ValueError("Nilai konteks memori terlalu panjang.")
            elif value is not None and type(value) not in (bool, int, float):
                raise ValueError("Nilai konteks memori harus berupa nilai sederhana.")
            if type(value) is float and not math.isfinite(value):
                raise ValueError("Nilai konteks memori harus terbatas.")
            normalized[key] = value
        return dict(sorted(normalized.items()))

    @staticmethod
    def _signature(domain, action, context):
        return (
            domain,
            action,
            tuple(
                (key, type(value).__name__, value)
                for key, value in context.items()
            ),
        )

    def _entry_signature(self, entry):
        return self._signature(entry.domain, entry.action, entry.context)

    @staticmethod
    def _summary_from(episodes):
        ordered = sorted(episodes, key=lambda item: (item.day, item.id))
        latest = ordered[-1]
        total = len(ordered)
        successes = sum(item.success is True for item in ordered)
        failures = sum(item.success is False for item in ordered)
        return MemorySummary(
            domain=latest.domain,
            action=latest.action,
            context=dict(latest.context),
            first_day=ordered[0].day,
            last_day=latest.day,
            source_count=total,
            source_ids=[item.id for item in ordered][-SOURCE_REFERENCE_CAPACITY:],
            success_count=successes,
            failure_count=failures,
            unknown_count=total - successes - failures,
            mean_value=sum(item.value for item in ordered) / total,
            mean_impact=sum(item.impact for item in ordered) / total,
            last_outcome=latest.outcome,
        )

    def _absorb(self, summary, episode):
        old_count = summary.source_count
        new_count = old_count + 1
        summary.mean_value = (
            summary.mean_value * old_count + episode.value
        ) / new_count
        summary.mean_impact = (
            summary.mean_impact * old_count + episode.impact
        ) / new_count
        summary.source_count = new_count
        summary.first_day = min(summary.first_day, episode.day)
        if episode.day >= summary.last_day:
            summary.last_day = episode.day
            summary.last_outcome = episode.outcome
        if episode.success is True:
            summary.success_count += 1
        elif episode.success is False:
            summary.failure_count += 1
        else:
            summary.unknown_count += 1
        summary.source_ids.append(episode.id)
        if len(summary.source_ids) > SOURCE_REFERENCE_CAPACITY:
            del summary.source_ids[:-SOURCE_REFERENCE_CAPACITY]

    def _trim(self):
        while len(self.episodes) > EPISODE_CAPACITY:
            oldest_low_impact = min(
                self.episodes,
                key=lambda item: (item.importance, item.day, item.id),
            )
            self.episodes.remove(oldest_low_impact)
        while len(self.summaries) > SUMMARY_CAPACITY:
            oldest_low_impact = min(
                self.summaries,
                key=lambda item: (item.importance, item.last_day, item.id),
            )
            self.summaries.remove(oldest_low_impact)

    def record(self, day, domain, action, context, outcome, success,
               impact=0.0, value=0.0):
        if isinstance(day, bool) or not isinstance(day, int) or day < 0:
            raise ValueError("Hari pengalaman harus berupa bilangan bulat nonnegatif.")
        if success is not None and not isinstance(success, bool):
            raise ValueError("Status keberhasilan memori tidak valid.")
        try:
            impact = float(impact)
            value = float(value)
        except (TypeError, ValueError, OverflowError):
            raise ValueError("Dampak dan nilai pengalaman harus berupa angka.") from None
        if (not math.isfinite(impact) or not 0 <= impact <= 1
                or not math.isfinite(value) or not -1 <= value <= 1):
            raise ValueError("Dampak atau nilai pengalaman di luar batas.")

        domain = self._text(domain, "Domain", 40)
        action = self._text(action, "Aksi", 40)
        outcome = self._text(outcome, "Hasil", 160)
        context = self._context(context)
        episode = MemoryEpisode(
            id=self.next_episode_id,
            day=day,
            domain=domain,
            action=action,
            context=context,
            outcome=outcome,
            success=success,
            impact=impact,
            value=value,
        )
        self.next_episode_id += 1
        signature = self._entry_signature(episode)

        for summary in self.summaries:
            if self._entry_signature(summary) == signature:
                self._absorb(summary, episode)
                self._trim()
                return summary

        similar = [
            item for item in self.episodes
            if self._entry_signature(item) == signature
        ]
        if len(similar) + 1 >= SUMMARY_THRESHOLD:
            summary = self._summary_from(similar + [episode])
            similar_ids = {item.id for item in similar}
            self.episodes = [
                item for item in self.episodes if item.id not in similar_ids
            ]
            self.summaries.append(summary)
            self._trim()
            return summary

        self.episodes.append(episode)
        self._trim()
        return episode

    def retrieve(self, domain=None, action=None, context=None, current_day=None,
                 since_day=None, limit=5):
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 0:
            raise ValueError("Batas hasil memori harus bilangan bulat nonnegatif.")
        query_context = self._context(context)
        if domain is not None:
            domain = self._text(domain, "Domain", 40)
        if action is not None:
            action = self._text(action, "Aksi", 40)
        if current_day is not None and (
                isinstance(current_day, bool) or not isinstance(current_day, int)
                or current_day < 0):
            raise ValueError("Hari pencarian memori tidak valid.")
        if since_day is not None and (
                isinstance(since_day, bool) or not isinstance(since_day, int)
                or since_day < 0):
            raise ValueError("Batas waktu memori tidak valid.")
        if limit == 0:
            return []

        entries = self.episodes + self.summaries
        if current_day is None:
            current_day = max(
                (entry.last_day for entry in entries), default=0
            )
        matches = []
        for entry in entries:
            if domain is not None and entry.domain != domain:
                continue
            if action is not None and entry.action != action:
                continue
            if since_day is not None and entry.last_day < since_day:
                continue
            if entry.last_day > current_day:
                continue
            if query_context:
                shared = sum(
                    entry.context.get(key, object()) == value
                    for key, value in query_context.items()
                )
                context_score = shared / max(
                    len(query_context), len(entry.context), 1
                )
            else:
                context_score = 0.5
            age = current_day - entry.last_day
            recency_score = 1.0 / (1.0 + age / 90.0)
            score = (
                0.55 * context_score
                + 0.25 * recency_score
                + 0.20 * entry.importance
            )
            matches.append((score, entry))
        matches.sort(
            key=lambda item: (
                item[0], item[1].last_day, item[1].id
            ),
            reverse=True,
        )
        return [entry for _, entry in matches[:limit]]
