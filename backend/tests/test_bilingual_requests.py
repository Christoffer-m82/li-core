"""Deterministic EN/SV parity and boundaries; no live models or external writes."""

import unicodedata

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.auth import require_api_token
from app.action_intents import IntentDecision
from app.freshness_policy import COMMON_CURRENT, POLICIES, decide_freshness
from app.li_runtime import _memory_search_queries
from app.location_settings import CurrentPlace, minimal_location_context
from app.main import app, _requested_text_artifact
from app.memory_capture import (
    MemoryCaptureAnalysis, _target_lookup_queries, is_ambiguous_bare_forget,
    is_contextual_memory_change,
)
from app.provider_coverage import requirement_for, provider_registry, select_providers
from app.request_language import ALIASES, has_term, requests_history
from app.specialist_runtime import (
    SPECIALIST_PROFILES, _TRIGGERS, route_specialists, specialist_needs_canonical_memory,
)


@pytest.mark.parametrize("key", list(SPECIALIST_PROFILES))
@pytest.mark.parametrize("verb", ["Be", "Fråga", "Rådfråga", "Konsultera", "Koppla in", "Ta in", "Låt"])
def test_explicit_request_routes_same_registered_specialist(key, verb):
    name = SPECIALIST_PROFILES[key].name
    en = route_specialists(f"Ask {name} to compare these options.")
    sv = route_specialists(f"{verb} {name} jämföra de här alternativen.")
    assert en.model_dump() == sv.model_dump()
    assert sv.specialists == [key]


@pytest.mark.parametrize("key", list(SPECIALIST_PROFILES))
def test_possessive_request_in_both_languages(key):
    name = SPECIALIST_PROFILES[key].name
    sv_name = name if name.endswith("s") else name + "s"
    assert route_specialists(f"{name}'s advice").specialists == [key]
    assert route_specialists(f"{sv_name} råd").specialists == [key]


@pytest.mark.parametrize("en,sv,expected", [
    ("Help me plan my training.", "Hjälp mig planera min träning.", ["marco"]),
    ("Help me with a recipe.", "Hjälp mig med ett recept.", ["elena"]),
    ("Help with my health.", "Hjälp med min hälsa.", ["sofia"]),
    ("Help with a relationship.", "Hjälp med en relation.", ["amelia"]),
    ("Help with parenting.", "Hjälp med föräldraskap.", ["freja"]),
    ("Help with a contract.", "Hjälp med ett avtal.", ["oliver"]),
    ("Help with an investment.", "Hjälp med en investering.", ["james"]),
    ("Help with negotiation.", "Hjälp med förhandling.", ["victor"]),
    ("Investigate this.", "Undersök detta.", ["nora"]),
    ("Help with my holiday.", "Hjälp med min ledighet.", ["milo"]),
    ("Help with furniture.", "Hjälp med möbler.", ["iris"]),
    ("Help with my habits.", "Hjälp med mina vanor.", ["clara"]),
    ("Plan training and food.", "Planera träning och mat.", ["marco", "elena"]),
    ("Consult Victor and Milo.", "Rådfråga Victor och Milo.", ["victor", "milo"]),
    ("Can you ask Nora?", "Kan du be Nora?", ["nora"]),
    ("Please ask Nora.", "Snälla be Nora.", ["nora"]),
    ("What is training?", "Vad är träning?", []),
    ("Translate this recipe.", "Översätt det här receptet.", []),
    ("Hi", "Hej", []),
])
def test_natural_requests_have_same_routing(en, sv, expected):
    assert route_specialists(en).model_dump() == route_specialists(sv).model_dump()
    assert route_specialists(sv).specialists == expected


@pytest.mark.parametrize("message", [
    "Nora", "Noras bok är blå.", "Can I be Nora in this story?",
    "Matematik är roligt.", "Jag är lagom trött.", "Skattjakt är kul.",
    "I live far away.",
])
def test_names_substrings_and_english_be_are_not_requests(message):
    assert route_specialists(message).specialists == []


@pytest.mark.parametrize("en,sv", [
    ("Do not ask Nora.", "Be inte Nora."),
    ("Don't consult Nora for research.", "Konsultera inte Nora för forskning."),
    ("Ask Marco without Elena.", "Fråga Marco utan Elena."),
])
def test_explicit_opt_out_is_preserved_in_both_languages(en, sv):
    assert route_specialists(en).model_dump() == route_specialists(sv).model_dump()
    assert "nora" not in route_specialists(sv).specialists
    assert "elena" not in route_specialists(sv).specialists


def test_word_count_does_not_change_number_of_specialists():
    short = route_specialists("Help with food and training.")
    long = route_specialists("Help with food and training. " + "Please think carefully. " * 8)
    assert short.model_dump() == long.model_dump()


def test_multiple_specialists_remain_bounded_in_both_languages():
    names = "Sofia, Marco, Elena, Amelia, Freja, Oliver, James, Victor, Nora, Milo, Iris, Clara"
    assert route_specialists("Ask " + names).specialists == route_specialists("Fråga " + names).specialists
    assert len(route_specialists("Fråga " + names).specialists) == 3


def test_mixed_language_and_decomposed_swedish_characters():
    assert route_specialists("Please fråga Nora to compare alternativen").specialists == ["nora"]
    message = unicodedata.normalize("NFD", "Hjälp mig med min träning")
    assert route_specialists(message).specialists == ["marco"]


def test_alias_table_covers_every_domain_and_freshness_trigger():
    terms = {t for values in _TRIGGERS.values() for t in values} | set(COMMON_CURRENT)
    for policy in POLICIES.values():
        terms.update(policy.high_stakes_triggers)
        terms.update(policy.live_verification_triggers)
    assert terms <= ALIASES.keys()


