# encoding: utf-8
from __future__ import division, print_function, unicode_literals

import json
import math
import objc
from AppKit import NSLineBreakByWordWrapping
from GlyphsApp import Glyphs, UPDATEINTERFACE
from GlyphsApp.plugins import PalettePlugin
from vanilla import (
	Button,
	ButtonListCell,
	EditText,
	Group,
	List,
	PopUpButton,
	TextBox,
	Window,
)


class GlyphsToDoPlugin(PalettePlugin):
	defaultsKey = "com.paulpaturel.GlyphsToDo.items"
	categoryOptions = [
		{'en': 'General', 'fr': 'General'},
		{'en': 'Drawing', 'fr': 'Dessin'},
		{'en': 'Spacing', 'fr': 'Espacement'},
		{'en': 'Kerning', 'fr': 'Crenage'},
		{'en': 'Hinting', 'fr': 'Hinting'},
		{'en': 'Proofing', 'fr': 'Epreuves'},
	]

	@objc.python_method
	def settings(self):
		self.name = Glyphs.localize({
			'en': 'Glyphs-ToDo',
			'fr': 'Glyphs-ToDo',
		})

		self.todoItems = []
		self._activeIndexMap = []
		self._doneIndexMap = []
		self._activeFont = None
		self._categoryFilter = None
		self._doneExpanded = False

		width, height = 260, 360
		self.paletteWindow = Window((width, height))
		self.paletteWindow.group = Group((0, 0, width, height))

		self.paletteWindow.group.taskLabel = TextBox((10, 8, -10, 14), Glyphs.localize({'en': 'Task', 'fr': 'Tache'}), sizeStyle='small')
		self.paletteWindow.group.newTaskField = EditText(
			(10, 20, -90, 24),
			placeholder=Glyphs.localize({
				'en': 'New task',
				'fr': 'Nouvelle tache',
			}),
			sizeStyle='small',
		)
		self.paletteWindow.group.addButton = Button(
			(-80, 20, -10, 24),
			Glyphs.localize({'en': 'Add', 'fr': 'Ajouter'}),
			callback=self.addTask,
			sizeStyle='small',
		)
		self.paletteWindow.group.glyphLabel = TextBox((10, 52, 90, 14), Glyphs.localize({'en': 'Glyph', 'fr': 'Glyphe'}), sizeStyle='small')
		self.paletteWindow.group.glyphField = EditText(
			(10, 64, 100, 22),
			placeholder=Glyphs.localize({'en': 'Name', 'fr': 'Nom'}),
			sizeStyle='small',
		)

		self.categoryStrings = [Glyphs.localize(names) for names in self.categoryOptions]
		self.categoryKeys = [entry['en'] for entry in self.categoryOptions]

		self.paletteWindow.group.categoryLabel = TextBox((120, 52, -10, 14), Glyphs.localize({'en': 'Category', 'fr': 'Categorie'}), sizeStyle='small')
		self.paletteWindow.group.categoryPopUp = PopUpButton((120, 64, -10, 22), self.categoryStrings, sizeStyle='small')

		filterOptions = [Glyphs.localize({'en': 'All categories', 'fr': 'Toutes categories'})] + self.categoryStrings
		self.paletteWindow.group.filterPopUp = PopUpButton((10, 96, -10, 22), filterOptions, sizeStyle='small', callback=self._filterChanged)

		activeColumns = self._buildColumnDescriptions(includeDoneButtons=True)
		self.paletteWindow.group.todoList = List(
			(10, 128, -10, 150),
			[],
			columnDescriptions=activeColumns,
			showColumnTitles=False,
			enableDelete=False,
			allowsMultipleSelection=False,
			drawFocusRing=False,
			rowHeight=56,
			doubleClickCallback=self._handleRowDoubleClick,
			buttonCallback=self._handleActiveButton,
		)

		self.paletteWindow.group.doneToggle = Button(
			(10, 286, -10, 22),
			self._doneToggleTitle(0),
			callback=self._toggleDoneVisibility,
			sizeStyle='small',
		)

		doneColumns = self._buildColumnDescriptions(includeDoneButtons=False)
		self.paletteWindow.group.doneList = List(
			(10, 314, -10, 100),
			[],
			columnDescriptions=doneColumns,
			showColumnTitles=False,
			enableDelete=False,
			allowsMultipleSelection=False,
			drawFocusRing=False,
			rowHeight=48,
			doubleClickCallback=self._handleRowDoubleClick,
			buttonCallback=self._handleDoneButton,
		)
		self.paletteWindow.group.doneList.show(False)

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
		glyphName = (self.paletteWindow.group.glyphField.get() or '').strip()
		catIndex = self.paletteWindow.group.categoryPopUp.get()
		category = self._categoryKeyFromIndex(catIndex)

		self.todoItems.insert(0, {
			'task': text,
			'done': False,
			'glyph': glyphName,
			'category': category,
		})
		self.paletteWindow.group.newTaskField.set('')
		self.paletteWindow.group.glyphField.set('')
		self._refreshList()
		self._saveTasks(font)

	@objc.python_method
	def _refreshList(self):
		activeItems = []
		doneItems = []
		self._activeIndexMap = []
		self._doneIndexMap = []

		for idx, item in enumerate(self.todoItems):
			displayData = self._formatDisplayItem(item)
			if item.get('done'):
				doneItems.append(displayData)
				self._doneIndexMap.append(idx)
			else:
				if self._categoryFilter and item.get('category') != self._categoryFilter:
					continue
				activeItems.append(displayData)
				self._activeIndexMap.append(idx)

		self.paletteWindow.group.todoList.set(activeItems)
		self.paletteWindow.group.doneList.set(doneItems)
		self._updateRowHeights()
		self.paletteWindow.group.doneToggle.setTitle(self._doneToggleTitle(len(doneItems)))

	@objc.python_method
	def _formatDisplayItem(self, item):
		return {
			'task': item.get('task', ''),
			'glyph': item.get('glyph', ''),
			'category': self._categoryLabelFromKey(item.get('category')),
			'openGlyph': Glyphs.localize({'en': 'Open', 'fr': 'Ouvrir'}),
			'doneButton': Glyphs.localize({'en': 'Done', 'fr': 'Fait'}),
			'deleteButton': Glyphs.localize({'en': 'Delete', 'fr': 'Supprimer'}),
			'undoButton': Glyphs.localize({'en': 'Undo', 'fr': 'Rouvrir'}),
		}

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
				glyphName = entry.get('glyph', '')
				category = self._normalizeCategory(entry.get('category'))
			else:
				task = entry
				done = False
				glyphName = ''
				category = self._categoryKeyFromIndex(0)

			if task:
				normalized.append({
					'task': task,
					'done': done,
					'glyph': glyphName,
					'category': category,
				})
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
		return 220

	@objc.python_method
	def maxHeight(self):
		return 520

	@objc.python_method
	def __file__(self):
		return __file__

	# --- UI helpers ---

	@objc.python_method
	def _buildColumnDescriptions(self, includeDoneButtons=True):
		taskTitle = Glyphs.localize({'en': 'Task', 'fr': 'Tache'})
		glyphTitle = Glyphs.localize({'en': 'Glyph', 'fr': 'Glyphe'})
		categoryTitle = Glyphs.localize({'en': 'Category', 'fr': 'Categorie'})

		columns = [
			{'title': taskTitle, 'key': 'task', 'editable': False, 'width': 150, 'lineBreakMode': NSLineBreakByWordWrapping},
			{'title': glyphTitle, 'key': 'glyph', 'editable': False, 'width': 70},
			{'title': categoryTitle, 'key': 'category', 'editable': False, 'width': 80},
			{'title': '', 'key': 'openGlyph', 'width': 50, 'cell': ButtonListCell(title=Glyphs.localize({'en': 'Open', 'fr': 'Ouvrir'}))},
		]

		if includeDoneButtons:
			columns.append({'title': '', 'key': 'doneButton', 'width': 58, 'cell': ButtonListCell(title=Glyphs.localize({'en': 'Done', 'fr': 'Fait'}))})
			columns.append({'title': '', 'key': 'deleteButton', 'width': 66, 'cell': ButtonListCell(title=Glyphs.localize({'en': 'Delete', 'fr': 'Supprimer'}))})
		else:
			columns.append({'title': '', 'key': 'undoButton', 'width': 58, 'cell': ButtonListCell(title=Glyphs.localize({'en': 'Undo', 'fr': 'Rouvrir'}))})
			columns.append({'title': '', 'key': 'deleteButton', 'width': 66, 'cell': ButtonListCell(title=Glyphs.localize({'en': 'Delete', 'fr': 'Supprimer'}))})

		return columns

	@objc.python_method
	def _categoryKeyFromIndex(self, index):
		index = max(0, min(index, len(self.categoryKeys) - 1))
		return self.categoryKeys[index]

	@objc.python_method
	def _categoryLabelFromKey(self, key):
		if key in self.categoryKeys:
			return self.categoryStrings[self.categoryKeys.index(key)]
		return self.categoryStrings[0]

	@objc.python_method
	def _normalizeCategory(self, value):
		if not value:
			return self._categoryKeyFromIndex(0)
		if value in self.categoryKeys:
			return value
		# try to match localized string
		for idx, localized in enumerate(self.categoryStrings):
			if localized == value:
				return self.categoryKeys[idx]
		return self._categoryKeyFromIndex(0)

	@objc.python_method
	def _filterChanged(self, sender):
		value = sender.get()
		if value == 0:
			self._categoryFilter = None
		else:
			self._categoryFilter = self._categoryKeyFromIndex(value - 1)
		self._refreshList()

	@objc.python_method
	def _handleRowDoubleClick(self, sender):
		row = sender.getSelection()
		if not row:
			return
		self._openGlyphForRow(sender, row[0])

	@objc.python_method
	def _handleActiveButton(self, sender, info=None):
		event = info
		if event is None and hasattr(sender, 'getLastClicked'):
			event = sender.getLastClicked()
		if event is None:
			event = {}
		row = event.get('row')
		key = event.get('columnIdentifier')
		if row is None and hasattr(sender, 'getClickedRow'):
			row = sender.getClickedRow()
		if key is None and hasattr(sender, 'getClickedColumnIdentifier'):
			key = sender.getClickedColumnIdentifier()
		if row is None or key is None:
			return
		targetIndex = self._indexFromActiveRow(row)
		if targetIndex is None:
			return
		if key == 'openGlyph':
			self._openGlyph(targetIndex)
		elif key == 'doneButton':
			self._markDone(targetIndex, True)
		elif key == 'deleteButton':
			self._deleteTask(targetIndex)

	@objc.python_method
	def _handleDoneButton(self, sender, info=None):
		event = info
		if event is None and hasattr(sender, 'getLastClicked'):
			event = sender.getLastClicked()
		if event is None:
			event = {}
		row = event.get('row')
		key = event.get('columnIdentifier')
		if row is None and hasattr(sender, 'getClickedRow'):
			row = sender.getClickedRow()
		if key is None and hasattr(sender, 'getClickedColumnIdentifier'):
			key = sender.getClickedColumnIdentifier()
		if row is None or key is None:
			return
		targetIndex = self._indexFromDoneRow(row)
		if targetIndex is None:
			return
		if key == 'openGlyph':
			self._openGlyph(targetIndex)
		elif key == 'undoButton':
			self._markDone(targetIndex, False)
		elif key == 'deleteButton':
			self._deleteTask(targetIndex)

	@objc.python_method
	def _indexFromActiveRow(self, row):
		if 0 <= row < len(self._activeIndexMap):
			return self._activeIndexMap[row]
		return None

	@objc.python_method
	def _indexFromDoneRow(self, row):
		if 0 <= row < len(self._doneIndexMap):
			return self._doneIndexMap[row]
		return None

	@objc.python_method
	def _openGlyphForRow(self, sender, row):
		if sender == self.paletteWindow.group.todoList:
			index = self._indexFromActiveRow(row)
		else:
			index = self._indexFromDoneRow(row)
		if index is None:
			return
		self._openGlyph(index)

	@objc.python_method
	def _openGlyph(self, index):
		font = self._currentFont()
		if font is None:
			return
		task = self.todoItems[index]
		glyphName = task.get('glyph') or ''
		if not glyphName:
			return
		glyph = font.glyphs[glyphName]
		if glyph is None:
			return
		document = font.parent()
		if document:
			document.windowController().setActiveGlyph_(glyph)

	@objc.python_method
	def _markDone(self, index, state):
		self.todoItems[index]['done'] = bool(state)
		font = self._currentFont()
		if font:
			self._saveTasks(font)
		self._refreshList()

	@objc.python_method
	def _deleteTask(self, index):
		del self.todoItems[index]
		font = self._currentFont()
		if font:
			self._saveTasks(font)
		self._refreshList()

	@objc.python_method
	def _toggleDoneVisibility(self, sender):
		self._doneExpanded = not self._doneExpanded
		self.paletteWindow.group.doneList.show(self._doneExpanded)
		self.paletteWindow.group.doneToggle.setTitle(self._doneToggleTitle(len(self.paletteWindow.group.doneList.get())))

	@objc.python_method
	def _doneToggleTitle(self, count):
		base = Glyphs.localize({'en': 'Completed (%d)', 'fr': 'Terminees (%d)'}) % count
		prefix = '[-] ' if self._doneExpanded else '[+] '
		return prefix + base

	@objc.python_method
	def _updateRowHeights(self):
		activeHeights = [self._heightForText(item['task'], 150) for item in self.paletteWindow.group.todoList.get()]
		doneHeights = [self._heightForText(item['task'], 150) for item in self.paletteWindow.group.doneList.get()]
		if activeHeights:
			height = max(50, min(120, max(activeHeights)))
			self.paletteWindow.group.todoList.setRowHeight(height)
		if doneHeights:
			height = max(40, min(120, max(doneHeights)))
			self.paletteWindow.group.doneList.setRowHeight(height)

	@objc.python_method
	def _heightForText(self, text, width):
		content = text or ''
		if not content:
			return 44
		characters_per_line = max(10, int(width / 6))
		lines = math.ceil(len(content) / characters_per_line)
		return 28 + (lines * 14)
