"""Quiz game for CodeCoach: random coding riddles for kids.
Answering correctly awards stars, badges, and unlockable coding themes/titles.
Scores and unlocked rewards are saved in kid_rewards.json.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SAVE_FILE = HERE / "kid_rewards.json"

QUESTIONS = [
    {
        "q": "What Python function prints words onto your screen?",
        "options": ["A) print()", "B) show()", "C) shout()", "D) screen()"],
        "answer": "A",
        "fact": "print() displays whatever text or numbers you put inside the parentheses!",
    },
    {
        "q": "In Python, which symbol do we use to save a value into a variable?",
        "options": ["A) ==", "B) =", "C) ->", "D) :="],
        "answer": "B",
        "fact": "A single '=' assigns a value, while '==' checks if two things are equal!",
    },
    {
        "q": "Which data type stores text inside quotation marks like 'Hello'?",
        "options": ["A) Integer", "B) Float", "C) String (str)", "D) Boolean"],
        "answer": "C",
        "fact": "Strings hold letters and text like beads on a necklace string!",
    },
    {
        "q": "What happens if you run: 10 / 0 in Python?",
        "options": [
            "A) It makes 0",
            "B) ZeroDivisionError crash!",
            "C) It makes infinity",
            "D) Python deletes the file",
        ],
        "answer": "B",
        "fact": "Math rule: dividing by zero is impossible, so Python stops with ZeroDivisionError.",
    },
    {
        "q": "Which loop repeats code over a list of items or numbers?",
        "options": ["A) for loop", "B) repeat loop", "C) spin loop", "D) jump loop"],
        "answer": "A",
        "fact": "A for loop steps through items one by one!",
    },
    {
        "q": "What boolean values can a bool have?",
        "options": ["A) Yes or No", "B) True or False", "C) 1 or 2", "D) High or Low"],
        "answer": "B",
        "fact": "Booleans in Python are always capitalized: True or False!",
    },
    {
        "q": "How do you write a comment in Python that the computer ignores?",
        "options": ["A) // comment", "B) -- comment", "C) # comment", "D) <!-- comment -->"],
        "answer": "C",
        "fact": "The '#' symbol lets you write secret notes to yourself in code!",
    },
    {
        "q": "What function turns the text '42' into the real number 42?",
        "options": ["A) str()", "B) int()", "C) num()", "D) calc()"],
        "answer": "B",
        "fact": "int() turns text numbers into real numbers you can do math with!",
    },
]

TITLES = [
    (0, "🌱 Code Sprout"),
    (3, "⚡ Junior Bug Hunter"),
    (7, "🧙 Code Wizard Apprentice"),
    (12, "🚀 Master Python Explorer"),
    (20, "👑 Supreme Coding Legend"),
]

BADGES = [
    (1, "⭐ First Star!", "Answered your first riddle correctly!"),
    (3, "🎯 Hat Trick!", "3 correct answers!"),
    (5, "🛡️ Bug Shield!", "5 correct answers! You know your Python basics!"),
    (10, "🏆 Coding Champion!", "10 correct answers! Double digits!"),
]


def load_rewards() -> dict:
    if SAVE_FILE.is_file():
        try:
            return json.loads(SAVE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"stars": 0, "streak": 0, "badges": []}


def save_rewards(data: dict):
    SAVE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def get_title(stars: int) -> str:
    current = TITLES[0][1]
    for req, title in TITLES:
        if stars >= req:
            current = title
    return current


def play():
    rewards = load_rewards()
    stars = rewards.get("stars", 0)
    badges = set(rewards.get("badges", []))

    print("\n" + "=" * 60)
    print("      🌟 CODECOACH BRAIN CHALLENGE FOR KIDS! 🌟")
    print(f"      Current Rank: {get_title(stars)}")
    print(f"      Total Stars: {'⭐' * min(stars, 15)} ({stars} stars)")
    print("=" * 60 + "\n")

    item = random.choice(QUESTIONS)
    print(f"  ❓ QUESTION:")
    print(f"  {item['q']}\n")
    for opt in item["options"]:
        print(f"    {opt}")
    print()

    choice = input("  Your answer (A, B, C, or D): ").strip().upper()

    if choice == item["answer"]:
        stars += 1
        rewards["stars"] = stars
        print("\n" + "🎉" * 20)
        print("  CORRECT! You earned +1 Star! ⭐")
        print(f"  Did you know? {item['fact']}")
        print("🎉" * 20)

        # Check for new badges
        new_badges = []
        for req, b_name, b_desc in BADGES:
            if stars >= req and b_name not in badges:
                badges.add(b_name)
                new_badges.append((b_name, b_desc))

        if new_badges:
            print("\n  🎊 NEW REWARD UNLOCKED! 🎊")
            for b_name, b_desc in new_badges:
                print(f"    🏅 {b_name} - {b_desc}")

        rewards["badges"] = sorted(list(badges))
        print(f"\n  Your New Rank: {get_title(stars)}")
    else:
        print("\n  Nice try! Almost had it!")
        print(f"  The right answer was {item['answer']}.")
        print(f"  💡 Clue: {item['fact']}")

    save_rewards(rewards)
    print("\n" + "-" * 60)
    print(f"  Total Stars: {stars} ⭐ | Badges Unlocked: {len(rewards['badges'])}")
    print("-" * 60 + "\n")


if __name__ == "__main__":
    play()
