"""
КАЗИНО: Блэкджек + Техасский Холдем + Обучение ИИ
==================================================

Один файл. Запуск: python casino.py
Требуется: pyglet >= 2.0 (проверено на 2.1.14)

Режимы:
  1. Блэкджек (игрок vs дилер)
  2. Холдем: игрок vs бот (правиловый, pot odds)
  3. Холдем: игрок vs обучаемый ИИ (Q-learning с save/load)
  4. Обучение: бот vs ИИ (автопрогон + периодическое сохранение)

Что исправлено в этой версии:
  • Полноценные рейзы (check/bet/call/raise/fold) у игрока и AI
  • BotAI использует pot odds — не фолдит на второй/третий бет
  • LearningAI сохраняется в casino_ai.json и загружается при старте
  • Фикс Pyglet 2.x: держатель ссылок, иначе чёрный экран
  • Расширенные интервалы между текстом/картами/кнопками
"""

import json
import os
import random

import pyglet
from pyglet import shapes
from pyglet import text
from itertools import combinations
from collections import Counter

# ═══════════════════════════════════════════════════════════════════════════
#  КРИТИЧЕСКИЙ ФИКС Pyglet 2.x — держатель ссылок
#  В Pyglet 2.x shapes.* и text.Label удаляются из batch сборщиком мусора,
#  если нет живой Python-ссылки. Симптом: окно открывается, но всё чёрное.
#  Оборачиваем конструкторы: каждый объект с batch=... регистрируется в
#  batch._refs. Когда batch пересоздаётся — старый _refs уходит вместе с ним.
# ═══════════════════════════════════════════════════════════════════════════
def _keep_wrap(ctor):
    def wrapper(*args, batch=None, **kwargs):
        obj = ctor(*args, batch=batch, **kwargs)
        if batch is not None:
            refs = getattr(batch, '_refs', None)
            if refs is None:
                batch._refs = refs = []
            refs.append(obj)
        return obj
    return wrapper

for _n in ('Rectangle', 'RoundedRectangle', 'Circle', 'Ellipse',
           'Triangle', 'Line', 'Arc', 'Sector'):
    if hasattr(shapes, _n):
        setattr(shapes, _n, _keep_wrap(getattr(shapes, _n)))
text.Label = _keep_wrap(text.Label)


# ═══════════════════════════════════════════════════════════════════════════
#  КОНСТАНТЫ
# ═══════════════════════════════════════════════════════════════════════════
WIDTH, HEIGHT = 1280, 800
CARD_W, CARD_H = 80, 110

WHITE          = (255, 255, 255, 255)
BLACK          = (0,   0,   0,   255)
RED            = (200, 30,  30,  255)
DARK_GREEN     = (10,  80,  40,  255)
GOLD           = (230, 200, 60,  255)
DARK_BLUE      = (30,  50,  130, 255)
BTN            = (50,  80,  130, 255)
BTN_LIGHT      = (70,  110, 170, 255)
BTN_DIS        = (80,  80,  80,  255)
BTN_LIGHT_DIS  = (100, 100, 100, 255)
BTN_GOLD       = (170, 130, 40,  255)
BTN_GOLD_LIGHT = (226, 180, 62,  255)
BTN_RED        = (140, 48,  48,  255)
BTN_RED_LIGHT  = (194, 68,  68,  255)

SUITS    = ['♠', '♥', '♦', '♣']
SUIT_RED = [False, True, True, False]

RANKS = list(range(2, 15))
RANK_NAMES = {2:'2',3:'3',4:'4',5:'5',6:'6',7:'7',8:'8',9:'9',10:'10',
              11:'J',12:'Q',13:'K',14:'A'}
HAND_NAMES = ['Старшая карта', 'Пара', 'Две пары', 'Тройка',
              'Стрит', 'Флеш', 'Фулл-хаус', 'Каре',
              'Стрит-флеш', 'Роял-флеш']

# Файл сохранения Q-таблицы — рядом со скриптом
SAVE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'casino_ai.json')

APP = None


# ═══════════════════════════════════════════════════════════════════════════
#  КАРТЫ
# ═══════════════════════════════════════════════════════════════════════════
class Card:
    __slots__ = ('rank', 'suit')
    def __init__(self, rank, suit):
        self.rank = rank
        self.suit = suit
    def bj_value(self):
        if self.rank == 14: return 11
        if self.rank >= 10: return 10
        return self.rank


class Deck:
    def __init__(self):
        self.reset()
    def reset(self):
        self.cards = [Card(r, s) for s in range(4) for r in RANKS]
        random.shuffle(self.cards)
    def draw(self):
        if not self.cards:
            self.reset()
        return self.cards.pop()


# ═══════════════════════════════════════════════════════════════════════════
#  ОЦЕНКА РУК
# ═══════════════════════════════════════════════════════════════════════════
def evaluate_5(cards):
    ranks = sorted([c.rank for c in cards], reverse=True)
    suits = [c.suit for c in cards]
    is_flush = len(set(suits)) == 1
    unique = sorted(set(ranks), reverse=True)
    is_straight = False
    sh = 0
    if len(unique) == 5:
        if unique[0] - unique[4] == 4:
            is_straight = True
            sh = unique[0]
        elif unique == [14, 5, 4, 3, 2]:
            is_straight = True
            sh = 5
    counts = Counter(ranks)
    sc = sorted(counts.items(), key=lambda x: (x[1], x[0]), reverse=True)
    if is_straight and is_flush:
        return (9, (14,)) if sh == 14 else (8, (sh,))
    if sc[0][1] == 4:
        return (7, (sc[0][0], sc[1][0]))
    if sc[0][1] == 3 and sc[1][1] == 2:
        return (6, (sc[0][0], sc[1][0]))
    if is_flush:
        return (5, tuple(ranks))
    if is_straight:
        return (4, (sh,))
    if sc[0][1] == 3:
        kk = sorted([r for r, c in sc[1:]], reverse=True)
        return (3, (sc[0][0],) + tuple(kk))
    if sc[0][1] == 2 and sc[1][1] == 2:
        p1, p2 = sc[0][0], sc[1][0]
        return (2, (max(p1, p2), min(p1, p2), sc[2][0]))
    if sc[0][1] == 2:
        kk = sorted([r for r, c in sc[1:]], reverse=True)
        return (1, (sc[0][0],) + tuple(kk))
    return (0, tuple(ranks))


def evaluate_7(cards):
    if len(cards) < 5:
        return (0, tuple(sorted([c.rank for c in cards], reverse=True)))
    best = None
    for combo in combinations(cards, 5):
        v = evaluate_5(list(combo))
        if best is None or v > best:
            best = v
    return best


