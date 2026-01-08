import json
import os
import tkinter as tk
from tkinter import simpledialog
from datetime import datetime


# ==================================================
# МОДЕЛИ СЮЖЕТА
# ==================================================

class Choice:
    def __init__(self, text, next_id):
        self.text = text
        self.next = next_id


class StoryNode:
    def __init__(self, node_id, text, choices, node_type="choice", input_key=None):
        self.id = node_id
        self.text = text
        self.choices = choices
        self.type = node_type
        self.input_key = input_key

    def is_end(self):
        return len(self.choices) == 0


def load_story(path):
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    nodes = {}
    for node_id, data in raw.items():
        nodes[node_id] = StoryNode(
            node_id=node_id,
            text=data["text"],
            choices=[
                Choice(c["text"], c["next"])
                for c in data.get("choices", [])
            ],
            node_type=data.get("type", "choice"),
            input_key=data.get("input_key")
        )
    return nodes


# ==================================================
# СОСТОЯНИЕ ИГРЫ
# ==================================================

class GameState:
    def __init__(self, nodes, start_id):
        self.nodes = nodes
        self.start_id = start_id
        self.variables = {}
        self.reset()

    def reset(self):
        self.current = self.nodes[self.start_id]
        self.history = []

    def make_choice(self, choice_index):
        choice = self.current.choices[choice_index]
        self.history.append((self.current.id, choice_index))
        self.current = self.nodes[choice.next]

    def restore_from_history(self, history):
        self.reset()
        for node_id, choice_index in history:
            self.current = self.nodes[node_id]
            self.make_choice(choice_index)

    def rollback_to(self, index):
        self.restore_from_history(self.history[:index])

    def is_finished(self):
        return self.current.is_end()


# ==================================================
# СОХРАНЕНИЕ
# ==================================================

class SaveManager:
    def __init__(self, player_name):
        os.makedirs("saves", exist_ok=True)
        self.path = f"saves/{player_name}.json"

    def save(self, game):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "variables": game.variables,
                    "history": game.history,
                    "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                },
                f,
                ensure_ascii=False,
                indent=2
            )

    def load(self):
        if not os.path.exists(self.path):
            return None
        with open(self.path, "r", encoding="utf-8") as f:
            return json.load(f)


# ==================================================
# GUI
# ==================================================

class QuestApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Текстовый квест")

        self.story = load_story("story.json")

        self.player_name = simpledialog.askstring(
            "Игрок", "Введите имя для сохранения:"
        ) or "Player"

        self.game = GameState(self.story, "start")
        self.save_manager = SaveManager(self.player_name)

        save = self.save_manager.load()
        if save:
            self.game.variables = save.get("variables", {})
            self.game.restore_from_history(save.get("history", []))

        self.build_ui()
        self.update_ui()

    # ---------------- UI ----------------

    def build_ui(self):
        self.main = tk.Frame(self.root)
        self.main.pack(fill="both", expand=True)

        self.left = tk.Frame(self.main)
        self.left.pack(side="left", fill="both", expand=True, padx=10)

        self.right = tk.Frame(self.main, width=260)

        self.text_label = tk.Label(
            self.left,
            wraplength=520,
            justify="left",
            font=("Arial", 12)
        )
        self.text_label.pack(pady=10)

        self.input_frame = tk.Frame(self.left)
        self.input_entry = tk.Entry(self.input_frame, font=("Arial", 12))
        self.input_entry.pack()

        self.choices_frame = tk.Frame(self.left)
        self.choices_frame.pack(pady=10)

        tk.Label(self.right, text="История решений").pack()
        self.history_list = tk.Listbox(self.right)
        self.history_list.pack(fill="y", expand=True)
        self.history_list.bind("<<ListboxSelect>>", self.on_history_select)

    # ---------------- LOGIC ----------------

    def update_ui(self):
        node = self.game.current

        # Текст с подстановкой переменных
        try:
            text = node.text.format(**self.game.variables)
        except KeyError:
            text = node.text

        self.text_label.config(text=text)

        # Очистка
        for w in self.choices_frame.winfo_children():
            w.destroy()
        self.input_frame.pack_forget()

        # Input-узел
        if node.type == "input":
            self.input_frame.pack(pady=10)
            self.input_entry.delete(0, tk.END)

        # Кнопки
        for i, choice in enumerate(node.choices):
            btn = tk.Button(
                self.choices_frame,
                text=choice.text,
                command=lambda i=i: self.on_choice(i)
            )
            btn.pack(fill="x", pady=4)

        # История только в концовке
        if self.game.is_finished():
            self.show_history()
        else:
            self.hide_history()

    def on_choice(self, index):
        node = self.game.current

        if node.type == "input" and node.input_key:
            value = self.input_entry.get().strip()
            if value:
                self.game.variables[node.input_key] = value

        self.game.make_choice(index)
        self.save_manager.save(self.game)
        self.update_ui()

    # ---------------- HISTORY ----------------

    def show_history(self):
        if not self.right.winfo_ismapped():
            self.right.pack(side="right", fill="y", padx=10)

        self.history_list.delete(0, tk.END)
        self.history_list.insert(tk.END, "0: Начало")

        for i, (node_id, choice_index) in enumerate(self.game.history, 1):
            node = self.story[node_id]
            choice = node.choices[choice_index]
            self.history_list.insert(
                tk.END, f"{i}: {choice.text}"
            )

    def hide_history(self):
        if self.right.winfo_ismapped():
            self.right.pack_forget()

    def on_history_select(self, event):
        if not self.history_list.curselection():
            return
        index = self.history_list.curselection()[0]
        self.game.rollback_to(index)
        self.save_manager.save(self.game)
        self.update_ui()


# ==================================================
# ЗАПУСК
# ==================================================

if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("920x520")
    QuestApp(root)
    root.mainloop()
