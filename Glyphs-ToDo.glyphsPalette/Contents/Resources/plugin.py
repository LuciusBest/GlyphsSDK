# encoding: utf-8
from __future__ import division, print_function, unicode_literals

import json
import math
import objc
from Foundation import NSObject
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
	Popover,
	PopUpButton,
	SegmentedButtonListCell,
	TextBox,
	Window,
)


class TaskFieldDelegate(NSObject):
	controller = None

	def initWithController_(self, controller):
		self = objc.super(TaskFieldDelegate, self).init()
		if self is None:
			return None
		self.controller = controller
		return self

	def controlTextDidChange_(self, notification):
		controller = self._controller()
		if controller:
			controller._taskFieldDidChange()

	def control_textView_doCommandBySelector_(self, control, textView, selector):
		controller = self._controller()
		if controller:
			handled = controller._handleTaskFieldCommand(selector)
			if handled:
				return True
		return False

	def controlTextDidEndEditing_(self, notification):
		controller = self._controller()
		if controller:
			controller._hideSuggestions()

	def _controller(self):
		return self.controller


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
		self._suggestionPopover = None
		self._suggestionList = None
		self._currentSuggestions = []
		self._selectedSuggestionIndex = -1
		self._currentTokenRange = None
		self._glyphNames = []
		self._glyphLookup = {}

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
		self.taskFieldDelegate = TaskFieldDelegate.alloc().initWithController_(self)
		self.paletteWindow.group.newTaskField._nsObject.setDelegate_(self.taskFieldDelegate)
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
		self._categoryLookup = self._buildCategoryLookup()
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

		rawText = (self.paletteWindow.group.newTaskField.get() or '').strip()
		if not rawText:
			return
		cleanText, glyphTokens, categoryFromText = self._extractMetadataFromText(rawText)
		glyphInput = (self.paletteWindow.group.glyphField.get() or '').strip()
		manualGlyphs = self._parseGlyphInput(glyphInput)
		glyphNames = self._normalizeGlyphList(glyphTokens + manualGlyphs)
		glyphNames = [self._resolveGlyphName(name) for name in glyphNames]
		categoryKey = categoryFromText
		if not categoryKey:
			categoryKey = self._categoryKeyFromIndex(self.paletteWindow.group.categoryPopUp.get())

		if not cleanText:
			cleanText = ' '.join(glyphNames) or categoryKey or ''
		self.todoItems.insert(0, {
			'task': cleanText,
			'done': False,
			'glyphs': glyphNames,
			'glyph': glyphNames[0] if glyphNames else '',
			'category': categoryKey,
		})
		self.paletteWindow.group.newTaskField.set('')
		self.paletteWindow.group.glyphField.set('')
		self._hideSuggestions()
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
			'glyph': self._glyphDisplay(item),
			'category': self._categoryLabelFromKey(item.get('category')),
		}

	@objc.python_method
	def _glyphDisplay(self, item):
		glyphs = item.get('glyphs')
		if not glyphs and item.get('glyph'):
			glyphs = [item.get('glyph')]
		if not glyphs:
			return ''
		resolved = [self._resolveGlyphName(name) for name in glyphs]
		return ', '.join(resolved)

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
				glyphList = []
				storedGlyphs = entry.get('glyphs')
				if isinstance(storedGlyphs, list):
					glyphList = [name for name in storedGlyphs if isinstance(name, str)]
				elif glyphName:
					glyphList = [glyphName]
				category = self._normalizeCategory(entry.get('category'))
			else:
				task = entry
				done = False
				glyphName = ''
				glyphList = []
				category = self._categoryKeyFromIndex(0)

			if task:
				normalized.append({
					'task': task,
					'done': done,
					'glyph': glyphList[0] if glyphList else glyphName,
					'glyphs': glyphList,
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
		if font:
			self._glyphNames = sorted(
				[glyph.name for glyph in font.glyphs if glyph.name],
				key=lambda n: n.lower(),
			)
			self._glyphLookup = {name.lower(): name for name in self._glyphNames}
		else:
			self._glyphNames = []
			self._glyphLookup = {}

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
	def _taskFieldDidChange(self):
		self._pendingGlyphName = None
		self._pendingCategoryKey = None
		self._updateSuggestions()

	@objc.python_method
	def _handleTaskFieldCommand(self, selector):
		if selector in ('moveDown:', 'moveUp:'):
			if self._currentSuggestions:
				self._moveSuggestion(1 if selector == 'moveDown:' else -1)
				return True
			return False
		if selector in ('insertTab:', 'insertNewline:'):
			if self._acceptCurrentSuggestion():
				return True
			return False
		if selector == 'cancelOperation:':
			self._hideSuggestions()
			return False
		return False

	@objc.python_method
	def _currentTaskFieldState(self):
		field = self.paletteWindow.group.newTaskField
		text = field.get() or ''
		editor = field._nsObject.currentEditor()
		cursor = len(text)
		if editor:
			try:
				cursor = editor.selectedRange()[0]
			except Exception:
				pass
		return text, cursor

	@objc.python_method
	def _updateSuggestions(self):
		text, cursor = self._currentTaskFieldState()
		token, start, end = self._detectSlashToken(text, cursor)
		if not token:
			self._hideSuggestions()
			return
		suggestions = self._buildSuggestions(token[1:])
		self._currentTokenRange = (start, end)
		if suggestions:
			self._showSuggestions(suggestions)
		else:
			self._hideSuggestions()

	@objc.python_method
	def _detectSlashToken(self, text, cursor):
		if not text or cursor == 0:
			return (None, None, None)
		start = cursor
		while start > 0 and not text[start - 1].isspace():
			start -= 1
		end = cursor
		length = len(text)
		while end < length and not text[end].isspace():
			end += 1
		token = text[start:end]
		if token.startswith('/'):
			return token, start, end
		return (None, None, None)

	@objc.python_method
	def _buildSuggestions(self, prefix):
		prefixLower = prefix.lower()
		items = []
		categoryItems = []
		for key in self.categoryKeys:
			label = key
			display = "/%s" % key
			if not prefixLower or key.lower().startswith(prefixLower):
				categoryItems.append({
					'label': display,
					'kind': Glyphs.localize({'en': 'Category', 'fr': 'Categorie'}),
					'type': 'category',
					'value': key,
				})
		glyphItems = []
		limit = 50 if prefixLower else 25
		count = 0
		for name in self._glyphNames:
			if not prefixLower or name.lower().startswith(prefixLower):
				glyphItems.append({
					'label': "/%s" % name,
					'kind': Glyphs.localize({'en': 'Glyph', 'fr': 'Glyphe'}),
					'type': 'glyph',
					'value': name,
				})
				count += 1
				if count >= limit:
					break
		items.extend(categoryItems)
		items.extend(glyphItems)
		return items

	@objc.python_method
	def _showSuggestions(self, suggestions):
		if not suggestions:
			self._hideSuggestions()
			return
		self._currentSuggestions = suggestions
		if not self._suggestionPopover:
			self._createSuggestionPopover()
			parentView = self.paletteWindow.group.newTaskField._nsObject
			origin, size = parentView.bounds()
			rect = (0, size[1], size[0], 1)
			self._suggestionPopover.open(parentView=parentView, preferredEdge='bottom', relativeRect=rect)
		self._selectedSuggestionIndex = 0
		if self._suggestionList:
			self._suggestionList.set(suggestions)
			self._suggestionList.setSelection([0])
		self._resizeSuggestionPopover()

	@objc.python_method
	def _resizeSuggestionPopover(self):
		if not self._suggestionPopover:
			return
		rows = max(1, min(8, len(self._currentSuggestions)))
		height = 10 + rows * 22
		self._suggestionPopover.resize(260, height)

	@objc.python_method
	def _hideSuggestions(self):
		if self._suggestionPopover:
			self._suggestionPopover.close()
			self._suggestionPopover = None
			self._suggestionList = None
		self._currentSuggestions = []
		self._selectedSuggestionIndex = -1
		self._currentTokenRange = None

	@objc.python_method
	def _createSuggestionPopover(self):
		pop = Popover((260, 120), behavior='transient')
		pop.list = List(
			(0, 0, -0, -0),
			[],
			columnDescriptions=[
				{'title': Glyphs.localize({'en': 'Suggestion', 'fr': 'Suggestion'}), 'key': 'label'},
				{'title': Glyphs.localize({'en': 'Type', 'fr': 'Type'}), 'key': 'kind', 'width': 80},
			],
			showColumnTitles=False,
			enableDelete=False,
			allowsMultipleSelection=False,
			selectionCallback=self._suggestionSelectionChanged,
			doubleClickCallback=self._suggestionDoubleClicked,
		)
		self._suggestionPopover = pop
		self._suggestionList = pop.list
		pop.bind('did close', self._suggestionPopoverClosed)

	@objc.python_method
	def _suggestionPopoverClosed(self, sender):
		self._suggestionPopover = None
		self._suggestionList = None
		self._currentSuggestions = []
		self._selectedSuggestionIndex = -1
		self._currentTokenRange = None

	@objc.python_method
	def _moveSuggestion(self, delta):
		if not self._currentSuggestions:
			return
		index = self._selectedSuggestionIndex if self._selectedSuggestionIndex is not None else 0
		index = (index + delta) % len(self._currentSuggestions)
		self._selectedSuggestionIndex = index
		if self._suggestionList:
			self._suggestionList.setSelection([index])

	@objc.python_method
	def _acceptCurrentSuggestion(self):
		if not self._currentSuggestions:
			return False
		index = self._selectedSuggestionIndex
		if index is None or index < 0:
			index = 0
		return self._applySuggestion(index)

	@objc.python_method
	def _applySuggestion(self, index):
		if not self._currentTokenRange or index >= len(self._currentSuggestions):
			return False
		item = self._currentSuggestions[index]
		text, _ = self._currentTaskFieldState()
		start, end = self._currentTokenRange
		replacement = "/%s" % item['value']
		newText = text[:start] + replacement + text[end:]
		field = self.paletteWindow.group.newTaskField
		field.set(newText)
		editor = field._nsObject.currentEditor()
		if editor:
			try:
				editor.setSelectedRange_((start + len(replacement), 0))
			except Exception:
				pass
		if item['type'] == 'glyph':
			self.paletteWindow.group.glyphField.set(item['value'])
		elif item['type'] == 'category':
			self._selectCategoryKey(item['value'])
		self._taskFieldDidChange()
		self._hideSuggestions()
		return True

	@objc.python_method
	def _suggestionSelectionChanged(self, sender):
		selection = sender.getSelection()
		if selection:
			self._selectedSuggestionIndex = selection[0]

	@objc.python_method
	def _suggestionDoubleClicked(self, sender):
		selection = sender.getSelection()
		if selection:
			if self._applySuggestion(selection[0]):
				self._hideSuggestions()

	@objc.python_method
	def _selectCategoryKey(self, key):
		if key not in self.categoryKeys:
			return
		index = self.categoryKeys.index(key)
		self.paletteWindow.group.categoryPopUp.set(index)

	@objc.python_method
	def _extractMetadataFromText(self, text):
		words = text.split()
		cleanWords = []
		glyphTokens = []
		categoryKey = None
		for word in words:
			if word.startswith('/') and len(word) > 1:
				token = word[1:]
				lower = token.lower()
				if categoryKey is None and lower in self._categoryLookup:
					categoryKey = self._categoryLookup[lower]
				elif lower not in self._categoryLookup:
					glyphTokens.append(token)
				cleanWords.append(token)
			else:
				cleanWords.append(word)
		cleanText = ' '.join(filter(None, cleanWords)).strip()
		return cleanText, glyphTokens, categoryKey

	@objc.python_method
	def _parseGlyphInput(self, text):
		if not text:
			return []
		normalized = []
		for chunk in text.replace(',', ' ').split():
			token = chunk.strip()
			if not token:
				continue
			if token.startswith('/'):
				token = token[1:]
			if token:
				normalized.append(token)
		return normalized

	@objc.python_method
	def _normalizeGlyphList(self, names):
		if not names:
			return []
		seen = set()
		result = []
		for name in names:
			if not name:
				continue
			token = name.strip()
			if not token:
				continue
			key = token.lower()
			if key in seen:
				continue
			seen.add(key)
			result.append(token)
		return result

	@objc.python_method
	def _resolveGlyphName(self, name):
		if not name:
			return ''
		return self._glyphLookup.get(name.lower(), name)

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
	def _buildCategoryLookup(self):
		lookup = {}
		for key, label in zip(self.categoryKeys, self.categoryStrings):
			lookup[key.lower()] = key
			lookup[label.lower()] = key
		return lookup

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
	def _glyphsForTask(self, task):
		glyphs = []
		if isinstance(task.get('glyphs'), list):
			glyphs = [name for name in task.get('glyphs') if isinstance(name, str)]
		elif task.get('glyph'):
			glyphs = [task.get('glyph')]
		normalized = []
		seen = set()
		for name in glyphs:
			if not name:
				continue
			resolved = self._resolveGlyphName(name)
			if not resolved:
				continue
			key = resolved.lower()
			if key in seen:
				continue
			seen.add(key)
			normalized.append(resolved)
		return normalized

	@objc.python_method
	def _openGlyph(self, index):
		font = self._currentFont()
		if font is None:
			return
		task = self.todoItems[index]
		glyphNames = self._glyphsForTask(task)
		if not glyphNames:
			return
		layersToOpen = []
		for glyphName in glyphNames:
			glyph = font.glyphs[glyphName]
			if glyph is None:
				continue
			layer = self._layerForGlyph(glyph)
			if layer is not None:
				layersToOpen.append(layer)
		if not layersToOpen:
			return
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
			self.logToConsole("Glyphs-ToDo: unable to open glyphs '%s'" % ', '.join(glyphNames))

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
