"""Qt callbacks must not abort a windowed executable without stderr."""

import unittest
from unittest.mock import patch
from PyQt6.QtCore import QtMsgType
from src.gui import app as gui_app


class TestGuiMessageHandler(unittest.TestCase):
    def emit_warning(self, stream):
        with patch('PyQt6.QtCore.qInstallMessageHandler', return_value=None) as install:
            gui_app._install_qt_message_filter()
        handler = install.call_args.args[0]
        with patch.object(gui_app.sys, 'stderr', stream):
            handler(QtMsgType.QtWarningMsg, None, 'DirectWrite: Fixedsys font warning')

    def test_windowed_executable_without_stderr(self):
        self.emit_warning(None)

    def test_closed_stderr(self):
        from io import StringIO
        stream = StringIO()
        stream.close()
        self.emit_warning(stream)

    def test_console_warning_is_preserved(self):
        from io import StringIO
        stream = StringIO()
        self.emit_warning(stream)
        self.assertIn('Fixedsys font warning', stream.getvalue())
