# -*- coding: utf-8 -*-
##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-17  Jim Easterbrook  jim@jim-easterbrook.me.uk
##
##  This program is free software: you can redistribute it and/or
##  modify it under the terms of the GNU General Public License as
##  published by the Free Software Foundation, either version 3 of the
##  License, or (at your option) any later version.
##
##  This program is distributed in the hope that it will be useful,
##  but WITHOUT ANY WARRANTY; without even the implied warranty of
##  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
##  General Public License for more details.
##
##  You should have received a copy of the GNU General Public License
##  along with this program.  If not, see
##  <http://www.gnu.org/licenses/>.

from __future__ import unicode_literals

from collections import defaultdict
from datetime import datetime

import six

from photini.pyqt import (multiple_values, MultiLineEdit, Qt, QtCore, QtGui,
                          QtWidgets, qt_version_info, SingleLineEdit)

class LineEdit(QtWidgets.QLineEdit):
    def __init__(self, *arg, **kw):
        super(LineEdit, self).__init__(*arg, **kw)
        self.multiple_values = multiple_values()
        self._is_multiple = False

    def contextMenuEvent(self, event):
        menu = self.createStandardContextMenu()
        suggestion_group = QtWidgets.QActionGroup(menu)
        if self._is_multiple:
            if self.choices:
                sep = menu.insertSeparator(menu.actions()[0])
                fm = menu.fontMetrics()
                for suggestion in self.choices:
                    label = six.text_type(suggestion).replace('\n', ' ')
                    label = fm.elidedText(label, Qt.ElideMiddle, self.width())
                    action = QtWidgets.QAction(label, suggestion_group)
                    action.setData(six.text_type(suggestion))
                    menu.insertAction(sep, action)
        action = menu.exec_(event.globalPos())
        if action and action.actionGroup() == suggestion_group:
            self.set_value(action.data())

    def set_value(self, value):
        self._is_multiple = False
        if not value:
            self.clear()
            self.setPlaceholderText('')
        else:
            self.setText(six.text_type(value))

    def get_value(self):
        return self.text()

    def set_multiple(self, choices=[]):
        self._is_multiple = True
        self.choices = list(choices)
        self.setPlaceholderText(self.multiple_values)
        self.clear()

    def is_multiple(self):
        return self._is_multiple and not bool(self.get_value())


class LineEditWithAuto(QtWidgets.QWidget):
    def __init__(self, *arg, **kw):
        super(LineEditWithAuto, self).__init__(*arg, **kw)
        self._is_multiple = False
        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        # line edit box
        self.edit = LineEdit()
        layout.addWidget(self.edit)
        # auto complete button
        self.auto = QtWidgets.QPushButton(self.tr('Auto'))
        layout.addWidget(self.auto)
        # adopt child widget methods and signals
        self.set_value = self.edit.set_value
        self.get_value = self.edit.get_value
        self.set_multiple = self.edit.set_multiple
        self.is_multiple = self.edit.is_multiple
        self.editingFinished = self.edit.editingFinished
        self.autoComplete = self.auto.clicked


class KeywordsEditor(QtWidgets.QWidget):
    def __init__(self, *arg, **kw):
        super(KeywordsEditor, self).__init__(*arg, **kw)
        self.config_store = QtWidgets.QApplication.instance().config_store
        self.league_table = defaultdict(int)
        for keyword, score in eval(self.config_store.get(
            'descriptive', 'keywords', '{}')).items():
            self.league_table[keyword] = score
        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        # line edit box
        self.edit = SingleLineEdit(spell_check=True)
        layout.addWidget(self.edit)
        # favourites drop down
        self.favourites = QtWidgets.QComboBox()
        self.update_favourites()
        self.favourites.currentIndexChanged.connect(self.add_favourite)
        layout.addWidget(self.favourites)
        # adopt child widget methods and signals
        self.get_value = self.edit.get_value
        self.set_value = self.edit.set_value
        self.set_multiple = self.edit.set_multiple
        self.is_multiple = self.edit.is_multiple
        self.editingFinished = self.edit.editingFinished

    def update_favourites(self):
        self.favourites.clear()
        self.favourites.addItem(self.tr('<favourites>'))
        keywords = list(self.league_table.keys())
        keywords.sort(key=lambda x: self.league_table[x], reverse=True)
        # limit size of league_table by deleting lowest scoring
        if len(keywords) > 100:
            threshold = self.league_table[keywords[100]]
            for keyword in keywords:
                if self.league_table[keyword] <= threshold:
                    del self.league_table[keyword]
        # select highest scoring for drop down list
        keywords = keywords[:20]
        keywords.sort(key=lambda x: x.lower())
        for keyword in keywords:
            self.favourites.addItem(keyword)

    def update_league_table(self, images):
        for image in images:
            value = image.metadata.keywords
            if not value:
                continue
            for keyword in self.league_table:
                self.league_table[keyword] = max(
                    self.league_table[keyword] - 1, -5)
            for keyword in value:
                self.league_table[keyword] = min(
                    self.league_table[keyword] + 10, 1000)
        self.config_store.set(
            'descriptive', 'keywords', six.text_type(dict(self.league_table)))
        self.update_favourites()

    @QtCore.pyqtSlot(int)
    def add_favourite(self, idx):
        if idx <= 0:
            return
        self.favourites.setCurrentIndex(0)
        new_value = self.favourites.itemText(idx)
        current_value = self.get_value()
        if current_value:
            new_value = current_value + '; ' + new_value
        self.set_value(new_value)
        self.editingFinished.emit()


