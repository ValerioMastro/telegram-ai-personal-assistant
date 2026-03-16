# Telegram AI Personal Assistant

![Python](https://img.shields.io/badge/Python-3.11-blue)
![Telegram Bot](https://img.shields.io/badge/Telegram-Bot-26A5E4)
![SQLite](https://img.shields.io/badge/Database-SQLite-lightgrey)
![Status](https://img.shields.io/badge/Status-Active-success)

An intelligent Telegram personal assistant built to manage **calendar, tasks, notes, memory, planning**, and a fully integrated **fitness coach** for both **gym training** and **HYROX preparation**.

Designed as a practical daily assistant, this project combines conversational UX, structured workflows, and modular services to support productivity, training, and personal organization from a single Telegram bot.

---

# Overview

This bot is designed to be more than a simple chatbot. It acts as a **personal operating system on Telegram**, helping the user manage:

- calendar events  
- tasks and reminders  
- notes and personal memory  
- day planning  
- guided fitness tracking  
- HYROX preparation and performance progression  

The architecture is modular and built to evolve safely over time, with backward-compatible behavior and production-oriented deployment.

---

# Main Features

## Productivity Assistant

- Google Calendar integration  
- task creation and tracking  
- note capture and quick retrieval  
- personal memory and context-aware assistance  
- weekly/day planning support  
- reminder and scheduling logic  

## Fitness Coach

- guided gym workout tracking  
- guided HYROX workout tracking  
- workout dashboards by training day  
- automatic load suggestions  
- progression recommendations  
- baseline weight tracking  
- intelligent estimation for missing sessions  
- recovery check and readiness score  
- weekly training planner  
- race preparation mode for HYROX  

## Telegram-First UX

- menu-based navigation  
- inline buttons for guided workflows  
- step-by-step exercise logging  
- fast interaction designed for real-world daily use  
- easy updating of loads, reps, and workout history  

## Backend / Architecture

- modular runtime  
- legacy-safe fallback behavior  
- SQLite persistence  
- Google integrations  
- deployable on a low-cost/free VPS  
- designed for incremental refactors without breaking production  

---

# Fitness Module Highlights

The fitness system is one of the most advanced parts of the bot.

It supports two parallel coaching flows.

## 1. Gym Training Coach

Tracks and improves structured strength training sessions:

- Day A — Push + Triceps  
- Day B — Pull + Biceps  
- Day C — Legs + Arms  
- Day D — Upper Light + Arms  

For each exercise, the bot can:

- show latest load  
- suggest starting weight  
- ask for kg, reps, and RIR  
- save performance  
- recommend next progression  
- estimate missing exercise loads from similar movements  

## 2. HYROX Coach

Tracks and improves:

- running intervals  
- easy runs / base runs  
- wall balls  
- burpees  
- lunges  
- specific race-oriented sessions  

It can:

- convert treadmill speed to pace  
- compare current pace with target pace  
- guide progression toward HYROX goals  
- support race-prep planning and weekly structure  

---

# Example Use Cases

This assistant can be used to:

- ask “what do I have today?”  
- create or cancel tasks  
- save personal notes or reminders  
- manage weekly workload  
- log a gym session exercise by exercise  
- update current training loads  
- track running sessions  
- prepare for HYROX with structured progression  
- calculate a smart weekly training plan based on recovery and past workouts  

---

# Tech Stack

- **Python**
- **Telegram Bot API** via `python-telegram-bot`
- **Google Calendar API**
- **Google OAuth**
- **SQLite**
- **Gemini / Google GenAI**
- modular service-oriented internal architecture
- deploy script for VPS environments

---

# Project Structure

```text
telegram-calendar-agent/
│
├── main.py
├── agent.py
├── config.py
├── db.py
├── deploy.sh
├── requirements.txt
│
├── agent_runtime/
│   ├── __init__.py
│   ├── assistant.py
│   ├── context_service.py
│   ├── formatters.py
│   ├── models.py
│   └── router.py
│
├── agents/
│   ├── calendar_agent.py
│   ├── memory_agent.py
│   ├── notes_agent.py
│   ├── personal_agent.py
│   ├── planner_agent.py
│   ├── task_agent.py
│   └── workout_agent.py
│
├── services/
│   ├── followup_service.py
│   ├── pending_actions_service.py
│   ├── llm_service.py
│   ├── workout_progression_service.py
│   ├── running_progression_service.py
│   ├── hyrox_training_service.py
│   └── workout_dashboard_service.py
│
├── tools/
│   ├── calendar_tools.py
│   ├── memory_tools_adapter.py
│   ├── notes_tools_adapter.py
│   ├── planner_tools.py
│   ├── task_tools_adapter.py
│   └── workout_tools_adapter.py
│
├── tests/
│   ├── test_formatters.py
│   ├── test_router_smoke.py
│   ├── test_tools_smoke.py
│   ├── test_workout_agent.py
│   ├── test_running_tracker.py
│   └── test_hyrox_tracker.py
│
└── ...
```

The exact structure may evolve over time as the project grows.

---

# How It Works

The bot follows a modular request flow.

1. Telegram receives a user message  
2. `main.py` forwards it to the runtime assistant  
3. The router decides whether the message belongs to:
   - pending actions  
   - follow-up flow  
   - shortcuts  
   - productivity logic  
   - fitness logic  
   - legacy fallback  
4. The appropriate service or agent handles the request  
5. The result is returned to Telegram  

This architecture allows the bot to scale while keeping backward compatibility.

---

# Setup

## 1. Clone the repository

```bash
git clone https://github.com/ValerioMastro/telegram-ai-personal-assistant.git
cd telegram-ai-personal-assistant
```

## 2. Create the virtual environment

```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

## 3. Install dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

## 4. Configure environment variables

Create a `.env` file based on `.env.example`.

Typical variables include:

- Telegram bot token  
- Gemini / Google AI key  
- calendar settings  
- timezone  
- feature flags  

## 5. Add Google credentials

Place your Google credentials files in the project root if needed:

- `credentials.json`
- `token.json`

---

# Run Locally

```bash
source .venv/bin/activate
python main.py
```

---

# Run Tests

```bash
python -m pytest -q
```

Optional compile checks:

```bash
python -m py_compile main.py
python -m py_compile agent.py
python -m py_compile config.py
find agent_runtime agents tools services tests -name "*.py" -exec python -m py_compile {} \;
```

---

# Deploy

The repository includes a ready-to-use deploy script.

```bash
./deploy.sh
```

The script typically:

- synchronizes the code with the server  
- excludes local-only files  
- updates dependencies  
- backs up the SQLite database  
- restarts the bot  

---

# Example Commands

## Productivity

- `cosa ho oggi?`
- `che ho domani`
- `mostrami i task`
- `aggiungi task finire slide`
- `ricorda che studio meglio la sera`

## Gym Tracking

- `fitness`
- `scheda`
- `giorno A`
- `inizia allenamento`
- `aggiorna panca 72.5`
- `carichi attuali`
- `dashboard giorno A`

## HYROX

- `dashboard hyrox`
- `ho fatto 4x1km a 10 km/h`
- `wall ball 5x20`
- `burpees 5x10`
- `affondi 4x12 per lato`
- `quanto mi manca per 4:30/km`

## Planning / Readiness / Race Prep

- `pianifica settimana`
- `mostra settimana`
- `check recupero`
- `dashboard recupero`
- `modalità gara`
- `fase preparazione`
- `dashboard gara`

---

# Why This Project Is Interesting

This is not just a standard bot. It is a real-world personal assistant built around:

- daily usefulness  
- structured workflows  
- production-safe incremental architecture  
- practical Telegram UX  
- integration of productivity and athletic coaching in one system  

It combines:

- conversational AI  
- workflow automation  
- personal knowledge and memory  
- sports tracking  
- goal-oriented planning  

all in a single deployable project.

---

# Roadmap

Possible future improvements:

- better analytics dashboard  
- richer Telegram UI flows  
- improved training load visualization  
- session summaries and weekly reports  
- smarter adaptive progression engine  
- better race simulation features  
- more robust state handling for guided workflows  

---

# Safety / Design Philosophy

This project is built with the following principles:

- do not break production behavior  
- prefer incremental refactors  
- keep legacy fallback when useful  
- make daily interactions fast and practical  
- prioritize real usability over flashy complexity  

---

# Author

**Valerio Mastro**

Master’s student in Computer Engineering with focus on AI, building practical software projects that combine productivity, automation, and performance tracking.

GitHub:  
https://github.com/ValerioMastro

---

# License

You can choose the license you prefer.

A common option is:

```
MIT License
```

Create a `LICENSE` file accordingly.

---

# Final Note

This repository represents an evolving personal assistant designed around real daily needs:

- study  
- work  
- planning  
- training  
- performance improvement  

It is both a **practical daily tool** and a **modular software engineering project**.
