"""
Server module for Chat Bot Conversations.
Provides both CLI-only mode and web server mode.

Usage:
    CLI-only mode (terminal only, no web):
        python server.py --cli
        
    Web server mode:
        python server.py
        python server.py --web
        python server.py --web --port 5000
        
    Show help:
        python server.py --help
"""

import os
import sys
import argparse
import time
from flask import Flask, jsonify, request, send_from_directory
from models import db, Conversation, Message, Personality, init_presets
import groq_client
import threading


# Flask app configuration
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///conversations.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)

BOT_ORDER = ["bot1", "bot2"]

# Default settings (can be overridden by CLI args)
DEFAULT_MAX_TURNS = 20
DEFAULT_DELAY = 30


# ============== Database Routes ==============

@app.route("/api/defaults")
def get_defaults():
    return jsonify({
        "max_turns": DEFAULT_MAX_TURNS,
        "delay": DEFAULT_DELAY
    })


@app.route("/")
def index():
    return send_from_directory("public", "index.html")


@app.route("/start")
def start_page():
    return send_from_directory("public", "start.html")


@app.route("/conversation/<int:conv_id>")
def conversation_page(conv_id):
    return send_from_directory("public", "conversation.html")


@app.route("/<path:filename>")
def static_files(filename):
    return send_from_directory("public", filename)


@app.route("/api/personalities", methods=["GET"])
def get_personalities():
    global DEFAULT_MAX_TURNS, DEFAULT_DELAY
    personalities = Personality.query.order_by(Personality.is_preset.desc(), Personality.name).all()
    return jsonify({
        "personalities": [
            {
                "id": p.id,
                "name": p.name,
                "system_prompt": p.system_prompt,
                "is_preset": p.is_preset
            }
            for p in personalities
        ],
        "defaults": {
            "max_turns": DEFAULT_MAX_TURNS,
            "delay": DEFAULT_DELAY
        }
    })


@app.route("/api/personalities", methods=["POST"])
def create_personality():
    data = request.json
    existing = Personality.query.filter_by(name=data["name"]).first()
    if existing:
        return jsonify({"error": "Personality already exists"}), 400
    
    p = Personality(
        name=data["name"],
        system_prompt=data["system_prompt"],
        is_preset=False
    )
    db.session.add(p)
    db.session.commit()
    return jsonify({"id": p.id, "name": p.name}), 201


@app.route("/api/personalities/<int:pid>", methods=["DELETE"])
def delete_personality(pid):
    p = Personality.query.get_or_404(pid)
    if p.is_preset:
        return jsonify({"error": "Cannot delete preset personalities"}), 400
    db.session.delete(p)
    db.session.commit()
    return jsonify({"success": True})


@app.route("/api/conversations", methods=["GET"])
def get_conversations():
    conversations = Conversation.query.order_by(Conversation.created_at.desc()).all()
    return jsonify([
        {
            "id": c.id,
            "title": c.title,
            "status": c.status,
            "current_turn": c.current_turn,
            "max_turns": c.max_turns,
            "created_at": c.created_at.isoformat()
        }
        for c in conversations
    ])


@app.route("/api/conversations/<int:conv_id>", methods=["GET"])
def get_conversation(conv_id):
    conv = Conversation.query.get_or_404(conv_id)
    messages = Message.query.filter_by(conversation_id=conv_id).order_by(Message.timestamp).all()
    return jsonify({
        "id": conv.id,
        "title": conv.title,
        "initial_message": conv.initial_message,
        "max_turns": conv.max_turns,
        "current_turn": conv.current_turn,
        "remaining": conv.max_turns - conv.current_turn,
        "delay": conv.delay,
        "status": conv.status,
        "bot1_personality": conv.bot1_personality.name if conv.bot1_personality else None,
        "bot2_personality": conv.bot2_personality.name if conv.bot2_personality else None,
        "created_at": conv.created_at.isoformat(),
        "messages": [
            {
                "sender": m.sender,
                "content": m.content,
                "timestamp": m.timestamp.isoformat()
            }
            for m in messages
        ]
    })


@app.route("/api/conversations", methods=["POST"])
def create_conversation():
    data = request.json
    
    bot1 = Personality.query.get(data.get("bot1_personality_id"))
    bot2 = Personality.query.get(data.get("bot2_personality_id"))
    
    if not bot1 or not bot2:
        return jsonify({"error": "Invalid personality selection"}), 400
    
    conv = Conversation(
        title=data.get("title", "Untitled")[:50] or "Untitled",
        initial_message=data["initial_message"],
        max_turns=data.get("max_turns", 20),
        delay=data.get("delay", 30),
        bot1_personality_id=bot1.id,
        bot2_personality_id=bot2.id,
        status="pending"
    )
    db.session.add(conv)
    db.session.commit()
    
    user_msg = Message(conversation_id=conv.id, sender="You", content=data["initial_message"])
    db.session.add(user_msg)
    db.session.commit()
    
    thread = threading.Thread(target=run_conversation_thread, args=(conv.id,))
    thread.start()
    
    return jsonify({"id": conv.id}), 201


