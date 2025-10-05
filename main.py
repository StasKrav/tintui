#!/usr/bin/env python3
# coding: utf-8
"""
Цветовая утилита в консоли с панелями:
- Левая панель: ввод + история (скролл)
- Правая панель: отображение цвета (прямоугольник)

Клавиши:
  Enter       - обработать ввод (HEX или "R G B" в 0-1000)
  ↑ / ↓       - навигация по истории (подставляет в поле ввода)
  PageUp      - постраничный скролл истории (по умолчанию поменяны местами с PageDown)
  PageDown    - постраничный скролл истории (поведение можно инвертировать флагом SWAP_PAGE_KEYS)
  c           - копировать последний HEX (pyperclip), если установлен
  s           - сохранить историю в colors_history.json
  l           - загрузить историю из colors_history.json
  C (Shift+c) - очистить историю
  Esc         - выход
"""

import curses
import json
import os

# ----------------- КОНСТАНТЫ РАЗМЕРОВ -----------------
INPUT_PANEL_WIDTH = 50   # ширина левой панели (включая рамку)
INPUT_PANEL_HEIGHT = 12  # высота левой панели (чтобы поместилась история)
COLOR_DISPLAY_WIDTH = 20 # ширина правой панели (включая рамку)
COLOR_DISPLAY_HEIGHT = 12 # высота правой панели (включая рамку)

# ----------------- ПРОЧИЕ КОНСТАНТЫ -----------------
HISTORY_MAX = 200
HISTORY_FILENAME = "colors_history.json"

INDENT_X = 2
INDENT_Y = 1

# Если True — PageUp и PageDown поменяны местами (по желанию пользователя)
SWAP_PAGE_KEYS = True

# ----------------- ПОПЫТКА ИМПОРТА ДЛЯ КЛИПБОРА -----------------
try:
    import pyperclip
    CLIP_AVAILABLE = True
except Exception:
    CLIP_AVAILABLE = False

# ----------------- УТИЛИТЫ -----------------
def hex_to_1000(hex_color: str):
    hex_color = hex_color.lstrip("#")
    if len(hex_color) != 6:
        raise ValueError("HEX должен быть в формате #rrggbb")
    try:
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
    except ValueError:
        raise ValueError("Недопустимые символы в HEX")
    r_1000 = round(r / 255 * 1000)
    g_1000 = round(g / 255 * 1000)
    b_1000 = round(b / 255 * 1000)
    return r_1000, g_1000, b_1000

def rgb1000_to_hex(r: int, g: int, b: int):
    if not (0 <= r <= 1000 and 0 <= g <= 1000 and 0 <= b <= 1000):
        raise ValueError("Значения RGB должны быть в диапазоне 0–1000")
    r_255 = round(r / 1000 * 255)
    g_255 = round(g / 1000 * 255)
    b_255 = round(b / 1000 * 255)
    return f"#{r_255:02x}{g_255:02x}{b_255:02x}"

def save_history_to_file(history, filename=HISTORY_FILENAME):
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        return True, f"История сохранена в {filename}"
    except Exception as e:
        return False, f"Ошибка сохранения: {e}"

def load_history_from_file(filename=HISTORY_FILENAME):
    if not os.path.exists(filename):
        return [], f"Файл {filename} не найден"
    try:
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            return [], "Неверный формат файла истории"
        return data[:HISTORY_MAX], f"История загружена из {filename}"
    except Exception as e:
        return [], f"Ошибка загрузки: {e}"

