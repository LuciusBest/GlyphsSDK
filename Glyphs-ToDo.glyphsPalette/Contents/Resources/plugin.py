# encoding: utf-8
from __future__ import division, print_function, unicode_literals

import json
import math
import re
import objc
from Foundation import NSObject, NSNotificationCenter
from AppKit import (
	NSAttributedString,
	NSBezierPath,
	NSButton,
	NSColor,
	NSFontAttributeName,
	NSMutableAttributedString,
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
	NSMakeSize,
	NSTableView,
	NSTableViewNoColumnAutoresizing,
	NSTableColumnUserResizingMask,
	NSStringDrawingUsesFontLeading,
	NSStringDrawingUsesLineFragmentOrigin,
	NSTextAlignmentCenter,
	NSTextAttachment,
	NSTextAttachmentCell,
	NSParagraphStyleAttributeName,
	NSStrikethroughStyleAttributeName,
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


class ActionHoverButton(NSButton):
	hoverCornerRadius = 5.0

	def initWithFrame_(self, frame):
		self = objc.super(ActionHoverButton, self).initWithFrame_(frame)
		if self is None:
			return None
		self._hovered = False
		self._trackingArea = None
		self._configure()
		return self

	@objc.python_method
	def _configure(self):
		self.setBordered_(False)
		self.setButtonType_(NSButtonTypeMomentaryChange)
		try:
			self.setFocusRingType_(0)
		except Exception:
			pass
		try:
			self.setContentTintColor_(NSColor.whiteColor())
		except Exception:
			pass
		self.setWantsLayer_(False)
		self._installTracking()

	@objc.python_method
	def _installTracking(self):
		if self._trackingArea is not None:
			self.removeTrackingArea_(self._trackingArea)
		options = NSTrackingActiveAlways | NSTrackingInVisibleRect | NSTrackingMouseEnteredAndExited
		self._trackingArea = NSTrackingArea.alloc().initWithRect_options_owner_userInfo_(self.bounds(), options, self, None)
		self.addTrackingArea_(self._trackingArea)

	def updateTrackingAreas(self):
		self._installTracking()
		objc.super(ActionHoverButton, self).updateTrackingAreas()

	def mouseEntered_(self, event):
		self._hovered = True
		self.setNeedsDisplay_(True)

	def mouseExited_(self, event):
		self._hovered = False
		self.setNeedsDisplay_(True)

	def drawRect_(self, rect):
		if self._hovered or self.isHighlighted():
			accent = self._accentColor()
			path = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(self.bounds(), self.hoverCornerRadius, self.hoverCornerRadius)
			accent.set()
			path.fill()
		objc.super(ActionHoverButton, self).drawRect_(rect)

	@objc.python_method
	def _accentColor(self):
		alpha = 0.32 if self.isHighlighted() else 0.2
		try:
			return NSColor.controlAccentColor().colorWithAlphaComponent_(alpha)
		except Exception:
			return NSColor.colorWithCalibratedRed_green_blue_alpha_(0.0, 0.45, 1.0, alpha)


def _color_from_rgb(red, green, blue, alpha=1.0):
	return NSColor.colorWithCalibratedRed_green_blue_alpha_(red, green, blue, alpha)


_CATEGORY_TAG_COLORS = {
	'General': _color_from_rgb(0.32, 0.34, 0.78),
	'Drawing': _color_from_rgb(0.93, 0.42, 0.24),
	'Spacing': _color_from_rgb(0.19, 0.53, 0.84),
	'Kerning': _color_from_rgb(0.27, 0.56, 0.42),
	'Hinting': _color_from_rgb(0.58, 0.32, 0.74),
	'Proofing': _color_from_rgb(0.20, 0.27, 0.35),
}
_DEFAULT_CATEGORY_COLOR = _color_from_rgb(0.36, 0.33, 0.86)
_GLYPH_TAG_COLOR = _color_from_rgb(0.18, 0.62, 0.32)
_MASTER_TAG_COLOR = _color_from_rgb(0.18, 0.45, 0.92)


class TagAttachmentCell(NSTextAttachmentCell):
	descriptor = None
	horizontalPadding = 3
	verticalPadding = 1
	radius = 0

	def initWithDescriptor_(self, descriptor):
		self = objc.super(TagAttachmentCell, self).initTextCell_('')
		if self is None:
			return None
		self.descriptor = descriptor or {}
		self.font = NSFont.systemFontOfSize_(11)
		return self

	def cellSize(self):
		label = self.descriptor.get('label') or ''
		attributes = {NSFontAttributeName: self.font}
		attrString = NSAttributedString.alloc().initWithString_attributes_(label, attributes)
		size = attrString.size()
		width = math.ceil(size.width) + (self.horizontalPadding * 2) + 2
		height = math.ceil(size.height) + (self.verticalPadding * 2)
		return NSMakeSize(width, height)

	def drawWithFrame_inView_(self, frame, controlView):
		self._drawTagInFrame(frame)

	def drawWithFrame_inView_characterIndex_layoutManager_(self, frame, controlView, charIndex, layoutManager):
		self._drawTagInFrame(frame)

	@objc.python_method
	def _drawTagInFrame(self, frame):
		descriptor = self.descriptor or {}
		bgColor, textColor = self._colorsForDescriptor(descriptor)
		path = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(frame, self.radius, self.radius)
		bgColor.set()
		path.fill()
		textRect = NSInsetRect(frame, self.horizontalPadding, self.verticalPadding)
		paragraph = NSMutableParagraphStyle.alloc().init()
		paragraph.setAlignment_(NSTextAlignmentCenter)
		attributes = {
			NSFontAttributeName: self.font,
			NSForegroundColorAttributeName: textColor,
			NSParagraphStyleAttributeName: paragraph,
		}
		label = descriptor.get('label') or ''
		attrString = NSAttributedString.alloc().initWithString_attributes_(label, attributes)
		attrString.drawInRect_(textRect)

	@objc.python_method
	def baselineOffsetY(self):
		try:
			return math.floor(self.font.descender()) - self.verticalPadding
		except Exception:
			return -2

	@objc.python_method
	def _colorsForDescriptor(self, descriptor):
		bgAlpha = 0.72
		bgWhite = 0.26
		if descriptor.get('inactive'):
			bgAlpha = 0.56
			bgWhite = 0.32
		if descriptor.get('highlighted'):
			bgAlpha = 0.84
			bgWhite = 0.18
		bgColor = NSColor.colorWithCalibratedWhite_alpha_(bgWhite, bgAlpha)
		return bgColor, NSColor.whiteColor()

class TaskSentenceCell(NSTextFieldCell):
	paddingX = 4
	paddingY = 3

	def init(self):
		self = objc.super(TaskSentenceCell, self).init()
		if self is None:
			return None
		self._storedValue = None
		self.setWraps_(True)
		self.setLineBreakMode_(NSLineBreakByWordWrapping)
		return self

	def setObjectValue_(self, value):
		self._storedValue = value
		if isinstance(value, dict):
			text = value.get('text', '')
		else:
			text = value
		objc.super(TaskSentenceCell, self).setObjectValue_(text)

	def objectValue(self):
		return getattr(self, '_storedValue', None)

	def drawWithFrame_inView_(self, frame, view):
		value = self.objectValue()
		if isinstance(value, dict):
			attributed = self._buildAttributedSentence(value)
			if attributed is not None:
				inset = NSInsetRect(frame, self.paddingX, self.paddingY)
				attributed.drawInRect_(inset)
				return
		objc.super(TaskSentenceCell, self).drawWithFrame_inView_(frame, view)

	@objc.python_method
	def heightForValue_width_(self, value, width):
		usableWidth = max(40, width - (self.paddingX * 2))
		if isinstance(value, dict):
			attributed = self._buildAttributedSentence(value)
		else:
			text = value or ''
			attributed = NSAttributedString.alloc().initWithString_attributes_(text, self._textAttributes({'done': False}))
		if attributed is None:
			return self.paddingY * 2
		options = NSStringDrawingUsesLineFragmentOrigin | NSStringDrawingUsesFontLeading
		rect = attributed.boundingRectWithSize_options_(NSMakeSize(usableWidth, 10000), options)
		return int(math.ceil(rect.size.height + (self.paddingY * 2)))

	@objc.python_method
	def _buildAttributedSentence(self, value):
		domainAttributes = self._textAttributes(value)
		content = NSMutableAttributedString.alloc().init()
		segments = value.get('segments') or []
		if segments:
			for segment in segments:
				if segment.get('kind') == 'tag':
					descriptor = dict(segment.get('descriptor') or {})
					descriptor['inactive'] = descriptor.get('inactive') or value.get('done')
					descriptor['highlighted'] = bool(self.isHighlighted())
					attachment = self._attachmentForDescriptor(descriptor)
					if attachment:
						content.appendAttributedString_(NSAttributedString.attributedStringWithAttachment_(attachment))
					continue
				text = segment.get('value') or ''
				if text:
					content.appendAttributedString_(NSAttributedString.alloc().initWithString_attributes_(text, domainAttributes))
			return content
		text = value.get('text') or ''
		if not isinstance(text, str):
			text = str(text)
		text = text.strip()
		if not text:
			text = value.get('fallback') or ''
		content.appendAttributedString_(NSAttributedString.alloc().initWithString_attributes_(text, domainAttributes))
		tags = value.get('tags') or []
		if tags:
			content.appendAttributedString_(NSAttributedString.alloc().initWithString_attributes_('  ', domainAttributes))
			for descriptor in tags:
				descriptor = dict(descriptor)
				descriptor['inactive'] = descriptor.get('inactive') or value.get('done')
				descriptor['highlighted'] = bool(self.isHighlighted())
				attachment = self._attachmentForDescriptor(descriptor)
				if attachment:
					content.appendAttributedString_(NSAttributedString.attributedStringWithAttachment_(attachment))
					content.appendAttributedString_(NSAttributedString.alloc().initWithString_attributes_(' ', domainAttributes))
		return content

	@objc.python_method
	def _textAttributes(self, value):
		done = bool(value.get('done'))
		highlighted = bool(self.isHighlighted())
		paragraph = NSMutableParagraphStyle.alloc().init()
		paragraph.setLineBreakMode_(NSLineBreakByWordWrapping)
		paragraph.setLineSpacing_(1.0)
		paragraph.setParagraphSpacing_(1.0)
		color = self._textColor(done, highlighted)
		attributes = {
			NSFontAttributeName: self._bodyFont(),
			NSForegroundColorAttributeName: color,
			NSParagraphStyleAttributeName: paragraph,
		}
		if done:
			attributes[NSStrikethroughStyleAttributeName] = 1
		return attributes

	@objc.python_method
	def _bodyFont(self):
		if not hasattr(self, '_cachedBodyFont'):
			self._cachedBodyFont = NSFont.systemFontOfSize_(11)
		return self._cachedBodyFont

	@objc.python_method
	def _textColor(self, done, highlighted):
		if highlighted:
			return NSColor.alternateSelectedControlTextColor()
		if done:
			try:
				return NSColor.disabledControlTextColor()
			except Exception:
				return NSColor.colorWithCalibratedWhite_alpha_(0.45, 1.0)
		return NSColor.textColor()

	@objc.python_method
	def _attachmentForDescriptor(self, descriptor):
		try:
			attachment = NSTextAttachment.alloc().init()
			cell = TagAttachmentCell.alloc().initWithDescriptor_(descriptor)
			if not cell:
				return None
			attachment.setAttachmentCell_(cell)
			size = cell.cellSize()
			attachment.setBounds_(NSMakeRect(0, cell.baselineOffsetY(), size.width, size.height))
			return attachment
		except Exception:
			return None

class HoverActionPanel(NSView):
	buttonHeight = 20
	rowPadding = 8

	@classmethod
	def minimumRowHeight(cls):
		return cls.buttonHeight + cls.rowPadding

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
		button = ActionHoverButton.alloc().initWithFrame_(NSMakeRect(0, 0, 24, 24))
		button.setTarget_(self)
		button.setAction_(getattr(self, actionName))
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
			button.setFrame_(NSMakeRect(startX, (height - self.buttonHeight) / 2.0, buttonWidth, self.buttonHeight))
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
		height = max(self.buttonHeight + 2, min(28, rowRect.size.height - 4))
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
		self._untitledTaskLabel = Glyphs.localize({
			'en': 'Untitled task',
			'fr': 'Tache sans titre',
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
		self._masterNames = []
		self._masterLookup = {}
		self._hoverPanel = None
		self._hoverTracker = None
		self._suggestionTypeColumnWidth = 70
		self._minimumTaskRowHeight = HoverActionPanel.minimumRowHeight()

		width, height = 260, 360
		self.paletteWindow = Window((width, height))
		self.paletteWindow.group = Group((0, 0, width, height))

		self.paletteWindow.group.taskLabel = TextBox((10, 8, -10, 14), Glyphs.localize({'en': 'New Task', 'fr': 'Nouvelle tache'}), sizeStyle='small')
		self.paletteWindow.group.newTaskField = EditText(
			(10, 24, -110, 26),
			placeholder=Glyphs.localize({
				'en': 'e.g. /redraw counters /o /O /a /A',
				'fr': 'ex: /redraw counters /o /O /a /A',
			}),
			sizeStyle='small',
		)
		self.taskFieldDelegate = TaskFieldDelegate.alloc().initWithController_(self)
		self.paletteWindow.group.newTaskField._nsObject.setDelegate_(self.taskFieldDelegate)
		self.paletteWindow.group.addButton = Button(
			(-100, 24, -10, 26),
			Glyphs.localize({'en': 'Add Task', 'fr': 'Ajouter la tache'}),
			callback=self.addTask,
			sizeStyle='small',
		)
		self.paletteWindow.group.sortLabel = TextBox(
			(10, 60, 200, 14),
			Glyphs.localize({'en': 'Sort by · Categories', 'fr': 'Trier par · Categories'}),
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
		self.paletteWindow.group.filterPopUp = PopUpButton((10, 76, -10, 24), filterOptions, sizeStyle='small', callback=self._filterChanged)
		self.paletteWindow.group.tasksListLabel = TextBox(
			(10, 108, -10, 14),
			Glyphs.localize({'en': 'Tasks List', 'fr': 'Liste des taches'}),
			sizeStyle='small',
		)

		activeColumns = self._buildActiveColumns()
		self.paletteWindow.group.todoList = List(
			(10, 124, -10, 148),
			[],
			columnDescriptions=activeColumns,
			showColumnTitles=False,
			enableDelete=False,
			allowsMultipleSelection=False,
			drawFocusRing=False,
			rowHeight=self._minimumTaskRowHeight,
			doubleClickCallback=self._handleActiveDoubleClick,
		)

		self.paletteWindow.group.doneToggle = Button(
			(10, 276, -10, 22),
			self._doneToggleTitle(0),
			callback=self._toggleDoneVisibility,
			sizeStyle='small',
		)

		doneColumns = self._buildDoneColumns()
		self.paletteWindow.group.doneList = List(
			(10, 304, -10, 54),
			[],
			columnDescriptions=doneColumns,
			showColumnTitles=False,
			enableDelete=False,
			allowsMultipleSelection=False,
			drawFocusRing=False,
			rowHeight=self._minimumTaskRowHeight,
			doubleClickCallback=self._handleDoneDoubleClick,
		)
		self.paletteWindow.group.doneList.show(False)

		self.paletteWindow.group.suggestionList = List(
			(10, 48, -10, 120),
			[],
			columnDescriptions=[
				{'title': Glyphs.localize({'en': 'Suggestion', 'fr': 'Suggestion'}), 'key': 'label'},
				{
					'title': Glyphs.localize({'en': 'Type', 'fr': 'Type'}),
					'key': 'kind',
					'width': self._suggestionTypeColumnWidth,
					'lineBreakMode': NSLineBreakByTruncatingTail,
				},
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
		cleanText, glyphTokens, categoryFromText, masterTokens = self._extractMetadataFromText(rawText)
		glyphNames = self._normalizeGlyphList(glyphTokens)
		glyphNames = [self._resolveGlyphName(name) for name in glyphNames]
		categoryKey = categoryFromText
		if not categoryKey:
			categoryKey = self._categoryKeyFromIndex(0)

		if not cleanText:
			cleanText = ' '.join(glyphNames) or ' '.join(masterTokens) or categoryKey or ''
		self.todoItems.insert(0, {
			'task': cleanText,
			'rawTask': rawText,
			'done': False,
			'glyphs': glyphNames,
			'glyph': glyphNames[0] if glyphNames else '',
			'category': categoryKey,
			'masters': masterTokens,
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
			'sentenceData': self._sentenceDisplayData(item),
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
	def _sentenceDisplayData(self, item):
		text = (item.get('task') or '').strip()
		if not text:
			text = self._untitledTaskLabel
		rawText = (item.get('rawTask') or '').strip()
		categoryKey = self._categoryKeyForDisplay(item.get('category'))
		segments = self._inlineSegmentsForItem(item, rawText)
		if segments:
			return {
				'segments': segments,
				'fallback': self._untitledTaskLabel,
				'done': bool(item.get('done')),
			}
		tags = []
		if categoryKey:
			tags.append({
				'type': 'category',
				'label': categoryKey,
				'categoryKey': categoryKey,
			})
		for glyphName in self._glyphTokenList(item):
			tags.append({'type': 'glyph', 'label': glyphName})
		for masterName in self._mastersForTask(item):
			tags.append({'type': 'master', 'label': masterName})
		return {
			'text': text,
			'fallback': self._untitledTaskLabel,
			'tags': tags,
			'done': bool(item.get('done')),
		}

	@objc.python_method
	def _inlineSegmentsForItem(self, item, rawText):
		if not rawText:
			return []
		segments = []
		lastIndex = 0
		for match in re.finditer(r'\S+', rawText):
			start, end = match.span()
			if start > lastIndex:
				segments.append({'kind': 'text', 'value': rawText[lastIndex:start]})
			token = match.group(0)
			descriptor, trailingText = self._descriptorForInlineToken(token)
			if descriptor is None:
				segments.append({'kind': 'text', 'value': token})
			else:
				segments.append({'kind': 'tag', 'descriptor': descriptor})
				if trailingText:
					segments.append({'kind': 'text', 'value': trailingText})
			lastIndex = end
		if lastIndex < len(rawText):
			segments.append({'kind': 'text', 'value': rawText[lastIndex:]})
		return segments

	@objc.python_method
	def _descriptorForInlineToken(self, token):
		if not token.startswith('/') or len(token) <= 1:
			return (None, None)
		trailingChars = []
		core = token
		while len(core) > 1 and core[-1] in '.,;:!?)]}':
			trailingChars.append(core[-1])
			core = core[:-1]
		if len(core) <= 1:
			return (None, None)
		label = core[1:]
		lower = label.lower()
		if lower in self._categoryLookup:
			categoryKey = self._categoryLookup[lower]
			descriptor = {
				'type': 'category',
				'label': categoryKey,
				'categoryKey': categoryKey,
			}
		else:
			masterName = self._canonicalMasterName(label)
			if masterName:
				descriptor = {'type': 'master', 'label': masterName}
			else:
				glyphName = self._resolveGlyphName(label)
				descriptor = {'type': 'glyph', 'label': glyphName}
		return descriptor, ''.join(reversed(trailingChars))

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
				rawTask = entry.get('rawTask')
				done = bool(entry.get('done', False))
				glyphName = entry.get('glyph', '')
				glyphList = []
				masterList = []
				storedGlyphs = entry.get('glyphs')
				if isinstance(storedGlyphs, list):
					glyphList = [name for name in storedGlyphs if isinstance(name, str)]
				elif glyphName:
					glyphList = [glyphName]
				storedMasters = entry.get('masters')
				if isinstance(storedMasters, list):
					masterList = [name for name in storedMasters if isinstance(name, str)]
				category = self._normalizeCategory(entry.get('category'))
			else:
				task = entry
				rawTask = None
				done = False
				glyphName = ''
				glyphList = []
				category = self._categoryKeyFromIndex(0)
				masterList = []

			if task:
				normalized.append({
					'task': task,
					'rawTask': rawTask,
					'done': done,
					'glyph': glyphList[0] if glyphList else glyphName,
					'glyphs': glyphList,
					'category': category,
					'masters': masterList,
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

		if font is not self._activeFont:
			self._activeFont = font
			self.todoItems = self._loadTasks(font)
			self._refreshList()

		self._updateFontCaches(font)

	@objc.python_method
	def _updateFontCaches(self, font):
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
			self._masterNames = sorted(
				[master.name for master in getattr(font, 'masters', []) if getattr(master, 'name', None)],
				key=lambda n: n.lower(),
			)
			self._masterLookup = {}
			for name in self._masterNames:
				lower = name.lower()
				self._masterLookup[lower] = name
				normalized = self._normalizedIdentifier(name)
				if normalized and normalized not in self._masterLookup:
					self._masterLookup[normalized] = name
			self._log('_updateFontCaches glyphs=%d masters=%d' % (len(self._glyphNames), len(self._masterNames)))
		else:
			self._glyphNames = []
			self._glyphLookup = {}
			self._glyphNameSet = set()
			self._masterNames = []
			self._masterLookup = {}
			self._log('_updateFontCaches cleared caches')

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
		masterItems = []
		for masterName in self._currentMasterNames():
			if self._matchesRelaxedPrefix(prefixLower, masterName):
				masterItems.append({
					'label': "/%s" % masterName,
					'kind': Glyphs.localize({'en': 'Master', 'fr': 'Master'}),
					'type': 'master',
					'value': masterName,
				})
		items.extend(masterItems)
		self._log('_buildSuggestions master matches=%d' % len(masterItems))
		return items

	@objc.python_method
	def _currentMasterNames(self):
		font = self._activeFont or self._currentFont()
		if not font:
			return []
		names = []
		for master in getattr(font, 'masters', []):
			name = getattr(master, 'name', None)
			if name:
				names.append(name)
		return names

	@objc.python_method
	def _matchesRelaxedPrefix(self, prefixLower, candidate):
		if not prefixLower:
			return True
		candidateLower = candidate.lower()
		if candidateLower.startswith(prefixLower):
			return True
		normalizedPrefix = self._normalizedIdentifier(prefixLower)
		normalizedCandidate = self._normalizedIdentifier(candidateLower)
		return bool(normalizedPrefix) and normalizedPrefix in normalizedCandidate

	@objc.python_method
	def _normalizedIdentifier(self, text):
		if not text:
			return ''
		return ''.join(ch for ch in text.lower() if ch.isalnum())

	@objc.python_method
	def _canonicalMasterName(self, token):
		if not token:
			return ''
		lookup = getattr(self, '_masterLookup', {}) or {}
		lower = token.lower()
		name = lookup.get(lower)
		if name:
			return name
		normalized = self._normalizedIdentifier(lower)
		return lookup.get(normalized, '')

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
			extraWidth = self._suggestionTypeColumnWidth if hasattr(self, '_suggestionTypeColumnWidth') else 0
			desiredWidth = max(fieldRect.size.width + extraWidth, minWidth)
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
					{
						'title': Glyphs.localize({'en': 'Type', 'fr': 'Type'}),
						'key': 'kind',
						'width': self._suggestionTypeColumnWidth,
						'lineBreakMode': NSLineBreakByTruncatingTail,
					},
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
			width = self._suggestionTypeColumnWidth
			typeColumn.setWidth_(width)
			typeColumn.setMinWidth_(max(40, width - 20))
			typeColumn.setResizingMask_(0)
			cell = typeColumn.dataCell()
			if cell and hasattr(cell, 'setLineBreakMode_'):
				cell.setLineBreakMode_(NSLineBreakByTruncatingTail)
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
		masterTokens = []
		for word in words:
			if word.startswith('/') and len(word) > 1:
				token = word[1:]
				lower = token.lower()
				if categoryKey is None and lower in self._categoryLookup:
					categoryKey = self._categoryLookup[lower]
				elif lower not in self._categoryLookup:
					masterName = self._canonicalMasterName(token)
					if masterName:
						masterTokens.append(masterName)
					else:
						glyphTokens.append(token)
			else:
				cleanWords.append(word)
		cleanText = ' '.join(filter(None, cleanWords)).strip()
		return cleanText, glyphTokens, categoryKey, masterTokens

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
		taskTitle = Glyphs.localize({'en': 'Task', 'fr': 'Tache'})
		if not hasattr(self, '_taskSentenceCell'):
			self._taskSentenceCell = TaskSentenceCell.alloc().init()
		return [
			{
				'title': taskTitle,
				'key': 'sentenceData',
				'editable': False,
				'width': 320,
				'lineBreakMode': NSLineBreakByWordWrapping,
				'cell': self._taskSentenceCell,
			},
		]

	@objc.python_method
	def _buildDoneColumns(self):
		taskTitle = Glyphs.localize({'en': 'Completed Task', 'fr': 'Tache terminee'})
		if not hasattr(self, '_taskSentenceCell'):
			self._taskSentenceCell = TaskSentenceCell.alloc().init()
		return [
			{
				'title': taskTitle,
				'key': 'sentenceData',
				'editable': False,
				'width': 320,
				'lineBreakMode': NSLineBreakByWordWrapping,
				'cell': self._taskSentenceCell,
			},
		]

	@objc.python_method
	def _configureTaskTables(self):
		self._styleListView(self.paletteWindow.group.todoList, self._minimumTaskRowHeight, False)
		self._styleListView(self.paletteWindow.group.doneList, self._minimumTaskRowHeight, False)
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
			tableView.setIntercellSpacing_(NSMakeSize(0, 0))
		except Exception:
			pass
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
		else:
			if scrollView:
				try:
					scrollView.setHasHorizontalScroller_(False)
				except Exception:
					pass
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
	def _categoryKeyForDisplay(self, value):
		if not value:
			return self._categoryKeyFromIndex(0)
		if value in self.categoryKeys:
			return value
		if isinstance(value, str):
			lookup = self._categoryLookup.get(value.lower())
			if lookup:
				return lookup
		return self._categoryKeyFromIndex(0)

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
	def _mastersForTask(self, task):
		masters = []
		if isinstance(task.get('masters'), list):
			masters = [name for name in task.get('masters') if isinstance(name, str)]
		if not masters:
			return []
		normalized = []
		seen = set()
		for name in masters:
			if not name:
				continue
			canonical = self._canonicalMasterName(name) or name
			key = canonical.lower()
			if key in seen:
				continue
			seen.add(key)
			normalized.append(canonical)
		return normalized

	@objc.python_method
	def _openGlyph(self, index):
		font = self._currentFont()
		if font is None:
			return
		task = self.todoItems[index]
		glyphNames = self._glyphsForTask(task)
		masterNames = self._mastersForTask(task)
		if not glyphNames and masterNames:
			self._openMasterGlyphSet(font, masterNames)
			return
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
			if masterNames:
				self._openMasterGlyphSet(font, masterNames)
			return
		self._openLayers(font, layersToOpen)

	@objc.python_method
	def _openMasterGlyphSet(self, font, masterNames):
		if not masterNames:
			return
		orderedGlyphs = self._orderedGlyphs(font)
		if not orderedGlyphs:
			return
		for masterName in masterNames:
			master = self._masterByName(font, masterName)
			if master is None:
				continue
			layers = []
			for glyph in orderedGlyphs:
				layer = None
				try:
					if master.id in glyph.layers:
						layer = glyph.layers[master.id]
				except Exception:
					layer = None
				if layer is None:
					try:
						if glyph.layers:
							layer = glyph.layers[0]
					except Exception:
						layer = None
				if layer:
					layers.append(layer)
			if layers:
				self._openLayers(font, layers)

	@objc.python_method
	def _orderedGlyphs(self, font):
		try:
			glyphs = list(font.glyphs)
		except Exception:
			return []
		try:
			glyphs.sort(key=self._glyphSortKey)
		except Exception:
			pass
		return glyphs

	@objc.python_method
	def _glyphSortKey(self, glyph):
		if glyph is None:
			return ''
		sortName = ''
		try:
			sortName = glyph.sortName()
		except TypeError:
			sortName = getattr(glyph, 'sortName', None)
			if callable(sortName):
				try:
					sortName = sortName()
				except Exception:
					sortName = ''
		except Exception:
			sortName = ''
		if not sortName:
			sortName = getattr(glyph, 'name', '') or ''
		return sortName.lower()

	@objc.python_method
	def _masterByName(self, font, name):
		if not font or not name:
			return None
		targetLower = name.lower()
		for master in getattr(font, 'masters', []):
			masterName = getattr(master, 'name', None)
			if masterName and masterName.lower() == targetLower:
				return master
		return None

	@objc.python_method
	def _openLayers(self, font, layers):
		if not layers:
			return
		document = getattr(font, 'parent', None)
		if document:
			try:
				windowController = document.windowController()
				if windowController:
					windowController.addTabWithLayers_(layers)
					return
			except Exception:
				pass
		try:
			font.newTab(layers)
		except Exception:
			try:
				glyphNames = [layer.parent.name for layer in layers if getattr(layer, 'parent', None)]
			except Exception:
				glyphNames = []
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
		base = Glyphs.localize({'en': 'Completed Tasks (%d)', 'fr': 'Taches terminees (%d)'}) % count
		prefix = '[-] ' if self._doneExpanded else '[+] '
		return prefix + base

	@objc.python_method
	def _updateRowHeights(self):
		self._setListRowHeight(self.paletteWindow.group.todoList, self._fittedRowHeightForList(self.paletteWindow.group.todoList))
		self._setListRowHeight(self.paletteWindow.group.doneList, self._fittedRowHeightForList(self.paletteWindow.group.doneList))

	@objc.python_method
	def _fittedRowHeightForList(self, listView):
		try:
			tableView = listView._tableView
			columns = tableView.tableColumns()
		except Exception:
			return self._minimumTaskRowHeight
		if not columns:
			return self._minimumTaskRowHeight
		try:
			columnWidth = columns[0].width()
		except Exception:
			columnWidth = 0
		if columnWidth <= 0:
			return self._minimumTaskRowHeight
		items = listView.get() or []
		if not items:
			return self._minimumTaskRowHeight
		cell = getattr(self, '_taskSentenceCell', None)
		if cell is None:
			return self._minimumTaskRowHeight
		height = self._minimumTaskRowHeight
		for item in items:
			value = item.get('sentenceData') if isinstance(item, dict) else item
			try:
				height = max(height, cell.heightForValue_width_(value, columnWidth))
			except Exception:
				pass
		return height

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
