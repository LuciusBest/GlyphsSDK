# MenuTitle: Regular Alphabet Sketch Overview
# -*- coding: utf-8 -*-
__doc__ = """
Cree un onglet pour le master 'Regular' (insensible a la casse) qui affiche une ligne par
lettre majuscule. Chaque ligne contient le calque du master Regular suivi de tous les
calques associes (sketchs), puis le script ouvre un onglet individuel par sketch du B.
"""

from GlyphsApp import Glyphs, Message, GSBackgroundLayer, GSControlLayer


ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def get_master(font, master_name):
	target = master_name.lower()
	for master in font.masters:
		if master.name.lower() == target:
			return master
	return None


def gather_sketch_layers(glyph, master_id):
	"""
	Retourne les calques non maitres/non speciaux (brouillons) associes au master donne.
	"""
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


def layers_for_letter(font, letter, master):
	glyph = font.glyphs[letter]
	if glyph is None:
		return []

	layers = []
	master_layer = glyph.layers[master.id]
	if master_layer:
		layers.append(master_layer)
	layers.extend(gather_sketch_layers(glyph, master.id))
	return layers


def new_tab_for_alphabet(font, master):
	tab = font.newTab()
	tab.masterIndex = font.masters.index(master)

	tab_layers = []
	for letter in ALPHABET:
		letter_layers = layers_for_letter(font, letter, master)
		tab_layers.extend(letter_layers)
		tab_layers.append(GSControlLayer(10))

	if tab_layers:
		tab_layers.pop()

	if tab_layers:
		tab.layers = tab_layers
	return tab


def show_sketch_tabs(font, master, sketch_layers):
	if not sketch_layers:
		return

	master_index = font.masters.index(master)
	for idx, layer in enumerate(sketch_layers, 1):
		tab = font.newTab()
		tab.masterIndex = master_index
		tab.layers = [layer]
		layer_name = layer.name or f"Sketch {idx}"
		try:
			window = tab.graphicView().window()
			if window is not None:
				window.setTitle_(f"B - {layer_name}")
		except AttributeError:
			pass


def main():
	font = Glyphs.font
	if font is None:
		Message("Alphabet Sketch", "Ouvrez une police avant d'executer ce script.")
		return

	master = get_master(font, "Regular")
	if master is None:
		Message("Alphabet Sketch", "Aucun master nomme 'Regular' dans cette police.")
		return

	b_glyph = font.glyphs["B"]
	b_sketch_layers = gather_sketch_layers(b_glyph, master.id)

	new_tab_for_alphabet(font, master)

	if b_sketch_layers:
		Glyphs.showMacroWindow()
		print(f"{len(b_sketch_layers)} sketch(s) pour B sur le master Regular :")
		for idx, layer in enumerate(b_sketch_layers, 1):
			layer_name = layer.name or f"Sketch {idx}"
			print(f"{idx:02d} - {layer_name}")

	show_sketch_tabs(font, master, b_sketch_layers)


if __name__ == "__main__":
	main()
