import datetime

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models.functions import Lower
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from read_only_mode import writeable_site_required

from demoscene.forms.releaser import (
    CreateScenerForm, ScenerEditLocationForm, ScenerEditRealNameForm, ScenerMembershipForm
)
from demoscene.models import Edit, Membership, Nick, Releaser
from demoscene.shortcuts import get_page, simple_ajax_form
from demoscene.views.generic import AjaxConfirmationView


def index(request):

    nick_page = get_page(
        Nick.objects.filter(releaser__is_group=False).extra(
            select={'lower_name': 'lower(demoscene_nick.name)'}
        ).order_by('lower_name'),
        request.GET.get('page', '1'))

    return render(request, 'sceners/index.html', {
        'nick_page': nick_page,
    })


def show(request, scener_id, edit_mode=False):
    scener = get_object_or_404(Releaser, id=scener_id)
    if scener.is_group:
        return HttpResponseRedirect(scener.get_absolute_url())

    can_edit_real_names = request.user.has_perm('demoscene.change_releaser_real_names')

    external_links = scener.active_external_links.select_related('releaser').defer('releaser__notes')
    if not request.user.is_staff:
        external_links = external_links.exclude(link_class='SlengpungUser')

    external_links = sorted(external_links, key=lambda obj: obj.sort_key)

    parties_organised = (
        scener.parties_organised.select_related('party').defer('party__notes').order_by('-party__start_date_date')
    )
    # order by -role to get Sysop before Co-sysop.
    # Will need to come up with something less hacky if more roles are added :-)
    bbses_operated = (
        scener.bbses_operated.select_related('bbs').defer('bbs__notes')
        .order_by('-is_current', '-role', 'bbs__name')
    )

    return render(request, 'sceners/show.html', {
        'scener': scener,
        'alternative_nicks': scener.alternative_nicks.prefetch_related('variants'),
        'external_links': external_links,
        'editing_groups': (request.GET.get('editing') == 'groups'),
        'editing_nicks': (request.GET.get('editing') == 'nicks'),
        'memberships': (
            scener.group_memberships.select_related('group').defer('group__notes')
            .order_by('-is_current', Lower('group__name'))
        ),
        'parties_organised': parties_organised,
        'bbses_operated': bbses_operated,
        'can_edit_real_names': can_edit_real_names,
        'prompt_to_edit': settings.SITE_IS_WRITEABLE and (request.user.is_staff or not scener.locked),
        'show_locked_button': request.user.is_authenticated and scener.locked,
        'show_lock_button': request.user.is_staff and settings.SITE_IS_WRITEABLE and not scener.locked,
    })


def history(request, scener_id):
    scener = get_object_or_404(Releaser, is_group=False, id=scener_id)
    return render(request, 'sceners/history.html', {
        'scener': scener,
        'edits': Edit.for_model(scener, request.user.is_staff),
    })


@writeable_site_required
@login_required
def edit_location(request, scener_id):
    scener = get_object_or_404(Releaser, is_group=False, id=scener_id)

    if not scener.editable_by_user(request.user):
        raise PermissionDenied

    def success(form):
        form.log_edit(request.user)

    return simple_ajax_form(
        request, 'scener_edit_location', scener, ScenerEditLocationForm,
        title='Editing location for %s:' % scener.name,
        update_datestamp=True, on_success=success
    )


@writeable_site_required
@login_required
def edit_real_name(request, scener_id):
    scener = get_object_or_404(Releaser, is_group=False, id=scener_id)
    if not request.user.has_perm('demoscene.view_releaser_real_names'):
        return HttpResponseRedirect(scener.get_absolute_url())

    def success(form):
        form.log_edit(request.user)

    return simple_ajax_form(
        request, 'scener_edit_real_name', scener, ScenerEditRealNameForm,
        title="Editing %s's real name:" % scener.name,
        update_datestamp=True, on_success=success, ajax_submit=request.GET.get('ajax_submit')
    )


@writeable_site_required
@login_required
def create(request):
    if request.method == 'POST':
        form = CreateScenerForm(request.POST)
        if form.is_valid():
            scener = form.save()
            form.log_creation(request.user)
            return HttpResponseRedirect(scener.get_absolute_url())
    else:
        form = CreateScenerForm()

    return render(request, 'shared/simple_form.html', {
        'form': form,
        'html_title': "New scener",
        'title': "New scener",
        'action_url': reverse('new_scener'),
    })


