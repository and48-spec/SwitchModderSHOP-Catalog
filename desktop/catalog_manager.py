"""SwitchModderSHOP Catalog Manager — Windows desktop interface."""
import json
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

from catalog_manager_core import (
    DATA_PATHS, REPO, TYPES, addon_key, atomic_write, backup_local, data_dir,
    get_inputs, get_public_catalog, json_text, key_for, normalize_addon,
    normalize_game, publish, read_json, validate, self_test,
)

GAME_FIELDS = [
    ("title", "Titolo"),
    ("title_id", "Title ID (16 caratteri esadecimali)"),
    ("version", "Versione"),
    ("description", "Descrizione"),
    ("cover", "URL copertina"),
    ("url", "URL contenuto autorizzato"),
    ("magnet", "Magnet del contenuto autorizzato"),
]
ADDON_FIELDS = [
    ("title", "Nome contenuto aggiuntivo"),
    ("parent_title_id", "Title ID del gioco principale"),
    ("content_type", "Tipo di contenuto"),
    ("title_id", "Title ID del DLC/aggiornamento (facoltativo)"),
    ("language", "Lingua (es. it)"),
    ("version", "Versione"),
    ("description", "Descrizione"),
    ("cover", "URL copertina"),
    ("url", "URL contenuto autorizzato"),
]


class Editor(tk.Toplevel):
    def __init__(self, master, kind, source, save_callback):
        super().__init__(master)
        self.title("Modifica gioco" if kind == "game" else "Modifica contenuto aggiuntivo")
        self.geometry("780x660")
        self.minsize(600, 500)
        self.transient(master)
        self.grab_set()
        self.kind = kind
        self.source = source
        self.save_callback = save_callback
        self.inputs = {}
        self.columnconfigure(1, weight=1)
        fields = GAME_FIELDS if kind == "game" else ADDON_FIELDS
        for i, (key, label) in enumerate(fields):
            ttk.Label(self, text=label).grid(row=i, column=0, sticky="nw", padx=14, pady=9)
            value = source.get(key, "")
            if key == "description":
                field = tk.Text(self, height=4, wrap="word")
                field.insert("1.0", str(value))
            elif key == "content_type":
                field = ttk.Combobox(self, values=TYPES, state="readonly")
                field.set(value if value in TYPES else "language")
            else:
                field = ttk.Entry(self, width=66)
                field.insert(0, str(value))
            field.grid(row=i, column=1, sticky="ew", padx=(4, 16), pady=5)
            self.inputs[key] = field
        help_text = ("Modificare un gioco originale crea una personalizzazione; "
                     "il catalogo a monte non viene alterato."
                     if kind == "game" else
                     "Il contenuto viene collegato al gioco principale dal parent Title ID.")
        ttk.Label(self, text=help_text, wraplength=690).grid(
            row=len(fields), column=0, columnspan=2, sticky="w", padx=14, pady=12)
        actions = ttk.Frame(self)
        actions.grid(row=len(fields)+1, column=0, columnspan=2, sticky="e", padx=16, pady=12)
        ttk.Button(actions, text="Annulla", command=self.destroy).pack(side="right", padx=6)
        ttk.Button(actions, text="Salva", command=self.save).pack(side="right", padx=6)
        self.bind("<Escape>", lambda _event: self.destroy())

    def save(self):
        updated = dict(self.source)
        for key, widget in self.inputs.items():
            text = (widget.get("1.0", "end-1c") if isinstance(widget, tk.Text)
                    else widget.get()).strip()
            if text:
                updated[key] = text
            else:
                updated.pop(key, None)
        try:
            updated = normalize_game(updated) if self.kind == "game" else normalize_addon(updated)
            self.save_callback(updated)
        except (ValueError, KeyError) as exc:
            messagebox.showerror("Dati non validi", str(exc), parent=self)
            return
        self.destroy()


