# encoding: utf-8
from __future__ import division, print_function, unicode_literals

import json
import uuid


DEFAULT_SCHEMA_VERSION = 2


class TaskStoreError(Exception):
	pass


class TaskStore(object):
	def __init__(self, defaults_key, schema_version=DEFAULT_SCHEMA_VERSION, normalize_category=None, normalize_glyph=None, canonical_master=None):
		self.defaults_key = defaults_key
		self.schema_version = schema_version
		self._normalize_category = normalize_category or (lambda value: value)
		self._normalize_glyph = normalize_glyph or (lambda value: value)
		self._canonical_master = canonical_master or (lambda value: value)

	def read_raw_payload(self, font):
		if font is None:
			return None
		try:
			return font.userData.get(self.defaults_key)
		except Exception:
			return None

	def payload_fingerprint(self, payload):
		if payload is None:
			return ''
		if isinstance(payload, str):
			return payload
		try:
			return json.dumps(payload, sort_keys=True, ensure_ascii=False)
		except Exception:
			try:
				return repr(payload)
			except Exception:
				return ''

	def save(self, font, tasks):
		if font is None:
			return False, 'No open font.'
		try:
			normalized = [self._normalize_task(task) for task in (tasks or [])]
		except TaskStoreError as error:
			return False, str(error)
		except Exception as error:
			return False, 'Task normalization failed: %s' % error
		payload_obj = {
			'schemaVersion': self.schema_version,
			'items': normalized,
		}
		try:
			serialized = json.dumps(payload_obj, ensure_ascii=False)
		except Exception as error:
			return False, 'Task serialization failed: %s' % error
		try:
			font.userData[self.defaults_key] = serialized
			return True, None
		except Exception as error:
			return False, 'Unable to write tasks to font.userData: %s' % error

	def load(self, font):
		payload = self.read_raw_payload(font)
		fingerprint = self.payload_fingerprint(payload)
		if payload in (None, ''):
			return [], fingerprint, None
		try:
			decoded = self._decode_payload(payload)
		except TaskStoreError as error:
			return None, fingerprint, str(error)
		try:
			items = self._extract_items(decoded)
		except TaskStoreError as error:
			return None, fingerprint, str(error)
		normalized = []
		for entry in items:
			try:
				task = self._normalize_task(entry)
			except TaskStoreError as error:
				return None, fingerprint, str(error)
			if task.get('task'):
				normalized.append(task)
		return normalized, fingerprint, None

	def _decode_payload(self, payload):
		if isinstance(payload, str):
			try:
				return json.loads(payload)
			except Exception:
				raise TaskStoreError('Stored tasks are not valid JSON.')
		if isinstance(payload, (list, dict)):
			return payload
		try:
			return json.loads(json.dumps(payload))
		except Exception:
			raise TaskStoreError('Stored tasks use an unsupported data format.')

	def _extract_items(self, decoded):
		if isinstance(decoded, list):
			return decoded
		if isinstance(decoded, dict):
			if 'items' in decoded:
				version = decoded.get('schemaVersion', 1)
				if not isinstance(version, int):
					raise TaskStoreError('Stored task schemaVersion must be an integer.')
				if version > self.schema_version:
					raise TaskStoreError('Stored task schemaVersion %d is newer than supported %d.' % (version, self.schema_version))
				items = decoded.get('items')
				if not isinstance(items, list):
					raise TaskStoreError('Stored task payload.items must be a list.')
				return items
			return [decoded]
		raise TaskStoreError('Stored tasks must be a list or dictionary.')

	def _normalize_task(self, entry):
		if isinstance(entry, str):
			entry = {
				'task': entry,
				'done': False,
			}
		if not isinstance(entry, dict):
			raise TaskStoreError('Task entry must be a dictionary or string.')

		task_id = entry.get('id')
		if not isinstance(task_id, str) or not task_id.strip():
			task_id = uuid.uuid4().hex
		else:
			task_id = task_id.strip()

		raw_task = entry.get('rawTask')
		if raw_task is not None and not isinstance(raw_task, str):
			raw_task = None

		task = entry.get('task')
		if task is None and isinstance(raw_task, str):
			task = raw_task
		if task is None:
			task = ''
		if not isinstance(task, str):
			try:
				task = str(task)
			except Exception:
				task = ''
		task = task.strip()

		done = bool(entry.get('done', False))

		glyph_tokens = []
		stored_glyphs = entry.get('glyphs')
		if isinstance(stored_glyphs, list):
			for name in stored_glyphs:
				if isinstance(name, str) and name.strip():
					glyph_tokens.append(name.strip())
		elif isinstance(entry.get('glyph'), str) and entry.get('glyph').strip():
			glyph_tokens.append(entry.get('glyph').strip())
		glyphs = self._normalize_glyphs(glyph_tokens)

		masters = []
		stored_masters = entry.get('masters')
		if isinstance(stored_masters, list):
			for name in stored_masters:
				if not isinstance(name, str) or not name.strip():
					continue
				canonical = self._canonical_master(name.strip()) or name.strip()
				if canonical:
					masters.append(canonical)
		masters = self._dedupe_preserve_order_case_insensitive(masters)

		category = self._normalize_category(entry.get('category'))

		return {
			'id': task_id,
			'task': task,
			'rawTask': raw_task,
			'done': done,
			'glyph': glyphs[0] if glyphs else '',
			'glyphs': glyphs,
			'category': category,
			'masters': masters,
		}

	def _normalize_glyphs(self, names):
		resolved = []
		for name in names or []:
			glyph_name = self._normalize_glyph(name)
			if not glyph_name:
				continue
			resolved.append(glyph_name)
		return self._dedupe_preserve_order_case_insensitive(resolved)

	def _dedupe_preserve_order_case_insensitive(self, values):
		seen = set()
		result = []
		for value in values:
			key = value.lower()
			if key in seen:
				continue
			seen.add(key)
			result.append(value)
		return result


