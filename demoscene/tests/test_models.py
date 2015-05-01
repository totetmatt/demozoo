from __future__ import unicode_literals

import datetime

from django.test import TestCase

from demoscene.models import Releaser, Nick
from productions.models import Production


class TestReleaser(TestCase):
	def setUp(self):
		self.gasman = Releaser.objects.create(
			name="Gasman",
			is_group=False,
			updated_at=datetime.datetime.now()  # FIXME: having to pass updated_at is silly
		)
		self.hooy_program = Releaser.objects.create(
			name="Hooy-Program",
			is_group=True,
			updated_at=datetime.datetime.now()
		)

	def test_releaser_nick_creation(self):
		# creating a releaser should create a corresponding Nick object
		self.assertEqual(Nick.objects.filter(name="Gasman").count(), 1)

	def test_string_repr(self):
		self.assertEqual(str(self.gasman), "Gasman")

	def test_search_template(self):
		self.assertEqual(
			self.gasman.search_result_template(),
			'search/results/scener.html'
		)

		self.assertEqual(
			self.hooy_program.search_result_template(),
			'search/results/group.html'
		)

	def test_url(self):
		self.assertEqual(
			self.gasman.get_absolute_url(),
			'/sceners/%d/' % self.gasman.id
		)

		self.assertEqual(
			self.hooy_program.get_absolute_url(),
			'/groups/%d/' % self.hooy_program.id
		)

	def test_history_url(self):
		self.assertEqual(
			self.gasman.get_history_url(),
			'/sceners/%d/history/' % self.gasman.id
		)

		self.assertEqual(
			self.hooy_program.get_history_url(),
			'/groups/%d/history/' % self.hooy_program.id
		)


class TestReleaserProductions(TestCase):
	def setUp(self):
		self.gasman = Releaser.objects.create(
			name="Gasman",
			is_group=False,
			updated_at=datetime.datetime.now()
		)
		self.gasman_nick = self.gasman.nicks.get(name="Gasman")
		self.shingebis_nick = Nick.objects.create(
			releaser=self.gasman,
			name="Shingebis"
		)

		self.madrielle = Production.objects.create(
			title="Madrielle",
			updated_at=datetime.datetime.now()
		)
		self.madrielle.author_nicks.add(self.gasman_nick)

		self.mooncheese = Production.objects.create(
			title="Mooncheese",
			updated_at=datetime.datetime.now()
		)
		self.mooncheese.author_nicks.add(self.shingebis_nick)

	def test_get_productions(self):
		gasman_productions = self.gasman.productions().order_by('title')
		self.assertEqual(
			list(gasman_productions.values_list('title', flat=True)),
			["Madrielle", "Mooncheese"]
		)