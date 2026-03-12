# encoding: utf-8
from __future__ import division, print_function, unicode_literals

import json
import objc
from GlyphsApp import Glyphs, UPDATEINTERFACE
from GlyphsApp.plugins import PalettePlugin
from vanilla import Button, EditText, Group, List, Window


class GlyphsToDoPlugin(PalettePlugin):
	defaultsKey = "com.paulpaturel.GlyphsToDo.items"

	@objc.python_method
	def settings(self):
		self.name = Glyphs.localize({
			'en': 'Glyphs-ToDo',
			'fr': 'Glyphs-ToDo',
		})

		self.todoItems = []
		self._activeFont = None

		width, height = 240, 220
		self.paletteWindow = Window((width, height))
		self.paletteWindow.group = Group((0, 0, width, height))

		self.paletteWindow.group.newTaskField = EditText(
			(10, 10, -90, 24),
			placeholder=Glyphs.localize({
				'en': 'New task',
				'fr': 'Nouvelle tache',
			}),
			sizeStyle='small',
		)
		self.paletteWindow.group.addButton = Button(
			(-80, 10, -10, 24),
			Glyphs.localize({'en': 'Add', 'fr': 'Ajouter'}),
			callback=self.addTask,
			sizeStyle='small',
		)
		self.paletteWindow.group.todoList = List(
			(10, 44, -10, -10),
			self.todoItems,
			columnDescriptions=[
				{'title': Glyphs.localize({'en': 'Task', 'fr': 'Tache'}), 'key': 'task'},
			],
			showColumnTitles=False,
			enableDelete=False,
			doubleClickCallback=self.toggleCompletion,
		)

		self.dialog = self.paletteWindow.group.getNSView()
		self._syncFromFont()

	@objc.python_method
	def start(self):
		Glyphs.addCallback(self._handleInterfaceUpdate, UPDATEINTERFACE)

	@objc.python_method
	def __del__(self):
		try:
			Glyphs.removeCallback(self._handleInterfaceUpdate)
		except Exception:
			pass

	@objc.python_method
	def addTask(self, sender=None):
		font = self._currentFont()
		if font is None:
			return

		text = self.paletteWindow.group.newTaskField.get().strip()
		if not text:
			return

		self.todoItems.insert(0, {'task': text, 'done': False})
		self.paletteWindow.group.newTaskField.set('')
		self._refreshList()
		self._saveTasks(font)

	@objc.python_method
	def toggleCompletion(self, sender):
		font = self._currentFont()
		if font is None:
			return

		selection = sender.getSelection()
		if not selection:
			return

		for index in selection:
			item = self.todoItems[index]
			item['done'] = not item.get('done', False)
		self._refreshList()
		self._saveTasks(font)

	@objc.python_method
	def _refreshList(self):
		displayItems = [
			{'task': self._formatTask(item)} for item in self.todoItems
		]
		self.paletteWindow.group.todoList.set(displayItems)

	@objc.python_method
	def _formatTask(self, item):
		title = item.get('task', '')
		return '[x] ' + title if item.get('done') else title

	@objc.python_method
	def _saveTasks(self, font):
		payload = json.dumps(self.todoItems)
		font.userData[self.defaultsKey] = payload

	@objc.python_method
	def _loadTasks(self, font):
		payload = font.userData.get(self.defaultsKey)
		if not payload:
			return []
		if not isinstance(payload, str):
			try:
				payload = json.dumps(payload)
			except Exception:
				return []
		try:
			items = json.loads(payload)
		except Exception:
			return []

		normalized = []
		for entry in items:
			if isinstance(entry, dict):
				task = entry.get('task')
				done = bool(entry.get('done', False))
			else:
				task = entry
				done = False

			if task:
				normalized.append({'task': task, 'done': done})
		return normalized

	@objc.python_method
	def _currentFont(self):
		try:
			windowController = self.windowController()
			if not windowController:
				return None
			document = windowController.document()
			if not document:
				return None
			return document.font
		except Exception:
			return None

	@objc.python_method
	def _handleInterfaceUpdate(self, sender):
		self._syncFromFont()

	@objc.python_method
	def _syncFromFont(self):
		font = self._currentFont()
		if font is None:
			if self._activeFont is not None:
				self._activeFont = None
				self.todoItems = []
				self._refreshList()
			return

		if font is self._activeFont:
			return

		self._activeFont = font
		self.todoItems = self._loadTasks(font)
		self._refreshList()

	@objc.python_method
	def minHeight(self):
		return 120

	@objc.python_method
	def maxHeight(self):
		return 350

	@objc.python_method
	def __file__(self):
		return __file__
