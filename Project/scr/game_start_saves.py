import json
import tkinter as tk
from tkinter import simpledialog, messagebox, scrolledtext
import os
from datetime import datetime
from typing import Dict, List, Optional, Any


# ==================== МОДЕЛЬ ДАННЫХ ====================

class GameState:
    #Состояние игры (сохранение)

    def __init__(self):
        self.current_node = "start"
        self.player_name = ""
        self.flags = {}
        self.choice_history = []
        self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict:
        #Преобразование в словарь для сохранения
        return {
            "current_node": self.current_node,
            "player_name": self.player_name,
            "flags": self.flags,
            "choice_history": self.choice_history,
            "timestamp": self.timestamp
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'GameState':
        #Создание из словаря (загрузка)
        state = cls()
        state.current_node = data.get("current_node", "start")
        state.player_name = data.get("player_name", "")
        state.flags = data.get("flags", {})
        state.choice_history = data.get("choice_history", [])
        state.timestamp = data.get("timestamp", datetime.now().isoformat())
        return state


class StoryNode:
    #Точка выбора (сцена)

    def __init__(self, node_id: str, data: Dict):
        self.id = node_id
        self.text = data.get("text", "")
        self.choices = data.get("choices", [])
        self.type = data.get("type", "default")

    def get_available_choices(self, mode: str = "default") -> List[Dict]:
        #Получение доступных вариантов выбора для данного режима
        if isinstance(self.choices, dict) and "variants" in self.choices:
            variants = self.choices["variants"]
            if mode in variants:
                return variants[mode]
            return variants.get("default", [])
        return self.choices if isinstance(self.choices, list) else []


# ==================== ДВИЖОК ИГРЫ ====================

class GameEngine:

    def __init__(self, story_file: str = "story.json"):
        self.story_file = story_file
        self.story: Dict[str, StoryNode] = {}
        self.state = GameState()
        self._mode = "default"
        self._load_story()

    def _load_story(self):

        try:
            with open(self.story_file, 'r', encoding='utf-8') as f:
                story_data = json.load(f)

            for node_id, node_data in story_data.items():
                self.story[node_id] = StoryNode(node_id, node_data)

        except FileNotFoundError:
            messagebox.showerror("Ошибка", f"Файл сценария '{self.story_file}' не найден!")
            raise
        except json.JSONDecodeError:
            messagebox.showerror("Ошибка", f"Файл сценария '{self.story_file}' повреждён!")
            raise

    def get_current_node(self) -> Optional[StoryNode]:
        #Получение текущего узла
        return self.story.get(self.state.current_node)

    def _update_mode(self):
        #Обновление кнопок выбора на основе флагов
        node_id = self.state.current_node

        if node_id == "corridor_cross":
            if self.state.flags.get("refused_journalist") and self.state.flags.get("close_seat_v1"):
                self._mode = "add_var1"
            elif self.state.flags.get("fire_alarm_cross2"):
                self._mode = "add_var2"
            else:
                self._mode = "default"
        elif node_id == "new_floor_cross":
            if self.state.flags.get("wait_stay_cross"):
                self._mode = "add_var1"
            else:
                self._mode = "default"
        else:
            self._mode = "default"

    def make_choice(self, choice_index: int) -> bool:
        """Обработка выбора игрока"""
        current_node = self.get_current_node()
        if not current_node:
            return False

        # Получаем доступные варианты с учетом режима
        self._update_mode()
        choices = current_node.get_available_choices(self._mode)

        if 0 <= choice_index < len(choices):
            choice = choices[choice_index]

            # Записываем в историю
            self.state.choice_history.append({
                "node": self.state.current_node,
                "choice_text": choice.get("text", ""),
                "timestamp": datetime.now().strftime("%H:%M:%S")
            })

            # Обработка действий
            if "action" in choice:
                self._handle_action(choice["action"])

            # Переход к следующей сцене
            if "next" in choice:
                next_scene = choice["next"]
                self._update_flags(next_scene)
                self.state.current_node = next_scene

            return True
        return False

    def _update_flags(self, next_scene: str):
        """Обновление флагов состояния при переходе"""
        # Обновляем флаги на основе перехода
        flag_updates = {
            "refuse": {"refused_journalist": True},
            "close_seat_v1": {"close_seat_v1": True},
            "wait_stay_cross": {"wait_stay_cross": True},
            "fire_alarm_cross2": {"fire_alarm_cross2": True},
        }

        if next_scene in flag_updates:
            self.state.flags.update(flag_updates[next_scene])

    def _handle_action(self, action: str):
        """Обработка специальных действий"""
        if action == "restart":
            self.restart_game()

    def jump_to_node(self, node_id: str) -> bool:
        """Переход к конкретному узлу (для навигации по истории)"""
        if node_id in self.story:
            # Находим позицию этого узла в истории
            for i, entry in enumerate(self.state.choice_history):
                if entry["node"] == node_id:
                    # Обрезаем историю
                    self.state.choice_history = self.state.choice_history[:i]
                    break

            self.state.current_node = node_id
            return True
        return False

    def restart_game(self):
        """Начать игру заново"""
        self.state = GameState()
        self._mode = "default"

    def is_game_over(self) -> bool:
        """Проверка, завершена ли игра"""
        current_node = self.get_current_node()
        return current_node and current_node.type in ["game_over", "final"]

    def ask_player_name(self, name: str):
        """Установить имя игрока"""
        self.state.player_name = name if name else "Player"


# ==================== СИСТЕМА СОХРАНЕНИЙ ====================

class SaveManager:
    """Управление сохранениями игры"""

    SAVE_FILE = "game_save.json"

    def __init__(self):
        self.saves_dir = "saves"
        if not os.path.exists(self.saves_dir):
            os.makedirs(self.saves_dir)

    def save_game(self, game_state: GameState, slot: int = 0) -> bool:
        """Сохранение игры в указанный слот"""
        try:
            save_path = os.path.join(self.saves_dir, f"save_{slot}.json")
            save_data = game_state.to_dict()
            save_data["slot"] = slot
            save_data["save_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2)

            # Также сохраняем в основной файл для автозагрузки
            with open(self.SAVE_FILE, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2)

            return True
        except Exception as e:
            print(f"Ошибка сохранения: {e}")
            return False

    def load_game(self, slot: int = 0) -> Optional[GameState]:
        """Загрузка игры из указанного слота"""
        try:
            save_path = os.path.join(self.saves_dir, f"save_{slot}.json")
            if os.path.exists(save_path):
                with open(save_path, 'r', encoding='utf-8') as f:
                    save_data = json.load(f)
                return GameState.from_dict(save_data)
            return None
        except Exception as e:
            print(f"Ошибка загрузки: {e}")
            return None

    def load_autosave(self) -> Optional[GameState]:
        """Загрузка автосохранения"""
        try:
            if os.path.exists(self.SAVE_FILE):
                with open(self.SAVE_FILE, 'r', encoding='utf-8') as f:
                    save_data = json.load(f)
                return GameState.from_dict(save_data)
            return None
        except Exception:
            return None

    def delete_save(self, slot: int) -> bool:
        """Удаление сохранения"""
        try:
            save_path = os.path.join(self.saves_dir, f"save_{slot}.json")
            if os.path.exists(save_path):
                os.remove(save_path)
                return True
        except Exception:
            pass
        return False

    def get_save_info(self, slot: int) -> Optional[Dict]:
        """Получение информации о сохранении"""
        try:
            save_path = os.path.join(self.saves_dir, f"save_{slot}.json")
            if os.path.exists(save_path):
                with open(save_path, 'r', encoding='utf-8') as f:
                    save_data = json.load(f)
                return {
                    "slot": slot,
                    "player_name": save_data.get("player_name", ""),
                    "current_node": save_data.get("current_node", "start"),
                    "save_time": save_data.get("save_time", ""),
                    "timestamp": save_data.get("timestamp", "")
                }
        except Exception:
            pass
        return None


# ==================== ГРАФИЧЕСКИЙ ИНТЕРФЕЙС ====================

class QuestGUI:
    """Графический интерфейс игры"""

    def __init__(self, root: tk.Tk, game_engine: GameEngine, save_manager: SaveManager):
        self.root = root
        self.engine = game_engine
        self.save_manager = save_manager

        self.setup_ui()
        self.setup_menu()
        self.refresh()

        # Автозагрузка при запуске
        self.auto_load()

    def setup_ui(self):
        """Настройка пользовательского интерфейса"""
        self.root.title("Text Horror Quest")
        self.root.geometry("900x700")
        self.root.minsize(800, 600)

        # Основной контейнер
        main_frame = tk.Frame(self.root)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Левая панель - текст истории
        left_frame = tk.Frame(main_frame)
        left_frame.pack(side="left", fill="both", expand=True)

        tk.Label(left_frame, text="История", font=("Arial", 12, "bold")).pack(anchor="w")

        self.text_widget = scrolledtext.ScrolledText(
            left_frame,
            wrap="word",
            font=("Arial", 11),
            height=20,
            bg="#1a1a1a",
            fg="#e0e0e0",
            insertbackground="#e0e0e0"
        )
        self.text_widget.pack(fill="both", expand=True, pady=(5, 10))
        self.text_widget.config(state="disabled")

        # Правая панель - управление
        right_frame = tk.Frame(main_frame, width=300)
        right_frame.pack(side="right", fill="y", padx=(10, 0))

        # Панель выбора
        choice_frame = tk.LabelFrame(right_frame, text="Выбор действия", font=("Arial", 10, "bold"))
        choice_frame.pack(fill="x", pady=(0, 10))

        self.choice_buttons_frame = tk.Frame(choice_frame)
        self.choice_buttons_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Панель истории выборов
        history_frame = tk.LabelFrame(right_frame, text="История выборов", font=("Arial", 10, "bold"))
        history_frame.pack(fill="both", expand=True)

        self.history_listbox = tk.Listbox(
            history_frame,
            font=("Arial", 9),
            height=15,
            selectmode="single"
        )
        self.history_listbox.pack(fill="both", expand=True, padx=10, pady=10)
        self.history_listbox.bind('<<ListboxSelect>>', self.on_history_select)

        # Панель состояния
        status_frame = tk.Frame(self.root)
        status_frame.pack(side="bottom", fill="x", padx=10, pady=(0, 10))

        self.status_label = tk.Label(
            status_frame,
            text="",
            font=("Arial", 9),
            anchor="w",
            bg="#f0f0f0",
            relief="sunken",
            padx=10,
            pady=5
        )
        self.status_label.pack(fill="x")

    def setup_menu(self):
        """Создание меню"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # Меню "Игра"
        game_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Игра", menu=game_menu)
        game_menu.add_command(label="Сохранить игру", command=self.save_game_dialog)
        game_menu.add_command(label="Загрузить игру", command=self.load_game_dialog)
        game_menu.add_separator()
        game_menu.add_command(label="Начать заново", command=self.confirm_restart)
        game_menu.add_separator()
        game_menu.add_command(label="Выход", command=self.root.quit)

        # Меню "Справка"
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Справка", menu=help_menu)
        help_menu.add_command(label="Правила игры", command=self.show_rules)
        help_menu.add_command(label="Об игре", command=self.show_about)

    def refresh(self):
        """Обновление интерфейса"""
        # Очистка предыдущих кнопок
        for widget in self.choice_buttons_frame.winfo_children():
            widget.destroy()

        # Получение текущего узла
        current_node = self.engine.get_current_node()
        if not current_node:
            return

        # Отображение текста сцены
        self.text_widget.config(state="normal")
        self.text_widget.delete("1.0", tk.END)

        # Форматирование текста
        text = current_node.text
        if self.engine.state.player_name:
            text = text.replace("{player_name}", self.engine.state.player_name)

        # Добавляем заголовок сцены
        scene_header = f"══════ {current_node.id} ══════\n\n"
        self.text_widget.insert("1.0", scene_header, "header")
        self.text_widget.insert("end", text + "\n\n", "text")

        # Настройка тегов для форматирования
        self.text_widget.tag_config("header",
                                    font=("Arial", 12, "bold"),
                                    foreground="#4a90e2")
        self.text_widget.tag_config("text",
                                    font=("Arial", 11),
                                    foreground="#e0e0e0")

        self.text_widget.config(state="disabled")

        # Определяем режим и получаем варианты выбора
        self.engine._update_mode()
        choices = current_node.get_available_choices(self.engine._mode)

        # Создание кнопок выбора
        if choices:
            for i, choice in enumerate(choices):
                btn_text = choice.get("text", f"Вариант {i + 1}")
                btn = tk.Button(
                    self.choice_buttons_frame,
                    text=btn_text,
                    command=lambda idx=i: self.on_choice_made(idx),
                    font=("Arial", 10),
                    bg="#4a90e2",
                    fg="white",
                    activebackground="#357ae8",
                    activeforeground="white",
                    relief="flat",
                    padx=20,
                    pady=10,
                    wraplength=250,
                    cursor="hand2"
                )
                btn.pack(fill="x", pady=5)
        else:
            # Если выбора нет - это конечная сцена
            label = tk.Label(
                self.choice_buttons_frame,
                text="Конец сцены",
                font=("Arial", 10, "italic"),
                fg="#888"
            )
            label.pack(pady=10)

            if current_node.type in ["game_over", "final"]:
                restart_btn = tk.Button(
                    self.choice_buttons_frame,
                    text="Начать заново",
                    command=self.confirm_restart,
                    font=("Arial", 10, "bold"),
                    bg="#e74c3c",
                    fg="white",
                    padx=30,
                    pady=10
                )
                restart_btn.pack(pady=10)

        # Обновление списка истории
        self.update_history_list()

        # Обновление статуса
        self.update_status()

    def update_history_list(self):
        """Обновление списка истории выборов"""
        self.history_listbox.delete(0, tk.END)

        for i, entry in enumerate(self.engine.state.choice_history):
            node_name = entry.get("node", "?")
            choice_text = entry.get("choice_text", "")
            time_str = entry.get("timestamp", "")

            # Форматируем для отображения
            display_text = f"{i + 1}. [{time_str}] {choice_text[:40]}..."
            self.history_listbox.insert(tk.END, display_text)

        # Прокручиваем к концу
        if self.history_listbox.size() > 0:
            self.history_listbox.see(tk.END)

    def update_status(self):
        """Обновление строки статуса"""
        current_node = self.engine.get_current_node()
        player_name = self.engine.state.player_name or "Неизвестный"
        flags_count = len(self.engine.state.flags)
        history_count = len(self.engine.state.choice_history)

        status_text = (
            f"Игрок: {player_name} | "
            f"Текущая сцена: {current_node.id if current_node else '?'} | "
            f"Флагов: {flags_count} | "
            f"Выборов: {history_count}"
        )

        self.status_label.config(text=status_text)

    def on_choice_made(self, choice_index: int):
        """Обработка выбора игрока"""
        # Проверяем, нужно ли запросить имя
        if self.engine.state.current_node == "introduction" and not self.engine.state.player_name:
            self.ask_player_name()
            return

        # Выполняем выбор
        if self.engine.make_choice(choice_index):
            # Автосохранение
            self.save_manager.save_game(self.engine.state)
            # Обновляем интерфейс
            self.refresh()

    def on_history_select(self, event):
        """Обработка выбора из истории"""
        selection = self.history_listbox.curselection()
        if selection:
            index = selection[0]
            if 0 <= index < len(self.engine.state.choice_history):
                # Получаем узел из истории
                entry = self.engine.state.choice_history[index]
                node_id = entry.get("node")

                # Запрашиваем подтверждение
                if messagebox.askyesno(
                        "Вернуться в прошлое",
                        f"Вернуться к сцене '{node_id}'?\n"
                        "Весь прогресс после этой точки будет потерян."
                ):
                    if self.engine.jump_to_node(node_id):
                        self.save_manager.save_game(self.engine.state)
                        self.refresh()

    def ask_player_name(self):
        """Запрос имени игрока"""
        name = simpledialog.askstring(
            "Ваше имя",
            "Как вас зовут?",
            parent=self.root,
            initialvalue=self.engine.state.player_name
        )

        if name is not None:  # Нажали OK
            self.engine.ask_player_name(name)
            # Продолжаем игру
            self.engine.make_choice(0)  # Переходим к следующей сцене
            self.save_manager.save_game(self.engine.state)
            self.refresh()

    def auto_load(self):
        """Автозагрузка при запуске"""
        saved_state = self.save_manager.load_autosave()
        if saved_state:
            response = messagebox.askyesno(
                "Продолжить?",
                f"Найдено сохранение от {saved_state.timestamp[:16]}. "
                f"Игрок: {saved_state.player_name or 'Неизвестный'}\n"
                f"Продолжить с этого момента?"
            )

            if response:
                self.engine.state = saved_state
                self.refresh()

    def save_game_dialog(self):
        """Диалог сохранения игры"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Сохранение игры")
        dialog.geometry("300x400")
        dialog.transient(self.root)
        dialog.grab_set()

        tk.Label(dialog, text="Выберите слот для сохранения:",
                 font=("Arial", 11, "bold")).pack(pady=10)

        # Слоты сохранения
        for slot in range(5):
            frame = tk.Frame(dialog)
            frame.pack(fill="x", padx=20, pady=5)

            save_info = self.save_manager.get_save_info(slot)

            if save_info:
                btn_text = f"Слот {slot}: {save_info.get('player_name', '')}"
                info_text = f"Сцена: {save_info.get('current_node', '')}, {save_info.get('save_time', '')}"

                btn = tk.Button(
                    frame,
                    text=btn_text,
                    command=lambda s=slot: self.do_save(s, dialog),
                    width=20,
                    anchor="w"
                )
                btn.pack(side="left")

                tk.Label(frame, text=info_text, font=("Arial", 8)).pack(side="left", padx=10)

                # Кнопка удаления
                del_btn = tk.Button(
                    frame,
                    text="×",
                    command=lambda s=slot: self.delete_save(s, dialog),
                    fg="red",
                    font=("Arial", 9, "bold"),
                    width=3
                )
                del_btn.pack(side="right")
            else:
                btn = tk.Button(
                    frame,
                    text=f"Слот {slot}: (пусто)",
                    command=lambda s=slot: self.do_save(s, dialog),
                    width=30,
                    anchor="w"
                )
                btn.pack()

        tk.Button(dialog, text="Отмена", command=dialog.destroy).pack(pady=10)

    def do_save(self, slot: int, dialog: tk.Toplevel):
        """Выполнение сохранения"""
        if self.save_manager.save_game(self.engine.state, slot):
            messagebox.showinfo("Успех", f"Игра сохранена в слот {slot}!")
            dialog.destroy()
            self.refresh()
        else:
            messagebox.showerror("Ошибка", "Не удалось сохранить игру!")

    def delete_save(self, slot: int, dialog: tk.Toplevel):
        """Удаление сохранения"""
        if messagebox.askyesno("Удаление", f"Удалить сохранение в слоте {slot}?"):
            if self.save_manager.delete_save(slot):
                dialog.destroy()
                self.save_game_dialog()

    def load_game_dialog(self):
        """Диалог загрузки игры"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Загрузка игры")
        dialog.geometry("300x400")
        dialog.transient(self.root)
        dialog.grab_set()

        tk.Label(dialog, text="Выберите слот для загрузки:",
                 font=("Arial", 11, "bold")).pack(pady=10)

        # Слоты сохранения
        for slot in range(5):
            save_info = self.save_manager.get_save_info(slot)

            if save_info:
                frame = tk.Frame(dialog)
                frame.pack(fill="x", padx=20, pady=5)

                btn_text = f"Слот {slot}: {save_info.get('player_name', '')}"
                info_text = f"Сцена: {save_info.get('current_node', '')}, {save_info.get('save_time', '')}"

                btn = tk.Button(
                    frame,
                    text=btn_text,
                    command=lambda s=slot: self.do_load(s, dialog),
                    width=20,
                    anchor="w"
                )
                btn.pack(side="left")

                tk.Label(frame, text=info_text, font=("Arial", 8)).pack(side="left", padx=10)

        if not any(self.save_manager.get_save_info(slot) for slot in range(5)):
            tk.Label(dialog, text="Нет сохраненных игр", fg="gray").pack(pady=20)

        tk.Button(dialog, text="Отмена", command=dialog.destroy).pack(pady=10)

    def do_load(self, slot: int, dialog: tk.Toplevel):
        """Выполнение загрузки"""
        saved_state = self.save_manager.load_game(slot)
        if saved_state:
            self.engine.state = saved_state
            dialog.destroy()
            self.refresh()
            messagebox.showinfo("Загрузка", f"Игра загружена из слота {slot}!")
        else:
            messagebox.showerror("Ошибка", "Не удалось загрузить игру!")

    def confirm_restart(self):
        """Подтверждение перезапуска игры"""
        if messagebox.askyesno(
                "Начать заново",
                "Вы уверены, что хотите начать игру заново?\n"
                "Текущий прогресс будет потерян."
        ):
            self.engine.restart_game()
            self.refresh()
            # Удаляем автосохранение
            if os.path.exists(SaveManager.SAVE_FILE):
                os.remove(SaveManager.SAVE_FILE)

    def show_rules(self):
        """Показать правила игры"""
        rules_text = """
        ПРАВИЛА ИГРЫ:

        1. Читайте текст истории и выбирайте действия с помощью кнопок.
        2. Ваши выборы влияют на развитие сюжета.
        3. Используйте меню для сохранения и загрузки игры.
        4. В любой момент можно вернуться к предыдущим выборам через историю.
        5. Игра автоматически сохраняется при каждом выборе.

        Управление:
        - Левая панель: текст истории
        - Правая верхняя панель: варианты выбора
        - Правая нижняя панель: история ваших выборов

        Чтобы вернуться к предыдущему выбору:
        1. Выберите пункт в списке истории
        2. Подтвердите возврат
        3. Игра продолжится с этого момента
        """

        messagebox.showinfo("Правила игры", rules_text)

    def show_about(self):
        """Показать информацию об игре"""
        about_text = """
        ТЕКСТОВЫЙ ХОРРОР-КВЕСТ

        Версия: 2.0
        Разработчик: Text Adventure Studio

        Игра представляет собой интерактивную историю
        с ветвящимся сюжетом и несколькими концовками.

        Особенности:
        - Система сохранения и загрузки
        - Возможность вернуться к любому выбору
        - Динамическое изменение вариантов выбора
        - Система флагов и состояний

        © 2024 Text Adventure Studio
        Все права защищены.
        """

        messagebox.showinfo("Об игре", about_text)


# ==================== ОСНОВНОЙ ЗАПУСК ====================

def main():
    """Основная функция запуска игры"""
    try:
        # Создаем корневое окно
        root = tk.Tk()

        # Создаем компоненты игры
        engine = GameEngine("story.json")
        save_manager = SaveManager()

        # Создаем интерфейс
        gui = QuestGUI(root, engine, save_manager)

        # Запускаем главный цикл
        root.mainloop()

    except Exception as e:
        print(f"Ошибка запуска игры: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()