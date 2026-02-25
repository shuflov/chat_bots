from flask import Flask, jsonify, request, send_from_directory
from models import db, Conversation, Message, Personality, init_presets
import threading
import time
import groq_client

app = Flask(__name__, static_folder="public")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///conversations.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)

BOT_ORDER = ["bot1", "bot2"]


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
    personalities = Personality.query.order_by(Personality.is_preset.desc(), Personality.name).all()
    return jsonify([
        {
            "id": p.id,
            "name": p.name,
            "system_prompt": p.system_prompt,
            "is_preset": p.is_preset
        }
        for p in personalities
    ])


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


def init_db():
    with app.app_context():
        db.create_all()
        init_presets()


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)
