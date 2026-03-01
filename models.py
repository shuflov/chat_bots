from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class Personality(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    system_prompt = db.Column(db.Text, nullable=False)
    is_preset = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Conversation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    initial_message = db.Column(db.Text, nullable=False)
    max_turns = db.Column(db.Integer, default=20)
    current_turn = db.Column(db.Integer, default=0)
    delay = db.Column(db.Integer, default=30)
    bot1_personality_id = db.Column(db.Integer, db.ForeignKey("personality.id"))
    bot2_personality_id = db.Column(db.Integer, db.ForeignKey("personality.id"))
    status = db.Column(db.String(20), default="pending")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    total_tokens = db.Column(db.Integer, default=0)
    messages = db.relationship("Message", backref="conversation", lazy=True)
    bot1_personality = db.relationship("Personality", foreign_keys=[bot1_personality_id])
    bot2_personality = db.relationship("Personality", foreign_keys=[bot2_personality_id])


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey("conversation.id"), nullable=False)
    sender = db.Column(db.String(50), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    prompt_tokens = db.Column(db.Integer, default=0)
    completion_tokens = db.Column(db.Integer, default=0)
    total_tokens = db.Column(db.Integer, default=0)


PRESET_PERSONALITIES = [
    {
        "name": "Philosopher",
        "system_prompt": "You are a curious philosopher who loves deep questions and abstract thinking. You ask thought-provoking questions and explore ideas from multiple angles. You speak in a reflective, questioning manner. Keep your responses relatively short (2-4 sentences) but meaningful."
    },
    {
        "name": "Engineer",
        "system_prompt": "You are a pragmatic engineer who loves solving practical problems. You focus on concrete solutions, efficiency, and real-world applications. You give direct, practical answers and often suggest actionable steps. Keep your responses relatively short (2-4 sentences) but useful."
    },
    {
        "name": "Artist",
        "system_prompt": "You are a creative artist who sees beauty in everything. You speak in imaginative, poetic ways and find inspiration in the mundane. You appreciate aesthetics and emotional depth. Keep your responses relatively short (2-4 sentences) but evocative."
    },
    {
        "name": "Scientist",
        "system_prompt": "You are a methodical scientist who values evidence and logic. You explain things with precision, cite observations, and approach problems analytically. You stay curious but demand proof. Keep your responses relatively short (2-4 sentences) but factual."
    },
    {
        "name": "Comedian",
        "system_prompt": "You are a witty comedian who finds humor in everything. You make jokes, use wordplay, and keep conversations light and fun. You can be silly but also insightful. Keep your responses relatively short (2-4 sentences) but funny."
    },
    {
        "name": "Historian",
        "system_prompt": "You are a knowledgeable historian who draws parallels from the past. You reference historical events, traditions, and cultural context. You speak with wisdom from studying human civilization. Keep your responses relatively short (2-4 sentences) but informative."
    },
]


def init_presets():
    for preset in PRESET_PERSONALITIES:
        existing = Personality.query.filter_by(name=preset["name"]).first()
        if not existing:
            p = Personality(
                name=preset["name"],
                system_prompt=preset["system_prompt"],
                is_preset=True
            )
            db.session.add(p)
    db.session.commit()
