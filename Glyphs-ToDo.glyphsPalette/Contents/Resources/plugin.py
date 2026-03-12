# encoding: utf-8
from __future__ import division, print_function, unicode_literals

import json
import math
import objc
from AppKit import (
	NSImage,
	NSImageNameFollowLinkFreestandingTemplate,
	NSImageNameRefreshTemplate,
	NSImageNameStatusAvailable,
	NSImageNameTrashEmpty,
	NSLineBreakByWordWrapping,
)
from GlyphsApp import Glyphs, UPDATEINTERFACE
from GlyphsApp.plugins import PalettePlugin
from vanilla import (
	Button,
	EditText,
	Group,
	List,
	PopUpButton,
	SegmentedButtonListCell,
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
		self.openIcon = self._symbolImage('pencil') or NSImage.imageNamed_(NSImageNameFollowLinkFreestandingTemplate)
		self.doneIcon = self._symbolImage('checkmark.circle') or NSImage.imageNamed_(NSImageNameStatusAvailable)
		self.deleteIcon = self._symbolImage('trash') or NSImage.imageNamed_(NSImageNameTrashEmpty)
		self.undoIcon = self._symbolImage('arrow.uturn.left') or NSImage.imageNamed_(NSImageNameRefreshTemplate)

		self.paletteWindow.group.categoryLabel = TextBox((120, 52, -10, 14), Glyphs.localize({'en': 'Category', 'fr': 'Categorie'}), sizeStyle='small')
		self.paletteWindow.group.categoryPopUp = PopUpButton((120, 64, -10, 22), self.categoryStrings, sizeStyle='small')

		filterOptions = [Glyphs.localize({'en': 'All categories', 'fr': 'Toutes categories'})] + self.categoryStrings
		self.paletteWindow.group.filterPopUp = PopUpButton((10, 96, -10, 22), filterOptions, sizeStyle='small', callback=self._filterChanged)

		activeColumns = self._buildActiveColumns()
		self.paletteWindow.group.todoList = List(
			(10, 128, -10, 150),
			[],
			columnDescriptions=activeColumns,
			showColumnTitles=False,
			enableDelete=False,
			allowsMultipleSelection=False,
			drawFocusRing=False,
			rowHeight=56,
			editCallback=self._handleActiveEdit,
		)

		self.paletteWindow.group.doneToggle = Button(
			(10, 286, -10, 22),
			self._doneToggleTitle(0),
			callback=self._toggleDoneVisibility,
			sizeStyle='small',
		)

		doneColumns = self._buildDoneColumns()
		self.paletteWindow.group.doneList = List(
			(10, 314, -10, 100),
			[],
			columnDescriptions=doneColumns,
			showColumnTitles=False,
			enableDelete=False,
			allowsMultipleSelection=False,
			drawFocusRing=False,
			rowHeight=48,
			editCallback=self._handleDoneEdit,
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
			if item.get('done'):
				doneItems.append(self._doneDisplayItem(item))
				self._doneIndexMap.append(idx)
			else:
				if self._categoryFilter and item.get('category') != self._categoryFilter:
					continue
				activeItems.append(self._activeDisplayItem(item))
				self._activeIndexMap.append(idx)

		self.paletteWindow.group.todoList.set(activeItems)
		self.paletteWindow.group.doneList.set(doneItems)
		self._updateRowHeights()
		self.paletteWindow.group.doneToggle.setTitle(self._doneToggleTitle(len(doneItems)))

	@objc.python_method
	def _baseDisplayItem(self, item):
		return {
			'task': item.get('task', ''),
			'glyph': item.get('glyph', ''),
			'category': self._categoryLabelFromKey(item.get('category')),
		}

	@objc.python_method
	def _activeDisplayItem(self, item):
		data = self._baseDisplayItem(item)
		data.update({
			'openAction': -1,
			'statusAction': -1,
		})
		return data

	@objc.python_method
	def _doneDisplayItem(self, item):
		data = self._baseDisplayItem(item)
		data.update({
			'openAction': -1,
			'doneActions': -1,
		})
		return data

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
	def _buildActiveColumns(self):
		taskTitle = Glyphs.localize({'en': 'Task', 'fr': 'Tache'})
		glyphTitle = Glyphs.localize({'en': 'Glyph', 'fr': 'Glyphe'})
		categoryTitle = Glyphs.localize({'en': 'Category', 'fr': 'Categorie'})
		openCell = SegmentedButtonListCell([{
			'imageObject': self.openIcon,
			'toolTip': Glyphs.localize({'en': 'Open glyph', 'fr': 'Ouvrir le glyphe'}),
		}])
		statusCell = SegmentedButtonListCell([
			{
				'imageObject': self.doneIcon,
				'toolTip': Glyphs.localize({'en': 'Mark as done', 'fr': 'Marquer comme fait'}),
			},
			{
				'imageObject': self.deleteIcon,
				'toolTip': Glyphs.localize({'en': 'Delete task', 'fr': 'Supprimer la tache'}),
			},
		])

		columns = [
			{'title': taskTitle, 'key': 'task', 'editable': False, 'width': 150, 'lineBreakMode': NSLineBreakByWordWrapping},
			{'title': glyphTitle, 'key': 'glyph', 'editable': False, 'width': 70},
			{'title': categoryTitle, 'key': 'category', 'editable': False, 'width': 90},
			{'title': '', 'key': 'openAction', 'editable': True, 'width': 40, 'binding': 'selectedIndex', 'cell': openCell},
			{'title': '', 'key': 'statusAction', 'editable': True, 'width': 80, 'binding': 'selectedIndex', 'cell': statusCell},
		]
		self._activeColumnKeys = [col['key'] for col in columns]
		return columns

	@objc.python_method
	def _buildDoneColumns(self):
		taskTitle = Glyphs.localize({'en': 'Task', 'fr': 'Tache'})
		glyphTitle = Glyphs.localize({'en': 'Glyph', 'fr': 'Glyphe'})
		categoryTitle = Glyphs.localize({'en': 'Category', 'fr': 'Categorie'})
		openCell = SegmentedButtonListCell([{
			'imageObject': self.openIcon,
			'toolTip': Glyphs.localize({'en': 'Open glyph', 'fr': 'Ouvrir le glyphe'}),
		}])
		doneCell = SegmentedButtonListCell([
			{
				'imageObject': self.undoIcon,
				'toolTip': Glyphs.localize({'en': 'Move back to todo', 'fr': 'Replacer dans TODO'}),
			},
			{
				'imageObject': self.deleteIcon,
				'toolTip': Glyphs.localize({'en': 'Delete task', 'fr': 'Supprimer la tache'}),
			},
		])

		columns = [
			{'title': taskTitle, 'key': 'task', 'editable': False, 'width': 150, 'lineBreakMode': NSLineBreakByWordWrapping},
			{'title': glyphTitle, 'key': 'glyph', 'editable': False, 'width': 70},
			{'title': categoryTitle, 'key': 'category', 'editable': False, 'width': 90},
			{'title': '', 'key': 'openAction', 'editable': True, 'width': 40, 'binding': 'selectedIndex', 'cell': openCell},
			{'title': '', 'key': 'doneActions', 'editable': True, 'width': 80, 'binding': 'selectedIndex', 'cell': doneCell},
		]
		self._doneColumnKeys = [col['key'] for col in columns]
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
	def _handleActiveEdit(self, sender):
		columnIndex, rowIndex = self._clickedCellPosition(sender)
		if columnIndex is None or rowIndex is None:
			return
		if columnIndex >= len(self._activeColumnKeys):
			return
		targetIndex = self._indexFromActiveRow(rowIndex)
		if targetIndex is None:
			return
		columnKey = self._activeColumnKeys[columnIndex]
		value = sender.get()[rowIndex].get(columnKey)
		if columnKey == 'openAction' and value == 0:
			self._openGlyph(targetIndex)
			self._clearActionValue(sender, rowIndex, columnKey)
		elif columnKey == 'statusAction':
			if value == 0:
				self._markDone(targetIndex, True)
			elif value == 1:
				self._deleteTask(targetIndex)

	@objc.python_method
	def _handleDoneEdit(self, sender):
		columnIndex, rowIndex = self._clickedCellPosition(sender)
		if columnIndex is None or rowIndex is None:
			return
		if columnIndex >= len(self._doneColumnKeys):
			return
		targetIndex = self._indexFromDoneRow(rowIndex)
		if targetIndex is None:
			return
		columnKey = self._doneColumnKeys[columnIndex]
		value = sender.get()[rowIndex].get(columnKey)
		if columnKey == 'openAction' and value == 0:
			self._openGlyph(targetIndex)
			self._clearActionValue(sender, rowIndex, columnKey)
		elif columnKey == 'doneActions':
			if value == 0:
				self._markDone(targetIndex, False)
			elif value == 1:
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
	def _clickedCellPosition(self, listView):
		columnIndex = rowIndex = None
		try:
			tableView = listView._tableView
			columnIndex = tableView.clickedColumn()
			rowIndex = tableView.clickedRow()
		except Exception:
			pass
		editedColumn, editedRow = listView.getEditedColumnAndRow()
		if (columnIndex is None or columnIndex < 0) and editedColumn is not None and editedColumn >= 0:
			columnIndex = editedColumn
		if (rowIndex is None or rowIndex < 0) and editedRow is not None and editedRow >= 0:
			rowIndex = editedRow
		if columnIndex is None or rowIndex is None or columnIndex < 0 or rowIndex < 0:
			return None, None
		return columnIndex, rowIndex

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
		layer = self._layerForGlyph(glyph)
		if layer is None:
			return
		layersToOpen = [layer]
		document = getattr(font, 'parent', None)
		if document:
			try:
				windowController = document.windowController()
				if windowController:
					windowController.addTabWithLayers_(layersToOpen)
					return
			except Exception:
				pass
		try:
			font.newTab(layersToOpen)
		except Exception:
			self.logToConsole(f"Glyphs-ToDo: unable to open glyph '{glyphName}'")

	@objc.python_method
	def _layerForGlyph(self, glyph):
		try:
			font = glyph.parent
			if font is None:
				return glyph.layers[0]
			currentMaster = font.selectedFontMaster
			if currentMaster and currentMaster.id in glyph.layers:
				return glyph.layers[currentMaster.id]
		except Exception:
			pass
		try:
			if glyph.layers:
				return glyph.layers[0]
		except Exception:
			pass
		return None

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
			self._setListRowHeight(self.paletteWindow.group.todoList, height)
		if doneHeights:
			height = max(40, min(120, max(doneHeights)))
			self._setListRowHeight(self.paletteWindow.group.doneList, height)

	@objc.python_method
	def _setListRowHeight(self, listView, height):
		try:
			listView._tableView.setRowHeight_(height)
		except Exception:
			pass

	@objc.python_method
	def _clearActionValue(self, listView, rowIndex, columnKey):
		try:
			items = listView.get()
			if 0 <= rowIndex < len(items):
				items[rowIndex][columnKey] = -1
				listView.set(items)
		except Exception:
			pass

	@objc.python_method
	def _symbolImage(self, symbolName):
		try:
			image = NSImage.imageWithSystemSymbolName_accessibilityDescription_(symbolName, None)
			if image:
				image.setTemplate_(True)
				return image
		except Exception:
			pass
		image = NSImage.imageNamed_(symbolName)
		if image:
			image.setTemplate_(True)
		return image

	@objc.python_method
	def _heightForText(self, text, width):
		content = text or ''
		if not content:
			return 44
		characters_per_line = max(10, int(width / 6))
		lines = math.ceil(len(content) / characters_per_line)
		return 28 + (lines * 14)