class Descriptive(QtWidgets.QWidget):
    def __init__(self, image_list, *arg, **kw):
        super(Descriptive, self).__init__(*arg, **kw)
        self.config_store = QtWidgets.QApplication.instance().config_store
        self.image_list = image_list
        self.form = QtWidgets.QFormLayout()
        self.setLayout(self.form)
        if qt_version_info >= (5, 0):
            self.trUtf8 = self.tr
        # construct widgets
        self.widgets = {}
        # title
        self.widgets['title'] = SingleLineEdit(spell_check=True)
        self.widgets['title'].editingFinished.connect(self.new_title)
        self.form.addRow(self.tr('Title / Object Name'), self.widgets['title'])
        # description
        self.widgets['description'] = MultiLineEdit(spell_check=True)
        self.widgets['description'].editingFinished.connect(self.new_description)
        self.form.addRow(
            self.tr('Description / Caption'), self.widgets['description'])
        # keywords
        self.widgets['keywords'] = KeywordsEditor()
        self.widgets['keywords'].editingFinished.connect(self.new_keywords)
        self.form.addRow(self.tr('Keywords'), self.widgets['keywords'])
        self.image_list.image_list_changed.connect(self.image_list_changed)
        # copyright
        self.widgets['copyright'] = LineEditWithAuto()
        self.widgets['copyright'].editingFinished.connect(self.new_copyright)
        self.widgets['copyright'].autoComplete.connect(self.auto_copyright)
        self.form.addRow(self.tr('Copyright'), self.widgets['copyright'])
        # creator
        self.widgets['creator'] = LineEditWithAuto()
        self.widgets['creator'].editingFinished.connect(self.new_creator)
        self.widgets['creator'].autoComplete.connect(self.auto_creator)
        self.form.addRow(self.tr('Creator / Artist'), self.widgets['creator'])
        # disable until an image is selected
        self.setEnabled(False)

    def refresh(self):
        pass

    def do_not_close(self):
        return False

    @QtCore.pyqtSlot()
    def image_list_changed(self):
        self.widgets['keywords'].update_league_table(
            self.image_list.get_images())

    @QtCore.pyqtSlot()
    def new_title(self):
        self._new_value('title')

    @QtCore.pyqtSlot()
    def new_description(self):
        self._new_value('description')

    @QtCore.pyqtSlot()
    def new_keywords(self):
        self._new_value('keywords')
        self.widgets['keywords'].update_league_table(
            self.image_list.get_selected_images())

    @QtCore.pyqtSlot()
    def new_copyright(self):
        self._new_value('copyright')

    @QtCore.pyqtSlot()
    def new_creator(self):
        self._new_value('creator')

    @QtCore.pyqtSlot()
    def auto_copyright(self):
        name = self.config_store.get('user', 'copyright_name')
        if not name:
            name, OK = QtWidgets.QInputDialog.getText(
                self, self.tr('Photini: input name'),
                self.tr("Please type in the copyright holder's name"),
                text=self.config_store.get('user', 'creator_name', ''))
            if OK and name:
                self.config_store.set('user', 'copyright_name', name)
            else:
                name = ''
        copyright_text = self.config_store.get(
            'user', 'copyright_text',
            self.trUtf8('Copyright ©{year} {name}. All rights reserved.'))
        for image in self.image_list.get_selected_images():
            date_taken = image.metadata.date_taken
            if date_taken is None:
                date_taken = datetime.now()
            else:
                date_taken = date_taken.datetime
            value = copyright_text.format(year=date_taken.year, name=name)
            image.metadata.copyright = value
        self._update_widget('copyright')

    @QtCore.pyqtSlot()
    def auto_creator(self):
        name = self.config_store.get('user', 'creator_name')
        if not name:
            name, OK = QtWidgets.QInputDialog.getText(
                self, self.tr('Photini: input name'),
                self.tr("Please type in the creator's name"),
                text=self.config_store.get('user', 'copyright_name', ''))
            if OK and name:
                self.config_store.set('user', 'creator_name', name)
            else:
                name = ''
        for image in self.image_list.get_selected_images():
            image.metadata.creator = name
        self._update_widget('creator')

    def _new_value(self, key):
        if not self.widgets[key].is_multiple():
            value = self.widgets[key].get_value()
            for image in self.image_list.get_selected_images():
                setattr(image.metadata, key, value)
        self._update_widget(key)

    def _update_widget(self, key):
        images = self.image_list.get_selected_images()
        if not images:
            return
        values = []
        for image in images:
            value = getattr(image.metadata, key)
            if value not in values:
                values.append(value)
        if len(values) > 1:
            self.widgets[key].set_multiple(choices=filter(None, values))
        else:
            self.widgets[key].set_value(values[0])

    @QtCore.pyqtSlot(list)
    def new_selection(self, selection):
        if not selection:
            for key in self.widgets:
                self.widgets[key].set_value(None)
            self.setEnabled(False)
            return
        for key in self.widgets:
            self._update_widget(key)
        self.setEnabled(True)
