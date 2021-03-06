# -*- coding: utf-8 -*-
#  Photini - a simple photo metadata editor.
#  http://github.com/jim-easterbrook/Photini
#  Copyright (C) 2012-16  Jim Easterbrook  jim@jim-easterbrook.me.uk
#
#  This program is free software: you can redistribute it and/or
#  modify it under the terms of the GNU General Public License as
#  published by the Free Software Foundation, either version 3 of the
#  License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#  General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see
#  <http://www.gnu.org/licenses/>.

from __future__ import unicode_literals

import logging
import logging.handlers
import os
import sys

from photini.pyqt import qt_version_info, QtCore, QtWidgets

class OutputInterceptor(object):
    def __init__(self, name, stream):
        self.logger = logging.getLogger(name)
        self.stream = stream
        self.flush = self.stream.flush
        self.fileno = self.stream.fileno

    def write(self, msg):
        self.stream.write(msg)
        msg = msg.strip()
        if 'WARNING' in msg:
            self.logger.warning(msg)
        elif msg:
            self.logger.info(msg)


class StreamProxy(QtCore.QObject):
    # only the GUI thread is allowed to write messages in the
    # LoggerWindow, so this class acts as a proxy, passing messages
    # over Qt signal/slot for thread safety
    flush_text = QtCore.pyqtSignal()
    write_text = QtCore.pyqtSignal(str)

    def write(self, msg):
        msg = msg.strip()
        if msg:
            self.write_text.emit(msg)

    def flush(self):
        self.flush_text.emit()


class LoggerFilter(object):
    def __init__(self, verbosity):
        self.threshold = min(logging.ERROR, (6 - verbosity) * 10)

    def filter(self, record):
        # reduce severity of non-Photini messages
        if (record.levelno < self.threshold and
                not record.name.startswith('photini')):
            return 0
        return 1


class LoggerWindow(QtWidgets.QWidget):
    def __init__(self, verbose, *arg, **kw):
        super(LoggerWindow, self).__init__(*arg, **kw)
        QtWidgets.QApplication.instance().aboutToQuit.connect(self.shutdown)
        self.setWindowTitle(self.tr("Photini error logging"))
        self.setLayout(QtWidgets.QGridLayout())
        self.layout().setRowStretch(0, 1)
        self.layout().setColumnStretch(0, 1)
        # main dialog area
        self.text = QtWidgets.QTextEdit()
        self.text.setReadOnly(True)
        self.text.setMinimumWidth(500)
        self.layout().addWidget(self.text, 0, 0, 1, 3)
        # save button
        save_button = QtWidgets.QPushButton(self.tr('Save'))
        save_button.clicked.connect(self.save)
        self.layout().addWidget(save_button, 1, 1)
        # dismiss button
        dismiss_button = QtWidgets.QPushButton(self.tr('Dismiss'))
        dismiss_button.clicked.connect(self.hide)
        self.layout().addWidget(dismiss_button, 1, 2)
        # Python logger
        self.logger = logging.getLogger('')
        for handler in list(self.logger.handlers):
            self.logger.removeHandler(handler)
        self.logger.setLevel(max(logging.ERROR - (verbose * 10), 1))
        self.stream_proxy = StreamProxy(self)
        self.stream_proxy.write_text.connect(self.write)
        self.stream_proxy.flush_text.connect(self.flush)
        handler = logging.StreamHandler(self.stream_proxy)
        handler.setFormatter(logging.Formatter(
            '%(asctime)s: %(levelname)s: %(name)s: %(message)s',
            datefmt='%H:%M:%S'))
        if verbose > 0:
            handler.addFilter(LoggerFilter(verbose))
        self.logger.addHandler(handler)
        # intercept stdout and stderr, if they exist
        if sys.stderr:
            sys.stderr = OutputInterceptor('stderr', sys.stderr)
        if sys.stdout:
            sys.stdout = OutputInterceptor('stdout', sys.stdout)

    @QtCore.pyqtSlot()
    def shutdown(self):
        self.stream_proxy.write_text.disconnect()
        self.stream_proxy.flush_text.disconnect()
        for handler in list(self.logger.handlers):
            self.logger.removeHandler(handler)

    @QtCore.pyqtSlot()
    def save(self):
        file_name = QtWidgets.QFileDialog.getSaveFileName(
            self, self.tr('Save log file'),
            os.path.expanduser('~/photini_log.txt'))
        if qt_version_info >= (5, 0):
            file_name = file_name[0]
        with open(file_name, 'w') as of:
            of.write(self.text.toPlainText())

    @QtCore.pyqtSlot(str)
    def write(self, msg):
        self.text.append(msg)

    @QtCore.pyqtSlot()
    def flush(self):
        if self.isHidden():
            self.show()
        self.raise_()
