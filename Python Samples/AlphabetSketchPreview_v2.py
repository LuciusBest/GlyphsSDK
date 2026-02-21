# MenuTitle: Regular Alphabet Sketch Overview v2
# -*- coding: utf-8 -*-
__doc__ = """
Version interactive du script AlphabetSketchPreview : propose une fenetre de selection
des masters disponibles ainsi que des categories (UPPERCASE, LOWERCASE, PONCTUATION).
Chaque combinaison master/options ouvre un onglet unique regroupant toutes les lettres
et leurs calques associes.
"""

from GlyphsApp import Glyphs, Message, GSBackgroundLayer, GSControlLayer

try:
	from vanilla import FloatingWindow, TextBox, CheckBox, Button, List, CheckBoxListCell, EditText
	VANILLA_AVAILABLE = True
except Exception:
	VANILLA_AVAILABLE = False


UPPERCASE_GLYPHS = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
LOWERCASE_GLYPHS = list("abcdefghijklmnopqrstuvwxyz")
PUNCTUATION_GLYPHS = [
	"period",
	"comma",
	"semicolon",
	"colon",
	"question",
	"exclam",
	"hyphen",
	"endash",
	"emdash",
	"parenleft",
	"parenright",
]


def gather_sketch_layers(glyph, master_id):
	if glyph is None:
		return []

	sketch_layers = []
	for layer in glyph.layers:
		if layer.associatedMasterId != master_id:
			continue
		if layer.isMasterLayer or layer.isSpecialLayer:
			continue
		if isinstance(layer, GSBackgroundLayer):
			continue
		sketch_layers.append(layer)
	return sketch_layers


def glyph_layers(font, glyph_name, master):
	glyph = font.glyphs[glyph_name]
	if glyph is None:
		return []

	layers = []
	master_layer = glyph.layers[master.id]
	if master_layer:
		layers.append(master_layer)
	layers.extend(gather_sketch_layers(glyph, master.id))
	return layers


def layers_from_text(font, master, text):
	layers = []
	for char in text:
		if char == "\n":
			layers.append(GSControlLayer(10))
			continue
		if char == " ":
			layers.append(GSControlLayer(32))
			continue
		glyph = font.glyphs[char]
		if glyph:
			layer = glyph.layers[master.id]
			if layer:
				layers.append(layer)
	return layers


class SelectionDialog:
	SECTION_KEYS = [
		("UPPERCASE", "uppercase"),
		("LOWERCASE", "lowercase"),
		("PONCTUATION", "punctuation"),
	]

	def __init__(self, controller, font):
		self.controller = controller
		self.font = font
		masters = font.masters
		self.glyph_names = [glyph.name for glyph in font.glyphs]

		list_height = min(200, 24 * max(1, len(self.glyph_names)))
		height = 120 + 22 * (len(masters) + len(self.SECTION_KEYS)) + list_height + 120
		self.w = FloatingWindow((420, height), "Alphabet Sketch V2")

		y = 12
		self.w.masterLabel = TextBox((15, y, -15, 17), "Masters disponibles")
		y += 20

		self.master_checks = []
		for idx, master in enumerate(masters):
			attr = f"masterCheck{idx}"
			cb = CheckBox((25, y, -25, 20), master.name, value=True)
			setattr(self.w, attr, cb)
			self.master_checks.append((master, cb))
			y += 22

		self.w.sectionLabel = TextBox((15, y, -15, 17), "Sections a afficher")
		y += 20

		self.section_checks = []
		for idx, (label, key) in enumerate(self.SECTION_KEYS):
			default_value = label == "UPPERCASE"
			attr = f"sectionCheck{idx}"
			cb = CheckBox((25, y, -25, 20), label, value=default_value)
			setattr(self.w, attr, cb)
			self.section_checks.append((key, cb))
			y += 22

		self.w.compareLabel = TextBox((15, y, -15, 17), "Compare all masters")
		y += 20

		self.w.compareCheck = CheckBox((25, y, -25, 20), "Activer la comparaison", value=False, callback=self.toggle_compare_options)
		y += 28

		column_descriptions = [
			{"title": "Inclure", "key": "include", "editable": True, "width": 70, "cell": CheckBoxListCell()},
			{"title": "Glyphe", "key": "glyph", "editable": False},
		]
		glyph_items = [{"include": False, "glyph": name} for name in self.glyph_names]
		self.w.glyphList = List((25, y, -25, list_height), glyph_items, columnDescriptions=column_descriptions, showColumnTitles=True)
		self.w.glyphList.enable(False)
		y += list_height + 8

		self.w.selectAllGlyphs = Button((25, y, 140, 24), "Tout cocher", callback=self.select_all_glyphs)
		self.w.clearGlyphs = Button((180, y, 140, 24), "Tout decocher", callback=self.clear_glyphs)
		self.w.selectAllGlyphs.enable(False)
		self.w.clearGlyphs.enable(False)
		y += 36

		self.w.textLabel = TextBox((15, y, -15, 17), "Texte libre (optionnel)")
		y += 20
		self.w.textInput = EditText((25, y, -25, 22), "", placeholder="Entrez un mot ou une phrase")
		y += 32

		self.w.runButton = Button((25, y, 140, 24), "Ouvrir les onglets", callback=self.run)
		self.w.cancelButton = Button((190, y, 140, 24), "Annuler", callback=self.close)

		self.w.open()

	def run(self, sender):
		selected_masters = [master for master, cb in self.master_checks if cb.get()]
		selected_sections = [key for key, cb in self.section_checks if cb.get()]
		compare_enabled = self.w.compareCheck.get()
		selected_glyphs = self.selected_compare_glyphs() if compare_enabled else []
		text_input = (self.w.textInput.get() or "").strip()

		if not selected_masters:
			Message("Alphabet Sketch V2", "Selectionnez au moins un master.")
			return
		if not selected_sections and not compare_enabled and not text_input:
			Message("Alphabet Sketch V2", "Selectionnez au moins une section, une comparaison ou saisissez du texte.")
			return
		if compare_enabled and not selected_glyphs:
			Message("Alphabet Sketch V2", "Selectionnez au moins un glyphe pour la comparaison.")
			return

		self.close(None)
		self.controller.run_with_options(
			selected_masters,
			selected_sections,
			compare_enabled,
			selected_glyphs,
			text_input,
		)

	def close(self, sender):
		self.w.close()

	def toggle_compare_options(self, sender):
		state = bool(sender.get())
		self.w.glyphList.enable(state)
		self.w.selectAllGlyphs.enable(state)
		self.w.clearGlyphs.enable(state)

	def select_all_glyphs(self, sender):
		data = self.w.glyphList.get()
		for item in data:
			item["include"] = True
		self.w.glyphList.set(data)

	def clear_glyphs(self, sender):
		data = self.w.glyphList.get()
		for item in data:
			item["include"] = False
		self.w.glyphList.set(data)

	def selected_compare_glyphs(self):
		return [item["glyph"] for item in self.w.glyphList.get() if item.get("include")]


