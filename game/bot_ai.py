"""
game/bot_ai.py
Bot AI decision engine for the Mafia game.
Each bot has a personality that determines how it votes, acts at night,
and what flavour messages it posts during day discussions.
"""
import random
from collections import Counter
from game.models import GameState, BotPlayer, BotPersonality, Role

# ── Bot name pools by personality ──────────────────────────────────────────────
BOT_NAMES: dict[BotPersonality, list[str]] = {
    BotPersonality.AGGRESSIVE: ["Ravager", "Brutus", "Havoc", "Carnage", "Slayer", "Viper"],
    BotPersonality.PARANOID:   ["Cipher", "Shade", "Wraith", "Spectre", "Vex", "Gloom"],
    BotPersonality.PASSIVE:    ["Mellow", "Bloom", "Pebble", "Wisp", "Cloud", "Breeze"],
    BotPersonality.DETECTIVE:  ["Sherlock", "Marlowe", "Clue", "Watson", "Magnifier", "Lumen"],
}

# Emoji per personality for use in cog
PERSONALITY_EMOJI: dict[BotPersonality, str] = {
    BotPersonality.AGGRESSIVE: "🔥",
    BotPersonality.PARANOID:   "👁️",
    BotPersonality.PASSIVE:    "🌿",
    BotPersonality.DETECTIVE:  "🔍",
}

# ── Day discussion templates ────────────────────────────────────────────────────
_DAY_MESSAGES: dict[BotPersonality, list[str]] = {
    BotPersonality.AGGRESSIVE: [
        "We need to act **fast**. Stop stalling and vote already!",
        "I have a gut feeling. We can't let another night go by without a lynching.",
        "Someone here is the Mafia. I can feel it. **Let's go.**",
        "No more waiting. We eliminate someone NOW.",
        "Time is on the Mafia's side if we hesitate. MOVE.",
    ],
    BotPersonality.PARANOID: [
        "I trust **no one** here. Every single one of you is a suspect.",
        "Did anyone else notice how quiet {target} has been...? 👀",
        "Something is *very* off. I can sense the Mafia among us.",
        "Why would an innocent person stay so silent? That's suspicious.",
        "I watched how {target} voted last round. Very telling.",
    ],
    BotPersonality.PASSIVE: [
        "Let's just... hear everyone out before we decide anything.",
        "I don't know, everyone seems okay to me honestly...",
        "Maybe we shouldn't rush? Mistakes get innocents killed.",
        "I'll follow whatever the town decides.",
        "No strong opinions from me. Let's be careful.",
    ],
    BotPersonality.DETECTIVE: [
        "Based on the voting patterns so far, I have a strong suspicion.",
        "Cross-referencing all available information... my analysis points to {target}.",
        "The logical choice here is clear if you look at the evidence carefully.",
        "Statistics don't lie. We should be focusing on {target}.",
        "Think about it: who benefits most from yesterday's outcome? That's your answer.",
    ],
}

# ── Bot vote flavour messages ───────────────────────────────────────────────────
VOTE_MESSAGES: dict[BotPersonality, str] = {
    BotPersonality.AGGRESSIVE: '**{bot}** slams their fist. 🗳️ *"**{target}** is sus! I vote them OUT!"*',
    BotPersonality.PARANOID:   '**{bot}** narrows their eyes. 🗳️ *"I\'ve been watching **{target}**... They\'re hiding something."*',
    BotPersonality.PASSIVE:    '**{bot}** sighs quietly. 🗳️ *"...I\'ll go with **{target}**, I suppose."*',
    BotPersonality.DETECTIVE:  '**{bot}** checks their notes. 🗳️ *"The evidence points squarely to **{target}**. Vote cast."*',
}

# ── Night action flavour messages ───────────────────────────────────────────────
NIGHT_MESSAGES: dict[Role, str] = {
    Role.MAFIA:   "🔪 *{bot} vanishes silently into the shadows...*",
    Role.DOCTOR:  "💊 *{bot} quietly prepares their medicine bag...*",
    Role.COP:     "🔍 *{bot} slips into the night to conduct an investigation...*",
}

# ── Public API ─────────────────────────────────────────────────────────────────

