import asyncio
import json
from agent import is_mui


async def main():
    with open("eval/scope_set.json") as f:
        test_set = json.load(f)

    correct = 0
    result_set = {}

    for row in test_set:
        got = await is_mui(row["question"], row.get("previous"))

        if got == row["expected"]:
            correct += 1
        else:
            print(
                f"MISS [{row['group']}] expected={row['expected']} got={got} | {row['question']}"
            )

        result = {
            "question": row["question"],
            "expected_response": row["expected"],
            "verdict": got,
        }
        result_set.setdefault(row["group"], []).append(result)

    print(f"\nAccuracy: {correct}/{len(test_set)}")
    for group, results in result_set.items():
        ok = sum(1 for r in results if r["verdict"] == r["expected_response"])
        print(f"  {group}: {ok}/{len(results)}")


asyncio.run(main())
