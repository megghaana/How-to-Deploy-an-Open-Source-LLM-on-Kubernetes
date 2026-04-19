#!/usr/bin/env python3
"""
Comparative analysis: Mistral 7B (local) vs GPT-4o mini (commercial)
Runs 10 prompts, measures latency, token count, and saves results to JSON + markdown.

SETUP:
  pip install openai requests tabulate
  export OPENAI_API_KEY=your_key_here
  kubectl port-forward svc/ollama-service 11434:11434 -n llm-stack
"""

import json
import os
import time
from datetime import datetime

import requests
from openai import OpenAI
from tabulate import tabulate


OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "mistral:7b"
OPENAI_MODEL = "gpt-4o-mini"  # cheapest option — change to "gpt-4o" for smarter

PROMPTS = [
    "Which model are you and who created you?",
    "What is your knowledge cutoff date?",
    "Explain how transformers work in 3 sentences.",
    "Write a Python function to reverse a linked list.",
    "What is the capital of Australia? Give 3 facts about it.",
    "Summarize the causes of World War I in under 100 words.",
    "What are the pros and cons of Kubernetes vs Docker Compose?",
    "Write a haiku about machine learning.",
    "What is 17 multiplied by 23? Show your working.",
    "Explain the CAP theorem in simple terms."
]


def query_ollama(prompt: str) -> dict:
    start = time.time()
    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": OLLAMA_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False
            },
            timeout=120
        )
        data = resp.json()
        latency = time.time() - start
        content = data.get("message", {}).get("content", "ERROR: no content")
        tokens = data.get("eval_count", 0)
        return {
            "response": content,
            "latency_s": round(latency, 2),
            "tokens": tokens,
            "cost_usd": 0.0  # free, running locally
        }
    except Exception as e:
        return {"response": f"ERROR: {e}", "latency_s": 0, "tokens": 0, "cost_usd": 0.0}


def query_openai(client: OpenAI, prompt: str) -> dict:
    start = time.time()
    try:
        msg = client.chat.completions.create(
            model=OPENAI_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )
        latency = time.time() - start
        content = msg.choices[0].message.content
        input_tokens = msg.usage.prompt_tokens
        output_tokens = msg.usage.completion_tokens
        # gpt-4o-mini pricing: $0.15/M input, $0.60/M output (as of 2025)
        # gpt-4o pricing:      $5.00/M input, $15.0/M output
        if OPENAI_MODEL == "gpt-4o":
            cost = (input_tokens * 5.0 + output_tokens * 15.0) / 1_000_000
        else:
            cost = (input_tokens * 0.15 + output_tokens * 0.60) / 1_000_000
        return {
            "response": content,
            "latency_s": round(latency, 2),
            "tokens": output_tokens,
            "cost_usd": round(cost, 6)
        }
    except Exception as e:
        return {"response": f"ERROR: {e}", "latency_s": 0, "tokens": 0, "cost_usd": 0.0}


def score_response(response: str) -> int:
    """
    Simple heuristic quality score (0-10).
    For a real eval, use an LLM-as-judge or human annotation.
    """
    r = response.lower()
    score = 5  # base
    if len(response) > 200:
        score += 1
    if len(response) > 500:
        score += 1
    if any(word in r for word in ["because", "therefore", "however", "example"]):
        score += 1
    if response.startswith("ERROR"):
        score = 0
    if len(response) < 30:
        score -= 2
    return max(0, min(10, score))


