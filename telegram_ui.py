from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup

MAIN_REPLY_LAYOUT = [
    ["📅 Oggi", "📆 Domani"],
    ["🧠 Cattura", "📋 Planner"],
    ["✅ Task", "📝 Note"],
    ["📥 Inbox", "🧩 Memoria"],
    ["⚡ Quick Add", "❓ Help"],
    ["📅 Settimana"],
]


def build_main_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        MAIN_REPLY_LAYOUT,
        resize_keyboard=True,
        one_time_keyboard=False,
        input_field_placeholder="Scrivi o scegli un'azione rapida...",
    )


def build_help_main() -> str:
    return (
        "Help rapido\n\n"
        "📅 Calendario\n"
        "- agenda oggi/domani/settimana\n"
        "- creazione/modifica/cancellazione eventi\n"
        "- slot liberi e gestione conflitti\n\n"
        "✅ Task\n"
        "- aggiungi, completa, snooze, sposta, elimina\n"
        "- categorie/priorità e task urgenti\n\n"
        "📝 Note\n"
        "- salvataggio, ricerca e conversione in task/evento\n\n"
        "📥 Inbox\n"
        "- cattura rapida se input ambiguo\n"
        "- conversione in evento/task/nota/memoria\n\n"
        "🧩 Memoria\n"
        "- preferenze personali persistenti\n\n"
        "📋 Planner\n"
        "- planner oggi, preview domani, settimana\n"
        "- recap automatici 09:00 e 18:00\n\n"
        "🎤 Audio\n"
        "- invia vocali: trascrizione e gestione come testo"
    )


def build_help_calendar() -> str:
    return (
        "Help Calendario\n\n"
        "Esempi:\n"
        "- che ho oggi?\n"
        "- che ho domani?\n"
        "- cosa ho il 15 marzo?\n"
        "- domani alle 18 palestra\n"
        "- cancella l'evento 2\n"
        "- sposta il primo a domani\n"
        "- quando sono libero domani?"
    )


def build_help_tasks() -> str:
    return (
        "Help Task\n\n"
        "Esempi:\n"
        "- aggiungi task finire slide Deloitte\n"
        "- ricordami di bere acqua fra 10 minuti\n"
        "- mostra task lavoro\n"
        "- completa il 2\n"
        "- snooze del primo a stasera"
    )


def build_help_notes() -> str:
    return (
        "Help Note\n\n"
        "Esempi:\n"
        "- segnati questa idea: dashboard CRM\n"
        "- salva nota: ripassare Nyquist\n"
        "- cerca note CRM\n"
        "- ultime 5 note"
    )


def build_help_inbox() -> str:
    return (
        "Help Inbox\\n\\n"
        "Quando l'input è ambiguo viene salvato in Inbox.\\n"
        "Esempi:\\n"
        "- Paolo venerdì\\n"
        "- idea app\\n"
        "- vacanza agosto\\n\\n"
        "Poi puoi convertire in:\\n"
        "- evento\\n"
        "- task\\n"
        "- nota\\n"
        "- memoria"
    )


def build_help_memory() -> str:
    return (
        "Help Memoria\n\n"
        "Esempi:\n"
        "- ricorda che studio meglio la sera\n"
        "- ricorda che mi alleno alle 18\n"
        "- cerca memoria allenamento"
    )


def build_help_planner() -> str:
    return (
        "Help Planner\n\n"
        "Comandi:\n"
        "- /planner\n"
        "- /settimana\n"
        "- /irrisolti\n\n"
        "Mostra:\n"
        "- eventi\n"
        "- task aperti/urgenti\n"
        "- inbox\n"
        "- focus lavoro/studio/allenamento/personale"
    )


def build_help_inline_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📅 Calendario", callback_data="help_calendar")],
            [InlineKeyboardButton("✅ Task", callback_data="help_tasks")],
            [InlineKeyboardButton("📝 Note", callback_data="help_notes")],
            [InlineKeyboardButton("📥 Inbox", callback_data="help_inbox")],
            [InlineKeyboardButton("🧩 Memoria", callback_data="help_memory")],
            [InlineKeyboardButton("📋 Planner", callback_data="help_planner")],
        ]
    )