@pytest.mark.parametrize("key,term,alias", [
    (key, term, alias)
    for key, policy in POLICIES.items()
    for term in (*policy.high_stakes_triggers, *policy.live_verification_triggers, *COMMON_CURRENT)
    for alias in ALIASES[term]
])
def test_freshness_alias_preserves_requirements_and_source_policy(key, term, alias):
    en = decide_freshness(key, term).model_dump(exclude={"freshness_reason"})
    sv = decide_freshness(key, alias).model_dump(exclude={"freshness_reason"})
    assert sv == en
    assert sv["evidence_required"]


@pytest.mark.parametrize("message", ["separate", "marketing", "skattjakt", "lagom", "matematik"])
def test_freshness_does_not_use_substring_matching(message):
    assert not decide_freshness("james", message).evidence_required
    assert not has_term(message, "food")


@pytest.mark.parametrize("en,sv", [
    ("based on my goals", "utifrån mina mål"),
    ("I prefer the cheaper option", "Jag föredrar det billigare alternativet"),
    ("based on what you know", "baserat på vad du vet"),
])
def test_personal_context_gate(en, sv):
    assert specialist_needs_canonical_memory(en)
    assert specialist_needs_canonical_memory(sv)
    assert not specialist_needs_canonical_memory("Explain a general principle.")
    assert not specialist_needs_canonical_memory("Förklara en allmän princip.")


@pytest.mark.parametrize("en,sv", [
    ("forget that", "glöm det"), ("Please forget it.", "Snälla glöm det där."),
    ("don't remember that", "kom inte ihåg detta"),
])
def test_ambiguous_memory_change_remains_guarded(en, sv):
    for message in (en, sv):
        assert is_ambiguous_bare_forget(message)
        assert is_contextual_memory_change(message)


def test_contextual_corrections_and_unicode_search_words():
    for message in ("change what I just told you", "ändra det jag nyss sa"):
        assert is_contextual_memory_change(message)
    assert not is_ambiguous_bare_forget("glöm min gamla färgpreferens")
    assert "trädgården" in _memory_search_queries("Berätta om trädgården")
    assert _target_lookup_queries("min preferens för blå anteckningsböcker")[-1] == "blå anteckningsböcker"
    assert "rd" not in _memory_search_queries("trädgården")


@pytest.mark.parametrize("en,sv", [
    ("Do you remember our decision?", "Minns du vårt beslut?"),
    ("We discussed notebooks.", "Vi pratade om anteckningsböcker."),
    ("Our previous conversation", "Vårt tidigare samtal"),
    ("Last year", "Förra året"),
])
def test_history_trigger(en, sv):
    assert requests_history(en) and requests_history(sv)
    assert not requests_history("Hello") and not requests_history("Hej")


@pytest.mark.parametrize("key,en,sv", [
    ("james", "Current stock price", "Aktuellt aktiepris"),
    ("james", "Current inflation", "Aktuell inflation"),
    ("oliver", "Contract law in Germany", "Avtalslag i Tyskland"),
    ("oliver", "Legal advice in the United Kingdom", "Juridisk rådgivning i Storbritannien"),
    ("oliver", "Legal advice in Sweden", "Juridisk rådgivning i Sverige"),
])
def test_provider_requirements_and_unavailable_provider_fail_closed(key, en, sv):
    requirements = [requirement_for(key, m, decide_freshness(key, m)) for m in (en, sv)]
    assert requirements[0] == requirements[1]
    selections = [select_providers(r, provider_registry(web_configured=False)) for r in requirements]
    assert selections[0] == selections[1]
    assert not selections[0].compliant


@pytest.mark.parametrize("en,sv", [
    ("Create a text file", "Skapa en textfil"),
    ("Give me a markdown file", "Ge mig en markdownfil"),
])
def test_text_artifact_request(en, sv):
    assert _requested_text_artifact(en) and _requested_text_artifact(sv)
    assert not _requested_text_artifact("Vad är en textfil?")


@pytest.mark.parametrize("en,sv", [
    ("weather near me", "väder nära mig"),
    ("tax rules", "skatteregler"),
    ("Hello", "Hej"),
])
def test_minimal_place_disclosure_is_the_same(en, sv):
    place = CurrentPlace(country_code="MT", town_city="Synthetic town")
    assert minimal_location_context(en, place) == minimal_location_context(sv, place)


@pytest.mark.parametrize("word", ["yes", "ja", "sure", "absolut"])
def test_chat_agreement_cannot_replace_typed_approval(word):
    with pytest.raises(ValidationError):
        IntentDecision(decision=word)


@pytest.mark.parametrize("message", ["Do you remember our discussion?", "Minns du vårt samtal?"])
def test_chat_history_gate_reaches_bounded_lookup_without_translation(monkeypatch, message):
    seen = []
    cid = "d729b771-a656-470e-bf83-2f542f910154"
    monkeypatch.setattr("app.main.get_recent_conversation_messages", lambda **k: [])
    monkeypatch.setattr("app.main.append_conversation_message", lambda **k: "message-id")
    monkeypatch.setattr("app.main.analyze_memory_capture", lambda *a, **k: MemoryCaptureAnalysis())
    monkeypatch.setattr("app.main.talk_to_li", lambda *a, **k: "No stored discussion found.")
    monkeypatch.setattr("app.main.search_conversation_history", lambda query, limit: seen.append((query, limit)) or [])
    app.dependency_overrides[require_api_token] = lambda: None
    try:
        with TestClient(app) as client:
            response = client.post("/li/chat", json={"message": message, "conversation_id": cid})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert seen == [(message, 6)]
