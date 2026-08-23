from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Estimate OpenAI API cost for the PoC.")
    parser.add_argument("--pricing", default="configs/openai_pricing_approx_2026-07-03.json")
    parser.add_argument("--calls", type=int, default=30)
    parser.add_argument("--input-tokens", type=int, default=3200)
    parser.add_argument("--output-tokens", type=int, default=650)
    args = parser.parse_args()

    pricing = json.loads(Path(args.pricing).read_text(encoding="utf-8"))
    estimates = estimate_costs(pricing, args.calls, args.input_tokens, args.output_tokens)
    print(json.dumps(estimates, indent=2))


def estimate_costs(
    pricing: dict,
    calls: int,
    input_tokens_per_call: int,
    output_tokens_per_call: int,
) -> dict:
    total_input = calls * input_tokens_per_call
    total_output = calls * output_tokens_per_call
    models = {}
    for model, rates in pricing["models"].items():
        input_cost = (total_input / 1_000_000) * rates["input"]
        output_cost = (total_output / 1_000_000) * rates["output"]
        models[model] = {
            "input_cost_usd": round(input_cost, 6),
            "output_cost_usd": round(output_cost, 6),
            "total_cost_usd": round(input_cost + output_cost, 6),
        }
    return {
        "calls": calls,
        "input_tokens_per_call": input_tokens_per_call,
        "output_tokens_per_call": output_tokens_per_call,
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "models": models,
        "pricing_source": pricing["source"],
        "pricing_retrieved_date": pricing["retrieved_date"],
    }


if __name__ == "__main__":
    main()
