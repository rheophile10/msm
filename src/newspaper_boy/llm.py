import json
import yaml
from typing import List, Dict, Any
from openai import OpenAI
from newspaper_boy import openai_client, PROMPTS


def filter_firearms_policy_citations(
    citations: List[Dict[str, Any]],
    *,
    yaml_path: str = "prompt.yaml",
    yaml_key: str = "filter_firearms_policy_citations",
    model: str = "gpt-4.1-mini",
) -> List[Dict[str, Any]]:
    """
    Uses an OpenAI model and an external YAML prompt to filter citations
    relevant to firearms policy in Canada.
    """

    # Load YAML prompt
    with open(PROMPTS, "r", encoding="utf-8") as f:
        prompts = yaml.safe_load(f)

    if yaml_key not in prompts:
        raise KeyError(f"Key '{yaml_key}' not found in {PROMPTS}")
    system_prompt = prompts[yaml_key]

    # Reduce payload size
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

    user_prompt = (
        "Classify the following citations according to the system instructions.\n\n"
        "Return ONLY JSON with this exact format:\n"
        '{ "relevant_ids": ["V0001", "V0002"] }\n\n'
        "Citations:\n"
        f"{json.dumps(slim, ensure_ascii=False, indent=2)}"
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
        relevant_ids = set(data.get("relevant_ids", []))
    except Exception:
        relevant_ids = set()

    # Filter original data
    return [c for c in citations if c.get("citation_id") in relevant_ids]
