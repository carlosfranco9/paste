from pathlib import Path


def test_installed_launcher_does_not_depend_on_current_directory():
    installer = (
        Path(__file__).resolve().parent.parent / "packaging" / "install.sh"
    ).read_text()

    assert 'APP_DIR="$DEST_DIR/lib/$APP_NAME"' in installer
    assert 'export PYTHONPATH="\\$APP_DIR' in installer
    assert 'cd "\\$APP_DIR"' in installer
    assert 'python3 -m src.main "\\$@"' in installer
    assert 'sudo cp -r "$SRC_DIR/resources" "$DEST_DIR/lib/$APP_NAME/resources"' in installer
    assert 'resources/icons/paste.png' in installer
