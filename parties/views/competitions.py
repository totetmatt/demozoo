import datetime
import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Max
from django.shortcuts import get_object_or_404, redirect, render
from read_only_mode import writeable_site_required

from demoscene.models import Edit
from demoscene.utils import result_parser
from demoscene.views.generic import AjaxConfirmationView
from parties.forms import CompetitionForm
from parties.models import Competition, CompetitionPlacing
from platforms.models import Platform
from productions.models import Production, ProductionType, Screenshot


def show(request, competition_id):
    competition = get_object_or_404(Competition, id=competition_id)

    placings = (
        competition.placings.order_by('position', 'production__id')
        .prefetch_related('production__author_nicks__releaser', 'production__author_affiliation_nicks__releaser')
        .defer(
            'production__notes', 'production__author_nicks__releaser__notes',
            'production__author_affiliation_nicks__releaser__notes'
        )
    )
    entry_production_ids = [placing.production_id for placing in placings]
    screenshot_map = Screenshot.select_for_production_ids(entry_production_ids)
    placings = [
        (placing, screenshot_map.get(placing.production_id))
        for placing in placings
    ]

    return render(request, 'competitions/show.html', {
        'competition': competition,
        'placings': placings,
    })


def history(request, competition_id):
    competition = get_object_or_404(Competition, id=competition_id)
    return render(request, 'competitions/history.html', {
        'competition': competition,
        'edits': Edit.for_model(competition, request.user.is_staff),
    })


@writeable_site_required
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
            return redirect('competition_edit', competition.id)
    else:
        competition_form = CompetitionForm(instance=competition, initial={
            'shown_date': competition.shown_date,
        })

    competition_placings = [
        placing.json_data
        for placing in competition.results().prefetch_related(
            'production', 'production__author_nicks', 'production__author_affiliation_nicks',
            'production__platforms', 'production__types',
        )
    ]

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
        'form': competition_form,
        'party': party,
        'competition': competition,
        'competition_json': competition_json,
        'competition_placings_json': competition_placings_json,
        'platforms_json': platforms_json,
        'production_types_json': production_types_json,
        'is_admin': request.user.is_staff,
    })


@writeable_site_required
@login_required
def import_text(request, competition_id):
    if not request.user.is_staff:
        return redirect('competition_edit', competition_id)

    competition = get_object_or_404(Competition, id=competition_id)

    if request.POST:
        current_highest_position = (
            CompetitionPlacing.objects.filter(competition=competition).aggregate(Max('position'))['position__max']
        )
        next_position = (current_highest_position or 0) + 1

        format = request.POST['format']
        if format == 'tsv':
            rows = result_parser.tsv(request.POST['results'])
        elif format == 'pm1':
            rows = result_parser.partymeister_v1(request.POST['results'])
        elif format == 'pm2':
            rows = result_parser.partymeister_v2(request.POST['results'])
        elif format == 'wuhu':
            rows = result_parser.wuhu(request.POST['results'])
        else:
            return redirect('competition_edit', competition_id)

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
                production.platforms.set([competition.platform])

            if competition.production_type:
                production.types.set([competition.production_type])

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

            Edit.objects.create(
                action_type='add_competition_placing', focus=competition, focus2=production,
                description=(
                    u"Added competition placing for %s in %s competition"
                    % (production.title, competition)
                ),
                user=request.user
            )

        return redirect('competition_edit', competition_id)
    else:
        return render(request, 'competitions/import_text.html', {
            'competition': competition,
        })


class DeleteCompetitionView(AjaxConfirmationView):
    html_title = "Deleting %s"
    message = "Are you sure you want to delete the %s competition?"
    action_url_path = 'delete_competition'

    def get_object(self, request, competition_id):
        return Competition.objects.get(id=competition_id)

    def is_permitted(self):
        return self.request.user.is_staff and not self.object.placings.exists()

    def get_redirect_url(self):
        return self.object.party.get_absolute_url()

    def perform_action(self):
        Edit.objects.create(
            action_type='delete_competition', focus=self.object.party,
            description=(u"Deleted competition '%s'" % self.object.name), user=self.request.user
        )

        self.object.delete()

        messages.success(self.request, "%s competition deleted" % self.object.name)