@app.route("/api/conversations/<int:conv_id>/stop", methods=["POST"])
def stop_conversation(conv_id):
    conv = Conversation.query.get_or_404(conv_id)
    if conv.status == "running":
        conv.status = "stopped"
        db.session.commit()
    return jsonify({"success": True})


@app.route("/api/conversations/<int:conv_id>", methods=["PUT"])
def update_conversation(conv_id):
    conv = Conversation.query.get_or_404(conv_id)
    data = request.json
    if "title" in data:
        conv.title = data["title"][:50] or "Untitled"
    db.session.commit()
    return jsonify({"success": True})


@app.route("/api/conversations/<int:conv_id>", methods=["DELETE"])
def delete_conversation(conv_id):
    conv = Conversation.query.get_or_404(conv_id)
    Message.query.filter_by(conversation_id=conv_id).delete()
    db.session.delete(conv)
    db.session.commit()
    return jsonify({"success": True})


# ============== Conversation Thread ==============

def run_conversation_thread(conv_id):
    with app.app_context():
        conv = Conversation.query.get(conv_id)
        if not conv:
            return
        
        conv.status = "running"
        db.session.commit()
        
        bot1 = {"name": conv.bot1_personality.name, "system_prompt": conv.bot1_personality.system_prompt}
        bot2 = {"name": conv.bot2_personality.name, "system_prompt": conv.bot2_personality.system_prompt}
        
        BOTS = {"bot1": bot1, "bot2": bot2}
        
        history = {
            "bot1": [{"role": "user", "content": conv.initial_message}],
            "bot2": [{"role": "user", "content": conv.initial_message}],
        }
        
        current_bot_idx = 0
        
        for turn in range(conv.max_turns):
            conv = Conversation.query.get(conv_id)
            if conv.status == "stopped":
                break
            
            bot_key = BOT_ORDER[current_bot_idx]
            bot = BOTS[bot_key]
            
            time.sleep(conv.delay)
            
            conv = Conversation.query.get(conv_id)
            if conv.status == "stopped":
                break
            
            response = groq_client.chat(bot["system_prompt"], history[bot_key])
            
            history[bot_key].append({"role": "assistant", "content": response})
            
            other_bot = BOT_ORDER[1 - current_bot_idx]
            history[other_bot].append({"role": "user", "content": f"{bot['name']}: {response}"})
            
            msg = Message(conversation_id=conv.id, sender=bot["name"], content=response)
            db.session.add(msg)
            conv.current_turn = turn + 1
            db.session.commit()
            
            current_bot_idx = 1 - current_bot_idx
        
        conv = Conversation.query.get(conv_id)
        conv.status = "completed" if conv.status == "running" else conv.status
        db.session.commit()


# ============== CLI-Only Mode ==============

CLI_COLORS = {
    "bot1": "\033[96m",  # Cyan
    "bot2": "\033[93m",  # Yellow
    "user": "\033[92m",  # Green
    "reset": "\033[0m",
}


