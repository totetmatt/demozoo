from demoscene.shortcuts import get_object_or_404, render, redirect
from demoscene.models import Competition, CompetitionPlacing, Edit, Platform, ProductionType, Production
from demoscene.forms.party import CompetitionForm
from demoscene.utils import result_parser

from unjoinify import unjoinify
from django.utils import simplejson as json
from django.contrib.auth.decorators import login_required
from django.db.models import Max
import datetime


def show(request, competition_id):
	competition = get_object_or_404(Competition, id=competition_id)

	columns = [
		'id',
		'ranking',
		'score',
		'production__id',
		'production__title',
		'production__supertype',
		'production__unparsed_byline',
		'production__author_nicks__id',
		'production__author_nicks__name',
		'production__author_nicks__releaser__id',
		'production__author_nicks__releaser__is_group',
		'production__author_affiliation_nicks__id',
		'production__author_affiliation_nicks__name',
		'production__author_affiliation_nicks__releaser__id',
		'production__author_affiliation_nicks__releaser__is_group',
	]
	query = '''
		SELECT
			demoscene_competitionplacing.id AS id,
			demoscene_competitionplacing.ranking AS ranking,
			demoscene_competitionplacing.score AS score,
			demoscene_production.id AS production__id,
			demoscene_production.title AS production__title,
			demoscene_production.supertype AS production__supertype,
			demoscene_production.unparsed_byline AS production__unparsed_byline,
			author_nick.id AS production__author_nicks__id,
			author_nick.name AS production__author_nicks__name,
			author.id AS production__author_nicks__releaser__id,
			author.is_group AS production__author_nicks__releaser__is_group,
			affiliation_nick.id AS production__author_affiliation_nicks__id,
			affiliation_nick.name AS production__author_affiliation_nicks__name,
			affiliation.id AS production__author_affiliation_nicks__releaser__id,
			affiliation.is_group AS production__author_affiliation_nicks__releaser__is_group
		FROM demoscene_competitionplacing
		LEFT JOIN demoscene_production ON (demoscene_competitionplacing.production_id = demoscene_production.id)
		LEFT JOIN demoscene_production_author_nicks ON (demoscene_production_author_nicks.production_id = demoscene_production.id)
		LEFT JOIN demoscene_nick AS author_nick ON (demoscene_production_author_nicks.nick_id = author_nick.id)
		LEFT JOIN demoscene_releaser AS author ON (author_nick.releaser_id = author.id)
		LEFT JOIN demoscene_production_author_affiliation_nicks ON (demoscene_production_author_affiliation_nicks.production_id = demoscene_production.id)
		LEFT JOIN demoscene_nick AS affiliation_nick ON (demoscene_production_author_affiliation_nicks.nick_id = affiliation_nick.id)
		LEFT JOIN demoscene_releaser AS affiliation ON (affiliation_nick.releaser_id = affiliation.id)
		WHERE demoscene_competitionplacing.competition_id = %s
		ORDER BY
			demoscene_competitionplacing.position,
			demoscene_production.id, author_nick.id, affiliation_nick.id
	'''
	placings = unjoinify(CompetitionPlacing, query, (competition.id,), columns)

	return render(request, 'competitions/show.html', {
		'competition': competition,
		'placings': placings,
	})


def history(request, competition_id):
	competition = get_object_or_404(Competition, id=competition_id)
	return render(request, 'competitions/history.html', {
		'competition': competition,
		'edits': Edit.for_model(competition),
	})


@login_required
def edit(request, competition_id):
	competition = get_object_or_404(Competition, id=competition_id)
	party = competition.party

	if request.method == 'POST':
		competition_form = CompetitionForm(request.POST, instance=competition)
		if competition_form.is_valid():
			competition.shown_date = competition_form.cleaned_data['shown_date']
			competition_form.save()
			competition_form.log_edit(request.user)
			return redirect('competition_edit', args=[competition.id])
	else:
		competition_form = CompetitionForm(instance=competition, initial={
			'shown_date': competition.shown_date,
		})

	competition_placings = [placing.json_data for placing in competition.results()]

	competition_placings_json = json.dumps(competition_placings)

	platforms = Platform.objects.all()
	platforms_json = json.dumps([[p.id, p.name] for p in platforms])

	production_types = ProductionType.objects.all()
	production_types_json = json.dumps([[p.id, p.name] for p in production_types])

	competition_json = json.dumps({
		'id': competition.id,
		'platformId': competition.platform_id,
		'productionTypeId': competition.production_type_id,
	})

	return render(request, 'competitions/edit.html', {
		'html_title': "Editing %s %s competition" % (party.name, competition.name),
		'form': competition_form,
		'party': party,
		'competition': competition,
		'competition_json': competition_json,
		'competition_placings_json': competition_placings_json,
		'platforms_json': platforms_json,
		'production_types_json': production_types_json,
		'is_admin': request.user.is_staff,
	})


@login_required
def import_text(request, competition_id):
	if not request.user.is_staff:
		return redirect('competition_edit', args=[competition_id])

	competition = get_object_or_404(Competition, id=competition_id)

	if request.POST:
		current_highest_position = CompetitionPlacing.objects.filter(competition=competition).aggregate(Max('position'))['position__max']
		next_position = (current_highest_position or 0) + 1

		format = request.POST['format']
		if format == 'tsv':
			rows = result_parser.tsv(request.POST['results'])
		elif format == 'pm1':
			rows = result_parser.partymeister(request.POST['results'])
		elif format == 'pm2':
			rows = result_parser.partymeister(request.POST['results'], author_separator=' by ')
		else:
			return redirect('competition_edit', args=[competition_id])

		for placing, title, byline, score in rows:
			if not title:
				continue

			production = Production(
				release_date=competition.shown_date,
				updated_at=datetime.datetime.now(),
				has_bonafide_edits=False,
				title=title)
			production.save()  # assign an ID so that associations work

			if competition.platform:
				production.platforms = [competition.platform]

			if competition.production_type:
				production.types = [competition.production_type]

			if byline:
				production.byline_string = byline

			production.supertype = production.inferred_supertype
			production.save()

			placing = CompetitionPlacing(
				production=production,
				competition=competition,
				ranking=placing,
				position=next_position,
				score=score,
			)
			next_position += 1
			placing.save()

			Edit.objects.create(action_type='add_competition_placing', focus=competition, focus2=production,
				description=(u"Added competition placing for %s in %s competition" % (production.title, competition)), user=request.user)

		return redirect('competition_edit', args=[competition_id])
	else:
		return render(request, 'competitions/import_text.html', {
			'competition': competition,
		})