def build_help_section_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("⬅️ Help", callback_data="help_main"),
                InlineKeyboardButton("📋 Planner", callback_data="show_planner"),
            ],
            [
                InlineKeyboardButton("📅 Calendario", callback_data="help_calendar"),
                InlineKeyboardButton("✅ Task", callback_data="help_tasks"),
            ],
            [
                InlineKeyboardButton("📝 Note", callback_data="help_notes"),
                InlineKeyboardButton("📥 Inbox", callback_data="help_inbox"),
            ],
            [InlineKeyboardButton("🧩 Memoria", callback_data="help_memory")],
        ]
    )


def build_confirmation_keyboard(
    confirm_callback: str = "confirm_pending_action",
    cancel_callback: str = "cancel_pending_action",
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Conferma", callback_data=confirm_callback),
                InlineKeyboardButton("❌ Annulla", callback_data=cancel_callback),
            ]
        ]
    )


def build_duplicate_warning_keyboard(
    confirm_callback: str = "confirm_pending_action",
    cancel_callback: str = "cancel_pending_action",
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Crea comunque", callback_data=confirm_callback),
                InlineKeyboardButton("❌ Annulla", callback_data=cancel_callback),
            ]
        ]
    )


def build_quick_add_inline_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("➕ Evento", callback_data="quick_add_event"),
                InlineKeyboardButton("➕ Task", callback_data="quick_add_task"),
            ],
            [
                InlineKeyboardButton("➕ Nota", callback_data="quick_add_note"),
                InlineKeyboardButton("➕ Inbox", callback_data="quick_add_inbox"),
            ],
            [InlineKeyboardButton("⬅️ Planner", callback_data="show_planner")],
        ]
    )


def build_snooze_keyboard(task_index: int | None = None, task_id: int | None = None) -> InlineKeyboardMarkup:
    if task_id is not None:
        complete_cb = f"task_complete_id_{task_id}"
        prefix = f"task_snooze_id_{task_id}"
    else:
        idx = task_index or 1
        complete_cb = f"task_complete_index_{idx}"
        prefix = f"task_snooze_index_{idx}"

    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✅ Fatto", callback_data=complete_cb)],
            [
                InlineKeyboardButton("+10 min", callback_data=f"{prefix}_10m"),
                InlineKeyboardButton("+30 min", callback_data=f"{prefix}_30m"),
            ],
            [
                InlineKeyboardButton("stasera", callback_data=f"{prefix}_stasera"),
                InlineKeyboardButton("domani", callback_data=f"{prefix}_domani"),
            ],
            [InlineKeyboardButton("weekend", callback_data=f"{prefix}_weekend")],
        ]
    )


def build_event_actions_keyboard(list_size: int = 0, current_view: str = "today") -> InlineKeyboardMarkup:
    refresh_cb = "show_today" if current_view == "today" else "show_tomorrow"
    rows = [
        [InlineKeyboardButton("🔄 Aggiorna", callback_data=refresh_cb)],
        [
            InlineKeyboardButton("❌ Cancella evento", callback_data="hint_delete_event"),
            InlineKeyboardButton("✏️ Sposta evento", callback_data="hint_move_event"),
        ],
        [
            InlineKeyboardButton("📅 Oggi", callback_data="show_today"),
            InlineKeyboardButton("📆 Domani", callback_data="show_tomorrow"),
        ],
        [
            InlineKeyboardButton("📅 Settimana", callback_data="show_week_summary"),
            InlineKeyboardButton("📍 Slot liberi", callback_data="calendar_free_slots_today"),
        ],
    ]

    if list_size > 0:
        max_buttons = min(list_size, 4)
        rows.append(
            [
                InlineKeyboardButton(f"❌ {i}", callback_data=f"event_delete_index_{i}")
                for i in range(1, max_buttons + 1)
            ]
        )
        rows.append(
            [
                InlineKeyboardButton(f"✏️ {i}", callback_data=f"event_move_index_{i}")
                for i in range(1, max_buttons + 1)
            ]
        )

    rows.append([InlineKeyboardButton("📅 Calendar Center", callback_data="open_calendar_center")])
    rows.append([InlineKeyboardButton("📋 Planner", callback_data="show_planner")])
    return InlineKeyboardMarkup(rows)


