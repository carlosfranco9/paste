import os
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("XDG_SESSION_TYPE", "wayland")

import pytest
from PySide2.QtCore import QEventLoop, QTimer
from PySide2.QtWidgets import QApplication, QMessageBox, QPushButton

from src.database.models import ClipboardEntry
from src.ui.filter_bar import FilterBar
from src.ui.history_list import HistoryItemWidget, HistoryListWidget
from src.ui.main_window import MainWindow
from src.ui.search_bar import SearchBar


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app


def make_entries(prefix, count=3):
    return [
        ClipboardEntry(
            id=f"{prefix}-{index}",
            type="text",
            content=f"{prefix} item {index}",
            fingerprint=f"{prefix}-{index}",
            created_at="2026-07-14T00:00:00+00:00",
        )
        for index in range(count)
    ]


def test_replacing_entries_detaches_old_widgets_immediately(qt_app):
    history = HistoryListWidget()
    history.resize(500, 400)
    history.show()
    history.set_entries(make_entries("old"))
    qt_app.processEvents()
    old_widgets = list(history._items)

    history.set_entries(make_entries("new"))

    assert all(not widget.isVisible() for widget in old_widgets)
    assert all(widget.parent() is None for widget in old_widgets)
    assert all(history._layout.indexOf(widget) == -1 for widget in old_widgets)
    assert len(history._container.findChildren(HistoryItemWidget)) == 3
    assert history.updatesEnabled()
    history.close()


def test_cancel_pending_search_prevents_debounced_emit(qt_app):
    search = SearchBar()
    emitted = []
    search.search_requested.connect(emitted.append)

    search.setText("pending query")
    assert search._debounce_timer.isActive()
    search.cancel_pending_search()
    loop = QEventLoop()
    QTimer.singleShot(350, loop.quit)
    loop.exec_()

    assert emitted == []


def test_initial_history_load_happens_once_when_window_is_shown(
    qt_app, monkeypatch
):
    loads = []
    monkeypatch.setattr(
        "src.ui.main_window.get_recent_entries",
        lambda limit, entry_type=None: loads.append(limit) or [],
    )
    monkeypatch.setattr(
        "src.ui.main_window.count_entries", lambda entry_type=None: 0
    )

    window = MainWindow()
    assert loads == []

    window.show()
    qt_app.processEvents()

    assert loads == [100]
    window.hide()
    window.show()
    qt_app.processEvents()
    assert loads == [100]
    window.close()


def test_search_confirm_cancels_debounce_before_refreshing():
    calls = []
    first_item = SimpleNamespace(entry=SimpleNamespace(id="first"))
    window = SimpleNamespace(
        _search_bar=SimpleNamespace(
            cancel_pending_search=lambda: calls.append("cancel"),
            text=lambda: " query ",
        ),
        _list=SimpleNamespace(_items=[first_item]),
        _refresh_list=lambda query: calls.append(("refresh", query)) or [object()],
        _on_entry_clicked=lambda entry_id: calls.append(("click", entry_id)),
    )

    MainWindow._on_search_confirm(window)

    assert calls == ["cancel", ("refresh", "query"), ("click", "first")]


def test_empty_search_confirm_refreshes_without_selecting_an_entry():
    calls = []
    first_item = SimpleNamespace(entry=SimpleNamespace(id="first"))
    window = SimpleNamespace(
        _search_bar=SimpleNamespace(
            cancel_pending_search=lambda: calls.append("cancel"),
            text=lambda: "   ",
        ),
        _list=SimpleNamespace(_items=[first_item]),
        _refresh_list=lambda query: calls.append(("refresh", query)) or [object()],
        _on_entry_clicked=lambda entry_id: calls.append(("click", entry_id)),
    )

    MainWindow._on_search_confirm(window)

    assert calls == ["cancel", ("refresh", "")]