@writeable_site_required
@login_required
def add_group(request, scener_id):
    scener = get_object_or_404(Releaser, is_group=False, id=scener_id)

    if not scener.editable_by_user(request.user):
        raise PermissionDenied

    if request.method == 'POST':
        form = ScenerMembershipForm(request.POST)
        if form.is_valid():
            group = form.cleaned_data['group_nick'].commit().releaser
            if not scener.group_memberships.filter(group=group).count():
                membership = Membership(
                    member=scener,
                    group=form.cleaned_data['group_nick'].commit().releaser,
                    is_current=form.cleaned_data['is_current']
                )
                membership.save()
                scener.updated_at = datetime.datetime.now()
                scener.save()
                description = u"Added %s as a member of %s" % (scener.name, group.name)
                Edit.objects.create(
                    action_type='add_membership', focus=scener, focus2=group,
                    description=description, user=request.user
                )
            return HttpResponseRedirect(scener.get_absolute_url() + "?editing=groups")
    else:
        form = ScenerMembershipForm()

    return render(request, 'sceners/add_group.html', {
        'scener': scener,
        'form': form,
    })


@writeable_site_required
@login_required
def remove_group(request, scener_id, group_id):
    scener = get_object_or_404(Releaser, is_group=False, id=scener_id)
    group = get_object_or_404(Releaser, is_group=True, id=group_id)

    if not scener.editable_by_user(request.user):
        raise PermissionDenied

    if request.method == 'POST':
        deletion_type = request.POST.get('deletion_type')
        if deletion_type == 'ex_member':
            # set membership to is_current=False - do not delete
            scener.group_memberships.filter(group=group).update(is_current=False)
            scener.updated_at = datetime.datetime.now()
            scener.save()
            Edit.objects.create(
                action_type='edit_membership', focus=scener, focus2=group,
                description=u"Updated %s's membership of %s: set as ex-member" % (scener.name, group.name),
                user=request.user
            )
            return HttpResponseRedirect(scener.get_absolute_url() + "?editing=groups")
        elif deletion_type == 'full':
            scener.group_memberships.filter(group=group).delete()
            scener.updated_at = datetime.datetime.now()
            scener.save()
            description = u"Removed %s as a member of %s" % (scener.name, group.name)
            Edit.objects.create(
                action_type='remove_membership', focus=scener, focus2=group,
                description=description, user=request.user
            )
            return HttpResponseRedirect(scener.get_absolute_url() + "?editing=groups")
        else:
            show_error_message = True

    else:
        show_error_message = False

    return render(request, 'sceners/remove_group.html', {
        'scener': scener,
        'group': group,
        'show_error_message': show_error_message,
    })


@writeable_site_required
@login_required
def edit_membership(request, scener_id, membership_id):
    scener = get_object_or_404(Releaser, is_group=False, id=scener_id)
    membership = get_object_or_404(Membership, member=scener, id=membership_id)

    if not scener.editable_by_user(request.user):
        raise PermissionDenied

    if request.method == 'POST':
        form = ScenerMembershipForm(request.POST, initial={
            'group_nick': membership.group.primary_nick,
            'is_current': membership.is_current,
        })
        if form.is_valid():
            group = form.cleaned_data['group_nick'].commit().releaser
            if not scener.group_memberships.exclude(id=membership_id).filter(group=group).count():
                membership.group = group
                membership.is_current = form.cleaned_data['is_current']
                membership.save()
                scener.updated_at = datetime.datetime.now()
                scener.save()
                form.log_edit(request.user, scener, group)
            return HttpResponseRedirect(scener.get_absolute_url() + "?editing=groups")
    else:
        form = ScenerMembershipForm(initial={
            'group_nick': membership.group.primary_nick,
            'is_current': membership.is_current,
        })
    return render(
        request, 'sceners/edit_membership.html',
        {
            'scener': scener,
            'membership': membership,
            'form': form,
        }
    )


class ConvertToGroupView(AjaxConfirmationView):
    action_url_path = 'scener_convert_to_group'
    html_title = "Converting %s to a group"
    message = "Are you sure you want to convert %s into a group?"

    def get_object(self, request, scener_id):
        return Releaser.objects.get(id=scener_id, is_group=False)

    def is_permitted(self):
        return self.request.user.is_staff and self.object.can_be_converted_to_group()

    def perform_action(self):
        scener = self.object

        scener.is_group = True
        scener.updated_at = datetime.datetime.now()
        scener.save()
        Edit.objects.create(
            action_type='convert_to_group', focus=scener,
            description=(u"Converted %s from a scener to a group" % scener), user=self.request.user
        )