# ═══════════════════════════════════════════════════════════════════════════
#  РИСОВАНИЕ
# ═══════════════════════════════════════════════════════════════════════════
def draw_card(batch, x, y, card):
    shapes.Rectangle(x, y, CARD_W, CARD_H, color=BLACK, batch=batch)
    shapes.Rectangle(x+2, y+2, CARD_W-4, CARD_H-4, color=WHITE, batch=batch)
    color = RED if SUIT_RED[card.suit] else BLACK
    text.Label(RANK_NAMES[card.rank], x=x+8, y=y+CARD_H-32,
               font_size=22, color=color, batch=batch, )
    text.Label(SUITS[card.suit], x=x+8, y=y+CARD_H-60,
               font_size=24, color=color, batch=batch)
    text.Label(SUITS[card.suit], x=x+CARD_W-30, y=y+12,
               font_size=20, color=color, batch=batch)


def draw_card_back(batch, x, y):
    shapes.Rectangle(x, y, CARD_W, CARD_H, color=BLACK, batch=batch)
    shapes.Rectangle(x+2, y+2, CARD_W-4, CARD_H-4, color=DARK_BLUE, batch=batch)
    shapes.Rectangle(x+12, y+12, CARD_W-24, CARD_H-24,
                     color=(60, 100, 180, 255), batch=batch)
    shapes.Rectangle(x+22, y+22, CARD_W-44, CARD_H-44,
                     color=DARK_BLUE, batch=batch)


def draw_hand(batch, hand, x, y, hide=None):
    if hide is None:
        hide = set()
    for i, c in enumerate(hand):
        cx = x + i * (CARD_W + 10)
        if i in hide:
            draw_card_back(batch, cx, y)
        else:
            draw_card(batch, cx, y, c)


def add_button(batch, buttons, x, y, w, h, txt, cb, enabled=True,
               style='blue', fs=18):
    """style: 'blue' | 'green' | 'red' | 'gold'"""
    if enabled:
        if style == 'green':
            bg, inner = (36, 118, 70, 255), (52, 160, 96, 255)
        elif style == 'red':
            bg, inner = BTN_RED, BTN_RED_LIGHT
        elif style == 'gold':
            bg, inner = BTN_GOLD, BTN_GOLD_LIGHT
        else:
            bg, inner = BTN, BTN_LIGHT
    else:
        bg, inner = BTN_DIS, BTN_LIGHT_DIS
    shapes.Rectangle(x, y, w, h, color=bg, batch=batch)
    shapes.Rectangle(x+3, y+3, w-6, h-6, color=inner, batch=batch)
    text.Label(txt, x=x+w//2, y=y+h//2, anchor_x='center',
               anchor_y='center', font_size=fs, color=WHITE, batch=batch,
               )
    buttons.append((x, y, w, h, cb, enabled))


# ═══════════════════════════════════════════════════════════════════════════
#  ИИ-ОППОНЕНТЫ
# ═══════════════════════════════════════════════════════════════════════════
class BotAI:
    """
    Правиловый бот на pot odds.

    Ключевое отличие от прошлой версии: колл проверяется по equity vs pot
    odds, а НЕ по фиксированному порогу. Чем больше банк — тем меньше нужно
    equity для колла. Это исправляет «бот сбрасывает после второго бета»:
    при pot odds 25% бот колит руки с equity > 30%, а не ждёт s > 0.35.
    """
    name = "Бот"

    def _strength(self, cards, community):
        if len(cards) < 2:
            return 0.5
        if len(cards + community) >= 5:
            return evaluate_7(cards + community)[0] / 9.0
        r1, r2 = cards[0].rank, cards[1].rank
        if r1 == r2:
            return 0.75 if r1 >= 10 else 0.55
        return (max(r1, r2) - 2) / 12 * 0.6

    def choose(self, cards, community, to_call, chips, bet_size,
               pot=0, can_raise=False, raise_to=0):
        s = self._strength(cards, community)

        if to_call > 0:
            # Pot odds = сколько нужно доплатить / (банк + доплата)
            pot_odds = to_call / (pot + to_call) if (pot + to_call) > 0 else 0.5

            # Против агрессии ослабляем руку на 5%
            adj = s - 0.05

            # Рейз при очень сильной руке (value raise)
            if can_raise and adj > 0.72 and chips >= to_call * 2 and random.random() < 0.7:
                return 'raise'

            # Колл если equity покрывает pot odds + запас
            if adj > pot_odds + 0.04:
                return 'call'

            # Блеф-кэтч: маргинальные руки иногда коллят (непредсказуемость)
            if adj > pot_odds - 0.02 and random.random() < 0.20:
                return 'call'

            return 'fold'

        # Нет ставки к коллу — можно чек или бет
        if can_raise and s > 0.62 and random.random() < 0.75:
            return 'bet'
        return 'check'

    def learn(self, chip_delta):
        pass


