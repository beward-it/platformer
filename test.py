"""
КАЗИНО: Блэкджек + Техасский Холдем + Обучение ИИ
==================================================

Один файл. Запуск: python casino.py
Требуется: pyglet >= 2.0

Режимы:
  1. Блэкджек (игрок vs дилер)
  2. Холдем: игрок vs бот (pot odds)
  3. Холдем: игрок vs обучаемый ИИ (Q-learning)
  4. Обучение: Холдем (бот vs ИИ, автопрогон)
  5. Обучение: Блэкджек (ИИ-игрок vs дилер, автопрогон)
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
#  ФИКС Pyglet 2.x:
#   1. shapes.* и text.Label удаляются из batch сборщиком мусора, если нет
#      живой Python-ссылки → оборачиваем и складываем в batch._refs.
#   2. У Label в 2.x нет аргумента bold — есть weight. Перехватываем bold=
#      и транслируем в weight= до вызова конструктора.
# ═══════════════════════════════════════════════════════════════════════════
def _keep_shape(ctor):
    def wrapper(*args, batch=None, **kwargs):
        obj = ctor(*args, batch=batch, **kwargs)
        if batch is not None:
            refs = getattr(batch, '_refs', None)
            if refs is None:
                batch._refs = refs = []
            refs.append(obj)
        return obj
    return wrapper


def _keep_label(ctor):
    def wrapper(*args, batch=None, bold=None, weight=None, **kwargs):
        # Транслируем устаревший bold= в weight=
        if weight is None and bold is not None:
            weight = 'bold' if bold else 'normal'
        if weight is not None:
            kwargs['weight'] = weight
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
        setattr(shapes, _n, _keep_shape(getattr(shapes, _n)))
text.Label = _keep_label(text.Label)


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

_here = os.path.dirname(os.path.abspath(__file__))
SAVE_PATH     = os.path.join(_here, 'casino_ai.json')
SAVE_PATH_BJ  = os.path.join(_here, 'casino_bj_ai.json')

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
#  БЛЭКДЖЕК: подсчёт суммы (модульная функция — нужна и сцене, и тренеру)
# ═══════════════════════════════════════════════════════════════════════════
def bj_hand_total(hand):
    """Сумма с автоспуском туза 11→1. Возвращает int."""
    total = sum(c.bj_value() for c in hand)
    aces = sum(1 for c in hand if c.rank == 14)
    while total > 21 and aces > 0:
        total -= 10
        aces -= 1
    return total


# ═══════════════════════════════════════════════════════════════════════════
#  ОЦЕНКА ПОКЕРНЫХ РУК
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
               font_size=22, color=color, batch=batch, bold=True)
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
               bold=True)
    buttons.append((x, y, w, h, cb, enabled))


# ═══════════════════════════════════════════════════════════════════════════
#  ИИ-ОППОНЕНТЫ (ХОЛДЕМ)
# ═══════════════════════════════════════════════════════════════════════════
class BotAI:
    """Правиловый бот на pot odds."""
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
            pot_odds = to_call / (pot + to_call) if (pot + to_call) > 0 else 0.5
            adj = s - 0.05
            if can_raise and adj > 0.72 and chips >= to_call * 2 and random.random() < 0.7:
                return 'raise'
            if adj > pot_odds + 0.04:
                return 'call'
            if adj > pot_odds - 0.02 and random.random() < 0.20:
                return 'call'
            return 'fold'
        if can_raise and s > 0.62 and random.random() < 0.75:
            return 'bet'
        return 'check'

    def learn(self, chip_delta):
        pass


class LearningAI:
    """Q-learning для Холдема. Сохранение в casino_ai.json."""
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
        if sb == 0:
            if tc: return (-0.3, -0.5, -0.8)
            return (-0.3, 0.0, -0.5)
        if sb == 1:
            if tc: return (-0.3, 0.1, -0.1)
            return (-0.3, 0.1, 0.0)
        if tc: return (-0.5, 0.0, 0.3)
        return (-0.5, 0.0, 0.2)

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

        if action == 0:
            if to_call > 0 and chips > 0:
                self.last_action = 0
                return 'fold'
            self.last_action = 1
            return 'check'
        if action == 1:
            self.last_action = 1
            return 'call' if to_call > 0 else 'check'
        if can_raise:
            self.last_action = 2
            return 'raise' if to_call > 0 else 'bet'
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
        alpha = max(0.03, self.alpha / (1 + n * 0.05))
        self.Q[s][a] += alpha * (reward - self.Q[s][a])
        self.N[s][a] += 1
        if chip_delta > 0: self.wins += 1
        elif chip_delta < 0: self.losses += 1
        else: self.ties += 1
        self.last_state = None
        self.last_action = None

    def winrate(self):
        return (self.wins / self.games * 100) if self.games else 0.0

    def aggression(self):
        total = 0.0
        for sb in range(3):
            for tc in range(2):
                q = self.Q[(sb, tc)]
                total += q[2] - q[0]
        return total / 6.0

    def save(self, path=SAVE_PATH):
        try:
            data = {
                'games': self.games, 'wins': self.wins,
                'losses': self.losses, 'ties': self.ties,
                'Q': {f"{s[0]},{s[1]}": list(v) for s, v in self.Q.items()},
                'N': {f"{s[0]},{s[1]}": list(v) for s, v in self.N.items()},
            }
            tmp = path + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False)
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
#  ИИ-ОППОНЕНТЫ (БЛЭКДЖЕК)
# ═══════════════════════════════════════════════════════════════════════════
class LearningBlackjack:
    """
    Q-learning AI для блэкджека.

    СОСТОЯНИЕ (5-tuple):
      (total, soft, dealer_up, is_pair, can_double)
        total       — сумма очков игрока (4..21)
        soft        — 1 если есть туз, считающийся за 11
        dealer_up   — открытая карта дилера (2..11; 11 = A)
        is_pair     — 1 если первые 2 карты одной стоимости (можно сплит)
        can_double  — 1 если можно удвоить (ровно 2 карты и хватает фишек)

    ДЕЙСТВИЯ (4): hit / stand / double / split

    ПОЧЕМУ ТАК:
      Это классическая дискретизация для блэкджека — по ней уже есть
      вычислимая базовая стратегия (Thorp, 1962). Наша задача — чтобы
      AI САМ к ней пришёл, поэтому стартовые priors только задают
      разумное направление, но не фиксируют поведение.

    ПРИОРЫ (basic strategy hints):
      • 17+ → stand (q_stand высокий)
      • ≤11 → hit (или double на 10/11)
      • 12 против слабой карты дилера → stand
      • 13–16 против сильной карты → hit

    REWARD:
      clip(chip_delta / 25, -1, +1) — нормировано на размер ставки.
      game with blackjack: reward клипуется, но и так +1.5 * bet / 25.

    SPLIT:
      В v1 тренера split обрабатывается упрощённо: у AI есть слот в Q,
      но тренер трактует split как stand (редко оптимален в упрощённой
      модели). Это позволяет сохранить совместимость с будущим улучшением.
    """
    name = "Обучаемый Блэкджек-ИИ"
    ACTIONS = ['hit', 'stand', 'double', 'split']
    ACTION_NAMES = ['Взять', 'Пас', 'Удвоить', 'Сплит']

    def __init__(self):
        self.Q = {}
        self.N = {}
        self.alpha = 0.10
        self.epsilon = 0.15
        self.games = 0
        self.wins = 0
        self.losses = 0
        self.ties = 0
        self.traj = []

    def _state(self, hand, dealer_up, can_double):
        total = bj_hand_total(hand)
        # soft: есть ли туз, ещё считающийся за 11 (т.е. total не «пересчитан»)
        raw = sum(c.bj_value() for c in hand)
        soft = raw <= 21 and raw == total and any(c.rank == 14 for c in hand)
        is_pair = (len(hand) == 2 and
                   hand[0].bj_value() == hand[1].bj_value())
        up = dealer_up.bj_value()
        return (min(total, 21), int(soft), up, int(is_pair), int(can_double))

    def _prior(self, state):
        total, soft, up, pair, can_double = state
        q = [0.0, 0.0, 0.0, 0.0]
        if total >= 17:
            q[0] = -0.5; q[1] = 0.5
        elif total <= 11:
            q[0] = 0.5; q[1] = -0.5
            if can_double and total == 11:
                q[2] = 0.7
            elif can_double and total == 10 and up <= 9:
                q[2] = 0.6
        elif 12 <= total <= 16:
            if up in (4, 5, 6):
                q[0] = -0.3; q[1] = 0.3
            else:
                q[0] = 0.2; q[1] = -0.1
        if pair:
            # Стандартно: сплитим A,A и 8,8; не сплитим 5,5 и 10,10
            if up != 0:
                if total in (2, 12, 16):  # A,A (12 soft) или 8,8 (16)
                    q[3] = 0.6
                elif total == 10:  # 5,5
                    q[3] = -0.5
                elif total == 20:  # 10,10
                    q[3] = -0.7
        return q

    def _legal(self, hand, chips, bet, can_double, can_split):
        legal = [0, 1]  # hit, stand
        if can_double and chips >= bet:
            legal.append(2)
        if can_split:
            legal.append(3)
        return legal

    def choose(self, hand, dealer_up, chips, bet, can_double, can_split):
        state = self._state(hand, dealer_up, can_double)
        if state not in self.Q:
            self.Q[state] = self._prior(state)
            self.N[state] = [0, 0, 0, 0]
        legal = self._legal(hand, chips, bet, can_double, can_split)

        if random.random() < self.epsilon:
            action_idx = random.choice(legal)
        else:
            q = self.Q[state]
            action_idx = max(legal, key=lambda i: q[i])

        self.traj.append((state, action_idx))
        return self.ACTIONS[action_idx]

    def end_hand(self, delta):
        reward = max(-1.0, min(1.0, delta / 25.0))
        for state, action in self.traj:
            if state not in self.N:
                self.N[state] = [0, 0, 0, 0]
            n = self.N[state][action]
            alpha = max(0.03, self.alpha / (1 + n * 0.05))
            self.Q[state][action] += alpha * (reward - self.Q[state][action])
            self.N[state][action] += 1
        self.traj = []
        self.games += 1
        if delta > 0: self.wins += 1
        elif delta < 0: self.losses += 1
        else: self.ties += 1

    def winrate(self):
        return (self.wins / self.games * 100) if self.games else 0.0

    def top_states(self, k=10):
        """Топ состояний по числу посещений — для UI тренировки."""
        rows = []
        for state, ns in self.N.items():
            v = sum(ns)
            if v >= 5:
                q = self.Q[state]
                best = q.index(max(q))
                rows.append((v, state, best, max(q)))
        rows.sort(reverse=True)
        return rows[:k]

    def describe_state(self, state):
        total, soft, up, pair, can_double = state
        up_name = 'A' if up == 11 else str(up)
        tag = 'soft' if soft else 'hard'
        extra = ''
        if pair: extra = ' · пара'
        elif can_double: extra = ' · ×2'
        return f"{total} ({tag}) vs {up_name}{extra}"

    def save(self, path=SAVE_PATH_BJ):
        try:
            data = {
                'games': self.games, 'wins': self.wins,
                'losses': self.losses, 'ties': self.ties,
                'Q': {','.join(map(str, s)): list(v)
                      for s, v in self.Q.items()},
                'N': {','.join(map(str, s)): list(v)
                      for s, v in self.N.items()},
            }
            tmp = path + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False)
            os.replace(tmp, path)
            return True
        except Exception as e:
            print(f"BJ AI save error: {e}")
            return False

    def load(self, path=SAVE_PATH_BJ):
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
                key = tuple(int(x) for x in k_str.split(','))
                self.Q[key] = list(q_list)
            for k_str, n_list in data.get('N', {}).items():
                key = tuple(int(x) for x in k_str.split(','))
                self.N[key] = list(n_list)
            return True
        except Exception as e:
            print(f"BJ AI load error: {e}")
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
        self.doubled_this_hand = False
        self.buttons      = []
        self.batch        = None
        self.rebuild()

    def hand_total(self, hand):
        return bj_hand_total(hand)

    def rebuild(self):
        self.batch   = pyglet.graphics.Batch()
        self.buttons = []
        b = self.batch

        shapes.Rectangle(0, 0, WIDTH, HEIGHT, color=DARK_GREEN, batch=b)

        text.Label(f"Фишки: ${self.chips}", x=30, y=HEIGHT-42,
                   font_size=22, batch=b, bold=True)
        bet_disp = f"Ставка: ${self.bet}"
        if self.doubled_this_hand:
            bet_disp += "   ×2"
        text.Label(bet_disp, x=30, y=HEIGHT-74, font_size=16, batch=b,
                   color=GOLD if self.doubled_this_hand else WHITE,
                   bold=self.doubled_this_hand)

        text.Label("ДИЛЕР", x=200, y=HEIGHT-130, font_size=20, batch=b, bold=True)
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

        if self.player:
            t = self.hand_total(self.player)
            player_label = f"ВЫ · {t}"
            if self.doubled_this_hand:
                player_label += "   (×2)"
            text.Label(player_label, x=200, y=238, font_size=18, batch=b,
                       bold=True,
                       color=GOLD if self.doubled_this_hand else WHITE)
        else:
            text.Label("ВЫ", x=200, y=238, font_size=20, batch=b, bold=True)
        draw_hand(b, self.player, 200, 115)

        if self.state in ('playing', 'dealer', 'over') and self.player:
            text.Label(f"Ставка в раунде: ${self.bet}",
                       x=200, y=98, font_size=13, batch=b,
                       color=GOLD if self.doubled_this_hand else BTN_LIGHT)

        if self.message:
            text.Label(self.message, x=WIDTH//2, y=HEIGHT//2 + 10,
                       anchor_x='center', anchor_y='center',
                       font_size=28, batch=b, bold=True, color=GOLD)

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
        self.doubled_this_hand = False
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
        if self.state != 'playing':
            return
        self.player.append(self.deck.draw())
        if self.hand_total(self.player) > 21:
            self.end_round(f"ПЕРЕБОР! Теряете ${self.bet}.")
        else:
            self.rebuild()

    def stand(self):
        if self.state != 'playing':
            return
        self.state = 'dealer'
        self.rebuild()
        pyglet.clock.schedule_once(self._dealer_phase, 0.4)

    def double(self):
        if self.state != 'playing':
            return
        if self.chips < self.bet:
            return
        self.chips -= self.bet
        self.bet *= 2
        self.doubled_this_hand = True
        self.player.append(self.deck.draw())
        if self.hand_total(self.player) > 21:
            self.end_round(f"ПЕРЕБОР! Теряете ${self.bet}.")
        else:
            self.state = 'dealer'
            self.rebuild()
            pyglet.clock.schedule_once(self._dealer_phase, 0.9)

    def _dealer_phase(self, dt):
        if self.state != 'dealer':
            return
        self.show_dealer = True
        while self.hand_total(self.dealer) < 17:
            self.dealer.append(self.deck.draw())
        self.rebuild()
        pyglet.clock.schedule_once(self._finalize, 0.6)

    def _finalize(self, dt):
        if self.state != 'dealer':
            return
        self._resolve()

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
        if self.doubled_this_hand:
            msg = f"×2   {msg}"
        self.message = msg
        self.rebuild()

    def new_round(self):
        if self.chips < self.BET:
            self.chips = self.START
        self.state = 'ready'
        self.player, self.dealer = [], []
        self.message = ""
        self.show_dealer = False
        self.bet = self.BET
        self.doubled_this_hand = False
        self.rebuild()


# ═══════════════════════════════════════════════════════════════════════════
#  ПОКЕР (без изменений — рейзы и pot odds работают)
# ═══════════════════════════════════════════════════════════════════════════
class Poker:
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

    def rebuild(self):
        self.batch = pyglet.graphics.Batch()
        self.buttons = []
        b = self.batch
        shapes.Rectangle(0, 0, WIDTH, HEIGHT, color=DARK_GREEN, batch=b)

        text.Label(f"Вы: ${self.player_chips}", x=30, y=HEIGHT-42,
                   font_size=18, batch=b, bold=True)
        text.Label(f"{self.opponent.name}: ${self.ai_chips}",
                   x=WIDTH-280, y=HEIGHT-42, font_size=18, batch=b, bold=True)
        text.Label(f"Банк: ${self.pot}", x=WIDTH//2, y=HEIGHT-42,
                   anchor_x='center', font_size=22, batch=b, bold=True, color=GOLD)

        sn = ['ПРЕФЛОП', 'ФЛОП', 'ТЁРН', 'РИВЕР']
        if self.state == 'playing':
            text.Label(sn[self.street], x=WIDTH//2, y=HEIGHT-74,
                       anchor_x='center', font_size=15, batch=b)

        text.Label(self.opponent.name, x=200, y=HEIGHT-130,
                   font_size=18, batch=b, bold=True)
        if self.show_ai and len(self.ai) == 2 and len(self.community) >= 3:
            ev = evaluate_7(self.ai + self.community)
            text.Label(HAND_NAMES[ev[0]], x=370, y=HEIGHT-130,
                       font_size=14, batch=b, color=GOLD)
        hide = set() if self.show_ai else {0, 1}
        draw_hand(b, self.ai, 200, HEIGHT-265, hide)
        if self.ai_street_bet > 0:
            text.Label(f"ставка: ${self.ai_street_bet}",
                       x=200, y=HEIGHT-290, font_size=14, batch=b, color=GOLD)

        if self.community:
            text.Label("ОБЩИЕ КАРТЫ", x=200, y=HEIGHT//2 + 100,
                       font_size=15, batch=b, bold=True)
            draw_hand(b, self.community, 200, HEIGHT//2 - 45)

        if self.player and len(self.community) >= 3:
            ev = evaluate_7(self.player + self.community)
            text.Label(f"ВЫ · {HAND_NAMES[ev[0]]}", x=200, y=253,
                       font_size=15, batch=b, bold=True)
        else:
            text.Label("ВЫ", x=200, y=253, font_size=18, batch=b, bold=True)
        draw_hand(b, self.player, 200, 115)
        if self.player_street_bet > 0:
            text.Label(f"ставка: ${self.player_street_bet}",
                       x=200, y=100, font_size=13, batch=b, color=GOLD)

        if self.message:
            text.Label(self.message, x=WIDTH//2, y=305,
                       anchor_x='center', font_size=22, batch=b,
                       bold=True, color=GOLD)

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
            return

        to_call = self.current_bet - self.player_street_bet
        btn_w, btn_h, gap, y = 175, 55, 6, 30
        total_w = 6 * btn_w + 5 * gap
        x = (WIDTH - total_w) // 2

        add_button(b, self.buttons, x, y, btn_w, btn_h,
                   "ФОЛД", self.player_fold,
                   to_call > 0, style='red')
        x += btn_w + gap

        if to_call > 0:
            add_button(b, self.buttons, x, y, btn_w, btn_h,
                       f"КОЛЛ ${to_call}", self.player_call,
                       self.player_chips >= to_call)
        else:
            add_button(b, self.buttons, x, y, btn_w, btn_h,
                       "ЧЕК", self.player_check)
        x += btn_w + gap

        can_raise = self._can_player_raise()
        min_to = self._player_min_raise()
        max_to = self._player_max_raise()

        label1 = f"МИН →{min_to}" if to_call > 0 else f"БЕТ {self.BET}"
        add_button(b, self.buttons, x, y, btn_w, btn_h,
                   label1, lambda: self.player_raise('min'),
                   can_raise, style='gold')
        x += btn_w + gap

        half = self._player_raise_amount('half')
        add_button(b, self.buttons, x, y, btn_w, btn_h,
                   f"½ →{half}", lambda: self.player_raise('half'),
                   can_raise, style='gold')
        x += btn_w + gap

        pot_raise = self._player_raise_amount('pot')
        add_button(b, self.buttons, x, y, btn_w, btn_h,
                   f"БАНК →{pot_raise}", lambda: self.player_raise('pot'),
                   can_raise, style='gold')
        x += btn_w + gap

        add_button(b, self.buttons, x, y, btn_w, btn_h,
                   f"ВСЁ →{max_to}", lambda: self.player_raise('allin'),
                   can_raise, style='red')

    def _player_max_raise(self):
        return min(self.player_street_bet + self.player_chips,
                   self.ai_street_bet + self.ai_chips)

    def _player_min_raise(self):
        return min(self.current_bet + self.min_raise, self._player_max_raise())

    def _can_player_raise(self):
        return (self.player_chips > (self.current_bet - self.player_street_bet) and
                self._player_max_raise() > self.current_bet)

    def _player_raise_amount(self, kind):
        to_call = self.current_bet - self.player_street_bet
        max_to = self._player_max_raise()
        min_to = self._player_min_raise()
        if kind == 'min': return min_to
        if kind == 'allin': return max_to
        frac = 0.5 if kind == 'half' else 1.0
        target = self.current_bet + int(frac * (self.pot + to_call))
        return max(min_to, min(max_to, target))

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

    def player_fold(self):
        if self.state != 'playing' or self.to_act != 0:
            return
        self.ai_chips += self.pot
        self.pot = 0
        if self._is_learning():
            self.opponent.learn(self.ai_chips - self.ai_hand_start)
        self.end_hand("Вы сбросили.")

    def player_check(self):
        if self.state != 'playing' or self.to_act != 0:
            return
        if self.current_bet > self.player_street_bet:
            return
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

    def _switch_to_ai(self):
        self.to_act = 1
        self.rebuild()
        pyglet.clock.schedule_once(lambda dt: self._ai_turn(), 0.5)

    def _ai_turn(self):
        if self.state != 'playing' or self.to_act != 1:
            return
        to_call = self.current_bet - self.ai_street_bet
        max_to = min(self.ai_street_bet + self.ai_chips,
                     self.player_street_bet + self.player_chips)
        min_to = self.current_bet + self.min_raise
        can_raise = (self.ai_chips > to_call and max_to > self.current_bet and
                     min_to <= max_to)
        if can_raise:
            base = self.current_bet * 2 if self.current_bet else self.BET * 2
            raise_to = max(min_to, min(max_to, base))
        else:
            raise_to = 0
        action = self.opponent.choose(
            self.ai, self.community, to_call, self.ai_chips,
            self.BET, self.pot, can_raise, raise_to)

        if action == 'fold':
            if to_call > 0:
                self.player_chips += self.pot
                self.pot = 0
                if self._is_learning():
                    self.opponent.learn(self.ai_chips - self.ai_hand_start)
                self.end_hand(f"{self.opponent.name} сбросил.")
                return
            action = 'check'

        if action == 'check':
            if to_call > 0:
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

        if self.current_bet == 0:
            amount = min(self.BET, self.ai_chips)
            self.ai_chips -= amount
            self.pot += amount
            self.ai_street_bet = amount
            self.current_bet = amount
            self.min_raise = self.BET
        else:
            if not can_raise or raise_to <= self.current_bet:
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

    def _next_street(self):
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
            self.opponent.learn(self.ai_chips - self.ai_hand_start)
        self.end_hand(msg)

    def end_hand(self, msg):
        self.state = 'over'
        self.message = msg
        self.rebuild()


# ═══════════════════════════════════════════════════════════════════════════
#  ОБУЧЕНИЕ: ХОЛДЕМ
# ═══════════════════════════════════════════════════════════════════════════
class Training:
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
        self.ai.save()

    def toggle_pause(self):
        self.paused = not self.paused
        self.ai.save()
        self.rebuild()

    def go_menu(self):
        self.stop()
        back_to_menu()

    def _tick(self, dt):
        if self.paused:
            return
        for _ in range(3):
            self._play_one()
        self.rebuild()

    def _play_one(self):
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
            ai_action = self.ai.choose(ai_cards, [], Poker.BET, 500 - ai_contrib,
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
            ai_action = self.ai.choose(ai_cards, [], 0, 500 - ai_contrib,
                                       Poker.BET, pot, can_raise=False)
            if ai_action == 'bet':
                ai_contrib += Poker.BET
                pot += Poker.BET
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
        if self.ai.games > 0 and self.ai.games % 1000 == 0:
            self.ai.save()

    def rebuild(self):
        self.batch   = pyglet.graphics.Batch()
        self.buttons = []
        b = self.batch
        shapes.Rectangle(0, 0, WIDTH, HEIGHT, color=DARK_GREEN, batch=b)

        text.Label("ОБУЧЕНИЕ: ХОЛДЕМ (БОТ vs ИИ)", x=WIDTH//2, y=HEIGHT-60,
                   anchor_x='center', font_size=30, batch=b,
                   bold=True, color=GOLD)
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
                   anchor_x='center', font_size=15, batch=b, bold=True)
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
#  ОБУЧЕНИЕ: БЛЭКДЖЕК
# ═══════════════════════════════════════════════════════════════════════════
class BlackjackTrainer:
    """
    Автопрогон раздач: AI-игрок vs дилер.
    Каждая раздача — обновление Q-таблицы по итоговому чип-дельте.
    Сплит в v1 не реализован — если AI его выбирает, действие
    трактуется как stand (чтобы не усложнять траекторию).
    """
    BET = 25

    def __init__(self, ai):
        self.ai = ai
        self.hands = 0
        self.ai_wins = 0
        self.dealer_wins = 0
        self.ties = 0
        self.net = 0

    def play_hand(self):
        deck = Deck()
        player = [deck.draw(), deck.draw()]
        dealer = [deck.draw(), deck.draw()]
        bet = self.BET

        pt = bj_hand_total(player)
        dt_visible = dealer[0].bj_value()

        # Блэкджек с раздачи
        if pt == 21:
            if bj_hand_total(dealer) == 21:
                self.ai.end_hand(0)
                self.hands += 1; self.ties += 1
            else:
                delta = int(bet * 1.5)
                self.ai.end_hand(delta)
                self.hands += 1; self.ai_wins += 1; self.net += delta
            return

        # Основной цикл решений
        while True:
            total = bj_hand_total(player)
            if total >= 21:
                break
            can_double = (len(player) == 2)
            can_split = False  # v1: сплит отключён в тренере
            action = self.ai.choose(player, dealer[0], 500, bet,
                                    can_double, can_split)
            if action == 'hit':
                player.append(deck.draw())
            elif action == 'stand':
                break
            elif action == 'double':
                bet *= 2
                player.append(deck.draw())
                break
            elif action == 'split':
                # v1: сплит не поддерживается — трактуем как stand
                break

        pt = bj_hand_total(player)
        if pt > 21:
            self.ai.end_hand(-bet)
            self.hands += 1; self.dealer_wins += 1; self.net -= bet
            return

        # Ход дилера
        while bj_hand_total(dealer) < 17:
            dealer.append(deck.draw())
        dt = bj_hand_total(dealer)

        if dt > 21 or pt > dt:
            self.ai.end_hand(bet)
            self.hands += 1; self.ai_wins += 1; self.net += bet
        elif pt == dt:
            self.ai.end_hand(0)
            self.hands += 1; self.ties += 1
        else:
            self.ai.end_hand(-bet)
            self.hands += 1; self.dealer_wins += 1; self.net -= bet


class BlackjackTrainingScene:
    """Сцена обучения блэкджек-AI. Автопрогон раздач с UI."""
    SPEEDS = [('x1', 0.0), ('x10', 0.012), ('МАКС', 0.040)]

    def __init__(self, app, ai):
        self.app = app
        self.ai = ai
        self.trainer = BlackjackTrainer(ai)
        self.paused = False
        self.speed = 1
        self.batch = None
        self.buttons = []
        self.saved_note = ''
        self._acc = 0.0
        self._last_draw = 0.0
        self.rebuild()
        pyglet.clock.schedule_interval(self._tick, 1/30)

    def _tick(self, dt):
        if self.paused:
            return
        import time as _t
        t0 = _t.perf_counter()
        budget = self.SPEEDS[self.speed][1]
        if budget == 0.0:
            self._acc += dt
            if self._acc >= 0.25:
                self._acc = 0.0
                self.trainer.play_hand()
        else:
            # 1 партия за тик при малой скорости, ~200 за 30 мс при макс
            while _t.perf_counter() - t0 < budget:
                self.trainer.play_hand()
        if _t.perf_counter() - self._last_draw > 0.12:
            self._last_draw = _t.perf_counter()
            self.rebuild()

    def toggle_pause(self):
        self.paused = not self.paused
        self.ai.save()
        self.rebuild()

    def cycle_speed(self):
        self.speed = (self.speed + 1) % len(self.SPEEDS)
        self.rebuild()

    def save(self):
        self.saved_note = "Сохранено" if self.ai.save() else "Ошибка"
        self.rebuild()

    def reset(self):
        self.ai.__init__()
        self.trainer = BlackjackTrainer(self.ai)
        self.rebuild()

    def go_menu(self):
        pyglet.clock.unschedule(self._tick)
        self.ai.save()
        back_to_menu()

    def rebuild(self):
        self.batch = pyglet.graphics.Batch()
        self.buttons = []
        b = self.batch
        ai = self.ai
        tr = self.trainer

        shapes.Rectangle(0, 0, WIDTH, HEIGHT, color=DARK_GREEN, batch=b)

        text.Label("ОБУЧЕНИЕ: БЛЭКДЖЕК (ИИ vs ДИЛЕР)",
                   x=WIDTH//2, y=HEIGHT-55,
                   anchor_x='center', font_size=28, batch=b,
                   bold=True, color=GOLD)
        text.Label("ПАУЗА" if self.paused else "идёт обучение…",
                   x=WIDTH//2, y=HEIGHT-92, anchor_x='center',
                   font_size=15, batch=b,
                   color=RED if self.paused else GREEN_TXT
                   if 'GREEN_TXT' in globals() else (130, 230, 150, 255))

        # Левая панель — статистика
        shapes.Rectangle(30, 150, 480, 540, color=(0, 0, 0, 130), batch=b)
        y = 655
        stats = [
            ("Раздач в сессии", f"{tr.hands}", WHITE),
            ("ИИ / дилер / ничьи",
             f"{tr.ai_wins} / {tr.dealer_wins} / {tr.ties}", WHITE),
            ("Итог сессии", f"{tr.net:+d} $",
             (130, 230, 150, 255) if tr.net > 0 else
             ((240, 110, 110, 255) if tr.net < 0 else WHITE)),
            ("Всего раздач у ИИ", f"{ai.games}", GOLD),
            ("Винрейт ИИ", f"{ai.winrate():.1f}%", GOLD),
            ("Состояний в памяти", f"{len(ai.Q)}", (185, 205, 192, 255)),
            ("ε (исследование)", f"{ai.epsilon:.3f}", (185, 205, 192, 255)),
        ]
        for name, val, col in stats:
            text.Label(name, x=50, y=y, font_size=15,
                       color=(185, 205, 192, 255), batch=b)
            text.Label(val, x=492, y=y, font_size=16, color=col,
                       batch=b, bold=True, anchor_x='right')
            y -= 32

        # Правая панель — топ Q-состояний
        shapes.Rectangle(530, 380, 720, 310, color=(0, 0, 0, 130), batch=b)
        text.Label("Топ состояний (по числу посещений)",
                   x=550, y=660, font_size=15, color=WHITE,
                   batch=b, bold=True)
        yy = 632
        rows = ai.top_states(10)
        if rows:
            for v, state, best, qv in rows:
                desc = ai.describe_state(state)
                act = ai.ACTION_NAMES[best]
                text.Label(f"{desc} → {act}", x=550, y=yy,
                           font_size=13, color=(230, 230, 230, 255), batch=b)
                text.Label(f"n={v}  Q={qv:+.2f}",
                           x=1230, y=yy, font_size=12,
                           color=GOLD, batch=b, anchor_x='right')
                yy -= 24
        else:
            text.Label("Накопится после первых раздач…",
                       x=890, y=500, font_size=14,
                       color=(185, 205, 192, 255),
                       batch=b, anchor_x='center')

        # Нижняя панель — кнопки
        if self.paused:
            add_button(b, self.buttons, 150, 55, 190, 55,
                       "ПРОДОЛЖИТЬ", self.toggle_pause, style='green')
        else:
            add_button(b, self.buttons, 150, 55, 190, 55,
                       "ПАУЗА", self.toggle_pause)
        add_button(b, self.buttons, 360, 55, 200, 55,
                   "Скорость", self.cycle_speed, style='blue')
        text.Label(f"[{self.SPEEDS[self.speed][0]}]",
                   x=460, y=40, font_size=13, color=GOLD,
                   batch=b, anchor_x='center')
        add_button(b, self.buttons, 580, 55, 190, 55,
                   "СОХРАНИТЬ", self.save, style='gold')
        if self.saved_note:
            text.Label(self.saved_note, x=675, y=40, font_size=12,
                       color=(185, 205, 192, 255),
                       batch=b, anchor_x='center')
        add_button(b, self.buttons, 790, 55, 190, 55,
                   "СБРОС ИИ", self.reset, style='red')
        add_button(b, self.buttons, WIDTH-130, 55, 110, 45,
                   "МЕНЮ", self.go_menu, style='gold')


# импорт цвета — добавляем, чтобы не падать на GREEN_TXT
GREEN_TXT = (130, 230, 150, 255)


# ═══════════════════════════════════════════════════════════════════════════
#  МЕНЮ И ПРИЛОЖЕНИЕ
# ═══════════════════════════════════════════════════════════════════════════
def back_to_menu():
    if APP:
        if APP.scene == 'training' and APP.training:
            APP.training.stop()
        if APP.scene == 'bj_training' and APP.bj_training:
            try:
                pyglet.clock.unschedule(APP.bj_training._tick)
            except Exception:
                pass
            APP.bj_training.ai.save()
        APP.learning_ai.save()
        APP.bj_ai.save()
        APP._build_menu()
        APP.scene = 'menu'


class App:
    def __init__(self, window):
        global APP
        APP = self
        self.window = window
        self.scene = 'menu'
        self.menu_batch = None
        self.menu_buttons = []
        self.blackjack = None
        self.poker = None
        self.training = None
        self.bj_training = None

        self.bot = BotAI()
        self.learning_ai = LearningAI()
        self.bj_ai = LearningBlackjack()

        if self.learning_ai.load():
            print(f"Загружено {self.learning_ai.games} партий Холдема")
        else:
            print("Холдем: данных нет, обучение с нуля")
        if self.bj_ai.load():
            print(f"Загружено {self.bj_ai.games} раздач Блэкджека")
        else:
            print("Блэкджек: данных нет, обучение с нуля")

        self._build_menu()

    def _build_menu(self):
        self.menu_batch = pyglet.graphics.Batch()
        self.menu_buttons = []
        b = self.menu_batch
        shapes.Rectangle(0, 0, WIDTH, HEIGHT, color=DARK_GREEN, batch=b)

        text.Label("КАЗИНО", x=WIDTH//2, y=HEIGHT-100,
                   anchor_x='center', anchor_y='center',
                   font_size=68, batch=b, color=GOLD, bold=True)
        text.Label("Блэкджек · Холдем · Обучение ИИ",
                   x=WIDTH//2, y=HEIGHT-165,
                   anchor_x='center', font_size=22, batch=b)

        specs = [
            (525, "БЛЭКДЖЕК",                       self.start_blackjack,    'blue'),
            (445, "ХОЛДЕМ: Игрок vs Бот",           self.start_poker_bot,    'blue'),
            (365, "ХОЛДЕМ: Игрок vs Обучаемый ИИ",  self.start_poker_ai,     'green'),
            (285, "ОБУЧЕНИЕ: Холдем (Бот vs ИИ)",   self.start_training,     'gold'),
            (205, "ОБУЧЕНИЕ: Блэкджек (ИИ vs дилер)", self.start_bj_training, 'gold'),
        ]
        for y, label, cb, style in specs:
            add_button(b, self.menu_buttons, WIDTH//2-260, y, 520, 58,
                       label, cb, style=style)

        ai = self.learning_ai
        bj = self.bj_ai
        text.Label(
            f"Холдем ИИ: {ai.games} партий ({ai.winrate():.1f}%)   ·   "
            f"Блэкджек ИИ: {bj.games} раздач ({bj.winrate():.1f}%)",
            x=WIDTH//2, y=155, anchor_x='center',
            font_size=14, batch=b, color=GOLD)

    def start_blackjack(self):
        self.learning_ai.save()
        self.bj_ai.save()
        self.blackjack = Blackjack()
        self.scene = 'blackjack'

    def start_poker_bot(self):
        self.learning_ai.save()
        self.bj_ai.save()
        self.poker = Poker(self.bot)
        self.scene = 'poker'

    def start_poker_ai(self):
        self.learning_ai.save()
        self.bj_ai.save()
        self.poker = Poker(self.learning_ai)
        self.scene = 'poker'

    def start_training(self):
        self.learning_ai.save()
        self.bj_ai.save()
        if self.training:
            self.training.stop()
        self.training = Training(self.bot, self.learning_ai)
        self.scene = 'training'

    def start_bj_training(self):
        self.learning_ai.save()
        if self.bj_training:
            try:
                pyglet.clock.unschedule(self.bj_training._tick)
            except Exception:
                pass
        self.bj_training = BlackjackTrainingScene(self, self.bj_ai)
        self.scene = 'bj_training'

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
        elif self.scene == 'bj_training':
            self.bj_training.batch.draw()

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
        elif self.scene == 'bj_training':
            buttons = self.bj_training.buttons
        else:
            return
        for bx, by, bw, bh, cb, enabled in buttons:
            if enabled and bx <= x <= bx + bw and by <= y <= by + bh:
                cb()
                return

    def on_close(self):
        self.learning_ai.save()
        self.bj_ai.save()
        if self.training:
            self.training.stop()
        if self.bj_training:
            try:
                pyglet.clock.unschedule(self.bj_training._tick)
            except Exception:
                pass
        pyglet.app.exit()


if __name__ == '__main__':
    window = pyglet.window.Window(WIDTH, HEIGHT, "Казино + ИИ")
    app = App(window)
    window.push_handlers(app)
    pyglet.app.run()