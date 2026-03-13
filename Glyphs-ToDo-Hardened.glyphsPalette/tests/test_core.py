from __future__ import print_function, unicode_literals

import os
import sys
import unittest

HERE = os.path.dirname(__file__)
RESOURCES_DIR = os.path.abspath(os.path.join(HERE, '..', 'Contents', 'Resources'))
if RESOURCES_DIR not in sys.path:
	sys.path.insert(0, RESOURCES_DIR)

from core import AutocompleteProvider, TaskListViewModel, TaskParser, TaskStore


class FakeFont(object):
	def __init__(self):
		self.userData = {}


class TaskParserTests(unittest.TestCase):
	def setUp(self):
		self.parser = TaskParser(
			category_lookup={'general': 'General'},
			canonical_master_name=lambda token: 'Regular' if token.lower() == 'regular' else '',
			resolve_glyph_name=lambda token: 'A' if token.lower() == 'a' else token,
			glyph_exists=lambda name: name in {'A'},
			split_trailing_punctuation=self._split_trailing,
		)

	def _split_trailing(self, token):
		core = token
		trailing = ''
		while len(core) > 1 and core[-1] in '.,;:!?)]}':
			trailing = core[-1] + trailing
			core = core[:-1]
		return core, trailing

	def test_unknown_slash_token_stays_text(self):
		descriptor, trailing = self.parser.descriptor_for_inline_token('/unknown')
		self.assertIsNone(descriptor)
		self.assertIsNone(trailing)

	def test_extract_metadata_keeps_unknown_tokens(self):
		clean, glyphs, category, masters = self.parser.extract_metadata('fix /unknown /A /General /Regular.')
		self.assertIn('/unknown', clean)
		self.assertEqual(glyphs, ['A'])
		self.assertEqual(category, 'General')
		self.assertEqual(masters, ['Regular'])
		self.assertIn('.', clean)


class TaskStoreTests(unittest.TestCase):
	def setUp(self):
		self.store = TaskStore(
			defaults_key='com.example.tasks',
			normalize_category=lambda value: value if value else 'General',
			normalize_glyph=lambda value: value.upper(),
			canonical_master=lambda value: value.title(),
		)

	def test_save_and_load_assigns_ids_and_schema(self):
		font = FakeFont()
		tasks = [{'task': 'Review', 'done': False, 'glyphs': ['a', 'A'], 'category': 'General', 'masters': ['regular']}]
		success, error = self.store.save(font, tasks)
		self.assertTrue(success)
		self.assertIsNone(error)
		loaded, fingerprint, load_error = self.store.load(font)
		self.assertIsNone(load_error)
		self.assertTrue(fingerprint)
		self.assertEqual(len(loaded), 1)
		task = loaded[0]
		self.assertTrue(task['id'])
		self.assertEqual(task['glyphs'], ['A'])
		self.assertEqual(task['masters'], ['Regular'])

	def test_load_rejects_invalid_json(self):
		font = FakeFont()
		font.userData['com.example.tasks'] = '{broken json'
		items, fingerprint, error = self.store.load(font)
		self.assertIsNone(items)
		self.assertTrue(fingerprint)
		self.assertIn('valid JSON', error)

	def test_load_rejects_newer_schema(self):
		font = FakeFont()
		font.userData['com.example.tasks'] = '{"schemaVersion": 999, "items": []}'
		items, _fingerprint, error = self.store.load(font)
		self.assertIsNone(items)
		self.assertIn('newer', error)


class ViewModelTests(unittest.TestCase):
	def test_build_uses_ids_and_filter(self):
		tasks = [
			{'id': 'a1', 'task': 'A', 'done': False, 'category': 'General'},
			{'id': 'a2', 'task': 'B', 'done': False, 'category': 'Drawing'},
			{'id': 'd1', 'task': 'C', 'done': True, 'category': 'General'},
		]
		view_model = TaskListViewModel(category_filter='General', sentence_builder=lambda item: {'text': item['task'], 'done': item.get('done', False)})
		data = view_model.build(tasks)
		self.assertEqual(data['activeTaskIds'], ['a1'])
		self.assertEqual(data['doneTaskIds'], ['d1'])
		self.assertEqual(data['indexByTaskId']['a2'], 1)


class AutocompleteTests(unittest.TestCase):
	def test_build_includes_category_glyph_and_master(self):
		provider = AutocompleteProvider(
			localize=lambda mapping: mapping['en'],
			category_keys=['General'],
			glyph_names_getter=lambda: ['A', 'B'],
			master_names_getter=lambda: ['Regular'],
			normalized_identifier=lambda text: ''.join(ch for ch in text.lower() if ch.isalnum()),
		)
		items = provider.build('r')
		labels = [item['label'] for item in items]
		self.assertIn('/Regular', labels)


if __name__ == '__main__':
	unittest.main()
