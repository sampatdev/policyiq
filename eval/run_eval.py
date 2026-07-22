import json
import time
from app.db import SessionLocal
from app.query import embed_query, search_similar_chunks, ask_claude
import anthropic
from app.config import settings

claude_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)


def judge_answer(question: str, expected: str, actual: str) -> bool:
    """Use Claude as a judge: does the actual answer satisfy the expected answer?"""
    prompt = f"""Question: {question}
Expected answer: {expected}
Actual answer: {actual}

Does the actual answer correctly convey the expected answer? Reply with only "YES" or "NO"."""
    response = claude_client.messages.create(
        model="claude-haiku-4-5",  # cheap model — judging is a simple task, no need for Sonnet here
        max_tokens=10,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip().upper().startswith("YES")


def run_eval():
    with open("eval/golden_dataset.json") as f:
        golden_set = json.load(f)

    db = SessionLocal()
    results = []

    for item in golden_set:
        start = time.time()

        query_embedding = embed_query(item["question"])
        chunks = search_similar_chunks(db, query_embedding, top_k=3)
        answer = ask_claude(item["question"], chunks) if chunks else "No documents found."

        latency = time.time() - start
        correct = judge_answer(item["question"], item["expected_answer"], answer)

        results.append({
            "question": item["question"],
            "expected": item["expected_answer"],
            "actual": answer,
            "correct": correct,
            "latency_seconds": round(latency, 2),
        })

        time.sleep(20)  # stay under Voyage's 3 requests/minute cap on the free tier

    db.close()

    # Summary
    total = len(results)
    correct_count = sum(r["correct"] for r in results)
    avg_latency = sum(r["latency_seconds"] for r in results) / total

    print(f"\n{'='*50}")
    print(f"EVAL RESULTS: {correct_count}/{total} correct ({correct_count/total*100:.0f}%)")
    print(f"Average latency: {avg_latency:.2f}s")
    print(f"{'='*50}\n")

    for r in results:
        status = "✓" if r["correct"] else "✗"
        print(f"{status} {r['question']}")
        if not r["correct"]:
            print(f"    Expected: {r['expected']}")
            print(f"    Got: {r['actual'][:100]}...")

    return results


if __name__ == "__main__":
    run_eval()