def run_analysis():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("⚠  OPENAI_API_KEY not set — skipping GPT column.")
        run_openai = False
    else:
        run_openai = True
        openai_client = OpenAI(api_key=api_key)

    results = []
    print(f"\n{'=' * 60}")
    print(f"  Comparative LLM Analysis — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'=' * 60}\n")

    for i, prompt in enumerate(PROMPTS, 1):
        print(f"[{i:02d}/{len(PROMPTS)}] {prompt[:60]}...")

        mistral_res = query_ollama(prompt)
        print(f"       Mistral  : {mistral_res['latency_s']}s  |  {mistral_res['tokens']} tokens")

        if run_openai:
            openai_res = query_openai(openai_client, prompt)
            print(f"       GPT      : {openai_res['latency_s']}s  |  {openai_res['tokens']} tokens  |  ${openai_res['cost_usd']}")
        else:
            openai_res = {"response": "N/A", "latency_s": 0, "tokens": 0, "cost_usd": 0.0}

        results.append({
            "id": i,
            "prompt": prompt,
            "mistral": {**mistral_res, "quality": score_response(mistral_res["response"])},
            "openai": {**openai_res, "quality": score_response(openai_res["response"])},
        })

    # ── Summary table ─────────────────────────────────────
    print(f"\n{'=' * 60}")
    print("  RESULTS SUMMARY")
    print(f"{'=' * 60}\n")

    table_rows = []
    for r in results:
        table_rows.append([
            r["id"],
            r["prompt"][:45] + "…" if len(r["prompt"]) > 45 else r["prompt"],
            f"{r['mistral']['latency_s']}s",
            f"{r['mistral']['quality']}/10",
            "$0.00",
            f"{r['openai']['latency_s']}s",
            f"{r['openai']['quality']}/10",
            f"${r['openai']['cost_usd']}",
        ])

    headers = ["#", "Prompt", "Mistral⏱", "Mistral★", "Mistral$", "GPT⏱", "GPT★", "GPT$"]
    print(tabulate(table_rows, headers=headers, tablefmt="rounded_outline"))

    m_avg_lat = sum(r["mistral"]["latency_s"] for r in results) / len(results)
    m_avg_qual = sum(r["mistral"]["quality"] for r in results) / len(results)

    o_avg_lat = sum(r["openai"]["latency_s"] for r in results) / len(results)
    o_avg_qual = sum(r["openai"]["quality"] for r in results) / len(results)
    o_total_cost = sum(r["openai"]["cost_usd"] for r in results)

    print(f"\n  Mistral  — avg latency: {m_avg_lat:.1f}s | avg quality: {m_avg_qual:.1f}/10 | total cost: $0.00 (free!)")
    print(f"  GPT      — avg latency: {o_avg_lat:.1f}s | avg quality: {o_avg_qual:.1f}/10 | total cost: ${o_total_cost:.4f}")

    # ── Save outputs ──────────────────────────────────────
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    with open(f"comparison_results_{timestamp}.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n  ✅ Full responses saved → comparison_results_{timestamp}.json")

    # Markdown report
    md = [
        f"# LLM Comparison: Mistral 7B vs {OPENAI_MODEL}",
        f"**Date:** {datetime.now().strftime('%Y-%m-%d')}  ",
        f"**Prompts tested:** {len(PROMPTS)}  ",
        "",
        "## Summary",
        "",
        f"| Metric | Mistral 7B (local) | {OPENAI_MODEL} (API) |",
        "|--------|-------------------|-------------------|",
        f"| Avg Latency | {m_avg_lat:.1f}s | {o_avg_lat:.1f}s |",
        f"| Avg Quality Score | {m_avg_qual:.1f}/10 | {o_avg_qual:.1f}/10 |",
        f"| Total Cost (10 prompts) | $0.00 | ${o_total_cost:.4f} |",
        "",
        "## Per-prompt Results",
        "",
        "| # | Prompt | Mistral Latency | Mistral Quality | GPT Latency | GPT Quality | Cost Diff |",
        "|---|--------|----------------|----------------|-------------|-------------|-----------|",
    ]
    for r in results:
        md.append(
            f"| {r['id']} | {r['prompt'][:50]} | {r['mistral']['latency_s']}s "
            f"| {r['mistral']['quality']}/10 | {r['openai']['latency_s']}s "
            f"| {r['openai']['quality']}/10 | ${r['openai']['cost_usd']} |"
        )

    md += ["", "## Individual Responses", ""]
    for r in results:
        md += [
            f"### Prompt {r['id']}: {r['prompt']}",
            "",
            "**Mistral 7B:**",
            f"> {r['mistral']['response'][:500]}{'...' if len(r['mistral']['response']) > 500 else ''}",
            "",
            f"**{OPENAI_MODEL}:**",
            f"> {r['openai']['response'][:500]}{'...' if len(r['openai']['response']) > 500 else ''}",
            "",
            "---",
            "",
        ]

    with open(f"comparison_report_{timestamp}.md", "w") as f:
        f.write("\n".join(md))
    print(f"  ✅ Markdown report saved  → comparison_report_{timestamp}.md\n")


if __name__ == "__main__":
    run_analysis()
