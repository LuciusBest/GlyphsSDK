# encoding: utf-8
from __future__ import division, print_function, unicode_literals

import json
import math
import objc
from Foundation import NSObject, NSNotificationCenter
from AppKit import (
	NSAttributedString,
	NSBezierPath,
	NSButton,
	NSColor,
	NSFontAttributeName,
	NSMutableParagraphStyle,
	NSFont,
	NSForegroundColorAttributeName,
	NSImage,
	NSImageNameFollowLinkFreestandingTemplate,
	NSImageNameRefreshTemplate,
	NSImageNameStatusAvailable,
	NSImageNameTrashEmpty,
	NSInsetRect,
	NSLineBreakByTruncatingTail,
	NSLineBreakByWordWrapping,
	NSMakeRect,
	NSTableView,
	NSTableViewNoColumnAutoresizing,
	NSTableColumnUserResizingMask,
	NSTextAlignmentCenter,
	NSParagraphStyleAttributeName,
	NSTextFieldCell,
	NSTrackingActiveAlways,
	NSTrackingArea,
	NSTrackingInVisibleRect,
	NSTrackingMouseEnteredAndExited,
	NSTrackingMouseMoved,
	NSView,
	NSViewBoundsDidChangeNotification,
	NSButtonTypeMomentaryChange,
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


class CategoryBadgeCell(NSTextFieldCell):
	badgeColor = NSColor.colorWithCalibratedRed_green_blue_alpha_(0.36, 0.33, 0.86, 1.0)
	textColor = NSColor.whiteColor()
	paddingX = 10
	paddingY = 5
	radius = 8
	horizontalPadding = 5

	def drawWithFrame_inView_(self, frame, view):
		value = self.stringValue()
		if not value:
			return
		paragraph = NSMutableParagraphStyle.alloc().init()
		paragraph.setAlignment_(NSTextAlignmentCenter)
		attributes = {
			NSFontAttributeName: self.font() or NSFont.systemFontOfSize_(11),
			NSForegroundColorAttributeName: self.textColor,
			NSParagraphStyleAttributeName: paragraph,
		}
		attrString = NSAttributedString.alloc().initWithString_attributes_(value, attributes)
		textSize = attrString.size()
		width = textSize.width + (self.horizontalPadding * 2)
		height = textSize.height + 2
		centerY = frame.origin.y + frame.size.height / 2.0
		x = frame.origin.x + 4
		rect = NSMakeRect(x, centerY - height / 2.0, width, height)
		path = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(rect, self.radius, self.radius)
		self.badgeColor.set()
		path.fill()
		textRect = NSMakeRect(rect.origin.x + self.horizontalPadding, rect.origin.y + (height - textSize.height) / 2.0, textSize.width, textSize.height)
		attrString.drawInRect_(textRect)


class GlyphBadgeCell(NSTextFieldCell):
	badgeColor = NSColor.colorWithCalibratedRed_green_blue_alpha_(0.22, 0.63, 0.32, 1.0)
	textColor = NSColor.whiteColor()
	paddingX = 6
	paddingY = 4
	radius = 6
	gap = 4

	def drawWithFrame_inView_(self, frame, view):
		value = self.objectValue()
		if not value:
			return
		if isinstance(value, str):
			tokens = [token for token in value.split() if token]
		else:
			tokens = [token for token in value if token]
		if not tokens:
			return
		x = frame.origin.x + 4
		centerY = frame.origin.y + (frame.size.height / 2.0)
		font = self.font() or NSFont.systemFontOfSize_(11)
		for token in tokens:
			attr = NSAttributedString.alloc().initWithString_attributes_(token, {
				NSFontAttributeName: font,
				NSForegroundColorAttributeName: self.textColor,
			})
			size = attr.size()
			width = size.width + self.paddingX * 2
			height = size.height + self.paddingY * 2
			rect = NSMakeRect(x, centerY - height / 2.0, width, height)
			path = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(rect, self.radius, self.radius)
			self.badgeColor.set()
			path.fill()
			textRect = NSInsetRect(rect, self.paddingX, self.paddingY / 2.0)
			attr.drawInRect_(textRect)
			x += width + self.gap


class HoverActionPanel(NSView):
	def initWithController_(self, controller):
		self = objc.super(HoverActionPanel, self).initWithFrame_(NSMakeRect(0, 0, 110, 28))
		if self is None:
			return None
		self.controller = controller
		self.currentRow = -1
		self.setOpaque_(False)
		self.openButton = self._createButton('openClicked:')
		self.doneButton = self._createButton('doneClicked:')
		self.deleteButton = self._createButton('deleteClicked:')
		self.buttons = [self.openButton, self.doneButton, self.deleteButton]
		self._separatorPositions = []
		for button in self.buttons:
			self.addSubview_(button)
		return self

	@objc.python_method
	def _createButton(self, actionName):
		button = NSButton.alloc().initWithFrame_(NSMakeRect(0, 0, 24, 24))
		button.setBordered_(False)
		button.setButtonType_(NSButtonTypeMomentaryChange)
		button.setTarget_(self)
		button.setAction_(getattr(self, actionName))
		try:
			button.setContentTintColor_(NSColor.whiteColor())
		except Exception:
			pass
		return button

	@objc.python_method
	def setButtonImages(self, openImage, doneImage, deleteImage):
		if openImage:
			self.openButton.setImage_(openImage)
		if doneImage:
			self.doneButton.setImage_(doneImage)
		if deleteImage:
			self.deleteButton.setImage_(deleteImage)

	def drawRect_(self, rect):
		path = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(self.bounds(), 8, 8)
		NSColor.colorWithCalibratedWhite_alpha_(0.18, 0.9).set()
		path.fill()
		if self._separatorPositions:
			NSColor.colorWithCalibratedWhite_alpha_(1.0, 0.35).set()
			for pos in self._separatorPositions:
				line = NSBezierPath.bezierPath()
				line.setLineWidth_(1.0)
				line.moveToPoint_((pos, rect.origin.y + 4))
				line.lineToPoint_((pos, rect.origin.y + rect.size.height - 4))
				line.stroke()

	def setFrame_(self, frame):
		objc.super(HoverActionPanel, self).setFrame_(frame)
		self._layoutButtons()

	@objc.python_method
	def _layoutButtons(self):
		width = self.bounds().size.width
		height = self.bounds().size.height
		buttonWidth = 22
		gap = 6
		totalWidth = len(self.buttons) * buttonWidth + (len(self.buttons) - 1) * gap
		startX = max(4, (width - totalWidth) / 2.0)
		self._separatorPositions = []
		for index, button in enumerate(self.buttons):
			button.setFrame_(NSMakeRect(startX, (height - 20) / 2.0, buttonWidth, 20))
			startX += buttonWidth + gap
			if index < len(self.buttons) - 1:
				self._separatorPositions.append(startX - gap / 2.0)
		self.setNeedsDisplay_(True)

	@objc.python_method
	def presentInTable_atRow_(self, tableView, row):
		rowRect = tableView.rectOfRow_(row)
		if rowRect.size.height <= 0:
			self.setHidden_(True)
			return
		visible = tableView.visibleRect()
		height = min(28, rowRect.size.height - 6)
		width = max(96, len(self.buttons) * 24 + 12)
		rightEdge = visible.origin.x + visible.size.width
		x = rightEdge - width - 8
		y = rowRect.origin.y + (rowRect.size.height - height) / 2.0
		self.currentRow = row
		self.setFrame_(NSMakeRect(x, y, width, height))
		self.setHidden_(False)

	def openClicked_(self, sender):
		self.controller._handleHoverAction('open', self.currentRow)

	def doneClicked_(self, sender):
		self.controller._handleHoverAction('done', self.currentRow)

	def deleteClicked_(self, sender):
		self.controller._handleHoverAction('delete', self.currentRow)


class TableHoverTracker(NSObject):
	def initWithController_tableView_(self, controller, tableView):
		self = objc.super(TableHoverTracker, self).init()
		if self is None:
			return None
		self.controller = controller
		self.tableView = tableView
		options = NSTrackingActiveAlways | NSTrackingInVisibleRect | NSTrackingMouseMoved | NSTrackingMouseEnteredAndExited
		self.trackingArea = NSTrackingArea.alloc().initWithRect_options_owner_userInfo_(tableView.bounds(), options, self, None)
		tableView.addTrackingArea_(self.trackingArea)
		if tableView.window():
			tableView.window().setAcceptsMouseMovedEvents_(True)
		scrollView = tableView.enclosingScrollView()
		self.contentView = scrollView.contentView() if scrollView else None
		if self.contentView:
			self.contentView.setPostsBoundsChangedNotifications_(True)
			NSNotificationCenter.defaultCenter().addObserver_selector_name_object_(
				self,
				"contentViewDidScroll:",
				NSViewBoundsDidChangeNotification,
				self.contentView,
			)
		return self

	def mouseMoved_(self, event):
		point = self.tableView.convertPoint_fromView_(event.locationInWindow(), None)
		row = self.tableView.rowAtPoint_(point)
		self.controller._updateHoverRow(row)

	def mouseExited_(self, event):
		self.controller._updateHoverRow(-1)

	def contentViewDidScroll_(self, notification):
		self.controller._updateHoverRow(-1)

	def dealloc(self):
		try:
			if self.tableView and self.trackingArea:
				self.tableView.removeTrackingArea_(self.trackingArea)
		except Exception:
			pass
		try:
			NSNotificationCenter.defaultCenter().removeObserver_(self)
		except Exception:
			pass
		objc.super(TableHoverTracker, self).dealloc()


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
		self._suggestionList = None
		self._currentSuggestions = []
		self._selectedSuggestionIndex = -1
		self._currentTokenRange = None
		self._glyphNames = []
		self._glyphLookup = {}
		self._glyphNameSet = set()
		self._hoverPanel = None
		self._hoverTracker = None

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
		self.categoryStrings = [Glyphs.localize(names) for names in self.categoryOptions]
		self.categoryKeys = [entry['en'] for entry in self.categoryOptions]
		self._categoryLookup = self._buildCategoryLookup()
		self.openIcon = self._symbolImage('pencil') or NSImage.imageNamed_(NSImageNameFollowLinkFreestandingTemplate)
		self.doneIcon = self._symbolImage('checkmark.circle') or NSImage.imageNamed_(NSImageNameStatusAvailable)
		self.deleteIcon = self._symbolImage('trash') or NSImage.imageNamed_(NSImageNameTrashEmpty)
		self.undoIcon = self._symbolImage('arrow.uturn.left') or NSImage.imageNamed_(NSImageNameRefreshTemplate)

		filterOptions = [Glyphs.localize({'en': 'All categories', 'fr': 'Toutes categories'})] + self.categoryStrings
		self.paletteWindow.group.filterPopUp = PopUpButton((10, 56, -10, 22), filterOptions, sizeStyle='small', callback=self._filterChanged)

		activeColumns = self._buildActiveColumns()
		self.paletteWindow.group.todoList = List(
			(10, 90, -10, 172),
			[],
			columnDescriptions=activeColumns,
			showColumnTitles=True,
			enableDelete=False,
			allowsMultipleSelection=False,
			drawFocusRing=False,
			rowHeight=40,
			doubleClickCallback=self._handleActiveDoubleClick,
		)

		self.paletteWindow.group.doneToggle = Button(
			(10, 270, -10, 22),
			self._doneToggleTitle(0),
			callback=self._toggleDoneVisibility,
			sizeStyle='small',
		)

		doneColumns = self._buildDoneColumns()
		self.paletteWindow.group.doneList = List(
			(10, 298, -10, 100),
			[],
			columnDescriptions=doneColumns,
			showColumnTitles=False,
			enableDelete=False,
			allowsMultipleSelection=False,
			drawFocusRing=False,
			rowHeight=28,
			doubleClickCallback=self._handleDoneDoubleClick,
		)
		self.paletteWindow.group.doneList.show(False)

		self.paletteWindow.group.suggestionList = List(
			(10, 48, -10, 120),
			[],
			columnDescriptions=[
				{'title': Glyphs.localize({'en': 'Suggestion', 'fr': 'Suggestion'}), 'key': 'label'},
				{'title': Glyphs.localize({'en': 'Type', 'fr': 'Type'}), 'key': 'kind', 'width': 80, 'lineBreakMode': NSLineBreakByTruncatingTail},
			],
			showColumnTitles=False,
			enableDelete=False,
			allowsMultipleSelection=False,
			rowHeight=20,
			selectionCallback=self._suggestionSelectionChanged,
			doubleClickCallback=self._suggestionDoubleClicked,
		)
		self.paletteWindow.group.suggestionList.show(False)
		self._suggestionList = self.paletteWindow.group.suggestionList
		self._configureSuggestionListColumns()

		self.dialog = self.paletteWindow.group.getNSView()
		self._configureTaskTables()
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
		glyphNames = self._normalizeGlyphList(glyphTokens)
		glyphNames = [self._resolveGlyphName(name) for name in glyphNames]
		categoryKey = categoryFromText
		if not categoryKey:
			categoryKey = self._categoryKeyFromIndex(0)

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
		self._hideHoverActions()

	@objc.python_method
	def _baseDisplayItem(self, item):
		return {
			'task': item.get('task', ''),
			'categoryLabel': self._categoryLabelFromKey(item.get('category')),
			'glyphTokens': self._glyphTokenList(item),
		}

	@objc.python_method
	def _glyphTokenList(self, item):
		glyphs = item.get('glyphs')
		if not glyphs and item.get('glyph'):
			glyphs = [item.get('glyph')]
		if not glyphs:
			return []
		return [self._resolveGlyphName(name) for name in glyphs]

	@objc.python_method
	def _activeDisplayItem(self, item):
		return self._baseDisplayItem(item)

	@objc.python_method
	def _doneDisplayItem(self, item):
		return self._baseDisplayItem(item)

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
				self._hideHoverActions()
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
			self._glyphLookup = {}
			for name in self._glyphNames:
				lower = name.lower()
				self._glyphLookup.setdefault(lower, []).append(name)
			self._glyphNameSet = set(self._glyphNames)
		else:
			self._glyphNames = []
			self._glyphLookup = {}
			self._glyphNameSet = set()

	@objc.python_method
	def minHeight(self):
		return 220

	@objc.python_method
	def maxHeight(self):
		return 520

	@objc.python_method
	def __file__(self):
		return __file__

	@objc.python_method
	def _log(self, *parts):
		try:
			message = ' '.join(str(part) for part in parts)
		except Exception:
			message = ' '.join([repr(part) for part in parts])
		try:
			print('[Glyphs-ToDo]', message)
		except Exception:
			pass

	# --- UI helpers ---

	@objc.python_method
	def _taskFieldDidChange(self):
		self._log('_taskFieldDidChange')
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
		self._log('_updateSuggestions text="%s" cursor=%d' % (text, cursor))
		token, start, end = self._detectSlashToken(text, cursor)
		if not token:
			self._log('no slash token at cursor')
			self._hideSuggestions()
			return
		suggestions = self._buildSuggestions(token[1:])
		self._log('found token "%s" -> %d suggestion(s)' % (token, len(suggestions)))
		self._currentTokenRange = (start, end)
		if suggestions:
			self._showSuggestions(suggestions)
		else:
			self._log('no suggestions to show')
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
			self._log('_showSuggestions called without suggestions')
			self._hideSuggestions()
			return
		self._log('_showSuggestions displaying %d item(s)' % len(suggestions))
		self._currentSuggestions = suggestions
		self._selectedSuggestionIndex = 0
		listView = self._ensureSuggestionList()
		if listView is None:
			self._log('_showSuggestions cannot obtain list view')
			return
		listView.set(suggestions)
		listView.show(True)
		self._setSuggestionListHidden(False)
		listView.setSelection([0])
		self._positionSuggestionList()

	@objc.python_method
	def _hideSuggestions(self):
		self._log('_hideSuggestions')
		listView = self._ensureSuggestionList()
		if listView is not None:
			listView.show(False)
			listView.set([])
			self._setSuggestionListHidden(True)
		self._currentSuggestions = []
		self._selectedSuggestionIndex = -1
		self._currentTokenRange = None

	@objc.python_method
	def _positionSuggestionList(self):
		viewToMove, containerView = self._suggestionListViewAndContainer()
		if viewToMove is None or containerView is None:
			self._log('_positionSuggestionList missing viewToMove or container')
			return
		targetRect = self._caretRectRelativeToView(containerView)
		if targetRect is None:
			self._log('_positionSuggestionList caret rect unavailable')
			targetRect = self._textFieldRectRelativeToView(containerView)
		if targetRect is None:
			self._log('_positionSuggestionList no fallback rect')
			return
		fieldRect = self._textFieldRectRelativeToView(containerView)
		frame = viewToMove.frame()
		bounds = containerView.bounds()
		padding = 6.0
		minWidth = 140.0
		maxWidth = max(60.0, bounds.size.width - (padding * 2.0))
		if fieldRect is not None:
			desiredWidth = max(fieldRect.size.width, minWidth)
		else:
			desiredWidth = frame.size.width or minWidth
		width = min(max(desiredWidth, minWidth), maxWidth)
		height = frame.size.height or 120.0
		isFlipped = bool(containerView.isFlipped()) if hasattr(containerView, 'isFlipped') else False
		verticalSpacing = 4.0
		if isFlipped:
			preferredY = targetRect.origin.y + targetRect.size.height + verticalSpacing
			if preferredY + height > bounds.size.height - padding:
				preferredY = targetRect.origin.y - height - verticalSpacing
		else:
			preferredY = targetRect.origin.y - height - verticalSpacing
			if preferredY < padding:
				preferredY = targetRect.origin.y + targetRect.size.height + verticalSpacing
		minY = padding
		maxY = max(minY, bounds.size.height - height - padding)
		y = min(max(preferredY, minY), maxY)
		baseX = targetRect.origin.x
		minX = padding
		maxX = max(minX, bounds.size.width - width - padding)
		x = min(max(baseX, minX), maxX)
		viewToMove.setFrame_(NSMakeRect(x, y, width, height))
		self._log('_positionSuggestionList frame set to (%.1f, %.1f, %.1f, %.1f)' % (x, y, width, height))

	@objc.python_method
	def _suggestionListViewAndContainer(self):
		listView = self._ensureSuggestionList()
		if listView is None:
			self._log('_suggestionListViewAndContainer no suggestion list')
			return (None, None)
		groupView = self.paletteWindow.group.getNSView()
		if groupView is None:
			self._log('_suggestionListViewAndContainer missing group view')
			return (None, None)
		viewCandidate = getattr(listView, '_scrollView', None)
		getView = getattr(self._suggestionList, 'getNSView', None)
		if callable(getView):
			try:
				viewCandidate = viewCandidate or getView()
			except Exception:
				viewCandidate = viewCandidate or None
		if viewCandidate is None:
			viewCandidate = getattr(listView, '_nsObject', None)
		if viewCandidate is None:
			self._log('_suggestionListViewAndContainer missing candidate view')
			return (None, None)
		current = viewCandidate
		superview = current.superview()
		if superview is None:
			return (None, None)
		while superview is not None and superview != groupView:
			current = superview
			superview = current.superview()
		if superview is None:
			self._log('_suggestionListViewAndContainer chain did not reach group view')
			return (None, None)
		return current, superview

	@objc.python_method
	def _caretRectRelativeToView(self, view):
		if view is None:
			self._log('_caretRectRelativeToView view is None')
			return None
		field = self.paletteWindow.group.newTaskField
		if not field:
			self._log('_caretRectRelativeToView missing field')
			return None
		nsField = getattr(field, '_nsObject', None)
		if nsField is None:
			self._log('_caretRectRelativeToView missing nsField')
			return None
		window = nsField.window()
		if window is None:
			self._log('_caretRectRelativeToView missing window')
			return None
		editor = nsField.currentEditor()
		if editor is None:
			window.makeFirstResponder_(nsField)
			editor = nsField.currentEditor()
		if editor is None:
			self._log('_caretRectRelativeToView missing editor')
			return None
		_, cursor = self._currentTaskFieldState()
		try:
			charRect = editor.firstRectForCharacterRange_actualRange_((cursor, 0), None)
		except Exception:
			charRect = None
		if charRect is None:
			self._log('_caretRectRelativeToView charRect unavailable for cursor %d' % cursor)
			return None
		try:
			windowRect = window.convertRectFromScreen_(charRect)
		except Exception:
			self._log('_caretRectRelativeToView convertRectFromScreen failed')
			return None
		try:
			localRect = view.convertRect_fromView_(windowRect, None)
		except Exception:
			self._log('_caretRectRelativeToView convertRect_fromView failed')
			return None
		return localRect

	@objc.python_method
	def _textFieldRectRelativeToView(self, view):
		if view is None:
			self._log('_textFieldRectRelativeToView view is None')
			return None
		field = self.paletteWindow.group.newTaskField
		if not field:
			self._log('_textFieldRectRelativeToView missing field')
			return None
		nsField = getattr(field, '_nsObject', None)
		if nsField is None:
			self._log('_textFieldRectRelativeToView missing nsField')
			return None
		fieldSuperview = nsField.superview()
		fieldFrame = nsField.frame()
		if fieldSuperview is None:
			self._log('_textFieldRectRelativeToView missing field superview')
			return fieldFrame
		try:
			return view.convertRect_fromView_(fieldFrame, fieldSuperview)
		except Exception:
			self._log('_textFieldRectRelativeToView convert failed')
			return fieldFrame

	@objc.python_method
	def _setSuggestionListHidden(self, hidden):
		listView = self._ensureSuggestionList()
		if listView is None:
			self._log('_setSuggestionListHidden no suggestion list')
			return
		view = getattr(listView, '_scrollView', None)
		if view is None:
			view = getattr(listView, '_nsObject', None)
		if view is None:
			self._log('_setSuggestionListHidden no native view to hide/show')
			return
		try:
			view.setHidden_(hidden)
		except Exception:
			pass

	@objc.python_method
	def _moveSuggestion(self, delta):
		if not self._currentSuggestions:
			return
		index = self._selectedSuggestionIndex if self._selectedSuggestionIndex is not None else 0
		index = (index + delta) % len(self._currentSuggestions)
		self._selectedSuggestionIndex = index
		listView = self._ensureSuggestionList()
		if listView is not None:
			listView.setSelection([index])

	@objc.python_method
	def _ensureSuggestionList(self):
		if self._suggestionList:
			self._log('_ensureSuggestionList reusing cached list')
			return self._suggestionList
		group = getattr(self.paletteWindow, 'group', None)
		if group is None:
			self._log('_ensureSuggestionList missing group')
			return None
		existing = getattr(group, 'suggestionList', None)
		if existing is not None:
			self._log('_ensureSuggestionList found existing list on group')
			self._suggestionList = existing
			return self._suggestionList
		self._log('_ensureSuggestionList rebuilding suggestion list UI')
		try:
			group.suggestionList = List(
				(10, 48, -10, 120),
				[],
				columnDescriptions=[
					{'title': Glyphs.localize({'en': 'Suggestion', 'fr': 'Suggestion'}), 'key': 'label'},
					{'title': Glyphs.localize({'en': 'Type', 'fr': 'Type'}), 'key': 'kind', 'width': 80, 'lineBreakMode': NSLineBreakByTruncatingTail},
				],
				showColumnTitles=False,
				enableDelete=False,
				allowsMultipleSelection=False,
				rowHeight=20,
				selectionCallback=self._suggestionSelectionChanged,
				doubleClickCallback=self._suggestionDoubleClicked,
			)
			group.suggestionList.show(False)
			self._suggestionList = group.suggestionList
			self._configureSuggestionListColumns()
			self._log('_ensureSuggestionList rebuilt list successfully')
		except Exception as error:
			self._log('_ensureSuggestionList failed:', error)
			self._suggestionList = None
		return self._suggestionList

	@objc.python_method
	def _configureSuggestionListColumns(self):
		listView = self._suggestionList
		if not listView:
			return
		tableView = getattr(listView, '_tableView', None)
		if tableView is None:
			return
		try:
			columns = list(tableView.tableColumns())
		except Exception:
			return
		if len(columns) < 2:
			return
		labelColumn = columns[0]
		typeColumn = columns[1]
		try:
			labelColumn.setResizingMask_(NSTableColumnUserResizingMask)
		except Exception:
			pass
		try:
			typeColumn.setWidth_(80)
			typeColumn.setMinWidth_(60)
			typeColumn.setResizingMask_(0)
		except Exception:
			pass

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
			key = token
			if key in seen:
				continue
			seen.add(key)
			result.append(token)
		return result

	@objc.python_method
	def _resolveGlyphName(self, name):
		if not name:
			return ''
		if name in self._glyphNameSet:
			return name
		lower = name.lower()
		candidates = self._glyphLookup.get(lower)
		if candidates:
			for candidate in candidates:
				if candidate == name:
					return candidate
			return candidates[0]
		return name

	@objc.python_method
	def _buildActiveColumns(self):
		glyphTitle = Glyphs.localize({'en': 'Glyph', 'fr': 'Glyphe'})
		categoryTitle = Glyphs.localize({'en': 'Category', 'fr': 'Categorie'})
		taskTitle = Glyphs.localize({'en': 'Task Name', 'fr': 'Intitule'})
		if not hasattr(self, '_categoryBadgeCell'):
			self._categoryBadgeCell = CategoryBadgeCell.alloc().init()
		if not hasattr(self, '_glyphBadgeCell'):
			self._glyphBadgeCell = GlyphBadgeCell.alloc().init()
		columns = [
			{'title': categoryTitle, 'key': 'categoryLabel', 'editable': False, 'width': 110, 'cell': self._categoryBadgeCell},
			{'title': glyphTitle, 'key': 'glyphTokens', 'editable': False, 'width': 150, 'cell': self._glyphBadgeCell},
			{'title': taskTitle, 'key': 'task', 'editable': False, 'width': 240, 'lineBreakMode': NSLineBreakByTruncatingTail},
		]
		return columns

	@objc.python_method
	def _buildDoneColumns(self):
		taskTitle = Glyphs.localize({'en': 'Completed Task', 'fr': 'Tache terminee'})
		columns = [
			{'title': taskTitle, 'key': 'task', 'editable': False, 'width': 320, 'lineBreakMode': NSLineBreakByTruncatingTail},
		]
		return columns

	@objc.python_method
	def _configureTaskTables(self):
		self._styleListView(self.paletteWindow.group.todoList, 36, True)
		self._styleListView(self.paletteWindow.group.doneList, 26, False)
		self._installHoverUI()

	@objc.python_method
	def _styleListView(self, listView, rowHeight, horizontalScroll):
		try:
			tableView = listView._tableView
			scrollView = listView._scrollView
		except Exception:
			return
		tableView.setAllowsColumnReordering_(False)
		tableView.setAllowsColumnSelection_(False)
		try:
			tableView.setAllowsColumnResizing_(True)
		except Exception:
			pass
		tableView.setAllowsMultipleSelection_(False)
		tableView.setRowHeight_(rowHeight)
		try:
			for column in tableView.tableColumns():
				column.setResizingMask_(NSTableColumnUserResizingMask)
		except Exception:
			pass
		if horizontalScroll:
			try:
				tableView.setColumnAutoresizingStyle_(NSTableViewNoColumnAutoresizing)
			except Exception:
				pass
			if scrollView:
				scrollView.setHasHorizontalScroller_(True)
		self._installHoverUI()

	@objc.python_method
	def _installHoverUI(self):
		if self._hoverPanel:
			return
		try:
			tableView = self.paletteWindow.group.todoList._tableView
		except Exception:
			return
		self._hoverPanel = HoverActionPanel.alloc().initWithController_(self)
		self._hoverPanel.setButtonImages(self.openIcon, self.doneIcon, self.deleteIcon)
		self._hoverPanel.setHidden_(True)
		tableView.addSubview_(self._hoverPanel)
		self._hoverTracker = TableHoverTracker.alloc().initWithController_tableView_(self, tableView)

	@objc.python_method
	def _updateHoverRow(self, row):
		if row is None or row < 0:
			self._hideHoverActions()
			return
		if not self._hoverPanel:
			return
		try:
			tableView = self.paletteWindow.group.todoList._tableView
		except Exception:
			return
		self._hoverPanel.presentInTable_atRow_(tableView, row)

	@objc.python_method
	def _hideHoverActions(self):
		if self._hoverPanel:
			self._hoverPanel.setHidden_(True)
			self._hoverPanel.currentRow = -1

	@objc.python_method
	def _handleHoverAction(self, action, row):
		index = self._indexFromActiveRow(row)
		if index is None:
			return
		if action == 'open':
			self._openGlyph(index)
		elif action == 'done':
			self._markDone(index, True)
		elif action == 'delete':
			self._deleteTask(index)
		self._hideHoverActions()

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
	def _handleActiveDoubleClick(self, sender):
		selection = sender.getSelection()
		if not selection:
			return
		index = self._indexFromActiveRow(selection[0])
		if index is None:
			return
		self._openGlyph(index)

	@objc.python_method
	def _handleDoneDoubleClick(self, sender):
		selection = sender.getSelection()
		if not selection:
			return
		index = self._indexFromDoneRow(selection[0])
		if index is None:
			return
		self._openGlyph(index)

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
			key = resolved
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
		self._setListRowHeight(self.paletteWindow.group.todoList, 36)
		self._setListRowHeight(self.paletteWindow.group.doneList, 26)

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