# ----------------- ОСНОВНАЯ ФУНКЦИЯ CURSES -----------------
def main(stdscr):
    curses.curs_set(1)
    stdscr.nodelay(True)
    stdscr.keypad(True)

    # Проверка цвета
    if not curses.has_colors():
        stdscr.addstr("Терминал не поддерживает цвета. Нажмите любую клавишу для выхода.\n")
        stdscr.getch()
        return

    curses.start_color()
    curses.use_default_colors()
    curses.curs_set(0)

    # Цветовые пары для текста
    curses.init_pair(1, curses.COLOR_WHITE, -1)   # основной текст
    curses.init_pair(2, curses.COLOR_RED, -1)     # ошибки
    curses.init_pair(3, curses.COLOR_GREEN, -1)   # успех
    curses.init_pair(4, curses.COLOR_BLACK, curses.COLOR_WHITE) # вспомогательная

    # окна
    input_win = curses.newwin(INPUT_PANEL_HEIGHT, INPUT_PANEL_WIDTH, 0, 0)
    color_win = curses.newwin(COLOR_DISPLAY_HEIGHT, COLOR_DISPLAY_WIDTH, 0, INPUT_PANEL_WIDTH + 1)

    # состояние
    current_input = ""
    message = ""
    message_attr = curses.color_pair(1)
    last_hex = None  # последний успешно вычисленный hex
    history = []     # список hex-строк, последние первыми (0 — newest)
    history_index = None  # индекс в истории при навигации (None если не в навигации)
    history_view_start = 0  # индекс первого показываемого элемента в истории (0 = самый новый)
    use_custom_color_id = 100  # ID для init_color
    can_change_colors = curses.can_change_color()

    # вспомог: отрисовать панель цвета
    def draw_color_panel(hex_color_str):
        nonlocal color_win, last_hex
        color_win.erase()
        color_win.box()
        if not hex_color_str:
            label = "No color"
            color_win.addstr(COLOR_DISPLAY_HEIGHT//2, max(1, (COLOR_DISPLAY_WIDTH - len(label))//2), label, curses.color_pair(1))
            color_win.noutrefresh()
            return

        try:
            r_1000, g_1000, b_1000 = hex_to_1000(hex_color_str)
            if can_change_colors:
                try:
                    curses.init_color(use_custom_color_id, r_1000, g_1000, b_1000)
                    curses.init_pair(use_custom_color_id, curses.COLOR_BLACK, use_custom_color_id)
                    pair_attr = curses.color_pair(use_custom_color_id)
                except Exception:
                    pair_attr = curses.color_pair(1)
            else:
                r = round(int(hex_color_str[1:3], 16))
                g = round(int(hex_color_str[3:5], 16))
                b = round(int(hex_color_str[5:7], 16))
                avg = (r + g + b) / 3
                if avg > 200:
                    try:
                        curses.init_pair(200, curses.COLOR_BLACK, curses.COLOR_WHITE)
                        pair_attr = curses.color_pair(200)
                    except Exception:
                        pair_attr = curses.color_pair(1)
                else:
                    try:
                        curses.init_pair(201, curses.COLOR_WHITE, curses.COLOR_BLACK)
                        pair_attr = curses.color_pair(201)
                    except Exception:
                        pair_attr = curses.color_pair(1)

            inner_h = COLOR_DISPLAY_HEIGHT - 2
            inner_w = COLOR_DISPLAY_WIDTH - 2
            for y in range(inner_h):
                try:
                    color_win.addstr(1 + y, 1, " " * inner_w, pair_attr)
                except Exception:
                    color_win.addstr(1 + y, 1, "#" * inner_w, curses.color_pair(1))
        except Exception as e:
            color_win.addstr(1, 1, f"Ошибка цвета: {e}", curses.color_pair(2))

        color_win.noutrefresh()

    # начальная отрисовка
    draw_color_panel(None)

    while True:
        # отрисовываем левую панель
        input_win.erase()
        input_win.box()
        input_win.addstr(INDENT_Y, INDENT_X, "Введите hex (#rrggbb) или R G B (0-1000):", curses.color_pair(1))
        input_win.addstr(INDENT_Y + 1, INDENT_X, "", curses.color_pair(1))

        # поле ввода
        input_label = "Ввод: "
        input_win.addstr(INDENT_Y + 3, INDENT_X, input_label, curses.color_pair(1))
        max_input_len = INPUT_PANEL_WIDTH - INDENT_X - len(input_label) - 4
        display_input = current_input[-max_input_len:]
        input_win.addstr(INDENT_Y + 3, INDENT_X + len(input_label), display_input, curses.color_pair(1))

        # сообщение под вводом
        input_win.addstr(INDENT_Y + 5, INDENT_X, message[:INPUT_PANEL_WIDTH - 4], message_attr)

        # отобразим историю под сообщением (ограничено высотой окна)
        hist_start_y = INDENT_Y + 7
        available_lines = INPUT_PANEL_HEIGHT - hist_start_y - 1
        input_win.addstr(hist_start_y - 1, INDENT_X, "", curses.color_pair(1))

        # корректируем границы view_start
        if history_view_start < 0:
            history_view_start = 0
        if history_view_start > max(0, len(history) - available_lines):
            history_view_start = max(0, len(history) - available_lines)

        # берем срез для отображения
        to_show = history[history_view_start:history_view_start + available_lines]
        for i, hexv in enumerate(to_show):
            abs_idx = history_view_start + i  # абсолютный индекс в history (0 — newest)
            marker = " "
            if history_index is not None and history_index == abs_idx:
                marker = ">"
            line = f"{marker} {hexv}"
            input_win.addstr(hist_start_y + i, INDENT_X, line[:INPUT_PANEL_WIDTH - 4], curses.color_pair(1))

        input_win.noutrefresh()

        # позиция курсора: вычисляем абсолютные координаты на экране
        win_y, win_x = input_win.getbegyx()
        cursor_x = INDENT_X + len(input_label) + len(display_input)
        cursor_y = INDENT_Y + 3
        abs_cursor_y = win_y + cursor_y
        abs_cursor_x = win_x + cursor_x
        try:
            # ставим курсор в stdscr (абсолютные координаты) — чтобы мигание и ввод совпадали
            stdscr.move(abs_cursor_y, abs_cursor_x)
        except Exception:
            # fallback: если ошибка — используем move окна
            try:
                input_win.move(cursor_y, cursor_x)
            except Exception:
                pass

        curses.doupdate()

        try:
            key = stdscr.getch()
            if key == -1:
                continue

            # Выход
            if key == 27:  # ESC
                break

            # Enter
            if key in (curses.KEY_ENTER, 10, 13):
                if not current_input.strip():
                    message = "Ввод пустой"
                    message_attr = curses.color_pair(2)
                    continue

                try:
                    # определяем формат ввода
                    if current_input.strip().startswith("#"):
                        hex_color_str = current_input.strip()
                        _ = hex_to_1000(hex_color_str)
                        # Для HEX показываем RGB значения
                        r, g, b = hex_to_1000(hex_color_str)
                        message = f"HEX: {hex_color_str} -> RGB: {r} {g} {b}"
                    else:
                        parts = list(map(int, current_input.strip().split()))
                        if len(parts) != 3:
                            raise ValueError("Нужно 3 числа (0–1000) или HEX")
                        r, g, b = parts
                        hex_color_str = rgb1000_to_hex(r, g, b)
                        # Для RGB показываем HEX значение
                        message = f"RGB: {r} {g} {b} -> HEX: {hex_color_str}"

                    last_hex = hex_color_str
                    if not history or history[0] != hex_color_str:
                        history.insert(0, hex_color_str)
                    # урезаем историю
                    history = history[:HISTORY_MAX]
                    # сбрасываем навигацию и подстраиваем view чтобы показать первый элемент
                    history_index = None
                    history_view_start = 0
                    message_attr = curses.color_pair(3)
                    draw_color_panel(hex_color_str)
                except Exception as e:
                    message = f"Ошибка: {e}"
                    message_attr = curses.color_pair(2)
                finally:
                    current_input = ""

            # Backspace
            elif key in (curses.KEY_BACKSPACE, 127, 8):
                current_input = current_input[:-1]
                history_index = None
                message = ""
                message_attr = curses.color_pair(1)

            # Навигация по истории стрелками
            elif key == curses.KEY_DOWN:
                if history:
                    if history_index is None:
                        history_index = 0
                    else:
                        history_index = min(len(history) - 1, history_index + 1)
                    # подставляем в input
                    current_input = history[history_index]
                    # подстраиваем вид, чтобы выбранный был видим
                    if history_index < history_view_start:
                        history_view_start = history_index
                    if history_index >= history_view_start + available_lines:
                        history_view_start = history_index - available_lines + 1
                    # обновляем правую панель цвета
                    draw_color_panel(history[history_index])

            elif key == curses.KEY_UP:
                if history:
                    if history_index is None:
                        # ничего
                        pass
                    else:
                        history_index = history_index - 1
                        if history_index < 0:
                            history_index = None
                            current_input = ""
                            # очищаем правую панель цвета
                            draw_color_panel(None)
                        else:
                            current_input = history[history_index]
                            if history_index < history_view_start:
                                history_view_start = history_index
                            if history_index >= history_view_start + available_lines:
                                history_view_start = history_index - available_lines + 1
                            # обновляем правую панель цвета
                            draw_color_panel(history[history_index])

            # PageUp / PageDown для постраничного скролла истории
            elif key in (curses.KEY_PPAGE, curses.KEY_NPAGE):
                # SWAP_PAGE_KEYS == True  -> KEY_PPAGE behaves like PageDown (вперёд по истории к более старым),
                #                           KEY_NPAGE behaves как PageUp (к более новым).
                is_ppage = (key == curses.KEY_PPAGE)
                # направление: +1 -> движение к более старым (увеличение view_start), -1 -> к новым (уменьшение)
                if SWAP_PAGE_KEYS:
                    # swap semantics
                    if is_ppage:
                        direction = 1
                    else:
                        direction = -1
                else:
                    # стандарт: PageUp -> к новым (direction = -1), PageDown -> к старым (direction = +1)
                    if is_ppage:
                        direction = -1
                    else:
                        direction = 1

                # смещение на одну страницу
                step = available_lines if available_lines > 0 else 1
                new_start = history_view_start + direction * step
                # ограничение
                new_start = max(0, min(new_start, max(0, len(history) - available_lines)))
                history_view_start = new_start
                # при скролле снимаем текущий выбор (но можно оставить — решаем снять)
                #history_index = None
                
                # Если есть выбранный элемент, обновляем правую панель цвета
                if history_index is not None and 0 <= history_index < len(history):
                    draw_color_panel(history[history_index])

            # Клавиши управления
            elif key in (ord('c'),):
                to_copy = None
                if last_hex:
                    to_copy = last_hex
                else:
                    if current_input.strip().startswith("#"):
                        to_copy = current_input.strip()
                if to_copy:
                    if CLIP_AVAILABLE:
                        try:
                            pyperclip.copy(to_copy)
                            message = f"Скопировано: {to_copy}"
                            message_attr = curses.color_pair(3)
                        except Exception as e:
                            message = f"Ошибка копирования: {e}"
                            message_attr = curses.color_pair(2)
                    else:
                        message = "pyperclip не установлен — установить: pip install pyperclip"
                        message_attr = curses.color_pair(2)
                else:
                    message = "Нет HEX для копирования"
                    message_attr = curses.color_pair(2)

            elif key == ord('s'):  # сохранить историю в файл
                ok, msg = save_history_to_file(history, HISTORY_FILENAME)
                message = msg
                message_attr = curses.color_pair(3) if ok else curses.color_pair(2)

            elif key == ord('l'):  # загрузить историю из файла
                loaded, msg = load_history_from_file(HISTORY_FILENAME)
                if loaded:
                    history = loaded[:HISTORY_MAX]
                    history_index = None
                    history_view_start = 0
                    message = msg
                    message_attr = curses.color_pair(3)
                    # Если есть элементы в истории, показываем цвет первого элемента
                    if history:
                        draw_color_panel(history[0])
                    else:
                        # Если история пуста, очищаем правую панель
                        draw_color_panel(None)
                else:
                    message = msg
                    message_attr = curses.color_pair(2)

            elif key == ord('C'):  # очистить историю (Shift+C)
                history = []
                history_index = None
                history_view_start = 0
                message = "История очищена"
                message_attr = curses.color_pair(3)
                # Очищаем правую панель цвета
                draw_color_panel(None)

            # Печатные символы
            else:
                if 32 <= key <= 126:
                    current_input += chr(key)
                    history_index = None
                    message = ""
                    message_attr = curses.color_pair(1)

        except Exception as e:
            message = f"Global error: {e}"
            message_attr = curses.color_pair(2)
            current_input = ""

    # завершающие настройки
    curses.curs_set(1)
    stdscr.keypad(False)
    stdscr.nodelay(False)

if __name__ == "__main__":
    curses.wrapper(main)