class AlphabetSketchPreviewV2:
	def __init__(self):
		self.font = Glyphs.font
		if self.font is None:
			Message("Alphabet Sketch V2", "Ouvrez une police avant d'executer ce script.")
			return
		if not VANILLA_AVAILABLE:
			Message("Alphabet Sketch V2", "Installez Vanilla pour utiliser cette version.")
			return

		self.dialog = SelectionDialog(self, self.font)

	def run_with_options(self, masters, sections, compare_enabled=False, compare_glyphs=None, text_input=""):
		compare_glyphs = compare_glyphs or []

		for master in masters:
			self.open_tab_for_master(master, sections)
		if compare_enabled and compare_glyphs:
			self.open_comparison_tab(masters, compare_glyphs)
		if text_input:
			self.open_text_tab(masters, text_input)

	def open_tab_for_master(self, master, sections):
		tab = self.font.newTab()
		tab.masterIndex = self.font.masters.index(master)
		tab_layers = []

		for section in sections:
			glyph_names = self.section_glyphs(section)
			section_has_content = False
			for glyph_name in glyph_names:
				layers = glyph_layers(self.font, glyph_name, master)
				if not layers:
					continue
				tab_layers.extend(layers)
				tab_layers.append(GSControlLayer(10))
				section_has_content = True
			if section_has_content:
				tab_layers.append(GSControlLayer(10))

		while tab_layers and isinstance(tab_layers[-1], GSControlLayer):
			tab_layers.pop()

		if tab_layers:
			tab.layers = tab_layers

	def section_glyphs(self, section_key):
		if section_key == "uppercase":
			return UPPERCASE_GLYPHS
		if section_key == "lowercase":
			return LOWERCASE_GLYPHS
		if section_key == "punctuation":
			return PUNCTUATION_GLYPHS
		return []

	def open_comparison_tab(self, masters, glyph_names):
		if not masters or not glyph_names:
			return

		tab = self.font.newTab()
		tab.masterIndex = self.font.masters.index(masters[0])
		tab_layers = []

		for glyph_name in glyph_names:
			per_master_layers = []
			max_layers = 0
			for master in masters:
				layers = glyph_layers(self.font, glyph_name, master)
				per_master_layers.append(layers)
				if len(layers) > max_layers:
					max_layers = len(layers)

			for layer_index in range(max_layers):
				for layers in per_master_layers:
					if layer_index < len(layers):
						tab_layers.append(layers[layer_index])
				tab_layers.append(GSControlLayer(10))

			tab_layers.append(GSControlLayer(10))

		while tab_layers and isinstance(tab_layers[-1], GSControlLayer):
			tab_layers.pop()

		if tab_layers:
			tab.layers = tab_layers

	def open_text_tab(self, masters, text):
		text = text.strip()
		if not text:
			return

		tab = self.font.newTab()
		tab.masterIndex = self.font.masters.index(masters[0])
		tab_layers = []

		for master in masters:
			line_text = f"{text} {master.name}"
			line_layers = layers_from_text(self.font, master, line_text)
			if not line_layers:
				continue
			tab_layers.extend(line_layers)
			tab_layers.append(GSControlLayer(10))

		while tab_layers and isinstance(tab_layers[-1], GSControlLayer):
			tab_layers.pop()

		if tab_layers:
			tab.layers = tab_layers


def main():
	AlphabetSketchPreviewV2()


if __name__ == "__main__":
	main()