class LearningAI:
    """
    Q-learning агент. Сохраняет Q-таблицу в JSON.

    СОСТОЯНИЕ (6): (strength_bin, facing_bet)
      strength_bin ∈ {0,1,2}  — слабая / средняя / сильная
      facing_bet   ∈ {0,1}    — есть ли ставка к коллу

    ДЕЙСТВИЯ (3):
      0 = fold  (сброс)
      1 = call/check (пассив)
      2 = raise/bet  (агрессия)

    Приоритет действий задан через _prior() — стартовые Q-значения уже
    осмысленные, чтобы AI играл разумно с первой партии.

    Reward: clip(chip_delta / 40, -1, 1). Фолд при сильной руке = −1 (AI
    быстро учится не фолдить сильное). Колл при слабой руке = −0.5.
    """
    name = "Обучаемый ИИ"

    ACTION_NAMES = ['Фолд', 'Колл/Чек', 'Рейз/Бет']

    def __init__(self):
        self.Q = {}
        self.N = {}
        for sb in range(3):
            for tc in range(2):
                self.Q[(sb, tc)] = list(self._prior(sb, tc))
                self.N[(sb, tc)] = [0, 0, 0]
        self.alpha    = 0.10
        self.epsilon  = 0.15
        self.games    = 0
        self.wins     = 0
        self.losses   = 0
        self.ties     = 0
        self.last_state  = None
        self.last_action = None

    def _prior(self, sb, tc):
        """Стартовые Q-значения [fold, call, raise] для состояния (sb, tc)."""
        if sb == 0:                      # слабая рука
            if tc: return (-0.3, -0.5, -0.8)   # фолд лучше всего
            return (-0.3, 0.0, -0.5)           # чек ок
        if sb == 1:                      # средняя
            if tc: return (-0.3, 0.1, -0.1)    # колл
            return (-0.3, 0.1, 0.0)
        # сильная
        if tc: return (-0.5, 0.0, 0.3)         # рейз
        return (-0.5, 0.0, 0.2)                # бет

    def _bin(self, s):
        if s < 0.3: return 0
        if s < 0.6: return 1
        return 2

    def _strength(self, cards, community):
        if len(cards) < 2:
            return 0.5
        if len(cards + community) >= 5:
            return evaluate_7(cards + community)[0] / 9.0
        r1, r2 = cards[0].rank, cards[1].rank
        if r1 == r2:
            return 0.75 if r1 >= 10 else 0.55
        return (max(r1, r2) - 2) / 12 * 0.6

    def choose(self, cards, community, to_call, chips, bet_size,
               pot=0, can_raise=False, raise_to=0):
        s = self._strength(cards, community)
        state = (self._bin(s), 1 if to_call > 0 else 0)
        self.last_state = state

        if random.random() < self.epsilon:
            action = random.randint(0, 2)
        else:
            q = self.Q[state]
            action = q.index(max(q))

        # Разрешаем действие в конкретный ход с проверкой легальности.
        # last_action ВСЕГДА соответствует фактическому ходу (не намерению).
        if action == 0:  # fold
            if to_call > 0 and chips > 0:
                self.last_action = 0
                return 'fold'
            self.last_action = 1
            return 'check'

        if action == 1:  # call/check
            self.last_action = 1
            if to_call > 0:
                return 'call'
            return 'check'

        # action == 2: raise/bet
        if can_raise:
            self.last_action = 2
            if to_call > 0:
                return 'raise'
            return 'bet'

        # Не можем рейзить — фолбэк на колл/чек
        self.last_action = 1
        if to_call > 0:
            return 'call' if chips >= to_call else 'fold'
        return 'check'

    def learn(self, chip_delta):
        if self.last_state is None:
            return
        self.games += 1
        reward = max(-1.0, min(1.0, chip_delta / 40.0))
        s = self.last_state
        a = self.last_action
        n = self.N[s][a]
        alpha = max(0.03, self.alpha / (1 + n * 0.05))  # затухающий alpha
        self.Q[s][a] += alpha * (reward - self.Q[s][a])
        self.N[s][a] += 1

        if chip_delta > 0:
            self.wins += 1
        elif chip_delta < 0:
            self.losses += 1
        else:
            self.ties += 1

        self.last_state = None
        self.last_action = None

    def winrate(self):
        return (self.wins / self.games * 100) if self.games else 0.0

    def aggression(self):
        total = 0.0
        for sb in range(3):
            for tc in range(2):
                q = self.Q[(sb, tc)]
                total += q[2] - q[0]   # агрессия: рейз минус фолд
        return total / 6.0

    # ── Сохранение / загрузка ─────────────────────────────────────────
    def save(self, path=SAVE_PATH):
        try:
            data = {
                'games':  self.games,
                'wins':   self.wins,
                'losses': self.losses,
                'ties':   self.ties,
                'Q': {f"{s[0]},{s[1]}": list(v) for s, v in self.Q.items()},
                'N': {f"{s[0]},{s[1]}": list(v) for s, v in self.N.items()},
            }
            tmp = path + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=1)
            os.replace(tmp, path)
            return True
        except Exception as e:
            print(f"AI save error: {e}")
            return False

    def load(self, path=SAVE_PATH):
        if not os.path.exists(path):
            return False
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.games  = data.get('games', 0)
            self.wins   = data.get('wins', 0)
            self.losses = data.get('losses', 0)
            self.ties   = data.get('ties', 0)
            for k_str, q_list in data.get('Q', {}).items():
                parts = k_str.split(',')
                key = (int(parts[0]), int(parts[1]))
                q_list = list(q_list)
                # Миграция 2-действия → 3-действия (старый формат)
                if len(q_list) == 2:
                    q_list = [q_list[0] * 0.5, q_list[0], q_list[1]]
                self.Q[key] = q_list
            for k_str, n_list in data.get('N', {}).items():
                parts = k_str.split(',')
                key = (int(parts[0]), int(parts[1]))
                n_list = list(n_list)
                if len(n_list) == 2:
                    n_list = [0, n_list[0], n_list[1]]
                self.N[key] = n_list
            return True
        except Exception as e:
            print(f"AI load error: {e}")
            return False