def test_new_entry_refreshes_active_search_instead_of_polluting_results():
    entry = make_entries("new", count=1)[0]
    calls = []
    window = SimpleNamespace(
        _skip_fingerprint=None,
        _recent_hashes=set(),
        _clip_processor=SimpleNamespace(process=lambda data: entry),
        _search_bar=SimpleNamespace(text=lambda: "needle"),
        _list=SimpleNamespace(
            append_entry=lambda value: calls.append(("append", value.id))
        ),
        _refresh_list=lambda query: calls.append(("refresh", query)),
        _update_count=lambda: calls.append("count"),
    )
    data = SimpleNamespace(fingerprint_data=b"new clipboard data")

    MainWindow.add_clipboard_data(window, data)

    assert calls == [("refresh", "needle")]


def test_filter_bar_exposes_all_url_and_image_filters(qt_app):
    filters = FilterBar()
    selected = []
    filters.filter_changed.connect(selected.append)

    filters._buttons["link"].click()
    filters._buttons["image"].click()
    filters._buttons["all"].click()

    assert selected == ["link", "image", "all"]
    assert filters.current_filter == "all"


def test_refresh_applies_type_filter_to_database_query(monkeypatch):
    calls = []
    window = SimpleNamespace(
        _active_filter="link",
        _list=SimpleNamespace(set_entries=lambda entries: calls.append(entries)),
        _update_count=lambda entry_type: calls.append(("count", entry_type)),
    )
    monkeypatch.setattr(
        "src.ui.main_window.get_recent_entries",
        lambda limit, entry_type: calls.append((limit, entry_type)) or [],
    )

    MainWindow._refresh_list(window)

    assert calls == [(100, "link"), [], ("count", "link")]
    assert window._list_loaded
    assert not window._list_dirty


def test_history_item_delete_button_emits_entry_id(qt_app):
    entry = make_entries("delete", count=1)[0]
    widget = HistoryItemWidget(entry)
    deleted = []
    widget.delete_requested.connect(deleted.append)

    widget.findChild(QPushButton, "delete_button").click()

    assert deleted == [entry.id]


def test_deleting_entry_refreshes_current_view(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "src.ui.main_window.delete_entry",
        lambda entry_id: calls.append(("delete", entry_id)) or True,
    )
    window = SimpleNamespace(
        _recent_hashes={"hash"},
        _preview=SimpleNamespace(
            current_entry_id="entry-1",
            clear=lambda: calls.append("preview-clear"),
        ),
        _list_dirty=False,
        _search_bar=SimpleNamespace(text=lambda: "query"),
        _refresh_list=lambda query: calls.append(("refresh", query)),
    )

    MainWindow._delete_entry(window, "entry-1")

    assert calls == [
        ("delete", "entry-1"),
        "preview-clear",
        ("refresh", "query"),
    ]
    assert window._recent_hashes == set()


def test_clear_history_requires_confirmation_and_refreshes(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "src.ui.main_window.QMessageBox.question",
        lambda *args: QMessageBox.Yes,
    )
    monkeypatch.setattr(
        "src.ui.main_window.clear_entries",
        lambda: calls.append("clear-db") or 3,
    )
    window = SimpleNamespace(
        _recent_hashes={"hash"},
        _preview=SimpleNamespace(clear=lambda: calls.append("preview-clear")),
        _list_dirty=False,
        _search_bar=SimpleNamespace(text=lambda: ""),
        _refresh_list=lambda query: calls.append(("refresh", query)),
    )

    MainWindow._clear_history(window)

    assert calls == ["clear-db", "preview-clear", ("refresh", "")]
    assert window._recent_hashes == set()


def test_rapid_duplicate_show_requests_are_coalesced(qt_app):
    calls = []
    window = SimpleNamespace(
        _last_toggle_at=0.0,
        _show_pending=False,
        isVisible=lambda: False,
        _show_window=lambda source: calls.append(source),
    )

    MainWindow.toggle_visibility(window, "hotkey")
    MainWindow.toggle_visibility(window, "hotkey")
    qt_app.processEvents()

    assert calls == ["hotkey"]