def decide_night_action(bot: BotPlayer, game: GameState) -> int | None:
    """
    Decide who the bot targets during the night phase.
    Returns the target's user_id, or None if the bot takes no action.
    """
    alive = game.get_alive_players()
    others = [p for p in alive if p.user_id != bot.user_id]

    if not others:
        return None

    if bot.role == Role.MAFIA:
        # Never target fellow Mafia members
        town_targets = [p for p in others if p.role != Role.MAFIA]
        if not town_targets:
            return None

        if bot.personality == BotPersonality.DETECTIVE:
            # Prioritise Cop and Doctor — they're the biggest threat
            priority = [p for p in town_targets if p.role in (Role.COP, Role.DOCTOR)]
            if priority:
                return random.choice(priority).user_id

        if bot.personality == BotPersonality.PASSIVE and random.random() < 0.15:
            return None  # Passive bot very occasionally freezes up

        return random.choice(town_targets).user_id

    elif bot.role == Role.DOCTOR:
        if bot.personality == BotPersonality.PASSIVE:
            return bot.user_id  # Passive doctor always self-protects
        # Occasionally self-protect, otherwise protect a random player
        if random.random() < 0.25:
            return bot.user_id
        return random.choice(alive).user_id

    elif bot.role == Role.COP:
        # Prefer to investigate players not yet investigated
        already_checked = set(game.cop_results.keys())
        uninvestigated = [p for p in others if p.user_id not in already_checked]
        pool = uninvestigated if uninvestigated else others
        return random.choice(pool).user_id

    return None  # Villager has no night action


def decide_vote(bot: BotPlayer, game: GameState) -> int | None:
    """
    Decide who the bot votes to lynch during the day phase.
    Returns the target's user_id, or None for a skipped vote.
    """
    alive = game.get_alive_players()
    others = [p for p in alive if p.user_id != bot.user_id and p.is_alive]

    if not others:
        return None

    # Detective bots use cop investigation results first
    if bot.personality == BotPersonality.DETECTIVE and game.cop_results:
        for target_id, result in game.cop_results.items():
            target = game.players.get(target_id)
            if result == "Mafia" and target and target.is_alive:
                return target_id

    # Mafia bots never vote for fellow Mafia
    if bot.role == Role.MAFIA:
        town_targets = [p for p in others if p.role != Role.MAFIA]
        if town_targets:
            return random.choice(town_targets).user_id

    # Passive bots skip ~40% of the time
    if bot.personality == BotPersonality.PASSIVE and random.random() < 0.4:
        return None

    # Bandwagon logic — follow existing votes
    if game.votes:
        vote_counts = Counter(game.votes.values())
        top_target_id, top_count = vote_counts.most_common(1)[0]
        top_target = game.players.get(top_target_id)

        # Aggressive: always joins the bandwagon if someone has any votes
        if bot.personality == BotPersonality.AGGRESSIVE and top_count >= 1:
            if top_target and top_target.is_alive and top_target_id != bot.user_id:
                return top_target_id

        # Paranoid: 30% chance to pick the LEAST voted (contrarian)
        if bot.personality == BotPersonality.PARANOID and random.random() < 0.3:
            bottom_target_id = vote_counts.most_common()[-1][0]
            bottom_target = game.players.get(bottom_target_id)
            if bottom_target and bottom_target.is_alive and bottom_target_id != bot.user_id:
                return bottom_target_id

    # Default: random vote from valid targets
    valid = [p for p in others if p.is_alive]
    return random.choice(valid).user_id if valid else None


def get_discussion_message(bot: BotPlayer, game: GameState) -> str:
    """
    Generate a flavour in-channel discussion message for the bot to post
    at the start of the day phase.
    """
    templates = _DAY_MESSAGES.get(bot.personality, ["..."])
    message = random.choice(templates)

    # Fill {target} placeholder with a random alive player
    if "{target}" in message:
        alive = game.get_alive_players()
        suspects = [p for p in alive if p.user_id != bot.user_id]
        if suspects:
            target = random.choice(suspects)
            message = message.replace("{target}", f"**{target.name}**")
        else:
            message = message.replace("{target}", "**someone**")

    return message


def get_bot_night_message(bot: BotPlayer) -> str | None:
    """Return a mysterious night flavour message for this bot's role, or None for villager."""
    template = NIGHT_MESSAGES.get(bot.role)
    if template:
        return template.format(bot=bot.name)
    return None