# ═══════════════════════════════════════════════════════════════════════════
#  БЛЭКДЖЕК
# ═══════════════════════════════════════════════════════════════════════════
class Blackjack:
    BET   = 25
    START = 500

    def __init__(self):
        self.chips        = self.START
        self.deck         = Deck()
        self.player       = []
        self.dealer       = []
        self.state        = 'ready'
        self.message      = ""
        self.show_dealer  = False
        self.bet          = self.BET
        self.buttons      = []
        self.batch        = None
        self.rebuild()

    def hand_total(self, hand):
        total = sum(c.bj_value() for c in hand)
        aces = sum(1 for c in hand if c.rank == 14)
        while total > 21 and aces > 0:
            total -= 10
            aces -= 1
        return total

    def rebuild(self):
        self.batch   = pyglet.graphics.Batch()
        self.buttons = []
        b = self.batch

        shapes.Rectangle(0, 0, WIDTH, HEIGHT, color=DARK_GREEN, batch=b)

        # ── Верхняя панель ────────────────────────────────────────────
        text.Label(f"Фишки: ${self.chips}", x=30, y=HEIGHT-42,
                   font_size=22, batch=b, )
        text.Label(f"Ставка: ${self.bet}", x=30, y=HEIGHT-74,
                   font_size=16, batch=b)

        # ── Дилер ─────────────────────────────────────────────────────
        text.Label("ДИЛЕР", x=200, y=HEIGHT-130, font_size=20, batch=b, )
        hide = set()
        if not self.show_dealer and len(self.dealer) >= 2:
            hide = {1}
        draw_hand(b, self.dealer, 200, HEIGHT-265, hide)
        if self.dealer:
            if self.show_dealer:
                label = f"Сумма: {self.hand_total(self.dealer)}"
            else:
                label = f"Открыто: {self.dealer[0].bj_value()}"
            text.Label(label, x=200, y=HEIGHT-290, font_size=16, batch=b)

        # ── Игрок (объединённая подпись) ──────────────────────────────
        if self.player:
            t = self.hand_total(self.player)
            text.Label(f"ВЫ · {t}", x=200, y=238, font_size=18, batch=b, )
        else:
            text.Label("ВЫ", x=200, y=238, font_size=20, batch=b, )
        draw_hand(b, self.player, 200, 115)

        # ── Сообщение ─────────────────────────────────────────────────
        if self.message:
            text.Label(self.message, x=WIDTH//2, y=HEIGHT//2 + 10,
                       anchor_x='center', anchor_y='center',
                       font_size=28, batch=b, color=GOLD)

        # ── Кнопки в горизонтальный ряд ───────────────────────────────
        if self.state == 'ready':
            add_button(b, self.buttons, WIDTH//2 - 130, 30, 260, 55,
                       f"РАЗДАТЬ (${self.bet})", self.deal,
                       self.chips >= self.bet, style='green')
        elif self.state == 'playing':
            add_button(b, self.buttons, WIDTH//2 - 330, 30, 200, 55,
                       "ВЗЯТЬ", self.hit)
            add_button(b, self.buttons, WIDTH//2 - 110, 30, 200, 55,
                       "ПАС", self.stand)
            add_button(b, self.buttons, WIDTH//2 + 110, 30, 200, 55,
                       "УДВОИТЬ", self.double,
                       len(self.player) == 2 and self.chips >= self.bet,
                       style='gold')
        elif self.state == 'over':
            add_button(b, self.buttons, WIDTH//2 - 130, 30, 260, 55,
                       "НОВАЯ РАЗДАЧА", self.new_round, style='green')

        add_button(b, self.buttons, 20, 20, 110, 45, "МЕНЮ", back_to_menu)

    def deal(self):
        if self.chips < self.bet:
            return
        self.chips -= self.bet
        self.deck = Deck()
        self.player = [self.deck.draw(), self.deck.draw()]
        self.dealer = [self.deck.draw(), self.deck.draw()]
        self.show_dealer = False
        self.state = 'playing'
        self.message = ""
        if self.hand_total(self.player) == 21:
            self._player_bj()
            return
        self.rebuild()

    def _player_bj(self):
        self.show_dealer = True
        if self.hand_total(self.dealer) == 21:
            self.chips += self.bet
            self.end_round("У обоих блэкджек — ничья.")
        else:
            w = (self.bet * 3) // 2
            self.chips += self.bet + w
            self.end_round(f"БЛЭКДЖЕК! Выиграли ${w}!")

    def hit(self):
        self.player.append(self.deck.draw())
        if self.hand_total(self.player) > 21:
            self.end_round(f"ПЕРЕБОР! Теряете ${self.bet}.")
        else:
            self.rebuild()

    def stand(self):
        self.show_dealer = True
        while self.hand_total(self.dealer) < 17:
            self.dealer.append(self.deck.draw())
        self._resolve()

    def double(self):
        if self.chips < self.bet:
            return
        self.chips -= self.bet
        self.bet *= 2
        self.player.append(self.deck.draw())
        if self.hand_total(self.player) > 21:
            self.end_round(f"ПЕРЕБОР! Теряете ${self.bet}.")
        else:
            self.stand()

    def _resolve(self):
        pt = self.hand_total(self.player)
        dt = self.hand_total(self.dealer)
        if pt > 21:
            self.end_round(f"ПЕРЕБОР! Теряете ${self.bet}.")
        elif dt > 21:
            self.chips += self.bet * 2
            self.end_round(f"У дилера перебор! Выиграли ${self.bet}.")
        elif pt > dt:
            self.chips += self.bet * 2
            self.end_round(f"Вы выиграли ${self.bet}!")
        elif pt == dt:
            self.chips += self.bet
            self.end_round("Ничья — ставка возвращена.")
        else:
            self.end_round(f"Вы проиграли ${self.bet}.")

    def end_round(self, msg):
        self.state = 'over'
        self.show_dealer = True
        self.message = msg
        self.bet = self.BET
        self.rebuild()

    def new_round(self):
        if self.chips < self.BET:
            self.chips = self.START
        self.state = 'ready'
        self.player, self.dealer = [], []
        self.message = ""
        self.show_dealer = False
        self.bet = self.BET
        self.rebuild()


