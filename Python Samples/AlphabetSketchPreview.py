# MenuTitle: Regular Alphabet Sketch Overview
# -*- coding: utf-8 -*-
__doc__ = """
Cree un onglet pour le master 'Regular' (insensible a la casse) qui affiche une ligne par
lettre majuscule. Chaque ligne contient le calque du master Regular suivi de tous ses
calques associes (sketchs).
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


def main():
	font = Glyphs.font
	if font is None:
		Message("Alphabet Sketch", "Ouvrez une police avant d'executer ce script.")
		return

	master = get_master(font, "Regular")
	if master is None:
		Message("Alphabet Sketch", "Aucun master nomme 'Regular' dans cette police.")
		return

	new_tab_for_alphabet(font, master)


if __name__ == "__main__":
	main()
