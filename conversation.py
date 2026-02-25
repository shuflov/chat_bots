import time
from bots import BOTS, BOT_ORDER
import groq_client


COLORS = {
    "philosopher": "\033[96m",
    "engineer": "\033[93m",
    "user": "\033[92m",
    "reset": "\033[0m",
}

REPLY_DELAY = 30
MAX_TURNS = 20


def print_message(sender: str, text: str, color: str):
    print(f"{color}{sender}:{COLORS['reset']} {text}")


def run_conversation(initial_message: str):
    from api import app, db, Conversation, Message

    history = {
        "philosopher": [],
        "engineer": [],
    }

    print("\n" + "=" * 50)
    print("Starting conversation...")
    print("=" * 50 + "\n")

    print_message("You", initial_message, COLORS["user"])

    history["philosopher"].append({"role": "user", "content": initial_message})
    history["engineer"].append({"role": "user", "content": initial_message})

    with app.app_context():
        conv = Conversation(title=initial_message[:50] + "...")
        db.session.add(conv)
        db.session.commit()

        user_msg = Message(conversation_id=conv.id, sender="You", content=initial_message)
        db.session.add(user_msg)
        db.session.commit()

    current_bot_idx = 0

    for turn in range(MAX_TURNS):
        bot_key = BOT_ORDER[current_bot_idx]
        bot = BOTS[bot_key]

        print(f"\n[Waiting {REPLY_DELAY}s for {bot['name']}'s response...]")
        time.sleep(REPLY_DELAY)

        response = groq_client.chat(bot["system_prompt"], history[bot_key])

        history[bot_key].append({"role": "assistant", "content": response})

        other_bot = BOT_ORDER[1 - current_bot_idx]
        history[other_bot].append({"role": "user", "content": f"{bot['name']}: {response}"})

        print_message(bot["name"], response, COLORS[bot_key])

        with app.app_context():
            msg = Message(conversation_id=conv.id, sender=bot["name"], content=response)
            db.session.add(msg)
            db.session.commit()

        current_bot_idx = 1 - current_bot_idx

    print("\n" + "=" * 50)
    print("Conversation ended (max turns reached)")
    print("=" * 50 + "\n")