# ═══════════════════════════════════════════════════════════════════════════
#  ТЕХАССКИЙ ХОЛДЕМ — с полными рейзами
# ═══════════════════════════════════════════════════════════════════════════
class Poker:
    """
    Heads-up Холдем с полноценным betting round.

    Правила:
      • Анте $10, старт $500 у каждого.
      • Блайнды не используются — только анте (упрощение).
      • На каждой улице: игрок и AI могут check/bet/call/raise/fold.
      • Рейз-война продолжается пока кто-то не сколлирует или не сфолдит.
      • При достижении ривера — автоматический showdown.

    Betting round на улице:
      • Начинает игрок. Если check → AI (check/bet). Если bet/raise → AI отвечает.
      • После рейза AI: игрок снова действует (fold/call/raise).
      • После колла: улица закончена.
      • После двух чеков: улица закончена.

    Рейз-сайзинг:
      • МИН — current_bet + min_raise (min_raise = BB или последний рейз).
      • ½ БАНКА — current_bet + 0.5 × (пот + to_call).
      • БАНК — current_bet + (пот + to_call).
      • ВСЁ — все фишки (all-in).
    """
    ANTE  = 10
    BET   = 20
    START = 500

    def __init__(self, opponent):
        self.opponent = opponent
        self.deck = Deck()
        self.player = []
        self.ai = []
        self.community = []
        self.pot = 0
        self.player_chips = self.START
        self.ai_chips = self.START
        self.player_hand_start = self.START
        self.ai_hand_start = self.START

        # Betting state
        self.street = 0
        self.state = 'ready'
        self.message = ""
        self.show_ai = False
        self.player_street_bet = 0
        self.ai_street_bet = 0
        self.current_bet = 0
        self.min_raise = self.BET
        self.checks = 0
        self.to_act = 0

        self.buttons = []
        self.batch = None
        self.rebuild()

    def _is_learning(self):
        return isinstance(self.opponent, LearningAI)

    # ── Рендер ───────────────────────────────────────────────────────
    def rebuild(self):
        self.batch = pyglet.graphics.Batch()
        self.buttons = []
        b = self.batch
        shapes.Rectangle(0, 0, WIDTH, HEIGHT, color=DARK_GREEN, batch=b)

        # Верхняя панель
        text.Label(f"Вы: ${self.player_chips}", x=30, y=HEIGHT-42,
                   font_size=18, batch=b, )
        text.Label(f"{self.opponent.name}: ${self.ai_chips}",
                   x=WIDTH-280, y=HEIGHT-42, font_size=18, batch=b, )
        text.Label(f"Банк: ${self.pot}", x=WIDTH//2, y=HEIGHT-42,
                   anchor_x='center', font_size=22, batch=b, color=GOLD)

        sn = ['ПРЕФЛОП', 'ФЛОП', 'ТЁРН', 'РИВЕР']
        if self.state == 'playing':
            text.Label(sn[self.street], x=WIDTH//2, y=HEIGHT-74,
                       anchor_x='center', font_size=15, batch=b)

        # Оппонент: имя + комбинация
        text.Label(self.opponent.name, x=200, y=HEIGHT-130,
                   font_size=18, batch=b, )
        if self.show_ai and len(self.ai) == 2 and len(self.community) >= 3:
            ev = evaluate_7(self.ai + self.community)
            text.Label(HAND_NAMES[ev[0]], x=370, y=HEIGHT-130,
                       font_size=14, batch=b, color=GOLD)
        hide = set() if self.show_ai else {0, 1}
        draw_hand(b, self.ai, 200, HEIGHT-265, hide)
        # Ставка AI на улице
        if self.ai_street_bet > 0:
            text.Label(f"ставка: ${self.ai_street_bet}",
                       x=200, y=HEIGHT-290, font_size=14, batch=b, color=GOLD)

        # Общие карты
        if self.community:
            text.Label("ОБЩИЕ КАРТЫ", x=200, y=HEIGHT//2 + 100,
                       font_size=15, batch=b, )
            draw_hand(b, self.community, 200, HEIGHT//2 - 45)

        # Игрок
        if self.player and len(self.community) >= 3:
            ev = evaluate_7(self.player + self.community)
            text.Label(f"ВЫ · {HAND_NAMES[ev[0]]}", x=200, y=253,
                       font_size=15, batch=b, )
        else:
            text.Label("ВЫ", x=200, y=253, font_size=18, batch=b, )
        draw_hand(b, self.player, 200, 115)
        if self.player_street_bet > 0:
            text.Label(f"ставка: ${self.player_street_bet}",
                       x=200, y=100, font_size=13, batch=b, color=GOLD)

        # Сообщение
        if self.message:
            text.Label(self.message, x=WIDTH//2, y=305,
                       anchor_x='center', font_size=22, batch=b,
                        color=GOLD)

        # Кнопки
        self._draw_buttons(b)

        add_button(b, self.buttons, 20, 20, 110, 45, "МЕНЮ", back_to_menu)

    def _draw_buttons(self, b):
        if self.state == 'ready':
            can = self.player_chips >= self.ANTE and self.ai_chips >= self.ANTE
            add_button(b, self.buttons, WIDTH//2 - 110, 30, 220, 55,
                       f"РАЗДАТЬ (${self.ANTE})", self.new_hand, can,
                       style='green')
            return
        if self.state == 'over':
            add_button(b, self.buttons, WIDTH//2 - 110, 30, 220, 55,
                       "НОВАЯ РАЗДАЧА", self.new_hand, style='green')
            return
        if self.state == 'playing' and self.to_act == 1:
            # Ход AI — кнопки недоступны
            return

        to_call = self.current_bet - self.player_street_bet
        # ── Горизонтальный ряд кнопок ──────────────────────────────────
        # ФОЛД (только если есть ставка к коллу) | ЧЕК/КОЛЛ | рейзы
        btn_w, btn_h, gap, y = 175, 55, 6, 30
        total_w = 6 * btn_w + 5 * gap
        x = (WIDTH - total_w) // 2

        # 1. ФОЛД
        add_button(b, self.buttons, x, y, btn_w, btn_h,
                   "ФОЛД", self.player_fold,
                   to_call > 0, style='red')
        x += btn_w + gap

        # 2. ЧЕК / КОЛЛ
        if to_call > 0:
            call_label = f"КОЛЛ ${to_call}"
            add_button(b, self.buttons, x, y, btn_w, btn_h,
                       call_label, self.player_call,
                       self.player_chips >= to_call, style='blue')
        else:
            add_button(b, self.buttons, x, y, btn_w, btn_h,
                       "ЧЕК", self.player_check, style='blue')
        x += btn_w + gap

        # 3-6. Рейзы (только если можем повысить)
        can_raise = self._can_player_raise()
        max_to = self._player_max_raise()
        min_to = self._player_min_raise()

        # МИН-рейз / БЕТ МИН
        if to_call > 0:
            label = f"МИН →{min_to}"
        else:
            label = f"БЕТ {self.BET}"
        add_button(b, self.buttons, x, y, btn_w, btn_h,
                   label, lambda: self.player_raise('min'),
                   can_raise, style='gold')
        x += btn_w + gap

        # ½ БАНКА
        half = self._player_raise_amount('half')
        add_button(b, self.buttons, x, y, btn_w, btn_h,
                   f"½ →{half}", lambda: self.player_raise('half'),
                   can_raise, style='gold')
        x += btn_w + gap

        # БАНК
        pot_raise = self._player_raise_amount('pot')
        add_button(b, self.buttons, x, y, btn_w, btn_h,
                   f"БАНК →{pot_raise}", lambda: self.player_raise('pot'),
                   can_raise, style='gold')
        x += btn_w + gap

        # ВСЁ (all-in)
        add_button(b, self.buttons, x, y, btn_w, btn_h,
                   f"ВСЁ →{max_to}", lambda: self.player_raise('allin'),
                   can_raise, style='red')

    # ── Вспомогательные расчёты рейзов ───────────────────────────────
    def _player_max_raise(self):
        """Максимальная сумма, до которой игрок может поднять."""
        return min(self.player_street_bet + self.player_chips,
                   self.ai_street_bet + self.ai_chips)

    def _player_min_raise(self):
        """Минимальный легальный рейз."""
        return min(self.current_bet + self.min_raise, self._player_max_raise())

    def _can_player_raise(self):
        return (self.player_chips > (self.current_bet - self.player_street_bet) and
                self._player_max_raise() > self.current_bet)

    def _player_raise_amount(self, kind):
        to_call = self.current_bet - self.player_street_bet
        max_to = self._player_max_raise()
        min_to = self._player_min_raise()
        if kind == 'min':
            return min_to
        if kind == 'allin':
            return max_to
        frac = 0.5 if kind == 'half' else 1.0
        target = self.current_bet + int(frac * (self.pot + to_call))
        return max(min_to, min(max_to, target))

    # ── Новая раздача ────────────────────────────────────────────────
    def new_hand(self):
        if self.player_chips < self.ANTE:
            self.player_chips += self.START
        if self.ai_chips < self.ANTE:
            self.ai_chips += self.START

        self.deck = Deck()
        self.player = [self.deck.draw(), self.deck.draw()]
        self.ai     = [self.deck.draw(), self.deck.draw()]
        self.community = []

        self.player_hand_start = self.player_chips
        self.ai_hand_start     = self.ai_chips

        self.player_chips -= self.ANTE
        self.ai_chips     -= self.ANTE
        self.pot = self.ANTE * 2

        self.street = 0
        self.state = 'playing'
        self.show_ai = False
        self.message = ""

        self.player_street_bet = 0
        self.ai_street_bet = 0
        self.current_bet = 0
        self.min_raise = self.BET
        self.checks = 0
        self.to_act = 0

        self.rebuild()

    # ── Действия игрока ──────────────────────────────────────────────
    def player_fold(self):
        if self.state != 'playing' or self.to_act != 0:
            return
        self.ai_chips += self.pot
        self.pot = 0
        if self._is_learning():
            delta = self.ai_chips - self.ai_hand_start
            self.opponent.learn(delta)
        self.end_hand("Вы сбросили.")

    def player_check(self):
        if self.state != 'playing' or self.to_act != 0:
            return
        if self.current_bet > self.player_street_bet:
            return  # нельзя чекнуть при ставке
        self.checks += 1
        if self.checks >= 2:
            self._next_street()
        else:
            self._switch_to_ai()

    def player_call(self):
        if self.state != 'playing' or self.to_act != 0:
            return
        owed = self.current_bet - self.player_street_bet
        if owed <= 0 or owed > self.player_chips:
            return
        self.player_chips -= owed
        self.pot += owed
        self.player_street_bet = self.current_bet
        self._next_street()

    def player_raise(self, kind):
        if self.state != 'playing' or self.to_act != 0:
            return
        if not self._can_player_raise():
            return
        to_amount = self._player_raise_amount(kind)
        if to_amount <= self.current_bet:
            # По факту это колл
            self.player_call()
            return
        amount_to_put = to_amount - self.player_street_bet
        if amount_to_put > self.player_chips:
            amount_to_put = self.player_chips
            to_amount = self.player_street_bet + amount_to_put

        self.player_chips -= amount_to_put
        self.pot += amount_to_put
        self.player_street_bet = to_amount
        self.min_raise = max(self.min_raise, to_amount - self.current_bet)
        self.current_bet = to_amount
        self.checks = 0
        self._switch_to_ai()

    # ── Ход AI ────────────────────────────────────────────────────────
    def _switch_to_ai(self):
        self.to_act = 1
        self.rebuild()
        self._ai_turn()

    def _ai_turn(self):
        if self.state != 'playing' or self.to_act != 1:
            return
        to_call = self.current_bet - self.ai_street_bet

        # Может ли AI рейзить?
        max_to = min(self.ai_street_bet + self.ai_chips,
                     self.player_street_bet + self.player_chips)
        min_to = self.current_bet + self.min_raise
        can_raise = (self.ai_chips > to_call and max_to > self.current_bet and
                     min_to <= max_to)

        if can_raise:
            # AI рейзит до 2.5 × current_bet (или min_to если больше)
            raise_to = max(min_to, min(max_to, self.current_bet * 2 if self.current_bet else self.BET * 2))
        else:
            raise_to = 0

        action = self.opponent.choose(
            self.ai, self.community, to_call, self.ai_chips,
            self.BET, self.pot, can_raise, raise_to
        )

        # Обработка
        if action == 'fold':
            if to_call > 0:
                self.player_chips += self.pot
                self.pot = 0
                if self._is_learning():
                    delta = self.ai_chips - self.ai_hand_start
                    self.opponent.learn(delta)
                self.end_hand(f"{self.opponent.name} сбросил.")
                return
            # Фолд без ставки → чек
            action = 'check'

        if action == 'check':
            if to_call > 0:
                # Нельзя чекнуть — значит, колл
                action = 'call'
            else:
                self.checks += 1
                if self.checks >= 2:
                    self._next_street()
                else:
                    self.to_act = 0
                    self.rebuild()
                return

        if action == 'call':
            if to_call <= 0:
                # Нечего коллить → чек
                self.checks += 1
                if self.checks >= 2:
                    self._next_street()
                else:
                    self.to_act = 0
                    self.rebuild()
                return
            amount = min(to_call, self.ai_chips)
            self.ai_chips -= amount
            self.pot += amount
            self.ai_street_bet += amount
            self._next_street()
            return

        # bet / raise
        if self.current_bet == 0:
            # Первый бет на улице
            amount = min(self.BET, self.ai_chips)
            self.ai_chips -= amount
            self.pot += amount
            self.ai_street_bet = amount
            self.current_bet = amount
            self.min_raise = self.BET
        else:
            # Рейз
            if not can_raise or raise_to <= self.current_bet:
                # Фолбэк на колл
                amount = min(to_call, self.ai_chips)
                self.ai_chips -= amount
                self.pot += amount
                self.ai_street_bet += amount
                self._next_street()
                return
            amount = raise_to - self.ai_street_bet
            if amount > self.ai_chips:
                amount = self.ai_chips
                raise_to = self.ai_street_bet + amount
            self.ai_chips -= amount
            self.pot += amount
            self.ai_street_bet = raise_to
            self.min_raise = max(self.min_raise, raise_to - self.current_bet)
            self.current_bet = raise_to

        self.checks = 0
        self.to_act = 0
        self.rebuild()

    # ── Переход улицы / showdown ─────────────────────────────────────
    def _next_street(self):
        # Возврат неколлированного (на случай олл-ина за меньшую сумму)
        if self.player_street_bet > self.ai_street_bet:
            excess = self.player_street_bet - self.ai_street_bet
            self.player_chips += excess
            self.pot -= excess
        elif self.ai_street_bet > self.player_street_bet:
            excess = self.ai_street_bet - self.player_street_bet
            self.ai_chips += excess
            self.pot -= excess

        self.player_street_bet = 0
        self.ai_street_bet = 0
        self.current_bet = 0
        self.min_raise = self.BET
        self.checks = 0

        # Олл-ин: доигрываем до showdown
        if self.player_chips == 0 or self.ai_chips == 0:
            while len(self.community) < 5:
                self.community.append(self.deck.draw())
            self._showdown()
            return

        if self.street == 0:
            self.street = 1
            self.community = [self.deck.draw() for _ in range(3)]
        elif self.street == 1:
            self.street = 2
            self.community.append(self.deck.draw())
        elif self.street == 2:
            self.street = 3
            self.community.append(self.deck.draw())
        elif self.street == 3:
            self._showdown()
            return
        self.to_act = 0
        self.rebuild()

    def _showdown(self):
        self.show_ai = True
        pe = evaluate_7(self.player + self.community)
        ae = evaluate_7(self.ai + self.community)
        pn = HAND_NAMES[pe[0]]
        an = HAND_NAMES[ae[0]]
        pot = self.pot
        self.pot = 0

        if pe > ae:
            self.player_chips += pot
            msg = f"Вы выиграли ${pot} — {pn}!"
        elif ae > pe:
            self.ai_chips += pot
            msg = f"{self.opponent.name} выиграл ${pot} — {an}."
        else:
            half = pot // 2
            self.player_chips += half
            self.ai_chips += pot - half
            msg = f"Ничья ({pn})!"

        if self._is_learning():
            delta = self.ai_chips - self.ai_hand_start
            self.opponent.learn(delta)
        self.end_hand(msg)

    def end_hand(self, msg):
        self.state = 'over'
        self.message = msg
        self.rebuild()


# ═══════════════════════════════════════════════════════════════════════════
#  ОБУЧЕНИЕ: БОТ vs ИИ
# ═══════════════════════════════════════════════════════════════════════════
class Training:
    """
    Автопрогон партий для обучения. Раз в 1000 партий сохраняет Q-таблицу.
    """
    def __init__(self, bot, ai):
        self.bot = bot
        self.ai  = ai
        self.session_games     = 0
        self.session_ai_wins   = 0
        self.session_bot_wins  = 0
        self.session_ties      = 0
        self.paused    = False
        self.timer     = None
        self.batch     = None
        self.buttons   = []
        self.last_result = "Запуск..."
        self.rebuild()
        self._schedule()

    def _schedule(self):
        self.timer = pyglet.clock.schedule_interval(self._tick, 0.10)

    def stop(self):
        if self.timer:
            pyglet.clock.unschedule(self.timer)
            self.timer = None
        # Сохраняем при остановке
        self.ai.save()

    def toggle_pause(self):
        self.paused = not self.paused
        self.ai.save()   # Сохраняем при паузе
        self.rebuild()

    def go_menu(self):
        self.stop()
        back_to_menu()

    def _tick(self, dt):
        if self.paused:
            return
        # За тик — 3 партии (30/сек — быстро, но не жрёт CPU)
        for _ in range(3):
            self._play_one()
        self.rebuild()

    def _play_one(self):
        """
        Одна упрощённая партия preflop → showdown.
        Если AI фолдит — небольшой минус. Если выигрывает — плюс.
        """
        deck = Deck()
        bot_cards = [deck.draw(), deck.draw()]
        ai_cards  = [deck.draw(), deck.draw()]

        bot_contrib = Poker.ANTE
        ai_contrib  = Poker.ANTE
        pot         = Poker.ANTE * 2
        bot_chips   = 500 - bot_contrib
        ai_chips    = 500 - ai_contrib

        bot_action = self.bot.choose(bot_cards, [], 0, bot_chips,
                                     Poker.BET, pot, can_raise=False)

        if bot_action == 'bet':
            bot_contrib += Poker.BET
            pot += Poker.BET
            ai_chips = 500 - ai_contrib
            ai_action = self.ai.choose(ai_cards, [], Poker.BET, ai_chips,
                                       Poker.BET, pot, can_raise=False)
            if ai_action == 'call':
                ai_contrib += Poker.BET
                pot += Poker.BET
            else:
                self.ai.learn(-ai_contrib)
                self.session_bot_wins += 1
                self.session_games += 1
                self.last_result = f"#{self.session_games}: ИИ сбросил"
                return
        else:
            ai_action = self.ai.choose(ai_cards, [], 0, ai_chips,
                                       Poker.BET, pot, can_raise=False)
            if ai_action == 'bet':
                ai_contrib += Poker.BET
                pot += Poker.BET
                bot_chips = 500 - bot_contrib
                bot_response = self.bot.choose(bot_cards, [], Poker.BET,
                                               bot_chips, Poker.BET, pot,
                                               can_raise=False)
                if bot_response == 'call':
                    bot_contrib += Poker.BET
                    pot += Poker.BET
                else:
                    self.ai.learn(pot - ai_contrib)
                    self.session_ai_wins += 1
                    self.session_games += 1
                    self.last_result = f"#{self.session_games}: Бот сбросил"
                    return

        community = [deck.draw() for _ in range(5)]
        bot_eval = evaluate_7(bot_cards + community)
        ai_eval  = evaluate_7(ai_cards + community)

        if ai_eval > bot_eval:
            self.ai.learn(pot - ai_contrib)
            self.session_ai_wins += 1
            self.last_result = f"#{self.session_games+1}: ИИ +{pot-ai_contrib}"
        elif bot_eval > ai_eval:
            self.ai.learn(-ai_contrib)
            self.session_bot_wins += 1
            self.last_result = f"#{self.session_games+1}: Бот победил"
        else:
            self.ai.learn(0)
            self.session_ties += 1
            self.last_result = f"#{self.session_games+1}: Ничья"
        self.session_games += 1

        # Периодическое сохранение каждые 1000 партий
        if self.ai.games > 0 and self.ai.games % 1000 == 0:
            self.ai.save()

    def rebuild(self):
        self.batch   = pyglet.graphics.Batch()
        self.buttons = []
        b = self.batch
        shapes.Rectangle(0, 0, WIDTH, HEIGHT, color=DARK_GREEN, batch=b)

        text.Label("ОБУЧЕНИЕ: БОТ vs ИИ", x=WIDTH//2, y=HEIGHT-60,
                   anchor_x='center', font_size=30, batch=b,
                    color=GOLD)
        if self.paused:
            text.Label("ПАУЗА", x=WIDTH//2, y=HEIGHT-100,
                       anchor_x='center', font_size=22, batch=b, color=RED)

        y = HEIGHT - 160
        sess_wr = (self.session_ai_wins * 100.0 / self.session_games
                   if self.session_games else 0)
        for line in [
            f"В сессии: {self.session_games} партий",
            f"  ИИ: {self.session_ai_wins} ({sess_wr:.1f}%)   "
            f"Бот: {self.session_bot_wins}   Ничьих: {self.session_ties}",
        ]:
            text.Label(line, x=WIDTH//2, y=y, anchor_x='center',
                       font_size=17, batch=b)
            y -= 32

        y -= 25
        for line in [
            f"Всего ИИ обучен на {self.ai.games} партиях",
            f"Винрейт ИИ: {self.ai.winrate():.1f}%   "
            f"Агрессия: {self.ai.aggression():+.2f}",
        ]:
            text.Label(line, x=WIDTH//2, y=y, anchor_x='center',
                       font_size=15, batch=b, color=GOLD)
            y -= 28

        y -= 30
        text.Label("Q-таблица (память ИИ):", x=WIDTH//2, y=y,
                   anchor_x='center', font_size=15, batch=b, )
        y -= 32
        labels_sb = ['слабая', 'средняя', 'сильная']
        for sb in range(3):
            for tc in range(2):
                q = self.ai.Q[(sb, tc)]
                tn = 'ставка' if tc else 'нет ставки'
                line = (f"[{labels_sb[sb]}, {tn}]: "
                        f"фолд={q[0]:+.2f}  колл={q[1]:+.2f}  рейз={q[2]:+.2f}")
                text.Label(line, x=WIDTH//2, y=y, anchor_x='center',
                           font_size=13, batch=b)
                y -= 26

        y -= 45
        if self.last_result:
            text.Label(self.last_result, x=WIDTH//2, y=y, anchor_x='center',
                       font_size=17, batch=b, color=GOLD)

        if self.paused:
            add_button(b, self.buttons, WIDTH//2-260, 60, 240, 55,
                       "ПРОДОЛЖИТЬ", self.toggle_pause, style='green')
        else:
            add_button(b, self.buttons, WIDTH//2-260, 60, 240, 55,
                       "ПАУЗА", self.toggle_pause)
        add_button(b, self.buttons, WIDTH//2+20, 60, 240, 55,
                   "МЕНЮ", self.go_menu, style='gold')


# ═══════════════════════════════════════════════════════════════════════════
#  МЕНЮ И ПРИЛОЖЕНИЕ
# ═══════════════════════════════════════════════════════════════════════════
def back_to_menu():
    if APP:
        if APP.scene == 'training' and APP.training:
            APP.training.stop()
        APP.learning_ai.save()
        APP._build_menu()
        APP.scene = 'menu'


class App:
    def __init__(self, window):
        global APP
        APP = self
        self.window = window
        self.scene  = 'menu'

        self.menu_batch   = None
        self.menu_buttons = []

        self.blackjack = None
        self.poker     = None
        self.training  = None

        self.bot = BotAI()
        self.learning_ai = LearningAI()
        # Загружаем сохранённую Q-таблицу при старте
        loaded = self.learning_ai.load()
        if loaded:
            print(f"Загружено {self.learning_ai.games} партий из {SAVE_PATH}")
        else:
            print("Сохранённых данных нет — обучение с нуля")

        self._build_menu()

    def _build_menu(self):
        self.menu_batch   = pyglet.graphics.Batch()
        self.menu_buttons = []
        b = self.menu_batch
        shapes.Rectangle(0, 0, WIDTH, HEIGHT, color=DARK_GREEN, batch=b)

        text.Label("КАЗИНО", x=WIDTH//2, y=HEIGHT-110,
                   anchor_x='center', anchor_y='center',
                   font_size=72, batch=b, color=GOLD, )
        text.Label("Блэкджек · Холдем · Обучение ИИ",
                   x=WIDTH//2, y=HEIGHT-180,
                   anchor_x='center', font_size=22, batch=b)

        specs = [
            (540, "БЛЭКДЖЕК",                       self.start_blackjack,    'blue'),
            (456, "ХОЛДЕМ: Игрок vs Бот",           self.start_poker_bot,    'blue'),
            (372, "ХОЛДЕМ: Игрок vs Обучаемый ИИ",  self.start_poker_ai,     'green'),
            (288, "ОБУЧЕНИЕ: Бот vs ИИ",            self.start_training,     'gold'),
        ]
        for y, label, cb, style in specs:
            add_button(b, self.menu_buttons, WIDTH//2-240, y, 480, 62,
                       label, cb, style=style)

        ai = self.learning_ai
        text.Label(
            f"ИИ обучен на {ai.games} партиях · винрейт {ai.winrate():.1f}%",
            x=WIDTH//2, y=210, anchor_x='center',
            font_size=15, batch=b, color=GOLD)

    def start_blackjack(self):
        self.learning_ai.save()
        self.blackjack = Blackjack()
        self.scene = 'blackjack'

    def start_poker_bot(self):
        self.learning_ai.save()
        self.poker = Poker(self.bot)
        self.scene = 'poker'

    def start_poker_ai(self):
        self.learning_ai.save()
        self.poker = Poker(self.learning_ai)
        self.scene = 'poker'

    def start_training(self):
        self.learning_ai.save()
        if self.training:
            self.training.stop()
        self.training = Training(self.bot, self.learning_ai)
        self.scene = 'training'

    def on_draw(self):
        self.window.clear()
        if self.scene == 'menu':
            self.menu_batch.draw()
        elif self.scene == 'blackjack':
            self.blackjack.batch.draw()
        elif self.scene == 'poker':
            self.poker.batch.draw()
        elif self.scene == 'training':
            self.training.batch.draw()

    def on_mouse_press(self, x, y, button, modifiers):
        if button != pyglet.window.mouse.LEFT:
            return
        if self.scene == 'menu':
            buttons = self.menu_buttons
        elif self.scene == 'blackjack':
            buttons = self.blackjack.buttons
        elif self.scene == 'poker':
            buttons = self.poker.buttons
        elif self.scene == 'training':
            buttons = self.training.buttons
        else:
            return
        for bx, by, bw, bh, cb, enabled in buttons:
            if enabled and bx <= x <= bx + bw and by <= y <= by + bh:
                cb()
                return

    def on_close(self):
        # Сохраняем Q-таблицу перед закрытием
        saved = self.learning_ai.save()
        if saved:
            print(f"AI сохранён: {self.learning_ai.games} партий в {SAVE_PATH}")
        if self.training:
            self.training.stop()
        pyglet.app.exit()


if __name__ == '__main__':
    window = pyglet.window.Window(WIDTH, HEIGHT, "Казино + ИИ")
    app = App(window)
    window.push_handlers(app)
    pyglet.app.run()