def build_task_actions_keyboard(list_size: int = 0) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton("✅ Completa task", callback_data="hint_complete_task"),
            InlineKeyboardButton("⏰ Snooze", callback_data="hint_snooze_task"),
        ],
        [
            InlineKeyboardButton("🔥 Irrisolti", callback_data="show_unresolved_tasks"),
            InlineKeyboardButton("📋 Planner", callback_data="show_planner"),
        ],
        [
            InlineKeyboardButton("➕ Aggiungi task", callback_data="hint_add_task"),
            InlineKeyboardButton("🧭 Task Center", callback_data="open_task_center"),
        ],
    ]

    if list_size > 0:
        max_buttons = min(list_size, 4)
        rows.append(
            [
                InlineKeyboardButton(f"✅ {i}", callback_data=f"task_complete_index_{i}")
                for i in range(1, max_buttons + 1)
            ]
        )
        rows.append(
            [
                InlineKeyboardButton(f"⏰ {i}", callback_data=f"task_snooze_index_{i}_10m")
                for i in range(1, max_buttons + 1)
            ]
        )

    return InlineKeyboardMarkup(rows)


def build_notes_inline_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📝 Nuova nota", callback_data="hint_new_note"),
                InlineKeyboardButton("📚 Ultime note", callback_data="show_notes"),
            ],
            [
                InlineKeyboardButton("🔎 Cerca note", callback_data="hint_search_notes"),
                InlineKeyboardButton("🧭 Note Center", callback_data="open_notes_center"),
            ],
            [InlineKeyboardButton("📋 Planner", callback_data="show_planner")],
        ]
    )


def build_memory_inline_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🧩 Mostra memoria", callback_data="show_memory"),
                InlineKeyboardButton("➕ Aggiungi memoria", callback_data="hint_add_memory"),
            ],
            [
                InlineKeyboardButton("🔎 Cerca memoria", callback_data="hint_search_memory"),
                InlineKeyboardButton("🧭 Memoria Center", callback_data="open_memory_center"),
            ],
            [InlineKeyboardButton("📋 Planner", callback_data="show_planner")],
        ]
    )


def build_inbox_inline_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📥 Mostra inbox", callback_data="show_inbox"),
                InlineKeyboardButton("➕ Nuovo inbox", callback_data="quick_add_inbox"),
            ],
            [InlineKeyboardButton("🧭 Inbox Center", callback_data="open_inbox_center")],
            [InlineKeyboardButton("📋 Planner", callback_data="show_planner")],
        ]
    )


def build_inbox_convert_keyboard(item_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📅 Evento", callback_data=f"inbox_to_event_{item_id}"),
                InlineKeyboardButton("✅ Task", callback_data=f"inbox_to_task_{item_id}"),
            ],
            [
                InlineKeyboardButton("📝 Nota", callback_data=f"inbox_to_note_{item_id}"),
                InlineKeyboardButton("🧩 Memoria", callback_data=f"inbox_to_memory_{item_id}"),
            ],
            [InlineKeyboardButton("🗑 Elimina", callback_data=f"inbox_delete_{item_id}")],
        ]
    )


def build_planner_inline_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Task", callback_data="show_tasks"),
                InlineKeyboardButton("📅 Oggi", callback_data="show_today"),
            ],
            [
                InlineKeyboardButton("📆 Domani", callback_data="show_tomorrow"),
                InlineKeyboardButton("🔥 Irrisolti", callback_data="show_unresolved_tasks"),
            ],
            [
                InlineKeyboardButton("📥 Inbox", callback_data="show_inbox"),
                InlineKeyboardButton("⚡ Quick Add", callback_data="open_quick_add"),
            ],
            [InlineKeyboardButton("📅 Settimana", callback_data="show_week_summary")],
        ]
    )


def build_task_center_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📋 Vedi task", callback_data="show_tasks")],
            [
                InlineKeyboardButton("✅ Completa", callback_data="task_center_complete"),
                InlineKeyboardButton("✏️ Sposta", callback_data="task_center_move"),
            ],
            [
                InlineKeyboardButton("⏰ Snooze", callback_data="task_center_snooze"),
                InlineKeyboardButton("❌ Cancella", callback_data="task_center_delete"),
            ],
            [
                InlineKeyboardButton("🔥 Prioritari", callback_data="task_center_high"),
                InlineKeyboardButton("📂 Per categoria", callback_data="task_center_category"),
            ],
            [InlineKeyboardButton("⬅️ Planner", callback_data="show_planner")],
        ]
    )


