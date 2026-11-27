"""Bounded declarative concept and knowledge graph for individual agents."""
from dataclasses import dataclass
from itertools import combinations
import math


OBSERVATION_CAPACITY = 64
CONCEPT_CAPACITY = 64
CLAIM_CAPACITY = 128
EVIDENCE_REFERENCE_CAPACITY = 32
MIN_PATTERN_SAMPLES = 3
MIN_VALIDATION_SAMPLES = 5
MIN_CORRELATION = 0.25
VALIDATED_CORRELATION = 0.6


@dataclass
class Concept:
    name: str
    observation_count: int
    mean_value: float
    last_day: int
    source_refs: list


@dataclass
class KnowledgeObservation:
    id: int
    day: int
    source_type: str
    source_id: str
    context: dict
    values: dict

    @property
    def provenance(self):
        return f"{self.source_type}:{self.source_id}"


@dataclass
class KnowledgeClaim:
    id: int
    concept_a: str
    relation: str
    concept_b: str
    kind: str
    status: str
    confidence: float
    sample_count: int
    support_count: int
    contradiction_count: int
    context: dict
    evidence_refs: list
    derived_from: list
    last_day: int


class KnowledgeGraph:
    """Learn correlations and test declarative hypotheses from personal evidence."""

    SOURCE_TYPES = {
        "personal_experience",
        "social_information",
        "direct_observation",
    }

    def __init__(self):
        self.concepts = {}
        self.observations = []
        self.claims = []
        self.next_observation_id = 1
        self.next_claim_id = 1

    @staticmethod
    def _context(context):
        if context is None:
            return {}
        if not isinstance(context, dict) or len(context) > 16:
            raise ValueError("Konteks pengetahuan tidak valid.")
        normalized = {}
        for key, value in context.items():
            if not isinstance(key, str) or not key or len(key) > 64:
                raise ValueError("Kunci konteks pengetahuan tidak valid.")
            if isinstance(value, str):
                if len(value) > 120:
                    raise ValueError("Nilai konteks pengetahuan terlalu panjang.")
            elif value is not None and type(value) not in (bool, int, float):
                raise ValueError("Nilai konteks pengetahuan harus sederhana.")
            if type(value) is float and not math.isfinite(value):
                raise ValueError("Nilai konteks pengetahuan harus terbatas.")
            normalized[key] = value
        return dict(sorted(normalized.items()))

    @staticmethod
    def _name(value, label):
        if not isinstance(value, str) or not value.strip() or len(value) > 64:
            raise ValueError(f"{label} pengetahuan tidak valid.")
        return value.strip()

    @classmethod
    def _values(cls, values):
        if not isinstance(values, dict) or not values or len(values) > 16:
            raise ValueError("Observasi harus memiliki 1–16 konsep.")
        normalized = {}
        for key, value in values.items():
            name = cls._name(key, "Konsep")
            if isinstance(value, bool):
                raise ValueError("Nilai konsep harus berupa angka.")
            try:
                value = float(value)
            except (TypeError, ValueError, OverflowError):
                raise ValueError("Nilai konsep harus berupa angka.") from None
            if not math.isfinite(value):
                raise ValueError("Nilai konsep harus terbatas.")
            normalized[name] = value
        return dict(sorted(normalized.items()))

    @staticmethod
    def _append_reference(references, reference):
        if reference in references:
            return
        references.append(reference)
        if len(references) > EVIDENCE_REFERENCE_CAPACITY:
            del references[:-EVIDENCE_REFERENCE_CAPACITY]

    def _trim_claims(self):
        while len(self.claims) > CLAIM_CAPACITY:
            least_supported = min(
                self.claims,
                key=lambda claim: (
                    claim.status == "validated",
                    claim.confidence,
                    claim.last_day,
                    claim.id,
                ),
            )
            self.claims.remove(least_supported)

    def _track_concepts(self, observation):
        for name, value in observation.values.items():
            concept = self.concepts.get(name)
            if concept is None:
                if len(self.concepts) >= CONCEPT_CAPACITY:
                    oldest = min(
                        self.concepts.values(),
                        key=lambda item: (item.last_day, item.observation_count),
                    )
                    del self.concepts[oldest.name]
                    self.claims = [
                        claim for claim in self.claims
                        if oldest.name not in (claim.concept_a, claim.concept_b)
                    ]
                self.concepts[name] = Concept(
                    name, 1, value, observation.day,
                    [observation.provenance],
                )
                continue
            count = concept.observation_count + 1
            concept.mean_value += (value - concept.mean_value) / count
            concept.observation_count = count
            concept.last_day = observation.day
            self._append_reference(concept.source_refs, observation.provenance)

    def _samples(self, concept_a, concept_b, context):
        return [
            observation for observation in self.observations
            if observation.context == context
            and concept_a in observation.values
            and concept_b in observation.values
        ]

    @staticmethod
    def _statistics(samples, concept_a, concept_b):
        count = len(samples)
        if count < MIN_PATTERN_SAMPLES:
            return None
        values_a = [sample.values[concept_a] for sample in samples]
        values_b = [sample.values[concept_b] for sample in samples]
        mean_a = sum(values_a) / count
        mean_b = sum(values_b) / count
        centered = [
            (value_a - mean_a, value_b - mean_b)
            for value_a, value_b in zip(values_a, values_b)
        ]
        variance_a = sum(value_a * value_a for value_a, _ in centered)
        variance_b = sum(value_b * value_b for _, value_b in centered)
        if variance_a <= 1e-12 or variance_b <= 1e-12:
            return count, 0.0, 0, 0
        covariance = sum(value_a * value_b for value_a, value_b in centered)
        correlation = covariance / math.sqrt(variance_a * variance_b)
        support = sum(
            (value_a * value_b > 0) if correlation > 0
            else (value_a * value_b < 0)
            for value_a, value_b in centered
        )
        contradiction = count - support - sum(
            value_a == 0 or value_b == 0
            for value_a, value_b in centered
        )
        return count, max(-1.0, min(1.0, correlation)), support, contradiction

    @staticmethod
    def _pair_matches(claim, concept_a, concept_b, context):
        return (
            claim.kind == "correlation"
            and {claim.concept_a, claim.concept_b} == {concept_a, concept_b}
            and claim.context == context
        )

    def _new_claim(self, concept_a, relation, concept_b, kind, status,
                   confidence, sample_count, support_count,
                   contradiction_count, context, evidence_refs,
                   derived_from, day):
        claim = KnowledgeClaim(
            id=self.next_claim_id,
            concept_a=concept_a,
            relation=relation,
            concept_b=concept_b,
            kind=kind,
            status=status,
            confidence=confidence,
            sample_count=sample_count,
            support_count=support_count,
            contradiction_count=contradiction_count,
            context=dict(context),
            evidence_refs=list(evidence_refs[-EVIDENCE_REFERENCE_CAPACITY:]),
            derived_from=list(derived_from),
            last_day=day,
        )
        self.next_claim_id += 1
        self.claims.append(claim)
        self._trim_claims()
        return claim

    def _refresh_correlations(self, observation):
        changed = False
        concepts = list(observation.values)
        for raw_a, raw_b in combinations(concepts, 2):
            concept_a, concept_b = sorted((raw_a, raw_b))
            samples = self._samples(
                concept_a, concept_b, observation.context
            )
            stats = self._statistics(samples, concept_a, concept_b)
            if stats is None:
                continue
            count, correlation, support, contradiction = stats
            strength = min(0.99, abs(correlation) * min(1.0, count / 5.0))
            relation = (
                "positive" if correlation > 0 else "negative"
            ) if abs(correlation) >= MIN_CORRELATION else None
            matching = next((
                claim for claim in self.claims
                if self._pair_matches(
                    claim, concept_a, concept_b, observation.context
                ) and claim.relation == relation
            ), None) if relation is not None else None

            for claim in self.claims:
                if not self._pair_matches(
                        claim, concept_a, concept_b, observation.context):
                    continue
                if claim is matching:
                    continue
                claim.confidence = min(
                    claim.confidence * 0.75,
                    strength,
                )
                claim.status = "correlation"
                claim.sample_count = count
                claim.contradiction_count += 1
                claim.last_day = observation.day
                self._append_reference(
                    claim.evidence_refs, observation.provenance
                )
                changed = True

            if relation is None:
                continue
            evidence = [
                sample.provenance for sample in samples
            ][-EVIDENCE_REFERENCE_CAPACITY:]
            status = (
                "validated"
                if count >= MIN_VALIDATION_SAMPLES
                and abs(correlation) >= VALIDATED_CORRELATION
                else "correlation"
            )
            if matching is None:
                self._new_claim(
                    concept_a, relation, concept_b, "correlation", status,
                    strength, count, support, contradiction,
                    observation.context, evidence, [], observation.day,
                )
                changed = True
            else:
                changed = changed or matching.status != status
                matching.status = status
                matching.confidence = strength
                matching.sample_count = count
                matching.support_count = support
                matching.contradiction_count = contradiction
                matching.evidence_refs = evidence
                matching.last_day = observation.day
        return changed

    def _compose_hypotheses(self):
        correlations = [
            claim for claim in self.claims
            if claim.kind == "correlation" and claim.confidence >= 0.3
        ]
        for left, right in combinations(correlations, 2):
            if left.context != right.context:
                continue
            shared = {left.concept_a, left.concept_b}.intersection(
                (right.concept_a, right.concept_b)
            )
            if len(shared) != 1:
                continue
            pivot = next(iter(shared))
            outer_left = (
                left.concept_b if left.concept_a == pivot else left.concept_a
            )
            outer_right = (
                right.concept_b if right.concept_a == pivot else right.concept_a
            )
            if outer_left == outer_right:
                continue
            concept_a, concept_b = sorted((outer_left, outer_right))
            sign = (
                (1 if left.relation == "positive" else -1)
                * (1 if right.relation == "positive" else -1)
            )
            relation = "positive" if sign > 0 else "negative"
            existing = next((
                claim for claim in self.claims
                if claim.kind == "hypothesis"
                and claim.concept_a == concept_a
                and claim.concept_b == concept_b
                and claim.relation == relation
                and claim.context == left.context
            ), None)
            confidence = min(left.confidence, right.confidence) * 0.5
            evidence = list(dict.fromkeys(
                left.evidence_refs + right.evidence_refs
            ))[-EVIDENCE_REFERENCE_CAPACITY:]
            derived_from = [left.id, right.id]
            if existing is None:
                self._new_claim(
                    concept_a, relation, concept_b, "hypothesis",
                    "hypothesis", confidence, 0, 0, 0, left.context,
                    evidence, derived_from, max(left.last_day, right.last_day),
                )
            else:
                existing.confidence = max(existing.confidence, confidence)
                existing.evidence_refs = evidence
                existing.derived_from = derived_from

    def _validate_hypotheses(self, observation):
        for claim in self.claims:
            if (claim.kind != "hypothesis"
                    or claim.context != observation.context
                    or claim.concept_a not in observation.values
                    or claim.concept_b not in observation.values):
                continue
            samples = self._samples(
                claim.concept_a, claim.concept_b, observation.context
            )
            stats = self._statistics(samples, claim.concept_a, claim.concept_b)
            if stats is None:
                continue
            count, correlation, support, contradiction = stats
            relation = (
                "positive" if correlation > 0 else "negative"
            ) if abs(correlation) >= MIN_CORRELATION else None
            if relation == claim.relation:
                claim.sample_count = count
                claim.support_count = support
                claim.contradiction_count = contradiction
                claim.confidence = min(
                    0.99, abs(correlation) * min(1.0, count / 5.0)
                )
                claim.status = (
                    "validated"
                    if count >= MIN_VALIDATION_SAMPLES
                    and abs(correlation) >= VALIDATED_CORRELATION
                    else "hypothesis"
                )
                claim.evidence_refs = [
                    sample.provenance for sample in samples
                ][-EVIDENCE_REFERENCE_CAPACITY:]
            else:
                claim.contradiction_count += 1
                claim.confidence *= 0.75
                claim.status = "hypothesis"
                claim.last_day = observation.day
                self._append_reference(
                    claim.evidence_refs, observation.provenance
                )

    def observe(self, day, source_type, source_id, values, context=None):
        if isinstance(day, bool) or not isinstance(day, int) or day < 0:
            raise ValueError("Hari observasi harus bilangan bulat nonnegatif.")
        if (not isinstance(source_type, str)
                or source_type not in self.SOURCE_TYPES):
            raise ValueError("Jenis sumber pengetahuan tidak dikenal.")
        if (not isinstance(source_id, str) or not source_id.strip()
                or len(source_id) > 120):
            raise ValueError("Referensi sumber pengetahuan tidak valid.")
        values = self._values(values)
        context = self._context(context)
        observation = KnowledgeObservation(
            self.next_observation_id,
            day,
            source_type,
            source_id.strip(),
            context,
            values,
        )
        self.next_observation_id += 1
        self.observations.append(observation)
        if len(self.observations) > OBSERVATION_CAPACITY:
            del self.observations[:-OBSERVATION_CAPACITY]
        self._track_concepts(observation)
        if self._refresh_correlations(observation):
            self._compose_hypotheses()
        self._validate_hypotheses(observation)
        return observation

    def query(self, concept=None, other_concept=None, kind=None, status=None,
              context=None, current_day=None, limit=8):
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 0:
            raise ValueError("Batas hasil pengetahuan tidak valid.")
        if limit == 0:
            return []
        if concept is not None:
            concept = self._name(concept, "Konsep")
        if other_concept is not None:
            other_concept = self._name(other_concept, "Konsep")
            if concept is None:
                raise ValueError("Konsep utama diperlukan untuk pencarian relasi.")
        if kind is not None and kind not in ("correlation", "hypothesis"):
            raise ValueError("Jenis klaim pengetahuan tidak valid.")
        if status is not None and status not in (
                "correlation", "hypothesis", "validated"):
            raise ValueError("Status klaim pengetahuan tidak valid.")
        context = self._context(context)
        if current_day is not None and (
                isinstance(current_day, bool) or not isinstance(current_day, int)
                or current_day < 0):
            raise ValueError("Hari pencarian pengetahuan tidak valid.")
        matches = []
        for claim in self.claims:
            if concept is not None and concept not in (
                    claim.concept_a, claim.concept_b):
                continue
            if other_concept is not None and {
                    claim.concept_a, claim.concept_b
            } != {concept, other_concept}:
                continue
            if kind is not None and claim.kind != kind:
                continue
            if status is not None and claim.status != status:
                continue
            if context and claim.context != context:
                continue
            if current_day is not None and claim.last_day > current_day:
                continue
            age = (
                max(0, current_day - claim.last_day)
                if current_day is not None else 0
            )
            recency = 1.0 / (1.0 + age / 90.0)
            relevance = 0.7 * claim.confidence + 0.3 * recency
            matches.append((relevance, claim))
        matches.sort(
            key=lambda item: (item[0], item[1].last_day, item[1].id),
            reverse=True,
        )
        return [claim for _, claim in matches[:limit]]

    def prediction_adjustment(self, concept, other_concept, observed_value,
                              context=None, current_day=None):
        concept = self._name(concept, "Konsep")
        other_concept = self._name(other_concept, "Konsep")
        context = self._context(context)
        try:
            observed_value = float(observed_value)
        except (TypeError, ValueError, OverflowError):
            raise ValueError("Nilai prediksi pengetahuan harus berupa angka.") from None
        if not math.isfinite(observed_value):
            raise ValueError("Nilai prediksi pengetahuan harus terbatas.")
        adjustment = 0.0
        for claim in self.query(
                concept=concept, other_concept=other_concept,
                status="validated", context=context,
                current_day=current_day, limit=CLAIM_CAPACITY):
            sign = 1.0 if claim.relation == "positive" else -1.0
            adjustment += sign * observed_value * claim.confidence * 0.02
        return max(-0.02, min(0.02, adjustment))