def run_cli_conversation(initial_message: str, max_turns: int = 20, delay: int = 30):
    """
    Run a conversation in CLI-only mode (no web server).
    Uses the first two available personalities as bot1 and bot2.
    """
    with app.app_context():
        # Get personalities
        personalities = Personality.query.order_by(Personality.is_preset.desc(), Personality.name).all()
        
        if len(personalities) < 2:
            print("Error: Need at least 2 personalities to run a conversation.")
            print("Please create more personalities via the web interface first.")
            return
        
        bot1 = personalities[0]
        bot2 = personalities[1]
        
        print(f"\n{'=' * 50}")
        print(f"Starting CLI Conversation")
        print(f"Bot 1: {bot1.name}")
        print(f"Bot 2: {bot2.name}")
        print(f"Max turns: {max_turns}")
        print(f"Delay between responses: {delay} seconds")
        print(f"{'=' * 50}\n")
        
        # Create conversation in database
        conv = Conversation(
            title=initial_message[:50] + "...",
            initial_message=initial_message,
            max_turns=max_turns,
            delay=delay,
            bot1_personality_id=bot1.id,
            bot2_personality_id=bot2.id,
            status="running"
        )
        db.session.add(conv)
        db.session.commit()
        
        user_msg = Message(conversation_id=conv.id, sender="You", content=initial_message)
        db.session.add(user_msg)
        db.session.commit()
        
        # Initialize history
        BOTS = {
            "bot1": {"name": bot1.name, "system_prompt": bot1.system_prompt},
            "bot2": {"name": bot2.name, "system_prompt": bot2.system_prompt}
        }
        
        history = {
            "bot1": [{"role": "user", "content": initial_message}],
            "bot2": [{"role": "user", "content": initial_message}],
        }
        
        # Print initial message
        print(f"{CLI_COLORS['user']}You:{CLI_COLORS['reset']} {initial_message}\n")
        
        current_bot_idx = 0
        
        try:
            for turn in range(max_turns):
                bot_key = BOT_ORDER[current_bot_idx]
                bot = BOTS[bot_key]
                
                print(f"{CLI_COLORS['reset']}[Waiting {delay}s for {bot['name']}'s response...]")
                time.sleep(delay)
                
                response = groq_client.chat(bot["system_prompt"], history[bot_key])
                
                history[bot_key].append({"role": "assistant", "content": response})
                
                other_bot = BOT_ORDER[1 - current_bot_idx]
                history[other_bot].append({"role": "user", "content": f"{bot['name']}: {response}"})
                
                # Print bot response with color
                color = CLI_COLORS[bot_key]
                print(f"{color}{bot['name']}:{CLI_COLORS['reset']} {response}\n")
                
                # Save to database
                msg = Message(conversation_id=conv.id, sender=bot["name"], content=response)
                db.session.add(msg)
                conv.current_turn = turn + 1
                db.session.commit()
                
                current_bot_idx = 1 - current_bot_idx
            
            # Mark as completed
            conv.status = "completed"
            db.session.commit()
            
        except KeyboardInterrupt:
            print("\n\nConversation stopped by user.")
            conv.status = "stopped"
            db.session.commit()
        
        print(f"\n{'=' * 50}")
        print("Conversation ended")
        print(f"{'=' * 50}\n")


def init_database():
    """Initialize the database and create tables."""
    with app.app_context():
        db.create_all()
        init_presets()


# ============== Main Entry Points ==============

def main():
    parser = argparse.ArgumentParser(
        description="Chat Bot Conversations Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python server.py              # Run web server (default)
  python server.py --web         # Run web server explicitly
  python server.py --web -t 10   # Web server with default 10 turns
  python server.py --web -d 15   # Web server with default 15s delay
  python server.py --web -t 10 -d 15  # Web server with custom settings
  python server.py --cli         # Run CLI-only mode (terminal only)
  python server.py --cli -t 10   # CLI mode with 10 turns
  python server.py --port 8080   # Web server on port 8080
        """
    )
    
    parser.add_argument(
        "--web", 
        action="store_true",
        help="Run web server mode"
    )
    
    parser.add_argument(
        "--cli", 
        action="store_true",
        help="Run CLI-only mode (terminal only, no web)"
    )
    
    parser.add_argument(
        "--port", 
        type=int, 
        default=5000,
        help="Port for web server (default: 5000)"
    )
    
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host for web server (default: 0.0.0.0)"
    )
    
    parser.add_argument(
        "-t", "--turns",
        type=int,
        default=20,
        help="Default max turns for conversations (default: 20)"
    )
    
    parser.add_argument(
        "-d", "--delay",
        type=int,
        default=30,
        help="Default delay between responses in seconds (default: 30)"
    )
    
    args = parser.parse_args()
    
    # Check for API key
    if not os.getenv("GROQ_API_KEY") or os.getenv("GROQ_API_KEY") == "your_groq_api_key_here":
        print("Error: GROQ_API_KEY not set in .env")
        print("Get your key at: https://console.groq.com/")
        print("\nEdit .env file and add your key, then run again.")
        sys.exit(1)
    
    # Initialize database
    init_database()
    
    # Set global defaults from CLI arguments
    global DEFAULT_MAX_TURNS, DEFAULT_DELAY
    DEFAULT_MAX_TURNS = args.turns
    DEFAULT_DELAY = args.delay
    
    # Determine mode
    if args.cli:
        # CLI-only mode
        print("=== Chat Bot Conversations (CLI Mode) ===")
        print("Bot 1: First personality in database")
        print("Bot 2: Second personality in database")
        print(f"\nDelay between responses: {args.delay} seconds")
        print(f"Max turns: {args.turns}")
        print("\nType your first message to start the conversation:")
        
        initial = input("\n> ").strip()
        if not initial:
            print("Please enter a message to start.")
            sys.exit(1)
        
        run_cli_conversation(initial, args.turns, args.delay)
        
    else:
        # Web server mode (default)
        print(f"=== Chat Bot Conversations (Web Server) ===")
        print(f"Starting web server on http://{args.host}:{args.port}")
        print(f"Default max turns: {args.turns}")
        print(f"Default delay between responses: {args.delay} seconds")
        print("Press Ctrl+C to stop")
        
        # Run with debug=False for Raspberry Pi
        app.run(host=args.host, port=args.port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