class TaskParser(object):
	def __init__(self, category_lookup, canonical_master_name, resolve_glyph_name, glyph_exists, split_trailing_punctuation):
		self.category_lookup = category_lookup
		self.canonical_master_name = canonical_master_name
		self.resolve_glyph_name = resolve_glyph_name
		self.glyph_exists = glyph_exists
		self.split_trailing_punctuation = split_trailing_punctuation

	def detect_slash_token(self, text, cursor):
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

	def descriptor_for_inline_token(self, token):
		if not token.startswith('/') or len(token) <= 1:
			return (None, None)
		core, trailing_text = self.split_trailing_punctuation(token)
		if len(core) <= 1:
			return (None, None)
		label = core[1:]
		lower = label.lower()
		if lower in self.category_lookup:
			category_key = self.category_lookup[lower]
			return ({'type': 'category', 'label': category_key, 'categoryKey': category_key}, trailing_text)
		master_name = self.canonical_master_name(label)
		if master_name:
			return ({'type': 'master', 'label': master_name}, trailing_text)
		glyph_name = self.resolve_glyph_name(label)
		if glyph_name and self.glyph_exists(glyph_name):
			return ({'type': 'glyph', 'label': glyph_name}, trailing_text)
		return (None, None)

	def extract_metadata(self, text):
		words = (text or '').split()
		clean_words = []
		glyph_tokens = []
		category_key = None
		master_tokens = []
		for word in words:
			if not word.startswith('/') or len(word) <= 1:
				clean_words.append(word)
				continue
			core, trailing = self.split_trailing_punctuation(word)
			if len(core) <= 1:
				clean_words.append(word)
				continue
			token = core[1:]
			lower = token.lower()
			if category_key is None and lower in self.category_lookup:
				category_key = self.category_lookup[lower]
				if trailing:
					clean_words.append(trailing)
				continue
			master_name = self.canonical_master_name(token)
			if master_name:
				master_tokens.append(master_name)
				if trailing:
					clean_words.append(trailing)
				continue
			glyph_name = self.resolve_glyph_name(token)
			if glyph_name and self.glyph_exists(glyph_name):
				glyph_tokens.append(glyph_name)
				if trailing:
					clean_words.append(trailing)
				continue
			clean_words.append(word)
		clean_text = ' '.join([word for word in clean_words if word]).strip()
		return clean_text, glyph_tokens, category_key, master_tokens


class AutocompleteProvider(object):
	def __init__(self, localize, category_keys, glyph_names_getter, master_names_getter, normalized_identifier):
		self.localize = localize
		self.category_keys = category_keys
		self.glyph_names_getter = glyph_names_getter
		self.master_names_getter = master_names_getter
		self.normalized_identifier = normalized_identifier

	def build(self, prefix):
		prefix_lower = (prefix or '').lower()
		items = []
		for key in self.category_keys:
			if not prefix_lower or key.lower().startswith(prefix_lower):
				items.append({
					'label': '/%s' % key,
					'kind': self.localize({'en': 'Category', 'fr': 'Categorie'}),
					'type': 'category',
					'value': key,
				})
		glyph_limit = 50 if prefix_lower else 25
		glyph_count = 0
		for name in self.glyph_names_getter() or []:
			if prefix_lower and not name.lower().startswith(prefix_lower):
				continue
			items.append({
				'label': '/%s' % name,
				'kind': self.localize({'en': 'Glyph', 'fr': 'Glyphe'}),
				'type': 'glyph',
				'value': name,
			})
			glyph_count += 1
			if glyph_count >= glyph_limit:
				break
		for master_name in self.master_names_getter() or []:
			if self._matches_relaxed_prefix(prefix_lower, master_name):
				items.append({
					'label': '/%s' % master_name,
					'kind': self.localize({'en': 'Master', 'fr': 'Master'}),
					'type': 'master',
					'value': master_name,
				})
		return items

	def _matches_relaxed_prefix(self, prefix_lower, candidate):
		if not prefix_lower:
			return True
		candidate_lower = candidate.lower()
		if candidate_lower.startswith(prefix_lower):
			return True
		normalized_prefix = self.normalized_identifier(prefix_lower)
		normalized_candidate = self.normalized_identifier(candidate_lower)
		return bool(normalized_prefix) and normalized_prefix in normalized_candidate


class TaskListViewModel(object):
	def __init__(self, category_filter, sentence_builder):
		self.category_filter = category_filter
		self.sentence_builder = sentence_builder

	def build(self, tasks):
		active_items = []
		done_items = []
		active_ids = []
		done_ids = []
		index_by_id = {}
		for index, item in enumerate(tasks or []):
			if not isinstance(item, dict):
				continue
			task_id = item.get('id')
			if not isinstance(task_id, str) or not task_id:
				continue
			index_by_id[task_id] = index
			display_item = {
				'taskId': task_id,
				'task': item.get('task', ''),
				'sentenceData': self.sentence_builder(item),
			}
			if item.get('done'):
				done_items.append(display_item)
				done_ids.append(task_id)
			else:
				if self.category_filter and item.get('category') != self.category_filter:
					continue
				active_items.append(display_item)
				active_ids.append(task_id)
		return {
			'activeItems': active_items,
			'doneItems': done_items,
			'activeTaskIds': active_ids,
			'doneTaskIds': done_ids,
			'indexByTaskId': index_by_id,
		}