class CatalogManager(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SwitchModderSHOP — Catalog Manager Windows")
        self.geometry("1180x760")
        self.minsize(900, 620)
        self.folder = data_dir()
        self.folder.mkdir(parents=True, exist_ok=True)
        self.token = tk.StringVar()
        self.search_games = tk.StringVar()
        self.search_addons = tk.StringVar()
        self.status = tk.StringVar(value="Pronto. Carica i dati da GitHub oppure lavora offline.")
        self.games = read_json(self.folder / "custom_games.json")
        self.addons = read_json(self.folder / "addons.json")
        self.loaded_games = None
        self.loaded_addons = None
        self.public_games = []
        self.remote_loaded = False
        self.dirty = False
        self.last_game_id = ""
        self.visible_game_rows = {}
        self.visible_addon_rows = {}
        self.busy = False
        self._build()
        self.refresh_tables()
        self.protocol("WM_DELETE_WINDOW", self.close)

    def _build(self):
        outer = ttk.Frame(self, padding=12)
        outer.pack(fill="both", expand=True)
        top = ttk.Frame(outer)
        top.pack(fill="x", pady=(0, 10))
        ttk.Label(top, text="SwitchModderSHOP Catalog Manager",
                  font=("Segoe UI", 17, "bold")).pack(side="left", padx=(0, 20))
        ttk.Label(top, text="GitHub token:").pack(side="left")
        ttk.Entry(top, textvariable=self.token, width=29, show="*").pack(side="left", padx=6)
        ttk.Button(top, text="Carica da GitHub", command=self.load_github).pack(side="left", padx=3)
        ttk.Button(top, text="Salva copia locale", command=self.save_local).pack(side="left", padx=3)
        ttk.Button(top, text="Pubblica modifiche", command=self.publish_github).pack(side="right")
        ttk.Label(outer, text="Repository: " + REPO + "   |   Le modifiche pubblicate attivano automaticamente GitHub Actions.",
                  foreground="#526579").pack(fill="x", pady=(0, 10))
        self.tabs = ttk.Notebook(outer)
        self.tabs.pack(fill="both", expand=True)
        self.games_tab = ttk.Frame(self.tabs, padding=8)
        self.addons_tab = ttk.Frame(self.tabs, padding=8)
        self.info_tab = ttk.Frame(self.tabs, padding=16)
        self.tabs.add(self.games_tab, text="Giochi")
        self.tabs.add(self.addons_tab, text="DLC, traduzioni e aggiornamenti")
        self.tabs.add(self.info_tab, text="Sincronizzazione e backup")
        self.game_tree = self._build_table(self.games_tab, self.search_games, "game")
        self.addon_tree = self._build_table(self.addons_tab, self.search_addons, "addon")
        self.search_games.trace_add("write", lambda *_: self.refresh_games())
        self.search_addons.trace_add("write", lambda *_: self.refresh_addons())
        self.game_tree.bind("<<TreeviewSelect>>", self.game_selected)
        ttk.Label(self.info_tab,
                  text="Come funziona", font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(5, 16))
        info = (
            "1. Carica il catalogo originale e i file di personalizzazione dal repository.\n\n"
            "2. Cerca un gioco per nome o Title ID. Modificalo oppure aggiungi un nuovo titolo.\n\n"
            "3. Crea DLC, traduzioni o aggiornamenti specificando il Title ID del gioco principale.\n\n"
            "4. Salva una copia locale oppure pubblica direttamente su GitHub.\n\n"
            "5. GitHub Actions rigenera automaticamente generated/catalog.json e generated/addons.json.\n\n"
            "Il catalogo upstream non viene mai sovrascritto. Ogni modifica pubblicata "
            "è ripristinabile dalla cronologia Git.\n\n"
            "ATTENZIONE: generated/addons.json non è ancora visualizzato nella Switch. "
            "Per mostrare DLC e pacchetti lingua nella console servirà un aggiornamento "
            "separato della UI NRO.\n\n"
            "I file da pubblicare sono soltanto data/custom_games.json e data/addons.json.\n"
            "Il token non viene salvato in nessun file dal programma.\n"
            "Per pubblicare serve un fine-grained PAT GitHub con Contents: Read and write "
            "limitatamente al repository SwitchModderSHOP-Catalog."
        )
        ttk.Label(self.info_tab, text=info, wraplength=900, justify="left").pack(anchor="w")
        ttk.Button(self.info_tab, text="Apri cartella locale", command=self.open_folder).pack(anchor="w", pady=22)
        ttk.Separator(outer, orient="horizontal").pack(fill="x", pady=(9, 6))
        self.status_label = ttk.Label(outer, textvariable=self.status, wraplength=1100)
        self.status_label.pack(fill="x")

    def _build_table(self, frame, search_var, kind):
        actions = ttk.Frame(frame)
        actions.pack(fill="x", pady=(0, 8))
        ttk.Label(actions, text="Cerca titolo o Title ID:").pack(side="left")
        ttk.Entry(actions, textvariable=search_var, width=35).pack(side="left", padx=7)
        ttk.Button(actions, text="Nuovo", command=lambda: self.edit(kind, True)).pack(side="right", padx=4)
        ttk.Button(actions, text="Modifica selezionato", command=lambda: self.edit(kind, False)).pack(side="right", padx=4)
        ttk.Button(actions, text="Elimina personalizzazione",
                   command=lambda: self.delete(kind)).pack(side="right", padx=4)
        headers = ("title", "id", "extra")
        tree = ttk.Treeview(frame, columns=headers, show="headings", selectmode="browse")
        tree.heading("title", text="Gioco" if kind == "game" else "Contenuto")
        tree.heading("id", text="Title ID" if kind == "game" else "Gioco principale")
        tree.heading("extra", text="Origine" if kind == "game" else "Tipo")
        tree.column("title", width=490)
        tree.column("id", width=220)
        tree.column("extra", width=180)
        scroller = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroller.set)
        scroller.pack(side="right", fill="y")
        tree.pack(side="left", fill="both", expand=True)
        tree.bind("<Double-1>", lambda _event: self.edit(kind, False))
        return tree

    def refresh_tables(self):
        self.refresh_games()
        self.refresh_addons()
        label = ("NON SALVATO — " if self.dirty else "") + (
            "Personalizzazioni: " + str(len(self.games)) +
            " giochi; " + str(len(self.addons)) + " add-on"
            + ("; catalogo caricato: " + str(len(self.public_games)) if self.public_games else "")
        )
        self.status.set(label)

    def refresh_games(self):
        tree = self.game_tree
        tree.delete(*tree.get_children())
        custom_map = {key_for(x): x for x in self.games}
        merged = {}
        for original in self.public_games:
            if not isinstance(original, dict):
                continue
            try:
                key = key_for(original)
            except ValueError:
                continue
            if key not in merged:
                merged[key] = original
        for key, local in custom_map.items():
            merged[key] = {**merged.get(key, {}), **local}
        query = self.search_games.get().strip().casefold()
        rows = []
        for key, game in merged.items():
            title = str(game.get("title") or game.get("name") or "").strip()
            ident = str(game.get("title_id") or game.get("titleId") or "")
            if query and query not in title.casefold() and query not in ident.casefold():
                continue
            rows.append((title.casefold(), key, title, ident, game, key in custom_map))
        rows.sort()
        self.visible_game_rows = {}
        for i, (_sort, key, title, ident, record, is_custom) in enumerate(rows[:1500]):
            iid = str(i)
            tree.insert("", "end", iid=iid,
                        values=(title or "(senza titolo)", ident, "Personalizzato" if is_custom else "Originale"))
            self.visible_game_rows[iid] = (key, record, is_custom)

    def refresh_addons(self):
        tree = self.addon_tree
        tree.delete(*tree.get_children())
        query = self.search_addons.get().strip().casefold()
        self.visible_addon_rows = {}
        rows = sorted(enumerate(self.addons), key=lambda x: x[1].get("title", "").casefold())
        for original_index, addon in rows:
            title = str(addon.get("title") or "")
            parent = str(addon.get("parent_title_id") or "")
            if query and query not in title.casefold() and query not in parent.casefold():
                continue
            iid = str(original_index)
            tree.insert("", "end", iid=iid,
                        values=(title, parent, addon.get("content_type", "")))
            self.visible_addon_rows[iid] = original_index

    def game_selected(self, _event):
        selected = self.game_tree.selection()
        if selected:
            game = self.visible_game_rows[selected[0]][1]
            self.last_game_id = str(game.get("title_id") or game.get("titleId") or "")

    def edit(self, kind, is_new):
        if kind == "game":
            selection = self.game_tree.selection()
            if not is_new and not selection:
                messagebox.showinfo("Selezione", "Seleziona prima un gioco.")
                return
            old_key, record, custom = (
                ("", {}, False) if is_new else self.visible_game_rows[selection[0]])
            if not is_new and not custom and not (record.get("title_id") or record.get("titleId")):
                messagebox.showwarning("Title ID mancante",
                    "Per sovrascrivere senza duplicare un titolo upstream serve un Title ID.")
                return
            initial = {} if is_new else dict(record)
            def save_game(result):
                try:
                    proposed = [x for x in self.games if is_new or key_for(x) != old_key]
                    proposed.append(result)
                    validate(proposed, self.addons)
                except ValueError as exc:
                    raise ValueError(str(exc))
                self.games = proposed
                self.dirty = True
                self.refresh_tables()
            Editor(self, "game", initial, save_game)
        else:
            selection = self.addon_tree.selection()
            if not is_new and not selection:
                messagebox.showinfo("Selezione", "Seleziona prima un contenuto aggiuntivo.")
                return
            index = None if is_new else self.visible_addon_rows[selection[0]]
            initial = {"parent_title_id": self.last_game_id, "content_type": "language"} if is_new else dict(self.addons[index])
            def save_addon(result):
                proposed = list(self.addons)
                if index is None:
                    proposed.append(result)
                else:
                    proposed[index] = result
                validate(self.games, proposed)
                self.addons = proposed
                self.dirty = True
                self.refresh_tables()
            Editor(self, "addon", initial, save_addon)

    def delete(self, kind):
        if kind == "game":
            selected = self.game_tree.selection()
            if not selected:
                return
            key, _record, is_custom = self.visible_game_rows[selected[0]]
            if not is_custom:
                messagebox.showinfo("Gioco originale",
                    "Questo gioco proviene dal catalogo upstream. Non può essere eliminato "
                    "con questo comando; puoi soltanto rimuovere personalizzazioni locali.")
                return
            if not messagebox.askyesno("Conferma", "Eliminare la personalizzazione di questo gioco?"):
                return
            self.games = [x for x in self.games if key_for(x) != key]
        else:
            selected = self.addon_tree.selection()
            if not selected:
                return
            index = self.visible_addon_rows[selected[0]]
            if not messagebox.askyesno("Conferma", "Eliminare questo componente aggiuntivo?"):
                return
            self.addons.pop(index)
        self.dirty = True
        self.refresh_tables()

    def save_local(self):
        try:
            games, addons = validate(self.games, self.addons)
            folder = self.folder
            originals = {path: read_json(folder / Path(path).name)
                         for path in DATA_PATHS if (folder / Path(path).name).exists()}
            if originals:
                backup_local(folder, originals)
            atomic_write(folder / "custom_games.json", json_text(games))
            atomic_write(folder / "addons.json", json_text(addons))
            self.status.set("Copie locali salvate in: " + str(folder))
        except (OSError, ValueError) as exc:
            messagebox.showerror("Salvataggio non riuscito", str(exc))

    def _background(self, job, on_success, label):
        if self.busy:
            messagebox.showinfo("Operazione in corso", "Completa prima l'operazione corrente.")
            return
        self.busy = True
        self.status.set(label)
        def worker():
            try:
                result = job()
            except Exception as exc:
                message = str(exc)
                self.after(0, lambda: self._on_error(message))
            else:
                self.after(0, lambda: self._done(on_success, result))
        threading.Thread(target=worker, daemon=True).start()

    def _on_error(self, message):
        self.busy = False
        self.status.set("Errore: " + message)
        messagebox.showerror("Operazione non riuscita", message)

    def _done(self, callback, result):
        self.busy = False
        callback(result)

    def load_github(self):
        if self.dirty and not messagebox.askyesno("Modifiche locali",
            "Ricaricare GitHub sostituendo le modifiche non pubblicate? "
            "Salva prima una copia locale se vuoi conservarle."):
            return
        token = self.token.get().strip()
        def job():
            games, addons = get_inputs(token)
            try:
                upstream = get_public_catalog()
                note = ""
            except Exception as exc:
                upstream = []
                note = str(exc)
            return games, addons, upstream, note
        def done(result):
            self.games, self.addons, self.public_games, note = result
            self.loaded_games = json.loads(json_text(self.games))
            self.loaded_addons = json.loads(json_text(self.addons))
            self.remote_loaded = True
            self.dirty = False
            self.save_local()
            self.refresh_tables()
            self.status.set("Dati GitHub caricati. " +
                (("Elenco upstream non disponibile: " + note) if note else
                 str(len(self.public_games)) + " giochi consultabili."))
        self._background(job, done, "Download del catalogo in corso...")

    def publish_github(self):
        if not self.remote_loaded:
            messagebox.showwarning("Carica GitHub",
                    "Prima della pubblicazione carica i dati dal repository per rilevare conflitti.")
            return
        if not self.token.get().strip():
            messagebox.showwarning("Token mancante", "Inserisci il token GitHub per pubblicare.")
            return
        if not messagebox.askyesno("Pubblicazione",
                "Pubblicare entrambe le liste su GitHub? Il workflow Update catalog "
                "rigenererà il catalogo visibile alle console."):
            return
        self.save_local()
        games, addons = validate(self.games, self.addons)
        token = self.token.get().strip()
        before_games = self.loaded_games
        before_addons = self.loaded_addons
        def job():
            return publish(games, addons, before_games, before_addons, token)
        def done(sha):
            self.loaded_games = json.loads(json_text(games))
            self.loaded_addons = json.loads(json_text(addons))
            self.dirty = False
            self.refresh_tables()
            self.status.set("Pubblicazione completata: " + sha[:12] +
                             ". GitHub Actions sta aggiornando il catalogo.")
            messagebox.showinfo("Pubblicazione completata",
                "Modifiche inviate in un unico commit. Il workflow GitHub "
                "aggiornerà il catalogo automaticamente.\nCommit: " + sha[:12])
        self._background(job, done, "Pubblicazione GitHub e verifica conflitti...")

    def open_folder(self):
        import os
        import subprocess
        self.folder.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            os.startfile(str(self.folder))
        else:
            subprocess.Popen(["xdg-open", str(self.folder)])

    def close(self):
        if self.dirty and not messagebox.askyesno("Modifiche non salvate",
                "Ci sono modifiche non pubblicate. Uscire senza salvarle?"):
            return
        self.destroy()


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        self_test()
    else:
        CatalogManager().mainloop()
