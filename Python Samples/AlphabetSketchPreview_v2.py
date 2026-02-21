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
	from vanilla import FloatingWindow, TextBox, CheckBox, Button
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


class SelectionDialog:
	SECTION_KEYS = [
		("UPPERCASE", "uppercase"),
		("LOWERCASE", "lowercase"),
		("PONCTUATION", "punctuation"),
	]

	def __init__(self, controller, masters):
		self.controller = controller
		height = 60 + 22 * (len(masters) + len(self.SECTION_KEYS)) + 40
		self.w = FloatingWindow((360, height), "Alphabet Sketch V2")

		y = 12
		self.w.masterLabel = TextBox((15, y, -15, 17), "Masters disponibles")
		y += 20

		self.master_checks = []
		for master in masters:
			cb = CheckBox((25, y, -25, 20), master.name, value=True)
			self.master_checks.append((master, cb))
			y += 22

		self.w.sectionLabel = TextBox((15, y, -15, 17), "Sections a afficher")
		y += 20

		self.section_checks = []
		for label, key in self.SECTION_KEYS:
			default_value = label == "UPPERCASE"
			cb = CheckBox((25, y, -25, 20), label, value=default_value)
			self.section_checks.append((key, cb))
			y += 22

		self.w.runButton = Button((25, y, 140, 24), "Ouvrir les onglets", callback=self.run)
		self.w.cancelButton = Button((190, y, 140, 24), "Annuler", callback=self.close)

		self.w.open()

	def run(self, sender):
		selected_masters = [master for master, cb in self.master_checks if cb.get()]
		selected_sections = [key for key, cb in self.section_checks if cb.get()]

		if not selected_masters:
			Message("Alphabet Sketch V2", "Selectionnez au moins un master.")
			return
		if not selected_sections:
			Message("Alphabet Sketch V2", "Selectionnez au moins une section.")
			return

		self.close(None)
		self.controller.run_with_options(selected_masters, selected_sections)

	def close(self, sender):
		self.w.close()


class AlphabetSketchPreviewV2:
	def __init__(self):
		self.font = Glyphs.font
		if self.font is None:
			Message("Alphabet Sketch V2", "Ouvrez une police avant d'executer ce script.")
			return
		if not VANILLA_AVAILABLE:
			Message("Alphabet Sketch V2", "Installez Vanilla pour utiliser cette version.")
			return

		self.dialog = SelectionDialog(self, self.font.masters)

	def run_with_options(self, masters, sections):
		for master in masters:
			self.open_tab_for_master(master, sections)

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


def main():
	AlphabetSketchPreviewV2()


if __name__ == "__main__":
	main()
