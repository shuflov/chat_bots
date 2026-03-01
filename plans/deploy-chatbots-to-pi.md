# Deploying Chat Bots CLI to Raspberry Pi

## Overview

This document outlines the complete deployment plan for running the chat bots CLI mode on a Raspberry Pi using GitHub for code synchronization.

## Prerequisites

- GitHub repository: https://github.com/shuflov/chat_bots
- Raspberry Pi with SSH access
- Python 3.x installed on Pi

---

## Step 1: Push Code to GitHub

### On Your Local Machine

```bash
cd c:/Users/pavel/Desktop/vs_code/chat_bots

# Initialize git (if not already initialized)
git init

# Add all project files (except .env, instance/, __pycache__)
git add .
git add requirements.txt
git add server.py
git add main.py
git add bots.py
git add api.py
git add models.py
git add groq_client.py
git add conversation.py
git add public/

# Don't add these (they're local-specific):
# git reset .env
# git reset instance/
# git reset server.log

# Create initial commit
git commit -m "Initial commit: chat bots with CLI mode"

# Add your GitHub repo as remote
git remote add origin https://github.com/shuflov/chat_bots.git

# Push to GitHub
git push -u origin main
```

### Create .gitignore (Recommended)

Create a `.gitignore` file in your project root:

```
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
instance/
*.db

# Environment
.env

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Logs
*.log
server.log
```

Then:
```bash
git add .gitignore
git commit -m "Add .gitignore"
git push -u origin main
```

---

## Step 2: Set Up Your Pi

### SSH into Your Pi

```bash
ssh pi@<your-pi-ip-address>
```

Replace `<your-pi-ip-address>` with your Pi's actual IP (e.g., `192.168.1.100`)

### Clone the Repository

```bash
cd ~
git clone https://github.com/shuflov/chat_bots.git
cd chat_bots
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Set Up Environment Variables

```bash
# Option 1: Create .env file
nano .env
```

Add:
```
GROQ_API_KEY="your_actual_groq_api_key"
```

Or export directly:
```bash
export GROQ_API_KEY="your_actual_groq_api_key"
```

---

## Step 3: Run the CLI Bot - Option A: Screen (Simple)

### Install Screen

```bash
sudo apt update
sudo apt install screen
```

### Start a Screen Session

```bash
screen -S chatbot
```

### Run the Bot

```bash
cd ~/chat_bots
python server.py --cli
```

Or with custom settings:
```bash
python server.py --cli -t 10  # 10 turns
python server.py --cli -t 10 -d 15  # 10 turns, 15s delay
```

### Detach from Screen

Press `Ctrl+A`, then `D` to detach

### Reattach Later

```bash
screen -r chatbot
```

### List All Screen Sessions

```bash
screen -ls
```

---

## Step 4: Run the CLI Bot - Option B: Systemd (Auto-Start)

### Create Systemd Service File

```bash
sudo nano /etc/systemd/system/chatbot.service
```

Add the following content:

```ini
[Unit]
Description=Chat Bots CLI - Terminal Conversation
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/chat_bots
Environment="GROQ_API_KEY=your_actual_groq_api_key"
ExecStart=/usr/bin/python3 /home/pi/chat_bots/server.py --cli
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Important:** Replace `your_actual_groq_api_key` with your real API key, or remove the Environment line and ensure `.env` is used.

### Enable and Start the Service

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable on boot
sudo systemctl enable chatbot

# Start now
sudo systemctl start chatbot

# Check status
sudo systemctl status chatbot
```

### Useful Systemd Commands

```bash
# View logs
sudo journalctl -u chatbot -f

# Restart
sudo systemctl restart chatbot

# Stop
sudo systemctl stop chatbot

# Disable
sudo systemctl disable chatbot
```

---

## Step 5: Updating the Bot

When you push changes to GitHub:

### On Your Pi

```bash
cd ~/chat_bots
git pull origin main
```

If using Systemd, restart after update:
```bash
sudo systemctl restart chatbot
```

---

## Summary: Files to Transfer

| File | Purpose | Required |
|------|---------|----------|
| `server.py` | Main app with CLI mode | ✅ |
| `main.py` | Entry point | ✅ |
| `bots.py` | Bot configurations | ✅ |
| `api.py` | API routes | ✅ |
| `models.py` | Database models | ✅ |
| `groq_client.py` | Groq API client | ✅ |
| `conversation.py` | Conversation logic | ✅ |
| `requirements.txt` | Python dependencies | ✅ |
| `.env` | API key (create on Pi) | ✅ |
| `public/` | Web UI (not needed for CLI) | ❌ |
| `instance/` | Local database | ❌ |

source venv/bin/activate

---

## Quick Reference: Common Commands

### On Local Machine (Push Updates)
```bash
git add .
git commit -m "Your message"
git push origin main
```

### On Pi (Pull Updates)
```bash
cd ~/chat_bots
git pull
```

### Run CLI Mode Manually
```bash
python server.py --cli -t 10 -d 30
```

### Check GitHub Repo
https://github.com/shuflov/chat_bots