def build_calendar_center_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📅 Oggi", callback_data="show_today"),
                InlineKeyboardButton("📆 Domani", callback_data="show_tomorrow"),
            ],
            [InlineKeyboardButton("📅 Settimana", callback_data="show_week_summary")],
            [
                InlineKeyboardButton("➕ Evento", callback_data="quick_add_event"),
                InlineKeyboardButton("❌ Cancella", callback_data="hint_delete_event"),
            ],
            [
                InlineKeyboardButton("✏️ Sposta", callback_data="hint_move_event"),
                InlineKeyboardButton("🕒 Cambia ora", callback_data="hint_move_event"),
            ],
            [InlineKeyboardButton("📍 Slot liberi", callback_data="calendar_free_slots_today")],
            [InlineKeyboardButton("⬅️ Planner", callback_data="show_planner")],
        ]
    )


def build_notes_center_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📚 Ultime note", callback_data="show_notes"),
                InlineKeyboardButton("🔎 Cerca", callback_data="hint_search_notes"),
            ],
            [
                InlineKeyboardButton("➕ Nuova", callback_data="hint_new_note"),
                InlineKeyboardButton("✅→Task", callback_data="hint_note_to_task"),
            ],
            [
                InlineKeyboardButton("📅→Evento", callback_data="hint_note_to_event"),
                InlineKeyboardButton("❌ Elimina", callback_data="hint_delete_note"),
            ],
            [InlineKeyboardButton("⬅️ Planner", callback_data="show_planner")],
        ]
    )


def build_inbox_center_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📥 Mostra inbox", callback_data="show_inbox")],
            [
                InlineKeyboardButton("✅→Task", callback_data="hint_inbox_to_task"),
                InlineKeyboardButton("📅→Evento", callback_data="hint_inbox_to_event"),
            ],
            [
                InlineKeyboardButton("📝→Nota", callback_data="hint_inbox_to_note"),
                InlineKeyboardButton("🧩→Memoria", callback_data="hint_inbox_to_memory"),
            ],
            [InlineKeyboardButton("❌ Elimina", callback_data="hint_inbox_delete")],
            [InlineKeyboardButton("⬅️ Planner", callback_data="show_planner")],
        ]
    )


def build_memory_center_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🧩 Mostra", callback_data="show_memory"),
                InlineKeyboardButton("➕ Aggiungi", callback_data="hint_add_memory"),
            ],
            [InlineKeyboardButton("🔎 Cerca", callback_data="hint_search_memory")],
            [InlineKeyboardButton("⬅️ Planner", callback_data="show_planner")],
        ]
    )


def build_planner_center_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📋 Oggi", callback_data="show_planner"),
                InlineKeyboardButton("📆 Domani", callback_data="show_tomorrow"),
            ],
            [
                InlineKeyboardButton("📅 Settimana", callback_data="show_week_summary"),
                InlineKeyboardButton("🔥 Priorità", callback_data="task_center_high"),
            ],
            [
                InlineKeyboardButton("✅ Urgenti", callback_data="show_unresolved_tasks"),
                InlineKeyboardButton("📥 Inbox", callback_data="show_inbox"),
            ],
            [InlineKeyboardButton("📅 Eventi", callback_data="open_calendar_center")],
        ]
    )


def build_event_reminder_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Ok", callback_data="event_reminder_ack"),
                InlineKeyboardButton("⏰ Rimanda", callback_data="event_reminder_snooze"),
            ],
            [
                InlineKeyboardButton("📅 Apri giorno", callback_data="show_today"),
                InlineKeyboardButton("❌ Cancella evento", callback_data="hint_delete_event"),
            ],
        ]
    )


# Backward-compatible aliases

def build_help_main_inline_keyboard() -> InlineKeyboardMarkup:
    return build_help_inline_keyboard()


def build_events_inline_keyboard(current_view: str = "today") -> InlineKeyboardMarkup:
    return build_event_actions_keyboard(list_size=0, current_view=current_view)


def build_tasks_inline_keyboard() -> InlineKeyboardMarkup:
    return build_task_actions_keyboard(list_size=0)


def build_unresolved_inline_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Completa task", callback_data="hint_complete_task"),
                InlineKeyboardButton("✅ Task", callback_data="show_tasks"),
            ],
            [InlineKeyboardButton("📋 Planner", callback_data="show_planner")],
        ]
    )
