import json
import yaml
from typing import List, Dict, Any
from openai import OpenAI
from newspaper_boy import openai_client, PROMPTS


def filter_firearms_policy_citations(
    citations: List[Dict[str, Any]],
    *,
    model: str = "gpt-4.1-mini",
) -> List[Dict[str, Any]]:
    """
    Uses an OpenAI model and an external YAML prompt to filter citations
    relevant to firearms policy in Canada.
    """

    # Load YAML prompt
    with open(PROMPTS, "r", encoding="utf-8") as f:
        prompts = yaml.safe_load(f)

    system_prompt_key = "filter_firearms_policy_citations"
    user_prompt_key = "filter_firearms_policy_citations_user"

    if system_prompt_key not in prompts:
        raise KeyError(f"Key '{system_prompt_key}' not found in {PROMPTS}")
    if user_prompt_key not in prompts:
        raise KeyError(f"Key '{user_prompt_key}' not found in {PROMPTS}")
    system_prompt = prompts[system_prompt_key]

    slim = [
        {
            "citation_id": c.get("citation_id"),
            "title": c.get("title"),
            "url": c.get("url"),
            "publisher": c.get("publisher"),
            "source_type": c.get("source_type"),
            "media_type": c.get("media_type"),
        }
        for c in citations
    ]

    user_prompt = prompts[user_prompt_key].replace(
        "{citations_json}", f"{json.dumps(slim, ensure_ascii=False, indent=2)}"
    )

    response = openai_client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )

    content = response.choices[0].message.content

    try:
        data = json.loads(content)
        relevant_entries = data.get("relevant", [])
        meta_by_id: Dict[str, Dict[str, Any]] = {}
        for entry in relevant_entries:
            cid = entry.get("citation_id")
            if not cid:
                continue
            meta_by_id[cid] = {
                "reason_for_ccfr": entry.get("reason_for_ccfr"),
                "spiciness": entry.get("spiciness"),
            }
    except Exception:
        meta_by_id = {}

    filtered: List[Dict[str, Any]] = []
    for c in citations:
        cid = c.get("citation_id")
        if cid in meta_by_id:
            merged = dict(c)
            merged.update(meta_by_id[cid])
            filtered.append(merged)

    return filtered
