# MenuTitle: Regular Alphabet Sketch Overview
# -*- coding: utf-8 -*-
__doc__ = """
Cree un onglet pour le master 'Regular' avec l'alphabet (une lettre par ligne) en repetant
la ligne du B autant de fois qu'il existe de calques brouillon pour ce glyph, puis ouvre
un onglet dedie pour chaque sketch afin de pouvoir les inspecter.
"""

from GlyphsApp import Glyphs, Message, GSBackgroundLayer


ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def get_master(font, master_name):
	for master in font.masters:
		if master.name == master_name:
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


def new_tab_for_alphabet(font, master, b_sketch_count):
	lines = []
	for letter in ALPHABET:
		if letter == "B":
			repeat_count = max(b_sketch_count, 1)
			lines.append(" ".join("B" for _ in range(repeat_count)))
		else:
			lines.append(letter)

	tab = font.newTab("\n".join(lines))
	tab.masterIndex = font.masters.index(master)
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

	new_tab_for_alphabet(font, master, len(b_sketch_layers))

	if b_sketch_layers:
		Glyphs.showMacroWindow()
		print(f"{len(b_sketch_layers)} sketch(s) pour B sur le master Regular :")
		for idx, layer in enumerate(b_sketch_layers, 1):
			layer_name = layer.name or f"Sketch {idx}"
			print(f"{idx:02d} - {layer_name}")

	show_sketch_tabs(font, master, b_sketch_layers)


if __name__ == "__main__":
	main()
