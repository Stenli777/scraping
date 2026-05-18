"""Topic extraction quality filters and CRMFlow24 relevance scoring."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.core.config import get_settings
from app.core.feature_flags import is_llm_review_enabled

logger = logging.getLogger(__name__)

TOPIC_SCHEMA_VERSION = "topic_v2"

SEARCH_INTENTS = frozenset(
    {"informational", "commercial", "transactional", "comparison", "navigation", "unknown"}
)

RU_STOPWORDS = frozenset(
    {
        "?", "?", "??", "??", "???", "???", "???", "???????", "???????", "?????", "?????",
        "?????", "?????", "??????", "?????", "???", "???", "???", "???", "???", "???", "??",
        "??", "??", "??", "??", "??", "???", "???", "???", "???", "???", "??????", "?????",
        "?????", "?????", "????", "?????", "???", "???", "???", "???", "???", "???", "?????",
        "?????", "?????", "????", "????", "????", "???", "???", "???", "??", "???", "??", "??",
    }
)

EN_STOPWORDS = frozenset(
    {
        "the", "and", "for", "with", "how", "what", "why", "this", "that", "from", "into",
        "your", "our", "are", "was", "were", "can", "will", "new", "also", "just", "about",
    }
)

GENERIC_WORDS = frozenset(
    {
        "?????", "?????", "??????", "?????", "?????", "??????", "?????", "?????", "?????",
        "general", "article", "content", "post", "blog", "news", "update", "latest",
    }
)

PROTECTED_TERMS = frozenset(
    {
        "crm", "bitrix24", "???????24", "???????", "?????????", "?????????", "??????????",
        "??????????", "???????", "???????", "????", "???", "???????", "??????", "?????????",
        "?????????????", "?????????????", "whatsapp", "telegram", "????????", "amocrm",
        "??????-????????", "??????-?????????", "kpi", "?????", "??????",
    }
)

CRM_BOOST_TERMS = PROTECTED_TERMS | frozenset(
    {
        "crmflow24", "saas", "b2b", "??????? ??????", "???????? ?????????", "??????????",
        "???", "??????", "??????", "???????", "??????", "????????",
    }
)

INTERNAL_NOISE_TERMS = frozenset({"mock-rewriter", "cliproxyapi", "llm", "scrap", "rewriter", "studio"})

CRM_NEGATIVE_TERMS = frozenset(
    {
        "crypto", "bitcoin", "nft", "politics", "????????", "gaming", "????", "gamer",
        "kubernetes", "docker", "devops", "react", "vue", "angular", "python tutorial",
        "??????", "????????", "??????", "??????",
    }
)

# Russian adjective-like single tokens (heuristic)
_RU_ADJ_SUFFIXES = ("???", "???", "???", "???", "????", "????", "????", "????", "????", "????")


def normalize_token(text: str) -> str:
    s = (text or "").strip().lower()
    s = re.sub(r"[^\w\s\-]", " ", s, flags=re.UNICODE)
    return re.sub(r"\s+", " ", s).strip()


def is_garbage_token(token: str) -> bool:
    t = normalize_token(token)
    if not t or len(t) < 4:
        return True
    if t in RU_STOPWORDS or t in EN_STOPWORDS or t in GENERIC_WORDS:
        return True
    # lone Russian adjective fragment
    if " " not in t and any(t.endswith(suf) for suf in _RU_ADJ_SUFFIXES):
        if t not in PROTECTED_TERMS:
            return True
    # no vowels / mostly digits
    if not re.search(r"[??????????aeiou]", t):
        return True
    if re.fullmatch(r"\d+", t):
        return True
    return False


def tokenize_clean(text: str) -> list[str]:
    raw = normalize_token(text).split()
    out: list[str] = []
    for t in raw:
        if not is_garbage_token(t):
            out.append(t)
    return out


def extract_phrase_candidates(
    *,
    title: str,
    tags: list[str],
    text_sample: str,
) -> tuple[list[str], list[str]]:
    """Return (phrase_candidates, rejected_single_tokens)."""
    rejected: list[str] = []
    phrases: list[str] = []

    for tag in tags:
        tag_s = str(tag).strip()
        if not tag_s:
            continue
        if len(tag_s.split()) >= 2 or tag_s.lower() in PROTECTED_TERMS:
            phrases.append(tag_s)
        elif is_garbage_token(tag_s):
            rejected.append(tag_s)

    for part in re.split(r"[,;:\-\u2014]+", title):
        part = part.strip()
        if len(part) >= 12 and len(part.split()) >= 2:
            phrases.append(part)

    words = tokenize_clean(text_sample)
    for i in range(len(words) - 1):
        bigram = f"{words[i]} {words[i+1]}"
        if len(bigram) >= 10:
            phrases.append(bigram)
    for i in range(len(words) - 2):
        trigram = f"{words[i]} {words[i+1]} {words[i+2]}"
        if any(p in trigram for p in ("crm", "bitrix", "??????", "???????", "???????", "???????")):
            phrases.append(trigram)

    # singles only if protected CRM terms
    for w in words:
        if w in PROTECTED_TERMS:
            phrases.append(w.replace("-", " "))

    seen: set[str] = set()
    unique: list[str] = []
    for p in phrases:
        key = normalize_token(p)
        if key and key not in seen:
            seen.add(key)
            unique.append(p.strip()[:120])
    return unique, rejected


def score_project_relevance(
    *,
    tokens: set[str],
    phrases: list[str],
    project_slug: str | None,
) -> tuple[int, str]:
    slug = (project_slug or "").lower()
    project_fit = slug or "default"
    text_blob = " ".join(tokens) + " " + " ".join(normalize_token(p) for p in phrases)

    score = 50
    if slug in ("crmflow24", "crm-flow24", "crm"):
        project_fit = "crmflow24"
        score = 55

    for term in CRM_BOOST_TERMS:
        if term in text_blob:
            score += 8
    for term in CRM_NEGATIVE_TERMS:
        if term in text_blob:
            score -= 25

    if any(t in text_blob for t in ("bitrix", "???????", "crm", "??????", "???", "??????")):
        score += 10
    if any(t in text_blob for t in INTERNAL_NOISE_TERMS):
        score -= 8

    score = max(0, min(100, score))
    return score, project_fit


def infer_search_intent_v2(
    *,
    keywords: list[str],
    phrases: list[str],
    tags: list[str],
) -> str:
    blob = " ".join(keywords + phrases + tags).lower()
    if any(w in blob for w in ("??????", "????", "?????", "????????", "buy", "pricing")):
        return "commercial"
    if any(w in blob for w in ("vs", "???????", "compare", "??????", "???????????")):
        return "comparison"
    if any(w in blob for w in ("???", "how", "????", "guide", "??????????")):
        return "informational"
    if any(w in blob for w in ("????", "login", "?????? ???????")):
        return "navigation"
    if any(w in blob for w in ("????????", "?????", "checkout")):
        return "transactional"
    if any(w in blob for w in ("crm", "bitrix", "???????", "??????????", "??????")):
        return "commercial"
    return "informational"



def _phrase_is_noise(phrase: str) -> bool:
    low = normalize_token(phrase)
    if any(n in low for n in INTERNAL_NOISE_TERMS):
        return True
    if "mock" in low and "rewriter" in low:
        return True
    return False

def build_keywords(
    phrases: list[str],
    tokens: list[str],
    max_count: int = 10,
) -> list[str]:
    keywords: list[str] = []
    for p in phrases:
        pk = normalize_token(p)
        if pk and pk not in {normalize_token(k) for k in keywords}:
            keywords.append(p if len(p) < 40 else pk)
    for t in tokens:
        if t in PROTECTED_TERMS and t not in {normalize_token(k) for k in keywords}:
            keywords.append(t)
    filtered = [k for k in keywords if not any(n in normalize_token(k) for n in INTERNAL_NOISE_TERMS)]
    return filtered[:max_count]


def extract_entities(text_blob: str) -> list[str]:
    found: list[str] = []
    low = text_blob.lower()
    for term in sorted(PROTECTED_TERMS, key=len, reverse=True):
        if term in low and term not in {f.lower() for f in found}:
            found.append(term.title() if term.isascii() else term)
    return found[:8]


def maybe_llm_cleanup(
    *,
    primary_topic: str,
    secondary_topics: list[str],
    keywords: list[str],
) -> tuple[list[str], list[str], list[str]]:
    """Optional LLM cleanup; returns (secondary, keywords, warnings)."""
    warnings: list[str] = []
    if not is_llm_review_enabled():
        return secondary_topics, keywords, warnings

    try:
        from app.services.llm_tasks import run_json_prompt

        settings = get_settings()
        payload = {
            "primary_topic": primary_topic,
            "secondary_topics": secondary_topics,
            "keywords": keywords,
        }
        result = run_json_prompt(
            task_type="topic_cleanup_v1",
            model_alias=settings.review_model_alias,
            user_payload=payload,
        )
        if isinstance(result, dict):
            sec = result.get("secondary_topics")
            kw = result.get("keywords")
            if isinstance(sec, list):
                secondary_topics = [str(x) for x in sec[:6]]
            if isinstance(kw, list):
                keywords = [str(x) for x in kw[:10]]
            warnings.append("llm_cleanup_applied")
    except Exception as exc:
        logger.info("topic LLM cleanup skipped: %s", exc)
        warnings.append("llm_cleanup_skipped")
    return secondary_topics, keywords, warnings


def build_topic_extraction_v2(
    *,
    title: str,
    tags: list[str],
    text_sample: str,
    project_slug: str | None = None,
    use_llm_cleanup: bool = True,
) -> dict[str, Any]:
    phrases, rejected_singles = extract_phrase_candidates(
        title=title, tags=tags, text_sample=text_sample
    )
    tokens = tokenize_clean(f"{title} {text_sample}")
    token_set = set(tokens)

    raw_rejected = list(rejected_singles)
    for t in normalize_token(text_sample).split():
        if is_garbage_token(t) and t not in raw_rejected:
            raw_rejected.append(t)

    primary_topic = title.strip()
    if not primary_topic and phrases:
        primary_topic = phrases[0]
    elif not primary_topic and tokens:
        primary_topic = " ".join(tokens[:4]).title()

    pt_norm = normalize_token(primary_topic)
    secondary_topics = []
    for p in phrases:
        pn = normalize_token(p)
        if pn == pt_norm or pn in pt_norm or pt_norm in pn:
            continue
        if len(p.split()) < 2 and pn not in PROTECTED_TERMS:
            continue
        if _phrase_is_noise(p):
            continue
        secondary_topics.append(p)
        if len(secondary_topics) >= 6:
            break
    keywords = build_keywords(phrases, tokens)
    entities = extract_entities(f"{title} {text_sample} {' '.join(tags)}")
    search_intent = infer_search_intent_v2(keywords=keywords, phrases=phrases, tags=tags)
    relevance_score, project_fit = score_project_relevance(
        tokens=token_set, phrases=phrases, project_slug=project_slug
    )

    warnings: list[str] = []
    if relevance_score < 40:
        warnings.append("low_project_relevance")
    if len(secondary_topics) < 2:
        warnings.append("few_secondary_topics")

    if use_llm_cleanup:
        secondary_topics, keywords, llm_warn = maybe_llm_cleanup(
            primary_topic=primary_topic,
            secondary_topics=secondary_topics,
            keywords=keywords,
        )
        warnings.extend(llm_warn)

    return {
        "schema_version": TOPIC_SCHEMA_VERSION,
        "primary_topic": primary_topic,
        "secondary_topics": secondary_topics,
        "keywords": keywords,
        "entities": entities,
        "search_intent": search_intent if search_intent in SEARCH_INTENTS else "unknown",
        "relevance_score": relevance_score,
        "project_fit": project_fit,
        "rejected_terms": sorted(set(raw_rejected))[:30],
        "warnings": warnings,
    }
